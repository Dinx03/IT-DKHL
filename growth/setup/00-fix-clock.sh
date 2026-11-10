#!/usr/bin/env bash
# 00-fix-clock.sh — แก้นาฬิกา VM ที่เดินช้า
#
# รันใน VM:  bash /tmp/00-fix-clock.sh    (ต้องใส่รหัส sudo)
#
# ทำไมเรื่องนี้สำคัญกว่าแค่ "apt ลงไม่ได้":
#   - OAuth ของ Facebook/LINE และการตรวจลายเซ็น webhook ยอมให้เวลาคลาดเคลื่อน
#     ได้ไม่กี่นาที ช้า 13 ชั่วโมงคือ "เชื่อมต่อไม่ได้เลย" ในเฟส 2
#   - events.occurred_at จะผิดทั้งตาราง ย้อนสายเหตุการณ์ไม่ได้
#   - เทียบวันหมดอายุล็อต (expiry_date > today) จะเพี้ยน
#   - policy_rules.effective_from จะทำงานผิดวัน

set -uo pipefail

echo "==> เวลาก่อนแก้"
timedatectl | sed -n '1,6p'

echo ""
echo "==> วิธีที่ 1: เตะ systemd-timesyncd ให้ sync ใหม่"
sudo timedatectl set-ntp false
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd 2>/dev/null || true

for i in $(seq 1 12); do
  if timedatectl show -p NTPSynchronized --value | grep -q yes; then
    echo "    sync สำเร็จหลังรอ $((i*5)) วินาที"
    break
  fi
  sleep 5
done

if ! timedatectl show -p NTPSynchronized --value | grep -q yes; then
  echo "    NTP ไม่ผ่าน (พอร์ต UDP 123 น่าจะโดนบล็อก) — ใช้วิธีที่ 2"
  echo ""
  echo "==> วิธีที่ 2: ดึงเวลาจาก HTTP header แทน (ใช้พอร์ต 443 ที่รู้ว่าเปิดอยู่)"
  HTTP_DATE="$(curl -sSI --max-time 15 https://www.cloudflare.com 2>/dev/null \
               | grep -i '^date:' | cut -d' ' -f2- | tr -d '\r')"
  if [ -n "$HTTP_DATE" ]; then
    sudo date -s "$HTTP_DATE" >/dev/null
    echo "    ตั้งเวลาจาก HTTP header: $HTTP_DATE"
  else
    echo "    ดึงเวลาจาก HTTP ไม่ได้เหมือนกัน — ต้องตั้งมือ:"
    echo "      sudo date -s 'YYYY-MM-DD HH:MM:SS UTC'"
    exit 1
  fi
fi

echo ""
echo "==> เขียนเวลาลง RTC ของเครื่อง เพื่อให้รีบูตแล้วไม่กลับไปช้าอีก"
sudo hwclock --systohc 2>/dev/null && echo "    เขียน RTC แล้ว" \
  || echo "    เขียน RTC ไม่ได้ (ปกติสำหรับ VM บางแบบ) ข้ามไป"

echo ""
echo "==> เวลาหลังแก้"
timedatectl | sed -n '1,6p'

SKEW_OK=$(timedatectl show -p NTPSynchronized --value)
echo ""
if [ "$SKEW_OK" = "yes" ]; then
  echo "เรียบร้อย นาฬิกา sync แล้ว — รัน 01-install-postgres.sh ต่อได้"
else
  echo "ตั้งเวลาด้วยมือแล้ว แต่ยัง sync อัตโนมัติไม่ได้"
  echo "ถ้ารีบูต VM แล้วเวลาเพี้ยนอีก ให้รันสคริปต์นี้ซ้ำ"
  echo "ทางแก้ถาวรคือติดตั้ง VirtualBox Guest Additions ให้ sync เวลากับเครื่องแม่"
fi
