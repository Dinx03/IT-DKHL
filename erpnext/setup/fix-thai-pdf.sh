#!/bin/bash
# ===================================================================
#  แก้ปัญหาภาษาไทยและการพิมพ์ PDF ให้ครบในรอบเดียว
#    1) ติดตั้งฟอนต์ไทย  (ตอนนี้เครื่องไม่มีเลย -> PDF พิมพ์ไทยไม่ออก)
#    2) ติดตั้งไลบรารีที่ WeasyPrint ต้องใช้  (ตอนนี้ใช้งานไม่ได้)
#    3) รีสตาร์ท ERPNext ให้รับการแก้ไฟล์ CSV ทั้ง 5 จุด
#
#  รันแบบ:  ~/fix-thai-pdf.sh      (จะถามรหัสผ่าน frappe)
# ===================================================================
set -e
step() { echo; echo "=============================================="; echo ">>> $1"; echo "=============================================="; }

step "1/4 ติดตั้งฟอนต์ไทย"
sudo apt-get update -qq
sudo apt-get install -y fonts-thai-tlwg fonts-noto-core || \
  sudo apt-get install -y fonts-thai-tlwg || \
  echo "!! ติดตั้งฟอนต์ไม่สำเร็จ"
sudo fc-cache -f >/dev/null 2>&1 || true
echo "ฟอนต์ที่รองรับภาษาไทยตอนนี้: $(fc-list :lang=th 2>/dev/null | wc -l) ตัว"
fc-list :lang=th 2>/dev/null | head -5

step "2/4 ติดตั้งไลบรารีสำหรับสร้าง PDF"
sudo apt-get install -y \
  libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
  libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b \
  shared-mime-info libffi-dev || echo "!! บางแพ็กเกจติดตั้งไม่สำเร็จ - ดูข้อความข้างบน"

step "3/4 ทดสอบว่า WeasyPrint ใช้งานได้แล้ว"
cd ~/frappe-bench
env/bin/python - <<'PYEOF'
try:
    import weasyprint
    print("weasyprint version:", weasyprint.__version__)
    html = ('<html><body style="font-family:Loma,Garuda,sans-serif">'
            '<h1>ทดสอบภาษาไทย ONA Healthy</h1>'
            '<p>น้ำมะเขือเทศ 100% สกัดเย็น ขวดละ 56 บาท</p></body></html>')
    pdf = weasyprint.HTML(string=html).write_pdf()
    open("/tmp/thai-test.pdf", "wb").write(pdf)
    print("PDF_OK size =", len(pdf), "bytes -> /tmp/thai-test.pdf")
except Exception as e:
    print("PDF_FAILED:", type(e).__name__, str(e)[:300])
PYEOF

step "4/4 รีสตาร์ท ERPNext"
sudo systemctl restart erpnext
sleep 25
systemctl is-active erpnext
curl -s -o /dev/null -w "web HTTP %{http_code}\n" http://localhost:8000/

cat <<'DONE'

==============================================
        เสร็จแล้ว
==============================================

ตรวจต่อได้เลย
  1. โหลด CSV จากหน้ารายงาน  -> ภาษาไทยควรอ่านออกแล้ว
  2. เปิดเอกสารสักใบ กด Print -> ภาษาไทยควรขึ้นถูกต้อง

ถ้าขั้นที่ 3 ขึ้น PDF_FAILED ให้ก๊อปข้อความส่งให้ Claude ดู
DONE
