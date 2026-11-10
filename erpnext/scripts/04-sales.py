# ขายสินค้า -> ตัดสต็อกอัตโนมัติ -> สาวกลับถึงล็อตและรอบเก็บเกี่ยว
# ***** ลูกค้าเป็นข้อมูลตัวอย่าง ไม่ใช่ลูกค้าจริงของสวน *****
import frappe
from frappe.utils import add_days, nowdate

CO = "ONA Healthy"
FG = "Finished Goods - ONA"
ITEM = "ONATO-JUICE-75"
CUST = "ลูกค้าตัวอย่าง - ร้านค้าปลีก"
QTY = 24

try:
    # ---------- ลูกค้า ----------
    grp = frappe.get_all("Customer Group", filters={"is_group": 0}, pluck="name")[0]
    terr = frappe.get_all("Territory", filters={"is_group": 0}, pluck="name")[0]
    print("USING_GROUP:", grp, "| TERRITORY:", terr)
    if not frappe.db.exists("Customer", CUST):
        frappe.get_doc({
            "doctype": "Customer", "customer_name": CUST,
            "customer_group": grp, "territory": terr,
        }).insert()
        print("CUSTOMER_CREATED:", CUST)
    else:
        print("CUSTOMER_SKIP:", CUST)

    # ---------- ใบสั่งขาย ----------
    so_exist = frappe.get_all("Sales Order", filters={"customer": CUST, "docstatus": 1}, pluck="name")
    if so_exist:
        so_name = so_exist[0]
        print("SO_SKIP:", so_name)
    else:
        so = frappe.get_doc({
            "doctype": "Sales Order", "customer": CUST, "company": CO,
            "currency": "THB", "conversion_rate": 1,
            "selling_price_list": "Standard Selling",
            "price_list_currency": "THB", "plc_conversion_rate": 1,
            "transaction_date": nowdate(),
            "delivery_date": add_days(nowdate(), 2),
            "items": [{"item_code": ITEM, "qty": QTY, "rate": 56,
                       "delivery_date": add_days(nowdate(), 2), "warehouse": FG}],
        })
        so.insert()
        so.submit()
        so_name = so.name
        print("SO_CREATED:", so_name, "| ยอด", so.grand_total, "บาท")

    # ---------- ใบส่งของ ----------
    dn_exist = frappe.get_all("Delivery Note", filters={"customer": CUST, "docstatus": 1}, pluck="name")
    if dn_exist:
        dn_name = dn_exist[0]
        print("DN_SKIP:", dn_name)
    else:
        juice_batch = frappe.get_all("Batch", filters={"item": ITEM},
                                     pluck="name", order_by="creation desc")[0]
        from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
        dn = make_delivery_note(so_name)
        for row in dn.items:
            row.warehouse = FG
            row.use_serial_batch_fields = 1
            row.batch_no = juice_batch
        dn.insert()
        dn.submit()
        dn_name = dn.name
        print("DN_CREATED:", dn_name, "| ส่งจากล็อต:", juice_batch)

    frappe.db.commit()

    # ---------- การสาวกลับ ----------
    print("=== เส้นทางย้อนกลับของขวดที่ขายไป ===")
    dn = frappe.get_doc("Delivery Note", dn_name)
    for row in dn.items:
        print("  ขาย:", row.item_code, row.qty, "ขวด @", row.rate, "บาท | ล็อต:", row.batch_no)
        mfg = frappe.get_all("Stock Entry Detail",
                             filters={"item_code": row.item_code, "docstatus": 1, "is_finished_item": 1},
                             fields=["parent"], limit=1)
        if mfg:
            se = frappe.get_doc("Stock Entry", mfg[0].parent)
            print("  <- ผลิตจาก:", se.name, "วันที่", se.posting_date)
            for c in se.items:
                if c.s_warehouse:
                    print("     <- ใช้:", c.item_code, c.qty, c.uom, "| ล็อต:", c.batch_no or "-")

    print("--- สต็อกคงเหลือหลังขาย ---")
    for r in frappe.get_all("Bin", filters={"actual_qty": [">", 0]},
                            fields=["item_code", "warehouse", "actual_qty", "valuation_rate"]):
        print("STOCK:", r.item_code, "|", r.actual_qty, "@", round(r.valuation_rate, 2))

    print("RESULT_OK")
except Exception as e:
    frappe.db.rollback()
    import traceback
    traceback.print_exc()
    print("RESULT_FAILED:", type(e).__name__, str(e)[:400])
