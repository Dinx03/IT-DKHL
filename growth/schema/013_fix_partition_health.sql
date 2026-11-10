-- 013_fix_partition_health.sql — แก้ view ที่ cast ชื่อ partition เป็นวันที่ผิด
--
-- บั๊ก: replace('events_2026_09', 'events_', '') = '2026_09'
--       แล้ว ::date → ERROR invalid input syntax for type date
-- เขียนผิดมาตั้งแต่ไฟล์ 008 แต่ไม่มีใครเรียก view นี้จนกระทั่งมี nightly.py
-- จึงไม่เคยมีใครรู้ — เป็นตัวอย่างว่าโค้ดที่ไม่ถูกรันคือโค้ดที่ยังพิสูจน์ไม่ได้ว่าใช้ได้

create or replace view events_partition_health as
select (select count(*) from events_default)                       as ตกใน_default,
       (select min(occurred_at) from events_default)               as เก่าสุดที่ตก,
       (select max(occurred_at) from events_default)               as ใหม่สุดที่ตก,
       (select count(*) from pg_inherits i
          join pg_class p on p.oid = i.inhparent
         where p.relname = 'events')                               as partition_ทั้งหมด,
       (select to_char(max(to_date(substring(c.relname from 8), 'YYYY_MM')), 'YYYY-MM')
          from pg_inherits i
          join pg_class c on c.oid = i.inhrelid
          join pg_class p on p.oid = i.inhparent
         where p.relname = 'events'
           and c.relname ~ '^events_\d{4}_\d{2}$')                 as partition_ไกลสุด;

comment on view events_partition_health is
  'ตรวจทุกคืนพร้อม nightly.py — ตกใน_default ต้องเป็น 0 เสมอ';

select * from events_partition_health;
