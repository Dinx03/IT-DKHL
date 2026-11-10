# ตรวจสุขภาพระบบก่อนนำเสนอ
import frappe
from frappe.utils.scheduler import is_scheduler_disabled

print("=== ข้อมูลในระบบ ===")
for d in ["Item", "Batch", "BOM", "Stock Entry", "Sales Order",
          "Delivery Note", "Customer", "Warehouse", "Company"]:
    print(f"  {d}: {frappe.db.count(d)}")

print("=== ตั้งค่าสำคัญ ===")
print("  scheduler ปิดอยู่ไหม:", is_scheduler_disabled())
print("  print_style:", frappe.db.get_single_value("Print Settings", "print_style"))
print("  app_name:", frappe.db.get_single_value("System Settings", "app_name"))
print("  host_name:", frappe.conf.get("host_name"))
print("  batch tracking:", frappe.db.get_single_value("Stock Settings", "enable_serial_and_batch_no_for_item"))

print("=== Error Log ===")
n = frappe.db.count("Error Log")
print("  จำนวน:", n)
for e in frappe.get_all("Error Log", fields=["creation", "method", "error"],
                        order_by="creation desc", limit=5):
    first = (e.error or "").strip().split("\n")[-1][:90]
    print(f"  {str(e.creation)[:19]} | {(e.method or '')[:45]} | {first}")

print("=== สต็อกคงเหลือ ===")
for r in frappe.get_all("Bin", filters={"actual_qty": [">", 0]},
                        fields=["item_code", "warehouse", "actual_qty"]):
    print(f"  {r.item_code} | {r.warehouse} | {r.actual_qty}")
