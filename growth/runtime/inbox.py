"""
inbox.py — สายงานของข้อความขาเข้า (สถาปัตยกรรม 2 ชั้น)

    py -m growth.runtime.inbox "น้ำมะเขือเทศยังมีไหม" --channel line --from U123

    ข้อความเข้า
        │
        ├─ บันทึกตัวตนลูกค้า + บทสนทนา + ฐานทางกฎหมาย PDPA
        │
        ├─ ชั้น 1: Auto-Reply (กฎตายตัว ไม่มี LLM)
        │     reply    → ตอบเลย จบ                 ต้นทุน 0
        │     escalate → เข้าคิวรอคนตอบ ห้าม AI แตะ  ต้นทุน 0
        │     none     → ผ่านไปชั้น 2
        │
        └─ ชั้น 2: Concierge
              เฟสนี้ยังเป็นตัวชั่วคราวที่ประกอบคำตอบจาก ERPNext ด้วยเทมเพลต
              เฟสหน้าจะเปลี่ยนเป็น LLM แต่ "ตัวเลขในคำตอบ" มาจากที่เดิม
              ถ้าจับไม่ได้ว่าถามถึงอะไร → เข้าคิวรอคน ไม่เดา

ทุกก้าวลง event ด้วย correlation_id เดียวกัน causation_id ชี้ต่อกันเป็นลูกโซ่
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from datetime import datetime, timezone

from ..agents import closer, concierge, scorer
from ..agents.agents import (CloserInput, ConciergeInput, ContactBrief,
                             ScorerInput)
from ..agents.auto_reply import AutoReplyInput
from ..agents.auto_reply import run as auto_reply_run
from ..agents.common import (AgentContext, AgentResult, EventDraft, Escalation,
                             Turn, Usage)
from . import db, erp, llm, orchestrator, prompts

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass


def _run_concierge(conn, org_id: UUID, brand_id: UUID, conversation_id: UUID,
                   contact_id: UUID, channel: str, text: str) -> AgentResult:
    """Concierge ตัวจริง — เรียกโมเดล + วนเรียก ERP tool เอง
    ถ้ายังไม่มีคีย์โมเดล จะตกไปใช้ StubProvider อัตโนมัติ ระบบจึงรันได้เสมอ"""
    res_meta: dict = {}
    dna = db.load_dna(conn, brand_id, "concierge")
    turns = db.conversation_turns(conn, conversation_id)
    ident = conn.execute(
        """select channel, external_id, display_name from contact_identities
            where contact_id = %s limit 1""", (contact_id,)).fetchone()
    consent = conn.execute(
        """select is_valid from consent_current
            where contact_id = %s and purpose = 'marketing_message'""",
        (contact_id,)).fetchone()

    inp = ConciergeInput(
        ctx=AgentContext(org_id=org_id, brand_id=brand_id, agent="concierge",
                         now=datetime.now(timezone.utc)),
        dna=dna,
        turns=turns or [Turn(role="customer", text=text,
                             at=datetime.now(timezone.utc))],
        contact=ContactBrief(contact_id=contact_id, channel=channel,
                             display_name=(ident or {}).get("display_name"),
                             is_returning=len(turns) > 1,
                             consent_marketing=bool(consent and consent["is_valid"])),
        knowledge=db.knowledge_for(conn, brand_id, text),
        ai_turn_count=sum(1 for t in turns if t.role == "agent"),
    )

    template, _ = prompts.load("concierge")
    res = concierge.run(inp, provider=llm.get_provider(), prompt_template=template,
                        call_tool=erp.call, model=llm.MODEL_FOR["concierge"])
    res_meta.update(prompts.ref("concierge") | {"dna_checksum": dna.checksum})

    for ev in res.events:                       # ผูก event เข้ากับห้องแชท
        object.__setattr__(ev, "subject_id", str(conversation_id))
    return res, res_meta


def _run_scorer(conn, org_id: UUID, brand_id: UUID, conversation_id: UUID,
                text: str) -> AgentResult | None:
    """เรียกเฉพาะตอนคุ้ม — ทุก 3 เทิร์น หรือเจอคำบ่งชี้ว่าใกล้ซื้อ"""
    turns = db.conversation_turns(conn, conversation_id)
    n_customer = sum(1 for t in turns if t.role == "customer")
    if not scorer.should_score(n_customer, text):
        return None

    template, _ = prompts.load("scorer")
    res = scorer.run(
        ScorerInput(ctx=AgentContext(org_id=org_id, brand_id=brand_id,
                                     agent="scorer", now=datetime.now(timezone.utc)),
                    turns=turns, prior_score=db.latest_score(conn, conversation_id)),
        provider=llm.get_provider(), prompt_template=template,
        model=llm.MODEL_FOR["scorer"])
    for ev in res.events:
        object.__setattr__(ev, "subject_id", str(conversation_id))
    if res.ok and res.output:
        db.save_score(conn, conversation_id, res.output, llm.MODEL_FOR["scorer"])
    return res


def _run_closer(conn, org_id: UUID, brand_id: UUID, conversation_id: UUID,
                contact_id: UUID, channel: str, score_out) -> AgentResult | None:
    """เรียกเมื่อคะแนนถึงเกณฑ์ — ตัดสินด้วยกฎ สรุปด้วยโมเดลเล็ก"""
    if score_out.score < closer.SCORE_NURTURE:
        return None
    dna = db.load_dna(conn, brand_id, "closer")
    ident = conn.execute(
        """select display_name from contact_identities
            where contact_id = %s limit 1""", (contact_id,)).fetchone()
    stock = [erp.price_lookup(c) for c in score_out.signals.items[:2]]
    res = closer.run(
        CloserInput(
            ctx=AgentContext(org_id=org_id, brand_id=brand_id, agent="closer",
                             now=datetime.now(timezone.utc)),
            dna=dna, conversation_id=conversation_id,
            contact=ContactBrief(contact_id=contact_id, channel=channel,
                                 display_name=(ident or {}).get("display_name")),
            score=score_out.score, signals=score_out.signals,
            turns=db.conversation_turns(conn, conversation_id), stock=stock),
        provider=llm.get_provider(), prompt_template=prompts.load("closer")[0],
        model=llm.MODEL_FOR["closer"])
    for ev in res.events:
        object.__setattr__(ev, "subject_id", str(conversation_id))
    return res


def handle(text: str, channel: str = "line", sender_id: str = "test-user",
           display_name: str | None = None, chatwoot_id: int | None = None,
           brand: str = "ona-healthy") -> dict:
    with db.connect() as conn:
        org_id, brand_id = db.resolve_brand(conn, brand)
        corr = orchestrator.new_correlation()

        # ── ตัวตนลูกค้าและบทสนทนา ────────────────────────────
        contact_id, is_new = db.upsert_contact(conn, brand_id, channel,
                                               sender_id, display_name)
        conv_id = db.upsert_conversation(conn, brand_id, contact_id,
                                         channel, chatwoot_id)

        # ── บันทึกข้อความขาเข้าก่อนเสมอ ──────────────────────
        # ทุกเส้นทางต้องผ่านตรงนี้ ไม่ว่าจะตอบได้หรือไม่
        # ถ้าขาดไป Analyst จะนับ "คำถามที่ลูกค้าถามบ่อย" ไม่ได้เลย
        ingress = AgentResult(
            ok=True, output=None,
            events=[EventDraft(type="message.received", subject_type="conversation",
                               subject_id=str(conv_id), actor_type="customer",
                               actor_id=sender_id, pii_level="high",
                               payload={"channel": channel, "text": text,
                                        "new_contact": is_new})],
            usage=Usage(model="-"))
        root = orchestrator.commit(conn, ingress, org_id=org_id, brand_id=brand_id,
                                   correlation_id=corr, agent="ingress")

        if is_new:
            # ลูกค้าทักมาเอง = มีฐานให้ประมวลผลข้อมูลเพื่อ "ตอบกลับ"
            # ไม่ใช่ความยินยอมให้ส่งการตลาด — คนละเรื่องกัน
            db.record_inbound_consent(conn, contact_id, channel, root)
            conn.commit()

        base = {"correlation_id": corr, "conversation_id": conv_id,
                "contact_id": contact_id, "new_contact": is_new, "cost": "0 บาท"}

        # ── ชั้น 1 ───────────────────────────────────────────
        rules = db.load_auto_reply_rules(conn, brand_id)
        r1 = auto_reply_run(AutoReplyInput(brand_id=brand_id, channel=channel,
                                           text=text, rules=rules))
        for ev in r1.events:
            object.__setattr__(ev, "subject_id", str(conv_id))
        last = orchestrator.commit(conn, r1, org_id=org_id, brand_id=brand_id,
                                   correlation_id=corr, causation_id=root,
                                   agent="auto_reply", subject_id=str(conv_id))
        out1 = r1.output

        if out1.outcome != "none":
            if out1.matched_rule_id:
                db.bump_rule_hit(conn, out1.matched_rule_id)
            if out1.outcome == "escalate":
                db.handoff(conn, conv_id)
            conn.commit()
            return base | {"layer": "auto_reply", "outcome": out1.outcome,
                           "rule": out1.matched_rule_name, "terms": out1.matched_terms,
                           "reply": out1.reply_th,
                           "escalate": r1.escalate.reason_th if r1.escalate else None}

        # ── ชั้น 2 ───────────────────────────────────────────
        r2, meta2 = _run_concierge(conn, org_id, brand_id, conv_id, contact_id,
                                   channel, text)
        last = orchestrator.commit(conn, r2, org_id=org_id, brand_id=brand_id,
                                   correlation_id=corr, causation_id=last,
                                   agent="concierge", subject_id=str(conv_id),
                                   meta=meta2)
        cost = f"{r2.usage.cost_thb} บาท ({r2.usage.model})"

        # ── ให้คะแนนโอกาสปิด (เรียกเฉพาะตอนคุ้ม) ──────────────
        r3 = _run_scorer(conn, org_id, brand_id, conv_id, text)
        score = None
        if r3 is not None:
            orchestrator.commit(conn, r3, org_id=org_id, brand_id=brand_id,
                                correlation_id=corr, causation_id=last,
                                agent="scorer", subject_id=str(conv_id),
                                meta=dict(prompts.ref("scorer")))
            if r3.ok and r3.output:
                score = r3.output.score
                cost = (f"{r2.usage.cost_thb + r3.usage.cost_thb} บาท "
                        f"({r2.usage.model} + {r3.usage.model})")
        # ── ปิดการขาย: เสนอสร้างลีด (ต้องมีคนกดยืนยันเสมอ) ──
        lead_action = None
        if r3 is not None and r3.ok and r3.output:
            r4 = _run_closer(conn, org_id, brand_id, conv_id, contact_id, channel,
                             r3.output)
            if r4 is not None:
                orchestrator.commit(conn, r4, org_id=org_id, brand_id=brand_id,
                                    correlation_id=corr, causation_id=last,
                                    agent="closer", subject_id=str(conv_id),
                                    meta=dict(prompts.ref("closer")))
                if r4.ok and r4.output:
                    lead_action = r4.output.action
                    if lead_action == "create_lead":
                        db.upsert_lead(conn, brand_id, contact_id, conv_id,
                                       r3.output.score, r4.output.value_thb)
                    cost += f" + {r4.usage.cost_thb}"
        base["lead_action"] = lead_action
        conn.commit()

        if r2.escalate:
            db.handoff(conn, conv_id)
            conn.commit()
            return base | {"layer": "concierge", "outcome": "escalate",
                           "escalate": r2.escalate.reason_th, "cost": cost,
                           "score": score}
        if not r2.ok:
            db.handoff(conn, conv_id)
            conn.commit()
            return base | {"layer": "concierge", "outcome": "error",
                           "escalate": r2.error.message, "cost": cost}
        return base | {"layer": "concierge", "outcome": "reply",
                       "reply": r2.output.reply_th,
                       "grounded_on": r2.output.grounded_on,
                       "needs_human": r2.output.needs_human,
                       "score": score, "cost": cost}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--channel", default="line")
    p.add_argument("--from", dest="sender", default="test-user")
    p.add_argument("--name", default=None)
    p.add_argument("--trace", action="store_true")
    a = p.parse_args()

    res = handle(a.text, a.channel, a.sender, a.name)
    print(f"\n[ลูกค้า · {a.channel} · {a.sender}] {a.text}\n")
    print(f"  ชั้นที่ตอบ : {res['layer']}   ผล: {res['outcome']}   ต้นทุน: {res['cost']}")
    if res["new_contact"]:
        print("  ลูกค้าใหม่ : บันทึกตัวตน + ฐานทางกฎหมาย PDPA แล้ว")
    if res.get("rule"):
        print(f"  กฎที่ตรง  : {res['rule']}  (คำ: {', '.join(res['terms'])})")
    if res.get("escalate"):
        print(f"\n  → เข้าคิวรอคนตอบ: {res['escalate']}")
    if res.get("reply"):
        print("\n" + "\n".join("  " + ln for ln in res["reply"].splitlines()))

    if a.trace:
        with db.connect() as conn:
            print(f"\n  สายเหตุการณ์:")
            for e in orchestrator.trace(conn, res["correlation_id"]):
                t = e["occurred_at"].strftime("%H:%M:%S.%f")[:-3]
                mark = "●" if not e["causation_id"] else "↳"
                print(f"    {t}  {mark} {e['type']:18} {e['actor_id'] or '-'}")
    print()


if __name__ == "__main__":
    main()
