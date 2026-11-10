"""
test_pipeline.py — เทสต์ของจริง รันกับฐานข้อมูลและ ERPNext จริง

    py -m growth.tests.test_pipeline

ไม่ใช่ unit test แบบ mock ทุกอย่าง — ตั้งใจให้แตะของจริง เพราะบั๊กที่เจอมา
ทั้งหมดในโปรเจกต์นี้ (REVOKE ไม่กัน owner, now() ในทรานแซกชัน, cast วันที่ผิด,
คอลัมน์หาย) เป็นบั๊กที่ unit test แบบ mock จับไม่ได้เลยสักตัว

ใช้ StubProvider เสมอ เพื่อให้ผลเดิมทุกครั้งและไม่เสียค่าโมเดล
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from growth.agents import closer, reach_guard, strategist, writer   # noqa: E402
from growth.agents.agents import (ContentBrief, DraftMedia, GuardInput,      # noqa: E402
                                  InventorySignal, StrategistInput,
                                  WriterInput, WriterOutput)
from growth.agents.common import AgentContext, Turn                  # noqa: E402
from growth.runtime import db, erp, llm, orchestrator, prompts, worker  # noqa: E402
from growth.runtime.inbox import handle                              # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                # noqa: BLE001
        pass

# บังคับใช้ stub ทั้งกระบวนการ — เทสต์ต้องไม่เสียเงินและต้องให้ผลเดิมทุกครั้ง
# ถ้าไม่ล็อกตรงนี้ inbox.handle() จะเรียกโมเดลจริงทุกครั้งที่รันเทสต์
llm._cached = llm.StubProvider()

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  — {detail}" if detail else ""))


def section(t: str) -> None:
    print(f"\n{t}")


# ── ของใช้ร่วม ───────────────────────────────────────────────
CONN = db.connect()
ORG, BRAND = db.resolve_brand(CONN)
PROV = llm.StubProvider()
CTX = AgentContext(org_id=ORG, brand_id=BRAND, agent="reach_guard",
                   now=datetime.now(timezone.utc))


def guard(body: str, platform: str = "instagram", media=None, aigc=False,
          same_day: int = 0, recent=None):
    rules = db.load_rules(CONN, platform)
    return reach_guard.run(
        GuardInput(ctx=CTX, dna=db.load_dna(CONN, BRAND, "reach_guard"),
                   platform=platform,
                   draft=WriterOutput(body=body, media=media or [],
                                      aigc_label_required=aigc),
                   rules=rules, ruleset_hash=db.ruleset_hash(rules),
                   recent_posts=recent or [], scheduled_same_day=same_day),
        provider=PROV, prompts_load=prompts.load).output



def reset_test_state(conn) -> None:
    """ล้างร่องรอยของรอบก่อน — เทสต์ต้องให้ผลเดิมไม่ว่ารันกี่ครั้ง

    จำเป็นเพราะ idempotency_key ของ Closer ผูกกับ conversation_id
    ถ้าห้องแชททดสอบรอบก่อนยังอยู่ งานจะไม่เข้าคิวซ้ำ แล้วเทสต์จะ FAIL
    แบบที่ดูเหมือนโค้ดพัง ทั้งที่เป็นเรื่องข้อมูลค้าง

    แต่ละคำสั่งแยกทรานแซกชัน — ถ้าอันไหนพัง อันอื่นต้องไม่โดนยกเลิกตาม
    (บทเรียนจากรอบที่แล้ว: psycopg ยกเลิกทั้งก้อนเมื่อเจอ error)"""
    for sql in (
        "delete from outbound_jobs where payload->>'lead_name' = 'เทสต์'",
        """delete from lead_scores where conversation_id in (
             select v.id from conversations v join contact_identities i
                    on i.contact_id = v.contact_id
              where i.external_id like 'test-%')""",
        """delete from leads where contact_id in (
             select contact_id from contact_identities
              where external_id like 'test-%')""",
        """delete from conversations where contact_id in (
             select contact_id from contact_identities
              where external_id like 'test-%')""",
        "delete from contact_identities where external_id like 'test-%'",
    ):
        try:
            conn.execute(sql)
            conn.commit()
        except Exception as exc:                                     # noqa: BLE001
            conn.rollback()
            print(f"  (ล้างไม่สำเร็จ ข้ามไป: {str(exc)[:60]})")


reset_test_state(CONN)

# ── 1. Reach Guard ───────────────────────────────────────────
section("Reach Guard")
check("ข้อความสะอาด → ผ่าน",
      guard("มะเขือเทศจากสวนเรา เก็บเช้าคั้นเช้า").verdict == "pass")
g = guard("แท็กเพื่อนมาคอมเมนต์คำว่าสนใจ")
check("engagement bait → บล็อก และเขียนใหม่ได้",
      g.verdict == "block" and g.fixable_by_rewrite, f"risk={g.risk_score}")
g = guard("ดื่มแล้วรักษาสิวหายแน่นอน")
check("เคลมสุขภาพ → บล็อก (ตัวตรวจที่ใช้โมเดล)",
      g.verdict == "block" and any(f.rule_id == "ig.health_claim" for f in g.findings))
check("ตัวตรวจที่ใช้โมเดลทำงานแล้ว ไม่ใช่ deterministic ล้วน",
      not g.deterministic_only)
g = guard("ลองใช้เซรั่มดูนะคะ",
          media=[DraftMedia(kind="image", generator="ai:flux",
                            depicts_realistic_person=True)])
check("รูปคน AI ไม่ติดป้าย → บล็อก และเขียนใหม่ไม่ช่วย",
      g.verdict == "block" and not g.fixable_by_rewrite)
check("ติดป้าย AIGC แล้ว → ผ่าน",
      guard("ลองใช้เซรั่มดูนะคะ", aigc=True,
            media=[DraftMedia(kind="image", generator="ai:flux",
                              depicts_realistic_person=True)]).verdict == "pass")
check("โพสต์เกินเพดานต่อวัน → ต้องแก้",
      guard("โพสต์ที่สาม", same_day=2).verdict == "rewrite")
check("กฎเฉพาะ X ไม่ยิงบน IG",
      guard("รีพลายแล้วฟอลโลว์กลับ").verdict == "pass")
check("กฎเฉพาะ X ยิงบน X",
      guard("รีพลายแล้วฟอลโลว์กลับ", platform="x").verdict == "block")

# regression: prompt หายไฟล์เดียวต้องไม่ล้มทั้งด่าน
rules = db.load_rules(CONN, "instagram")
broken = [r.model_copy(update={"detector": {"prompt_key": "ไม่มีไฟล์นี้จริง"}})
          if r.detector_type == "llm" else r for r in rules]
res = reach_guard.run(
    GuardInput(ctx=CTX, dna=db.load_dna(CONN, BRAND, "reach_guard"),
               platform="instagram", draft=WriterOutput(body="ข้อความปกติ"),
               rules=broken, ruleset_hash="x"),
    provider=PROV, prompts_load=prompts.load)
check("prompt หาย → ข้ามกฎเดียว ไม่ล้มทั้งด่าน", res.ok and res.output.verdict == "pass")

# ── 2. Writer ⇄ Guard ────────────────────────────────────────
section("Writer ⇄ Guard")
brief = ContentBrief(slot_date=date.today(), platforms=["instagram"],
                     topic_th="ที่มาของมะเขือเทศ", angle_th="เล่ากระบวนการ",
                     strategy="ให้ความรู้", rationale_th="ทดสอบ")
dna_w = db.load_dna(CONN, BRAND, "writer")
w1 = writer.run(WriterInput(ctx=CTX.model_copy(update={"agent": "writer"}),
                            dna=dna_w, brief=brief, platform="instagram", attempt=1),
                provider=PROV, prompt_template=prompts.load("writer")[0],
                model="claude-opus-5")
g1 = guard(w1.output.body)
check("รอบแรกโดนด่านตรวจจับ", g1.verdict == "block", f"risk={g1.risk_score}")
w2 = writer.run(WriterInput(ctx=CTX.model_copy(update={"agent": "writer"}),
                            dna=dna_w, brief=brief, platform="instagram",
                            attempt=2, guard_feedback=g1.to_feedback(2)),
                provider=PROV, prompt_template=prompts.load("writer")[0],
                model="claude-opus-5")
check("รอบสองผ่านหลังได้ feedback", guard(w2.output.body).verdict == "pass")
try:
    WriterInput(ctx=CTX, dna=dna_w, brief=brief, platform="instagram", attempt=2)
    check("รอบ 2 ไม่แนบ feedback → ต้องพัง", False)
except Exception:                                                    # noqa: BLE001
    check("รอบ 2 ไม่แนบ feedback → ต้องพัง", True)

# ── 3. Strategist ────────────────────────────────────────────
section("Strategist")
inv = [InventorySignal(erp_item_code="HAVE-1", name_th="มีของ", qty_available=50,
                       flag="normal"),
       InventorySignal(erp_item_code="GONE-1", name_th="ของหมด", qty_available=0,
                       flag="low_stock")]
sres = strategist.run(
    StrategistInput(ctx=CTX.model_copy(update={"agent": "strategist"}),
                    dna=db.load_dna(CONN, BRAND, "strategist"),
                    goal_th="ทดสอบ", horizon_days=3,
                    platforms=["instagram", "facebook"], inventory=inv),
    provider=PROV, prompt_template=prompts.load("strategist")[0],
    model="claude-opus-5")
codes = {c for b in sres.output.briefs for c in b.product_refs}
check("ไม่วางแผนขายตรงสินค้าที่หมด", "GONE-1" not in codes)
check("บอกด้วยว่าตัดอะไรออกเพราะอะไร", len(sres.output.skipped_reasons_th) > 0,
      sres.output.skipped_reasons_th[0] if sres.output.skipped_reasons_th else "")

# ── 4. Auto-Reply / Concierge ────────────────────────────────
section("สายงานแชท")
r = handle("ใช้แล้วมีผื่นคันค่ะ", "line", "test-allergy", "เทสต์")
check("แจ้งอาการแพ้ → ชั้นกฎหยุดเอง ไม่เรียก AI",
      r["layer"] == "auto_reply" and r["outcome"] == "escalate")
check("เรื่องแพ้ต้นทุน 0 บาท", r["cost"] == "0 บาท")
r = handle("น้ำมะเขือเทศยังมีไหม", "line", "test-stock", "เทสต์")
check("ถามสต็อก → ถึงชั้น Concierge", r["layer"] == "concierge")
check("คำตอบอ้างอิง ERPNext จริง",
      any(g.startswith("erp.") for g in r.get("grounded_on", [])),
      str(r.get("grounded_on")))

# ── 5. Closer + worker ───────────────────────────────────────
section("Closer และด่านอนุมัติ")
before = CONN.execute("select count(*) n from outbound_jobs").fetchone()["n"]
r = handle("สั่ง 20 ขวด โอนเลยได้ไหม", "line", "test-closer", "เทสต์")
check("คะแนนสูง → เสนอสร้างลีด", r.get("lead_action") == "create_lead",
      f"score={r.get('score')}")
after = CONN.execute("select count(*) n from outbound_jobs").fetchone()["n"]
check("งานเข้าคิว", after > before)
job = CONN.execute(
    "select * from outbound_jobs order by created_at desc limit 1").fetchone()
check("งานถูกตั้งว่าต้องมีคนอนุมัติ", job["requires_approval"] is True)
check("worker ไม่แตะงานที่ยังไม่อนุมัติ", worker.drain(verbose=False) == 0)
CONN.execute("update outbound_jobs set approved_by='test', approved_at=now() "
             "where id=%s", (job["id"],))
CONN.commit()
check("อนุมัติแล้ว worker ทำงาน", worker.drain(verbose=False) >= 1)
done = CONN.execute("select status, result from outbound_jobs where id=%s",
                    (job["id"],)).fetchone()
check("สร้าง Lead ใน ERPNext สำเร็จ", done["status"] == "succeeded",
      str(done["result"])[:60] if done["result"] else "")

# ── 6. ERP tools ─────────────────────────────────────────────
section("ERPNext")
s = erp.stock_lookup("ONATO-JUICE-75")
check("ดึงสต็อกจริงได้", s.ok and float(s.data["qty_available"]) > 0,
      f"{s.data['qty_available'] if s.ok else s.error}")
check("สินค้าไม่มีจริง → บอกว่าไม่มี ไม่คืนศูนย์",
      not erp.stock_lookup("ไม่มีรหัสนี้").ok)
b = erp.batch_lookup("ONATO-JUICE-75")
check("ดึงล็อตและวันหมดอายุได้", b.ok and b.data["nearest_expiry"] is not None)

# ── 7. ฐานข้อมูล ─────────────────────────────────────────────
section("ฐานข้อมูล")
h = CONN.execute("select * from events_partition_health").fetchone()
check("view สุขภาพ partition ใช้งานได้", h["partition_ไกลสุด"] is not None,
      f"ไกลสุด {h['partition_ไกลสุด']}")
check("ไม่มี event ตกใน default", h["ตกใน_default"] == 0)
far = (date.today().replace(day=1) + timedelta(days=400)).replace(day=1)
CONN.execute("select ensure_event_partition(%s)", (far,))
CONN.commit()
name = "events_" + far.strftime("%Y_%m")
check("สร้าง partition ล่วงหน้าได้",
      CONN.execute("select 1 from pg_class where relname=%s", (name,)).fetchone()
      is not None, name)
CONN.execute(f"drop table if exists {name}")
CONN.commit()

try:
    CONN.execute("update events set payload='{}'::jsonb where false")
    CONN.commit()
    check("events แก้ไม่ได้ (append-only)", False)
except Exception:                                                    # noqa: BLE001
    CONN.rollback()
    check("events แก้ไม่ได้ (append-only)", True)
try:
    CONN.execute("delete from consent_events where false")
    CONN.commit()
    check("consent_events ลบไม่ได้", False)
except Exception:                                                    # noqa: BLE001
    CONN.rollback()
    check("consent_events ลบไม่ได้", True)

# ── 8. ต้นทุนถูกบันทึก ──────────────────────────────────────
section("การบันทึกต้นทุน")
row = CONN.execute(
    """select count(*) n, count(prompt_hash) with_prompt, sum(tool_calls) tools
         from agent_runs where started_at > now() - interval '10 minutes'""").fetchone()
check("agent_runs บันทึกทุกการเรียก", row["n"] > 0, f"{row['n']} แถว")
check("prompt_hash ถูกเก็บ", row["with_prompt"] > 0)
check("tool_calls ถูกเก็บ", (row["tools"] or 0) > 0)

# ── เก็บกวาดขยะที่เทสต์สร้าง ─────────────────────────────────
section("เก็บกวาด")
made = [r["name"] for r in CONN.execute(
    """select result->>'name' as name from outbound_jobs
        where kind = 'create_erp_lead' and status = 'succeeded'
          and payload->>'lead_name' = 'เทสต์' and result->>'name' is not null"""
).fetchall()]
deleted = sum(1 for n in made if erp.delete_doc("Lead", n))
reset_test_state(CONN)

# user integration ไม่มีสิทธิ์ลบใน ERPNext โดยตั้งใจ (least-privilege)
# เทสต์จึงลบขยะตัวเองไม่ได้ และนั่นถูกแล้ว — ต้องบอกให้ชัดว่าเหลืออะไร
# ล้างด้วยสิทธิ์ admin: bash growth/setup/07-clean-test-data.sh
check("รายงาน Lead ทดสอบที่สร้างไว้ได้ครบ", len(made) >= 1, f"{len(made)} รายการ")
check("ลบเองไม่ได้ เพราะสิทธิ์จำกัดตามที่ออกแบบ", deleted == 0,
      f"ลบได้ {deleted}/{len(made)} — ต้องใช้ 07-clean-test-data.sh")

# contacts ลบไม่ได้เพราะมี consent_events ผูกอยู่ และ ledger นั้นลบไม่ได้ตามการออกแบบ
blocked = False
try:
    CONN.execute("""delete from contacts where id in (
                      select contact_id from consent_events limit 1)""")
    CONN.commit()
except Exception:                                                    # noqa: BLE001
    CONN.rollback()
    blocked = True
check("ลบ contact ที่มี consent ไม่ได้ (PDPA ตามออกแบบ)", blocked)

CONN.close()

# ── สรุป ─────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"ผ่าน {len(PASS)} · ล้มเหลว {len(FAIL)}")
if FAIL:
    for f in FAIL:
        print(f"  ล้มเหลว: {f}")
sys.exit(1 if FAIL else 0)
