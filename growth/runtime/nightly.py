"""
nightly.py — งานประจำคืน: บำรุงรักษา + ปิดลูปการเรียนรู้

    py -m growth.runtime.nightly              ทำทั้งหมด
    py -m growth.runtime.nightly --maintenance-only
    py -m growth.runtime.nightly --dry-run    ดูว่าจะทำอะไรโดยไม่แตะข้อมูล

ทำไมต้องมี: ฟังก์ชัน ensure_event_partition() และ anonymize_events() เขียนไว้
ตั้งแต่ต้นแต่ไม่มีใครเรียก — partition มีถึงแค่ ธ.ค. 2026 พอพ้นวันนั้น
event ทุกตัวจะตกลง events_default เงียบๆ และ PDPA retention ก็ไม่เคยทำงาน
เป็นระเบิดเวลาที่ไม่มีอะไรเตือน

ตั้งให้รันทุกคืนด้วย Task Scheduler ของ Windows หรือ cron ใน VM
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

from ..agents import analyst
from ..agents.agents import (AnalystInput, GuardStat, LeadOutcome,
                             PerformanceRow, QuestionStat)
from ..agents.common import AgentContext
from . import db, llm, orchestrator, prompts

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

MONTHS_AHEAD = 3          # เตรียม partition ล่วงหน้ากี่เดือน
ANALYST_WINDOW_DAYS = 30


# ─────────────────────────────────────────────────────────────
# 1. บำรุงรักษา
# ─────────────────────────────────────────────────────────────

def maintenance(conn, dry_run: bool = False) -> dict:
    report: dict = {}

    health = conn.execute("select * from events_partition_health").fetchone()
    report["ก่อนทำ"] = {
        "partition ทั้งหมด": health["partition_ทั้งหมด"],
        "ไกลสุดถึง": health["partition_ไกลสุด"],
        "ตกใน default": health["ตกใน_default"],
    }

    if not dry_run:
        for n in range(MONTHS_AHEAD + 1):
            d = (date.today().replace(day=1) + timedelta(days=32 * n)).replace(day=1)
            conn.execute("select ensure_event_partition(%s)", (d,))
        conn.commit()

    after = conn.execute("select * from events_partition_health").fetchone()
    report["หลังทำ"] = {"partition ทั้งหมด": after["partition_ทั้งหมด"],
                        "ไกลสุดถึง": after["partition_ไกลสุด"]}

    # เตือนดังๆ ถ้ามีอะไรตกลง default — แปลว่ามีช่วงเวลาที่ไม่มี partition รองรับ
    if after["ตกใน_default"]:
        report["เตือน"] = (f"มี {after['ตกใน_default']} event ตกใน events_default "
                           f"(ช่วง {after['เก่าสุดที่ตก']} ถึง {after['ใหม่สุดที่ตก']}) "
                           f"— แปลว่าเคยมีช่วงที่ partition ขาด")

    # PDPA: ลบ PII ที่เกินกำหนดเก็บ
    pol = conn.execute(
        """select type_pattern, retain_days, action from retention_policies
            order by type_pattern""").fetchall()
    report["นโยบายเก็บข้อมูล"] = [
        f"{p['type_pattern']} → {p['action']} หลัง {p['retain_days']} วัน" for p in pol]

    if pol and not dry_run:
        shortest = min(p["retain_days"] for p in pol)
        cutoff = datetime.now(timezone.utc) - timedelta(days=shortest)
        n = conn.execute("select anonymize_events(%s) as n", (cutoff,)).fetchone()["n"]
        conn.commit()
        report["ล้าง PII"] = f"{n} แถว (เก่ากว่า {cutoff.date()})"
    elif dry_run:
        report["ล้าง PII"] = "(dry-run ไม่ได้ทำ)"

    # matview ต้องรีเฟรชเองไม่งั้นแดชบอร์ดโชว์ของเก่า
    if not dry_run:
        try:
            conn.execute("refresh materialized view concurrently content_performance")
        except Exception:                                      # noqa: BLE001
            conn.rollback()
            conn.execute("refresh materialized view content_performance")
        conn.commit()
        report["รีเฟรช content_performance"] = "เรียบร้อย"

    return report


# ─────────────────────────────────────────────────────────────
# 2. Analyst
# ─────────────────────────────────────────────────────────────

def gather(conn, brand_id, days: int = ANALYST_WINDOW_DAYS) -> tuple[AnalystInput, int]:
    since = date.today() - timedelta(days=days)
    dna = db.load_dna(conn, brand_id, "analyst")

    perf = [PerformanceRow(**r) for r in conn.execute(
        """select variant_id, platform, topic, strategy, published_at, reach,
                  engagement_rate_pct, 0 as leads_attributed
             from content_performance where brand_id = %s
            order by published_at desc limit 30""", (brand_id,)).fetchall()]

    guard = [GuardStat(**r) for r in conn.execute(
        """select f->>'rule_id' as rule_id, count(*) as hits,
                  count(*) filter (where pe.verdict = 'block') as blocked
             from policy_evaluations pe, jsonb_array_elements(pe.findings) f
            where pe.created_at >= %s
            group by 1 order by hits desc limit 10""", (since,)).fetchall()]

    questions = [QuestionStat(**r) for r in conn.execute(
        """select payload->>'text' as question_th, count(*) as count,
                  0 as answered_by_kb, array[]::uuid[] as example_conversation_ids
             from events
            where type = 'message.received' and occurred_at >= %s
              and brand_id = %s and payload->>'text' is not null
            group by 1 order by count desc limit 15""", (since, brand_id)).fetchall()]

    leads = [LeadOutcome(**r) for r in conn.execute(
        """select id as lead_id, coalesce(best_score,0) as best_score, stage,
                  value_thb, null::uuid as source_variant_id
             from leads where brand_id = %s and created_at >= %s
            limit 50""", (brand_id, since)).fetchall()]

    n = conn.execute(
        "select count(*) n from events where brand_id = %s and occurred_at >= %s",
        (brand_id, since)).fetchone()["n"]

    org_id = conn.execute("select org_id from brands where id = %s",
                          (brand_id,)).fetchone()["org_id"]
    return AnalystInput(
        ctx=AgentContext(org_id=org_id, brand_id=brand_id, agent="analyst",
                         now=datetime.now(timezone.utc)),
        dna=dna, window_start=since, window_end=date.today(),
        performance=perf, guard_stats=guard, top_questions=questions,
        lead_outcomes=leads), n


def save_proposals(conn, brand_id, dna_version_id, out) -> int:
    for p in out.proposals:
        conn.execute(
            """insert into brand_dna_proposals
                 (brand_id, based_on_version, facet_path, operation, value,
                  rationale_th, evidence, confidence, proposed_by)
               values (%s, %s, %s, %s, %s, %s, %s, %s, 'agent:analyst')""",
            (brand_id, dna_version_id, p.facet_path, p.operation,
             json.dumps(p.value, ensure_ascii=False) if p.value is not None else None,
             p.rationale_th,
             json.dumps([e.model_dump(mode="json") for e in p.evidence],
                        ensure_ascii=False),
             p.confidence))
    conn.commit()
    return len(out.proposals)


def run_analyst(conn, brand_id, dry_run: bool = False) -> dict:
    inp, n = gather(conn, brand_id)
    res = analyst.run(inp, provider=llm.get_provider(),
                      prompt_template=prompts.load("analyst")[0],
                      model=llm.MODEL_FOR["analyst"], event_count=n)
    org_id = inp.ctx.org_id
    if not dry_run:
        orchestrator.commit(conn, res, org_id=org_id, brand_id=brand_id,
                            correlation_id=orchestrator.new_correlation(),
                            agent="analyst",
                            meta=prompts.ref("analyst") | {"dna_checksum": inp.dna.checksum})
    if not res.ok:
        return {"ok": False, "error": res.error.message, "events": n}
    saved = 0 if dry_run else save_proposals(conn, brand_id, inp.dna.version_id, res.output)
    return {"ok": True, "events": n, "digest": res.output.digest_th,
            "proposals": [(p.facet_path, p.confidence, p.rationale_th)
                          for p in res.output.proposals],
            "saved": saved, "cost": res.usage.cost_thb}


# ─────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="งานประจำคืน")
    p.add_argument("--maintenance-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--brand", default="ona-healthy")
    a = p.parse_args()

    with db.connect() as conn:
        _, brand_id = db.resolve_brand(conn, a.brand)

        print("\n── บำรุงรักษา ──")
        for k, v in maintenance(conn, a.dry_run).items():
            print(f"  {k}: {v}")

        if a.maintenance_only:
            print()
            return

        print("\n── Analyst ──")
        r = run_analyst(conn, brand_id, a.dry_run)
        if not r["ok"]:
            print(f"  ล้มเหลว: {r['error']}")
        else:
            print(f"  เหตุการณ์ใน 30 วัน: {r['events']}")
            print(f"  {r['digest']}")
            for path, conf, why in r["proposals"]:
                print(f"    · {path}  (มั่นใจ {conf})")
                print(f"      {why}")
            print(f"  บันทึกข้อเสนอ {r['saved']} ข้อ · ต้นทุน {r['cost']} บาท")
    print()


if __name__ == "__main__":
    main()
