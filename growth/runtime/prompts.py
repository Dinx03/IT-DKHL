"""
prompts.py — โหลด prompt จากไฟล์ที่มีเวอร์ชัน

prompt คือส่วนที่เปลี่ยนพฤติกรรม agent มากที่สุด แต่แก้ง่ายที่สุด
ถ้าไม่บันทึกว่าใช้ prompt เวอร์ชันไหน จะไม่มีทางรู้ว่าทำไมคำตอบเมื่อวานดีกว่าวันนี้
hash จึงถูกส่งไปเก็บใน agent_runs.input_ref ทุกครั้ง
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=32)
def load(key: str, version: int = 1) -> tuple[str, str]:
    """คืน (เนื้อ prompt, hash) — ตัด front-matter ออกให้แล้ว"""
    path = _DIR / f"{key}.v{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"ไม่มี prompt {path.name} ใน {_DIR}")
    raw = path.read_text(encoding="utf-8")
    body = raw.split("---", 2)[2].strip() if raw.startswith("---") else raw
    return body, hashlib.sha256(raw.encode()).hexdigest()[:12]


def ref(key: str, version: int = 1) -> dict[str, str | int]:
    _, h = load(key, version)
    return {"prompt_key": key, "prompt_version": version, "prompt_hash": h}
