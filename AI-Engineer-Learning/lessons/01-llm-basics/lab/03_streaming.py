"""แล็บ 1.3 — streaming: ข้อความขึ้นทีละส่วน"""
import time

from common import report, stream

start = time.perf_counter()
first_token_at = None

with stream(
    max_tokens=64000,
    messages=[{"role": "user", "content": "เขียนเรื่องสั้น 2 ย่อหน้า เกี่ยวกับวิศวกรที่ไม่ยอมแพ้"}],
) as s:
    for text in s.text_stream:
        if first_token_at is None:
            first_token_at = time.perf_counter() - start
        print(text, end="", flush=True)
    final = s.get_final_message()

total = time.perf_counter() - start
print()
report(final)
# TTFT = Time To First Token คือเวลาที่ผู้ใช้ต้องรอก่อนเห็นตัวอักษรแรก ซึ่งเป็นตัวชี้วัด UX สำคัญ
if first_token_at is not None:
    print(f"TTFT         : {first_token_at:.2f}s")
print(f"total time   : {total:.2f}s")
