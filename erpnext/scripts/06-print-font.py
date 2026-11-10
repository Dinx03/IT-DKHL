# สร้างสไตล์การพิมพ์ที่บังคับใช้ฟอนต์ไทย แก้ปัญหาสระ/วรรณยุกต์หลุดตำแหน่ง
#
# ต้นเหตุ: ฟอนต์ฝรั่งไม่มีอักษรไทย ระบบเลยสลับฟอนต์กลางประโยค
#          ทำให้ "ราคา" กลายเป็น "ร้ำค้ำ"
# ทางแก้ : ใช้ฟอนต์เดียวที่มีครบทั้งไทยและอังกฤษ (Loma)
import frappe

STYLE = "ONA Healthy Thai"
THAI_CSS = """
/* ONA Healthy - บังคับฟอนต์เดียวทั้งเอกสาร ไม่ให้สลับฟอนต์กลางประโยค */
.print-format,
.print-format *,
.print-format table,
.print-format td,
.print-format th,
.print-format h1, .print-format h2, .print-format h3,
.print-format h4, .print-format h5, .print-format h6 {
    font-family: "Loma", "Garuda", "Norasi", sans-serif !important;
}
.print-format { line-height: 1.7; }
"""

try:
    base_css = frappe.db.get_value("Print Style", "Redesign", "css") or ""

    if frappe.db.exists("Print Style", STYLE):
        doc = frappe.get_doc("Print Style", STYLE)
        doc.css = base_css + THAI_CSS
        doc.save()
        print("STYLE_UPDATED:", STYLE)
    else:
        doc = frappe.get_doc({
            "doctype": "Print Style",
            "print_style_name": STYLE,
            "css": base_css + THAI_CSS,
            "disabled": 0,
        }).insert()
        print("STYLE_CREATED:", doc.name)

    frappe.db.set_single_value("Print Settings", "print_style", STYLE)
    frappe.db.set_single_value("Print Settings", "font", "Default")
    frappe.db.commit()
    frappe.clear_cache()

    print("ACTIVE_STYLE:", frappe.db.get_single_value("Print Settings", "print_style"))
    print("RESULT_OK")
except Exception as e:
    frappe.db.rollback()
    import traceback
    traceback.print_exc()
    print("RESULT_FAILED:", type(e).__name__, str(e)[:300])
