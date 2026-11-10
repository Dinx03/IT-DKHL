# บทที่ 5 — Context Management และ Memory

⏱ ประมาณ 4 ชั่วโมง

## เป้าหมาย
- [ ] เข้าใจว่าทำไม context ถึงเป็น "ทรัพยากรที่มีจำกัด" เหมือน RAM
- [ ] นับ token ก่อนส่ง request ได้
- [ ] รู้จัก 4 เทคนิคจัดการ context: ตัดทอน, ล้างผลเครื่องมือเก่า, สรุปย่อ (compaction), แยกงานให้ subagent
- [ ] ทำ memory ข้าม session ด้วยไฟล์หรือฐานข้อมูล

---

## 1. Context Window = RAM ของโมเดล

ทุกอย่างที่โมเดล "เห็น" ในแต่ละครั้งต้องอยู่ใน context window ได้แก่:
```
[ tools ] + [ system prompt ] + [ messages ทั้งหมด ] + [ คำตอบที่กำลังสร้าง ]
```

Claude รุ่นใหม่มี context window 1 ล้าน token แต่ **ใส่ได้เยอะไม่ได้แปลว่าควรใส่เยอะ**:

| ปัญหา | คำอธิบาย |
|---|---|
| 💰 เงิน | เสียเงินตาม input token **ทุกครั้ง** ที่เรียก API และ agent เรียก API หลายสิบรอบ |
| ⏱ ความเร็ว | input ยาว ทำให้รอนานขึ้น |
| 🎯 ความแม่น | ข้อมูลที่ไม่เกี่ยวข้องมากเกินไป ทำให้โมเดลหลงประเด็น (context rot) |

### ต้นทุนของ agent เติบโตเร็วกว่าที่คิด
ถ้าแต่ละรอบเพิ่มข้อมูลเข้า context 5,000 token แล้วทำงาน 20 รอบ:
- รอบที่ 1 ส่ง 5k, รอบที่ 2 ส่ง 10k, ... รอบที่ 20 ส่ง 100k
- **รวมทั้งหมด ≈ 1,050,000 input token** แม้ข้อมูลจริงจะมีแค่ 100k

(Prompt caching จากบทที่ 2 ช่วยลดส่วนนี้ได้มาก เพราะประวัติเก่าเป็น prefix เดิม)

---

## 2. นับ Token ก่อนส่ง

```python
from common import client, MODEL

count = client.messages.count_tokens(
    model=MODEL,
    system=SYSTEM,
    tools=TOOLS,
    messages=messages,
)
print(count.input_tokens)
```

การนับ token ไม่มีค่าใช้จ่าย ใช้ตรวจก่อนส่งจริงได้ เช่น ถ้าเกิน 150k ให้ย่อ context ก่อน

> ⚠️ อย่าใช้ไลบรารีนับ token ของค่ายอื่น (เช่น tiktoken) เพราะแต่ละค่ายตัด token ไม่เหมือนกัน

---

## 3. เทคนิคที่ 1: ตัดทอนตั้งแต่ต้นทาง

วิธีที่ถูกและได้ผลที่สุดคือ **อย่าให้ข้อมูลขยะเข้า context ตั้งแต่แรก**

```python
def get_sales_report(month: str) -> str:
    rows = db.query(...)                    # อาจได้ 10,000 แถว
    # ❌ return json.dumps(rows)
    # ✅ สรุปก่อนส่ง
    total = sum(r["amount"] for r in rows)
    top5 = sorted(rows, key=lambda r: -r["amount"])[:5]
    return f"ยอดรวม {total:,.0f} บาท จาก {len(rows)} รายการ\nTop 5: {top5}"
```

หลักการ:
- เครื่องมือควรมีพารามิเตอร์ `limit` และ `fields` ให้เลือกดึงเฉพาะที่จำเป็น
- ถ้าต้องตัดผลลัพธ์ ให้ **บอกโมเดลว่าตัด** และบอกวิธีดูส่วนที่เหลือ เช่น "ใช้ offset=50 เพื่อดูหน้าถัดไป"

---

## 4. เทคนิคที่ 2: ล้างผลเครื่องมือเก่า (Context Editing)

ใน agent ที่ทำงานยาว ผลของเครื่องมือจากรอบแรกๆ มักไม่จำเป็นแล้ว
API มีฟีเจอร์ (beta) ที่ล้างผลเครื่องมือเก่าออกให้อัตโนมัติ:

```python
from common import client, MODEL

response = client.beta.messages.create(
    model=MODEL,
    max_tokens=16000,
    betas=["context-management-2025-06-27"],
    context_management={"edits": [{"type": "clear_tool_uses_20250919"}]},
    tools=TOOLS,
    messages=messages,
)
```

ผลของเครื่องมือเก่าจะถูกแทนด้วยข้อความสั้นๆ ว่าถูกล้างไปแล้ว ส่วนโครงของบทสนทนายังอยู่ครบ

---

## 5. เทคนิคที่ 3: สรุปย่อ (Compaction)

เมื่อบทสนทนายาวใกล้เต็ม ให้ **สรุปส่วนเก่าเป็นข้อความสั้น** แล้วใช้สรุปนั้นแทนประวัติเดิม
ถ้าคุณคุยกับ Claude Code นานๆ ก็จะเห็นระบบทำแบบนี้

### แบบให้ API ทำให้ (beta)
```python
response = client.beta.messages.create(
    model=MODEL,
    max_tokens=16000,
    betas=["compact-2026-01-12"],
    context_management={"edits": [{"type": "compact_20260112"}]},
    messages=messages,
)
# ⚠️ ต้อง append response.content ทั้งก้อน เพราะมี compaction block อยู่ข้างใน
messages.append({"role": "assistant", "content": response.content})
```

### แบบเขียนเอง (เข้าใจหลักการ)
```python
# render(msgs) = ฟังก์ชันที่คุณเขียนเอง: แปลง messages เป็นข้อความธรรมดา (role: text)
def compact(messages: list, keep_last: int = 6) -> list:
    old, recent = messages[:-keep_last], messages[-keep_last:]
    summary = create(
        max_tokens=4000,
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": "สรุปบทสนทนาต่อไปนี้ให้กระชับ เก็บ: เป้าหมาย, สิ่งที่ทำไปแล้ว, "
                       "ข้อมูลสำคัญที่พบ (ตัวเลข ชื่อ), สิ่งที่ยังค้างอยู่\n\n"
                       f"<history>{render(old)}</history>",
        }],
    )
    return [{"role": "user", "content": f"[สรุปงานก่อนหน้า]\n{text_of(summary)}"}] + recent
```

**ข้อควรระวังเมื่อเขียนเอง:**
- อย่าตัดกลางคู่ `tool_use` / `tool_result` เพราะ API จะ error ต้องตัดที่ขอบของรอบ
- ทุกครั้งที่ย่อ ข้อมูลบางส่วนจะหายไป ถ้ามีข้อมูลสำคัญ ให้บันทึกลง memory ก่อน (หัวข้อที่ 7)
- ใช้ API compaction ถ้าทำได้ จะปลอดภัยกว่าเขียนเอง

---

## 6. เทคนิคที่ 4: Subagent — แยก context

ถ้างานย่อยต้องอ่านข้อมูลเยอะ (เช่น อ่านเอกสาร 30 ไฟล์เพื่อหาคำตอบเดียว)
ให้ **สร้าง agent ลูกที่มี context ของตัวเอง** แล้วส่งกลับมาแค่ผลสรุป

```
Agent หลัก (context สะอาด)
   │  "ช่วยหาว่าสัญญาไหนหมดอายุเดือนนี้"
   ▼
Subagent (context แยก: อ่าน 30 ไฟล์ ใช้ 200k token)
   │
   └─▶ ส่งกลับแค่: "3 สัญญา: A (15 ต.ค.), B (20 ต.ค.), C (31 ต.ค.)"   ← 50 token
```

เหมือนการ fork process ใน OS คือ memory แยกกัน และสื่อสารกันด้วยข้อความ

```python
def delegate(task: str) -> str:
    """เครื่องมือของ agent หลัก: ส่งงานให้ subagent"""
    return run_agent(task)        # เรียก run_agent จากบทที่ 4 ซึ่งเริ่มจาก messages ว่าง

TOOLS_MAIN = [..., {
    "name": "delegate",
    "description": "มอบงานค้นคว้าที่ต้องอ่านข้อมูลจำนวนมากให้ผู้ช่วย คืนค่าเป็นผลสรุป "
                   "ให้ระบุงานให้ครบ เพราะผู้ช่วยไม่เห็นบทสนทนานี้",
    "input_schema": {...},
}]
```

**ข้อดี:** context ของ agent หลักสะอาด และทำงานย่อยพร้อมกันได้หลายตัว
**ข้อเสีย:** ใช้ token รวมมากขึ้น และ subagent ไม่รู้บริบทของงานหลัก จึงต้องเขียนคำสั่งให้ครบในตัว

---

## 7. Memory ข้าม Session

Context หายไปทุกครั้งที่เริ่มแชทใหม่ ถ้าอยากให้ผู้ช่วย "จำ" ต้องเก็บลงที่ถาวร

### แบบที่ 1: ไฟล์ Markdown (ง่ายที่สุด)
Claude Code ใช้วิธีนี้ (ไฟล์ `MEMORY.md` ที่คุณเห็นในโปรเจกต์นี้ก็ใช้หลักการเดียวกัน)

```python
MEMORY_FILE = Path("memory.md")

def load_memory() -> str:
    return MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""

SYSTEM = f"""คุณคือผู้ช่วยบริหารร้าน
<memory>
{load_memory()}
</memory>
ถ้าผู้ใช้บอกข้อมูลที่ควรจำระยะยาว (ความชอบ, กฎของร้าน) ให้เรียก save_memory"""

def save_memory(fact: str) -> str:
    with MEMORY_FILE.open("a", encoding="utf-8") as f:
        f.write(f"- {fact}\n")
    return "บันทึกแล้ว"
```

### แบบที่ 2: Memory tool ของ API
Anthropic มีเครื่องมือ `memory_20250818` ที่ให้โมเดลจัดการไฟล์ความจำเอง (สร้าง อ่าน แก้ ลบ)
ส่วนเราเขียน backend ว่าจะเก็บไฟล์ไว้ที่ไหน

### แบบที่ 3: ฐานข้อมูล
สำหรับระบบหลายผู้ใช้ ให้เก็บใน Postgres แยกตาม `user_id`
ถ้าความจำมีมาก ให้ใช้ vector search (บทที่ 7) ดึงเฉพาะส่วนที่เกี่ยวข้อง

### ควรจำอะไร และไม่ควรจำอะไร
| ✅ ควรจำ | ❌ ไม่ควรจำ |
|---|---|
| ความชอบของผู้ใช้ ("ชอบรายงานเป็นตาราง") | ข้อมูลที่ดึงจากระบบได้อยู่แล้ว (ยอดขาย สต็อก) เพราะจะล้าสมัย |
| กฎของธุรกิจ ("สั่งของทุกวันจันทร์") | ข้อมูลที่ใช้แค่ในบทสนทนาปัจจุบัน |
| บทเรียนจากความผิดพลาด | รหัสผ่านและข้อมูลส่วนตัวที่อ่อนไหว |

> ⚠️ ความจำอาจล้าสมัยได้ ให้เก็บวันที่ไว้ด้วย และตรวจกับข้อมูลจริงก่อนนำไปใช้

---

## 8. Context Engineering — ภาพรวม

"Context engineering" คือศิลปะของการเลือกว่า **จะใส่อะไรเข้า context ในแต่ละรอบ**
เป็นงานหลักของคนสร้าง agent harness

```
            ┌──────────── Context Window ────────────┐
 tools ───▶ │ นิยามเครื่องมือ (คงที่ → cache ได้)         │
 system ──▶ │ บทบาท + กฎ + memory (คงที่ → cache ได้)    │
 RAG ─────▶ │ เอกสารที่เกี่ยวข้อง (เลือกเฉพาะส่วน)          │
 history ─▶ │ ประวัติ (ย่อ/ล้างผลเครื่องมือเก่า)            │
 user ────▶ │ คำถามล่าสุด                               │
            └────────────────────────────────────────┘
```

---

## สรุปบทที่ 5
1. Context เป็นทรัพยากรที่มีจำกัด ยิ่งยาวยิ่งแพง ยิ่งช้า และยิ่งหลงประเด็น
2. ใช้ `count_tokens` ตรวจก่อนส่ง
3. 4 เทคนิค: ตัดทอนตั้งแต่ต้นทาง, ล้างผลเครื่องมือเก่า, compaction, subagent
4. Memory ข้าม session เก็บในไฟล์หรือฐานข้อมูล จำเฉพาะสิ่งที่ดึงจากระบบไม่ได้

---

## แบบฝึกหัด
1. เพิ่มการนับ token ใน `mini_agent.py` ให้พิมพ์จำนวน token ก่อนส่งทุกรอบ แล้วดูว่าเพิ่มขึ้นเร็วแค่ไหน
2. ใส่ `context_management` แบบ `clear_tool_uses_20250919` แล้วเทียบ input token ก่อนและหลัง
3. ทำ memory แบบไฟล์ให้แชทจากบทที่ 1: บอกว่า "ร้านปิดวันอาทิตย์" แล้วปิดโปรแกรม เปิดใหม่ถามว่า "ร้านเปิดวันไหนบ้าง"
4. ทำเครื่องมือ `delegate` แล้วให้ agent หลักส่งงาน "อ่านทุกไฟล์ใน workspace แล้วหาตัวเลขยอดขาย" ให้ subagent
5. **Capstone:** เขียนรายการสิ่งที่ผู้ช่วยบริหารของคุณควรจำ และสิ่งที่ไม่ควรจำ อย่างละ 5 ข้อ

✅ ไปต่อที่ [บทที่ 6](../06-safety/lesson.md)
