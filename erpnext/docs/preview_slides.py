# -*- coding: utf-8 -*-
"""วาดตัวอย่างสไลด์เป็นภาพ ด้วยฟอนต์ Tahoma ตัวจริงของ Windows
เพื่อตรวจสายตาว่าข้อความล้นกล่องหรือทับกันไหม"""
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image, ImageDraw, ImageFont

DECK = r"C:\Users\User\Desktop\IT-DKHL\erpnext\docs\ONA-Healthy-นำเสนอ.pptx"
OUT = r"C:\Users\User\Desktop\IT-DKHL\erpnext\docs\preview"
EMU = 914400
DPI = 96
REG = r"C:\Windows\Fonts\tahoma.ttf"
BLD = r"C:\Windows\Fonts\tahomabd.ttf"

_cache = {}


def font(sz, bold):
    key = (round(sz), bold)
    if key not in _cache:
        path = BLD if bold else REG
        _cache[key] = ImageFont.truetype(path, max(6, int(sz * DPI / 72)))
    return _cache[key]


prs = Presentation(DECK)
SW = int(prs.slide_width / EMU * DPI)
SH = int(prs.slide_height / EMU * DPI)

overflow = []

for n, slide in enumerate(prs.slides, 1):
    bg = "#FFFFFF"
    f = slide.background.fill
    try:
        if f.type is not None and f.fore_color.rgb is not None:
            bg = "#" + str(f.fore_color.rgb)
    except Exception:
        pass
    img = Image.new("RGB", (SW, SH), bg)
    d = ImageDraw.Draw(img)

    for sh in slide.shapes:
        L = sh.left / EMU * DPI
        T = sh.top / EMU * DPI
        Wd = sh.width / EMU * DPI
        Ht = sh.height / EMU * DPI

        # วาดพื้นรูปทรง
        if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            try:
                col = "#" + str(sh.fill.fore_color.rgb)
            except Exception:
                col = "#EEEEEE"
            try:
                line = "#" + str(sh.line.color.rgb)
            except Exception:
                line = None
            d.rounded_rectangle([L, T, L + Wd, T + Ht], radius=8, fill=col, outline=line, width=2)

        if not sh.has_text_frame or not sh.text_frame.text.strip():
            continue

        y = T
        for p in sh.text_frame.paragraphs:
            txt = "".join(r.text for r in p.runs)
            if not txt.strip():
                continue
            r0 = p.runs[0]
            sz = r0.font.size.pt if r0.font.size else 15
            bold = bool(r0.font.bold)
            try:
                col = "#" + str(r0.font.color.rgb)
            except Exception:
                col = "#333333"
            ft = font(sz, bold)

            # ตัดบรรทัดตามความกว้างกล่อง (รองรับการขึ้นบรรทัดในข้อความ)
            lines = []
            for hard in txt.splitlines() or [txt]:
                cur = ""
                for word in hard.split(" "):
                    test = (cur + " " + word).strip()
                    if d.textlength(test, font=ft) <= Wd or not cur:
                        cur = test
                    else:
                        lines.append(cur)
                        cur = word
                lines.append(cur)

            lh = sz * DPI / 72 * 1.35
            for ln in lines:
                ax = L
                if p.alignment is not None and "CENTER" in str(p.alignment):
                    ax = L + (Wd - d.textlength(ln, font=ft)) / 2
                d.text((ax, y), ln, font=ft, fill=col)
                y += lh

        used = y - T
        if used > Ht + 12:
            overflow.append(f"สไลด์ {n}: ข้อความสูง {used:.0f}px เกินกล่อง {Ht:.0f}px : {sh.text_frame.text[:40]!r}")
        if L + Wd > SW + 2 or T + Ht > SH + 2:
            overflow.append(f"สไลด์ {n}: รูปทรงเลยขอบ")

    img.save(f"{OUT}-{n}.png")

print("RENDERED:", SW, "x", SH, "px ·", len(prs.slides._sldIdLst), "สไลด์")
if overflow:
    print("พบความเสี่ยงข้อความล้น:")
    for o in overflow:
        print("  -", o)
else:
    print("ไม่พบข้อความล้นกล่อง")
