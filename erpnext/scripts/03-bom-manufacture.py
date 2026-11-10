# สูตรการผลิตน้ำมะเขือเทศ + บันทึกการผลิตจริงหนึ่งรอบ
# ***** อัตราผลผลิตเป็นค่าสมมติ: มะเขือเทศ 12.5 กก. -> 100 ขวด (1 กก. = 8 ขวด) *****
# ***** ต้องแทนที่ด้วยตัวเลขจริงจากการชั่งของสวน *****
import frappe
from frappe.utils import add_days, nowdate

CO = "ONA Healthy"
SRC = "Stores - ONA"
FG = "Finished Goods - ONA"
FGITEM = "ONATO-JUICE-75"

try:
    # ---------- 1. สูตรการผลิต (BOM) ----------
    existing = frappe.get_all("BOM", filters={"item": FGITEM, "docstatus": 1}, pluck="name")
    if existing:
        bom_name = existing[0]
        print("BOM_SKIP (มีอยู่แล้ว):", bom_name)
    else:
        bom = frappe.get_doc({
            "doctype": "BOM",
            "item": FGITEM,
            "quantity": 100,
            "company": CO,
            "currency": "THB",
            "is_active": 1,
            "is_default": 1,
            "with_operations": 0,
            "rm_cost_as_per": "Valuation Rate",
            "items": [
                {"item_code": "FRESH-TOMATO", "qty": 12.5},
                {"item_code": "RM-BOTTLE-75", "qty": 100},
                {"item_code": "RM-LABEL", "qty": 100},
            ],
        })
        bom.insert()
        bom.submit()
        bom_name = bom.name
        print("BOM_CREATED:", bom_name)

    bom = frappe.get_doc("BOM", bom_name)
    print("BOM_TOTAL_COST:", bom.total_cost, "บาท ต่อ", bom.quantity, "ขวด")
    print("BOM_COST_PER_BOTTLE:", round(bom.total_cost / bom.quantity, 2), "บาท")

    # ---------- 2. บันทึกการผลิต ----------
    REMARK = "ผลิตน้ำมะเขือเทศ Onato รอบที่ 1"
    if frappe.db.exists("Stock Entry", {"remarks": REMARK, "docstatus": 1}):
        print("MFG_SKIP (มีอยู่แล้ว)")
    else:
        tomato_batch = frappe.get_all(
            "Batch", filters={"item": "FRESH-TOMATO"}, pluck="name", order_by="creation desc")[0]

        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Manufacture",
            "company": CO,
            "from_bom": 1,
            "bom_no": bom_name,
            "fg_completed_qty": 100,
            "posting_date": add_days(nowdate(), -1),
            "set_posting_time": 1,
            "remarks": REMARK,
            "items": [
                {"item_code": "FRESH-TOMATO", "qty": 12.5, "s_warehouse": SRC,
                 "use_serial_batch_fields": 1, "batch_no": tomato_batch},
                {"item_code": "RM-BOTTLE-75", "qty": 100, "s_warehouse": SRC,
                 "use_serial_batch_fields": 1},
                {"item_code": "RM-LABEL", "qty": 100, "s_warehouse": SRC,
                 "use_serial_batch_fields": 1},
                {"item_code": FGITEM, "qty": 100, "t_warehouse": FG,
                 "is_finished_item": 1, "use_serial_batch_fields": 1},
            ],
        })
        se.insert()
        se.submit()
        print("MFG_CREATED:", se.name, "| ใช้ล็อตมะเขือเทศ:", tomato_batch)

    frappe.db.commit()

    # ---------- 3. ผลลัพธ์ ----------
    print("--- ล็อตทั้งหมดในระบบ ---")
    for b in frappe.get_all("Batch", fields=["name", "item", "expiry_date"], order_by="creation"):
        print("BATCH:", b.name, "|", b.item, "| หมดอายุ:", b.expiry_date)

    print("--- สต็อกคงเหลือ ---")
    for r in frappe.get_all("Bin", filters={"actual_qty": [">", 0]},
                            fields=["item_code", "warehouse", "actual_qty", "valuation_rate"]):
        print("STOCK:", r.item_code, "|", r.warehouse, "|", r.actual_qty, "@", round(r.valuation_rate, 2))

    print("RESULT_OK")
except Exception as e:
    frappe.db.rollback()
    import traceback
    traceback.print_exc()
    print("RESULT_FAILED:", type(e).__name__, str(e)[:400])
