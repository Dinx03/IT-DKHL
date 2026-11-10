"""
scorer.py — ให้คะแนนโอกาสปิดการขายจากบทสนทนา

โมเดลเล็กที่สุดในระบบ และไม่ได้ Brand DNA เลย (ดู FACETS_FOR_AGENT)
การประเมินว่า "ลูกค้าใกล้ซื้อไหม" ไม่ต้องรู้จักแบรนด์ — ดูเจตนาอย่างเดียว
จึงเป็น agent ที่ถูกที่สุดทั้งที่เรียกบ่อยที่สุด

นโยบายการเรียก (อย่าเรียกทุกข้อความ):
  - ทุก 3 เทิร์นของลูกค้า
  - หรือทันทีเมื่อเจอคำบ่งชี้ใน TRIGGER_WORDS
  - หรือเมื่อบทสนทนาปิด
"""

from __future__ import annotations

import time

from .agents import ScorerInput, ScorerOutput
from .common import AgentError, AgentResult, EventDraft, Usage

TRIGGER_WORDS = ("สั่ง", "ซื้อ", "โอน", "เท่าไหร่", "ราคา", "ส่งเมื่อไหร่",
                 "ค่าส่ง", "เลขบัญชี", "พร้อมเพย์", "เก็บปลายทาง")


def should_score(customer_turns: int, latest_text: str, closed: bool = False) -> bool:
    if closed or customer_turns % 3 == 0:
        return True
    return any(w in latest_text for w in TRIGGER_WORDS)


def run(inp: ScorerInput, *, provider, prompt_template: str,
        model: str) -> AgentResult[ScorerOutput]:
    started = time.perf_counter()
    convo = "\n".join(f"{'ลูกค้า' if t.role == 'customer' else 'ร้าน'}: {t.text}"
                      for t in inp.turns)
    try:
        parsed, usage = provider.parse(
            model=model, system=prompt_template,
            messages=[{"role": "user", "content": convo}],
            schema=ScorerOutput, max_tokens=600)
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[ScorerOutput](
            ok=False,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}",
                             retryable=True),
            usage=Usage(model=model,
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="scorer",
                               payload={"error": str(exc)})])

    jump = (parsed.score - inp.prior_score) if inp.prior_score is not None else None
    return AgentResult[ScorerOutput](
        ok=True, output=parsed, usage=usage,
        events=[EventDraft(
            type="lead.scored", subject_type="conversation", actor_id="scorer",
            pii_level="low",
            payload={"score": parsed.score, "prior": inp.prior_score, "delta": jump,
                     "intent": parsed.signals.intent,
                     "urgency": parsed.signals.urgency,
                     "blockers": parsed.signals.blockers_th})])
