"""
worker.py — ตัวเดียวในระบบที่ลงมือทำกับโลกภายนอก

    py -m growth.runtime.worker --once      ทำงานที่อนุมัติแล้วทั้งหมดแล้วจบ
    py -m growth.runtime.worker             วนทำเรื่อยๆ (ทุก 10 วินาที)

หยิบเฉพาะงานที่:
  - status = pending หรือ failed (ยังไม่เกิน max_attempts)
  - ถึงเวลา next_attempt_at แล้ว
  - **ไม่ต้องอนุมัติ หรืออนุมัติแล้ว** ← กฎสำคัญที่สุด
    งานที่แตะเงินจะค้างอยู่จนกว่าคนจะกดในหน้าศูนย์กลาง

agent ไม่เคยเรียก ERPNext เขียนเอง — เส้นทางเดียวคือผ่านที่นี่
ทำให้มีจุดเดียวที่ต้องดูเวลาอยากรู้ว่า "ระบบไปทำอะไรข้างนอกบ้าง"
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import db, erp, orchestrator

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

BACKOFF_S = [30, 120, 600, 3600, 21600]     # หน่วงนานขึ้นเรื่อยๆ เมื่อพลาดซ้ำ


def claim(conn) -> dict | None:
    """หยิบงานทีละชิ้นแบบกันชนกัน — skip locked เผื่อวันหน้ารันหลาย worker"""
    return conn.execute(
        """update outbound_jobs set status = 'running', attempts = attempts + 1
            where id = (
              select id from outbound_jobs
               where status in ('pending', 'failed')
                 and next_attempt_at <= now()
                 and attempts < max_attempts
                 and (not requires_approval or approved_at is not null)
                 and rejected_by is null
               order by created_at
               for update skip locked limit 1)
          returning *""").fetchone()


def execute(job: dict) -> tuple[bool, dict | str]:
    fn = erp.WRITERS.get(job["kind"])
    if fn is None:
        return False, f"ยังไม่รองรับงานชนิด {job['kind']}"
    try:
        return True, fn(job["payload"])
    except Exception as exc:                                   # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def finish(conn, job: dict, ok: bool, result) -> None:
    if ok:
        conn.execute(
            """update outbound_jobs set status = 'succeeded', result = %s,
                      finished_at = now(), last_error = null where id = %s""",
            (json.dumps(result, default=str), job["id"]))
        # ผูกชื่อ document ที่ ERPNext สร้างกลับเข้าตาราง leads ของเรา
        if job["kind"] == "create_erp_lead" and isinstance(result, dict):
            conv = (job["payload"] or {}).get("conversation_id")
            if conv and result.get("name"):
                conn.execute(
                    """update leads set erp_lead = %s, updated_at = now()
                        where conversation_id = %s""", (result["name"], conv))
    else:
        idx = min(job["attempts"] - 1, len(BACKOFF_S) - 1)
        dead = job["attempts"] >= job["max_attempts"]
        conn.execute(
            """update outbound_jobs
                  set status = %s, last_error = %s,
                      next_attempt_at = now() + make_interval(secs => %s),
                      finished_at = case when %s then now() else null end
                where id = %s""",
            ("dead" if dead else "failed", str(result)[:500], BACKOFF_S[idx],
             dead, job["id"]))
    conn.commit()


def drain(verbose: bool = True) -> int:
    done = 0
    with db.connect() as conn:
        while True:
            job = claim(conn)
            conn.commit()
            if job is None:
                break
            ok, result = execute(job)
            finish(conn, job, ok, result)
            done += 1
            if verbose:
                mark = "สำเร็จ" if ok else "ล้มเหลว"
                detail = (result.get("name", "") if ok and isinstance(result, dict)
                          else str(result)[:90])
                print(f"  [{mark}] {job['kind']} → {job['target']}  {detail}")
    return done


def pending_summary() -> dict[str, int]:
    with db.connect() as conn:
        rows = conn.execute(
            """select status, count(*) n,
                      count(*) filter (where requires_approval and approved_at is null) waiting
                 from outbound_jobs group by status""").fetchall()
    return {r["status"]: r["n"] for r in rows} | {
        "รออนุมัติ": sum(r["waiting"] for r in rows)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="ทำรอบเดียวแล้วจบ")
    p.add_argument("--interval", type=int, default=10)
    a = p.parse_args()

    if a.once:
        n = drain()
        print(f"  ทำไป {n} งาน · คิวตอนนี้: {pending_summary()}")
        return

    print(f"worker ทำงานแล้ว ตรวจคิวทุก {a.interval} วินาที (Ctrl+C เพื่อหยุด)")
    try:
        while True:
            drain(verbose=True)
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nหยุดแล้ว")


if __name__ == "__main__":
    main()
