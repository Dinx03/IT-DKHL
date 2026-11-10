# เปลี่ยนแบรนด์จาก ERPNext เป็น ONA Healthy
import frappe

APP = "ONA Healthy"
LOGO_PATH = "/tmp/ona-logo.svg"

BRAND_HTML = (
    '<span style="display:inline-flex;align-items:center;gap:8px;font-weight:600;">'
    '<svg width="20" height="20" viewBox="0 0 64 64" style="flex:none">'
    '<circle cx="32" cy="37" r="22" fill="#C0392B"/>'
    '<path d="M32 17c-1.5-4-4.5-7-8-8 3 3.5 4.5 6 5 8z" fill="#4B7F3F"/>'
    '<path d="M32 17c1.5-4 4.5-7 8-8-3 3.5-4.5 6-5 8z" fill="#4B7F3F"/>'
    '<ellipse cx="24" cy="29" rx="6.5" ry="4" fill="#fff" opacity=".28" '
    'transform="rotate(-28 24 29)"/></svg>'
    '<span>ONA Healthy</span></span>'
)

try:
    # ---- อัปโหลดโลโก้เข้าระบบไฟล์ของ Frappe ----
    logo_url = None
    existing = frappe.get_all("File", filters={"file_name": "ona-logo.svg"}, pluck="file_url")
    if existing:
        logo_url = existing[0]
        print("LOGO_EXISTS:", logo_url)
    else:
        with open(LOGO_PATH, "rb") as f:
            content = f.read()
        doc = frappe.get_doc({
            "doctype": "File",
            "file_name": "ona-logo.svg",
            "is_private": 0,
            "content": content,
        }).insert(ignore_permissions=True)
        logo_url = doc.file_url
        print("LOGO_UPLOADED:", logo_url)

    # ---- ชื่อแอปที่โผล่ในแท็บเบราว์เซอร์และหัวเว็บ ----
    frappe.db.set_single_value("System Settings", "app_name", APP)
    frappe.db.set_single_value("Website Settings", "app_name", APP)
    frappe.db.set_single_value("Website Settings", "title_prefix", APP)
    frappe.db.set_single_value("Website Settings", "brand_html", BRAND_HTML)
    if logo_url:
        frappe.db.set_single_value("Website Settings", "app_logo", logo_url)
        frappe.db.set_single_value("Website Settings", "favicon", logo_url)
        frappe.db.set_single_value("Website Settings", "splash_image", logo_url)
        frappe.db.set_single_value("Navbar Settings", "app_logo", logo_url)

    frappe.db.commit()
    frappe.clear_cache()

    print("--- ผลลัพธ์ ---")
    for dt, fn in [("System Settings", "app_name"), ("Website Settings", "app_name"),
                   ("Website Settings", "title_prefix"), ("Website Settings", "app_logo"),
                   ("Website Settings", "favicon"), ("Navbar Settings", "app_logo")]:
        print(f"  {dt}.{fn} = {frappe.db.get_single_value(dt, fn)}")

    print("RESULT_OK")
except Exception as e:
    frappe.db.rollback()
    import traceback
    traceback.print_exc()
    print("RESULT_FAILED:", type(e).__name__, str(e)[:400])
