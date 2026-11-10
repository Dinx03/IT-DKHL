"""
line_webhook.py — รับข้อความจาก LINE แล้วส่งเข้าสายงานที่มีอยู่

    py -m growth.runtime.line_webhook            เปิดที่พอร์ต 8767
    py -m growth.runtime.line_webhook --tunnel   เปิดพร้อม quick tunnel ให้เลย

    LINE ──POST /webhook/line──> ตรวจลายเซ็น ──> inbox.handle() ──> Reply API ──> LINE

ทำไมตอบ 200 ทันทีแล้วค่อยประมวลผลเบื้องหลัง:
  LINE รอไม่นาน ถ้าตอบช้าจะถือว่า webhook ล้มเหลวและอาจปิด webhook ให้เอง
  งานจริง (เรียกโมเดล + ถาม ERPNext) ใช้เวลาหลายวินาที จึงต้องแยกเธรด

⚠️ ความลับแชนเนลของแชนเนลทดสอบนี้อยู่ในประวัติแชทแล้ว
   แปลว่าใครก็ปลอมลายเซ็นให้ถูกต้องได้ การตรวจลายเซ็นจึงไม่ได้ป้องกันอะไรจริงๆ
   สำหรับแชนเนลทดสอบยอมรับได้ แต่ OA จริงต้องใช้ค่าที่ไม่เคยหลุด
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from pathlib import Path

from .db import _load_env
from .inbox import handle

PORT = 8767
LINE_API = "https://api.line.me/v2/bot"
PATH = "/webhook/line"

# ข้อความตอนส่งต่อคน — ควรให้เจ้าของร้านแก้ถ้อยคำเอง
HANDOFF_TH = ("ขอบคุณที่ทักมานะคะ เรื่องนี้ขอให้เจ้าหน้าที่ตอบเองค่ะ "
              "เดี๋ยวมีคนมาตอบให้เร็วที่สุดค่ะ")
ERROR_TH = "ขออภัยค่ะ ระบบขัดข้องชั่วคราว เดี๋ยวเจ้าหน้าที่จะติดต่อกลับนะคะ"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

LOG_FILE = Path(__file__).resolve().parents[1] / "line.log"


def log(msg: str) -> None:
    """เขียนทั้งหน้าจอและไฟล์ — stdout จากเธรดย่อยหายบ่อยบน Windows
    ถ้าดูสดไม่ได้ ให้เปิดดู growth/line.log แทน"""
    line = f"{datetime.now().strftime('%H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:                                          # noqa: BLE001
        pass


_ENV = _load_env()
SECRET = (_ENV.get("LINE_CHANNEL_SECRET") or "").encode()
TOKEN = _ENV.get("LINE_CHANNEL_ACCESS_TOKEN") or ""
_HEAD = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
_names: dict[str, str] = {}


# ─────────────────────────────────────────────────────────────
# คุยกับ LINE
# ─────────────────────────────────────────────────────────────

def verify(body: bytes, signature: str) -> bool:
    expected = base64.b64encode(hmac.new(SECRET, body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature or "")


def display_name(user_id: str) -> str | None:
    if user_id in _names:
        return _names[user_id]
    try:
        r = requests.get(f"{LINE_API}/profile/{user_id}", headers=_HEAD, timeout=10)
        if r.ok:
            _names[user_id] = r.json().get("displayName") or user_id[:8]
            return _names[user_id]
    except Exception:                                          # noqa: BLE001
        pass
    return None


def reply(reply_token: str, text: str) -> bool:
    """reply token ใช้ได้ครั้งเดียวและหมดอายุเร็ว ถ้าพลาดต้องใช้ push แทน"""
    r = requests.post(f"{LINE_API}/message/reply", headers=_HEAD, timeout=15,
                      data=json.dumps({"replyToken": reply_token,
                                       "messages": [{"type": "text", "text": text[:4900]}]},
                                      ensure_ascii=False).encode())
    if not r.ok:
        log(f"    reply ล้มเหลว HTTP {r.status_code}: {r.text[:200]}")
    return r.ok


def push(user_id: str, text: str) -> bool:
    r = requests.post(f"{LINE_API}/message/push", headers=_HEAD, timeout=15,
                      data=json.dumps({"to": user_id,
                                       "messages": [{"type": "text", "text": text[:4900]}]},
                                      ensure_ascii=False).encode())
    if not r.ok:
        log(f"    push ล้มเหลว HTTP {r.status_code}: {r.text[:200]}")
    return r.ok


def send(reply_token: str | None, user_id: str, text: str) -> None:
    if reply_token and reply(reply_token, text):
        return
    push(user_id, text)          # reply token หมดอายุแล้ว ส่งแบบ push แทน


# ─────────────────────────────────────────────────────────────
# ประมวลผลข้อความ
# ─────────────────────────────────────────────────────────────

def process(ev: dict) -> None:
    src = ev.get("source") or {}
    user_id = src.get("userId")
    if not user_id:
        return
    text = ((ev.get("message") or {}).get("text") or "").strip()
    token = ev.get("replyToken")
    name = display_name(user_id)
    log(f"[{name or user_id[:8]}] {text}")

    try:
        r = handle(text, "line", user_id, name)
    except Exception as exc:                                   # noqa: BLE001
        log(f"    สายงานพัง: {type(exc).__name__}: {exc}")
        send(token, user_id, ERROR_TH)
        return

    out = r.get("reply") or (HANDOFF_TH if r.get("outcome") in ("escalate", "error")
                             else None)
    tag = f"{r['layer']}/{r['outcome']}"
    if r.get("score") is not None:
        tag += f" คะแนน {r['score']}"
    log(f"    → {tag} · {r['cost']}")
    if r.get("outcome") == "escalate":
        log(f"    → เข้าคิวรอคนตอบ: {r.get('escalate')}")

    if out:
        log(f"    ส่งกลับ: {out.splitlines()[0][:70]}")
        send(token, user_id, out)
    elif r.get("outcome") != "ignore":
        send(token, user_id, HANDOFF_TH)


def dispatch(payload: dict) -> None:
    for ev in payload.get("events", []):
        t = ev.get("type")
        if t == "message" and (ev.get("message") or {}).get("type") == "text":
            process(ev)
        elif t == "follow":
            uid = (ev.get("source") or {}).get("userId")
            log(f"[เพิ่มเพื่อนใหม่] {display_name(uid) or uid}")
        elif t == "unfollow":
            log("[บล็อก/ลบเพื่อน]")
        else:
            log(f"[ข้าม event ชนิด {t}]")


# ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes = b"") -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._send(200, "ตัวรับ webhook ของ LINE ทำงานอยู่".encode())

    def do_POST(self) -> None:
        if self.path.rstrip("/") not in (PATH, ""):
            self._send(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))

        if not verify(body, self.headers.get("X-Line-Signature", "")):
            log("ลายเซ็นไม่ถูกต้อง — ปฏิเสธ")
            self._send(403)
            return

        # ตอบ LINE ทันที แล้วค่อยทำงานจริงเบื้องหลัง
        self._send(200, b"ok")
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:                                      # noqa: BLE001
            log("อ่าน payload ไม่ได้")
            return
        threading.Thread(target=dispatch, args=(payload,), daemon=True).start()

    def log_message(self, *a) -> None:
        pass


def start_tunnel() -> str | None:
    """quick tunnel — URL เปลี่ยนทุกครั้งที่รีสตาร์ท ใช้ทดสอบเท่านั้น

    cloudflared รันใน VM แต่เซิร์ฟเวอร์อยู่บน Windows
    10.0.2.2 คือ gateway ของ VirtualBox NAT = เครื่อง Windows เมื่อมองจาก VM"""
    print("  เปิด quick tunnel...")
    p = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-p", "2222", "frappe@127.0.0.1",
         f"cloudflared tunnel --url http://10.0.2.2:{PORT} --no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
    for _ in range(60):
        line = p.stdout.readline()
        if not line:
            break
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            return m.group(0)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tunnel", action="store_true", help="เปิด quick tunnel ให้ด้วย")
    a = ap.parse_args()

    if not SECRET or not TOKEN:
        print("ยังไม่ได้ตั้ง LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN ใน growth/.env")
        raise SystemExit(1)

    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"ตัวรับ webhook เปิดที่ http://127.0.0.1:{PORT}{PATH}")

    if a.tunnel:
        url = start_tunnel()
        if url:
            print(f"\n  เอา URL นี้ไปวางในช่อง Webhook URL ของ LINE:\n"
                  f"    {url}{PATH}\n")
        else:
            print("  เปิด tunnel ไม่สำเร็จ")

    print("รอข้อความ... (Ctrl+C เพื่อหยุด)\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nหยุดแล้ว")


if __name__ == "__main__":
    main()
