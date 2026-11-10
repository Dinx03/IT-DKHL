"""
check.py — ตรวจข้อความหนึ่งชิ้นด้วย Reach Guard แล้วบันทึกลงฐานข้อมูล

    py -m growth.runtime.check "ข้อความที่จะโพสต์" --platform instagram
    py -m growth.runtime.check --file post.txt --platform facebook --persist

--persist  สร้าง content_item + content_variant + policy_evaluations จริง
           (ไม่ใส่ = ตรวจอย่างเดียว แต่ยังบันทึก event เสมอ)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from ..agents.agents import GuardInput, WriterOutput
from ..agents.common import AgentContext
from ..agents.reach_guard import run as guard_run
from . import db, llm, orchestrator, prompts

# console ของ Windows เป็น cp874 พิมพ์สัญลักษณ์นอก codepage แล้วพัง
# ต้องบังคับ UTF-8 ก่อนพิมพ์อะไรทั้งนั้น (เจอตอนรันจริงครั้งแรก)
for _s in (sys.stdout, sys.stderr):
    try:
        if (_s.encoding or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

_TTY = sys.stdout.isatty()
RESET, BOLD, DIM = ("\033[0m", "\033[1m", "\033[2m") if _TTY else ("", "", "")
RED, YELLOW, GREEN, CYAN = (
    ("\033[31m", "\033[33m", "\033[32m", "\033[36m") if _TTY else ("", "", "", ""))
_SEV = {"block": (RED, "ห้ามโพสต์"), "warn": (YELLOW, "ควรแก้"), "info": (CYAN, "หมายเหตุ")}


def _render(out, body: str, platform: str, rules_n: int) -> None:
    colour = {"pass": GREEN, "rewrite": YELLOW, "block": RED}[out.verdict]
    label = {"pass": "ผ่าน", "rewrite": "ต้องเขียนใหม่", "block": "ห้ามเผยแพร่"}[out.verdict]

    print(f"\n{BOLD}{colour}● {label}{RESET}  "
          f"ความเสี่ยง {BOLD}{out.risk_score}{RESET}/100   "
          f"{DIM}{platform} · ตรวจ {rules_n} กฎ · ruleset {out.ruleset_hash}{RESET}\n")

    if not out.findings:
        print(f"  {DIM}ไม่พบอะไรจากชั้นกฎตายตัว{RESET}")

    for i, f in enumerate(out.findings, 1):
        c, sev = _SEV[f.severity]
        print(f"  {c}{BOLD}{i}. {sev}{RESET}  {DIM}{f.rule_id}{RESET}")
        print(f"     {f.message_th}")
        if f.excerpt:
            print(f"     {DIM}เจอ:{RESET} {c}{f.excerpt}{RESET}")
        if f.fix_hint_th:
            print(f"     {DIM}แก้:{RESET} {f.fix_hint_th}")
        if f.source_url:
            print(f"     {DIM}อ้างอิง: {f.source_url}{RESET}")
        print()

    if out.verdict != "pass":
        nxt = ("ส่งกลับให้ Writer เขียนใหม่ได้"
               if out.fixable_by_rewrite
               else "เขียนใหม่ไม่ช่วย — ต้องแก้สื่อหรือตารางเวลา ส่งให้คนตัดสิน")
        print(f"  {DIM}ขั้นต่อไป: {nxt}{RESET}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ตรวจข้อความด้วย Reach Guard")
    p.add_argument("text", nargs="?", help="ข้อความที่จะตรวจ")
    p.add_argument("--file", type=Path, help="อ่านข้อความจากไฟล์แทน")
    p.add_argument("--platform", default="instagram",
                   choices=["facebook", "instagram", "tiktok", "line_oa", "x", "linkedin"])
    p.add_argument("--brand", default="ona-healthy")
    p.add_argument("--persist", action="store_true",
                   help="สร้าง content_variant + policy_evaluations จริง")
    p.add_argument("--json", action="store_true", help="พิมพ์ผลเป็น JSON")
    a = p.parse_args(argv)

    body = a.file.read_text(encoding="utf-8") if a.file else a.text
    if not body:
        p.error("ต้องมีข้อความ (ใส่เป็น argument หรือ --file)")

    with db.connect() as conn:
        org_id, brand_id = db.resolve_brand(conn, a.brand)
        dna = db.load_dna(conn, brand_id, "reach_guard")
        rules = db.load_rules(conn, a.platform)
        same_day = db.count_scheduled_same_day(conn, brand_id, a.platform, date.today())

        inp = GuardInput(
            ctx=AgentContext(org_id=org_id, brand_id=brand_id, agent="reach_guard",
                             now=datetime.now(timezone.utc)),
            dna=dna,
            platform=a.platform,
            draft=WriterOutput(body=body),
            rules=rules,
            ruleset_hash=db.ruleset_hash(rules),
            recent_posts=db.load_recent_posts(conn, brand_id, a.platform),
            scheduled_same_day=same_day,
        )

        result = guard_run(inp, provider=llm.get_provider(),
                           prompts_load=prompts.load)
        if not result.ok:
            print(f"{RED}Guard พัง:{RESET} {result.error.message}", file=sys.stderr)
            return 2

        out = result.output
        variant_id: UUID | None = None

        if a.persist:
            with conn.transaction():
                item = conn.execute(
                    """insert into content_items (brand_id, dna_version, topic, status, created_by)
                       values (%s, %s, %s, 'review', 'cli:check') returning id""",
                    (brand_id, dna.version_id, body[:60]),
                ).fetchone()
                var = conn.execute(
                    """insert into content_variants (content_id, platform, body, status)
                       values (%s, %s, %s, %s) returning id""",
                    (item["id"], a.platform, body,
                     "blocked" if out.verdict == "block" else "guarded"),
                ).fetchone()
                variant_id = var["id"]
                conn.execute(
                    """insert into policy_evaluations
                         (variant_id, attempt, ruleset_hash, verdict, risk_score,
                          findings, body_before, evaluated_by)
                       values (%s, 1, %s, %s, %s, %s, %s, 'agent:reach_guard')""",
                    (variant_id, out.ruleset_hash, out.verdict, out.risk_score,
                     json.dumps([f.model_dump(mode="json") for f in out.findings]), body),
                )

        corr = orchestrator.new_correlation()
        orchestrator.commit(conn, result, org_id=org_id, brand_id=brand_id,
                            correlation_id=corr, agent="reach_guard",
                            subject_id=str(variant_id) if variant_id else None)

    if a.json:
        print(json.dumps(out.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        _render(out, body, a.platform, len(rules))
        print(f"\n  {DIM}correlation_id: {corr}{RESET}")
        if variant_id:
            print(f"  {DIM}variant_id:     {variant_id}{RESET}")
        llm_left = sum(1 for r in rules if r.detector_type == "llm")
        if llm_left and out.verdict == "pass":
            print(f"\n  {YELLOW}หมายเหตุ:{RESET} ยังมี {llm_left} กฎที่ต้องใช้ LLM "
                  f"และยังไม่ได้ตรวจในเฟสนี้\n  "
                  f"{DIM}'ผ่าน' ตรงนี้แปลว่าผ่านชั้นกฎตายตัว ไม่ใช่ปลอดภัยแล้ว{RESET}")

    return 1 if out.verdict == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
