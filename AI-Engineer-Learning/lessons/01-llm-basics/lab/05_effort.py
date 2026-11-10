"""แล็บ 1.5 — effort: แลกความละเอียดกับเวลาและเงิน"""
import time

from common import cost_usd, create, text_of

QUESTION = (
    "ร้านมีสินค้า 3 ตัว: A ขายวันละ 5 ชิ้น เหลือ 12, "
    "B ขายวันละ 2 ชิ้น เหลือ 30, C ขายวันละ 8 ชิ้น เหลือ 20 "
    "ถ้าสั่งของใช้เวลา 3 วันถึงร้าน ควรสั่งตัวไหนก่อน เรียงลำดับพร้อมเหตุผลสั้นๆ"
)

for effort in ["low", "high"]:
    start = time.perf_counter()
    response = create(
        max_tokens=16000,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": QUESTION}],
    )
    elapsed = time.perf_counter() - start
    print(f"\n===== effort={effort} ({elapsed:.1f}s, "
          f"output={response.usage.output_tokens} tokens, "
          f"${cost_usd(response.usage, response.model):.5f}) =====")
    print(text_of(response))

# คำถาม: คำตอบต่างกันไหม ถ้าคำตอบถูกทั้งคู่ งานแบบนี้ควรใช้ effort ไหนใน production
