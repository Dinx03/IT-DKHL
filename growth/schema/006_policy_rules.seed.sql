-- 006_policy_rules.seed.sql — กฎชุดเริ่มต้นของ Reach Guard
-- ทุกข้อมี source_url ชี้หน้าทางการ — ถ้าตรวจแล้วบล็อกโพสต์ ต้องอธิบายได้ว่าอ้างจากไหน
-- ที่มา: platform-visibility-notes.md (ตรวจจากเว็บทางการ 12 ก.ย. 2026)

insert into policy_rules
  (id, platforms, category, severity, detector_type, detector, message_th, fix_hint_th, source_url, effective_from)
values

-- ── Meta: Engagement Bait 4 รูปแบบ ───────────────────────────
('meta.bait.react', '{facebook,instagram}', 'engagement_bait', 'block', 'keyword',
 '{"any":["กดไลก์ถ้า","กดหัวใจถ้า","กดว้าวถ้า","กดโกรธถ้า","ถูกใจถ้าคุณ"]}',
 'ล่อให้แสดงความรู้สึก — Meta ลดการเผยแพร่ทั้งเพจ ไม่ใช่แค่โพสต์นี้',
 'ตัดประโยคที่ขอปฏิกิริยาออก เปลี่ยนเป็นคำถามปลายเปิดที่คนอยากตอบเอง',
 'https://www.facebook.com/business/help/259911614709806', current_date),

('meta.bait.comment', '{facebook,instagram}', 'engagement_bait', 'block', 'keyword',
 '{"any":["คอมเมนต์คำว่า","พิมพ์คำว่า","ตอบใต้โพสต์ว่า","คอมเมนต์เลข"]}',
 'ล่อให้คอมเมนต์คำตอบเฉพาะ — เข้าข่าย engagement bait',
 'ถามคำถามที่คนตอบได้หลากหลาย แทนการสั่งให้พิมพ์คำตายตัว',
 'https://www.facebook.com/business/help/259911614709806', current_date),

('meta.bait.share', '{facebook,instagram}', 'engagement_bait', 'block', 'keyword',
 '{"any":["แชร์ต่อให้เพื่อน","ช่วยแชร์หน่อย","แชร์เลย","แท็กเพื่อน"]}',
 'ล่อให้แชร์/แท็ก — เข้าข่าย engagement bait',
 'เอาออก ให้คุณค่าของเนื้อหาทำงานเอง',
 'https://www.facebook.com/business/help/259911614709806', current_date),

('meta.bait.vote', '{facebook,instagram}', 'engagement_bait', 'block', 'keyword',
 '{"any":["โหวตเลย","เลือกข้อไหน กดตรงนี้","โหวตให้หน่อย"]}',
 'ล่อให้โหวต — เข้าข่าย engagement bait',
 'ใช้ฟีเจอร์โพลของแพลตฟอร์มแทนการขอโหวตในแคปชั่น',
 'https://www.facebook.com/business/help/259911614709806', current_date),

-- ── IG: กลุ่มสุขภาพ/ความงาม — เสี่ยงสูงสุดสำหรับ ONA Healthy ──
('ig.health_claim', '{instagram,facebook}', 'health_claim', 'block', 'llm',
 '{"prompt_key":"health_claim_v1","threshold":60,"rubric":["เคลมรักษา/ป้องกันโรค","การันตีผลลัพธ์","ก่อน-หลังเรื่องน้ำหนัก","เชียร์ศัลยกรรมเชิงบวกเกินจริง"]}',
 'เข้าข่ายเนื้อหาที่ IG ไม่แนะนำ (ขายอาหารเสริม/ลดน้ำหนัก/เคลมผลลัพธ์) จะไม่ขึ้น Explore และ Reels กับคนที่ไม่ได้ตามอยู่',
 'เปลี่ยนจาก "ผลลัพธ์" เป็น "ส่วนประกอบและวิธีใช้" และใส่ disclaimer จาก claims_policy',
 'https://help.instagram.com/313829416281232/', current_date),

('ig.aigc_person', '{instagram}', 'aigc_label', 'block', 'structural',
 '{"check":"media_has_ai_realistic_person","requires":"aigc_labeled = true"}',
 'มีรูปคน AI สมจริงแต่ยังไม่ติดป้าย AI-generated — IG ตัดสิทธิ์ถูกแนะนำถ้าโพสต์ซ้ำๆ โดยไม่เปิดเผย',
 'ติดป้าย AI-generated ในโพสต์ หรือเปลี่ยนไปใช้รูปถ่ายจริง',
 'https://help.instagram.com/313829416281232/', current_date),

-- ── TikTok ───────────────────────────────────────────────────
('tiktok.aigc_label', '{tiktok}', 'aigc_label', 'block', 'structural',
 '{"check":"media_has_ai_realistic_scene_or_person","requires":"aigc_labeled = true"}',
 'TikTok บังคับติดป้าย AIGC สำหรับฉาก/คนที่ดูสมจริง ไม่ติด = อาจถูกลบ จำกัด หรือแบนบัญชี',
 'เปิดสวิตช์ AI-generated content ตอนอัปโหลด',
 'https://www.tiktok.com/community-guidelines/en/integrity-authenticity', current_date),

('tiktok.guidelines_update', '{tiktok}', 'prohibited_topic', 'info', 'structural',
 '{"check":"always"}',
 'TikTok อัปเดต Community Guidelines 24 ก.ย. 2026 — ทบทวนกฎชุดนี้หลังวันนั้น',
 'ตรวจหน้าทางการแล้วเพิ่ม/แก้กฎในตาราง policy_rules',
 'https://www.tiktok.com/community-guidelines/en/integrity-authenticity', '2026-09-24'),

-- ── ข้ามแพลตฟอร์ม ────────────────────────────────────────────
('all.unoriginal', '{*}', 'unoriginal', 'warn', 'llm',
 '{"prompt_key":"originality_v1","threshold":70,"compare_against":"last_90_days_same_brand"}',
 'เนื้อหาใกล้เคียงของเดิมมาก — Meta และ TikTok ทั้งคู่ตัดสิทธิ์แนะนำเนื้อหาที่รียูสโดยไม่เพิ่มอะไรใหม่',
 'เพิ่มมุมมอง ข้อมูล หรือตัวอย่างใหม่อย่างน้อย 1 อย่าง',
 'https://help.instagram.com/313829416281232/', current_date),

('all.frequency', '{*}', 'frequency', 'warn', 'structural',
 '{"check":"posts_per_day_exceeds","source":"brand_dna:/channel_prefs/max_posts_per_day"}',
 'โพสต์ถี่เกินที่ตั้งไว้ — โพสต์ที่ 2,3,4 จากบัญชีเดียวในฟีดเดียวถูกลดคะแนนทบต้น (author diversity decay)',
 'เลื่อนไปวันถัดไป หรือรวมเป็นโพสต์เดียว',
 'https://github.com/xai-org/x-algorithm', current_date),

('x.engagement_ask', '{x}', 'engagement_bait', 'block', 'keyword',
 '{"any":["รีพลายแล้วฟอลโลว์กลับ","follow back","RT แล้วจะ"]}',
 'ขอ engagement ตรงๆ ซ้ำหลายครั้งบน X เสี่ยงถูกถอดจากโปรแกรมรายได้ครีเอเตอร์',
 'เอาออกทั้งหมด',
 'https://help.x.com/en/rules-and-policies/authenticity', current_date);
