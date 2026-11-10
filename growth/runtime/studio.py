"""
studio.py — สายงานคอนเทนต์

    py -m growth.runtime.studio plan --days 3
    py -m growth.runtime.studio write "ที่มาของมะเขือเทศในขวด" --platform instagram

    Strategist ──briefs──> Writer ──draft──> Reach Guard
                              ↑                  │
                              └──GuardFeedback───┤ verdict != pass (สูงสุด 2 รอบ)
                                                 │
                                                 ├ pass  → เก็บเป็น content_variant (guarded)
                                                 └ block → เก็บเป็น blocked + ให้คนตัดสิน

Guard ไม่เขียนใหม่เอง Writer ไม่ตรวจงานตัวเอง — แยกบทบาทโดยตั้งใจ
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from ..agents import reach_guard, strategist, writer
from ..agents.agents import (ContentBrief, GuardInput, InventorySignal,
                             StrategistInput, WriterInput)
from ..agents.common import AgentContext
from . import db, erp, llm, orchestrator, prompts

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

MAX_REWRITES = 2        # เขียนใหม่ได้ 2 รอบ แล้วส่งให้คนตัดสิน


def inventory_signals(conn, brand_id: UUID) -> list[InventorySignal]:
    """สร้างสัญญาณคลังจาก ERPNext จริง — นี่คือสิ่งที่ทำให้แผนผูกกับของที่มีอยู่"""
    rows = conn.execute(
        """select erp_item_code, title from knowledge_docs
            where brand_id = %s and category = 'product'
              and erp_item_code is not null order by erp_item_code""",
        (brand_id,)).fetchall()
    out: list[InventorySignal] = []
    for r in rows:
        code = r["erp_item_code"]
        s, b = erp.stock_lookup(code), erp.batch_lookup(code)
        qty = Decimal(str(s.data["qty_available"])) if s.ok else Decimal(0)
        days = None
        if b.ok and b.data["batches"]:
            days = b.data["batches"][0]["days_to_expiry"]
        if qty <= 0:
            flag = "low_stock"
        elif days is not None and days < 90:
            flag = "expiring_soon"
        elif qty > 200:
            flag = "overstock"
        else:
            flag = "normal"
        out.append(InventorySignal(
            erp_item_code=code, name_th=r["title"], qty_available=qty,
            nearest_expiry=(b.data["nearest_expiry"] if b.ok else None),
            days_to_expiry=days, flag=flag))
    return out


# ─────────────────────────────────────────────────────────────

def plan(days: int = 3, goal: str = "เพิ่มการรับรู้และยอดขายน้ำมะเขือเทศ",
         platforms: list[str] | None = None, brand: str = "ona-healthy") -> dict:
    platforms = platforms or ["instagram", "facebook"]
    with db.connect() as conn:
        org_id, brand_id = db.resolve_brand(conn, brand)
        dna = db.load_dna(conn, brand_id, "strategist")
        corr = orchestrator.new_correlation()

        inv = inventory_signals(conn, brand_id)
        res = strategist.run(
            StrategistInput(
                ctx=AgentContext(org_id=org_id, brand_id=brand_id, agent="strategist",
                                 now=datetime.now(timezone.utc)),
                dna=dna, goal_th=goal, horizon_days=days, platforms=platforms,
                inventory=inv),
            provider=llm.get_provider(), prompt_template=prompts.load("strategist")[0],
            model=llm.MODEL_FOR["strategist"])

        orchestrator.commit(conn, res, org_id=org_id, brand_id=brand_id,
                            correlation_id=corr, agent="strategist",
                            meta=prompts.ref("strategist") | {"dna_checksum": dna.checksum})
        conn.commit()

    if not res.ok:
        return {"ok": False, "error": res.error.message, "correlation_id": corr}
    return {"ok": True, "briefs": res.output.briefs, "digest": res.output.digest_th,
            "dropped": res.output.skipped_reasons_th, "cost": res.usage.cost_thb,
            "in_stock": sum(1 for i in inv if i.qty_available > 0), "total_items": len(inv),
            "correlation_id": corr}


def write(brief: ContentBrief, platform: str, brand: str = "ona-healthy",
          persist: bool = True) -> dict:
    """เขียน → ตรวจ → เขียนใหม่ตาม feedback จนผ่านหรือหมดรอบ"""
    with db.connect() as conn:
        org_id, brand_id = db.resolve_brand(conn, brand)
        dna_w = db.load_dna(conn, brand_id, "writer")
        dna_g = db.load_dna(conn, brand_id, "reach_guard")
        rules = db.load_rules(conn, platform)
        rhash = db.ruleset_hash(rules)
        corr = orchestrator.new_correlation()
        last_ev = None

        knowledge = db.knowledge_for(conn, brand_id, brief.topic_th)
        ctx_w = AgentContext(org_id=org_id, brand_id=brand_id, agent="writer",
                             now=datetime.now(timezone.utc))
        ctx_g = ctx_w.model_copy(update={"agent": "reach_guard"})

        attempts: list[dict] = []
        feedback = None
        total_cost = Decimal(0)

        for attempt in range(1, MAX_REWRITES + 2):
            wres = writer.run(
                WriterInput(ctx=ctx_w, dna=dna_w, brief=brief, platform=platform,
                            knowledge=knowledge, attempt=attempt,
                            guard_feedback=feedback),
                provider=llm.get_provider(), prompt_template=prompts.load("writer")[0],
                model=llm.MODEL_FOR["writer"])
            last_ev = orchestrator.commit(
                conn, wres, org_id=org_id, brand_id=brand_id, correlation_id=corr,
                causation_id=last_ev, agent="writer",
                meta=prompts.ref("writer") | {"dna_checksum": dna_w.checksum,
                                              "attempt": attempt})
            total_cost += wres.usage.cost_thb
            if not wres.ok:
                conn.commit()
                return {"ok": False, "error": wres.error.message,
                        "correlation_id": corr, "cost": total_cost}

            draft = wres.output
            gres = reach_guard.run(GuardInput(
                ctx=ctx_g, dna=dna_g, platform=platform, draft=draft,
                rules=rules, ruleset_hash=rhash,
                recent_posts=db.load_recent_posts(conn, brand_id, platform),
                scheduled_same_day=db.count_scheduled_same_day(
                    conn, brand_id, platform, brief.slot_date)),
                provider=llm.get_provider(), prompts_load=prompts.load)
            last_ev = orchestrator.commit(
                conn, gres, org_id=org_id, brand_id=brand_id, correlation_id=corr,
                causation_id=last_ev, agent="reach_guard")

            g = gres.output
            attempts.append({"attempt": attempt, "verdict": g.verdict,
                             "risk": g.risk_score, "body": draft.body,
                             "findings": [f.rule_id for f in g.findings],
                             "fixable": g.fixable_by_rewrite})

            if g.verdict == "pass":
                break
            if attempt > MAX_REWRITES or not g.fixable_by_rewrite:
                break
            feedback = g.to_feedback(attempt + 1)

        variant_id = None
        if persist:
            item = conn.execute(
                """insert into content_items (brand_id, dna_version, topic, brief,
                                              strategy, status, created_by)
                   values (%s, %s, %s, %s, %s, %s, 'agent:strategist') returning id""",
                (brand_id, dna_w.version_id, brief.topic_th, brief.angle_th,
                 brief.strategy, "review" if g.verdict == "pass" else "failed")).fetchone()
            variant_id = conn.execute(
                """insert into content_variants (content_id, platform, body, hashtags,
                                                 status, scheduled_at)
                   values (%s, %s, %s, %s, %s, %s) returning id""",
                (item["id"], platform, draft.body, draft.hashtags,
                 "guarded" if g.verdict == "pass" else "blocked",
                 brief.slot_date)).fetchone()["id"]
            for a in attempts:
                conn.execute(
                    """insert into policy_evaluations
                         (variant_id, attempt, ruleset_hash, verdict, risk_score,
                          findings, body_before, evaluated_by)
                       values (%s, %s, %s, %s, %s, %s, %s, 'agent:reach_guard')""",
                    (variant_id, a["attempt"], rhash, a["verdict"], a["risk"],
                     json.dumps([{"rule_id": r} for r in a["findings"]]), a["body"]))
        conn.commit()

    return {"ok": True, "verdict": g.verdict, "attempts": attempts,
            "body": draft.body, "hashtags": draft.hashtags,
            "variant_id": variant_id, "cost": total_cost, "correlation_id": corr}


# ─────────────────────────────────────────────────────────────

def _print_plan(r: dict) -> None:
    if not r["ok"]:
        print(f"  วางแผนไม่สำเร็จ: {r['error']}")
        return
    print(f"\n  {r['digest']}")
    print(f"  สินค้าที่มีของจริง {r['in_stock']} จาก {r['total_items']} รายการ"
          f" · ต้นทุน {r['cost']} บาท\n")
    for b in r["briefs"]:
        print(f"  {b.slot_date}  {'/'.join(b.platforms):20} [{b.strategy}]")
        print(f"     {b.topic_th} — {b.angle_th}")
        print(f"     สินค้า: {', '.join(b.product_refs) or '-'}")
        print(f"     เหตุผล: {b.rationale_th}\n")
    if r["dropped"]:
        print("  ตัดออกเพราะผิดกฎ:")
        for d in r["dropped"]:
            print(f"     {d}")


def _print_write(r: dict) -> None:
    if not r["ok"]:
        print(f"  เขียนไม่สำเร็จ: {r['error']}")
        return
    for a in r["attempts"]:
        mark = {"pass": "ผ่าน", "rewrite": "ต้องแก้", "block": "ไม่ผ่าน"}[a["verdict"]]
        print(f"\n  ── รอบที่ {a['attempt']}: {mark} (เสี่ยง {a['risk']}/100) ──")
        for ln in a["body"].splitlines():
            print(f"     {ln}")
        if a["findings"]:
            print(f"     ติด: {', '.join(a['findings'])}"
                  f"  {'(เขียนใหม่ได้)' if a['fixable'] else '(เขียนใหม่ไม่ช่วย)'}")
    print(f"\n  สรุป: {r['verdict']}  #{' #'.join(r['hashtags'])}")
    print(f"  ต้นทุน {r['cost']} บาท · variant {r['variant_id']}")


def main() -> None:
    p = argparse.ArgumentParser(description="สายงานคอนเทนต์")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("plan", help="วางแผนคอนเทนต์จากสต็อกจริง")
    pp.add_argument("--days", type=int, default=3)
    pp.add_argument("--goal", default="เพิ่มการรับรู้และยอดขายน้ำมะเขือเทศ")

    pw = sub.add_parser("write", help="เขียน 1 โพสต์แล้วผ่านด่านตรวจ")
    pw.add_argument("topic")
    pw.add_argument("--platform", default="instagram")
    pw.add_argument("--angle", default="เล่าที่มาและวิธีใช้")
    pw.add_argument("--strategy", default="ให้ความรู้")
    pw.add_argument("--item", default="ONATO-JUICE-75")

    a = p.parse_args()
    if a.cmd == "plan":
        _print_plan(plan(days=a.days, goal=a.goal))
    else:
        _print_write(write(ContentBrief(
            slot_date=date.today(), platforms=[a.platform], topic_th=a.topic,
            angle_th=a.angle, strategy=a.strategy, product_refs=[a.item],
            rationale_th="สั่งจากบรรทัดคำสั่ง"), a.platform))
    print()


if __name__ == "__main__":
    main()
