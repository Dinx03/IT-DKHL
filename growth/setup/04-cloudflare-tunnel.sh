#!/usr/bin/env bash
# 04-cloudflare-tunnel.sh — เปิดทางให้ webhook จากภายนอกเข้าถึงระบบ
#
# รันใน VM:  bash /tmp/04-cloudflare-tunnel.sh <ชื่อโดเมนย่อยเต็มๆ>
# ตัวอย่าง:  bash /tmp/04-cloudflare-tunnel.sh hook.onahealthy.com
#
# ⚠ ต่อกับ "ตัวรับ webhook" เท่านั้น ไม่เปิด ERPNext ออกเน็ต
#   แอปเราเรียก ERPNext แบบขาออกทาง localhost — โลกภายนอกไม่ต้องเห็น Frappe admin
#
# มี 2 จุดที่สคริปต์หยุดรอคุณ:
#   1. cloudflared tunnel login — เปิดเบราว์เซอร์ ยืนยันบัญชี Cloudflare ของคุณเอง
#   2. ต้องมีโดเมนที่ตั้ง nameserver ไปที่ Cloudflare แล้ว
#
# ต้องใช้ sudo (ติดตั้งแพ็กเกจ + ตั้ง systemd service)

set -euo pipefail

HOSTNAME_ARG="${1:-}"
TUNNEL_NAME=ona-growth
LOCAL_PORT=9999          # พอร์ตของตัวรับ webhook (เฟส 2 จะเปลี่ยนเป็นพอร์ตจริงของ Chatwoot)

if [ -z "$HOSTNAME_ARG" ]; then
  echo "ต้องระบุโดเมนย่อย เช่น:  bash $0 hook.onahealthy.com"
  exit 1
fi

echo "==> [1/5] ตรวจนาฬิกา (TLS ของ tunnel พังถ้าเวลาเพี้ยน)"
if ! timedatectl show -p NTPSynchronized --value | grep -q yes; then
  echo "    นาฬิกายังไม่ sync — รัน bash /tmp/00-fix-clock.sh ก่อน"
  exit 1
fi
echo "    ปกติ: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

echo ""
echo "==> [2/5] ติดตั้ง cloudflared จาก apt repo ทางการของ Cloudflare"
if command -v cloudflared >/dev/null 2>&1; then
  echo "    มีอยู่แล้ว: $(cloudflared --version)"
else
  sudo mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
    | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
    | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq cloudflared
  echo "    ติดตั้งแล้ว: $(cloudflared --version)"
fi

echo ""
echo "==> [3/5] ล็อกอินบัญชี Cloudflare"
if [ -f "$HOME/.cloudflared/cert.pem" ]; then
  echo "    ล็อกอินไว้แล้ว (เจอ ~/.cloudflared/cert.pem) ข้ามไป"
else
  echo ""
  echo "    ┌──────────────────────────────────────────────────────────┐"
  echo "    │ สคริปต์จะพิมพ์ URL ออกมา                                  │"
  echo "    │ ให้ก๊อปไปเปิดในเบราว์เซอร์บน Windows แล้วเลือกโดเมนของคุณ  │"
  echo "    │ (ขั้นนี้คุณทำเอง — เป็นการยืนยันบัญชีของคุณ)               │"
  echo "    └──────────────────────────────────────────────────────────┘"
  echo ""
  cloudflared tunnel login
fi

echo ""
echo "==> [4/5] สร้าง tunnel และผูก DNS"
if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
  echo "    tunnel '$TUNNEL_NAME' มีอยู่แล้ว"
else
  cloudflared tunnel create "$TUNNEL_NAME"
fi

TUNNEL_ID="$(cloudflared tunnel list --output json 2>/dev/null \
             | python3 -c "import json,sys;print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'))")"
echo "    tunnel id: $TUNNEL_ID"

cloudflared tunnel route dns --overwrite-dns "$TUNNEL_NAME" "$HOSTNAME_ARG"
echo "    ผูก $HOSTNAME_ARG เข้ากับ tunnel แล้ว"

mkdir -p "$HOME/.cloudflared"
cat > "$HOME/.cloudflared/config.yml" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

# เปิดเฉพาะตัวรับ webhook — อย่าเพิ่ม ERPNext (พอร์ต 8000) เข้ามาที่นี่เด็ดขาด
ingress:
  - hostname: $HOSTNAME_ARG
    service: http://localhost:$LOCAL_PORT
  - service: http_status:404
EOF
echo "    เขียน config.yml แล้ว (ชี้ไป localhost:$LOCAL_PORT เท่านั้น)"

echo ""
echo "==> [5/5] ทดสอบเส้นทางจริงด้วย endpoint ชั่วคราว"
python3 -c "
import http.server, socketserver, threading, time
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers()
        self.wfile.write(b'tunnel-ok')
    def log_message(self, *a): pass
srv = socketserver.TCPServer(('127.0.0.1', $LOCAL_PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(90); srv.shutdown()
" &
TEST_PID=$!
sleep 2

cloudflared tunnel run "$TUNNEL_NAME" >/tmp/cf-test.log 2>&1 &
CF_PID=$!
echo "    รอ tunnel เชื่อมต่อ..."
sleep 15

if curl -fsS --max-time 20 "https://$HOSTNAME_ARG" 2>/dev/null | grep -q tunnel-ok; then
  echo "    สำเร็จ — https://$HOSTNAME_ARG ทะลุถึงเครื่องนี้แล้ว"
  RESULT=0
else
  echo "    ยังไม่ทะลุ — ดู log ที่ /tmp/cf-test.log"
  tail -15 /tmp/cf-test.log | sed 's/^/        /'
  RESULT=1
fi

kill $CF_PID $TEST_PID 2>/dev/null || true
wait 2>/dev/null || true

echo ""
if [ "$RESULT" = "0" ]; then
  echo "เรียบร้อย ทางเปิดแล้ว"
  echo ""
  echo "ยังไม่ตั้งเป็น service ถาวร — รอจนกว่าจะมีตัวรับ webhook จริงในเฟส 2"
  echo "ถึงตอนนั้นค่อยแก้ ingress ใน ~/.cloudflared/config.yml ให้ชี้พอร์ตจริง แล้วรัน:"
  echo "    sudo cloudflared service install"
  echo ""
  echo "⚠ อย่าลืม: ปิดเครื่องนี้เมื่อไหร่ ลูกค้าทักมาแล้วข้อความหาย ไม่ใช่แค่มาช้า"
  echo "  ก่อนเปิดใช้กับลูกค้าจริงควรย้ายขึ้น VPS"
else
  exit 1
fi
