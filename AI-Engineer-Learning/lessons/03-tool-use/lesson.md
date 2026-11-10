# บทที่ 3 — Tool Use (Function Calling)

⏱ ประมาณ 4 ชั่วโมง · บทนี้เป็นประตูไปสู่ agent

## เป้าหมาย
- [ ] เข้าใจว่าโมเดล "ใช้เครื่องมือ" ได้อย่างไร (และไม่ได้รันเครื่องมือเอง)
- [ ] นิยามเครื่องมือด้วย JSON Schema ได้
- [ ] เขียนวงรอบ request → tool_use → tool_result → คำตอบ ได้ครบ
- [ ] ออกแบบเครื่องมือที่โมเดลเลือกใช้ได้ถูกต้อง
- [ ] จัดการ error ของเครื่องมือได้

---

## 1. ปัญหา: LLM ไม่รู้ข้อมูลของคุณ

ถ้าถาม Claude ว่า "สต็อกเมาส์ในร้านเหลือกี่ชิ้น" Claude ตอบไม่ได้ เพราะไม่รู้ข้อมูลในระบบของคุณ
ถ้ามันพยายามตอบ ก็คือการเดา (hallucination)

**วิธีแก้:** บอกโมเดลว่า "มีฟังก์ชันชื่อ `get_stock` ให้ใช้นะ" แล้วให้โมเดลเป็นฝ่าย **ขอ** เรียกฟังก์ชันนั้น

---

## 2. ลำดับการทำงาน (สำคัญที่สุดในบทนี้)

```
 คุณ (โค้ด Python)                              Claude API
 ─────────────────                              ──────────
 1. ส่ง: คำถาม + รายการเครื่องมือ  ─────────────▶
                                                 2. คิด: "ต้องใช้ get_stock"
                                   ◀───────────── 3. ตอบ: stop_reason="tool_use"
                                                    tool_use {name, input, id}
 4. รันฟังก์ชัน get_stock("เมาส์") จริง
    ได้ผล: 12
 5. ส่ง: ประวัติทั้งหมด + tool_result ─────────▶
                                                 6. คิดต่อจากผลที่ได้
                                   ◀───────────── 7. ตอบ: "เมาส์เหลือ 12 ชิ้นครับ"
                                                    stop_reason="end_turn"
```

**จุดที่ต้องเข้าใจ:**
- โมเดล **ไม่ได้รันโค้ด** มันแค่ส่ง JSON บอกว่าอยากเรียกอะไร ด้วย argument อะไร
- **โค้ดของคุณเป็นคนรันจริง** คุณจึงควบคุมได้ทั้งหมดว่าจะรันหรือไม่รัน (เป็นพื้นฐานของความปลอดภัยในบทที่ 6)
- `tool_result` ต้องอ้างถึง `id` ของ `tool_use` ให้ตรงกัน

---

## 3. นิยามเครื่องมือ

เครื่องมือหนึ่งตัวมี 3 ส่วน:

```python
tools = [
    {
        "name": "get_stock",
        "description": (
            "ดูจำนวนสินค้าคงเหลือในคลังของร้าน ณ ปัจจุบัน "
            "ใช้เมื่อผู้ใช้ถามว่าสินค้าเหลือเท่าไร หรือมีของไหม "
            "คืนค่าเป็นจำนวนชิ้น หรือข้อความแจ้งว่าไม่พบสินค้า"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "ชื่อสินค้าภาษาไทยหรืออังกฤษ เช่น 'เมาส์ไร้สาย'",
                }
            },
            "required": ["product_name"],
            "additionalProperties": False,
        },
        "strict": True,     # บังคับให้ input ตรง schema เสมอ
    }
]
```

| ส่วน | หน้าที่ |
|---|---|
| `name` | ชื่อที่โมเดลใช้เรียก (อังกฤษ, snake_case) |
| `description` | **สำคัญที่สุด** โมเดลใช้ข้อความนี้ตัดสินใจว่าจะเรียกเครื่องมือนี้เมื่อไหร่ |
| `input_schema` | JSON Schema ของ argument |

> 💡 **description คือ prompt** ให้เขียนว่า เครื่องมือทำอะไร, ควรใช้เมื่อไหร่, คืนค่าอะไร และมีข้อจำกัดอะไร
> เครื่องมือที่เขียน description ไม่ดี จะถูกเรียกผิดจังหวะ หรือไม่ถูกเรียกเลย

---

## 4. โค้ดครบวงรอบ (รอบเดียว)

```python
import json
from common import create, text_of

# ---------- "ระบบหลังบ้าน" จำลอง (บทที่ 9 จะเปลี่ยนเป็น ERPNext จริง) ----------
STOCK = {"เมาส์ไร้สาย": 12, "คีย์บอร์ด": 0, "จอ 24 นิ้ว": 5}

def get_stock(product_name: str) -> str:
    if product_name not in STOCK:
        return f"ไม่พบสินค้าชื่อ '{product_name}' สินค้าที่มี: {', '.join(STOCK)}"
    return f"{product_name}: เหลือ {STOCK[product_name]} ชิ้น"

TOOL_FUNCTIONS = {"get_stock": get_stock}

# ---------- วงรอบ ----------
messages = [{"role": "user", "content": "เมาส์ไร้สายกับคีย์บอร์ดยังมีของไหม"}]

response = create(max_tokens=16000, tools=tools, messages=messages)
print("stop_reason:", response.stop_reason)          # tool_use

# เก็บคำตอบของ assistant ทั้งก้อน (รวม tool_use block)
messages.append({"role": "assistant", "content": response.content})

# รันทุกเครื่องมือที่โมเดลขอ แล้วรวม tool_result ไว้ใน user message เดียว
tool_results = []
for block in response.content:
    if block.type == "tool_use":
        print(f"→ เรียก {block.name}({block.input})")
        output = TOOL_FUNCTIONS[block.name](**block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output,
        })
messages.append({"role": "user", "content": tool_results})

# ส่งกลับไปให้โมเดลสรุป
final = create(max_tokens=16000, tools=tools, messages=messages)
print(text_of(final))
```

สิ่งที่น่าจะเกิดขึ้น: โมเดลเรียก `get_stock` **2 ครั้งพร้อมกัน** (parallel tool use) คือถามเมาส์กับคีย์บอร์ด
แล้วตอบว่า "เมาส์เหลือ 12 ชิ้น ส่วนคีย์บอร์ดหมดครับ"

### กฎของ parallel tool use
- ข้อความเดียวจาก assistant อาจมี `tool_use` หลายอัน
- ต้องส่ง `tool_result` **ทั้งหมดกลับใน user message เดียว** อย่าแยกส่งทีละข้อความ

---

## 5. จัดการ Error ของเครื่องมือ

เครื่องมือพังได้เสมอ เช่น เน็ตหลุด หรือหาข้อมูลไม่เจอ **อย่าให้โปรแกรม crash** ให้ส่ง error กลับไปให้โมเดลแทน

```python
try:
    output = TOOL_FUNCTIONS[block.name](**block.input)
    result = {"type": "tool_result", "tool_use_id": block.id, "content": output}
except Exception as e:
    result = {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": f"เกิดข้อผิดพลาด: {e}. ลองตรวจชื่อสินค้าอีกครั้ง",
        "is_error": True,
    }
```

**error message ที่ดีช่วยให้โมเดลแก้ปัญหาเองได้**
- ❌ `"Error"` → โมเดลไม่รู้จะทำอะไรต่อ
- ✅ `"ไม่พบสินค้า 'เม้าส์' สินค้าที่มี: เมาส์ไร้สาย, คีย์บอร์ด"` → โมเดลลองเรียกใหม่ด้วยชื่อที่ถูกได้

---

## 6. หลักการออกแบบเครื่องมือ

| หลักการ | ตัวอย่าง |
|---|---|
| **หนึ่งเครื่องมือ หนึ่งหน้าที่ชัดเจน** | `get_stock`, `search_customer` แทนที่จะมี `do_everything` |
| **ชื่อและ description ต้องไม่ทับซ้อนกัน** | ถ้ามี `find_item` กับ `search_product` โมเดลจะสับสนว่าต้องใช้ตัวไหน |
| **คืนผลลัพธ์ที่กระชับ** | คืนเฉพาะฟิลด์ที่จำเป็น ไม่ต้องคืน JSON 5,000 บรรทัด เพราะเปลือง token และทำให้โมเดลหลงประเด็น |
| **แยกเครื่องมือ "อ่าน" ออกจาก "เขียน"** | `get_invoice` (ปลอดภัย) กับ `create_invoice` (ต้องมีคนยืนยัน) |
| **ใช้ enum เมื่อค่าที่รับมีจำกัด** | `"status": {"enum": ["draft", "submitted", "cancelled"]}` |
| **ตั้งค่าเริ่มต้นที่ปลอดภัย** | `limit` มีค่าเริ่มต้น 20 ไม่ใช่ดึงทั้งหมด |

---

## 7. tool_choice — ควบคุมการเลือกเครื่องมือ

```python
tool_choice={"type": "auto"}   # ค่าเริ่มต้น: โมเดลเลือกเองว่าจะใช้เครื่องมือหรือไม่
tool_choice={"type": "none"}   # ห้ามใช้เครื่องมือในรอบนี้
```

ถ้าอยากให้โมเดลใช้เครื่องมือเฉพาะตัว **ให้เขียนสั่งใน prompt** ร่วมกับ `auto` จะเข้ากันได้กับโมเดลรุ่นใหม่ทุกรุ่นมากกว่า
(บางรุ่น เช่น Claude Fable 5.1 ไม่รองรับการบังคับเครื่องมือด้วย `tool_choice` แล้ว)

---

## 8. Server Tools — เครื่องมือที่ Anthropic รันให้

นอกจากเครื่องมือที่เราเขียนเอง ยังมีเครื่องมือที่รันบนเซิร์ฟเวอร์ของ Anthropic ซึ่งเราไม่ต้องเขียนโค้ดรันเอง:

```python
tools = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
]
```

| เครื่องมือ | ทำอะไร |
|---|---|
| `web_search` | ค้นเว็บ ได้ข้อมูลล่าสุดพร้อมแหล่งอ้างอิง |
| `web_fetch` | อ่านเนื้อหาจาก URL |
| `code_execution` | รันโค้ด Python หรือ bash ใน sandbox เหมาะกับการคำนวณหรือวิเคราะห์ไฟล์ |

เครื่องมือกลุ่มนี้มีค่าใช้จ่ายเพิ่มตามการใช้งาน ให้ตรวจราคาก่อนใช้จริง

---

## 9. Tool Runner — ให้ SDK วนลูปแทน

พอเข้าใจวงรอบแล้ว การเขียนลูปเองทุกครั้งจะเริ่มน่าเบื่อ SDK จึงมี **tool runner** ที่ช่วยวนลูปให้

```python
import anthropic
from anthropic import beta_tool

client = anthropic.Anthropic()

@beta_tool
def get_stock(product_name: str) -> str:
    """ดูจำนวนสินค้าคงเหลือในคลังของร้าน

    Args:
        product_name: ชื่อสินค้า เช่น 'เมาส์ไร้สาย'
    """
    return f"{product_name}: เหลือ {STOCK.get(product_name, 0)} ชิ้น"

runner = client.beta.messages.tool_runner(
    model="claude-opus-5",
    max_tokens=16000,
    tools=[get_stock],
    messages=[{"role": "user", "content": "เมาส์ไร้สายเหลือกี่ชิ้น"}],
)
for message in runner:          # ได้ข้อความทุกรอบ จนโมเดลไม่เรียกเครื่องมือแล้ว
    for block in message.content:
        if block.type == "text":
            print(block.text)
```

SDK จะสร้าง schema จาก type hint และ docstring ให้อัตโนมัติ

> 🎓 **แนะนำ:** บทที่ 4 จะให้เขียนลูปเองก่อนเพื่อให้เข้าใจกลไกจริง ในงานจริงค่อยใช้ tool runner

---

## สรุปบทที่ 3
1. โมเดล **ขอ** ใช้เครื่องมือ ส่วนโค้ดของเรา **รัน** เครื่องมือจริง
2. วงรอบคือ tool_use → รันเครื่องมือ → ส่ง tool_result (id ต้องตรงกัน) → โมเดลตอบ
3. description ของเครื่องมือคือ prompt ให้เขียนให้ดี
4. error ให้ส่งกลับไปพร้อม `is_error: True` และข้อความที่ช่วยให้โมเดลแก้ต่อได้
5. แยกเครื่องมืออ่านออกจากเครื่องมือเขียน และคืนผลลัพธ์ให้กระชับ

---

## แบบฝึกหัด
1. เพิ่มเครื่องมือ `get_price(product_name)` และ `calculate_total(items)` แล้วถามว่า "ซื้อเมาส์ 3 ตัวกับจอ 1 จอ ราคารวมเท่าไร"
2. จงใจพิมพ์ชื่อสินค้าผิด (เช่น "เม้าส์") แล้วดูว่าโมเดลแก้ตัวเองได้หรือไม่ จากนั้นลองปรับ error message ให้ช่วยโมเดลได้มากขึ้น
3. ลองเขียน description แย่ๆ (เช่น `"get data"`) แล้วสังเกตพฤติกรรมของโมเดลเทียบกับ description ที่ดี
4. **Capstone:** ออกแบบ (ยังไม่ต้องเขียนโค้ด) รายการเครื่องมือ 6–8 ตัวที่ผู้ช่วยบริหาร ERPNext ควรมี
   และระบุว่าแต่ละตัวเป็นเครื่องมือ "อ่าน" หรือ "เขียน"

✅ ไปต่อที่ [บทที่ 4](../04-agent-loop/lesson.md)
