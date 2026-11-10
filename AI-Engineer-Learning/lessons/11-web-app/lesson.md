# บทที่ 11 — Web App: FastAPI + Chat UI แบบ Streaming

⏱ ประมาณ 6 ชั่วโมง

## เป้าหมาย
- [ ] สร้าง backend ด้วย FastAPI ที่ห่อ agent ไว้
- [ ] ส่งคำตอบแบบ streaming ไปยังเบราว์เซอร์ด้วย Server-Sent Events (SSE)
- [ ] ทำปุ่ม "อนุมัติ / ปฏิเสธ" สำหรับเครื่องมืออันตราย
- [ ] จัดการ session ของผู้ใช้แต่ละคน
- [ ] รับ webhook จาก ERPNext

---

## 1. สถาปัตยกรรม

```
┌──────── Browser ────────┐        ┌──────────── FastAPI (Python) ────────────┐       ┌─────────┐
│ index.html              │  HTTP  │ POST /api/chat      → agent loop (stream)│ HTTPS │ Claude  │
│  - ช่องแชท               │ ─────▶ │ POST /api/approve   → ต่อหลังอนุมัติ         │ ────▶ │  API    │
│  - ปุ่มอนุมัติ              │ ◀───── │ POST /hooks/erpnext → รับ webhook          │       └─────────┘
│  - dashboard ตัวเลข       │  SSE   │ GET  /api/dashboard → ตัวเลขจาก ERPNext     │ ────▶ ERPNext
└─────────────────────────┘        └──────────────────────────────────────────┘
```

**กฎสำคัญ:** เบราว์เซอร์ **ห้าม** เรียก Claude API โดยตรง เพราะ API key จะหลุดไปอยู่ฝั่งผู้ใช้
ทุกการเรียกต้องผ่าน backend ของเรา

---

## 2. FastAPI เบื้องต้น

```powershell
pip install fastapi "uvicorn[standard]" python-dotenv
```

```python
# app.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ERPNext AI Assistant")

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.get("/health")
def health():
    return {"ok": True}
```

```powershell
uvicorn app:app --reload --port 8080
```
เปิด http://localhost:8080/docs จะเห็นหน้าเอกสาร API ที่ FastAPI สร้างให้อัตโนมัติ และทดสอบ endpoint จากหน้านั้นได้

---

## 3. Server-Sent Events (SSE)

SSE คือวิธีที่เซิร์ฟเวอร์ส่งข้อมูลทยอยไปยังเบราว์เซอร์ผ่าน HTTP connection เดียว
รูปแบบของข้อมูลเป็นข้อความธรรมดา:

```
data: {"type": "text", "text": "สวัส"}

data: {"type": "text", "text": "ดีครับ"}

data: {"type": "done"}

```
(แต่ละ event คั่นด้วยบรรทัดว่าง)

### ชนิดของ event ในแอปนี้
| type | ความหมาย |
|---|---|
| `text` | ข้อความจากโมเดลทีละส่วน |
| `tool` | agent กำลังเรียกเครื่องมือ (ให้ UI แสดง "กำลังดูสต็อก...") |
| `approval` | ต้องการให้ผู้ใช้อนุมัติ พร้อมรายละเอียด |
| `error` | เกิดข้อผิดพลาด |
| `done` | จบรอบนี้ |

---

## 4. Agent แบบ Streaming ใน Backend

```python
# agent_service.py
import json
import uuid

from common import FALLBACK_BETA, MODEL, client
from erp_tools_registry import HANDLERS, RISK, TOOLS   # จากบทที่ 9-10

SYSTEM = "..."   # system prompt ของผู้ช่วยบริหาร
MAX_TURNS = 15

# session_id -> {"messages": [...], "pending": {...} | None}
SESSIONS: dict[str, dict] = {}


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def describe(name: str, args: dict) -> str:
    """สรุปการกระทำเป็นภาษาคน ให้ผู้ใช้เข้าใจก่อนกดอนุมัติ (บทที่ 6)"""
    if name == "create_quotation_draft":
        items = ", ".join(f'{i["item_code"]} x{i["qty"]}' for i in args.get("items", []))
        return f"สร้างใบเสนอราคา (ร่าง) ให้ {args.get('customer')}: {items}"
    return f"{name}: {json.dumps(args, ensure_ascii=False)}"


def run_tool(block) -> dict:
    try:
        out = HANDLERS[block.name](**block.input)
        return {"type": "tool_result", "tool_use_id": block.id, "content": out}
    except Exception as e:
        return {"type": "tool_result", "tool_use_id": block.id,
                "content": f"{type(e).__name__}: {e}", "is_error": True}


def agent_stream(session_id: str):
    """generator ที่ yield SSE event จนกว่าจะจบ หรือจนกว่าจะต้องรออนุมัติ"""
    state = SESSIONS[session_id]
    messages = state["messages"]

    for _ in range(MAX_TURNS):
        with client.beta.messages.stream(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=TOOLS,
            messages=messages, betas=[FALLBACK_BETA], fallbacks="default",
        ) as stream:
            for text in stream.text_stream:
                yield sse({"type": "text", "text": text})
            response = stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            if response.stop_reason == "refusal":
                yield sse({"type": "error", "text": "ขออภัย ไม่สามารถดำเนินการคำขอนี้ได้"})
            yield sse({"type": "done"})
            return

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        dangerous = [b for b in tool_blocks if RISK.get(b.name, "dangerous") == "dangerous"]

        if dangerous:
            # หยุดรอผู้ใช้: เก็บสถานะไว้ แล้วส่ง event approval
            approval_id = uuid.uuid4().hex
            state["pending"] = {"id": approval_id, "blocks": tool_blocks}
            yield sse({"type": "approval", "approval_id": approval_id,
                       "actions": [describe(b.name, b.input) for b in dangerous]})
            return

        results = []
        for b in tool_blocks:
            yield sse({"type": "tool", "name": b.name})
            results.append(run_tool(b))
        messages.append({"role": "user", "content": results})

    yield sse({"type": "error", "text": "งานยาวเกินกำหนด กรุณาแบ่งคำถามให้เล็กลง"})


def resume_after_approval(session_id: str, approval_id: str, approved: bool):
    state = SESSIONS[session_id]
    pending = state.get("pending")
    if not pending or pending["id"] != approval_id:
        yield sse({"type": "error", "text": "ไม่พบรายการที่รออนุมัติ"})
        return
    state["pending"] = None

    results = []
    for b in pending["blocks"]:
        if RISK.get(b.name, "dangerous") == "dangerous" and not approved:
            results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                            "content": "ผู้ใช้ปฏิเสธรายการนี้ ห้ามลองใหม่ ให้ถามผู้ใช้ว่าต้องการทำอะไรแทน"})
        else:
            yield sse({"type": "tool", "name": b.name})
            results.append(run_tool(b))
    state["messages"].append({"role": "user", "content": results})
    yield from agent_stream(session_id)
```

**ประเด็นสำคัญ:**
- **ทุก `tool_use` ต้องมี `tool_result` ตอบกลับเสมอ** รวมถึงรายการที่ถูกปฏิเสธ ไม่อย่างนั้นการเรียก API ครั้งถัดไปจะ error
- **เครื่องมือปลอดภัยที่มากับรายการอันตรายในรอบเดียวกัน** จะรันหลังได้รับการอนุมัติ พร้อมกับรายการอันตราย
- `SESSIONS` เก็บไว้ในหน่วยความจำ ถ้ารีสตาร์ทเซิร์ฟเวอร์จะหายหมด ใน production ให้เก็บใน Redis หรือ Postgres (หัวข้อที่ 7)

---

## 5. Endpoints

```python
# app.py
import os
import uuid

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import agent_service as svc
from erp_tools import low_stock_items, sales_summary

app = FastAPI(title="ERPNext AI Assistant")
WEBHOOK_TOKEN = os.environ["WEBHOOK_TOKEN"]   # ตั้งใน .env และใส่ค่าเดียวกันใน header ของ Webhook ฝั่ง ERPNext


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ApproveRequest(BaseModel):
    session_id: str
    approval_id: str
    approved: bool


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/api/session")
def new_session():
    sid = uuid.uuid4().hex
    svc.SESSIONS[sid] = {"messages": [], "pending": None}
    return {"session_id": sid}


@app.post("/api/chat")
def chat(req: ChatRequest):
    state = svc.SESSIONS.get(req.session_id or "")
    if state is None:
        raise HTTPException(404, "ไม่พบ session")
    if state["pending"]:
        raise HTTPException(409, "มีรายการรออนุมัติอยู่")
    if len(req.message) > 4000:
        raise HTTPException(400, "ข้อความยาวเกินไป")
    state["messages"].append({"role": "user", "content": req.message})
    return StreamingResponse(svc.agent_stream(req.session_id), media_type="text/event-stream")


@app.post("/api/approve")
def approve(req: ApproveRequest):
    if req.session_id not in svc.SESSIONS:
        raise HTTPException(404, "ไม่พบ session")
    return StreamingResponse(
        svc.resume_after_approval(req.session_id, req.approval_id, req.approved),
        media_type="text/event-stream",
    )


@app.get("/api/dashboard")
def dashboard(start: str, end: str):
    # ตัวเลขใน dashboard ดึงจาก ERPNext ตรงๆ ไม่ผ่าน AI เพราะต้องแม่นยำ 100% และเร็ว
    return {"sales": sales_summary(start, end), "low_stock": low_stock_items(5)[:10]}


@app.post("/hooks/erpnext")
async def erpnext_webhook(request: Request, x_webhook_token: str = Header(default="")):
    if x_webhook_token != WEBHOOK_TOKEN:         # ตรวจว่า ERPNext ส่งมาจริง
        raise HTTPException(401)
    payload = await request.json()
    # เช่น ใส่ลงคิวให้ AI ร่างใบสั่งซื้อ แล้วแจ้งเตือนผู้จัดการ
    return {"received": True}
```

> 💡 **ส่วนไหนควรใช้ AI และส่วนไหนไม่ควรใช้:** dashboard ใช้โค้ดธรรมดาดึงตัวเลขตรงๆ
> AI เหมาะกับงานที่ต้องตีความ สรุป หรือโต้ตอบ **อย่าเอา AI ไปทำสิ่งที่ SQL ทำได้ดีกว่า**

---

## 6. Frontend: HTML + JavaScript (ไม่ใช้ framework)

```html
<!-- static/index.html -->
<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ผู้ช่วยบริหารร้าน</title>
<style>
  body { font-family: "Sarabun", system-ui, sans-serif; max-width: 760px; margin: 0 auto; padding: 16px; }
  #log { display: flex; flex-direction: column; gap: 8px; min-height: 60vh; }
  .msg { padding: 10px 14px; border-radius: 12px; white-space: pre-wrap; line-height: 1.6; }
  .user { align-self: flex-end; background: #dbeafe; }
  .bot { align-self: flex-start; background: #f1f5f9; }
  .tool { font-size: 13px; color: #64748b; }
  .approval { border: 2px solid #f59e0b; background: #fffbeb; }
  form { display: flex; gap: 8px; margin-top: 12px; }
  input { flex: 1; padding: 10px; font-size: 16px; }
</style>
</head>
<body>
<h1>ผู้ช่วยบริหารร้าน</h1>
<div id="log"></div>
<form id="f"><input id="q" placeholder="เช่น สินค้าไหนใกล้หมด" autocomplete="off"><button>ส่ง</button></form>

<script>
let sessionId = null;
const log = document.getElementById("log");

function add(cls, text) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;            // ใช้ textContent ไม่ใช้ innerHTML เพื่อกัน XSS
  log.appendChild(div);
  div.scrollIntoView();
  return div;
}

async function readSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", botDiv = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop();                         // ส่วนที่ยังไม่ครบ เก็บไว้รอบหน้า
    for (const e of events) {
      if (!e.startsWith("data: ")) continue;
      const ev = JSON.parse(e.slice(6));
      if (ev.type === "text") {
        botDiv ??= add("bot", "");
        botDiv.textContent += ev.text;
      } else if (ev.type === "tool") {
        add("tool", "🔧 กำลังใช้ " + ev.name + "...");
        botDiv = null;
      } else if (ev.type === "approval") {
        showApproval(ev);
      } else if (ev.type === "error") {
        add("bot", "⚠️ " + ev.text);
      }
    }
  }
}

function showApproval(ev) {
  const box = add("bot approval", "ต้องการอนุมัติ:\n• " + ev.actions.join("\n• ") + "\n");
  for (const [label, ok] of [["✅ อนุมัติ", true], ["❌ ปฏิเสธ", false]]) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.onclick = async () => {
      box.querySelectorAll("button").forEach(b => b.disabled = true);
      const r = await fetch("/api/approve", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, approval_id: ev.approval_id, approved: ok }),
      });
      await readSSE(r);
    };
    box.appendChild(btn);
  }
}

document.getElementById("f").onsubmit = async (e) => {
  e.preventDefault();
  const q = document.getElementById("q");
  const text = q.value.trim();
  if (!text) return;
  q.value = "";
  add("user", text);
  if (!sessionId) {
    sessionId = (await (await fetch("/api/session", { method: "POST" })).json()).session_id;
  }
  const r = await fetch("/api/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message: text }),
  });
  if (!r.ok) { add("bot", "⚠️ " + (await r.json()).detail); return; }
  await readSSE(r);
};
</script>
</body>
</html>
```

**ความปลอดภัยฝั่ง frontend:**
- ใช้ `textContent` แทน `innerHTML` ถ้าจะแสดงผลเป็น Markdown ต้องผ่าน sanitizer (เช่น DOMPurify) ก่อน
  เพราะคำตอบของ AI อาจมี HTML หรือสคริปต์ที่มาจาก prompt injection
- ระวังรูปภาพใน Markdown ที่ชี้ไป URL ภายนอก (ช่องทางส่งข้อมูลออก ดูบทที่ 6)

---

## 7. ก้าวต่อไปสู่ production

| เรื่อง | ระดับเรียนรู้ (บทนี้) | ระดับ production |
|---|---|---|
| Session | dict ในหน่วยความจำ | Redis หรือ Postgres |
| ผู้ใช้ | ไม่มี login | Login ด้วย ERPNext (OAuth) หรือระบบของบริษัท |
| สิทธิ์ | ทุกคนใช้เครื่องมือชุดเดียวกัน | เครื่องมือตาม role ของผู้ใช้ |
| งานยาว | รันใน request | ใช้คิว (Celery, RQ) และแจ้งผลทีหลัง |
| Frontend | HTML ธรรมดา | React หรือ Next.js (ถ้าทีมใช้) |
| HTTPS | ไม่มี | reverse proxy (Caddy หรือ Nginx) |

**สำหรับ portfolio ระดับบทนี้ก็เพียงพอแล้ว** ถ้าอธิบายตารางนี้ได้ตอนสัมภาษณ์จะเป็นจุดเด่นมาก

### ทางเลือก: สร้างเป็นแอปใน Frappe
อีกทางคือสร้าง **Custom App ใน Frappe** ให้หน้าแชทอยู่ใน ERPNext เลย
ผู้ใช้ไม่ต้องเปิดเว็บแยก และใช้ระบบ login กับ permission ของ ERPNext ได้ทันที
เป็นหัวข้อที่ควรศึกษาต่อเมื่อเรียนจบหลักสูตร

---

## สรุปบทที่ 11
1. Browser → Backend → Claude API (ห้ามให้ API key อยู่ฝั่ง browser)
2. SSE ส่งข้อความทีละส่วนผ่าน HTTP ธรรมดา
3. การอนุมัติทำได้โดยหยุด generator เก็บสถานะ แล้วทำต่อเมื่อผู้ใช้กดปุ่ม
4. ทุก `tool_use` ต้องได้ `tool_result` แม้ถูกปฏิเสธ
5. ตัวเลขใน dashboard ใช้โค้ดธรรมดา ส่วน AI ใช้กับงานที่ต้องตีความ
6. แสดงผลด้วย `textContent` เพื่อกัน XSS

---

## แบบฝึกหัด (โปรเจกต์ Portfolio ชิ้นที่ 3)
1. ประกอบ `app.py`, `agent_service.py` และ `static/index.html` ให้ทำงานได้
2. เพิ่ม dashboard ด้านบนหน้าเว็บ แสดงยอดขายเดือนนี้และสินค้าใกล้หมด 5 รายการ
3. เพิ่มปุ่มคำถามลัด เช่น "สรุปยอดขายสัปดาห์นี้" และ "สินค้าที่ควรสั่ง"
4. ทำ webhook: ตั้งค่า ERPNext ให้ส่ง event เมื่อมี Sales Order ใหม่ แล้วแสดงแจ้งเตือนในหน้าเว็บ
5. ทดสอบบนมือถือ: หน้าจอต้องใช้งานได้ที่ความกว้าง 375px

✅ ไปต่อที่ [บทที่ 12](../12-evals-production/lesson.md)
