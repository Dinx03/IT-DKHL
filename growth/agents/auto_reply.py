"""
auto_reply.py — ชั้นกฎตายตัว ทำงานก่อน Concierge เสมอ

ไม่ใช่ agent ที่ใช้ LLM — เป็น rule engine ล้วน แต่คืน AgentResult
รูปแบบเดียวกับตัวอื่น เพื่อให้ Orchestrator ปฏิบัติเหมือนกันหมด

ผลลัพธ์มี 4 แบบ:
  reply     ตอบได้เลย จบ ไม่ต้องเรียก AI      → ประหยัดสุด
  escalate  ส่งต่อคนทันที ห้าม AI แตะ          → เรื่องแพ้ยา คืนเงิน ภาษี
  ignore    ไม่ต้องทำอะไร (สแปม)
  none      ไม่เข้ากฎไหนเลย → ส่งต่อให้ Concierge
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal
from uuid import UUID

from .common import AgentResult, EventDraft, Escalation, Strict, Usage


class AutoReplyRule(Strict):
    id: UUID
    name: str
    priority: int
    channels: list[str]
    match_type: Literal["keyword", "regex"]
    match: dict[str, Any]
    action: Literal["reply", "escalate", "ignore"]
    reply_th: str | None = None
    escalate_note_th: str | None = None
    stop_processing: bool = True


class AutoReplyInput(Strict):
    brand_id: UUID
    channel: str
    text: str
    rules: list[AutoReplyRule]


class AutoReplyOutput(Strict):
    outcome: Literal["reply", "escalate", "ignore", "none"]
    reply_th: str | None = None
    matched_rule_id: UUID | None = None
    matched_rule_name: str | None = None
    matched_terms: list[str] = []


def _matches(rule: AutoReplyRule, text: str) -> list[str]:
    """คืนคำที่ตรง — เก็บไว้ลง event ด้วย จะได้รู้ว่ากฎยิงเพราะคำไหน"""
    low = text.casefold()

    if rule.match_type == "regex":
        flags = re.IGNORECASE if "i" in rule.match.get("flags", "") else 0
        m = re.search(rule.match["pattern"], text, flags)
        return [m.group(0)] if m else []

    none_terms = rule.match.get("none", [])
    if any(t.casefold() in low for t in none_terms):
        return []                                  # มีคำห้าม → ไม่นับว่าตรง

    all_terms = rule.match.get("all", [])
    if all_terms and not all(t.casefold() in low for t in all_terms):
        return []

    any_terms = rule.match.get("any", [])
    hits = [t for t in any_terms if t.casefold() in low]
    if any_terms and not hits:
        return []
    return hits or all_terms


def run(inp: AutoReplyInput) -> AgentResult[AutoReplyOutput]:
    started = time.perf_counter()

    for rule in sorted(inp.rules, key=lambda r: r.priority):
        if "*" not in rule.channels and inp.channel not in rule.channels:
            continue
        hits = _matches(rule, inp.text)
        if not hits:
            continue

        out = AutoReplyOutput(
            outcome=rule.action, reply_th=rule.reply_th,
            matched_rule_id=rule.id, matched_rule_name=rule.name,
            matched_terms=hits)

        payload = {"rule_id": str(rule.id), "rule_name": rule.name,
                   "action": rule.action, "matched_terms": hits,
                   "channel": inp.channel}
        events = [EventDraft(type="rule.matched", subject_type="conversation",
                             actor_id="auto_reply", pii_level="low", payload=payload)]

        escalate = None
        if rule.action == "escalate":
            escalate = Escalation(
                reason_th=rule.escalate_note_th or f"เข้ากฎ {rule.name}",
                rule=f"auto_reply:{rule.name}", suggested_owner="human")

        return AgentResult[AutoReplyOutput](
            ok=True, output=out, events=events, escalate=escalate,
            usage=Usage(model="rules-only",
                        latency_ms=int((time.perf_counter() - started) * 1000)))

    # ไม่เข้ากฎไหนเลย — ไม่ใช่ความล้มเหลว เป็นการส่งต่อตามปกติ
    return AgentResult[AutoReplyOutput](
        ok=True, output=AutoReplyOutput(outcome="none"), events=[],
        usage=Usage(model="rules-only",
                    latency_ms=int((time.perf_counter() - started) * 1000)))
