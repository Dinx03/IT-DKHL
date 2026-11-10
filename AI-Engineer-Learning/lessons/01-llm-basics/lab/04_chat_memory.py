"""แล็บ 1.4 — API เป็น stateless: เราต้องเก็บความจำเอง

พิมพ์คุยได้เรื่อยๆ พิมพ์ 'exit' เพื่อออก
สังเกตว่า input tokens เพิ่มขึ้นทุกรอบ เพราะเราส่งประวัติทั้งหมดเข้าไปใหม่
"""
from common import cost_usd, create, text_of

SYSTEM = "คุณคือเพื่อนติวเตอร์ด้าน AI ตอบภาษาไทย สั้น กระชับ"
messages = []   # ← นี่แหละคือ "ความจำ" ทั้งหมดของแชท
total_cost = 0.0

while True:
    user_text = input("\nคุณ: ").strip()
    if user_text.lower() in {"exit", "quit"}:
        break
    if not user_text:
        continue

    messages.append({"role": "user", "content": user_text})
    response = create(max_tokens=16000, system=SYSTEM, messages=messages)

    # เก็บ response.content ทั้งก้อน (ไม่ใช่แค่ข้อความ) เพื่อให้ block อื่นๆ อย่าง thinking ถูกส่งกลับไปครบ
    messages.append({"role": "assistant", "content": response.content})

    print(f"Claude: {text_of(response)}")
    cost = cost_usd(response.usage, response.model)
    total_cost += cost
    print(f"  [รอบที่ {len(messages)//2} | input={response.usage.input_tokens} "
          f"output={response.usage.output_tokens} | ${cost:.5f} | รวม ${total_cost:.5f}]")

# ทดลอง: บอกชื่อตัวเองในรอบแรก แล้วถามในรอบที่ 3 ว่า "ผมชื่ออะไร"
# จากนั้นลองลบบรรทัดที่เรียก messages.append ของ assistant แล้วรันใหม่ ดูว่าเกิดอะไรขึ้น
