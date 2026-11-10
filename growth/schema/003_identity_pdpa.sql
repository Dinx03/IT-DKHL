-- 003_identity_pdpa.sql — ลูกค้า 360 · ความยินยอม PDPA · แชท · ลีด

-- ─────────────────────────────────────────────────────────────
-- ตัวตนเดียว หลายช่องทาง
-- ─────────────────────────────────────────────────────────────

create table contacts (
  id              uuid primary key default gen_random_uuid(),
  brand_id        uuid not null references brands(id) on delete cascade,
  display_name    text,
  phone           text,
  email           text,
  -- ผูกกับ Customer ใน ERPNext — ตั้งค่าเมื่อปิดการขายได้จริง
  erp_customer    text,
  merged_into     uuid references contacts(id),   -- รวมร่างแล้วชี้ไปตัวหลัก
  first_seen_at   timestamptz not null default now(),
  last_seen_at    timestamptz not null default now(),
  created_at      timestamptz not null default now()
);

create index on contacts (brand_id, last_seen_at desc) where merged_into is null;
create index on contacts (erp_customer) where erp_customer is not null;

create table contact_identities (
  id            uuid primary key default gen_random_uuid(),
  contact_id    uuid not null references contacts(id) on delete cascade,
  channel       text not null
                check (channel in ('facebook','instagram','line','email','phone','web','tiktok')),
  external_id   text not null,     -- PSID / LINE userId / อีเมล
  display_name  text,
  first_seen_at timestamptz not null default now(),
  unique (channel, external_id)    -- ตัวตนหนึ่งผูกได้ contact เดียว
);

create index on contact_identities (contact_id);

-- ─────────────────────────────────────────────────────────────
-- ความยินยอม: append-only ledger — ห้าม UPDATE เด็ดขาด
-- PDPA ต้องพิสูจน์ได้ว่า "ณ วันที่ส่งข้อความนั้น มีสิทธิ์ส่งหรือไม่"
-- การ UPDATE ทับทำให้พิสูจน์ย้อนหลังไม่ได้
-- ─────────────────────────────────────────────────────────────

create table consent_events (
  id                uuid primary key default gen_random_uuid(),
  contact_id        uuid not null references contacts(id) on delete cascade,
  purpose           text not null
                    check (purpose in ('marketing_message','data_processing',
                                       'profiling','third_party_share')),
  state             text not null check (state in ('granted','withdrawn','expired')),
  lawful_basis      text not null
                    check (lawful_basis in ('consent','contract','legitimate_interest')),
  channel           text,
  source_text       text,        -- ข้อความจริงที่ลูกค้าพิมพ์/ปุ่มที่กด
  evidence_event_id uuid,        -- ชี้ไป events.event_id
  effective_at      timestamptz not null,
  expires_at        timestamptz,
  recorded_at       timestamptz not null default now()
);

create index on consent_events (contact_id, purpose, effective_at desc);

-- append-only บังคับด้วย trigger ใน 007_append_only.sql
-- (REVOKE ไม่พอ เพราะ owner มีสิทธิ์โดยปริยาย)
revoke update, delete on consent_events from public;

-- สถานะปัจจุบัน = view ไม่ใช่ตาราง
create view consent_current as
select distinct on (contact_id, purpose)
       contact_id, purpose, state, lawful_basis, effective_at, expires_at,
       (state = 'granted' and (expires_at is null or expires_at > now())) as is_valid
from   consent_events
order  by contact_id, purpose, effective_at desc, recorded_at desc;

-- ─────────────────────────────────────────────────────────────
-- บทสนทนา — ตัวข้อความอยู่ที่ Chatwoot (system of record)
-- ที่นี่เก็บแค่ "สถานะ + ผลการประเมิน" ไม่ก๊อปข้อความมาซ้ำ
-- ─────────────────────────────────────────────────────────────

create table conversations (
  id             uuid primary key default gen_random_uuid(),
  brand_id       uuid not null references brands(id) on delete cascade,
  contact_id     uuid references contacts(id) on delete set null,
  channel        text not null,
  chatwoot_id    bigint,
  handled_by     text not null default 'ai' check (handled_by in ('ai','human','rule')),
  state          text not null default 'open'
                 check (state in ('open','waiting_human','snoozed','closed')),
  opened_at      timestamptz not null default now(),
  last_message_at timestamptz,
  closed_at      timestamptz,
  unique (brand_id, chatwoot_id)
);

create index on conversations (brand_id, state, last_message_at desc);

-- closing score เป็นอนุกรมเวลา ไม่ใช่ค่าเดียว
-- ต้องเห็นว่าคะแนนพุ่งตอนไหน เพื่อ tune scorer และ trigger ตอนถูกจังหวะ
create table lead_scores (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  score           integer not null check (score between 0 and 100),
  -- {"intent":"ready_to_buy","items":["ONATO-500"],"qty":10,"budget_signal":true}
  signals         jsonb not null default '{}',
  model           text not null,
  scored_at       timestamptz not null default now()
);

create index on lead_scores (conversation_id, scored_at desc);

create table leads (
  id              uuid primary key default gen_random_uuid(),
  brand_id        uuid not null references brands(id) on delete cascade,
  contact_id      uuid not null references contacts(id) on delete cascade,
  conversation_id uuid references conversations(id) on delete set null,
  stage           text not null default 'new'
                  check (stage in ('new','qualified','proposal','won','lost','nurturing')),
  best_score      integer,
  -- ปลายทางใน ERPNext
  erp_lead        text,
  erp_sales_order text,
  value_thb       numeric(12,2),
  lost_reason     text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index on leads (brand_id, stage, updated_at desc);
