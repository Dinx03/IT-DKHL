-- 002_policy_content.sql — Reach Guard (กฎแพลตฟอร์ม) + คอนเทนต์ 1 บรีฟ → หลายแพลตฟอร์ม

-- ─────────────────────────────────────────────────────────────
-- กฎเป็น "ข้อมูล" ไม่ใช่ "โค้ด"
-- เหตุผล: TikTok อัปเดต Community Guidelines 24 ก.ย. 2026 —
--         ต้องเพิ่ม/ปิดกฎได้โดยไม่ deploy ใหม่ และตั้งวันมีผลล่วงหน้าได้
-- ─────────────────────────────────────────────────────────────

create table policy_rules (
  id              text primary key,          -- 'meta.engagement_bait.react'
  platforms       text[] not null,           -- {facebook,instagram} หรือ {*}
  category        text not null
                  check (category in ('engagement_bait','health_claim','aigc_label',
                                      'unoriginal','frequency','prohibited_topic',
                                      'clickbait','link_safety')),
  severity        text not null check (severity in ('block','warn','info')),
  detector_type   text not null check (detector_type in ('regex','keyword','llm','structural')),
  -- regex:      {"pattern":"...","flags":"i"}
  -- keyword:    {"any":["แท็กเพื่อน","คอมเมนต์คำว่า"]}
  -- llm:        {"prompt_key":"health_claim_v2","threshold":70}
  -- structural: {"check":"same_author_posts_per_feed","max":1}
  detector        jsonb not null,
  message_th      text not null,             -- บอกผู้ใช้ว่าผิดอะไร
  fix_hint_th     text,                      -- บอก Writer ว่าให้แก้ยังไง
  source_url      text,                      -- ลิงก์หน้าทางการ ตรวจย้อนได้ว่าไม่ได้เดา
  effective_from  date not null default current_date,
  effective_until date,
  enabled         boolean not null default true,
  updated_at      timestamptz not null default now()
);

create index on policy_rules (category, enabled);

-- ─────────────────────────────────────────────────────────────
-- คอนเทนต์: 1 บรีฟ (content_items) → N ชิ้นต่อแพลตฟอร์ม (content_variants)
-- ─────────────────────────────────────────────────────────────

create table content_items (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid not null references brands(id) on delete cascade,
  dna_version uuid references brand_dna_versions(id),   -- ใช้ DNA ชุดไหนสร้าง
  kind        text not null default 'social'
              check (kind in ('social','broadcast','sales_page','email')),
  topic       text not null,
  brief       text,
  strategy    text,        -- 'ขายตรง' | 'ให้ความรู้' | 'สร้างการรับรู้'
  campaign    text,
  status      text not null default 'draft'
              check (status in ('draft','generating','review','approved','scheduled','published','failed')),
  created_by  text not null,
  created_at  timestamptz not null default now()
);

create index on content_items (brand_id, status, created_at desc);

create table content_variants (
  id             uuid primary key default gen_random_uuid(),
  content_id     uuid not null references content_items(id) on delete cascade,
  platform       text not null
                 check (platform in ('facebook','instagram','tiktok','line_oa','x','linkedin')),
  body           text not null,
  hashtags       text[] not null default '{}',
  -- [{"url":"...","kind":"image","generator":"ai:flux","depicts_realistic_person":true}]
  -- Reach Guard อ่าน generator/depicts_* เพื่อบังคับติดป้าย AIGC
  media          jsonb not null default '[]',
  aigc_labeled   boolean not null default false,
  status         text not null default 'draft'
                 check (status in ('draft','guarded','blocked','scheduled','published','failed')),
  scheduled_at   timestamptz,
  published_at   timestamptz,
  external_id    text,       -- post id ฝั่งแพลตฟอร์ม
  external_url   text,
  ab_group       text check (ab_group in ('A','B')),
  created_at     timestamptz not null default now()
);

-- 1 บรีฟ ได้ 1 ชิ้นต่อแพลตฟอร์ม (หรือ 2 ชิ้นถ้าทำ A/B)
-- ต้องเป็น unique index ไม่ใช่ unique constraint — PostgreSQL ไม่รับ expression ใน constraint
create unique index content_variants_unique_slot
  on content_variants (content_id, platform, coalesce(ab_group, '-'));

create index on content_variants (status, scheduled_at)
  where status = 'scheduled';

-- ─────────────────────────────────────────────────────────────
-- ผลตรวจของ Reach Guard — เก็บทุกครั้ง ไม่ทับของเดิม
-- ─────────────────────────────────────────────────────────────

create table policy_evaluations (
  id             uuid primary key default gen_random_uuid(),
  variant_id     uuid not null references content_variants(id) on delete cascade,
  attempt        integer not null default 1,
  ruleset_hash   text not null,     -- hash ของกฎที่ enabled ตอนนั้น → reproduce ได้
  verdict        text not null check (verdict in ('pass','rewrite','block')),
  risk_score     integer not null check (risk_score between 0 and 100),
  -- [{"rule_id":"meta.engagement_bait.react","severity":"block","span":[12,28],"excerpt":"..."}]
  findings       jsonb not null default '[]',
  body_before    text not null,
  body_after     text,
  evaluated_by   text not null,     -- 'agent:reach_guard'
  human_override boolean not null default false,
  override_by    text,
  override_note  text,
  created_at     timestamptz not null default now(),
  unique (variant_id, attempt)
);

create index on policy_evaluations (variant_id, created_at desc);

-- ─────────────────────────────────────────────────────────────
-- ผลงานจริง — time series ไม่ใช่คอลัมน์เดียว
-- ต้องเห็น "reach โตช้าลงหลังชั่วโมงที่ 6" ไม่ใช่แค่ยอดรวมสุดท้าย
-- ─────────────────────────────────────────────────────────────

create table content_metrics (
  variant_id   uuid not null references content_variants(id) on delete cascade,
  captured_at  timestamptz not null,
  impressions  bigint,
  reach        bigint,
  likes        bigint,
  comments     bigint,
  shares       bigint,
  saves        bigint,
  clicks       bigint,
  video_views  bigint,
  raw          jsonb not null default '{}',
  primary key (variant_id, captured_at)
);
