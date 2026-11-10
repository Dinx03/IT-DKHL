# -*- coding: utf-8 -*-
"""สร้างสไลด์นำเสนอระบบ ERP ให้เจ้าของสวน ONA Healthy"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

OUT = r"C:\Users\User\Desktop\IT-DKHL\erpnext\docs\ONA-Healthy-นำเสนอ.pptx"

# ---- จานสี: ขาวเป็นพื้น เขียวเป็นโครง แดงเป็นจุดแต้ม ----
# (ตามหลักแบรนด์: "สีแดงเป็นเครื่องเคียง ไม่ใช่พื้น")
GREEN = RGBColor(0x1F, 0x4D, 0x2B)
GREEN_L = RGBColor(0x3A, 0x6B, 0x45)
RED = RGBColor(0xC0, 0x39, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x33, 0x38, 0x35)
MUTED = RGBColor(0x7A, 0x82, 0x7C)
TINT = RGBColor(0xF2, 0xF5, 0xF1)
LINE = RGBColor(0xD8, 0xDF, 0xD9)

F = "Tahoma"
W, H = 13.333, 7.5
M = 0.9  # ขอบซ้าย/ขวา

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)


def slide(dark=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    f = s.background.fill
    f.solid()
    f.fore_color.rgb = GREEN if dark else WHITE
    return s


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=0):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, r in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if space and i:
            p.space_before = Pt(space)
        run = p.add_run()
        run.text = r["t"]
        fo = run.font
        fo.name = F
        fo.size = Pt(r.get("sz", 15))
        fo.bold = r.get("b", False)
        fo.color.rgb = r.get("c", INK)
        if r.get("line"):
            p.line_spacing = r["line"]
    return tb


def card(s, x, y, w, h, fill=TINT, border=None):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = 0.06
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if border:
        sh.line.color.rgb = border
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def dot(s, x, y, d=0.22, color=RED):
    sh = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


# ═══════════════ 1 · ปก ═══════════════
s = slide(dark=True)
dot(s, M, 1.55, 0.26)
text(s, M + 0.42, 1.5, 6, 0.4, [{"t": "ONA HEALTHY", "sz": 14, "b": True, "c": WHITE}])
text(s, M, 2.15, 11.2, 2.2, [
    {"t": "ระบบจัดการสวน", "sz": 46, "b": True, "c": WHITE, "line": 1.25},
    {"t": "การผลิต และสต็อก", "sz": 46, "b": True, "c": WHITE, "line": 1.25},
])
text(s, M, 4.75, 10, 0.9, [
    {"t": "ต้นแบบที่ใส่สินค้าจริงของสวนครบทุกรายการ", "sz": 17, "c": RGBColor(0xC9, 0xDA, 0xCD)},
])
text(s, M, 6.35, 10, 0.4, [
    {"t": "สาธิตระบบ · กันยายน 2569", "sz": 12, "c": RGBColor(0x9F, 0xB8, 0xA6)}])
s.notes_slide.notes_text_frame.text = (
    "เปิดด้วยประโยคนี้: ผมเอาระบบ ERP ที่โรงงานใหญ่ใช้กัน มาปรับให้เป็นของสวนโดยเฉพาะ "
    "ใส่สินค้าจริงเข้าไปครบทุกตัวแล้ว ตัวเลขต้นทุนยังเป็นค่าสมมติเพราะเรายังไม่เคยชั่งจริง")

# ═══════════════ 2 · ปัญหา ═══════════════
s = slide()
text(s, M, 0.75, 11, 0.8, [{"t": "สามเรื่องที่สวนยังตอบไม่ได้วันนี้", "sz": 38, "b": True, "c": GREEN}])
items = [
    ("ออร์เดอร์อยู่ในโน้ต", "โทรศัพท์หายหรือเครื่องพัง\n= ประวัติการขายหายหมด\nสิ้นเดือนต้องไล่อ่านเอง"),
    ("ไม่รู้ต้นทุนจริงต่อขวด", "น้ำขวดละ 56 บาท\nกำไรเท่าไหร่กันแน่\nยังไม่เคยมีใครคำนวณจริง"),
    ("สาวกลับไม่ได้", "ถ้าลูกค้าบอกว่าขวดมีปัญหา\nเราบอกไม่ได้ว่ามาจาก\nมะเขือเทศรอบไหน"),
]
cw, gap = 3.55, 0.32
for i, (head, body) in enumerate(items):
    x = M + i * (cw + gap)
    card(s, x, 2.0, cw, 2.95)
    dot(s, x + 0.42, 2.38, 0.28)
    text(s, x + 0.42, 2.9, cw - 0.84, 0.5, [{"t": head, "sz": 21, "b": True, "c": GREEN}])
    text(s, x + 0.42, 3.55, cw - 0.84, 1.2, [{"t": body, "sz": 14, "c": MUTED, "line": 1.5}])
text(s, M, 5.45, 11.4, 0.5, [
    {"t": "ทั้งสามเรื่องนี้แก้ได้ด้วยระบบเดียวกัน", "sz": 16, "b": True, "c": RED}])
s.notes_slide.notes_text_frame.text = "อย่ารีบข้าม ให้เจ้าของสวนพยักหน้าเห็นด้วยกับปัญหาก่อน"

# ═══════════════ 3 · สิ่งที่ทำมา ═══════════════
s = slide()
text(s, M, 0.75, 11, 0.8, [{"t": "สิ่งที่อยู่ในระบบแล้ววันนี้", "sz": 38, "b": True, "c": GREEN}])
text(s, M, 1.62, 11, 0.5, [
    {"t": "ไม่ใช่ข้อมูลตัวอย่างจากโปรแกรม แต่เป็นสินค้าจริงของสวนทุกรายการ", "sz": 15, "c": MUTED}])
stats = [("17", "รายการสินค้า"), ("3", "กลุ่มสินค้า"), ("2", "ล็อตที่ติดตามอยู่"), ("1", "สูตรการผลิต")]
sw = 2.72
for i, (n, lab) in enumerate(stats):
    x = M + i * (sw + 0.22)
    card(s, x, 2.5, sw, 1.85, fill=WHITE, border=LINE)
    text(s, x, 2.78, sw, 0.9, [{"t": n, "sz": 44, "b": True, "c": RED}], align=PP_ALIGN.CENTER)
    text(s, x, 3.72, sw, 0.4, [{"t": lab, "sz": 13, "c": MUTED}], align=PP_ALIGN.CENTER)
card(s, M, 4.75, 11.53, 1.5)
text(s, M + 0.5, 5.05, 10.5, 1.0, [
    {"t": "สายสุขภาพ 7 รายการ   ·   สายผิว 8 รายการ   ·   วัตถุดิบและบรรจุภัณฑ์ 2 รายการ",
     "sz": 17, "b": True, "c": GREEN},
    {"t": "ทุกรายการมีราคา หน่วยนับ และระบบล็อตพร้อมใช้งาน", "sz": 13, "c": MUTED},
], space=8)
s.notes_slide.notes_text_frame.text = "เปิดหน้า Item List ให้ดูจริงตอนนี้ แล้วคลิก Onato ขวด 75 ml"

# ═══════════════ 4 · ต้นทุน ═══════════════
s = slide()
text(s, M, 0.75, 11, 0.8, [{"t": "ต้นทุนจริงต่อขวด", "sz": 38, "b": True, "c": GREEN}])
text(s, M, 1.62, 11, 0.5, [
    {"t": "ระบบคำนวณจากสูตรการผลิต ไม่ต้องกดเครื่องคิดเลขเอง", "sz": 15, "c": MUTED}])
nums = [("12.50", "ต้นทุนวัตถุดิบ", MUTED), ("56.00", "ราคาขาย", GREEN), ("43.50", "ส่วนต่างต่อขวด", RED)]
bw = 3.55
for i, (n, lab, col) in enumerate(nums):
    x = M + i * (bw + 0.32)
    card(s, x, 2.45, bw, 2.15, fill=TINT if i < 2 else WHITE, border=None if i < 2 else RED)
    text(s, x, 2.8, bw, 1.0, [{"t": n, "sz": 50, "b": True, "c": col}], align=PP_ALIGN.CENTER)
    text(s, x, 3.85, bw, 0.4, [{"t": lab + "  (บาท)", "sz": 13, "c": MUTED}], align=PP_ALIGN.CENTER)
text(s, M, 5.0, 11.4, 0.5, [
    {"t": "คิดเป็นส่วนต่าง 78% ของราคาขาย", "sz": 20, "b": True, "c": GREEN}])
card(s, M, 5.75, 11.53, 1.15, fill=RGBColor(0xFD, 0xF4, 0xF3))
text(s, M + 0.45, 5.98, 10.6, 0.8, [
    {"t": "ตัวเลขนี้ยังเชื่อไม่ได้", "sz": 14, "b": True, "c": RED},
    {"t": "ตั้งอยู่บนค่าสมมติ และยังไม่รวมค่าแรง ค่าไฟ ค่าขนส่ง", "sz": 13, "c": MUTED},
], space=4)
s.notes_slide.notes_text_frame.text = (
    "สไลด์สำคัญที่สุด ย้ำว่าเป็นค่าสมมติ แล้วบอกว่าถ้าพี่ชั่งจริงครั้งเดียว "
    "ระบบจะบอกกำไรจริงทันที และคำนวณใหม่เองทุกครั้งที่ราคามะเขือเทศเปลี่ยน")

# ═══════════════ 5 · สาวกลับ ═══════════════
s = slide()
text(s, M, 0.75, 11, 0.8, [{"t": "สาวกลับได้ถึงรอบเก็บเกี่ยว", "sz": 38, "b": True, "c": GREEN}])
text(s, M, 1.62, 11.4, 0.5, [
    {"t": "ลูกค้าบอกแค่เลขล็อตข้างขวด ระบบบอกได้ทันทีว่ามาจากมะเขือเทศรอบไหน", "sz": 15, "c": MUTED}])
chain = [("ขวดที่ลูกค้าซื้อ", "24 ขวด"), ("ล็อตน้ำมะเขือเทศ", "หมดอายุ 2570"),
         ("รอบการผลิต", "9 ก.ย. 2569"), ("ล็อตมะเขือเทศสด", "12.5 กก.")]
bw2 = 2.55
for i, (head, sub) in enumerate(chain):
    x = M + i * (bw2 + 0.44)
    card(s, x, 2.55, bw2, 1.75, fill=WHITE, border=GREEN if i in (0, 3) else LINE)
    text(s, x + 0.2, 2.85, bw2 - 0.4, 0.8, [{"t": head, "sz": 15, "b": True, "c": GREEN}],
         align=PP_ALIGN.CENTER)
    text(s, x + 0.2, 3.62, bw2 - 0.4, 0.4, [{"t": sub, "sz": 12, "c": MUTED}], align=PP_ALIGN.CENTER)
    if i < 3:
        a = s.shapes.add_shape(MSO_SHAPE.LEFT_ARROW, Inches(x + bw2 + 0.08), Inches(3.2),
                               Inches(0.3), Inches(0.4))
        a.fill.solid()
        a.fill.fore_color.rgb = RED
        a.line.fill.background()
        a.shadow.inherit = False
card(s, M, 4.85, 11.53, 1.35, fill=TINT)
text(s, M + 0.5, 5.12, 10.5, 1.0, [
    {"t": "ทำไมเรื่องนี้สำคัญกับสวนเรา", "sz": 17, "b": True, "c": GREEN},
    {"t": "ถ้าสินค้ามีปัญหา เรียกคืนเฉพาะล็อตนั้น ไม่ต้องเรียกคืนทั้งหมด   ·   "
          "เครื่องหมาย Q ต้องการข้อมูลชุดนี้อยู่แล้ว", "sz": 13, "c": MUTED, "line": 1.5},
], space=6)
s.notes_slide.notes_text_frame.text = (
    "เล่าเป็นเรื่อง: ลูกค้าโทรมาบอกว่าขวดมีปัญหา บอกแค่เลขล็อต แล้วเปิดใบส่งของให้ดูจริง "
    "ปิดท้ายว่าคู่แข่งที่จ้างโรงงานผลิตทำแบบนี้ไม่ได้ เพราะเขาไม่รู้ว่าวัตถุดิบมาจากไหน")

# ═══════════════ 6 · สาธิตสด ═══════════════
s = slide(dark=True)
dot(s, M, 2.62, 0.3)
text(s, M, 3.15, 11, 1.2, [{"t": "ขอเปิดระบบจริงให้ดู", "sz": 44, "b": True, "c": WHITE}])
text(s, M, 4.5, 11, 0.8, [
    {"t": "สินค้า  ·  สูตรการผลิต  ·  ล็อตและวันหมดอายุ  ·  ใบส่งของ  ·  สต็อกคงเหลือ",
     "sz": 16, "c": RGBColor(0xC9, 0xDA, 0xCD)}])
s.notes_slide.notes_text_frame.text = (
    "สลับไปที่เบราว์เซอร์ ใช้ Ctrl+G พิมพ์ชื่อหน้าจอ ตามลำดับใน สคริปต์นำเสนอ.md")

# ═══════════════ 7 · สิ่งที่ขอจากเจ้าของสวน ═══════════════
s = slide()
text(s, M, 0.75, 11.4, 0.8, [{"t": "ขอตัวเลขจริงจากพี่ 3 ตัว", "sz": 38, "b": True, "c": GREEN}])
text(s, M, 1.62, 11.4, 0.5, [
    {"t": "แค่สามตัวนี้ ระบบจะบอกกำไรจริงต่อขวดได้ทันที และคำนวณใหม่เองตลอดไป",
     "sz": 15, "c": MUTED}])
asks = [
    ("1", "มะเขือเทศ 1 กิโลกรัม ได้น้ำกี่ขวด", "ชั่งครั้งเดียวตอนผลิตรอบหน้า จดไว้ว่าใช้กี่กิโล ได้กี่ขวด"),
    ("2", "ราคามะเขือเทศต่อกิโลกรัม", "คิดจากต้นทุนปลูกจริง หรือราคาที่ขายส่งได้ถ้าไม่แปรรูป"),
    ("3", "ราคาขวด ฝา และฉลาก", "ดูจากใบเสร็จครั้งล่าสุดที่สั่งซื้อ"),
]
for i, (n, head, sub) in enumerate(asks):
    y = 2.45 + i * 1.42
    card(s, M, y, 11.53, 1.22, fill=TINT if i % 2 == 0 else WHITE, border=None if i % 2 == 0 else LINE)
    text(s, M + 0.45, y + 0.26, 0.6, 0.7, [{"t": n, "sz": 30, "b": True, "c": RED}])
    text(s, M + 1.25, y + 0.22, 9.6, 0.45, [{"t": head, "sz": 19, "b": True, "c": GREEN}])
    text(s, M + 1.25, y + 0.72, 9.6, 0.4, [{"t": sub, "sz": 13, "c": MUTED}])
s.notes_slide.notes_text_frame.text = "นี่คือสิ่งที่ต้องการจริง ๆ จากการประชุมนี้ อย่าลืมพูด"

# ═══════════════ 8 · ข้อจำกัด ═══════════════
s = slide()
text(s, M, 0.75, 11.4, 0.8, [{"t": "ข้อจำกัดที่ต้องบอกตรง ๆ", "sz": 38, "b": True, "c": GREEN}])
text(s, M, 1.62, 11.4, 0.5, [
    {"t": "ระบบยังไม่พร้อมใช้กับงานจริงทั้งหมด นี่คือสิ่งที่ยังขาด", "sz": 15, "c": MUTED}])
lims = [
    ("ราคาสินค้ายังไม่ยืนยัน", "ที่ใส่มาจากเพจ Facebook และโบรชัวร์ ต้องให้พี่ตรวจก่อนใช้จริง"),
    ("วันหมดอายุใส่ได้ 5 จาก 15 รายการ", "ที่เหลือต้องดูจากฉลากจริง ไม่ควรเดาเพราะเป็นอาหารและเครื่องสำอาง"),
    ("ออร์เดอร์จากไลน์ยังต้องคีย์เอง", "ระบบไม่ได้ดึงมาให้อัตโนมัติ แต่ทำตัวช่วยลดงานได้"),
    ("ยังไม่ได้ทำฝั่งบัญชีและภาษี", "ตั้งใจเว้นไว้ ต้องคุยกับสำนักงานบัญชีก่อน"),
]
for i, (head, sub) in enumerate(lims):
    x = M + (i % 2) * (5.77 + 0.32)
    y = 2.45 + (i // 2) * 1.85
    card(s, x, y, 5.77, 1.6, fill=WHITE, border=LINE)
    dot(s, x + 0.42, y + 0.34, 0.18)
    text(s, x + 0.78, y + 0.26, 4.6, 0.5, [{"t": head, "sz": 16, "b": True, "c": GREEN}])
    text(s, x + 0.78, y + 0.82, 4.6, 0.7, [{"t": sub, "sz": 12.5, "c": MUTED, "line": 1.45}])
text(s, M, 6.4, 11.4, 0.5, [
    {"t": "บอกข้อจำกัดเองดีกว่าให้ถูกจับได้ทีหลัง", "sz": 14, "c": MUTED}])
s.notes_slide.notes_text_frame.text = "การพูดข้อจำกัดเองทำให้ทั้งงานน่าเชื่อถือขึ้น ไม่ใช่ลดลง"

# ═══════════════ 9 · ขั้นต่อไป ═══════════════
s = slide(dark=True)
text(s, M, 0.9, 11.4, 0.9, [{"t": "ถ้าพี่เอาด้วย ขั้นต่อไปคือ", "sz": 38, "b": True, "c": WHITE}])
steps = [
    ("ระยะสั้น", "ชั่งตัวเลขจริง 3 ตัว แล้วใส่เข้าระบบ", "ได้ต้นทุนและกำไรจริงต่อขวด"),
    ("ระยะกลาง", "เริ่มบันทึกล็อตทุกรอบผลิตจริง", "สะสมประวัติที่สร้างย้อนหลังไม่ได้"),
    ("ระยะยาว", "ย้ายไปเครื่องที่เปิดตลอด", "ทุกคนในสวนเข้าใช้พร้อมกันได้"),
]
for i, (tag, head, sub) in enumerate(steps):
    y = 2.2 + i * 1.45
    text(s, M, y, 1.9, 0.4, [{"t": tag, "sz": 13, "b": True, "c": RED}])
    text(s, M + 2.1, y - 0.06, 9.0, 0.5, [{"t": head, "sz": 21, "b": True, "c": WHITE}])
    text(s, M + 2.1, y + 0.5, 9.0, 0.4, [{"t": sub, "sz": 13, "c": RGBColor(0xA9, 0xC0, 0xAF)}])
card(s, M, 6.35, 11.53, 0.72, fill=GREEN_L)
text(s, M + 0.45, 6.53, 10.6, 0.4, [
    {"t": "สิ่งที่ขอจากวันนี้: ตัวเลขจริง 3 ตัว และคำตอบว่าจะไปต่อไหม",
     "sz": 15, "b": True, "c": WHITE}])
s.notes_slide.notes_text_frame.text = "ปิดด้วยการขออนุญาตไปต่อ ไม่ใช่แค่จบการนำเสนอเฉย ๆ"

prs.save(OUT)
print("SAVED:", OUT)
print("SLIDES:", len(prs.slides.__iter__.__self__._sldIdLst))
