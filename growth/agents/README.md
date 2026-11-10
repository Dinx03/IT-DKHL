# growth/agents — สัญญาระหว่าง agent

Pydantic v2 · `py -m growth.agents.export_schema` แปลงเป็น JSON Schema ได้ (สัญญาจริงคือ JSON Schema ไม่ผูกภาษา)

ทดสอบ: `python growth/agents/test_contracts.py` → 17 เคส ตรวจว่า validator ดักของผิดจริง

---

## กฎเหล็ก 3 ข้อ

**1. agent เป็น pure function — ห้ามเขียน DB ห้ามยิง API เอง**
อยากให้เกิดผล → return `EventDraft` / `EffectDraft` ออกมา Orchestrator เป็นคนคอมมิต
ได้ผลพลอยได้: เทสต์ได้โดยไม่ต้องมี DB · replay สายเหตุการณ์เก่าได้ · `dry_run` ทำงานฟรี

**2. `correlation_id` / `causation_id` agent ไม่ตั้งเอง**
จงใจไม่ใส่ไว้ใน `AgentContext` — agent ไม่ต้องรู้ว่าตัวเองอยู่ตรงไหนของสาย Orchestrator เติมให้

**3. ห้ามเชื่อ self-report ของ agent อื่น**
Writer บอก "รูปนี้ไม่ใช่คน AI" → Reach Guard ต้องตรวจเอง
Writer มี validator ตรวจตัวเองอยู่แล้ว **แต่นั่นคือ sanity check ไม่ใช่การตรวจ**

---

## แบ่ง Brand DNA ให้แต่ละตัวเท่าที่จำเป็น

`FACETS_FOR_AGENT` ใน `common.py` — เป็นเรื่องต้นทุน token ล้วนๆ

| agent | facets ที่ได้ | หมายเหตุ |
|---|---|---|
| strategist | identity · audience · offer · channel_prefs · learned | |
| writer | identity · audience · voice · claims_policy · offer | |
| reach_guard | claims_policy · voice · channel_prefs | ไม่ต้องรู้ audience |
| concierge | identity · voice · offer · escalation | |
| **scorer** | **ไม่ได้เลย** | ประหยัดที่สุดในระบบ — ให้คะแนนไม่ต้องรู้จักแบรนด์ |
| closer | offer · escalation | |
| analyst | ทั้งหมด | รันวันละครั้ง ยอมจ่าย |

---

## สาย 1: คอนเทนต์ — generator ⇄ critic

```
Strategist ──briefs──> Writer ──draft──> ReachGuard
                          ↑                   │
                          └──GuardFeedback────┤ verdict=rewrite (สูงสุด 2 รอบ)
                                              │
                                              ├ verdict=pass  → EffectDraft(publish_post)
                                              └ verdict=block → คนตัดสิน
```

**Reach Guard ไม่เขียนใหม่เอง โดยตั้งใจ** — คืนแค่ `findings` + `fix_hint_th`
เพราะถ้าคนตรวจแก้งานเอง มันจะแก้ให้ผ่านการตรวจของตัวเอง การตรวจก็หมดความหมาย
`GuardOutput.to_feedback()` คือขอบที่ป้อนกลับเข้า `WriterInput.guard_feedback`

`WriterInput` มี validator: `attempt > 1` แต่ไม่แนบ feedback = พังทันที (กันเขียนผิดซ้ำเดิม)

**ลำดับการตรวจของ Guard — กฎตายตัวก่อนเสมอ**
`regex` / `keyword` / `structural` รันก่อนโดยไม่เสียเงิน ถ้าเจอ `severity=block` แล้วจบเลย
เรียก LLM เฉพาะกฎ `detector_type='llm'` และเฉพาะเมื่อกฎถูกๆ ผ่านหมด
`GuardOutput.deterministic_only=True` = รอบนั้นต้นทุน 0

---

## สาย 2: แชท

```
ข้อความเข้า
   │
   ├─ Auto-Reply (กฎตายตัวใน DB — ไม่ใช่ agent ไม่มี LLM)  ──match──> ตอบเลย + event rule.matched
   │                                                        └─no──┐
   ├─ Concierge ──tool_calls?──> ERPNext (stock/batch/price) ──┐   │
   │       ↑                                                   │   │
   │       └──────────── ToolResult ───────────────────────────┘   │
   │                                                               │
   │   needs_human=true → คน                                       │
   │   reply_th        → EffectDraft(send_message)                 │
   │                                                               │
   └─ Scorer (ทุก 3 เทิร์น / เจอคำบ่งชี้ / ปิดห้อง) ──score──> Closer
```

`ConciergeOutput` มี validator ที่เป็นหัวใจของทั้งโปรเจกต์:

> ถ้าคำตอบมีตัวเลข **และ** มีคำว่า บาท/ขวด/คงเหลือ/ล็อต/หมดอายุ/พร้อมส่ง
> ต้องมี `erp.*` ใน `grounded_on` — ไม่งั้นพัง

แปลว่า **โมเดลเดาตัวเลขสต็อกไม่ได้เลยในระดับ type** ไม่ใช่แค่ขอไว้ใน prompt
`MAX_STALENESS_S` ใน `tools.py` กำหนดอีกชั้น: ข้อมูลสต็อกเก่าเกิน 60 วินาที ห้ามใช้ตอบ

---

## สาย 3: ปิดลูป

```
Analyst (ตี 2 ทุกคืน)
   ├── อ่าน: content_performance · guard_stats · top_questions · lead_outcomes
   └── เขียน: DnaProposal[] → ตาราง brand_dna_proposals → คนกดอนุมัติ → DNA เวอร์ชันใหม่
```

ข้อจำกัดที่บังคับด้วย validator:
- ห้ามเสนอแก้ `/claims_policy` — เรื่อง อย./กฎหมาย คนแก้เท่านั้น
- `confidence < 0.6` เสนอไม่ได้ ให้สะสมหลักฐานก่อน
- `evidence` ว่างไม่ได้ — ต้องอ้าง variant/conversation/event จริง
- **สูงสุด 5 ข้อต่อรอบ** เพราะคนอนุมัติไหว เสนอ 40 ข้อ = ไม่มีใครอ่าน = ลูปตาย

---

## ขนาดโมเดลและงบต่อครั้ง

| agent | ความถี่ | ขนาด | `Budget.max_thb` |
|---|---|---|---|
| strategist | 1/สัปดาห์ | ใหญ่ | 15 |
| writer | ~20/สัปดาห์ | กลาง | 2 |
| reach_guard | ทุก draft | **กฎก่อน** แล้วเล็ก | 0.5 |
| concierge | ทุกข้อความ | กลาง | 1 |
| scorer | ทุก 3 เทิร์น | เล็ก | 0.2 |
| closer | เมื่อ score ≥ 70 | เล็ก | 0.3 |
| analyst | 1/คืน | ใหญ่ | 20 |

ตัวเลขเป็นเพดานกันพลาด ไม่ใช่ประมาณการค่าใช้จ่าย — ของจริงดูจาก view `agent_cost_daily`

---

## สิ่งที่จงใจ "ไม่" เป็น agent

- **Auto-Reply** — กฎตายตัวใน DB รันก่อน Concierge เสมอ เร็ว ฟรี คุมได้ (สถาปัตยกรรม 2 ชั้นแบบที่ Loopika ใช้)
- **Orchestrator** — state machine ธรรมดา ไม่ใช่ LLM ถ้าให้ LLM ตัดสินใจ routing จะ debug ไม่ได้และแพงโดยไม่จำเป็น
- **ดึง metrics** — cron + `outbound_jobs(kind='fetch_metrics')`

---

## ยังไม่ได้ทำ

- ตัว implement ของแต่ละ agent (ไฟล์นี้มีแต่สัญญา)
- prompt template — ควรอยู่ในไฟล์แยกที่มีเวอร์ชัน อ้างด้วย `prompt_key` เหมือนที่ `policy_rules.detector` ใช้
- Orchestrator + retry/backoff
