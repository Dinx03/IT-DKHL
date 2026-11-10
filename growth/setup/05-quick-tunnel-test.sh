#!/usr/bin/env bash
# 05-quick-tunnel-test.sh — พิสูจน์ว่าเส้นทางจากเน็ตเข้าถึงเครื่องนี้ได้จริง
#
# รันใน VM:  bash /tmp/05-quick-tunnel-test.sh
#
# ต่างจาก 04 ตรงที่ "ไม่ต้องมีโดเมน ไม่ต้องล็อกอิน Cloudflare"
# ใช้ quick tunnel ที่แจก URL สุ่มบน trycloudflare.com
#
# ข้อจำกัดที่ต้องรู้: URL เปลี่ยนทุกครั้งที่รีสตาร์ท
#   → ใช้ทดสอบได้ ใช้กับ webhook จริงระยะยาวไม่ได้
#   → ของจริงต้องมีโดเมน แล้วใช้ 04-cloudflare-tunnel.sh แทน
#
# ไม่ต้องใช้ sudo และไม่แตะ ERPNext

set -uo pipefail

PORT=9999
LOG=/tmp/quick-tunnel.log

cleanup() { kill ${CF_PID:-0} ${SRV_PID:-0} 2>/dev/null; wait 2>/dev/null; }
trap cleanup EXIT

echo "==> [1/4] เปิด endpoint ทดสอบที่ localhost:$PORT"
python3 - <<PY &
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8')
        self.end_headers(); self.wfile.write('tunnel-ok จากเครื่อง ONA'.encode())
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n)
        print('  [webhook เข้ามา]', body[:200].decode('utf-8', 'replace'), flush=True)
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a): pass
socketserver.TCPServer(('127.0.0.1', $PORT), H).serve_forever()
PY
SRV_PID=$!
sleep 2

echo "==> [2/4] เปิด quick tunnel"
rm -f "$LOG"
cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG" 2>&1 &
CF_PID=$!

echo "==> [3/4] รอ URL จาก Cloudflare"
URL=""
for i in $(seq 1 30); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1)"
  [ -n "$URL" ] && break
  sleep 2
done

if [ -z "$URL" ]; then
  echo "    ไม่ได้ URL มา — log 20 บรรทัดท้าย:"
  tail -20 "$LOG" | sed 's/^/        /'
  exit 1
fi
echo "    ได้ URL: $URL"

echo "==> [4/4] ยิงจากภายนอกกลับเข้ามา"
sleep 3
if curl -fsS --max-time 25 "$URL" | grep -q "tunnel-ok"; then
  echo ""
  echo "  ┌─────────────────────────────────────────────────────────┐"
  echo "  │ สำเร็จ — เน็ตข้างนอกเข้าถึงเครื่องนี้ได้แล้ว              │"
  echo "  └─────────────────────────────────────────────────────────┘"
  echo ""
  echo "  URL ตอนนี้: $URL"
  echo "  ลองเปิดในเบราว์เซอร์บน Windows ดูได้ ต้องเห็นข้อความ tunnel-ok"
  echo ""
  echo "  tunnel จะเปิดค้างไว้ 5 นาทีให้ลอง แล้วปิดเอง"
  echo "  ถ้ามี webhook ยิง POST เข้ามาจะพิมพ์ให้ดูตรงนี้"
  echo "  กด Ctrl+C เพื่อหยุดก่อนได้"
  sleep 300
else
  echo "    ยิงไม่ผ่าน — log:"
  tail -20 "$LOG" | sed 's/^/        /'
  exit 1
fi
