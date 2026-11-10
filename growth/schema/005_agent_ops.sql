-- 005_agent_ops.sql — ควบคุมต้นทุน AI · ส่งออกไม่ซ้ำ · โควตา

-- ─────────────────────────────────────────────────────────────
-- ทุกครั้งที่เรียก LLM ต้องลงที่นี่
-- ถ้าไม่มีตารางนี้ ค่า token จะบานโดยไม่รู้ตัวว่า agent ตัวไหนกิน
-- ─────────────────────────────────────────────────────────────

create table agent_runs (
  id                uuid primary key default gen_random_uuid(),
  correlation_id    uuid not null,          -- join กับ events ได้ตรงๆ
  brand_id          uuid references brands(id) on delete set null,
  agent             text not null,          -- 'writer' | 'reach_guard' | 'concierge' | ...
  step              text,                   -- 'draft' | 'critique' | 'rewrite'
  model             text not null,
  dna_checksum      text,                   -- ใช้ DNA ชุดไหน → reproduce ผลได้
  input_ref         jsonb not null default '{}',  -- ชี้ไป subject ไม่ใช่ก๊อป prompt ทั้งก้อน
  prompt_tokens     integer,
  completion_tokens integer,
  cached_tokens     integer,
  cost_thb          numeric(10,4),
  latency_ms        integer,
  status            text not null default 'ok'
                    check (status in ('ok','error','timeout','refused','budget_exceeded')),
  error             text,
  started_at        timestamptz not null default now(),
  finished_at       timestamptz
);

create index on agent_runs (brand_id, agent, started_at desc);
create index on agent_runs (correlation_id);

-- ดูรายวันว่า agent ตัวไหนกินเงินเท่าไหร่
create view agent_cost_daily as
select date_trunc('day', started_at)::date as day,
       brand_id,
       agent,
       model,
       count(*)                                  as runs,
       count(*) filter (where status <> 'ok')    as failures,
       sum(prompt_tokens + completion_tokens)    as tokens,
       round(sum(cost_thb), 2)                   as cost_thb,
       round(avg(latency_ms))                    as avg_latency_ms
from   agent_runs
group  by 1, 2, 3, 4;

-- ─────────────────────────────────────────────────────────────
-- Outbox — ส่งออกไปแพลตฟอร์มภายนอกต้องไม่ซ้ำและ retry ได้
-- ห้ามให้ agent ยิง API ตรง ต้องผ่านคิวนี้เสมอ
-- ─────────────────────────────────────────────────────────────

create table outbound_jobs (
  id              uuid primary key default gen_random_uuid(),
  correlation_id  uuid not null,
  kind            text not null
                  check (kind in ('publish_post','send_message','create_erp_lead',
                                  'create_erp_so','fetch_metrics')),
  target          text not null,          -- 'facebook' | 'line_oa' | 'erpnext'
  -- กันโพสต์ซ้ำตอน retry / webhook ยิงซ้ำ
  idempotency_key text not null unique,
  payload         jsonb not null,
  status          text not null default 'pending'
                  check (status in ('pending','running','succeeded','failed','dead')),
  attempts        integer not null default 0,
  max_attempts    integer not null default 5,
  next_attempt_at timestamptz not null default now(),
  last_error      text,
  result          jsonb,
  created_at      timestamptz not null default now(),
  finished_at     timestamptz
);

create index on outbound_jobs (status, next_attempt_at)
  where status in ('pending', 'failed');

-- ─────────────────────────────────────────────────────────────
-- โควตา — ใช้ในบริษัทตัวเองไว้กันค่า AI บานปลาย
--          ถ้าวันหนึ่งขายเป็น SaaS ก็ใช้ตารางเดียวกันคิดเงิน
-- ─────────────────────────────────────────────────────────────

create table usage_counters (
  org_id      uuid not null references organizations(id) on delete cascade,
  period      date not null,             -- วันแรกของเดือน
  resource    text not null
              check (resource in ('ai_posts','ai_images','chat_messages',
                                  'brainstorm','llm_thb')),
  used        numeric(14,4) not null default 0,
  quota       numeric(14,4),             -- null = ไม่จำกัด
  primary key (org_id, period, resource)
);

create or replace function bump_usage(
  p_org uuid, p_resource text, p_amount numeric default 1)
returns numeric language plpgsql as $fn$
declare
  new_used numeric;
  lim      numeric;
begin
  insert into usage_counters (org_id, period, resource, used)
  values (p_org, date_trunc('month', current_date)::date, p_resource, p_amount)
  on conflict (org_id, period, resource)
  do update set used = usage_counters.used + p_amount
  returning used, quota into new_used, lim;

  if lim is not null and new_used > lim then
    raise exception 'quota exceeded: % (%/%)', p_resource, new_used, lim
      using errcode = 'check_violation';
  end if;
  return new_used;
end
$fn$;
