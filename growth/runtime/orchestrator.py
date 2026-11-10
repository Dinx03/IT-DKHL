"""
orchestrator.py — ตัวเดียวในระบบที่ได้เขียนลงฐานข้อมูล

agent คืน AgentResult ที่มี EventDraft / EffectDraft มา
ที่นี่คือที่ที่มันกลายเป็นแถวจริง พร้อมเติม correlation_id / causation_id ให้

ทำไมต้องรวมไว้ที่เดียว:
  - agent ทดสอบได้โดยไม่ต้องมี DB (ดูกฎเหล็กข้อ 1)
  - ทุกอย่างลงในทรานแซกชันเดียว event กับ effect ไม่มีทางหลุดจากกัน
  - สายเหตุการณ์ถูกร้อยที่จุดเดียว ไม่ต้องเชื่อว่า agent แต่ละตัวร้อยถูก

Orchestrator ตั้งใจให้เป็น state machine ธรรมดา ไม่ใช่ LLM
ถ้าให้โมเดลตัดสินใจว่าจะเรียกใครต่อ จะ debug ไม่ได้และแพงโดยไม่จำเป็น
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import psycopg

from ..agents.common import AgentResult


def new_correlation() -> UUID:
    """เปิดสายเหตุการณ์ใหม่ — หนึ่งสาย = หนึ่งเรื่องที่ไล่ย้อนได้ตั้งแต่ต้นจนจบ"""
    return uuid4()


def commit(
    conn: psycopg.Connection,
    result: AgentResult,
    *,
    org_id: UUID,
    brand_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    agent: str,
    subject_id: str | None = None,
    meta: dict | None = None,
) -> UUID | None:
    """เขียน events + effects + agent_runs ในทรานแซกชันเดียว
    คืน event_id ตัวสุดท้าย เอาไปเป็น causation_id ของก้าวถัดไป"""

    last_event: UUID | None = causation_id

    with conn.transaction():
        # ── events ── ร้อยเป็นลูกโซ่: ตัวถัดไป causation ชี้ตัวก่อนหน้าเสมอ
        for ev in result.events:
            row = conn.execute(
                """insert into events
                     (occurred_at, org_id, brand_id, type, source,
                      subject_type, subject_id, actor_type, actor_id,
                      correlation_id, causation_id, pii_level, payload)
                   -- clock_timestamp() ไม่ใช่ now() —
                   -- now() คืนเวลา "เริ่มทรานแซกชัน" event ที่เขียนพร้อมกัน
                   -- จะได้เวลาเท่ากันหมด แล้วเรียงลำดับเหตุการณ์ไม่ได้เลย
                   values (clock_timestamp(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   returning event_id""",
                (org_id, brand_id, ev.type, f"agent:{agent}",
                 ev.subject_type, ev.subject_id or subject_id,
                 ev.actor_type, ev.actor_id or agent,
                 correlation_id, last_event, ev.pii_level, json.dumps(ev.payload)),
            ).fetchone()
            last_event = row["event_id"]

        # ── escalation ── เหตุผลที่ส่งต่อคน ต้องเก็บ ไม่งั้นคิวรอคนตอบจะบอกไม่ได้ว่าทำไม
        if result.escalate:
            e = result.escalate
            row = conn.execute(
                """insert into events
                     (occurred_at, org_id, brand_id, type, source, subject_type,
                      subject_id, actor_type, actor_id, correlation_id,
                      causation_id, pii_level, payload)
                   values (clock_timestamp(), %s, %s, 'conversation.escalated', %s,
                           'conversation', %s, 'agent', %s, %s, %s, 'low', %s)
                   returning event_id""",
                (org_id, brand_id, f"agent:{agent}", subject_id, agent,
                 correlation_id, last_event,
                 json.dumps({"reason_th": e.reason_th, "rule": e.rule,
                             "owner": e.suggested_owner})),
            ).fetchone()
            last_event = row["event_id"]

        # ── effects ── ยังไม่ทำงาน แค่เข้าคิว มี worker แยกไปหยิบ
        for eff in result.effects:
            conn.execute(
                """insert into outbound_jobs
                     (correlation_id, kind, target, idempotency_key, payload)
                   values (%s, %s, %s, %s, %s)
                   on conflict (idempotency_key) do nothing""",
                (correlation_id, eff.kind, eff.target,
                 eff.idempotency_key, json.dumps(eff.payload)),
            )

        # ── agent_runs ── ต้นทุนและความเร็ว ถ้าไม่เก็บจะไม่มีวันรู้ว่าใครกินเงิน
        u = result.usage
        conn.execute(
            """insert into agent_runs
                 (correlation_id, brand_id, agent, model, dna_checksum, prompt_hash,
                  input_ref, prompt_tokens, completion_tokens, cached_tokens,
                  cost_thb, latency_ms, tool_calls, status, error, finished_at)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())""",
            (correlation_id, brand_id, agent, u.model,
             (meta or {}).get("dna_checksum"), (meta or {}).get("prompt_hash"),
             json.dumps({"subject_id": subject_id} | (meta or {})),
             u.prompt_tokens, u.completion_tokens, u.cached_tokens,
             u.cost_thb, u.latency_ms, u.tool_calls,
             "ok" if result.ok else "error",
             result.error.message if result.error else None),
        )

    return last_event


def trace(conn: psycopg.Connection, correlation_id: UUID) -> list[dict]:
    """ไล่สายเหตุการณ์ทั้งสาย — เครื่องมือหลักตอน debug multi-agent"""
    return conn.execute(
        """select occurred_at, type, actor_type, actor_id, causation_id, payload
             from events where correlation_id = %s
            order by occurred_at, event_id""",
        (correlation_id,),
    ).fetchall()
