-- 06-seed-item-aliases.sql — ชื่อไทยของสินค้า เชื่อมกับรหัสจริงใน ERPNext
--
-- ปัญหาที่เจอตอนทดสอบ 12 ก.ย. 2026:
--   ชื่อสินค้าใน ERPNext เป็นภาษาอังกฤษ ("Onato Tomato Juice 100% 75ml")
--   ลูกค้าไทยพิมพ์ "น้ำมะเขือเทศ" แล้วค้นไม่เจอ → AI ตอบว่าไม่มีสินค้า ทั้งที่มี 76 ขวด
--
-- ตารางนี้คือชั้นแปลภาษา: ลูกค้าพูดยังไง → รหัสสินค้าอะไร
-- ใช้ pg_trgm ค้นแบบใกล้เคียงได้ พิมพ์ผิดนิดหน่อยก็ยังเจอ
--
-- ⚠️ คำเรียกด้านล่างผมเดาจากชื่ออังกฤษ — ต้องให้คนที่ขายจริงตรวจก่อนใช้กับลูกค้า
--    โดยเฉพาะคำที่ลูกค้าเรียกกันเองจริงๆ ซึ่งมีแต่คุณที่รู้

insert into knowledge_docs (brand_id, title, category, body, erp_item_code, status, source_type)
select b.id, t.title, 'product', t.body, t.code, 'draft', 'manual'
from   brands b,
       (values
         ('ONATO-JUICE-75',    'น้ำมะเขือเทศ Onato 75ml',
          'น้ำมะเขือเทศ · น้ำมะเขือเทศ 100% · โอนาโตะ · onato · น้ำมะเขือเทศขวดเล็ก · น้ำผัก'),
         ('ONATO-BOXSET-6',    'Onato เซ็ต 6 ขวด',
          'เซ็ต 6 ขวด · ยกกล่อง · แพ็ค 6 · กล่อง 6 ขวด · ซื้อยกลัง'),
         ('ONATO-GIFTSET',     'Onato ชุดของขวัญ',
          'ชุดของขวัญ · เซ็ตของฝาก · กระเช้า · ของฝาก · ของขวัญ'),
         ('ONATO-MONTHLY',     'Onato แพ็กรายเดือน',
          'แพ็กรายเดือน · ชุดดื่มทั้งเดือน · สมัครรายเดือน'),
         ('TOMATO-TABLET-50',  'มะเขือเทศอัดเม็ด 100 เม็ด',
          'มะเขือเทศเม็ด · แบบเม็ด · อัดเม็ด · เม็ดมะเขือเทศ · ไม่ชอบดื่มน้ำ'),
         ('BLACK-TOMATO-90',   'มะเขือเทศดำ Black Tomato Plus',
          'มะเขือเทศดำ · black tomato · แบล็คโทเมโท'),
         ('SERUM-BRIGHT-20',   'เซรั่มผิวกระจ่างใส 20g',
          'เซรั่ม · เซรั่มหน้าใส · serum · น้ำตบ'),
         ('AMANA-CREAM-30',    'ครีม AMANA 30g',
          'ครีม · ครีมทาหน้า · อมานา · amana · ครีมบำรุง'),
         ('LOTION-200',        'โลชั่นบำรุงผิว 200ml',
          'โลชั่น · ครีมทาตัว · lotion · บำรุงผิวกาย'),
         ('SUNSCREEN-200',     'ครีมกันแดด 200ml',
          'กันแดด · ครีมกันแดด · sunscreen · ทากันแดด'),
         ('UV-PROTECT-20',     'UV Protection 20g',
          'กันแดดหลอดเล็ก · ยูวี · uv · กันยูวี'),
         ('SOAP-TOMATO-HONEY', 'สบู่มะเขือเทศน้ำผึ้ง 75ml',
          'สบู่ · สบู่มะเขือเทศ · สบู่น้ำผึ้ง · สบู่ล้างหน้า · มาส์ก'),
         ('ESSENCE-TOMATO',    'เอสเซ้นส์มะเขือเทศ',
          'เอสเซ้นส์มะเขือเทศ · essence มะเขือเทศ'),
         ('ESSENCE-CUCUMBER',  'เอสเซ้นส์แตงกวา',
          'เอสเซ้นส์แตงกวา · แตงกวา · cucumber')
       ) as t(code, title, body)
where  b.slug = 'ona-healthy'
  and  not exists (select 1 from knowledge_docs k
                    where k.brand_id = b.id and k.erp_item_code = t.code
                      and k.category = 'product');

-- ดัชนีสำหรับค้นชื่อไทยแบบใกล้เคียง (พิมพ์ผิดนิดหน่อยยังเจอ)
create index if not exists knowledge_docs_body_trgm
  on knowledge_docs using gin (body gin_trgm_ops);
create index if not exists knowledge_docs_title_trgm
  on knowledge_docs using gin (title gin_trgm_ops);

\echo ''
\echo '=== ชื่อไทยที่ผูกกับรหัสสินค้าแล้ว (สถานะ draft รอคนตรวจ) ==='
select erp_item_code, title, status from knowledge_docs
where category = 'product' order by erp_item_code;
