# ส่งมอบงาน — ONA Growth Platform

_ปรับล่าสุด 13 ก.ย. 2026_

## เปิดระบบดู 3 คำสั่ง

```bash
# ศูนย์กลาง — ของที่รอคนทั้งหมด
growth/.venv/Scripts/python.exe -m growth.runtime.console      # :8766

# ตรวจข้อความก่อนโพสต์
growth/.venv/Scripts/python.exe -m growth.runtime.web          # :8765

# เทสต์ทั้งหมด (39 เคส ควรผ่านหมด)
growth/.venv/Scripts/python.exe -m growth.tests.run_all

# ล้างขยะที่เทสต์ทิ้งไว้ — ต้องทำทุกครั้งหลังรันเทสต์
ssh -p 2222 frappe@127.0.0.1 'bash /tmp/07-clean-test-data.sh'
```

> เทสต์สร้าง Lead จริงใน ERPNext ทุกรอบ (เพื่อพิสูจน์ว่าเส้นทางเขียนใช้ได้จริง)
> และลบเองไม่ได้เพราะ user ของระบบไม่มีสิทธิ์ลบโดยตั้งใจ
> ถ้าไม่ล้าง Lead ปลอมจะสะสมจนปนกับลูกค้าจริง

## ทีม agent ครบ 7 ตัว

| Agent | โมเดล | ทำอะไร |
|---|---|---|
| Auto-Reply | ไม่ใช้ LLM | กฎตายตัว ทำงานก่อน AI เสมอ · 0 บาท |
| Reach Guard | กฎก่อน แล้วค่อย haiku | ตรวจก่อนเผยแพร่ · ไม่เขียนใหม่เอง |
| Concierge | opus-5 | ตอบแชท เรียก ERP tool เอง |
| Scorer | haiku-4-5 | คะแนนโอกาสปิด · ไม่ใช้ Brand DNA |
| Closer | haiku-4-5 | เสนอสร้างลีด · กฎตัดสิน โมเดลแค่สรุป |
| Writer | opus-5 | เขียนต่อแพลตฟอร์ม · เขียนใหม่ตาม Guard |
| Strategist | opus-5 | วางแผนจากสต็อกจริง |
| Analyst | opus-5 | เสนอแก้ Brand DNA จากข้อมูลจริง |

## สิ่งที่รอคุณ (ผมทำแทนไม่ได้)

**1. สต็อกใน ERPNext — มีผลมากที่สุด**
ตอนนี้ AI ขายได้จริง 1 จาก 14 รายการ ที่เหลือคงเหลือเป็น 0
ถ้ามีของจริงต้องรับเข้าสต็อกก่อน ไม่งั้นระบบจะไล่ลูกค้ากลับ
ตรวจซ้ำได้ด้วย `python -m growth.runtime.erp_audit`

**2. LINE Official Account** → Channel secret + access token
**3. คีย์โมเดล** → ใส่ `ANTHROPIC_API_KEY=...` ใน `growth/.env` บรรทัดเดียว
**4. โดเมน** → สำหรับ URL webhook คงที่ (ตอนนี้ใช้ quick tunnel ได้ แต่ URL เปลี่ยนทุกครั้ง)
**5. ชื่อไทยสินค้า 14 รายการ** — ผมเดาจากชื่ออังกฤษ ต้องให้คนขายจริงตรวจ
   (`select erp_item_code, title, body from knowledge_docs where category='product'`)

## ต้องตั้งให้รันเองทุกคืน

```bash
growth/.venv/Scripts/python.exe -m growth.runtime.nightly
```

สร้าง partition ล่วงหน้า 3 เดือน · ล้าง PII ตามนโยบาย · รีเฟรช matview · รัน Analyst

**ถ้าไม่ตั้ง: partition มีถึงแค่ ธ.ค. 2026** พ้นจากนั้น event จะตกลง `events_default`
เงียบๆ และ PDPA retention จะไม่เคยทำงาน

ตั้งด้วย Task Scheduler ของ Windows (ทุกวัน ตี 2) หรือ cron ใน VM

## ของที่ยังไม่ได้ทำ และเหตุผล

| | ทำไมยัง |
|---|---|
| ตัวรับ webhook ของ Chatwoot | ยังไม่รู้รูปร่าง payload จริง เดาไปก็ต้องรื้อ |
| เผยแพร่ FB/IG จริง | ต้อง OAuth ซึ่งต้องใช้บัญชีคุณ |
| ดึง metrics กลับ | ต้องต่อ API แพลตฟอร์มก่อน |
| `all.unoriginal` ใช้จริง | ต้องมีโพสต์เก่าสะสมก่อนถึงจะเทียบได้ |
| Chatwoot | เขียนสคริปต์ไว้แล้ว (`08-install-chatwoot.sh`) **แต่ยังไม่เคยรัน** |

## ข้อควรรู้ที่เสียเวลาค้นมาแล้ว

- **Docker ใช้ไม่ได้** บนเครื่องนี้ (WSL ไม่ได้ลง) — งาน Linux ทั้งหมดไปที่ VM
- **นาฬิกา VM เพี้ยนได้** เมื่อ VM หยุดนาน เช็คด้วย `timedatectl` ก่องานที่พึ่งเวลา
- **`bench` ไม่อยู่ใน PATH** ของ non-interactive ssh → ใช้ `~/.local/bin/bench`
- **user `growth-agent@ona.local` ลบอะไรใน ERPNext ไม่ได้** โดยตั้งใจ
  ล้างข้อมูลทดสอบด้วย `bash /tmp/07-clean-test-data.sh` (สิทธิ์ admin)
- **`consent_events` และ `events` ลบไม่ได้** — trigger บังคับ append-only
  ล้างข้อมูลทดสอบใช้ `truncate` ไม่ใช่ `delete`

## บั๊กที่เจอจากการรันจริง (ไม่ใช่จากการอ่านโค้ด)

1. `REVOKE ... FROM public` ไม่กัน owner → PDPA ledger แก้ได้ · แก้ด้วย trigger (007)
2. `now()` คืนเวลาเริ่มทรานแซกชัน → event เรียงลำดับไม่ได้ · แก้เป็น `clock_timestamp()`
3. event นอกช่วง partition → insert ล้มเหลว ข้อมูลหาย · แก้ด้วย default partition (008)
4. `tool_calls`, `prompt_hash`, `requires_approval` มีในสัญญาแต่ไม่มีคอลัมน์ (011, 012)
5. escalation reason ไม่เคยถูกบันทึก → คิวบอกเหตุผลผิด (010)
6. view `events_partition_health` cast วันที่ผิด — ไม่มีใครเรียกจึงไม่มีใครรู้ (013)
7. prompt หายไฟล์เดียวทำให้ Reach Guard ล่มทั้งด่าน

ทั้งเจ็ดข้อ unit test แบบ mock จับไม่ได้เลย — เทสต์ใน `growth/tests/` จึงแตะของจริง
