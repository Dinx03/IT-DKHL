"""
common.py — ซองจดหมายกลางที่ agent ทุกตัวใช้ร่วมกัน

กฎเหล็ก 3 ข้อ (ละเมิดเมื่อไหร่ ระบบจะ debug ไม่ได้):

  1. agent เป็น pure function — ห้ามเขียน DB ห้ามยิง API ภายนอกเอง
     อยากให้เกิดผลอะไร ให้ return EventDraft / EffectDraft ออกมา
     Orchestrator เป็นคนเขียนลง events และ outbound_jobs เอง

  2. correlation_id / causation_id agent ไม่ตั้งเอง — Orchestrator เติมให้
     agent แค่ประกาศว่า "เหตุการณ์นี้เกิด" ไม่ต้องรู้ว่าตัวเองอยู่ตรงไหนของสาย

  3. ห้ามเชื่อ self-report ของ agent อื่น
     Writer บอกว่า "รูปนี้ไม่ใช่คน AI" → Reach Guard ต้องตรวจเอง ไม่ใช่เชื่อคำบอก
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    """extra='forbid' = ส่งฟิลด์เกินมาแล้วพังทันที ดีกว่าเงียบแล้วเพี้ยนทีหลัง
    frozen=True     = input/output แก้ไม่ได้หลังสร้าง บังคับความเป็น pure function"""

    model_config = ConfigDict(extra="forbid", frozen=True)


Platform = Literal["facebook", "instagram", "tiktok", "line_oa", "x", "linkedin"]
Strategy = Literal["ขายตรง", "ให้ความรู้", "สร้างการรับรู้", "รีวิวและความเชื่อมั่น"]

# ตรงกับ event_types ใน 004_event_store.sql
EventType = Literal[
    "brand.dna_activated", "content.requested", "content.generated",
    "policy.evaluated", "policy.blocked", "content.scheduled",
    "content.published", "content.publish_failed", "metrics.captured",
    "message.received", "message.sent", "rule.matched", "stock.queried",
    "lead.scored", "lead.created", "order.created", "consent.changed",
    "human.intervened", "agent.failed", "conversation.escalated",
]

# ─────────────────────────────────────────────────────────────
# Brand DNA slice — agent แต่ละตัวได้เฉพาะ facet ที่ต้องใช้
# เหตุผลคือค่า token ล้วนๆ: Scorer ไม่ต้องใช้ DNA เลย ถูกลง ~70%
# ─────────────────────────────────────────────────────────────

Facet = Literal[
    "identity", "audience", "voice", "claims_policy",
    "offer", "channel_prefs", "escalation", "learned",
]

FACETS_FOR_AGENT: dict[str, tuple[Facet, ...]] = {
    "strategist":  ("identity", "audience", "offer", "channel_prefs", "learned"),
    "writer":      ("identity", "audience", "voice", "claims_policy", "offer"),
    "reach_guard": ("claims_policy", "voice", "channel_prefs"),
    "concierge":   ("identity", "voice", "offer", "escalation"),
    "scorer":      (),
    "closer":      ("offer", "escalation"),
    "analyst":     ("identity", "audience", "voice", "claims_policy",
                    "offer", "channel_prefs", "escalation", "learned"),
}


class DnaSlice(Strict):
    version_id: UUID
    checksum: str           # ลงใน agent_runs.dna_checksum → reproduce ผลได้
    facets: dict[str, Any]  # เฉพาะ key ที่อยู่ใน FACETS_FOR_AGENT[agent]


# ─────────────────────────────────────────────────────────────
# ซองเข้า
# ─────────────────────────────────────────────────────────────

class Budget(Strict):
    """agent ต้องหยุดเองเมื่อเกิน ไม่ใช่ให้ orchestrator มาฆ่าทีหลัง"""

    max_tokens: int = 8000
    max_thb: Decimal = Decimal("2.00")
    deadline_ms: int = 20_000


class AgentContext(Strict):
    org_id: UUID
    brand_id: UUID
    agent: str
    budget: Budget = Budget()
    locale: str = "th-TH"
    now: datetime
    dry_run: bool = False
    # correlation_id / causation_id จงใจไม่อยู่ที่นี่ — ดูกฎข้อ 2


# ─────────────────────────────────────────────────────────────
# ซองออก
# ─────────────────────────────────────────────────────────────

class EventDraft(Strict):
    """ตรงกับตาราง events — orchestrator เติม correlation_id/causation_id/org_id ให้"""

    type: EventType
    subject_type: str | None = None
    subject_id: str | None = None
    actor_type: Literal["human", "agent", "system", "customer", "platform"] = "agent"
    actor_id: str | None = None
    pii_level: Literal["none", "low", "high"] = "none"
    payload: dict[str, Any] = Field(default_factory=dict)


class EffectDraft(Strict):
    """ตรงกับตาราง outbound_jobs — ผลกระทบต่อโลกภายนอกทุกอย่างต้องผ่านที่นี่
    idempotency_key ต้อง deterministic (hash ของ subject + attempt)
    ไม่ใช่ uuid สุ่ม มิฉะนั้น retry แล้วจะโพสต์ซ้ำจริง"""

    kind: Literal["publish_post", "send_message", "create_erp_lead",
                  "create_erp_so", "fetch_metrics"]
    target: str
    idempotency_key: str
    payload: dict[str, Any]
    requires_approval: bool = True


class Escalation(Strict):
    """ไม่ใช่ error — เป็นผลลัพธ์ที่ถูกต้องชนิดหนึ่ง
    agent ที่รู้ตัวว่าไม่ควรตอบ มีค่ากว่า agent ที่เดา"""

    reason_th: str
    rule: str | None = None       # เช่น '/escalation/never_answer_th[0]'
    suggested_owner: Literal["human", "supervisor_agent"] = "human"
    draft_for_human_th: str | None = None


class AgentError(Strict):
    code: Literal["invalid_input", "model_error", "timeout",
                  "budget_exceeded", "refused", "downstream_error"]
    message: str
    retryable: bool = False


class Usage(Strict):
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_thb: Decimal = Decimal("0")
    latency_ms: int = 0
    tool_calls: int = 0


TOut = TypeVar("TOut", bound=Strict)


class AgentResult(Strict, Generic[TOut]):
    ok: bool
    output: TOut | None = None
    error: AgentError | None = None
    escalate: Escalation | None = None
    events: list[EventDraft] = Field(default_factory=list)
    effects: list[EffectDraft] = Field(default_factory=list)
    usage: Usage


# ─────────────────────────────────────────────────────────────
# ชิ้นส่วนที่ใช้ร่วมหลาย agent
# ─────────────────────────────────────────────────────────────

class KnowledgeSnippet(Strict):
    doc_id: UUID
    chunk_id: UUID
    title: str
    content: str
    category: str
    erp_item_code: str | None = None
    score: float
    valid_until: datetime | None = None


class Turn(Strict):
    role: Literal["customer", "agent", "system"]
    text: str
    at: datetime
