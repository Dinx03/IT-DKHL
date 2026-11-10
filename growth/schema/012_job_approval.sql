-- 012_job_approval.sql — งานที่ต้องมีคนกดยืนยันก่อนทำจริง
--
-- ช่องโหว่แบบเดียวกับ tool_calls และ prompt_hash:
--   EffectDraft.requires_approval มีในสัญญามาตั้งแต่ต้น แต่ orchestrator ไม่เคยเขียนลง DB
--   → ทุกงานในคิวดูเหมือนกันหมด ไม่มีทางรู้ว่าอันไหนต้องให้คนกดก่อน
--   ซึ่งอันตรายมาก เพราะ CloserOutput บังคับ requires_approval=True สำหรับ Sales Order

alter table outbound_jobs add column if not exists requires_approval boolean not null default true;
alter table outbound_jobs add column if not exists approved_by text;
alter table outbound_jobs add column if not exists approved_at timestamptz;
alter table outbound_jobs add column if not exists rejected_by text;
alter table outbound_jobs add column if not exists reject_reason text;

-- งานที่รออนุมัติต้องไม่ถูก worker หยิบไปทำ
drop index if exists outbound_jobs_status_next_attempt_at_idx;
create index outbound_jobs_runnable
  on outbound_jobs (status, next_attempt_at)
  where status in ('pending', 'failed') and (not requires_approval or approved_at is not null);

create or replace view jobs_awaiting_approval as
select id, kind, target, payload, created_at, correlation_id
from   outbound_jobs
where  status = 'pending' and requires_approval and approved_at is null
       and rejected_by is null
order  by created_at;

comment on view jobs_awaiting_approval is 'คิวที่คนต้องกดยืนยันก่อน — โดยเฉพาะอะไรที่แตะเงิน';
