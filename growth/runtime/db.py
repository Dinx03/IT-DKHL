"""
db.py — ชั้นเข้าถึงฐานข้อมูล

หน้าที่เดียว: แปลงแถวใน DB เป็น contract ที่ agent กิน และกลับกัน
agent ไม่เคยเห็น SQL — ดูกฎเหล็กข้อ 1 ใน agents/common.py
"""

from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ..agents.agents import PolicyRuleView, RecentPost
from ..agents.auto_reply import AutoReplyRule
from ..agents.common import FACETS_FOR_AGENT, DnaSlice, KnowledgeSnippet, Turn

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _load_env() -> dict[str, str]:
    """อ่าน growth/.env — ไฟล์นี้อยู่ใน .gitignore ห้ามคอมมิต"""
    env: dict[str, str] = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k in ("GROWTH_DB_HOST", "GROWTH_DB_PORT", "GROWTH_DB_NAME",
              "GROWTH_DB_USER", "GROWTH_DB_PASS"):
        if k in os.environ:
            env[k] = os.environ[k]          # env var ชนะไฟล์เสมอ
    return env


def connect() -> psycopg.Connection:
    e = _load_env()
    missing = [k for k in ("GROWTH_DB_HOST", "GROWTH_DB_NAME",
                           "GROWTH_DB_USER", "GROWTH_DB_PASS") if not e.get(k)]
    if missing:
        raise RuntimeError(
            f"ตั้งค่าไม่ครบ: {', '.join(missing)} — ดู growth/.env "
            f"(สร้างจากรหัสใน ~/growth.env บน VM)")
    return psycopg.connect(
        host=e["GROWTH_DB_HOST"], port=int(e.get("GROWTH_DB_PORT", "5432")),
        dbname=e["GROWTH_DB_NAME"], user=e["GROWTH_DB_USER"],
        password=e["GROWTH_DB_PASS"], row_factory=dict_row, connect_timeout=10,
    )


# ─────────────────────────────────────────────────────────────
# แบรนด์ + Brand DNA
# ─────────────────────────────────────────────────────────────

def resolve_brand(conn: psycopg.Connection, slug: str = "ona-healthy") -> tuple[UUID, UUID]:
    row = conn.execute(
        "select b.id as brand_id, b.org_id from brands b where b.slug = %s", (slug,)
    ).fetchone()
    if not row:
        raise LookupError(f"ไม่พบแบรนด์ slug={slug}")
    return row["org_id"], row["brand_id"]


def load_dna(conn: psycopg.Connection, brand_id: UUID, agent: str) -> DnaSlice:
    """ตัดเฉพาะ facet ที่ agent ตัวนั้นต้องใช้ — เรื่องต้นทุน token ล้วนๆ"""
    row = conn.execute(
        """select id, checksum, document from brand_dna_versions
            where brand_id = %s and status = 'active'""", (brand_id,)
    ).fetchone()
    if not row:
        raise LookupError("แบรนด์นี้ยังไม่มี Brand DNA ที่ active")

    allowed = FACETS_FOR_AGENT.get(agent)
    if allowed is None:
        raise KeyError(f"ไม่รู้จัก agent ชื่อ {agent} — เพิ่มใน FACETS_FOR_AGENT ก่อน")
    doc: dict[str, Any] = row["document"]
    return DnaSlice(
        version_id=row["id"],
        checksum=row["checksum"],
        facets={k: doc[k] for k in allowed if k in doc},
    )


# ─────────────────────────────────────────────────────────────
# กฎของ Reach Guard
# ─────────────────────────────────────────────────────────────

def load_rules(conn: psycopg.Connection, platform: str,
               on_date: date | None = None) -> list[PolicyRuleView]:
    """เอาเฉพาะกฎที่ 'มีผลวันนี้' — effective_from ทำให้ตั้งกฎล่วงหน้าได้
    เช่น กฎ TikTok 24 ก.ย. 2026 ที่ยังไม่ควรทำงานวันนี้"""
    rows = conn.execute(
        """select id, platforms, category, severity, detector_type, detector,
                  message_th, fix_hint_th, source_url
             from policy_rules
            where enabled
              and effective_from <= coalesce(%(d)s, current_date)
              and (effective_until is null
                   or effective_until >= coalesce(%(d)s, current_date))
              and (%(p)s = any(platforms) or '*' = any(platforms))
            order by
              case severity when 'block' then 0 when 'warn' then 1 else 2 end,
              id""",
        {"d": on_date, "p": platform},
    ).fetchall()
    return [PolicyRuleView(**r) for r in rows]


def ruleset_hash(rules: list[PolicyRuleView]) -> str:
    """ลายนิ้วมือของชุดกฎที่ใช้ตรวจรอบนั้น — ทำให้ reproduce ผลย้อนหลังได้
    ว่าตอนนั้นตรวจด้วยกฎอะไรบ้าง แม้กฎจะถูกแก้ไปแล้ว"""
    material = "|".join(
        f"{r.id}:{r.severity}:{sorted(r.detector.items())!r}" for r in sorted(rules, key=lambda x: x.id)
    )
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def load_recent_posts(conn: psycopg.Connection, brand_id: UUID, platform: str,
                      days: int = 90, limit: int = 50) -> list[RecentPost]:
    rows = conn.execute(
        """select v.id as variant_id, v.platform, v.body, v.published_at
             from content_variants v
             join content_items c on c.id = v.content_id
            where c.brand_id = %s and v.platform = %s
              and v.published_at > now() - make_interval(days => %s)
            order by v.published_at desc limit %s""",
        (brand_id, platform, days, limit),
    ).fetchall()
    return [RecentPost(**r) for r in rows]


def count_scheduled_same_day(conn: psycopg.Connection, brand_id: UUID,
                             platform: str, on_date: date) -> int:
    row = conn.execute(
        """select count(*) as n
             from content_variants v
             join content_items c on c.id = v.content_id
            where c.brand_id = %s and v.platform = %s
              and v.status in ('scheduled', 'published')
              and coalesce(v.published_at, v.scheduled_at)::date = %s""",
        (brand_id, platform, on_date),
    ).fetchone()
    return int(row["n"])


# ─────────────────────────────────────────────────────────────
# กฎ Auto-Reply (ชั้นที่ทำงานก่อน AI)
# ─────────────────────────────────────────────────────────────

def load_auto_reply_rules(conn: psycopg.Connection, brand_id: UUID) -> list[AutoReplyRule]:
    rows = conn.execute(
        """select id, name, priority, channels, match_type, match,
                  action, reply_th, escalate_note_th, stop_processing
             from auto_reply_rules
            where brand_id = %s and enabled
            order by priority""",
        (brand_id,),
    ).fetchall()
    return [AutoReplyRule(**r) for r in rows]


def bump_rule_hit(conn: psycopg.Connection, rule_id: UUID) -> None:
    """นับว่ากฎไหนถูกใช้บ่อย — Analyst เอาไปเสนอว่าควรเพิ่ม/ตัดกฎไหน"""
    conn.execute("update auto_reply_rules set hit_count = hit_count + 1 where id = %s",
                 (rule_id,))


def resolve_item(conn: psycopg.Connection, text: str, limit: int = 3) -> list[dict]:
    """ลูกค้าพูดไทย → รหัสสินค้าจริง (ชื่อใน ERPNext เป็นอังกฤษ ค้นตรงไม่เจอ)"""
    conn.execute("set local pg_trgm.similarity_threshold = 0.1")
    return conn.execute(
        """select erp_item_code, title,
                  greatest(similarity(title, %(q)s), similarity(body, %(q)s)) as score
             from knowledge_docs
            where category = 'product' and erp_item_code is not null
              and (title %% %(q)s or body %% %(q)s)
            order by score desc limit %(n)s""",
        {"q": text, "n": limit},
    ).fetchall()


# ─────────────────────────────────────────────────────────────
# ตัวตนลูกค้า + บทสนทนา (ลูกค้า 360 + PDPA)
# ─────────────────────────────────────────────────────────────

def upsert_contact(conn: psycopg.Connection, brand_id: UUID, channel: str,
                   external_id: str, display_name: str | None = None) -> tuple[UUID, bool]:
    """คืน (contact_id, เป็นคนใหม่ไหม)

    contact_identities มี unique(channel, external_id) — ตัวตนหนึ่งผูกได้ contact เดียว
    ลูกค้าคนเดียวที่ทักทั้ง LINE และ FB จะเป็นคนละ contact จนกว่าจะมีคนสั่งรวมร่าง
    (รวมอัตโนมัติจากเบอร์/อีเมลตรงกัน เป็นงานของเฟสหลัง — รวมผิดคนแย่กว่าไม่รวม)"""
    row = conn.execute(
        """select contact_id from contact_identities
            where channel = %s and external_id = %s""",
        (channel, external_id),
    ).fetchone()
    if row:
        conn.execute("update contacts set last_seen_at = now() where id = %s",
                     (row["contact_id"],))
        return row["contact_id"], False

    c = conn.execute(
        "insert into contacts (brand_id, display_name) values (%s, %s) returning id",
        (brand_id, display_name),
    ).fetchone()
    conn.execute(
        """insert into contact_identities (contact_id, channel, external_id, display_name)
           values (%s, %s, %s, %s)""",
        (c["id"], channel, external_id, display_name),
    )
    return c["id"], True


def record_inbound_consent(conn: psycopg.Connection, contact_id: UUID,
                           channel: str, evidence_event_id: UUID | None) -> None:
    """ลูกค้าทักมาหาเรา = มีฐานทางกฎหมายให้ประมวลผลข้อมูลเพื่อ "ตอบกลับ" ได้
    lawful_basis = contract (จำเป็นต่อการให้บริการตามที่เขาร้องขอ)

    ⚠️ ไม่ใช่ความยินยอมให้ส่งการตลาด — อันนั้นต้องขอแยกและต้องกดยอมจริง
    การเหมารวมสองอย่างนี้คือความผิดพลาดที่ทำให้โดน PDPA"""
    exists = conn.execute(
        """select 1 from consent_events
            where contact_id = %s and purpose = 'data_processing' limit 1""",
        (contact_id,),
    ).fetchone()
    if exists:
        return
    conn.execute(
        """insert into consent_events
             (contact_id, purpose, state, lawful_basis, channel,
              source_text, evidence_event_id, effective_at)
           values (%s, 'data_processing', 'granted', 'contract', %s, %s, %s, now())""",
        (contact_id, channel, "ลูกค้าเริ่มทักเข้ามาเอง", evidence_event_id),
    )


def upsert_conversation(conn: psycopg.Connection, brand_id: UUID, contact_id: UUID,
                        channel: str, chatwoot_id: int | None = None) -> UUID:
    if chatwoot_id is not None:
        row = conn.execute(
            "select id from conversations where brand_id = %s and chatwoot_id = %s",
            (brand_id, chatwoot_id),
        ).fetchone()
        if row:
            conn.execute(
                "update conversations set last_message_at = now() where id = %s",
                (row["id"],))
            return row["id"]

    row = conn.execute(
        """select id from conversations
            where brand_id = %s and contact_id = %s and state = 'open'
            order by opened_at desc limit 1""",
        (brand_id, contact_id),
    ).fetchone()
    if row:
        conn.execute("update conversations set last_message_at = now() where id = %s",
                     (row["id"],))
        return row["id"]

    row = conn.execute(
        """insert into conversations (brand_id, contact_id, channel, chatwoot_id,
                                      last_message_at)
           values (%s, %s, %s, %s, now()) returning id""",
        (brand_id, contact_id, channel, chatwoot_id),
    ).fetchone()
    return row["id"]


def handoff(conn: psycopg.Connection, conversation_id: UUID) -> None:
    """ส่งต่อคน — ตั้งสถานะให้ขึ้นในคิวรอคนตอบ"""
    conn.execute(
        """update conversations
              set state = 'waiting_human', handled_by = 'human'
            where id = %s""",
        (conversation_id,))


def human_queue(conn: psycopg.Connection, brand_id: UUID) -> list[dict]:
    """คิวที่คนต้องเข้ามาตอบ — เรียงคนที่รอนานสุดก่อน"""
    return conn.execute(
        """select c.id, c.channel, c.last_message_at,
                  coalesce(ct.display_name, ci.display_name, ci.external_id) as ลูกค้า,
                  (select payload->>'text' from events e
                    where e.correlation_id is not null
                      and e.subject_id = c.id::text
                      and e.type = 'message.received'
                    order by e.occurred_at desc limit 1) as ข้อความล่าสุด,
                  (select payload->>'reason_th' from events e
                    where e.subject_id = c.id::text
                      and e.type = 'conversation.escalated'
                    order by e.occurred_at desc limit 1) as เหตุผล
             from conversations c
             left join contacts ct on ct.id = c.contact_id
             left join contact_identities ci on ci.contact_id = c.contact_id
            where c.brand_id = %s and c.state = 'waiting_human'
            order by c.last_message_at asc""",
        (brand_id,),
    ).fetchall()


def knowledge_for(conn: psycopg.Connection, brand_id: UUID, text: str,
                  limit: int = 4) -> list[KnowledgeSnippet]:
    """ดึงความรู้ที่เกี่ยวข้องให้ Concierge — ตัดของที่หมดอายุออกตั้งแต่ชั้นนี้
    ไม่ปล่อยให้ agent เห็นโปรที่จบไปแล้วแล้วตัดสินใจเอง"""
    conn.execute("set local pg_trgm.similarity_threshold = 0.1")
    rows = conn.execute(
        """select id, title, body, category, erp_item_code, valid_until,
                  greatest(similarity(title, %(q)s), similarity(body, %(q)s)) as score
             from knowledge_docs
            where brand_id = %(b)s
              and status in ('published', 'draft')
              and (valid_until is null or valid_until >= current_date)
              and (title %% %(q)s or body %% %(q)s)
            order by score desc limit %(n)s""",
        {"q": text, "b": brand_id, "n": limit},
    ).fetchall()
    return [KnowledgeSnippet(doc_id=r["id"], chunk_id=r["id"], title=r["title"],
                             content=r["body"], category=r["category"],
                             erp_item_code=r["erp_item_code"], score=float(r["score"]),
                             valid_until=None) for r in rows]


def conversation_turns(conn: psycopg.Connection, conversation_id: UUID,
                       limit: int = 20) -> list[Turn]:
    """ประกอบประวัติแชทจาก event — Chatwoot เป็นเจ้าของข้อความจริง
    ที่นี่เก็บพอให้ agent มีบริบท ไม่ได้ตั้งใจเก็บครบ"""
    rows = conn.execute(
        """select type, occurred_at, payload from events
            where subject_id = %s and type in ('message.received', 'message.sent')
            order by occurred_at desc limit %s""",
        (str(conversation_id), limit),
    ).fetchall()
    out: list[Turn] = []
    for r in reversed(rows):
        txt = r["payload"].get("text")
        if not txt:
            continue
        out.append(Turn(role="customer" if r["type"] == "message.received" else "agent",
                        text=txt, at=r["occurred_at"]))
    return out


def latest_score(conn: psycopg.Connection, conversation_id: UUID) -> int | None:
    row = conn.execute(
        """select score from lead_scores where conversation_id = %s
            order by scored_at desc limit 1""", (conversation_id,)).fetchone()
    return row["score"] if row else None


def save_score(conn: psycopg.Connection, conversation_id: UUID, out, model: str) -> None:
    conn.execute(
        """insert into lead_scores (conversation_id, score, signals, model)
           values (%s, %s, %s, %s)""",
        (conversation_id, out.score, out.signals.model_dump_json(), model))


def upsert_lead(conn: psycopg.Connection, brand_id: UUID, contact_id: UUID,
                conversation_id: UUID, score: int, value) -> UUID:
    """ลีดของเรา — erp_lead จะถูกเติมโดย worker หลังคนอนุมัติและ ERPNext สร้างจริง"""
    row = conn.execute(
        "select id, best_score from leads where conversation_id = %s", (conversation_id,)
    ).fetchone()
    if row:
        conn.execute(
            """update leads set best_score = greatest(coalesce(best_score,0), %s),
                      value_thb = coalesce(%s, value_thb), updated_at = now()
                where id = %s""", (score, value, row["id"]))
        return row["id"]
    return conn.execute(
        """insert into leads (brand_id, contact_id, conversation_id, stage,
                              best_score, value_thb)
           values (%s, %s, %s, 'qualified', %s, %s) returning id""",
        (brand_id, contact_id, conversation_id, score, value)).fetchone()["id"]
