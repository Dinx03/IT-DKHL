"""แล็บ 1.2 — system prompt เปลี่ยนพฤติกรรมของโมเดลอย่างไร"""
from common import create, report, text_of

QUESTION = "สต็อกสินค้า A เหลือ 3 ชิ้น ควรทำอะไร"

SYSTEMS = {
    "ไม่มี system prompt": None,
    "ผู้ช่วยบริหารร้าน": (
        "คุณคือผู้ช่วยบริหารร้านขายอุปกรณ์ไอทีที่ใช้ระบบ ERPNext\n"
        "- ตอบภาษาไทย ไม่เกิน 4 บรรทัด\n"
        "- ถ้าข้อมูลไม่พอ ให้ถามกลับ 1 คำถาม ห้ามเดาตัวเลข\n"
        "- ห้ามสั่งซื้อหรือแก้ข้อมูลเอง ให้เสนอทางเลือกเท่านั้น"
    ),
}

for name, system in SYSTEMS.items():
    print(f"\n===== {name} =====")
    kwargs = {"max_tokens": 16000, "messages": [{"role": "user", "content": QUESTION}]}
    if system:
        kwargs["system"] = system
    response = create(**kwargs)
    print(text_of(response))
    report(response)

# สังเกต: input tokens ของแบบที่มี system prompt จะมากกว่า เพราะ system prompt ก็นับเป็น token
