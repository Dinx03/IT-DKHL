"""
analyst.py — ปิดลูปการเรียนรู้

อ่านสิ่งที่เกิดขึ้นจริง แล้วเสนอแก้ Brand DNA ผ่าน brand_dna_proposals
คนต้องกดอนุมัติก่อนเสมอ — agent ไม่เคยแก้ DNA เอง

ข้อจำกัดที่บังคับด้วยโค้ด ไม่ใช่แค่ขอใน prompt (DnaProposal validator):
  - ห้ามแตะ /claims_policy (เรื่อง อย. คนแก้เท่านั้น)
  - confidence < 0.6 เสนอไม่ได้
  - evidence ว่างไม่ได้
  - สูงสุด 5 ข้อต่อรอบ

รันกลางคืน ไม่ใช่ทุกข้อความ — เป็น agent ที่แพงที่สุดแต่เรียกน้อยที่สุด
"""

from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from .agents import AnalystInput, AnalystOutput, DnaProposal, Evidence
from .common import AgentError, AgentResult, EventDraft, Usage

MIN_EVENTS = 20     # ต่ำกว่านี้ข้อมูลน้อยเกินจะสรุปอะไรได้


class ProposedChange(BaseModel):
    facet_path: str
    operation: str = Field(description="add | replace | remove")
    value_json: str = Field(description="ค่าใหม่ในรูป JSON string")
    rationale_th: str = Field(max_length=500)
    evidence_refs: list[str] = Field(description="อ้างอิงจากข้อมูลที่ให้มา")
    confidence: float = Field(ge=0, le=1)


class AnalystReport(BaseModel):
    digest_th: str
    changes: list[ProposedChange] = Field(default_factory=list)


def _render(template: str, inp: AnalystInput) -> str:
    perf = "\n".join(
        f"- {p.topic} ({p.platform}/{p.strategy}) reach={p.reach} "
        f"eng={p.engagement_rate_pct}% ลีด={p.leads_attributed}"
        for p in inp.performance) or "- (ยังไม่มีโพสต์ที่เผยแพร่)"
    gs = "\n".join(f"- {g.rule_id}: เจอ {g.hits} ครั้ง บล็อก {g.blocked} ครั้ง"
                   for g in inp.guard_stats) or "- (ยังไม่มี)"
    qs = "\n".join(f"- \"{q.question_th}\" ถาม {q.count} ครั้ง "
                   f"(คลังความรู้ตอบได้ {q.answered_by_kb} ครั้ง)"
                   for q in inp.top_questions) or "- (ยังไม่มี)"
    lo = "\n".join(f"- ลีดคะแนน {l.best_score} stage={l.stage} มูลค่า={l.value_thb}"
                   for l in inp.lead_outcomes) or "- (ยังไม่มีลีด)"
    return (template
            .replace("{window}", f"{inp.window_start} ถึง {inp.window_end}")
            .replace("{dna}", json.dumps(inp.dna.facets, ensure_ascii=False)[:4000])
            .replace("{performance}", perf)
            .replace("{guard_stats}", gs)
            .replace("{questions}", qs)
            .replace("{leads}", lo))


def run(inp: AnalystInput, *, provider, prompt_template: str, model: str,
        event_count: int = 0) -> AgentResult[AnalystOutput]:
    started = time.perf_counter()

    if event_count < MIN_EVENTS:
        # ข้อมูลน้อยเกินจะสรุป — บอกตรงๆ ดีกว่าเสนอสิ่งที่เดาเอา
        return AgentResult[AnalystOutput](
            ok=True,
            output=AnalystOutput(
                digest_th=(f"ข้อมูลยังน้อยเกินไป (มี {event_count} เหตุการณ์ "
                           f"ต้องการอย่างน้อย {MIN_EVENTS}) ยังไม่เสนอแก้อะไร"),
                proposals=[]),
            usage=Usage(model="rules-only",
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="analyst",
                               payload={"reason": "ข้อมูลไม่พอ",
                                        "events": event_count})])

    try:
        report, usage = provider.parse(
            model=model, system=_render(prompt_template, inp),
            messages=[{"role": "user",
                       "content": "สรุปและเสนอแก้ Brand DNA ตามกฎข้างบน"}],
            schema=AnalystReport, max_tokens=3000)
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[AnalystOutput](
            ok=False,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}",
                             retryable=True),
            usage=Usage(model=model,
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="analyst",
                               payload={"error": str(exc)})])

    proposals: list[DnaProposal] = []
    rejected: list[str] = []
    for ch in report.changes:
        try:
            proposals.append(DnaProposal(
                facet_path=ch.facet_path,
                operation=ch.operation,
                value=json.loads(ch.value_json) if ch.value_json else None,
                rationale_th=ch.rationale_th,
                evidence=[Evidence(kind="metric", ref=r) for r in ch.evidence_refs],
                confidence=ch.confidence))
        except Exception as exc:                               # noqa: BLE001
            # validator ปฏิเสธ (แตะ claims_policy / มั่นใจต่ำ / ไม่มีหลักฐาน)
            rejected.append(f"{ch.facet_path}: {exc}")

    try:
        out = AnalystOutput(digest_th=report.digest_th, proposals=proposals[:5])
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[AnalystOutput](
            ok=False, usage=usage,
            error=AgentError(code="invalid_input", message=str(exc)),
            events=[EventDraft(type="agent.failed", actor_id="analyst",
                               payload={"error": str(exc)})])

    return AgentResult[AnalystOutput](
        ok=True, output=out, usage=usage,
        events=[EventDraft(
            type="brand.dna_activated", actor_id="analyst", pii_level="none",
            payload={"stage": "proposed", "accepted": len(out.proposals),
                     "rejected_by_guardrails": rejected,
                     "window": f"{inp.window_start}..{inp.window_end}"})])
