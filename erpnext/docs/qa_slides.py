# -*- coding: utf-8 -*-
"""ตรวจคุณภาพสไลด์: เนื้อหา ขอบเขต การซ้อนทับ และความเสี่ยงข้อความล้น"""
from pptx import Presentation
from pptx.util import Emu

DECK = r"C:\Users\User\Desktop\IT-DKHL\erpnext\docs\ONA-Healthy-นำเสนอ.pptx"
EMU_IN = 914400

prs = Presentation(DECK)
W = prs.slide_width / EMU_IN
H = prs.slide_height / EMU_IN
print(f"ขนาดสไลด์: {W:.3f} x {H:.3f} นิ้ว | จำนวน {len(prs.slides._sldIdLst)} สไลด์")

problems = []

# ความกว้างเฉลี่ยต่อตัวอักษร (สัดส่วนของ font size) - ไทยใน Tahoma ค่อนข้างแคบ
def est_w(txt, sz):
    w = 0.0
    for ch in txt:
        if "\u0e30" <= ch <= "\u0e3a" or "\u0e47" <= ch <= "\u0e4e":
            continue                      # สระบน/ล่าง วรรณยุกต์ ไม่กินความกว้าง
        elif "\u0e00" <= ch <= "\u0e7f":
            w += sz * 0.52                # พยัญชนะไทย
        elif ch == " ":
            w += sz * 0.28
        else:
            w += sz * 0.55                # ละติน/ตัวเลข
    return w / 72.0                       # pt -> นิ้ว

for idx, slide in enumerate(prs.slides, 1):
    print(f"\n───── สไลด์ {idx} ─────")
    boxes = []
    for sh in slide.shapes:
        L, T = sh.left / EMU_IN, sh.top / EMU_IN
        Wd, Ht = sh.width / EMU_IN, sh.height / EMU_IN
        boxes.append((L, T, Wd, Ht, sh))

        # 1) หลุดขอบสไลด์
        if L < -0.01 or T < -0.01 or L + Wd > W + 0.01 or T + Ht > H + 0.01:
            problems.append(f"สไลด์ {idx}: รูปทรงหลุดขอบ ({L:.2f},{T:.2f}) {Wd:.2f}x{Ht:.2f}")

        # 2) ข้อความล้นกล่อง
        if sh.has_text_frame and sh.text_frame.text.strip():
            for p in sh.text_frame.paragraphs:
                txt = "".join(r.text for r in p.runs)
                if not txt.strip():
                    continue
                sz = next((r.font.size.pt for r in p.runs if r.font.size), 15)
                need = est_w(txt, sz)
                lines = max(1, int(need / Wd) + (1 if need % Wd else 0))
                need_h = lines * sz * 1.5 / 72.0
                if need > Wd and lines == 1:
                    problems.append(f"สไลด์ {idx}: ข้อความอาจล้นแนวนอน ({need:.2f}\" > {Wd:.2f}\") : {txt[:40]}")
                if need_h > Ht + 0.35:
                    problems.append(f"สไลด์ {idx}: ข้อความอาจล้นแนวตั้ง (ต้อง {need_h:.2f}\" มี {Ht:.2f}\") : {txt[:40]}")
            print(f"  [{sh.shape_type}] {sh.text_frame.text[:70]!r}")

    # 3) การ์ดซ้อนทับกัน (เฉพาะรูปทรงที่ไม่ใช่กล่องข้อความ)
    cards = [b for b in boxes if not b[4].has_text_frame or not b[4].text_frame.text.strip()]
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            a, b = cards[i], cards[j]
            ox = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
            oy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            if ox > 0.05 and oy > 0.05:
                small = min(a[2] * a[3], b[2] * b[3])
                if ox * oy > small * 0.5:
                    problems.append(f"สไลด์ {idx}: รูปทรงซ้อนกันมาก {ox:.2f}x{oy:.2f}\"")

print("\n" + "=" * 60)
if problems:
    print(f"พบจุดที่ต้องดู {len(problems)} จุด:")
    for p in problems:
        print("  -", p)
else:
    print("ไม่พบปัญหาขอบเขต การซ้อนทับ หรือข้อความล้น")

# ตรวจข้อความค้างจากแม่แบบ
import re
alltext = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
bad = re.findall(r"lorem|ipsum|TODO|\[insert|xxx", alltext, re.I)
print("ข้อความค้าง:", bad if bad else "ไม่มี")
