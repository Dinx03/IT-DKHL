"""
strategist.py — วางแผนคอนเทนต์จากของจริงในคลัง

จุดที่ทำให้ต่างจากเครื่องมือการตลาดทั่วไป: แผนผูกกับสต็อกจริงใน ERPNext
เครื่องมืออื่นวางแผนจากปฏิทินและหัวข้อลอยๆ เพราะไม่มีใครเห็นคลังของเรา

กฎที่บังคับหลังโมเดลตอบ (ไม่เชื่อว่า prompt พอ):
  - ห้ามมีโพสต์ "ขายตรง" ของสินค้าที่คงเหลือ 0  → ตัดทิ้งพร้อมเหตุผล
  - ห้ามเกินเพดานความถี่ต่อวัน                  → StrategistOutput validator จับ
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta

from pydantic import BaseModel, Field

from .agents import ContentBrief, InventorySignal, StrategistInput, StrategistOutput
from .common import AgentError, AgentResult, EventDraft, Usage


class PlannedBrief(BaseModel):
    slot_date: str = Field(description="YYYY-MM-DD")
    platforms: list[str]
    topic_th: str
    angle_th: str
    strategy: str = Field(description="ขายตรง | ให้ความรู้ | สร้างการรับรู้ | รีวิวและความเชื่อมั่น")
    product_refs: list[str] = Field(default_factory=list, description="รหัสสินค้าใน ERPNext")
    must_include_th: list[str] = Field(default_factory=list)
    rationale_th: str


class StrategistPlan(BaseModel):
    briefs: list[PlannedBrief]
    digest_th: str


def _fmt_inventory(inv: list[InventorySignal]) -> str:
    if not inv:
        return "- (ไม่มีข้อมูลคลัง)"
    rows = []
    for i in inv:
        exp = (f" หมดอายุอีก {i.days_to_expiry} วัน" if i.days_to_expiry is not None
               else " ไม่ระบุวันหมดอายุ")
        mark = "  ← ห้ามวางแผนขาย" if i.qty_available <= 0 else ""
        rows.append(f"- {i.erp_item_code} ({i.name_th}) คงเหลือ {i.qty_available}"
                    f"{exp} [{i.flag}]{mark}")
    return "\n".join(rows)


def _render(template: str, inp: StrategistInput) -> str:
    f = inp.dna.facets
    perf = ("- (ยังไม่มีโพสต์ที่เผยแพร่ ยังไม่มีข้อมูลผลงาน)"
            if not inp.recent_performance else
            "\n".join(f"- {p.topic} ({p.platform}, {p.strategy}) reach={p.reach} "
                      f"engagement={p.engagement_rate_pct}% ลีด={p.leads_attributed}"
                      for p in inp.recent_performance))
    return (template
            .replace("{brand_name}", f.get("identity", {}).get("display_name", "แบรนด์"))
            .replace("{horizon}", str(inp.horizon_days))
            .replace("{identity}", json.dumps(f.get("identity", {}), ensure_ascii=False))
            .replace("{audience}", json.dumps(f.get("audience", {}), ensure_ascii=False))
            .replace("{max_per_day}", json.dumps(
                f.get("channel_prefs", {}).get("max_posts_per_day", {}), ensure_ascii=False))
            .replace("{inventory}", _fmt_inventory(inp.inventory))
            .replace("{performance}", perf)
            .replace("{goal}", inp.goal_th)
            .replace("{start_date}", str(date.today() + timedelta(days=1))))


def run(inp: StrategistInput, *, provider, prompt_template: str,
        model: str) -> AgentResult[StrategistOutput]:
    started = time.perf_counter()
    try:
        plan, usage = provider.parse(
            model=model, system=_render(prompt_template, inp),
            messages=[{"role": "user",
                       "content": f"วางแผน {inp.horizon_days} วันสำหรับ "
                                  f"{', '.join(inp.platforms)}"}],
            schema=StrategistPlan, max_tokens=4000)
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[StrategistOutput](
            ok=False,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}",
                             retryable=True),
            usage=Usage(model=model,
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="strategist",
                               payload={"error": str(exc)})])

    out_of_stock = {i.erp_item_code for i in inp.inventory if i.qty_available <= 0}
    briefs: list[ContentBrief] = []
    dropped: list[str] = []

    for b in plan.briefs:
        # ตรวจซ้ำหลังโมเดลตอบ — prompt บอกไว้แล้วแต่ไม่เชื่อว่าพอ
        bad = [c for c in b.product_refs if c in out_of_stock]
        if bad and b.strategy == "ขายตรง":
            dropped.append(f"{b.slot_date} {b.topic_th} — ขายตรงสินค้าที่หมด ({', '.join(bad)})")
            continue
        try:
            briefs.append(ContentBrief(
                slot_date=date.fromisoformat(b.slot_date),
                platforms=[p for p in b.platforms if p in inp.platforms],
                topic_th=b.topic_th, angle_th=b.angle_th, strategy=b.strategy,
                product_refs=b.product_refs, must_include_th=b.must_include_th,
                rationale_th=b.rationale_th[:300]))
        except Exception as exc:                               # noqa: BLE001
            dropped.append(f"{b.slot_date} {b.topic_th} — รูปแบบไม่ถูกต้อง ({exc})")

    try:
        out = StrategistOutput(briefs=briefs, digest_th=plan.digest_th,
                               skipped_reasons_th=dropped)
    except ValueError as exc:
        return AgentResult[StrategistOutput](
            ok=False, usage=usage,
            error=AgentError(code="invalid_input", message=str(exc), retryable=True),
            events=[EventDraft(type="agent.failed", actor_id="strategist",
                               payload={"reason": "แผนละเมิดเพดานความถี่",
                                        "detail": str(exc)})])

    return AgentResult[StrategistOutput](
        ok=True, output=out, usage=usage,
        events=[EventDraft(
            type="content.requested", actor_id="strategist",
            payload={"briefs": len(briefs), "dropped": len(dropped),
                     "horizon_days": inp.horizon_days,
                     "dropped_reasons": dropped})])
