"""
reach_guard.py — ด่านตรวจก่อนเผยแพร่ (เฉพาะชั้นกฎตายตัว)

เฟส 1 ทำเฉพาะ detector ที่ไม่ต้องใช้ LLM: keyword · regex · structural
ครอบ 9 จาก 11 กฎที่ seed ไว้ — ต้นทุนรัน 0 บาท ทดสอบซ้ำได้ผลเดิมทุกครั้ง

สิ่งที่ยังไม่ได้ตรวจในเฟสนี้ (detector_type='llm'):
  - ig.health_claim   เคลมสุขภาพเกินจริง
  - all.unoriginal    เนื้อหาซ้ำของเดิม
จึงรายงาน unevaluated_rules กลับมาด้วยเสมอ — verdict='pass' ในเฟสนี้
แปลว่า "ผ่านชั้นกฎตายตัว" ไม่ใช่ "ปลอดภัยแล้ว"

Guard ไม่เขียนข้อความใหม่เอง โดยตั้งใจ — คืนแค่ finding + fix_hint
ถ้าคนตรวจแก้งานเอง มันจะแก้ให้ผ่านการตรวจของตัวเอง
"""

from __future__ import annotations

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from .agents import Finding, GuardInput, GuardOutput
from .common import AgentError, AgentResult, EventDraft, Usage


class LlmVerdict(BaseModel):
    """รูปร่างที่ให้โมเดลกรอกตอนตรวจกฎที่ตัดสินด้วยกฎตายตัวไม่ได้"""
    risk: int = Field(ge=0, le=100)
    quote_th: str = ""
    reason_th: str = Field(max_length=300)

# น้ำหนักคะแนนความเสี่ยง — ตายตัว ไม่ใช่ให้โมเดลเดา
_WEIGHT = {"block": 35, "warn": 12, "info": 3}


def _find_spans(haystack: str, needle: str) -> tuple[int, int] | None:
    i = haystack.casefold().find(needle.casefold())
    return (i, i + len(needle)) if i >= 0 else None


def _mk(rule, *, span=None, excerpt=None, detector=None) -> Finding:
    return Finding(
        rule_id=rule.id,
        category=rule.category,
        severity=rule.severity,
        detector=detector or rule.detector_type,
        span=span,
        excerpt=excerpt,
        message_th=rule.message_th,
        fix_hint_th=rule.fix_hint_th,
        source_url=rule.source_url,
    )


# ─────────────────────────────────────────────────────────────
# detector แต่ละชนิด
# ─────────────────────────────────────────────────────────────

def _detect_keyword(rule, body: str) -> list[Finding]:
    out = []
    for term in rule.detector.get("any", []):
        span = _find_spans(body, term)
        if span:
            out.append(_mk(rule, span=span, excerpt=body[span[0]:span[1]]))
    return out


def _detect_regex(rule, body: str) -> list[Finding]:
    flags = re.IGNORECASE if "i" in rule.detector.get("flags", "") else 0
    m = re.search(rule.detector["pattern"], body, flags)
    if not m:
        return []
    return [_mk(rule, span=(m.start(), m.end()), excerpt=m.group(0))]


def _detect_structural(rule, inp: GuardInput) -> tuple[list[Finding], bool]:
    """คืน (findings, supported) — supported=False แปลว่ายังไม่ได้เขียนตัวตรวจนี้
    ต้องรายงานออกไป ไม่ใช่เงียบแล้วปล่อยผ่าน"""
    check = rule.detector.get("check")
    draft = inp.draft

    if check == "always":
        return [_mk(rule)], True

    if check in ("media_has_ai_realistic_person",
                 "media_has_ai_realistic_scene_or_person"):
        want_scene = check.endswith("scene_or_person")
        hit = any(
            m.generator and m.generator.startswith("ai:")
            and (m.depicts_realistic_person or (want_scene and m.depicts_realistic_scene))
            for m in draft.media
        )
        if hit and not draft.aigc_label_required:
            return [_mk(rule, excerpt="สื่อ AI สมจริงแต่ไม่ตั้งธง aigc")], True
        if hit and draft.aigc_label_required:
            return [], True          # มีสื่อ AI แต่ติดป้ายแล้ว ผ่าน
        return [], True

    if check == "posts_per_day_exceeds":
        limits: dict[str, Any] = (
            inp.dna.facets.get("channel_prefs", {}).get("max_posts_per_day", {}))
        cap = limits.get(inp.platform)
        if cap is None:
            return [], True
        if inp.scheduled_same_day + 1 > int(cap):
            return [_mk(rule, excerpt=f"วันนั้นจะมี {inp.scheduled_same_day + 1} โพสต์ "
                                      f"เพดานตั้งไว้ {cap}")], True
        return [], True

    return [], False


# ─────────────────────────────────────────────────────────────
# ตัว agent
# ─────────────────────────────────────────────────────────────

def _detect_llm(rule, inp: GuardInput, provider, prompts_load) -> tuple[list[Finding], Usage]:
    """เรียกโมเดลเฉพาะกฎที่ตัดสินด้วยคำตายตัวไม่ได้ เช่น เคลมสรรพคุณ
    เรียกหลังกฎถูกๆ ผ่านหมดแล้วเท่านั้น"""
    key = rule.detector.get("prompt_key") or rule.id.replace(".", "_")
    threshold = int(rule.detector.get("threshold", 60))
    template, _ = prompts_load(key)      # ไม่มีไฟล์ → FileNotFoundError ให้ผู้เรียกจัดการ

    content = inp.draft.body
    if rule.detector.get("compare_against"):
        # กฎความซ้ำต้องเห็นของเดิมถึงจะตัดสินได้ ส่งแค่ข้อความใหม่ไม่พอ
        if not inp.recent_posts:
            return [], Usage(model="rules-only")   # ยังไม่มีของเดิมให้เทียบ ถือว่าไม่ซ้ำ
        olds = "\n\n".join(f"[{i + 1}] {p.body[:400]}"
                           for i, p in enumerate(inp.recent_posts[:8]))
        content = (f"## โพสต์ใหม่ที่จะลง\n{inp.draft.body}\n\n"
                   f"## โพสต์เดิมของแบรนด์\n{olds}")

    v, usage = provider.parse(
        model=rule.detector.get("model", "gemini-2.5-flash-lite"),
        system=template,
        messages=[{"role": "user", "content": content}],
        schema=LlmVerdict, max_tokens=400)
    if v.risk < threshold:
        return [], usage
    span = None
    if v.quote_th and v.quote_th in inp.draft.body:
        i = inp.draft.body.index(v.quote_th)
        span = (i, i + len(v.quote_th))
    return [Finding(
        rule_id=rule.id, category=rule.category, severity=rule.severity,
        detector="llm", span=span, excerpt=v.quote_th or None,
        message_th=f"{rule.message_th} — {v.reason_th}",
        fix_hint_th=rule.fix_hint_th, source_url=rule.source_url,
        confidence=round(v.risk / 100, 2))], usage


def run(inp: GuardInput, *, provider=None, prompts_load=None) -> AgentResult[GuardOutput]:
    started = time.perf_counter()
    findings: list[Finding] = []
    llm_usage = Usage(model="rules-only")
    used_llm = False
    unevaluated: list[str] = []     # กฎที่ต้องใช้ LLM แต่ยังไม่มีโมเดลให้เรียก
    unsupported: list[str] = []     # structural check ที่ยังไม่ได้เขียนตัวตรวจ

    try:
        for rule in inp.rules:
            if rule.detector_type == "keyword":
                findings += _detect_keyword(rule, inp.draft.body)
            elif rule.detector_type == "regex":
                findings += _detect_regex(rule, inp.draft.body)
            elif rule.detector_type == "structural":
                got, supported = _detect_structural(rule, inp)
                findings += got
                if not supported:
                    unsupported.append(rule.id)
            elif rule.detector_type == "llm":
                if provider is None or prompts_load is None:
                    unevaluated.append(rule.id)   # ไม่มีโมเดล ก็บอกตรงๆ ว่ายังไม่ได้ตรวจ
                    continue
                try:
                    got, u = _detect_llm(rule, inp, provider, prompts_load)
                except FileNotFoundError:
                    # prompt ของกฎนี้ยังไม่ได้เขียน — ข้ามกฎเดียว ไม่ล้มทั้งด่าน
                    # และต้องรายงานออกไป ไม่ใช่เงียบแล้วปล่อยผ่าน
                    unevaluated.append(rule.id)
                    continue
                findings += got
                llm_usage = Usage(
                    model=u.model,
                    prompt_tokens=llm_usage.prompt_tokens + u.prompt_tokens,
                    completion_tokens=llm_usage.completion_tokens + u.completion_tokens,
                    cost_thb=llm_usage.cost_thb + u.cost_thb,
                    latency_ms=u.latency_ms)
                used_llm = True
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[GuardOutput](
            ok=False,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}"),
            usage=Usage(model="rules-only",
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="reach_guard",
                               payload={"error": str(exc)})],
        )

    score = min(100, sum(_WEIGHT[f.severity] for f in findings))
    if any(f.severity == "block" for f in findings):
        verdict = "block"
    elif any(f.severity == "warn" for f in findings):
        verdict = "rewrite"
    else:
        verdict = "pass"

    out = GuardOutput(
        verdict=verdict,
        risk_score=score,
        findings=findings,
        deterministic_only=not used_llm,
        ruleset_hash=inp.ruleset_hash,
    )

    payload = {
        "platform": inp.platform,
        "verdict": verdict,
        "risk_score": score,
        "ruleset_hash": inp.ruleset_hash,
        "rules_checked": len(inp.rules) - len(unevaluated),
        "findings": [
            {"rule_id": f.rule_id, "severity": f.severity, "excerpt": f.excerpt}
            for f in findings
        ],
        "unevaluated_llm_rules": unevaluated,
        "unsupported_checks": unsupported,
    }
    events = [EventDraft(
        type="policy.blocked" if verdict == "block" else "policy.evaluated",
        subject_type="content_variant",
        actor_id="reach_guard",
        payload=payload,
    )]

    return AgentResult[GuardOutput](
        ok=True,
        output=out,
        events=events,
        usage=Usage(model=llm_usage.model if used_llm else "rules-only",
                    prompt_tokens=llm_usage.prompt_tokens,
                    completion_tokens=llm_usage.completion_tokens,
                    cost_thb=llm_usage.cost_thb,
                    latency_ms=int((time.perf_counter() - started) * 1000)),
    )
