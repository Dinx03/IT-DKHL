#!/bin/bash
# ===================================================================
#  ติดตั้ง ERPNext v16 ต่อจากจุดที่ค้างไว้
#  รันในฐานะผู้ใช้ frappe   ไม่ต้องใช้ sudo เลยสักคำสั่ง
# ===================================================================
set -e
trap 'echo; echo "!!!!!!  หยุดที่ขั้น: $CURRENT  !!!!!!"; echo "ก๊อปข้อความข้างบนนี้ส่งให้ Claude ดูได้เลย"; echo' ERR

step() { CURRENT="$1"; echo; echo "=============================================="; echo ">>> $1"; echo "=============================================="; }

cd ~/frappe-bench

step "1/9 ตรวจเครื่องมือ build"
which gcc
ls /usr/bin/mysql_config
echo "OK"

step "2/9 ติดตั้ง frappe (คอมไพล์ mysqlclient) - จุดที่พังรอบก่อน"
uv pip install -e apps/frappe --python env/bin/python

step "3/9 ทดสอบว่า import frappe ได้จริง"
env/bin/python -c "import frappe; print('frappe OK')"

step "4/9 ติดตั้ง dependency ที่เหลือ"
bench setup requirements

step "5/9 สร้างเว็บไซต์ erpnext.local"
if [ -d "sites/erpnext.local" ]; then
  echo "มีอยู่แล้ว ข้าม"
else
  echo "*** จะถาม 2 รหัส ***"
  echo "  1) MySQL root password       = รหัส root ของฐานข้อมูล"
  echo "  2) Set Administrator password = รหัสล็อกอิน ERPNext (จดไว้)"
  echo
  bench new-site erpnext.local
fi

step "6/9 ดาวน์โหลดโค้ด ERPNext v16 (ราว 5 นาที)"
if [ -d "apps/erpnext" ]; then
  echo "มีอยู่แล้ว ข้าม"
else
  bench get-app --branch version-16 erpnext
fi

step "7/9 ติดตั้ง ERPNext ลงเว็บไซต์ (10-20 นาที ดูเหมือนค้างแต่กำลังทำงาน)"
if bench --site erpnext.local list-apps 2>/dev/null | grep -q erpnext; then
  echo "ติดตั้งแล้ว ข้าม"
else
  bench --site erpnext.local install-app erpnext
fi

step "8/9 ตั้งค่าปิดท้าย"
bench use erpnext.local
bench --site erpnext.local enable-scheduler
bench --site erpnext.local set-maintenance-mode off

step "9/9 ตรวจผลลัพธ์"
echo "--- แอปที่ติดตั้ง ---"
bench --site erpnext.local list-apps
echo "--- เวอร์ชัน ---"
bench version

cat <<'DONE'

==============================================
        ติดตั้งสำเร็จเรียบร้อย
==============================================

ขั้นต่อไป เลือกอย่างใดอย่างหนึ่ง

[A] ลองเปิดดูเลย (ปิด SSH แล้วเซิร์ฟเวอร์จะดับ)
      cd ~/frappe-bench && bench start

[B] ตั้งให้รันอัตโนมัติตลอด แม้ปิด SSH หรือรีบูต VM  <-- แนะนำ
      ~/setup-extras.sh

แล้วเปิดเบราว์เซอร์บน Windows ไปที่
      http://localhost:8080
ล็อกอิน  Administrator  + รหัสที่ตั้งไว้ในขั้นที่ 5

DONE
