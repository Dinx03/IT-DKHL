"""
concierge.py — ตอบแชทลูกค้า โดยห้ามเดาตัวเลขเด็ดขาด

รูปแบบ: วนเรียก tool เองแบบ manual loop ไม่ใช้ tool runner ของ SDK
เหตุผล: กฎเหล็กข้อ 1 — agent ห้ามลงมือทำอะไรเอง
        ถ้าปล่อยให้ SDK เรียก tool ตรงๆ ผลจะไม่ผ่าน ToolResult contract
        เราจะไม่รู้ว่าคำตอบอ้างอิงอะไร และ as_of เท่าไหร่

กฎที่บังคับด้วยโค้ด ไม่ใช่แค่ขอไว้ใน prompt:
  - ตอบเป็นตัวเลขเรื่องราคา/สต็อก/ล็อต ต้องมี erp.* ใน grounded_on
    (ConciergeOutput._facts_must_be_grounded จะโยน error ถ้าไม่มี)
  - ข้อมูลเก่าเกิน MAX_STALENESS_S ห้ามใช้ตอบ
  - เกิน max_ai_turns_before_offer_human แล้วต้องเสนอส่งต่อคน
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .agents import ConciergeInput, ConciergeOutput
from .common import AgentError, AgentResult, EventDraft, Escalation, Usage
from .tools import MAX_STALENESS_S, ToolCall, ToolResult

MAX_TOOL_ROUNDS = 3          # กันวนไม่จบ ค่าจ้างบานและลูกค้ารอ

# ชื่อ tool ฝั่งโมเดลใช้ _ ส่วนฝั่งเราใช้ . — แปลงตรงนี้จุดเดียว
_WIRE_TO_TOOL = {
    "erp_stock_lookup": "erp.stock_lookup",
    "erp_batch_lookup": "erp.batch_lookup",
    "erp_price_lookup": "erp.price_lookup",
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "erp_stock_lookup",
        "description": "ดูจำนวนคงเหลือจริงของสินค้าในคลัง ต้องเรียกก่อนบอกลูกค้าว่ามีของหรือไม่",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"erp_item_code": {"type": "string", "description": "รหัสสินค้า เช่น ONATO-JUICE-75"}},
            "required": ["erp_item_code"], "additionalProperties": False,
        },
    },
    {
        "name": "erp_price_lookup",
        "description": "ดูราคาขายจริงของสินค้า ต้องเรียกก่อนบอกราคาทุกครั้ง",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"erp_item_code": {"type": "string"}},
            "required": ["erp_item_code"], "additionalProperties": False,
        },
    },
    {
        "name": "erp_batch_lookup",
        "description": "ดูล็อตและวันหมดอายุจริง ต้องเรียกก่อนตอบเรื่องวันหมดอายุ",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"erp_item_code": {"type": "string"}},
            "required": ["erp_item_code"], "additionalProperties": False,
        },
    },
]


def _render_prompt(template: str, inp: ConciergeInput) -> str:
    f = inp.dna.facets
    esc = f.get("escalation", {})
    kn = "\n".join(f"- {k.title}: {k.content[:400]}" for k in inp.knowledge) or "- (ยังไม่มี)"
    return (template
            .replace("{brand_name}", f.get("identity", {}).get("display_name", "แบรนด์"))
            .replace("{identity}", json.dumps(f.get("identity", {}), ensure_ascii=False))
            .replace("{voice}", json.dumps(f.get("voice", {}), ensure_ascii=False))
            .replace("{never_answer}", "\n".join(f"- {x}" for x in esc.get("never_answer_th", [])))
            .replace("{handoff_when}", "\n".join(f"- {x}" for x in esc.get("handoff_to_human_when_th", [])))
            .replace("{knowledge}", kn))


def _stale(r: ToolResult, now: datetime) -> bool:
    limit = MAX_STALENESS_S.get(r.name, 600)
    return (now - r.as_of).total_seconds() > limit


def run(inp: ConciergeInput, *, provider, prompt_template: str,
        call_tool: Callable[[ToolCall], ToolResult],
        model: str) -> AgentResult[ConciergeOutput]:
    started = time.perf_counter()
    system = _render_prompt(prompt_template, inp)

    messages: list[dict[str, Any]] = [
        {"role": "user" if t.role == "customer" else "assistant", "content": t.text}
        for t in inp.turns
    ]
    grounded: list[str] = []
    events: list[EventDraft] = []
    total = Usage(model=model)
    tool_rounds = 0

    esc_cfg = inp.dna.facets.get("escalation", {})
    max_turns = int(esc_cfg.get("max_ai_turns_before_offer_human", 8))

    try:
        while True:
            c = provider.complete(model=model, system=system, messages=messages,
                                  tools=TOOL_SCHEMAS, max_tokens=1500)
            total = Usage(
                model=model,
                prompt_tokens=total.prompt_tokens + c.usage.prompt_tokens,
                completion_tokens=total.completion_tokens + c.usage.completion_tokens,
                cached_tokens=total.cached_tokens + c.usage.cached_tokens,
                cost_thb=total.cost_thb + c.usage.cost_thb,
                latency_ms=int((time.perf_counter() - started) * 1000),
                tool_calls=total.tool_calls + len(c.tool_uses))

            if c.stop_reason == "refusal":
                return AgentResult[ConciergeOutput](
                    ok=True, output=None, usage=total,
                    escalate=Escalation(
                        reason_th=f"โมเดลปฏิเสธคำขอ ({c.refusal_category or 'ไม่ระบุ'})",
                        suggested_owner="human"),
                    events=[EventDraft(type="agent.failed", actor_id="concierge",
                                       payload={"refusal": c.refusal_category})])

            if not c.tool_uses:
                break

            if tool_rounds >= MAX_TOOL_ROUNDS:
                return AgentResult[ConciergeOutput](
                    ok=True, output=None, usage=total,
                    escalate=Escalation(
                        reason_th=f"เรียกเครื่องมือเกิน {MAX_TOOL_ROUNDS} รอบแล้วยังตอบไม่ได้",
                        suggested_owner="human"),
                    events=[EventDraft(type="agent.failed", actor_id="concierge",
                                       payload={"reason": "tool_loop_exhausted"})])
            tool_rounds += 1

            messages.append({"role": "assistant", "content": c.raw_content or [
                {"type": "tool_use", "id": t.id, "name": t.name, "input": t.input}
                for t in c.tool_uses]})

            results_blocks = []
            now = datetime.now(timezone.utc)
            for tu in c.tool_uses:
                name = _WIRE_TO_TOOL.get(tu.name)
                if name is None:
                    results_blocks.append({"type": "tool_result", "tool_use_id": tu.id,
                                           "is_error": True,
                                           "content": f"ไม่รู้จักเครื่องมือ {tu.name}"})
                    continue
                res = call_tool(ToolCall(name=name, args=tu.input, why_th="ตอบคำถามลูกค้า"))
                if res.ok and _stale(res, now):
                    res = res.model_copy(update={"ok": False, "data": None,
                                                 "error": "ข้อมูลเก่าเกินกำหนด ต้องดึงใหม่"})
                if res.ok:
                    grounded.append(res.ref)
                events.append(EventDraft(
                    type="stock.queried", subject_type="conversation", actor_id="concierge",
                    payload={"tool": res.name, "args": res.args, "ok": res.ok,
                             "as_of": res.as_of.isoformat()}))
                results_blocks.append({
                    "type": "tool_result", "tool_use_id": tu.id, "is_error": not res.ok,
                    "content": json.dumps(res.data if res.ok else {"error": res.error},
                                          ensure_ascii=False, default=str)})
            messages.append({"role": "user", "content": results_blocks})

    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[ConciergeOutput](
            ok=False, usage=total,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}",
                             retryable=True),
            events=[EventDraft(type="agent.failed", actor_id="concierge",
                               payload={"error": str(exc)})])

    needs_human = inp.ai_turn_count + 1 >= max_turns
    try:
        out = ConciergeOutput(
            reply_th=c.text or None, grounded_on=grounded,
            needs_human=needs_human,
            needs_human_reason_th=("คุยกับ AI มานานแล้ว ควรให้คนรับช่วง"
                                   if needs_human else None),
            confidence=0.8 if grounded else 0.5)
    except ValueError as exc:
        # validator จับได้ว่าโมเดลตอบตัวเลขโดยไม่มีหลักฐาน — ห้ามส่งออกเด็ดขาด
        return AgentResult[ConciergeOutput](
            ok=True, output=None, usage=total,
            escalate=Escalation(
                reason_th=f"คำตอบมีตัวเลขแต่ไม่มีหลักฐานจาก ERPNext ({exc})",
                suggested_owner="human", draft_for_human_th=c.text),
            events=events + [EventDraft(type="agent.failed", actor_id="concierge",
                                        payload={"reason": "ungrounded_numbers",
                                                 "draft": c.text[:500]})])

    events.append(EventDraft(type="message.sent", subject_type="conversation",
                             actor_id="concierge", pii_level="low",
                             payload={"grounded_on": grounded,
                                      "tool_rounds": tool_rounds,
                                      "cost_thb": str(total.cost_thb),
                                      "text": out.reply_th}))
    return AgentResult[ConciergeOutput](ok=True, output=out, events=events, usage=total)
