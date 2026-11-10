-- 000_extensions.sql — รันก่อนทุกไฟล์
-- PostgreSQL 16+ (แยกจาก MariaDB ของ ERPNext โดยตั้งใจ — ดู README)

create extension if not exists pgcrypto;   -- gen_random_uuid()
create extension if not exists vector;     -- pgvector สำหรับ knowledge_chunks
create extension if not exists pg_trgm;    -- ค้นหาข้อความไทยแบบ fuzzy

-- ขนาด embedding: ตั้งไว้ที่ 1536 (OpenAI text-embedding-3-small / Voyage)
-- ถ้าเปลี่ยนโมเดล ต้องแก้ที่ knowledge_chunks.embedding และ reindex ใหม่ทั้งหมด
