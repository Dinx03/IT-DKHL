# growth/ — Brand Core + Event Store

สคีมาฐานข้อมูลของแพลตฟอร์มการตลาด/ขาย ที่วางคู่กับ ERPNext เดิม

> **สถานะ: เฟส 0-1 เสร็จ · เฟส 2 เสร็จเกือบหมด · เฟส 3 เริ่มแล้ว** (13 ก.ย. 2026)
> PostgreSQL 18.6 + pgvector 0.8.1 ใน VM เดียวกับ ERPNext · database `growth`
> 27 ตาราง · กฎ 11 ข้อ · Brand DNA เวอร์ชัน 1 active อยู่
> ต่อจาก Windows ได้ที่ `127.0.0.1:5432` (port forward ของ VirtualBox)
>
> รหัสผ่านอยู่ที่ `~/growth.env` ในเครื่อง VM สิทธิ์ 600 — **ไม่อยู่ในรีโป**

## ทีม agent ที่มีอยู่จริง

| Agent | โมเดล | ทำอะไร | เฟส |
|---|---|---|---|
| **Auto-Reply** | ไม่ใช้ LLM | กฎตายตัว ทำงานก่อน AI เสมอ · 0 บาท | 2 |
| **Concierge** | `claude-opus-5` | ตอบแชท วนเรียก ERP tool เอง | 2 |
| **Scorer** | `claude-haiku-4-5` | คะแนนโอกาสปิด · ไม่ใช้ Brand DNA เลย | 2 |
| **Reach Guard** | กฎตายตัว (LLM รอเฟส 3) | ตรวจก่อนเผยแพร่ · ไม่เขียนใหม่เอง | 1 |
| **Writer** | `claude-opus-5` | เขียนต่อแพลตฟอร์ม · เขียนใหม่ตาม Guard | 3 |
| **Strategist** | `claude-opus-5` | วางแผนจากสต็อกจริง | 3 |

ยังไม่ทำ: Closer (เฟส 4) · Analyst (เฟส 5)

## ใช้งาน

```
# แชท
growth/.venv/Scripts/python.exe -m growth.runtime.inbox "น้ำมะเขือเทศยังมีไหม" --trace

# คอนเทนต์
growth/.venv/Scripts/python.exe -m growth.runtime.studio plan --days 3
growth/.venv/Scripts/python.exe -m growth.runtime.studio write "หัวข้อ" --platform instagram

# ตรวจข้อความเดี่ยว / หน้าเว็บ / เทสต์ / ตรวจข้อมูล ERP
growth/.venv/Scripts/python.exe -m growth.runtime.check "ข้อความ" --platform instagram
growth/.venv/Scripts/python.exe -m growth.runtime.web      # http://127.0.0.1:8765
growth/.venv/Scripts/python.exe growth/agents/test_contracts.py
growth/.venv/Scripts/python.exe -m growth.runtime.erp_audit
```

**ยังไม่มีคีย์โมเดลก็รันได้ทั้งหมด** — ระบบตกไปใช้ `StubProvider` อัตโนมัติ
คำตอบจะขึ้นต้นด้วย `[stub]` เสมอ จะไม่มีทางเข้าใจผิดว่าเป็นของจริง
พอใส่ `ANTHROPIC_API_KEY` ใน `growth/.env` แล้วสลับเป็นของจริงเอง ไม่ต้องแก้โค้ด

## ติดตั้งใหม่ตั้งแต่ต้น

```
ssh -p 2222 frappe@127.0.0.1 'bash /tmp/00-fix-clock.sh && bash /tmp/01-install-postgres.sh'
bash growth/setup/02-load-schema.sh --reset
ssh -p 2222 frappe@127.0.0.1 'source ~/growth.env && psql -h 127.0.0.1 -U growth growth -f /tmp/growth-schema/03-seed-brand.sql'
```

---

## หลักการ 5 ข้อที่ทั้งสคีมายึด

**1. Brand DNA เก็บ "ตัวตน" ไม่เก็บ "ข้อเท็จจริง"**
ราคา สต็อก ล็อต วันหมดอายุ — ERPNext เป็นเจ้าของ Brand DNA เก็บได้แค่ pointer
(`"price_source": "erpnext://Item Price?price_list=Standard Selling"`)
ถ้าละเมิดข้อนี้ AI จะตอบราคาเก่าค้างเป็นเดือนโดยไม่มีใครรู้ — เป็นบั๊กที่พบบ่อยที่สุดของระบบ RAG

**2. Brand DNA 1 เวอร์ชัน = 1 แถว = 1 เอกสาร jsonb สมบูรณ์**
ไม่ normalize เป็นหลายตาราง เพราะ agent ต้องโหลดทั้งก้อนทุกครั้งอยู่แล้ว
ได้ของแถม: immutable, diff ได้, rollback ได้, และ `checksum` บอกได้ว่า output ชิ้นไหนมาจาก DNA เวอร์ชันไหน

**3. กฎแพลตฟอร์มเป็นข้อมูล ไม่ใช่โค้ด**
TikTok อัปเดต Community Guidelines **24 ก.ย. 2026** — ต้องเพิ่มกฎได้โดยไม่ deploy
ทุกกฎมี `source_url` และ `effective_from` ตั้งล่วงหน้าได้

**4. ความยินยอมเป็น append-only ledger — ห้าม UPDATE**
PDPA ต้องพิสูจน์ได้ว่า *ณ วันที่ส่งข้อความนั้น* มีสิทธิ์ส่งหรือไม่
ถ้า UPDATE ทับ จะพิสูจน์ย้อนหลังไม่ได้เลย สถานะปัจจุบันอ่านจาก view `consent_current`

> ⚠️ **บทเรียนจากการรันจริง:** ตอนแรกใช้ `revoke update, delete ... from public`
> ซึ่ง **ไม่กันอะไรเลย** เพราะ owner ของตารางมีสิทธิ์โดยปริยาย และ owner
> ก็คือ role เดียวกับที่แอปต่อเข้ามา ต้องใช้ **trigger** เท่านั้น (ไฟล์ 007)
> เจอตอนรัน DDL จริงครั้งแรก ไม่ใช่ตอนออกแบบ

**5. ข้อความแชทอยู่ที่ Chatwoot ที่นี่เก็บแค่ metadata**
ไม่ก๊อปข้อความมาซ้ำสองที่ — เก็บ `chatwoot_id` แล้วอ้างอิงเอา
ที่เก็บที่นี่คือสิ่งที่ Chatwoot ไม่มี: closing score, ผลตรวจ policy, สายเหตุการณ์

---

## ไฟล์

| ไฟล์ | เนื้อหา |
|---|---|
| `schema/000_extensions.sql` | pgcrypto · pgvector · pg_trgm |
| `schema/001_brand_core.sql` | org · brand · **brand_dna_versions** · proposals · knowledge base |
| `schema/002_policy_content.sql` | **policy_rules** · content_items/variants · policy_evaluations · metrics |
| `schema/003_identity_pdpa.sql` | contacts · identities · **consent_events** · conversations · lead_scores · leads |
| `schema/004_event_store.sql` | **events** (partitioned) · event_types · retention · projection |
| `schema/005_agent_ops.sql` | **agent_runs** (คุมต้นทุน) · outbound_jobs (กันโพสต์ซ้ำ) · usage_counters |
| `schema/006_policy_rules.seed.sql` | กฎเริ่มต้น 11 ข้อ จาก `platform-visibility-notes.md` |
| `schema/007_append_only.sql` | trigger บังคับ append-only **(REVOKE ไม่พอ — ดูด้านล่าง)** |
| `schema/008_events_default_partition.sql` | default partition กัน event หายเมื่อเวลาอยู่นอกช่วง |
| `schema/brand-dna.example.json` | รูปร่าง Brand DNA แบบทั่วไป (placeholder) |
| `schema/brand-dna.ona.v1.json` | **ของจริงของ ONA Healthy** — item_code/price_list/warehouse ดึงจาก ERPNext |
| `setup/00-fix-clock.sh` | แก้นาฬิกา VM (ต้อง sudo) |
| `setup/01-install-postgres.sh` | ติดตั้ง PostgreSQL 18 + pgvector ใน VM (ต้อง sudo) |
| `setup/02-load-schema.sh` | ส่งสคีมาเข้า VM แล้วรัน DDL ตามลำดับ |
| `setup/03-seed-brand.sql` | ใส่องค์กร แบรนด์ และ Brand DNA เวอร์ชัน 1 |
| `setup/04-cloudflare-tunnel.sh` | named tunnel (ต้องมีโดเมน) — สำหรับ webhook จริง |
| `setup/05-quick-tunnel-test.sh` | quick tunnel ไม่ต้องมีโดเมน — พิสูจน์เส้นทางว่าทะลุ |
| `agents/reach_guard.py` | **ตัว Guard จริง** — detector keyword/regex/structural |
| `runtime/db.py` | โหลด Brand DNA แบบตัด facet · โหลดกฎที่มีผลวันนี้ |
| `runtime/orchestrator.py` | **ตัวเดียวที่เขียน DB ได้** — commit event/effect/agent_run |
| `runtime/check.py` | CLI ตรวจข้อความ |
| `runtime/web.py` | หน้าเว็บทดสอบ (stdlib ล้วน) |
| `runtime/llm.py` | ชั้นเชื่อมโมเดล + **StubProvider** + คิดต้นทุนเป็นบาท |
| `runtime/erp.py` | ดึงสต็อก/ล็อต/ราคาจาก ERPNext (อ่านอย่างเดียว) |
| `runtime/inbox.py` | สายงานแชท 2 ชั้น |
| `runtime/studio.py` | สายงานคอนเทนต์ Strategist → Writer ⇄ Guard |
| `runtime/erp_audit.py` | ตรวจว่าข้อมูล ERP พร้อมให้ AI ขายหรือยัง |
| `runtime/prompts.py` | โหลด prompt ที่มีเวอร์ชัน + hash |
| `agents/concierge.py` · `scorer.py` · `writer.py` · `strategist.py` · `auto_reply.py` | ตัว agent |
| `prompts/*.v1.md` | prompt แยกไฟล์ มีเวอร์ชัน แก้ได้โดยไม่แตะโค้ด |
| `schema/009_auto_reply.sql` · `010` · `011` | กฎตอบอัตโนมัติ · เหตุผลส่งต่อคน · ปิดช่อง agent_runs |

---

## ทำไมใช้ PostgreSQL ทั้งที่ ERPNext ใช้ MariaDB

แยกกันโดยตั้งใจ:

- ต้องการ `jsonb` + partition + `pgvector` — MariaDB ทำได้ไม่ดีทั้งสามอย่าง
- ไม่ควรเขียนลงตาราง ERPNext ตรงๆ อยู่แล้ว (Frappe มี hook/permission ของตัวเอง) ต้องผ่าน REST API เท่านั้น
- ถ้าอัปเกรด ERPNext แล้วสคีมาเปลี่ยน ระบบเราไม่พังตาม

ผูกกันด้วยคอลัมน์ `erp_*` ที่เก็บ **ชื่อ document ของ Frappe** (เช่น `erp_customer`, `erp_sales_order`) ไม่ใช่ FK ข้ามฐาน

---

## ตัวอย่าง: 1 โพสต์ ไล่ได้ตั้งแต่บรีฟจนถึงเงินเข้า

ทุก event ในสายนี้ใช้ `correlation_id` เดียวกัน และ `causation_id` ชี้ต่อกันเป็นลูกโซ่

```
correlation_id = 7f3a…
├ content.requested    actor=human:pom        subject=content_item
├ content.generated    actor=agent:writer     platform=instagram   agent_runs +1
├ policy.blocked       actor=agent:reach_guard  rule=ig.health_claim  risk=78
├ content.generated    actor=agent:writer     attempt=2  (เขียนใหม่ตาม fix_hint)
├ policy.evaluated     actor=agent:reach_guard  verdict=pass  risk=21
├ content.published    actor=system           external_id=1789…
├ metrics.captured     ×6 (ชม.ที่ 1,3,6,24,72,168)
├ message.received     actor=customer         "ยังมีของไหม"
├ stock.queried        actor=agent:concierge  → ERPNext Bin + Batch
├ message.sent         actor=agent:concierge  "เหลือ 42 ขวด ล็อต B-2609 หมดอายุ ก.พ. 68"
├ lead.scored          actor=agent:scorer     score=84
├ lead.created         actor=agent:closer     erp_lead=CRM-LEAD-0042
└ order.created        actor=human:pom        erp_sales_order=SAL-ORD-0118
```

จากสายนี้ Analyst ตอบได้ว่า **โพสต์แนวไหนทำให้เกิดยอดขายจริง** ไม่ใช่แค่แนวไหนได้ไลก์เยอะ — นั่นคือเหตุผลทั้งหมดที่ต้องมี event store

---

## ยังไม่ได้ทำในสคีมานี้ (ตั้งใจ)

- ตาราง users/roles/auth — เฟสแรกใช้คนเดียว ยังไม่ต้อง
- Sales Page · A/B testing · Ads Boost — ตัดออกตามแผน (เฟส 4+)
- Row-level security สำหรับ multi-tenant — `org_id` เตรียมไว้แล้ว ค่อยเปิด RLS วันที่ขายเป็น SaaS
