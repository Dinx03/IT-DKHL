-- 001_brand_core.sql — Brand DNA (แกนกลาง) + Knowledge Base
-- หลักการ: Brand DNA 1 เวอร์ชัน = 1 แถว = 1 เอกสาร jsonb สมบูรณ์ในตัว
-- agent โหลดแถวเดียวจบ ไม่ต้อง join, cache ง่าย, diff/rollback ได้

create table organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text        not null,
  timezone    text        not null default 'Asia/Bangkok',
  currency    char(3)     not null default 'THB',
  created_at  timestamptz not null default now()
);

create table brands (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null references organizations(id) on delete cascade,
  slug          text not null,
  display_name  text not null,
  -- ผูกกับ Company ใน ERPNext (ชื่อ doctype record ไม่ใช่ตัวเลข)
  erp_company   text,
  status        text not null default 'active'
                check (status in ('active','paused','archived')),
  created_at    timestamptz not null default now(),
  unique (org_id, slug)
);

-- ─────────────────────────────────────────────────────────────
-- Brand DNA — versioned, immutable
-- ─────────────────────────────────────────────────────────────

create table brand_dna_versions (
  id              uuid primary key default gen_random_uuid(),
  brand_id        uuid    not null references brands(id) on delete cascade,
  version         integer not null,
  parent_version  integer,
  status          text    not null default 'draft'
                  check (status in ('draft','active','archived')),
  document        jsonb   not null,
  -- ใช้เทียบว่า agent run ไหนใช้ DNA ชุดไหน (บันทึกลง agent_runs)
  checksum        text generated always as (md5(document::text)) stored,
  created_by      text    not null,        -- 'human:pom' | 'agent:analyst'
  note            text,
  created_at      timestamptz not null default now(),
  activated_at    timestamptz,

  unique (brand_id, version),

  -- บังคับ contract ระดับ DB: ขาด facet ไหนไม่ให้บันทึก
  constraint brand_dna_shape check (
    document ?& array['schema','identity','audience','voice','claims_policy','offer','escalation']
  )
);

-- active ได้แบรนด์ละ 1 เวอร์ชันเท่านั้น
create unique index brand_dna_one_active
  on brand_dna_versions (brand_id) where status = 'active';

comment on column brand_dna_versions.document is
  'รูปร่างดู brand-dna.example.json — ห้ามเก็บ "ข้อเท็จจริงที่ ERPNext เป็นเจ้าของ" (ราคา/สต็อก/ล็อต) เก็บได้แค่ pointer';

-- ─────────────────────────────────────────────────────────────
-- ข้อเสนอแก้ DNA จาก Analyst agent — ปิดลูปการเรียนรู้ แต่มีคนอนุมัติ
-- ─────────────────────────────────────────────────────────────

create table brand_dna_proposals (
  id                 uuid primary key default gen_random_uuid(),
  brand_id           uuid not null references brands(id) on delete cascade,
  based_on_version   uuid not null references brand_dna_versions(id),
  facet_path         text not null,   -- JSON Pointer เช่น '/voice/avoid_phrases/-'
  operation          text not null check (operation in ('add','replace','remove')),
  value              jsonb,
  rationale_th       text not null,
  -- หลักฐาน: อ้าง event_id + ตัวเลขที่ใช้สรุป ตรวจย้อนได้ว่าไม่ได้มั่ว
  evidence           jsonb not null default '[]',
  confidence         numeric(3,2) check (confidence between 0 and 1),
  proposed_by        text not null,   -- 'agent:analyst'
  status             text not null default 'pending'
                     check (status in ('pending','accepted','rejected','superseded')),
  reviewed_by        text,
  reviewed_at        timestamptz,
  applied_in_version uuid references brand_dna_versions(id),
  created_at         timestamptz not null default now()
);

create index on brand_dna_proposals (brand_id, status, created_at desc);

-- ─────────────────────────────────────────────────────────────
-- Knowledge Base (RAG ของ Concierge agent)
-- ─────────────────────────────────────────────────────────────

create table knowledge_docs (
  id              uuid primary key default gen_random_uuid(),
  brand_id        uuid not null references brands(id) on delete cascade,
  title           text not null,
  category        text not null
                  check (category in ('product','pricing','promotion','booking',
                                      'aftercare','faq','policy','shipping')),
  body            text not null,
  -- ผูกกับของจริงใน ERP: ถ้ามีค่า Concierge จะ join สต็อก/ราคาสดตอนตอบ
  erp_item_code   text,
  -- โปรโมชั่น/ราคาช่วงเทศกาลหมดอายุเองได้ กัน AI ตอบโปรที่จบไปแล้ว
  valid_from      date,
  valid_until     date,
  -- true = เนื้อหาแตะเคลมสุขภาพ ต้องผ่านคนก่อน publish เข้า KB
  review_required boolean not null default false,
  status          text not null default 'draft'
                  check (status in ('draft','pending_review','published','archived')),
  source_type     text not null default 'manual'
                  check (source_type in ('manual','file_import','ai_suggested','erp_sync')),
  source_uri      text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index on knowledge_docs (brand_id, status, category);
create index on knowledge_docs (erp_item_code) where erp_item_code is not null;

create table knowledge_chunks (
  id           uuid primary key default gen_random_uuid(),
  doc_id       uuid not null references knowledge_docs(id) on delete cascade,
  chunk_index  integer not null,
  content      text not null,
  embedding    vector(1536),
  token_count  integer,
  unique (doc_id, chunk_index)
);

create index on knowledge_chunks using hnsw (embedding vector_cosine_ops);
create index on knowledge_chunks using gin (content gin_trgm_ops);
