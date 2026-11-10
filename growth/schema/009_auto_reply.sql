-- 009_auto_reply.sql — ชั้นกฎตายตัวที่ทำงานก่อน AI เสมอ
--
-- ทำไมต้องมีชั้นนี้ ทั้งที่มี AI แล้ว:
--   1. ถูก  — คำถามซ้ำๆ อย่าง "เปิดกี่โมง" ไม่ควรเสียค่าโมเดลทุกครั้ง
--   2. เร็ว — ตอบได้ในหลักมิลลิวินาที ไม่ต้องรอ API
--   3. คุมได้ — คำตอบเรื่องราคา/เงื่อนไข ต้องเป๊ะเหมือนเดิมทุกครั้ง ไม่ให้โมเดลเรียบเรียงเอง
--   4. ปลอดภัย — บางคำ (แพ้ · คืนเงิน · ร้องเรียน) ต้องถึงคนทันที ห้ามให้ AI จัดการ
--
-- ลำดับการทำงาน:  ข้อความเข้า → กฎที่นี่ → ถ้าไม่เข้ากฎไหนเลย → Concierge (AI)

create table auto_reply_rules (
  id             uuid primary key default gen_random_uuid(),
  brand_id       uuid not null references brands(id) on delete cascade,
  name           text not null,
  -- เลขน้อย = ตรวจก่อน · กฎส่งต่อคนควรมี priority ต่ำสุดเสมอ
  priority       integer not null default 100,
  channels       text[] not null default '{*}',

  match_type     text not null check (match_type in ('keyword', 'regex')),
  -- keyword: {"any": ["เปิดกี่โมง","กี่โมง"], "all": [], "none": ["ปิด"]}
  -- regex:   {"pattern": "...", "flags": "i"}
  match          jsonb not null,

  action         text not null default 'reply'
                 check (action in ('reply', 'escalate', 'ignore')),
  reply_th       text,
  -- เหตุผลที่ส่งต่อคน — โชว์ให้แอดมินเห็นในกล่องข้อความ
  escalate_note_th text,

  -- true = ตอบแล้วจบ ไม่ต้องดูกฎถัดไปและไม่ต้องเรียก AI
  stop_processing boolean not null default true,
  enabled        boolean not null default true,
  hit_count      bigint not null default 0,
  created_at     timestamptz not null default now(),

  constraint reply_needs_text
    check (action <> 'reply' or (reply_th is not null and length(reply_th) > 0))
);

create index on auto_reply_rules (brand_id, enabled, priority);

comment on table auto_reply_rules is
  'ทำงานก่อน Concierge เสมอ — ดู growth/agents/auto_reply.py';


-- ─────────────────────────────────────────────────────────────
-- กฎเริ่มต้นของ ONA Healthy
-- ─────────────────────────────────────────────────────────────

insert into auto_reply_rules
  (brand_id, name, priority, match_type, match, action, reply_th, escalate_note_th)
select b.id, t.name, t.pri, t.mtype, t.m::jsonb, t.act, t.reply, t.note
from   brands b,
       (values
         -- ── ส่งต่อคนทันที (priority ต่ำสุด ตรวจก่อนทุกกฎ) ───────────
         ('แพ้สินค้า', 1, 'keyword',
          '{"any":["แพ้","ผื่น","คัน","บวม","แสบ","ระคายเคือง"]}',
          'escalate', null,
          'ลูกค้าแจ้งอาการแพ้ — ต้องมีคนตอบเอง ห้ามให้ AI ตอบเรื่องอาการ'),

         ('ขอคืนเงิน/ร้องเรียน', 2, 'keyword',
          '{"any":["คืนเงิน","คืนสินค้า","ร้องเรียน","ไม่พอใจ","ของเสีย","ของแตก","ผิดล็อต"]}',
          'escalate', null,
          'เรื่องคืนเงินหรือร้องเรียน — ต้องมีคนตัดสินใจ'),

         ('ถามเรื่องโรค/ยา', 3, 'keyword',
          '{"any":["เบาหวาน","ความดัน","มะเร็ง","ตั้งครรภ์","ให้นม","กินยา","โรคประจำตัว","รักษา"]}',
          'escalate', null,
          'ถามเรื่องสุขภาพเฉพาะบุคคล — ห้าม AI ตอบ (ผิดกฎ อย. และอันตราย)'),

         ('ขอเป็นตัวแทน/ราคาส่ง', 4, 'keyword',
          '{"any":["ตัวแทน","ขายส่ง","ราคาส่ง","dealer","สมัครตัวแทน","ซื้อเยอะ"]}',
          'escalate', null,
          'เรื่องราคาส่งและตัวแทน — เป็นการต่อรอง ต้องให้คนคุย'),

         ('ขอใบกำกับภาษี', 5, 'keyword',
          '{"any":["ใบกำกับภาษี","ใบเสร็จ","หักภาษี","vat","นิติบุคคล"]}',
          'escalate', null,
          'เอกสารภาษี — ต้องให้คนจัดการ'),

         -- ── ตอบอัตโนมัติได้ ─────────────────────────────────────
         ('ทักทาย', 50, 'keyword',
          '{"any":["สวัสดี","หวัดดี","ดีครับ","ดีค่ะ","hello","hi"]}',
          'reply',
          'สวัสดีค่ะ ONA Healthy ยินดีให้บริการค่ะ 🍅'||chr(10)||
          'สนใจสินค้าตัวไหน หรืออยากให้ช่วยแนะนำบอกได้เลยนะคะ',
          null),

         ('ขอบคุณ', 51, 'keyword',
          '{"any":["ขอบคุณ","ขอบใจ","thank"]}',
          'reply',
          'ยินดีค่ะ หากมีอะไรให้ช่วยเพิ่มเติมทักมาได้ตลอดเลยนะคะ',
          null)
       ) as t(name, pri, mtype, m, act, reply, note)
where  b.slug = 'ona-healthy'
  and  not exists (select 1 from auto_reply_rules a
                    where a.brand_id = b.id and a.name = t.name);

-- ⚠️ กฎที่ "ยังเขียนไม่ได้" เพราะต้องรอเนื้อหาจากเจ้าของธุรกิจ:
--    - เวลาทำการ / เวลาตอบแชท
--    - ค่าส่ง และเงื่อนไขส่งฟรี
--    - วิธีชำระเงิน (เลขบัญชี / พร้อมเพย์)
--    - นโยบายคืนสินค้า
--    ทั้งหมดนี้ผูกกับ brand_dna.offer ซึ่งตอนนี้ยังเป็น <ยังไม่ได้เขียน>
--    ห้ามเดาแทนเจ้าของธุรกิจ — ตอบผิดเรื่องเงินเสียหายจริง
