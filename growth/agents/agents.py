"""
agents.py — สัญญา input/output ของ agent ทั้ง 7 ตัว

ลำดับในไฟล์ = ลำดับในสายงานจริง
  Strategist → Writer ⇄ ReachGuard → (publish)
  Concierge → Scorer → Closer
  Analyst (รันกลางคืน ป้อนกลับเข้า Brand DNA)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import (
    AgentContext, DnaSlice, KnowledgeSnippet, Platform, Strategy, Strict, Turn,
)
from .tools import ToolCall, ToolResult

# ═════════════════════════════════════════════════════════════
# 1. STRATEGIST — วางแผนคอนเทนต์ · รันวันละครั้ง · โมเดลใหญ่
# ═════════════════════════════════════════════════════════════

class PerformanceRow(Strict):
    """มาจาก materialized view content_performance"""
    variant_id: UUID
    platform: Platform
    topic: str
    strategy: Strategy | None
    published_at: datetime
    reach: int | None
    engagement_rate_pct: Decimal | None
    leads_attributed: int = 0        # นับจาก correlation_id สายเดียวกัน
    revenue_thb: Decimal | None = None


class InventorySignal(Strict):
    """จุดที่ทำให้แผนคอนเทนต์ผูกกับของจริงในสวน
    ล็อตใกล้หมดอายุ = เหตุผลที่ควรดันคอนเทนต์สินค้านั้นสัปดาห์นี้
    ไม่มีเครื่องมือการตลาดเจ้าไหนทำได้ เพราะไม่มีใครเห็นคลังของคุณ"""

    erp_item_code: str
    name_th: str
    qty_available: Decimal
    nearest_expiry: date | None = None
    days_to_expiry: int | None = None
    flag: Literal["overstock", "expiring_soon", "low_stock", "new_product", "normal"]


class StrategistInput(Strict):
    ctx: AgentContext
    dna: DnaSlice
    goal_th: str
    horizon_days: int = 7
    platforms: list[Platform]
    recent_performance: list[PerformanceRow] = Field(default_factory=list)
    inventory: list[InventorySignal] = Field(default_factory=list)
    blackout_dates: list[date] = Field(default_factory=list)


class ContentBrief(Strict):
    slot_date: date
    platforms: list[Platform]
    topic_th: str
    angle_th: str
    strategy: Strategy
    product_refs: list[str] = Field(default_factory=list)   # erp_item_code
    must_include_th: list[str] = Field(default_factory=list)
    rationale_th: str = Field(max_length=300)
    evidence: list[UUID] = Field(default_factory=list)      # variant_id ที่ใช้อ้าง


class StrategistOutput(Strict):
    briefs: list[ContentBrief]
    digest_th: str
    skipped_reasons_th: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _respect_frequency(self):
        """กันแผนที่ละเมิด channel_prefs.max_posts_per_day ตั้งแต่ต้นทาง
        ถูกกว่าปล่อยให้ Reach Guard มาจับทีหลัง (เสียค่า Writer ไปฟรีๆ)"""
        seen: dict[tuple[date, str], int] = {}
        for b in self.briefs:
            for p in b.platforms:
                k = (b.slot_date, p)
                seen[k] = seen.get(k, 0) + 1
        over = [f"{d} {p} x{n}" for (d, p), n in seen.items() if n > 3]
        if over:
            raise ValueError(f"วางแผนถี่เกินเพดานแข็ง: {over}")
        return self


# ═════════════════════════════════════════════════════════════
# 2. WRITER — เขียนต่อแพลตฟอร์ม · โมเดลกลาง · เรียกซ้ำได้สูงสุด 3 ครั้ง
# ═════════════════════════════════════════════════════════════

class DraftMedia(Strict):
    kind: Literal["image", "video"]
    prompt_th: str | None = None
    asset_url: str | None = None
    generator: str | None = None                  # 'ai:flux' | 'camera' | None
    depicts_realistic_person: bool = False
    depicts_realistic_scene: bool = False


class GuardFeedback(Strict):
    """ขอบที่ทำให้เป็น generator→critic loop จริง
    Writer รอบที่ 2 ได้เห็นว่าโดนจับอะไรและต้องแก้ยังไง"""

    attempt: int
    findings_th: list[str]
    fix_hints_th: list[str]
    must_not_repeat: list[str] = Field(default_factory=list)


class WriterInput(Strict):
    ctx: AgentContext
    dna: DnaSlice
    brief: ContentBrief
    platform: Platform
    knowledge: list[KnowledgeSnippet] = Field(default_factory=list)
    attempt: int = 1
    guard_feedback: GuardFeedback | None = None

    @model_validator(mode="after")
    def _rewrite_needs_feedback(self):
        if self.attempt > 1 and self.guard_feedback is None:
            raise ValueError("เขียนใหม่รอบที่ 2+ ต้องแนบ guard_feedback ไม่งั้นจะเขียนผิดซ้ำเดิม")
        return self


class WriterOutput(Strict):
    body: str
    hashtags: list[str] = Field(default_factory=list)
    media: list[DraftMedia] = Field(default_factory=list)
    aigc_label_required: bool = False
    grounded_on: list[str] = Field(default_factory=list)   # doc_id ที่ใช้อ้าง
    self_check_th: list[str] = Field(default_factory=list)

    # เคยมี validator ตรงนี้ที่บังคับว่า "มีสื่อ AI สมจริง → ต้องตั้ง aigc_label_required"
    # ถอดออกเมื่อ 12 ก.ย. 2026 หลังเจอตอนรันจริงว่ามันทำให้สถานะผิดพลาด
    # "สร้างไม่ได้เลยทั้งระบบ" → กฎ ig.aigc_person / tiktok.aigc_label ยิงไม่ได้ตลอดกาล
    # การตรวจของ Reach Guard กลายเป็นพิธีกรรม ขัดกับกฎเหล็กข้อ 3 (ห้ามเชื่อ self-report)
    #
    # ตอนนี้ aigc_label_required เป็นแค่ "สิ่งที่ Writer บอก" — Guard เป็นคนตัดสินว่าถูกไหม
    # และทำให้ draft ที่ไม่ได้มาจาก Writer (คนแปะเอง / นำเข้า) ถูกตรวจด้วยกฎเดียวกัน
    #
    # ⚠ ข้อจำกัดที่ยังเหลือ: Guard ตรวจจาก metadata ของสื่อ ไม่ได้ดูรูปจริง
    #   ถ้า depicts_realistic_person ถูกตั้งผิด ไม่มีอะไรจับได้
    #   การตรวจจริงต้องอ่าน C2PA หรือใช้ classifier — ยังไม่อยู่ในขอบเขตเฟสนี้

    @property
    def aigc_label_missing(self) -> bool:
        """สื่อบอกว่าเป็น AI สมจริง แต่ยังไม่ตั้งธงติดป้าย"""
        return (not self.aigc_label_required) and any(
            m.generator and m.generator.startswith("ai:")
            and (m.depicts_realistic_person or m.depicts_realistic_scene)
            for m in self.media)


# ═════════════════════════════════════════════════════════════
# 3. REACH GUARD — ด่านตรวจ · กฎตายตัวก่อน แล้วค่อย LLM
# ═════════════════════════════════════════════════════════════
#
# Guard "ไม่เขียนใหม่เอง" โดยตั้งใจ — คืนแค่ findings + fix_hints
# เหตุผล: ถ้าคนตรวจแก้งานเอง มันจะแก้ให้ผ่านการตรวจของตัวเอง
#         แยก generator ออกจาก critic ทำให้การตรวจยังมีความหมาย
# ═════════════════════════════════════════════════════════════

class PolicyRuleView(Strict):
    """กฎที่ enabled และ effective_from <= today (จากตาราง policy_rules)"""
    id: str
    platforms: list[str]
    category: str
    severity: Literal["block", "warn", "info"]
    detector_type: Literal["regex", "keyword", "llm", "structural"]
    detector: dict[str, Any]
    message_th: str
    fix_hint_th: str | None = None
    source_url: str | None = None


class RecentPost(Strict):
    """ใช้ตรวจ frequency + originality"""
    variant_id: UUID
    platform: Platform
    body: str
    published_at: datetime


class GuardInput(Strict):
    ctx: AgentContext
    dna: DnaSlice
    platform: Platform
    draft: WriterOutput
    rules: list[PolicyRuleView]
    ruleset_hash: str
    recent_posts: list[RecentPost] = Field(default_factory=list)
    scheduled_same_day: int = 0


class Finding(Strict):
    rule_id: str
    category: str
    severity: Literal["block", "warn", "info"]
    detector: Literal["regex", "keyword", "llm", "structural"]
    span: tuple[int, int] | None = None
    excerpt: str | None = None
    message_th: str
    fix_hint_th: str | None = None
    source_url: str | None = None
    confidence: float | None = None      # เฉพาะ detector='llm'


class GuardOutput(Strict):
    verdict: Literal["pass", "rewrite", "block"]
    risk_score: int = Field(ge=0, le=100)
    findings: list[Finding] = Field(default_factory=list)
    # true = ตรวจจบด้วยกฎตายตัว ไม่ได้เรียก LLM เลย → ต้นทุน 0
    deterministic_only: bool = True
    ruleset_hash: str

    @model_validator(mode="after")
    def _verdict_matches_findings(self):
        has_block = any(f.severity == "block" for f in self.findings)
        if has_block and self.verdict == "pass":
            raise ValueError("มี finding ระดับ block แต่ตัดสินว่า pass")
        if not self.findings and self.verdict != "pass":
            raise ValueError("ไม่มี finding แต่ไม่ยอมให้ผ่าน — ต้องบอกเหตุผลได้เสมอ")
        return self

    @property
    def fixable_by_rewrite(self) -> bool:
        """Writer เขียนใหม่แล้วมีโอกาสผ่านไหม
        finding ที่มาจากข้อความ (keyword/regex/llm) แก้ด้วยการเขียนใหม่ได้
        แต่ finding เชิงโครงสร้าง (ไม่ติดป้าย AIGC · โพสต์ถี่เกิน) แก้ด้วยข้อความไม่ได้
        ต้องไปแก้สื่อหรือตารางเวลา — ส่งให้คนตัดสินดีกว่าวนให้ Writer เขียนฟรีๆ"""
        blockers = [f for f in self.findings if f.severity == "block"]
        return bool(blockers) and all(f.detector != "structural" for f in blockers)

    def to_feedback(self, attempt: int) -> GuardFeedback:
        return GuardFeedback(
            attempt=attempt,
            findings_th=[f.message_th for f in self.findings],
            fix_hints_th=[f.fix_hint_th for f in self.findings if f.fix_hint_th],
            must_not_repeat=[f.excerpt for f in self.findings if f.excerpt],
        )


# ═════════════════════════════════════════════════════════════
# 4. CONCIERGE — ตอบแชท · เรียก ERPNext ได้ · โมเดลกลาง
# ═════════════════════════════════════════════════════════════

class ContactBrief(Strict):
    contact_id: UUID
    display_name: str | None = None
    channel: str
    is_returning: bool = False
    erp_customer: str | None = None
    consent_marketing: bool = False    # จาก view consent_current


class ConciergeInput(Strict):
    ctx: AgentContext
    dna: DnaSlice
    turns: list[Turn]
    contact: ContactBrief
    knowledge: list[KnowledgeSnippet] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    ai_turn_count: int = 0


# คำที่บ่งชี้ว่ากำลังพูดถึงข้อเท็จจริงที่ ERPNext เป็นเจ้าของ
_FACT_MARKERS = ("บาท", "ขวด", "ชิ้น", "คงเหลือ", "สต็อก", "ล็อต", "หมดอายุ", "พร้อมส่ง")


class ConciergeOutput(Strict):
    # ถ้ามี tool_calls = ยังไม่ตอบ ขอข้อมูลก่อน (reply_th ต้องเป็น None)
    reply_th: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    grounded_on: list[str] = Field(default_factory=list)
    needs_human: bool = False
    needs_human_reason_th: str | None = None
    confidence: float = Field(ge=0, le=1, default=1.0)

    @model_validator(mode="after")
    def _one_mode_only(self):
        if self.tool_calls and self.reply_th:
            raise ValueError("เรียก tool กับตอบพร้อมกันไม่ได้ — ให้ขอข้อมูลก่อนแล้วค่อยตอบรอบถัดไป")
        if not self.tool_calls and not self.reply_th and not self.needs_human:
            raise ValueError("ต้องมีอย่างน้อยหนึ่ง: ตอบ / เรียก tool / ส่งต่อคน")
        return self

    @model_validator(mode="after")
    def _facts_must_be_grounded(self):
        """หัวใจของไอเดีย 'AI ที่รู้ของจริงในสต็อก'
        ถ้าตอบเรื่องราคา/จำนวน/ล็อต/วันหมดอายุ ต้องมี ToolResult จาก ERP อ้างอิง
        ห้ามให้โมเดลเดาตัวเลขเด็ดขาด — ผิดแล้วลูกค้าเสียหายจริง"""
        if not self.reply_th:
            return self
        mentions_fact = any(m in self.reply_th for m in _FACT_MARKERS)
        has_digit = any(c.isdigit() for c in self.reply_th)
        if mentions_fact and has_digit:
            if not any(g.startswith("erp.") for g in self.grounded_on):
                raise ValueError(
                    "ตอบตัวเลขเรื่องราคา/สต็อก/ล็อต โดยไม่มี erp.* ใน grounded_on")
        return self


# ═════════════════════════════════════════════════════════════
# 5. SCORER — ให้คะแนนโอกาสปิด · โมเดลเล็ก · ไม่ใช้ Brand DNA เลย
# ═════════════════════════════════════════════════════════════
#
# นโยบายการเรียก (อย่าเรียกทุกข้อความ ค่าจะบาน):
#   - ทุก 3 เทิร์นของลูกค้า
#   - หรือทันทีเมื่อเจอคำบ่งชี้ ('สั่ง', 'โอน', 'เท่าไหร่', 'ส่งเมื่อไหร่')
#   - หรือเมื่อบทสนทนาปิด
# ═════════════════════════════════════════════════════════════

class ScorerSignals(Strict):
    intent: Literal["browsing", "comparing", "ready_to_buy",
                    "support", "complaint", "spam"]
    items: list[str] = Field(default_factory=list)   # erp_item_code ถ้าระบุได้
    qty: int | None = None
    budget_signal: bool = False
    urgency: Literal["none", "soon", "now"] = "none"
    blockers_th: list[str] = Field(default_factory=list)


class ScorerInput(Strict):
    ctx: AgentContext          # ไม่มี dna — นี่คือจุดที่ประหยัดที่สุดของระบบ
    turns: list[Turn]
    prior_score: int | None = None


class ScorerOutput(Strict):
    score: int = Field(ge=0, le=100)
    signals: ScorerSignals
    rationale_th: str = Field(max_length=200)   # จำกัดความยาว = จำกัดค่า token


# ═════════════════════════════════════════════════════════════
# 6. CLOSER — เสนอให้สร้างลีด/ออเดอร์ใน ERPNext · ไม่เคยลงมือเอง
# ═════════════════════════════════════════════════════════════

class CloserInput(Strict):
    ctx: AgentContext
    dna: DnaSlice
    conversation_id: UUID
    contact: ContactBrief
    score: int
    signals: ScorerSignals
    turns: list[Turn]
    stock: list[ToolResult] = Field(default_factory=list)


class CloserOutput(Strict):
    action: Literal["create_lead", "create_sales_order", "nurture", "none"]
    erp_payload: dict[str, Any] = Field(default_factory=dict)
    value_thb: Decimal | None = None
    summary_th: str = Field(max_length=400)
    requires_approval: bool = True

    @model_validator(mode="after")
    def _money_needs_a_human(self):
        """เฟส 1: อะไรที่แตะเงินต้องมีคนกดยืนยันเสมอ ไม่มีข้อยกเว้น
        ปลดล็อกได้เมื่อมีสถิติความแม่นย้อนหลังพอ — แก้ที่นี่จุดเดียว"""
        if self.action == "create_sales_order" and not self.requires_approval:
            raise ValueError("สร้าง Sales Order อัตโนมัติโดยไม่ผ่านคนยังไม่อนุญาตในเฟสนี้")
        if self.action in ("create_lead", "create_sales_order") and not self.erp_payload:
            raise ValueError("action ที่เขียนลง ERP ต้องมี erp_payload")
        return self


# ═════════════════════════════════════════════════════════════
# 7. ANALYST — ปิดลูปการเรียนรู้ · รันกลางคืน · โมเดลใหญ่
# ═════════════════════════════════════════════════════════════

class GuardStat(Strict):
    rule_id: str
    hits: int
    blocked: int


class QuestionStat(Strict):
    question_th: str
    count: int
    answered_by_kb: int
    example_conversation_ids: list[UUID] = Field(default_factory=list)


class LeadOutcome(Strict):
    lead_id: UUID
    best_score: int
    stage: str
    value_thb: Decimal | None = None
    source_variant_id: UUID | None = None    # โพสต์ที่พาลูกค้าเข้ามา


class AnalystInput(Strict):
    ctx: AgentContext
    dna: DnaSlice
    window_start: date
    window_end: date
    performance: list[PerformanceRow] = Field(default_factory=list)
    guard_stats: list[GuardStat] = Field(default_factory=list)
    top_questions: list[QuestionStat] = Field(default_factory=list)
    lead_outcomes: list[LeadOutcome] = Field(default_factory=list)


class Evidence(Strict):
    kind: Literal["variant", "conversation", "event", "metric"]
    ref: str
    note_th: str | None = None


class DnaProposal(Strict):
    """ตรงกับตาราง brand_dna_proposals — คนกดอนุมัติก่อนถึงจะเข้า DNA จริง"""

    facet_path: str                      # JSON Pointer เช่น '/voice/avoid_phrases_th/-'
    operation: Literal["add", "replace", "remove"]
    value: Any = None
    rationale_th: str = Field(max_length=500)
    evidence: list[Evidence] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _guardrails(self):
        if self.facet_path.startswith("/claims_policy"):
            raise ValueError(
                "claims_policy เป็นเรื่องกฎหมาย/อย. — คนแก้เท่านั้น agent เสนอไม่ได้")
        if self.confidence < 0.6:
            raise ValueError("มั่นใจต่ำกว่า 0.6 อย่าเสนอ ปล่อยให้สะสมหลักฐานก่อน")
        return self


class AnalystOutput(Strict):
    digest_th: str
    proposals: list[DnaProposal] = Field(default_factory=list, max_length=5)
    # จำกัด 5 ข้อ/รอบ เพราะคนอนุมัติไหว — เสนอ 40 ข้อ = ไม่มีใครอ่าน = ลูปตาย
