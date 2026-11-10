#!/bin/bash
# ===================================================================
#  ส่วนเสริมหลังติดตั้ง ERPNext เสร็จ
#    1) ให้ ERPNext รันเองตลอด แม้ปิด SSH หรือรีบูต VM
#    2) สำรองข้อมูลอัตโนมัติทุกวัน เก็บย้อนหลัง 7 วัน
#
#  ต้องใช้ sudo  ->  จะถามรหัสผ่าน frappe ระหว่างทาง
#  รันแบบ:  ssh frappe@127.0.0.1 -p 2222 -t "~/setup-extras.sh"
# ===================================================================
set -e
step() { echo; echo "=============================================="; echo ">>> $1"; echo "=============================================="; }

BENCH="$HOME/frappe-bench"
[ -d "$BENCH" ] || { echo "ไม่พบ $BENCH - ติดตั้ง ERPNext ให้เสร็จก่อน"; exit 1; }

# หา path จริงของ bench และ node แบบไม่พึ่ง PATH ปัจจุบัน
# (systemd ไม่โหลด .bashrc จึงไม่รู้จัก nvm ต้องระบุเต็ม)
BENCH_BIN="$HOME/.local/bin/bench"
NODE_BIN="$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | tail -1)"

[ -x "$BENCH_BIN" ] || { echo "ไม่พบ bench ที่ $BENCH_BIN"; exit 1; }
[ -n "$NODE_BIN" ]  || { echo "ไม่พบ node ใน ~/.nvm"; exit 1; }
echo "bench : $BENCH_BIN"
echo "node  : $NODE_BIN"

# -------------------------------------------------------------------
step "1/2 ตั้งให้ ERPNext รันอัตโนมัติ (systemd)"
# -------------------------------------------------------------------
sudo tee /etc/systemd/system/erpnext.service > /dev/null <<EOF
[Unit]
Description=ERPNext (Frappe bench)
After=network.target mariadb.service redis-server.service
Requires=mariadb.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$BENCH
Environment=PATH=$NODE_BIN:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$BENCH_BIN start
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

# ปิด bench ที่รันค้างอยู่แบบชั่วคราวก่อน ไม่งั้นพอร์ตชนกัน
echo "ปิด bench ที่รันอยู่เดิม (ถ้ามี)..."
pkill -f "honcho start" 2>/dev/null || true
pkill -f "bench start"  2>/dev/null || true
sleep 5

sudo systemctl daemon-reload
sudo systemctl enable erpnext.service
sudo systemctl restart erpnext.service
echo "รอ 30 วินาทีให้ระบบสตาร์ท..."
sleep 30
sudo systemctl is-active erpnext.service || true
echo "--- ทดสอบว่าเว็บตอบจริง ---"
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000 || echo "ยังไม่ตอบ - ดู log ด้วย: sudo journalctl -u erpnext -n 50"

# -------------------------------------------------------------------
step "2/2 ตั้งสำรองข้อมูลอัตโนมัติทุกวัน ตี 2"
# -------------------------------------------------------------------
mkdir -p "$HOME/backups"

cat > "$HOME/backup-erpnext.sh" <<EOF
#!/bin/bash
# สำรองฐานข้อมูล + ไฟล์แนบ แล้วลบตัวที่เก่ากว่า 7 วันทิ้ง
set -e
export PATH="$NODE_BIN:$HOME/.local/bin:\$PATH"
cd "$BENCH"
"$BENCH_BIN" --site erpnext.local backup --with-files
find "$BENCH/sites/erpnext.local/private/backups" -type f -mtime -1 -exec cp {} "$HOME/backups/" \;
find "$HOME/backups" -type f -name '*.gz' -mtime +7 -delete
echo "\$(date '+%Y-%m-%d %H:%M') backup ok" >> "$HOME/backups/backup.log"
EOF
chmod +x "$HOME/backup-erpnext.sh"

if ! crontab -l 2>/dev/null | grep -q backup-erpnext; then
  (crontab -l 2>/dev/null; echo "0 2 * * * $HOME/backup-erpnext.sh >> $HOME/backups/cron.log 2>&1") | crontab -
  echo "ตั้ง cron แล้ว: ทุกวันตี 2"
else
  echo "มี cron อยู่แล้ว ข้าม"
fi

echo "--- ทดสอบสำรองข้อมูลหนึ่งครั้ง ---"
"$HOME/backup-erpnext.sh"
ls -lh "$HOME/backups/" | tail -6

cat <<'DONE'

==============================================
        ตั้งค่าส่วนเสริมเสร็จแล้ว
==============================================

ERPNext ทำงานเองตลอด ไม่ต้องสั่งอะไรอีก
ปิด SSH หรือรีบูต VM ก็ขึ้นเอง

เปิดใช้งาน:  http://localhost:8080   (เบราว์เซอร์บน Windows)

คำสั่งที่ใช้บ่อย
  sudo systemctl status erpnext     ดูว่าทำงานอยู่ไหม
  sudo systemctl restart erpnext    สั่งรีสตาร์ท
  sudo journalctl -u erpnext -f     ดู log สด ๆ  (Ctrl+C ออก)
  ~/backup-erpnext.sh               สำรองข้อมูลทันที
  ls -lh ~/backups/                 ดูไฟล์สำรอง

หมายเหตุ - ไม่ต้องติดตั้ง wkhtmltopdf
ERPNext v16 ใช้ WeasyPrint สร้าง PDF ซึ่งติดตั้งมาพร้อม frappe แล้ว
DONE
