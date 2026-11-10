"""
web.py — หน้าเว็บเล็กๆ สำหรับวางข้อความแล้วดูผลตรวจ

    py -m growth.runtime.web        แล้วเปิด http://127.0.0.1:8765

ใช้ stdlib ล้วน ไม่เพิ่ม dependency — เป็นเครื่องมือภายในสำหรับทดสอบ Reach Guard
ไม่ใช่หน้าเว็บของผลิตภัณฑ์ อย่าเปิดออกอินเทอร์เน็ต
"""

from __future__ import annotations

import html
import json
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from ..agents.agents import GuardInput, WriterOutput
from ..agents.common import AgentContext
from ..agents.reach_guard import run as guard_run
from . import db, llm, orchestrator, prompts

PORT = 8765
PLATFORMS = ["instagram", "facebook", "tiktok", "line_oa", "x", "linkedin"]

_CSS = """
:root{--bg:#f5f7f2;--card:#fff;--ink:#1b1f1a;--dim:#5a6356;--line:#dbe0d4;
--ok:#2e6b42;--warn:#8f6210;--bad:#a02d2d;--chip:#edf0e9}
@media(prefers-color-scheme:dark){:root{--bg:#131611;--card:#1b1f19;--ink:#e9ece4;
--dim:#98a292;--line:#2e342b;--ok:#7cb68c;--warn:#d9a44e;--bad:#e08585;--chip:#232821}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:52rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
h1{font-size:1.5rem;margin:0 0 .25rem}
.sub{color:var(--dim);font-size:.9rem;margin:0 0 1.75rem}
form{display:flex;flex-direction:column;gap:.75rem}
textarea{width:100%;min-height:8rem;padding:.85rem;border:1px solid var(--line);
background:var(--card);color:var(--ink);border-radius:6px;font:inherit;resize:vertical}
.row{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap}
select{padding:.5rem;border:1px solid var(--line);background:var(--card);
color:var(--ink);border-radius:6px;font:inherit}
button{padding:.55rem 1.4rem;border:0;border-radius:6px;background:var(--ok);
color:var(--bg);font:inherit;font-weight:600;cursor:pointer}
label.chk{display:flex;gap:.4rem;align-items:center;color:var(--dim);font-size:.9rem}
.verdict{margin:2rem 0 1rem;padding:1rem 1.15rem;border-radius:8px;background:var(--card);
border-left:4px solid var(--line);display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap}
.verdict.pass{border-color:var(--ok)}.verdict.rewrite{border-color:var(--warn)}
.verdict.block{border-color:var(--bad)}
.verdict b{font-size:1.15rem}
.verdict.pass b{color:var(--ok)}.verdict.rewrite b{color:var(--warn)}.verdict.block b{color:var(--bad)}
.meta{color:var(--dim);font-size:.85rem;font-family:ui-monospace,monospace}
.f{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:.9rem 1.1rem;margin-bottom:.75rem}
.f .top{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin-bottom:.35rem}
.sev{font-size:.72rem;font-weight:700;padding:.12rem .5rem;border-radius:999px;background:var(--chip)}
.sev.block{color:var(--bad)}.sev.warn{color:var(--warn)}.sev.info{color:var(--dim)}
.rid{font-family:ui-monospace,monospace;font-size:.78rem;color:var(--dim)}
.ex{background:var(--chip);padding:.12rem .4rem;border-radius:4px;font-weight:600}
.fix{color:var(--dim);font-size:.92rem;margin-top:.3rem}
a{color:var(--dim);font-size:.8rem}
.note{margin-top:1.5rem;padding:.85rem 1rem;border-radius:8px;background:var(--chip);
color:var(--dim);font-size:.88rem}
"""

_SEV_TH = {"block": "ห้ามโพสต์", "warn": "ควรแก้", "info": "หมายเหตุ"}
_VERDICT_TH = {"pass": "ผ่านชั้นกฎตายตัว", "rewrite": "ต้องเขียนใหม่", "block": "ห้ามเผยแพร่"}


def _page(body: str = "", platform: str = "instagram", result: str = "") -> bytes:
    opts = "".join(
        f'<option value="{p}"{" selected" if p == platform else ""}>{p}</option>'
        for p in PLATFORMS)
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reach Guard — ONA</title><style>{_CSS}</style></head><body><div class="wrap">
<h1>Reach Guard</h1>
<p class="sub">วางข้อความที่จะโพสต์ แล้วดูว่าติดกฎของแพลตฟอร์มไหนบ้าง — ชั้นกฎตายตัว ไม่ใช้ LLM</p>
<form method="post">
<textarea name="body" placeholder="วางข้อความโพสต์ที่นี่…">{html.escape(body)}</textarea>
<div class="row">
<select name="platform">{opts}</select>
<label class="chk"><input type="checkbox" name="persist" value="1"> บันทึกเป็น content_variant จริง</label>
<button type="submit">ตรวจ</button>
</div></form>
{result}
</div></body></html>""".encode()


def _render(out, rules_n: int, corr, llm_left: int) -> str:
    parts = [
        f'<div class="verdict {out.verdict}"><b>{_VERDICT_TH[out.verdict]}</b>'
        f'<span>ความเสี่ยง {out.risk_score}/100</span>'
        f'<span class="meta">ตรวจ {rules_n} กฎ · ruleset {out.ruleset_hash}</span></div>'
    ]
    if not out.findings:
        parts.append('<div class="f">ไม่พบอะไรจากชั้นกฎตายตัว</div>')
    for f in out.findings:
        ex = f'<span class="ex">{html.escape(f.excerpt)}</span>' if f.excerpt else ""
        fix = f'<div class="fix">แก้: {html.escape(f.fix_hint_th)}</div>' if f.fix_hint_th else ""
        src = (f'<a href="{html.escape(f.source_url)}" target="_blank" rel="noopener">'
               f'อ้างอิงหน้าทางการ</a>') if f.source_url else ""
        parts.append(
            f'<div class="f"><div class="top"><span class="sev {f.severity}">{_SEV_TH[f.severity]}</span>'
            f'<span class="rid">{html.escape(f.rule_id)}</span>{ex}</div>'
            f'<div>{html.escape(f.message_th)}</div>{fix}<div>{src}</div></div>')

    if out.verdict != "pass":
        nxt = ("ส่งกลับให้ Writer เขียนใหม่ได้"
               if out.fixable_by_rewrite
               else "เขียนใหม่ไม่ช่วย — ต้องแก้สื่อหรือตารางเวลา ส่งให้คนตัดสิน")
        parts.append(f'<div class="note">ขั้นต่อไป: {nxt}</div>')
    if llm_left and out.verdict == "pass":
        parts.append(
            f'<div class="note">ยังมี {llm_left} กฎที่ต้องใช้ LLM และยังไม่ได้ตรวจในเฟสนี้ — '
            f'“ผ่าน” ตรงนี้แปลว่าผ่านชั้นกฎตายตัว ไม่ใช่ปลอดภัยแล้ว</div>')
    parts.append(f'<p class="meta">correlation_id: {corr}</p>')
    return "\n".join(parts)


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: bytes, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._send(_page())

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode("utf-8"))
        body = (form.get("body") or [""])[0].strip()
        platform = (form.get("platform") or ["instagram"])[0]
        if platform not in PLATFORMS:
            platform = "instagram"
        if not body:
            self._send(_page(platform=platform))
            return

        with db.connect() as conn:
            org_id, brand_id = db.resolve_brand(conn)
            dna = db.load_dna(conn, brand_id, "reach_guard")
            rules = db.load_rules(conn, platform)
            inp = GuardInput(
                ctx=AgentContext(org_id=org_id, brand_id=brand_id,
                                 agent="reach_guard", now=datetime.now(timezone.utc)),
                dna=dna, platform=platform, draft=WriterOutput(body=body),
                rules=rules, ruleset_hash=db.ruleset_hash(rules),
                scheduled_same_day=db.count_scheduled_same_day(
                    conn, brand_id, platform, date.today()),
            )
            result = guard_run(inp, provider=llm.get_provider(),
                               prompts_load=prompts.load)
            corr = orchestrator.new_correlation()
            orchestrator.commit(conn, result, org_id=org_id, brand_id=brand_id,
                                correlation_id=corr, agent="reach_guard")

        llm_left = sum(1 for r in rules if r.detector_type == "llm")
        self._send(_page(body, platform,
                         _render(result.output, len(rules), corr, llm_left)))

    def log_message(self, *args) -> None:      # เงียบไว้ ไม่รกเทอร์มินัล
        pass


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Reach Guard เปิดที่ http://127.0.0.1:{PORT}  (Ctrl+C เพื่อหยุด)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nหยุดแล้ว")


if __name__ == "__main__":
    main()
