# สร้างสินค้าจริงของ ONA Healthy + วัตถุดิบสำหรับสูตรการผลิต
import frappe

def group(name, parent="All Item Groups"):
    if not frappe.db.exists("Item Group", name):
        frappe.get_doc({"doctype": "Item Group", "item_group_name": name,
                        "parent_item_group": parent, "is_group": 0}).insert()

def uom(name):
    if not frappe.db.exists("UOM", name):
        frappe.get_doc({"doctype": "UOM", "uom_name": name}).insert()

def item(code, name, grp, stock_uom, rate, desc="", batch=False, shelf=None, is_purchase=False, is_sales=True):
    if frappe.db.exists("Item", code):
        return
    d = {
        "doctype": "Item", "item_code": code, "item_name": name,
        "item_group": grp, "stock_uom": stock_uom, "is_stock_item": 1,
        "description": desc or name,
        "is_purchase_item": 1 if is_purchase else 0,
        "is_sales_item": 1 if is_sales else 0,
    }
    if batch:
        d.update({"has_batch_no": 1, "create_new_batch": 1,
                  "batch_number_series": code + "-.YYYY.-.####"})
        if shelf:
            d.update({"has_expiry_date": 1, "shelf_life_in_days": shelf})
    doc = frappe.get_doc(d).insert()
    if rate:
        doc.db_set("standard_rate", rate)
        if not frappe.db.exists("Item Price", {"item_code": code, "price_list": "Standard Selling"}):
            frappe.get_doc({"doctype": "Item Price", "item_code": code,
                            "price_list": "Standard Selling", "price_list_rate": rate}).insert()

# ---- กลุ่มสินค้า ----
group("สายสุขภาพ")
group("สายผิว")
group("วัตถุดิบและบรรจุภัณฑ์")
uom("ขวด")
uom("ชิ้น")

H, S, R = "สายสุขภาพ", "สายผิว", "วัตถุดิบและบรรจุภัณฑ์"

# ---- สายสุขภาพ (7) ----
item("ONATO-JUICE-75", "Onato Tomato Juice 100% 75ml", H, "ขวด", 56,
     "น้ำมะเขือเทศ 100% สกัดเย็น ไม่เติมน้ำตาล 10 กิโลแคลอรีต่อขวด ผ่าน อย.", True, 365)
item("BLACK-TOMATO-90", "Black Tomato Plus 90g", H, "ชิ้น", 190,
     "มะเขือเทศสกัดเข้มข้น 100% แดงและเหลืองผสมพันธุ์ดำ", True)
item("ONATO-BOXSET-6", "Onato Box Set 6 ขวด", H, "ชิ้น", 320, "ชุด 6 ขวด ดื่มหนึ่งสัปดาห์", True, 365)
item("ONATO-MONTHLY", "Onato Monthly Health Pack", H, "ชิ้น", 1200, "ชุดดื่มหนึ่งเดือน ส่งฟรีทั่วประเทศ", True, 365)
item("ONATO-GIFTSET", "Onato Premium Gift Set", H, "ชิ้น", 590, "ชุดของขวัญเพื่อสุขภาพ", True, 365)
item("TOMATO-TABLET-50", "Tomato Tablets 50g 100 เม็ด", H, "ชิ้น", 350,
     "ไลโคปีนธรรมชาติ แบบเคี้ยว 1 เม็ดเทียบเท่ามะเขือเทศเชอรี่ 20 ลูก", True)
item("FRESH-TOMATO", "มะเขือเทศสด ตามฤดูกาล", H, "Kg", 0,
     "ปลูกในโรงเรือน หลายสายพันธุ์ - สอบถามราคา", True, is_purchase=True)

# ---- สายผิว (8) ----
item("SOAP-TOMATO-HONEY", "Tomato & Honey Mask Soap 75ml", S, "ชิ้น", 56,
     "สบู่ทำมือ 100% บ่ม 2 ปี แถมจานไม้สัก สินค้า OTOP", True, 730)
item("AMANA-CREAM-30", "AMANA Perfect Cream 30g", S, "ชิ้น", 380, "ครีมบำรุงหน้า สารสกัดมะเขือเทศและพืช 7 ชนิด", True)
item("SERUM-BRIGHT-20", "ONA Healthy Bright Serum 20g", S, "ชิ้น", 499, "สำหรับจุดด่างดำและรอยสิว", True)
item("UV-PROTECT-20", "ONA Healthy UV Protection 20g", S, "ชิ้น", 499, "กันแดดสำหรับหน้า ไม่ทิ้งคราบขาว", True)
item("LOTION-200", "ONA Healthy Lotion 200ml", S, "ชิ้น", 250, "โลชั่นบำรุงผิวกาย", True)
item("SUNSCREEN-200", "ONA Healthy Sunscreen 200ml", S, "ชิ้น", 280, "โลชั่นกันแดดผิวกาย UVA/UVB", True)
item("ESSENCE-TOMATO", "Tomato Essence", S, "ชิ้น", 229, "เอสเซนส์เข้มข้น หยดเดียวก่อนทาครีม", True)
item("ESSENCE-CUCUMBER", "Cucumber Essence", S, "ชิ้น", 229, "เอสเซนส์เข้มข้น หยดเดียวก่อนทาครีม", True)

# ---- วัตถุดิบและบรรจุภัณฑ์ (สำหรับสูตรการผลิต) ----
item("RM-BOTTLE-75", "ขวดแก้ว 75 ml พร้อมฝา", R, "ชิ้น", 6, "บรรจุภัณฑ์น้ำมะเขือเทศ",
     False, is_purchase=True, is_sales=False)
item("RM-LABEL", "ฉลาก Onato", R, "ชิ้น", 1.5, "ฉลากติดขวด",
     False, is_purchase=True, is_sales=False)

frappe.db.commit()
print("DONE_ITEMS", frappe.db.count("Item"))
