"""mini_agent.py — agent loop ที่เขียนเองจากศูนย์ (บทที่ 4)

รัน:  python mini_agent.py "สรุปว่ามีไฟล์อะไรใน workspace บ้าง แล้วเขียน summary.md"
agent จะอ่านและเขียนไฟล์ได้เฉพาะในโฟลเดอร์ ./workspace เท่านั้น
"""
import json
import sys
import time
from pathlib import Path

from common import create, text_of

WORKSPACE = Path("workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)
MAX_TURNS = 15          # กันวนลูปไม่รู้จบ
LOG_FILE = Path("agent_log.jsonl")

SYSTEM = f"""คุณคือผู้ช่วยจัดการไฟล์ ทำงานใน workspace: {WORKSPACE}
- ใช้เครื่องมือเพื่อดูข้อมูลจริงก่อนตอบ ห้ามเดาเนื้อหาไฟล์
- ทำงานให้เสร็จแล้วสรุปสั้นๆ เป็นภาษาไทยว่าทำอะไรไปบ้าง"""

TOOLS = [
    {
        "name": "list_files",
        "description": "แสดงรายชื่อไฟล์ทั้งหมดใน workspace พร้อมขนาด (ไบต์)",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "read_file",
        "description": "อ่านเนื้อหาไฟล์ข้อความใน workspace คืนค่าไม่เกิน 20,000 ตัวอักษร",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "ชื่อไฟล์ relative กับ workspace"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": "สร้างหรือเขียนทับไฟล์ข้อความใน workspace",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
]


def safe_path(rel: str) -> Path:
    """กัน path traversal เช่น '../../Windows/system32'"""
    p = (WORKSPACE / rel).resolve()
    if not p.is_relative_to(WORKSPACE):
        raise PermissionError(f"ไม่อนุญาตให้เข้าถึงนอก workspace: {rel}")
    return p


def list_files() -> str:
    files = [f"{p.relative_to(WORKSPACE)} ({p.stat().st_size} bytes)"
             for p in WORKSPACE.rglob("*") if p.is_file()]
    return "\n".join(files) or "(workspace ว่าง)"


def read_file(path: str) -> str:
    text = safe_path(path).read_text(encoding="utf-8")
    if len(text) > 20_000:
        return text[:20_000] + f"\n...[ตัดทอน: ไฟล์ยาว {len(text)} ตัวอักษร]"
    return text


def write_file(path: str, content: str) -> str:
    p = safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"เขียน {path} แล้ว ({len(content)} ตัวอักษร)"


HANDLERS = {"list_files": list_files, "read_file": read_file, "write_file": write_file}


def log(event: dict) -> None:
    event["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_tool(block) -> dict:
    try:
        output = HANDLERS[block.name](**block.input)
        return {"type": "tool_result", "tool_use_id": block.id, "content": output}
    except Exception as e:  # ส่ง error กลับให้โมเดล ไม่ให้โปรแกรมพัง
        return {"type": "tool_result", "tool_use_id": block.id,
                "content": f"{type(e).__name__}: {e}", "is_error": True}


def run_agent(goal: str) -> str:
    messages = [{"role": "user", "content": goal}]
    total_in = total_out = 0

    for turn in range(1, MAX_TURNS + 1):
        response = create(max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=messages)
        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        log({"turn": turn, "stop_reason": response.stop_reason,
             "input_tokens": response.usage.input_tokens})

        if response.stop_reason == "end_turn":
            print(f"\n[จบใน {turn} รอบ | tokens in={total_in} out={total_out}]")
            return text_of(response)
        if response.stop_reason == "refusal":
            return "โมเดลปฏิเสธคำขอนี้"
        if response.stop_reason == "max_tokens":
            return "คำตอบยาวเกิน max_tokens"
        if response.stop_reason != "tool_use":
            return f"หยุดด้วยเหตุผลที่ไม่คาดคิด: {response.stop_reason}"

        results = []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"💭 {block.text.strip()}")
            if block.type == "tool_use":
                print(f"🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:80]})")
                result = run_tool(block)
                log({"turn": turn, "tool": block.name, "input": block.input,
                     "is_error": result.get("is_error", False)})
                results.append(result)
        messages.append({"role": "user", "content": results})

    return f"หยุด: ครบ {MAX_TURNS} รอบแล้วแต่งานยังไม่เสร็จ"


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]) or "ดูว่ามีไฟล์อะไรใน workspace แล้วเขียน summary.md สรุปเนื้อหา"
    print(run_agent(goal))
