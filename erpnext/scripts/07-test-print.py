# ทดสอบพิมพ์เอกสารจริงเป็น PDF แล้วอ่านข้อความกลับมาตรวจภาษาไทย
import frappe
from frappe.utils.pdf import get_pdf

DOC = ("Delivery Note", "MAT-DN-2026-00001")

try:
    html = frappe.get_print(DOC[0], DOC[1])
    pdf = get_pdf(html)
    open("/tmp/dn.pdf", "wb").write(pdf)
    print("PDF_SIZE:", len(pdf))

    import pdfplumber
    with pdfplumber.open("/tmp/dn.pdf") as p:
        txt = "\n".join((pg.extract_text() or "") for pg in p.pages)
        fonts = sorted({c.get("fontname", "") for pg in p.pages for c in pg.chars})

    print("FONTS_USED:", fonts)
    checks = {
        "ชื่อลูกค้าไทย": "ลูกค้าตัวอย่าง" in txt,
        "หน่วยนับไทย": "ขวด" in txt,
        "ไม่มีสระเพี้ยน": "้ำ" not in txt.replace("น้ำ", ""),
    }
    for k, v in checks.items():
        print(f"  {'OK  ' if v else 'FAIL'}  {k}")
    print("--- ตัวอย่างข้อความใน PDF ---")
    for line in [l for l in txt.split("\n") if l.strip()][:12]:
        print("   ", line[:80])
    print("RESULT_OK")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("RESULT_FAILED:", type(e).__name__, str(e)[:300])
