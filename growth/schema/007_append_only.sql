-- 007_append_only.sql — บังคับ append-only ด้วย trigger แทน REVOKE
--
-- ทำไมต้องมีไฟล์นี้:
--   ไฟล์ 003 และ 004 ใช้ `revoke update, delete ... from public` ซึ่ง "ไม่กันอะไรเลย"
--   เพราะ owner ของตารางมีสิทธิ์โดยปริยาย REVOKE จาก public ไม่แตะ owner
--   และ owner ก็คือ role เดียวกับที่แอปต่อเข้ามา (growth)
--   → ledger ความยินยอมแก้ย้อนหลังได้จริง ซึ่งทำให้ข้อกำหนด PDPA พัง
--   ตรวจพบตอนรันจริง 12 ก.ย. 2026 ไม่ใช่ตอนออกแบบ
--
-- trigger กันได้ทุก role รวมทั้ง owner (superuser ยังสั่งปิด trigger ได้
-- ซึ่งถูกต้องแล้ว — งานซ่อมข้อมูลระดับนั้นควรต้องตั้งใจทำ)

create or replace function deny_mutation()
returns trigger language plpgsql as $fn$
begin
  -- ช่องทางเดียวที่ยอมให้แก้: งาน retention ที่ตั้งธงไว้ในทรานแซกชัน
  if coalesce(current_setting('growth.maintenance', true), '') = 'on' then
    return null;
  end if;
  raise exception 'ตาราง % เป็น append-only ห้าม %', tg_table_name, tg_op
    using errcode = 'restrict_violation',
          hint = 'ถ้าเป็นงาน retention ให้เรียกผ่าน anonymize_events() ไม่ใช่ UPDATE ตรง';
end
$fn$;

-- ── consent_events: ห้ามแก้เด็ดขาด ไม่มีข้อยกเว้นแม้แต่งาน retention ──
-- PDPA ต้องพิสูจน์ย้อนหลังได้ว่า ณ วันนั้นมีสิทธิ์ส่งหรือไม่
create or replace function deny_consent_mutation()
returns trigger language plpgsql as $fn$
begin
  raise exception 'consent_events เป็น append-only ห้าม % — เพิกถอนความยินยอมให้ INSERT แถวใหม่ state=withdrawn', tg_op
    using errcode = 'restrict_violation';
end
$fn$;

drop trigger if exists consent_events_append_only on consent_events;
create trigger consent_events_append_only
  before update or delete on consent_events
  for each statement execute function deny_consent_mutation();

-- ── events: ห้ามแก้ ยกเว้นงาน retention ──
-- การลบข้อมูลเก่าใช้ DROP PARTITION ไม่ใช่ DELETE
drop trigger if exists events_append_only on events;
create trigger events_append_only
  before update or delete on events
  for each statement execute function deny_mutation();

-- partition ที่มีอยู่แล้วต้องติด trigger ด้วย ไม่งั้นยิงตรงที่ partition จะทะลุ
do $mig$
declare
  part text;
begin
  for part in
    select c.relname from pg_inherits i
    join pg_class c on c.oid = i.inhrelid
    join pg_class p on p.oid = i.inhparent
    where p.relname = 'events'
  loop
    execute format('drop trigger if exists events_append_only on %I', part);
    execute format(
      'create trigger events_append_only before update or delete on %I
         for each statement execute function deny_mutation()', part);
  end loop;
end
$mig$;

-- สร้าง partition ใหม่แล้วต้องติด trigger ให้ด้วยเสมอ
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
    execute format(
      'create trigger events_append_only before update or delete on %I
         for each statement execute function deny_mutation()', part_name);
  end if;
end
$fn$;

-- anonymize_events ต้องตั้งธงเองก่อนแก้ ไม่งั้นโดน trigger กัน
create or replace function anonymize_events(p_before timestamptz)
returns bigint language plpgsql as $fn$
declare
  n bigint;
begin
  perform set_config('growth.maintenance', 'on', true);   -- true = ผลเฉพาะทรานแซกชันนี้
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
