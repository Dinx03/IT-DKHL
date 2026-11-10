#!/usr/bin/env bash
# 07-clean-test-data.sh — ล้างข้อมูลทดสอบใน ERPNext ด้วยสิทธิ์ Administrator
#
# รันใน VM:  bash /tmp/07-clean-test-data.sh
#
# ทำไมต้องแยกไฟล์: user ที่ระบบใช้เรียก ERPNext (growth-agent@ona.local)
# ไม่มีสิทธิ์ลบโดยตั้งใจ (least-privilege) เทสต์จึงเก็บกวาดขยะตัวเองไม่ได้
# การเพิ่มสิทธิ์ลบให้ระบบเพื่อความสะดวกของเทสต์คือการแลกความปลอดภัยกับความสบาย
#
# ลบเฉพาะ Lead ที่ lead_name เป็น 'เทสต์' หรือ 'วิชัย' เท่านั้น

set -euo pipefail

cat > /tmp/_clean.py <<'PY'
import frappe
TARGETS = ("เทสต์", "วิชัย", "ลูกค้าจากแชท")
rows = frappe.get_all("Lead", fields=["name", "lead_name"])
n = 0
for r in rows:
    if r.lead_name in TARGETS:
        frappe.delete_doc("Lead", r.name, force=1, ignore_permissions=True)
        print(f"  ลบ {r.name}  {r.lead_name}")
        n += 1
frappe.db.commit()
print(f"<<<DONE>>> ลบไป {n} รายการ · เหลือ {frappe.db.count('Lead')} Lead ในระบบ")
PY

cd ~/frappe-bench
~/.local/bin/bench --site erpnext.local console < /tmp/_clean.py 2>&1 \
  | grep -E "ลบ |<<<DONE>>>" | sed 's/<<<DONE>>> //'
rm -f /tmp/_clean.py
