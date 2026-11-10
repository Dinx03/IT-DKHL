"""แล็บ 1.1 — เรียก Claude API ครั้งแรก"""
from common import create, report, text_of

response = create(
    max_tokens=16000,
    messages=[
        {"role": "user", "content": "อธิบายว่า LLM คืออะไร ให้เด็ก ม.ปลายเข้าใจ ใน 3 ประโยค"}
    ],
)

# เช็ค stop_reason ก่อนใช้คำตอบทุกครั้ง
if response.stop_reason == "refusal":
    print("โมเดลปฏิเสธคำขอนี้")
elif response.stop_reason == "max_tokens":
    print("คำตอบถูกตัดกลางคัน ควรเพิ่ม max_tokens")
    print(text_of(response))
else:
    print(text_of(response))

report(response)

# ลองดูโครงสร้างดิบของ response (ไม่มีอะไรซ่อนอยู่)
print("\nชนิดของ content blocks:", [b.type for b in response.content])
