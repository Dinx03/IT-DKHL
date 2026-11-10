-- 011_agent_runs_gaps.sql — ปิดช่องที่ข้อมูลตกหายระหว่างสัญญากับตาราง
--
-- เจอตอนรันจริง 13 ก.ย. 2026:
--   Usage.tool_calls นับไว้ครบในโค้ด แต่ agent_runs ไม่มีคอลัมน์รองรับ
--   → ไม่มีทางรู้ว่า agent ตัวไหนเรียก ERP ถี่แค่ไหน ซึ่งเป็นทั้งต้นทุนและภาระของ ERPNext
--
--   prompt_hash ก็เช่นกัน — prompts.ref() เขียนไว้แล้วแต่ไม่เคยถูกเก็บ
--   ถ้าไม่เก็บ จะตอบไม่ได้ว่า "ทำไมคำตอบเมื่อวานดีกว่าวันนี้" หลังแก้ prompt

alter table agent_runs add column if not exists tool_calls integer not null default 0;
alter table agent_runs add column if not exists prompt_hash text;

comment on column agent_runs.tool_calls is 'จำนวนครั้งที่เรียก tool ในรอบนั้น';
comment on column agent_runs.prompt_hash is 'จาก growth/prompts/<key>.v<n>.md — ใช้ไล่ย้อนว่าคำตอบมาจาก prompt เวอร์ชันไหน';

drop view if exists agent_cost_daily;
create view agent_cost_daily as
select date_trunc('day', started_at)::date as day,
       brand_id, agent, model,
       count(*)                               as runs,
       count(*) filter (where status <> 'ok') as failures,
       sum(prompt_tokens + completion_tokens) as tokens,
       sum(tool_calls)                        as tool_calls,
       round(sum(cost_thb), 4)                as cost_thb,
       round(avg(latency_ms))                 as avg_latency_ms
from   agent_runs
group  by 1, 2, 3, 4;
