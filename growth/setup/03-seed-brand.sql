-- 03-seed-brand.sql — ใส่องค์กร แบรนด์ และ Brand DNA เวอร์ชัน 1 ของ ONA Healthy
--
-- รันหลัง DDL ผ่านครบแล้ว:
--   psql -h 127.0.0.1 -U growth growth -v ON_ERROR_STOP=1 -f 03-seed-brand.sql
--
-- รันซ้ำได้ ไม่สร้างซ้ำ (ทุก insert มี not exists คุม)

\set dna `cat /tmp/growth-schema/brand-dna.ona.v1.json`

begin;

-- องค์กร
insert into organizations (name, timezone, currency)
select 'ONA Healthy', 'Asia/Bangkok', 'THB'
where not exists (select 1 from organizations where name = 'ONA Healthy');

-- แบรนด์ — ผูกกับ Company ชื่อเดียวกันใน ERPNext
insert into brands (org_id, slug, display_name, erp_company)
select o.id, 'ona-healthy', 'ONA Healthy', 'ONA Healthy'
from   organizations o
where  o.name = 'ONA Healthy'
  and  not exists (
         select 1 from brands b where b.org_id = o.id and b.slug = 'ona-healthy');

-- Brand DNA เวอร์ชัน 1 — active ทันที
insert into brand_dna_versions
       (brand_id, version, status, document, created_by, note, activated_at)
select b.id, 1, 'active', :'dna'::jsonb, 'human:setup',
       'ดึง item_code / price_list / warehouse จาก ERPNext จริงเมื่อ 12 ก.ย. 2026',
       now()
from   brands b
join   organizations o on o.id = b.org_id
where  o.name = 'ONA Healthy' and b.slug = 'ona-healthy'
  and  not exists (select 1 from brand_dna_versions v where v.brand_id = b.id);

-- นโยบายเก็บข้อมูลเริ่มต้น (PDPA — เก็บเท่าที่จำเป็น)
insert into retention_policies (org_id, type_pattern, retain_days, action)
select o.id, '*', 365, 'anonymize'
from   organizations o
where  o.name = 'ONA Healthy'
on conflict (org_id, type_pattern) do nothing;

insert into retention_policies (org_id, type_pattern, retain_days, action)
select o.id, 'message.%', 365, 'anonymize'
from   organizations o
where  o.name = 'ONA Healthy'
on conflict (org_id, type_pattern) do nothing;

commit;

-- ── ตรวจผล ────────────────────────────────────────────────
\echo ''
\echo '=== Brand DNA ที่ active อยู่ ==='
select b.slug,
       v.version,
       v.status,
       left(v.checksum, 12) as checksum,
       jsonb_array_length(v.document->'identity'->'hero_products') as สินค้าหลัก,
       jsonb_array_length(v.document->'audience'->'segments')      as กลุ่มเป้าหมาย,
       jsonb_array_length(v.document->'voice'->'avoid_phrases_th') as คำต้องห้าม
from   brand_dna_versions v
join   brands b on b.id = v.brand_id
where  v.status = 'active';

\echo ''
\echo '=== pointer ที่ชี้ไป ERPNext (ต้องตรงกับของจริง) ==='
select v.document->'offer'->>'price_source' as price_source,
       v.document->'offer'->>'stock_source' as stock_source
from   brand_dna_versions v
where  v.status = 'active';
