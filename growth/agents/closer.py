"""
closer.py — เสนอสร้างลีด/ออเดอร์ใน ERPNext เมื่อบทสนทนาสุกงอม

แบ่งงานระหว่างกฎกับโมเดลอย่างตั้งใจ:
  - **การตัดสินใจ** ว่าจะสร้างลีดไหม → กฎตายตัวจากคะแนน ไม่ให้โมเดลตัดสิน
    เพราะเป็นเรื่องเชิงกลไก และต้องอธิบายได้ว่าทำไมถึงสร้าง
  - **การสรุปให้คนอ่าน** → โมเดลเล็ก เพราะคนที่กดอนุมัติต้องเข้าใจใน 3 บรรทัด

Closer ไม่เคยเขียน ERPNext เอง — คืน EffectDraft เข้าคิว outbound_jobs
แล้วคนต้องกดยืนยันในหน้าศูนย์กลางก่อน worker ถึงจะลงมือ
CloserOutput._money_needs_a_human บังคับข้อนี้ไว้ที่ระดับ type
"""

from __future__ import annotations

import hashlib
import time
from decimal import Decimal

from .agents import CloserInput, CloserOutput
from .common import AgentError, AgentResult, EffectDraft, EventDraft, Usage

# เกณฑ์ตัดสิน — เปิดเผยและปรับได้ ไม่ซ่อนอยู่ในโมเดล
SCORE_CREATE_LEAD = 70      # ตั้งแต่นี้ขึ้นไป เสนอสร้างลีด
SCORE_NURTURE = 40          # 40-69 ยังไม่สร้าง แต่ควรตามต่อ


def _decide(score: int, intent: str) -> str:
    if intent in ("complaint", "spam", "support"):
        return "none"
    if score >= SCORE_CREATE_LEAD:
        return "create_lead"
    if score >= SCORE_NURTURE:
        return "nurture"
    return "none"


def run(inp: CloserInput, *, provider, prompt_template: str,
        model: str) -> AgentResult[CloserOutput]:
    started = time.perf_counter()
    action = _decide(inp.score, inp.signals.intent)

    if action in ("none", "nurture"):
        return AgentResult[CloserOutput](
            ok=True,
            output=CloserOutput(action=action, summary_th=(
                f"คะแนน {inp.score} — "
                + ("ยังไม่ถึงเกณฑ์สร้างลีด ควรตามต่อ" if action == "nurture"
                   else "ยังไม่ต้องทำอะไร")),
                value_thb=None),
            usage=Usage(model="rules-only",
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="lead.scored", subject_type="conversation",
                               actor_id="closer", pii_level="low",
                               payload={"score": inp.score, "action": action})])

    # สรุปให้คนที่ต้องกดอนุมัติอ่าน — ใช้โมเดลเล็ก
    convo = "\n".join(f"{'ลูกค้า' if t.role == 'customer' else 'ร้าน'}: {t.text}"
                      for t in inp.turns)
    try:
        from pydantic import BaseModel, Field

        class _Summary(BaseModel):
            summary_th: str = Field(max_length=400)

        parsed, usage = provider.parse(
            model=model, system=prompt_template,
            messages=[{"role": "user", "content": convo}],
            schema=_Summary, max_tokens=400)
        summary = parsed.summary_th
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[CloserOutput](
            ok=False,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}",
                             retryable=True),
            usage=Usage(model=model,
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="closer",
                               payload={"error": str(exc)})])

    # ประเมินมูลค่าจากราคาจริงที่ดึงมาแล้ว ไม่ให้โมเดลเดาตัวเลขเงิน
    value: Decimal | None = None
    qty = inp.signals.qty or 0
    for r in inp.stock:
        if r.ok and r.name == "erp.price_lookup" and qty:
            value = Decimal(str(r.data["rate"])) * qty
            break

    payload = {
        "lead_name": inp.contact.display_name or f"ลูกค้า {inp.contact.channel}",
        "source": f"chat:{inp.contact.channel}",
        "summary_th": summary,
        "closing_score": inp.score,
        "items": inp.signals.items,
        "qty": inp.signals.qty,
        "conversation_id": str(inp.conversation_id),
    }
    out = CloserOutput(action="create_lead", erp_payload=payload, value_thb=value,
                       summary_th=summary, requires_approval=True)

    # idempotency_key ต้องคงที่ — retry แล้วต้องไม่สร้างลีดซ้ำ
    key = hashlib.sha256(
        f"lead:{inp.conversation_id}:{inp.contact.contact_id}".encode()).hexdigest()[:32]

    return AgentResult[CloserOutput](
        ok=True, output=out, usage=usage,
        effects=[EffectDraft(kind="create_erp_lead", target="erpnext",
                             idempotency_key=key, payload=payload,
                             requires_approval=True)],
        events=[EventDraft(type="lead.created", subject_type="conversation",
                           actor_id="closer", pii_level="low",
                           payload={"score": inp.score, "action": "create_lead",
                                    "value_thb": str(value) if value else None,
                                    "awaiting_approval": True})])
