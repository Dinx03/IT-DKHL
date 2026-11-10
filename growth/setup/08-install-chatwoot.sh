#!/usr/bin/env bash
# 08-install-chatwoot.sh — ติดตั้ง Chatwoot ใน VM เดียวกับ ERPNext
#
# รันใน VM:  bash /tmp/08-install-chatwoot.sh
#
# ⚠️ สคริปต์นี้ยังไม่เคยรันจริง — ผมเขียนไว้ให้แต่ทดสอบไม่ได้
#    เพราะต้องใช้รหัส sudo และใช้เวลาติดตั้งนาน (20-40 นาที)
#    ถ้ามันพังตรงไหน ให้ส่ง error มา แล้วผมแก้ให้
#
# Chatwoot คือกล่องข้อความรวมทุกช่องทาง (LINE/FB/IG) — เป็นส่วนที่เราไม่เขียนเอง
# เพราะการต่อ OAuth และ webhook ของแต่ละแพลตฟอร์มคืองานหลายเดือน
# ระบบเราจะรับ webhook จาก Chatwoot แล้วตอบกลับผ่าน API ของมัน

set -euo pipefail

echo "════════════════════════════════════════════════════════"
echo " ติดตั้ง Chatwoot"
echo "════════════════════════════════════════════════════════"

# ── ตรวจก่อนเริ่ม ─────────────────────────────────────────────
echo ""
echo "==> [1/4] ตรวจความพร้อม"

FREE_MB=$(free -m | awk '/^Mem:/{print $7}')
echo "    RAM ว่าง: ${FREE_MB} MB"
if [ "$FREE_MB" -lt 2500 ]; then
  echo "    ไม่พอ — Chatwoot ต้องการอย่างน้อย 2.5 GB"
  echo "    ปิด VM แล้วเพิ่ม RAM ก่อน (ตอนนี้ตั้งไว้ 8 GB น่าจะพอ)"
  exit 1
fi

FREE_GB=$(df -BG / | awk 'NR==2{gsub("G","",$4); print $4}')
echo "    ดิสก์ว่าง: ${FREE_GB} GB"
[ "$FREE_GB" -lt 10 ] && { echo "    ต้องการอย่างน้อย 10 GB"; exit 1; }

if ! timedatectl show -p NTPSynchronized --value | grep -q yes; then
  echo "    นาฬิกายังไม่ sync — รัน bash /tmp/00-fix-clock.sh ก่อน"
  echo "    (OAuth ของ LINE/Meta จะพังถ้าเวลาเพี้ยน)"
  exit 1
fi
echo "    นาฬิกาปกติ"

if systemctl is-active --quiet postgresql; then
  echo "    เจอ PostgreSQL ที่เราติดตั้งไว้ — Chatwoot จะสร้าง database ของตัวเองแยก"
fi

# ── ติดตั้ง ───────────────────────────────────────────────────
echo ""
echo "==> [2/4] ดาวน์โหลดตัวติดตั้งทางการของ Chatwoot"
echo "    แหล่ง: https://get.chatwoot.app/linux/install.sh"
echo "    (สคริปต์ทางการจาก chatwoot/chatwoot บน GitHub — เปิดอ่านก่อนได้)"
echo ""
read -r -p "    ดาวน์โหลดและรันเลยไหม [y/N] " ans
[ "$ans" = "y" ] || { echo "    ยกเลิก"; exit 0; }

curl -fsSL https://get.chatwoot.app/linux/install.sh -o /tmp/chatwoot-install.sh
echo "    ดาวน์โหลดแล้ว ขนาด $(wc -c < /tmp/chatwoot-install.sh) bytes"
echo "    อ่านก่อนรันได้ที่ /tmp/chatwoot-install.sh"
echo ""
read -r -p "    รันตัวติดตั้ง [y/N] " ans
[ "$ans" = "y" ] || { echo "    ยกเลิก — ไฟล์อยู่ที่ /tmp/chatwoot-install.sh"; exit 0; }

chmod +x /tmp/chatwoot-install.sh
sudo bash /tmp/chatwoot-install.sh --install

# ── หลังติดตั้ง ───────────────────────────────────────────────
echo ""
echo "==> [3/4] ตรวจว่าขึ้นแล้ว"
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null --max-time 5 http://localhost:3000; then
    echo "    Chatwoot ตอบที่ localhost:3000 แล้ว"
    break
  fi
  sleep 10
done

echo ""
echo "==> [4/4] ขั้นตอนที่เหลือ (ต้องทำในหน้าเว็บ)"
cat <<'NEXT'

    1. เปิด http://localhost:3000 สร้างบัญชีผู้ดูแลคนแรก

    2. เพิ่ม port forward ให้เข้าจาก Windows ได้:
       (รันบน Windows)
       VBoxManage controlvm erpnext natpf1 "chatwoot,tcp,127.0.0.1,3000,,3000"

    3. ต่อ LINE: Settings → Inboxes → Add Inbox → LINE
       ต้องมี Channel ID + Channel Secret + Channel Access Token
       จาก https://developers.line.biz

    4. ตั้ง webhook ให้ยิงเข้าระบบเรา:
       Settings → Integrations → Webhooks → Add
       URL: https://<โดเมนของคุณ>/webhook/chatwoot
       Events: message_created

    5. เปิด tunnel ชี้มาที่ตัวรับ webhook ของเรา:
       แก้ ingress ใน ~/.cloudflared/config.yml ให้ชี้พอร์ตของตัวรับ
       แล้ว sudo cloudflared service install

    ⚠️ ตัวรับ webhook ฝั่งเรายังไม่ได้เขียน — เขียนได้หลังจากรู้รูปร่าง
       payload จริงของ Chatwoot แล้ว (เดาไว้ก่อนแล้วต้องรื้อ)

NEXT
echo "เสร็จ"
