-- 008_events_default_partition.sql — กัน event หายเพราะไม่มี partition รองรับ
--
-- ปัญหาที่เจอตอนรันจริง 12 ก.ย. 2026:
--   insert event ที่ occurred_at อยู่นอกช่วง partition ที่มี → ERROR ทันที
--   "no partition of relation events found for row"
--
-- ในระบบจริงเกิดได้จาก:
--   - webhook ส่งเวลาเก่ามา (ระบบปลายทางค้างคิวไว้)
--   - cron สร้าง partition ล่วงหน้าไม่ทำงาน
--   - นำเข้าข้อมูลย้อนหลัง
--   - นาฬิกาเครื่องเพี้ยน (เคยเจอกับ VM นี้มาแล้ว ช้าไป 13 ชม.)
--
-- event store ที่ทำ insert หายคือ event store ที่เชื่อไม่ได้
-- ยอมให้ตกลง default partition ดีกว่าทิ้ง แล้วค่อยเฝ้าดูว่ามีอะไรตกไหม

create table if not exists events_default partition of events default;

create trigger events_append_only
  before update or delete on events_default
  for each statement execute function deny_mutation();

comment on table events_default is
  'ควรว่างเสมอ — มีแถวเมื่อไหร่แปลว่า partition ขาดช่วง ให้ดู view events_partition_health';

-- เฝ้าดูว่ามีอะไรตกลง default ไหม
create or replace view events_partition_health as
select (select count(*) from events_default)                       as ตกใน_default,
       (select min(occurred_at) from events_default)               as เก่าสุดที่ตก,
       (select max(occurred_at) from events_default)               as ใหม่สุดที่ตก,
       (select count(*) from pg_inherits i
          join pg_class p on p.oid = i.inhparent
         where p.relname = 'events')                               as partition_ทั้งหมด,
       (select to_char(max(
                 replace(c.relname, 'events_', '')::text::date), 'YYYY-MM')
          from pg_inherits i
          join pg_class c on c.oid = i.inhrelid
          join pg_class p on p.oid = i.inhparent
         where p.relname = 'events'
           and c.relname ~ '^events_\d{4}_\d{2}$')                 as partition_ไกลสุด;

comment on view events_partition_health is
  'ตรวจทุกเดือนพร้อมตอนรัน ensure_event_partition — ตกใน_default ต้องเป็น 0';
