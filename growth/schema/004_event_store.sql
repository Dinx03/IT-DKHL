-- 004_event_store.sql — Event Store: append-only, partition รายเดือน
--
-- ทำไมต้องมี ทั้งที่มีตารางอื่นอยู่แล้ว:
--   ตารางข้างบนเก็บ "สถานะปัจจุบัน" (ลีดอยู่ stage ไหน)
--   Event Store เก็บ "อะไรเกิดขึ้นบ้าง ตามลำดับ ใครทำ เพราะอะไร"
--   agent หลายตัวคุยกันผ่านที่นี่ — ถ้าไม่มี จะ debug multi-agent ไม่ได้เลย
--   และ Analyst ต้องใช้มันย้อนดูว่าโพสต์ไหนทำให้เกิดยอดขายจริง

create table events (
  event_id        uuid        not null default gen_random_uuid(),
  occurred_at     timestamptz not null,               -- เกิดขึ้นจริงเมื่อไหร่ (เวลาของโลก)
  recorded_at     timestamptz not null default now(), -- เราบันทึกเมื่อไหร่ (อาจช้ากว่า)
  org_id          uuid        not null,
  brand_id        uuid,

  type            text        not null,   -- 'content.published' (ดู event_types)
  source          text        not null,   -- 'chatwoot' | 'meta' | 'erpnext' | 'agent:writer'

  subject_type    text,                   -- 'content_variant' | 'conversation' | 'contact'
  subject_id      text,

  actor_type      text        not null default 'system'
                  check (actor_type in ('human','agent','system','customer','platform')),
  actor_id        text,

  -- หัวใจของ multi-agent:
  -- correlation_id = ทั้งสายเหตุการณ์เดียวกัน (โพสต์ 1 ชิ้นตั้งแต่บรีฟจนปิดการขาย)
  -- causation_id   = event ที่ทำให้ event นี้เกิดขึ้นโดยตรง
  -- สองอันนี้ทำให้ไล่ได้ว่า agent ตัวไหนทำอะไรเพราะอะไร
  correlation_id  uuid        not null,
  causation_id    uuid,

  schema_version  smallint    not null default 1,
  pii_level       text        not null default 'none'
                  check (pii_level in ('none','low','high')),
  payload         jsonb       not null default '{}',

  primary key (event_id, occurred_at)     -- PK ต้องมี partition key
) partition by range (occurred_at);

create index on events (correlation_id, occurred_at);
create index on events (brand_id, type, occurred_at desc);
create index on events (subject_type, subject_id, occurred_at desc);
create index on events using gin (payload jsonb_path_ops);

-- append-only บังคับด้วย trigger ใน 007_append_only.sql
-- (REVOKE ไม่พอ เพราะ owner มีสิทธิ์โดยปริยาย)
revoke update, delete on events from public;

-- ─────────────────────────────────────────────────────────────
-- Partition รายเดือน — ลบข้อมูลเก่าด้วย DROP PARTITION (เร็วกว่า DELETE มาก)
-- ─────────────────────────────────────────────────────────────

create or replace function ensure_event_partition(p_month date)
returns void language plpgsql as $fn$
declare
  start_date date := date_trunc('month', p_month)::date;
  end_date   date := (date_trunc('month', p_month) + interval '1 month')::date;
  part_name  text := 'events_' || to_char(start_date, 'YYYY_MM');
begin
  if not exists (select 1 from pg_class where relname = part_name) then
    execute format(
      'create table %I partition of events for values from (%L) to (%L)',
      part_name, start_date, end_date);
  end if;
end
$fn$;

-- เตรียมเดือนนี้ + 3 เดือนข้างหน้า (ตั้ง cron เรียกทุกเดือน)
select ensure_event_partition((current_date + (n || ' month')::interval)::date)
from generate_series(0, 3) as n;

-- ─────────────────────────────────────────────────────────────
-- ทะเบียน event type — เอกสารที่บังคับใช้ได้ ไม่ใช่ comment ลอยๆ
-- ไม่ใส่ FK เพื่อไม่ให้ write ช้า แต่มี job ตรวจ type แปลกปลอมทุกคืน
-- ─────────────────────────────────────────────────────────────

create table event_types (
  type          text primary key,
  description   text not null,
  payload_shape jsonb,          -- JSON Schema ใช้ validate ตอน dev
  pii_level     text not null default 'none',
  retain_days   integer         -- null = ใช้ default ของ org
);

insert into event_types (type, description, pii_level, retain_days) values
  ('brand.dna_activated',    'เปิดใช้ Brand DNA เวอร์ชันใหม่',        'none', null),
  ('content.requested',      'มีคนสั่งให้สร้างคอนเทนต์',              'none', null),
  ('content.generated',      'Writer เขียนเสร็จ 1 variant',           'none', null),
  ('policy.evaluated',       'Reach Guard ตรวจเสร็จ',                 'none', null),
  ('policy.blocked',         'Reach Guard บล็อกไม่ให้โพสต์',           'none', null),
  ('content.scheduled',      'จัดคิวเผยแพร่',                         'none', null),
  ('content.published',      'เผยแพร่สำเร็จ',                         'none', null),
  ('content.publish_failed', 'เผยแพร่ล้มเหลว',                        'none', null),
  ('metrics.captured',       'ดึงตัวเลขผลงานเข้ามา',                  'none', null),
  ('message.received',       'ลูกค้าส่งข้อความเข้า',                  'high', 365),
  ('message.sent',           'ระบบ/คนตอบกลับ',                        'high', 365),
  ('rule.matched',           'Auto-Reply กฎตายตัวทำงาน',               'low',  180),
  ('stock.queried',          'Concierge ถามสต็อกจาก ERPNext',         'none', 90),
  ('lead.scored',            'Scorer ให้คะแนนโอกาสปิด',                'low',  365),
  ('lead.created',           'สร้างลีด',                              'low',  null),
  ('order.created',          'สร้าง Sales Order ใน ERPNext',           'low',  null),
  ('consent.changed',        'ความยินยอมเปลี่ยน',                     'high', 3650),
  ('human.intervened',       'คนเข้ามาแก้/ยกเลิกสิ่งที่ agent ทำ',     'low',  null),
  ('agent.failed',           'agent ทำงานพัง',                        'none', 90);

-- ─────────────────────────────────────────────────────────────
-- Retention — PDPA บังคับว่า "เก็บเท่าที่จำเป็น"
-- และเป็นกลไก upsell ถ้าวันหนึ่งขายเป็น SaaS (30/90/180/365 วัน)
-- ─────────────────────────────────────────────────────────────

create table retention_policies (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null references organizations(id) on delete cascade,
  type_pattern text not null default '*',   -- '*' หรือ 'message.%'
  retain_days  integer not null,
  action       text not null default 'anonymize'
               check (action in ('delete','anonymize')),
  unique (org_id, type_pattern)
);

-- anonymize = ลบ payload ที่เป็น PII แต่เก็บโครงเหตุการณ์ไว้ให้ Analyst ใช้ต่อ
-- รันด้วย role ที่มีสิทธิ์ update บน events เท่านั้น
create or replace function anonymize_events(p_before timestamptz)
returns bigint language plpgsql as $fn$
declare
  n bigint;
begin
  update events
     set payload = jsonb_build_object(
                     '_anonymized', true,
                     'kept', payload - 'text' - 'name' - 'phone' - 'email'),
         pii_level = 'none'
   where occurred_at < p_before
     and pii_level <> 'none'
     and not (payload ? '_anonymized');
  get diagnostics n = row_count;
  return n;
end
$fn$;

-- ─────────────────────────────────────────────────────────────
-- Read model — event store อ่านตรงช้า ต้องมี projection
-- ─────────────────────────────────────────────────────────────

create materialized view content_performance as
select v.id                       as variant_id,
       c.brand_id,
       v.platform,
       c.topic,
       c.strategy,
       c.dna_version,
       v.published_at,
       pe.risk_score,
       pe.verdict,
       m.reach,
       m.impressions,
       m.likes + m.comments + m.shares + coalesce(m.saves, 0) as engagements,
       case when m.reach > 0
            then round((m.likes + m.comments + m.shares)::numeric / m.reach * 100, 2)
       end                        as engagement_rate_pct
from   content_variants v
join   content_items    c on c.id = v.content_id
left join lateral (
         select * from policy_evaluations
          where variant_id = v.id
          order by attempt desc limit 1) pe on true
left join lateral (
         select * from content_metrics
          where variant_id = v.id
          order by captured_at desc limit 1) m on true
where  v.status = 'published';

create unique index on content_performance (variant_id);
