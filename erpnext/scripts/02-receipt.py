# รับวัตถุดิบเข้าคลัง - ระบบจะสร้างเลขล็อตให้อัตโนมัติ
# ***** ต้นทุนทั้งหมดเป็นค่าสมมติ ต้องแทนที่ด้วยตัวเลขจริงของสวน *****
# รันด้วย:  echo "exec(open('/tmp/02.py').read())" | bench --site erpnext.local console
import frappe
from frappe.utils import add_days, nowdate

CO = "ONA Healthy"
WH = "Stores - ONA"


def receipt(lines, days_ago, remark):
    if frappe.db.exists("Stock Entry", {"remarks": remark, "docstatus": 1}):
        print("SKIP (มีอยู่แล้ว):", remark)
        return None
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": CO,
        "posting_date": add_days(nowdate(), -days_ago),
        "set_posting_time": 1,
        "remarks": remark,
        "items": [
            {"item_code": c, "qty": q, "t_warehouse": WH,
             "basic_rate": r, "use_serial_batch_fields": 1}
            for c, q, r in lines
        ],
    })
    se.insert()
    se.submit()
    return se


try:
    se1 = receipt([("FRESH-TOMATO", 12.5, 40)], 3, "เก็บเกี่ยวจากโรงเรือน รอบที่ 1")
    print("RECEIPT_TOMATO:", se1.name if se1 else "-")

    se2 = receipt([("RM-BOTTLE-75", 100, 6), ("RM-LABEL", 100, 1.5)], 3, "ซื้อบรรจุภัณฑ์")
    print("RECEIPT_PACKAGING:", se2.name if se2 else "-")

    frappe.db.commit()

    print("--- ล็อตที่ระบบสร้างให้ ---")
    for b in frappe.get_all("Batch", fields=["name", "item", "expiry_date"]):
        print("BATCH:", b.name, "|", b.item, "| หมดอายุ:", b.expiry_date)

    print("--- สต็อกในคลัง", WH, "---")
    for r in frappe.get_all("Bin", filters={"warehouse": WH},
                            fields=["item_code", "actual_qty", "valuation_rate"]):
        print("STOCK:", r.item_code, "=", r.actual_qty, "@", r.valuation_rate)

    print("RESULT_OK")
except Exception as e:
    frappe.db.rollback()
    import traceback
    traceback.print_exc()
    print("RESULT_FAILED:", type(e).__name__, str(e)[:400])
