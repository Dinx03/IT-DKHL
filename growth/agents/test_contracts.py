"""ตรวจว่า contract ใช้ได้จริง และ validator ดักของผิดจริง"""
import sys, uuid
from pathlib import Path
from datetime import datetime, date, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pydantic import ValidationError
from growth.agents import agents as A
from growth.agents.common import AgentContext, DnaSlice
from growth.agents.tools import ToolResult

ctx = AgentContext(org_id=uuid.uuid4(), brand_id=uuid.uuid4(),
                   agent="concierge", now=datetime.now(timezone.utc))
dna = DnaSlice(version_id=uuid.uuid4(), checksum="abc123", facets={"voice": {}})

def expect_fail(label, fn):
    try:
        fn(); print(f"  [FAIL] {label} — ควรพังแต่ผ่าน"); return 1
    except (ValidationError, ValueError):
        print(f"  [ok]   {label} — ดักได้"); return 0

def expect_ok(label, fn):
    try:
        fn(); print(f"  [ok]   {label}"); return 0
    except Exception as e:
        print(f"  [FAIL] {label} -> {type(e).__name__}: {e}"); return 1

bad = 0
print("Concierge — ห้ามเดาตัวเลขสต็อก/ราคา")
bad += expect_fail("ตอบ 'เหลือ 42 ขวด' โดยไม่มี erp.* อ้างอิง",
    lambda: A.ConciergeOutput(reply_th="ยังมีครับ เหลือ 42 ขวด", grounded_on=["kb.search:x"]))
bad += expect_ok("ตอบตัวเลขพร้อมอ้าง erp.stock_lookup",
    lambda: A.ConciergeOutput(reply_th="ยังมีครับ เหลือ 42 ขวด",
                              grounded_on=["erp.stock_lookup:ONATO-500"]))
bad += expect_ok("ตอบเชิงคุณภาพ ไม่มีตัวเลข ไม่ต้องอ้าง ERP",
    lambda: A.ConciergeOutput(reply_th="ยังมีอยู่ครับ เดี๋ยวเช็คให้"))
bad += expect_fail("เรียก tool พร้อมตอบในรอบเดียว",
    lambda: A.ConciergeOutput(reply_th="ได้ครับ",
        tool_calls=[{"name":"erp.stock_lookup","args":{},"why_th":"เช็คของ"}]))

print("Reach Guard — คำตัดสินต้องสอดคล้องกับสิ่งที่ตรวจเจอ")
blk = dict(rule_id="ig.health_claim", category="health_claim", severity="block",
           detector="llm", message_th="เคลมเกิน")
bad += expect_fail("มี finding ระดับ block แต่ตัดสิน pass",
    lambda: A.GuardOutput(verdict="pass", risk_score=80, findings=[blk], ruleset_hash="h"))
bad += expect_fail("ไม่มี finding แต่บล็อก",
    lambda: A.GuardOutput(verdict="block", risk_score=0, findings=[], ruleset_hash="h"))
bad += expect_ok("block พร้อมเหตุผล แล้วแปลงเป็น feedback ให้ Writer",
    lambda: A.GuardOutput(verdict="block", risk_score=80, findings=[blk],
                          ruleset_hash="h").to_feedback(attempt=2))

print("Writer — เขียนใหม่ต้องรู้ว่าโดนจับอะไร")
brief = A.ContentBrief(slot_date=date.today(), platforms=["instagram"],
                       topic_th="น้ำมะเขือเทศ", angle_th="ที่มาวัตถุดิบ",
                       strategy="ให้ความรู้", rationale_th="ล็อตใกล้หมดอายุ")
bad += expect_fail("รอบที่ 2 แต่ไม่แนบ guard_feedback",
    lambda: A.WriterInput(ctx=ctx, dna=dna, brief=brief, platform="instagram", attempt=2))
# Writer ปล่อยรูป AI ไม่ติดป้ายออกมาได้ — โดยตั้งใจ
# ถ้าห้ามตรงนี้ กฎ ig.aigc_person ของ Reach Guard จะยิงไม่ได้ตลอดกาล (เจอตอนรันจริง)
ai_unlabeled = A.WriterOutput(body="x", media=[{"kind":"image","generator":"ai:flux",
                                                "depicts_realistic_person":True}])
bad += expect_ok("รูป AI ไม่ติดป้าย สร้างได้ (Guard เป็นคนจับ ไม่ใช่ Writer)",
    lambda: ai_unlabeled)
bad += expect_ok("aigc_label_missing บอกได้ว่าขาดป้าย",
    lambda: (_ for _ in ()).throw(AssertionError("ไม่ได้ตั้งธง"))
            if not ai_unlabeled.aigc_label_missing else None)
bad += expect_ok("ติดป้ายแล้ว ไม่ถือว่าขาด",
    lambda: (_ for _ in ()).throw(AssertionError("ยังบอกว่าขาด"))
            if A.WriterOutput(body="x", aigc_label_required=True,
                              media=[{"kind":"image","generator":"ai:flux",
                                      "depicts_realistic_person":True}]).aigc_label_missing
            else None)

print("Closer — อะไรแตะเงินต้องมีคนกด")
bad += expect_fail("สร้าง Sales Order อัตโนมัติ",
    lambda: A.CloserOutput(action="create_sales_order", erp_payload={"i":1},
                           summary_th="ปิดได้", requires_approval=False))

print("Analyst — ห้ามแตะกฎหมาย ห้ามเดา ห้ามท่วมคนอนุมัติ")
ev = [{"kind":"variant","ref":"abc"}]
bad += expect_fail("เสนอแก้ claims_policy",
    lambda: A.DnaProposal(facet_path="/claims_policy/banned_claim_types/-", operation="add",
                          value="x", rationale_th="r", evidence=ev, confidence=0.9))
bad += expect_fail("มั่นใจ 0.4 ก็เสนอ",
    lambda: A.DnaProposal(facet_path="/voice/avoid_phrases_th/-", operation="add",
                          value="x", rationale_th="r", evidence=ev, confidence=0.4))
bad += expect_fail("ไม่มีหลักฐานเลย",
    lambda: A.DnaProposal(facet_path="/voice/avoid_phrases_th/-", operation="add",
                          value="x", rationale_th="r", evidence=[], confidence=0.9))
ok_p = A.DnaProposal(facet_path="/voice/avoid_phrases_th/-", operation="add",
                     value="ขาวใสใน 7 วัน", rationale_th="โดนบล็อก 6 ครั้งใน 30 วัน",
                     evidence=ev, confidence=0.85)
bad += expect_ok("ข้อเสนอที่ถูกต้อง", lambda: ok_p)
bad += expect_fail("เสนอ 6 ข้อในรอบเดียว",
    lambda: A.AnalystOutput(digest_th="d", proposals=[ok_p]*6))

print("Strategist — แผนต้องไม่ละเมิดเพดานความถี่")
b4 = [brief.model_copy(update={"platforms":["instagram"]}) for _ in range(4)]
bad += expect_fail("วางแผน IG 4 โพสต์วันเดียว",
    lambda: A.StrategistOutput(briefs=b4, digest_th="d"))

print(f"\n{'ผ่านทั้งหมด' if bad==0 else f'ล้มเหลว {bad} เคส'}")
sys.exit(1 if bad else 0)
