-- 010_escalation_event.sql — บันทึก "ทำไมถึงส่งต่อคน"
--
-- ปัญหาที่เจอตอนรันจริง 12 ก.ย. 2026:
--   AgentResult มีช่อง escalate อยู่ แต่ orchestrator ไม่เคยเขียนลง DB
--   เหตุผลการส่งต่อคนจึงหายไปทั้งหมด คิวรอคนตอบต้องเดาจาก rule.matched ล่าสุด
--   ซึ่งให้คำตอบผิด (ลูกค้าที่เคยทักทายไว้ จะขึ้นเหตุผลว่า "ทักทาย" ตลอดไป)

insert into event_types (type, description, pii_level, retain_days) values
  ('conversation.escalated', 'ส่งต่อให้คนตอบ พร้อมเหตุผล', 'low', null)
on conflict (type) do nothing;
