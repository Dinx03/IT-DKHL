"""
run_all.py — รันเทสต์ทั้งหมด

    py -m growth.tests.run_all

3 ชั้น เรียงจากถูกไปแพง หยุดทันทีที่ชั้นไหนพัง:
  1. compile  — จับ syntax error (เคยหลุดมาแล้วเพราะไม่มีชั้นนี้)
  2. contract — validator ของสัญญา agent ดักของผิดจริงไหม
  3. pipeline — ของจริงทั้งสาย แตะฐานข้อมูลและ ERPNext
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                # noqa: BLE001
        pass

STAGES = [
    ("compile ทุกไฟล์", [PY, "-m", "compileall", "-q",
                          str(ROOT / "growth" / "agents"),
                          str(ROOT / "growth" / "runtime"),
                          str(ROOT / "growth" / "tests")]),
    ("สัญญา agent", [PY, str(ROOT / "growth" / "agents" / "test_contracts.py")]),
    ("สายงานจริง", [PY, "-m", "growth.tests.test_pipeline"]),
]


def main() -> int:
    for name, cmd in STAGES:
        print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
        r = subprocess.run(cmd, cwd=ROOT, env={"PYTHONIOENCODING": "utf-8",
                                               "PATH": "", "SYSTEMROOT": "C:\Windows"},
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        print(out.rstrip() or "  (ไม่มีข้อความ = ผ่าน)")
        if r.returncode != 0:
            print(f"\nหยุดที่ชั้น '{name}' — แก้ก่อนแล้วรันใหม่")
            return r.returncode
    print(f"\n{'=' * 60}\nผ่านทุกชั้น\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
