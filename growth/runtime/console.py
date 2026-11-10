"""
console.py — หน้าจอศูนย์กลางสำหรับคน

    py -m growth.runtime.console        แล้วเปิด http://127.0.0.1:8766

ทำไมต้องมี: ระบบพูดว่า "ส่งต่อคน" อยู่ตลอด แต่ไม่มีที่ให้คนไปดู
ของที่ agent ทำไว้ทั้งหมดจึงใช้งานจริงไม่ได้จนกว่าจะมีหน้านี้

รวมทุกอย่างที่รอคนไว้หน้าเดียว:
  1. บทสนทนารอคนตอบ      — พร้อมเหตุผลว่าทำไมถึงส่งต่อ
  2. คอนเทนต์รออนุมัติ     — พร้อมผลตรวจของ Reach Guard
  3. งานที่ต้องกดยืนยัน    — โดยเฉพาะอะไรที่แตะเงิน
  4. ต้นทุน AI รายวัน      — แยกตาม agent

stdlib ล้วน ไม่เพิ่ม dependency · ใช้ภายในเท่านั้น อย่าเปิดออกอินเทอร์เน็ต
"""

from __future__ import annotations

import html
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from . import db, llm

PORT = 8766
OPERATOR = "human:console"

_CSS = """
:root{--bg:#f5f7f2;--card:#fff;--ink:#1b1f1a;--dim:#5a6356;--line:#dbe0d4;
--ok:#2e6b42;--warn:#8f6210;--bad:#a02d2d;--chip:#edf0e9;--accent:#2e6b42}
@media(prefers-color-scheme:dark){:root{--bg:#131611;--card:#1b1f19;--ink:#e9ece4;
--dim:#98a292;--line:#2e342b;--ok:#7cb68c;--warn:#d9a44e;--bad:#e08585;--chip:#232821;--accent:#7cb68c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:64rem;margin:0 auto;padding:2rem 1.25rem 4rem}
header{display:flex;justify-content:space-between;align-items:baseline;
flex-wrap:wrap;gap:.75rem;margin-bottom:.4rem}
h1{font-size:1.45rem;margin:0}
.sys{font-size:.82rem;color:var(--dim);font-family:ui-monospace,monospace}
.sys b{color:var(--ink)}
h2{font-size:1.05rem;margin:2.25rem 0 .75rem;display:flex;gap:.6rem;align-items:center}
.count{background:var(--chip);color:var(--dim);font-size:.78rem;
padding:.1rem .5rem;border-radius:999px;font-family:ui-monospace,monospace}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:.9rem 1.1rem;margin-bottom:.7rem}
.card .top{display:flex;gap:.6rem;align-items:baseline;flex-wrap:wrap;margin-bottom:.3rem}
.who{font-weight:600}
.tag{font-size:.72rem;padding:.1rem .45rem;border-radius:999px;background:var(--chip);
color:var(--dim);font-family:ui-monospace,monospace}
.tag.bad{color:var(--bad)}.tag.ok{color:var(--ok)}.tag.warn{color:var(--warn)}
.msg{background:var(--chip);padding:.5rem .7rem;border-radius:6px;margin:.4rem 0;
white-space:pre-wrap}
.why{color:var(--dim);font-size:.9rem}
.acts{display:flex;gap:.5rem;margin-top:.6rem;flex-wrap:wrap}
button{padding:.35rem .9rem;border:1px solid var(--line);border-radius:6px;
background:var(--card);color:var(--ink);font:inherit;font-size:.88rem;cursor:pointer}
button.primary{background:var(--accent);color:var(--bg);border-color:var(--accent);font-weight:600}
button.danger{color:var(--bad);border-color:var(--bad)}
.empty{color:var(--dim);font-size:.92rem;padding:.6rem 0}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500;font-size:.8rem}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-family:ui-monospace,monospace}
.banner{background:var(--chip);border-left:3px solid var(--warn);padding:.7rem .9rem;
border-radius:0 6px 6px 0;margin-bottom:1.25rem;font-size:.9rem;color:var(--dim)}
"""


def _sec(title: str, n: int) -> str:
    return f'<h2>{title}<span class="count">{n}</span></h2>'


def _render(conn) -> bytes:
    _, brand_id = db.resolve_brand(conn)
    parts: list[str] = []

    real = llm.provider_is_real()
    erp_items = conn.execute(
        "select count(*) n from knowledge_docs where category='product'").fetchone()["n"]
    parts.append(
        '<header><h1>ONA Growth</h1>'
        f'<div class="sys">โมเดล <b>{"ของจริง" if real else "stub (ยังไม่ใส่คีย์)"}</b>'
        f' · สินค้าที่ผูกชื่อไทย <b>{erp_items}</b></div></header>')
    if not real:
        parts.append('<div class="banner">ยังไม่ได้ใส่คีย์โมเดล — คำตอบของ AI '
                     'เป็นข้อความจำลองที่ขึ้นต้นด้วย [stub] อย่าเอาไปใช้กับลูกค้าจริง</div>')

    # ── 1. บทสนทนารอคนตอบ ───────────────────────────────────
    q = db.human_queue(conn, brand_id)
    parts.append(_sec("บทสนทนารอคนตอบ", len(q)))
    if not q:
        parts.append('<div class="empty">ไม่มีใครรออยู่</div>')
    for r in q:
        parts.append(
            f'<div class="card"><div class="top"><span class="who">'
            f'{html.escape(str(r["ลูกค้า"] or "-"))}</span>'
            f'<span class="tag">{html.escape(r["channel"])}</span>'
            f'<span class="tag bad">รอคนตอบ</span></div>'
            f'<div class="msg">{html.escape(str(r["ข้อความล่าสุด"] or "-"))}</div>'
            f'<div class="why">เหตุผล: {html.escape(str(r["เหตุผล"] or "-"))}</div>'
            f'<form method="post" class="acts">'
            f'<input type="hidden" name="action" value="close_conv">'
            f'<input type="hidden" name="id" value="{r["id"]}">'
            f'<button type="submit">ตอบแล้ว ปิดเรื่องนี้</button></form></div>')

    # ── 2. คอนเทนต์รออนุมัติ ────────────────────────────────
    rows = conn.execute(
        """select v.id, v.platform, v.body, v.hashtags, v.status, c.topic, c.strategy,
                  pe.verdict, pe.risk_score, pe.findings, pe.attempt
             from content_variants v
             join content_items c on c.id = v.content_id
             left join lateral (select * from policy_evaluations
                                 where variant_id = v.id
                                 order by attempt desc limit 1) pe on true
            where c.brand_id = %s and v.status in ('guarded', 'blocked')
            order by v.created_at desc""", (brand_id,)).fetchall()
    parts.append(_sec("คอนเทนต์รออนุมัติ", len(rows)))
    if not rows:
        parts.append('<div class="empty">ไม่มีคอนเทนต์ค้าง</div>')
    for r in rows:
        blocked = r["status"] == "blocked"
        tag = ('<span class="tag bad">Guard ไม่ให้ผ่าน</span>' if blocked
               else '<span class="tag ok">ผ่าน Guard</span>')
        finds = ", ".join(f.get("rule_id", "") for f in (r["findings"] or [])) or "-"
        tags = " ".join("#" + h for h in (r["hashtags"] or []))
        parts.append(
            f'<div class="card"><div class="top">'
            f'<span class="who">{html.escape(r["topic"] or "-")}</span>'
            f'<span class="tag">{html.escape(r["platform"])}</span>'
            f'<span class="tag">{html.escape(r["strategy"] or "-")}</span>{tag}'
            f'<span class="tag">เสี่ยง {r["risk_score"]}/100</span>'
            f'<span class="tag">รอบที่ {r["attempt"]}</span></div>'
            f'<div class="msg">{html.escape(r["body"])}</div>'
            f'<div class="why">{html.escape(tags)}'
            + (f'<br>ติดกฎ: {html.escape(finds)}' if blocked else '')
            + '</div>'
            f'<form method="post" class="acts">'
            f'<input type="hidden" name="id" value="{r["id"]}">'
            + ('' if blocked else
               '<button class="primary" name="action" value="approve_content" '
               'type="submit">อนุมัติ พร้อมโพสต์</button>')
            + '<button class="danger" name="action" value="reject_content" '
              'type="submit">ทิ้ง</button></form></div>')

    # ── 3. งานที่ต้องกดยืนยัน ───────────────────────────────
    jobs = conn.execute("select * from jobs_awaiting_approval").fetchall()
    parts.append(_sec("งานที่ต้องกดยืนยันก่อนทำจริง", len(jobs)))
    if not jobs:
        parts.append('<div class="empty">ไม่มีงานรอยืนยัน</div>')
    for j in jobs:
        parts.append(
            f'<div class="card"><div class="top">'
            f'<span class="who">{html.escape(j["kind"])}</span>'
            f'<span class="tag warn">{html.escape(j["target"])}</span></div>'
            f'<div class="msg">{html.escape(json.dumps(j["payload"], ensure_ascii=False, indent=2))}</div>'
            f'<form method="post" class="acts">'
            f'<input type="hidden" name="id" value="{j["id"]}">'
            f'<button class="primary" name="action" value="approve_job" type="submit">'
            f'ยืนยัน ส่งเข้า ERPNext</button>'
            f'<button class="danger" name="action" value="reject_job" type="submit">'
            f'ไม่เอา</button></form></div>')

    # ── 4. ต้นทุน AI ────────────────────────────────────────
    cost = conn.execute(
        """select agent, model, sum(runs) runs, sum(tokens) tokens,
                  sum(tool_calls) tools, sum(cost_thb) thb, max(avg_latency_ms) ms
             from agent_cost_daily where day >= current_date - 7
            group by 1,2 order by thb desc nulls last""").fetchall()
    total = sum(float(c["thb"] or 0) for c in cost)
    parts.append(_sec("ต้นทุน AI 7 วันล่าสุด", f"{total:.2f} บาท"))
    parts.append('<table><tr><th>agent</th><th>โมเดล</th><th class="num">ครั้ง</th>'
                 '<th class="num">token</th><th class="num">tool</th>'
                 '<th class="num">บาท</th><th class="num">ms</th></tr>')
    for c in cost:
        parts.append(
            f'<tr><td>{html.escape(c["agent"])}</td><td>{html.escape(c["model"] or "-")}</td>'
            f'<td class="num">{c["runs"]}</td><td class="num">{c["tokens"] or 0}</td>'
            f'<td class="num">{c["tools"] or 0}</td>'
            f'<td class="num">{float(c["thb"] or 0):.4f}</td>'
            f'<td class="num">{c["ms"] or 0}</td></tr>')
    parts.append('</table>')

    body = "\n".join(parts)
    return (f'<!doctype html><html lang="th"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>ONA Growth — ศูนย์กลาง</title><style>{_CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>').encode()


def _act(conn, action: str, rid: str) -> None:
    if action == "close_conv":
        conn.execute("""update conversations set state = 'closed', closed_at = now()
                         where id = %s""", (rid,))
    elif action == "approve_content":
        conn.execute("update content_variants set status = 'scheduled' where id = %s", (rid,))
    elif action == "reject_content":
        conn.execute("update content_variants set status = 'failed' where id = %s", (rid,))
    elif action == "approve_job":
        conn.execute("""update outbound_jobs set approved_by = %s, approved_at = now()
                         where id = %s""", (OPERATOR, rid))
    elif action == "reject_job":
        conn.execute("""update outbound_jobs set rejected_by = %s, status = 'dead',
                               reject_reason = 'คนไม่อนุมัติ' where id = %s""",
                     (OPERATOR, rid))
    conn.commit()


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: bytes, code: int = 200, location: str | None = None) -> None:
        self.send_response(code)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        with db.connect() as conn:
            self._send(_render(conn))

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode("utf-8"))
        action = (form.get("action") or [""])[0]
        rid = (form.get("id") or [""])[0]
        if action and rid:
            with db.connect() as conn:
                _act(conn, action, rid)
        self._send(b"", 303, "/")          # POST-redirect-GET กันกดซ้ำตอนรีเฟรช

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"ศูนย์กลาง ONA Growth เปิดที่ http://127.0.0.1:{PORT}  (Ctrl+C เพื่อหยุด)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nหยุดแล้ว")


if __name__ == "__main__":
    main()
