# บทที่ 7 — Embeddings และ Vector Search

⏱ ประมาณ 4 ชั่วโมง

## เป้าหมาย
- [ ] เข้าใจว่า embedding คืออะไร และทำไมถึงค้นหา "ตามความหมาย" ได้
- [ ] คำนวณ cosine similarity เองได้
- [ ] สร้าง embedding ภาษาไทยด้วยโมเดลฟรีที่รันในเครื่อง
- [ ] เก็บและค้นข้อมูลด้วย vector database (Chroma)
- [ ] รู้จัก hybrid search และ reranking

---

## 1. ปัญหาของการค้นด้วย keyword

คู่มือร้านมีประโยคว่า "**สามารถคืนสินค้าได้ภายใน 7 วัน**"
แต่ลูกค้าพิมพ์ถามว่า "**ซื้อไปแล้วไม่ชอบ ขอเงินคืนได้ไหม**"

การค้นด้วย keyword จะหาไม่เจอ เพราะไม่มีคำไหนตรงกันเลย
เราต้องการการค้นหาที่เข้าใจว่า "ขอเงินคืน" มีความหมายใกล้กับ "คืนสินค้า"

---

## 2. Embedding = พิกัดของความหมาย

**Embedding** คือการแปลงข้อความเป็น **เวกเตอร์ของตัวเลข** (เช่น 384 หรือ 1024 มิติ)
โดยข้อความที่ความหมายใกล้กัน จะได้เวกเตอร์ที่อยู่ใกล้กันในปริภูมินั้น

```
"คืนสินค้าได้ใน 7 วัน"     → [0.12, -0.53, 0.88, ...]  ┐
"ขอเงินคืนได้ไหม"          → [0.10, -0.49, 0.91, ...]  ┘ ใกล้กัน ✅
"ร้านเปิด 9 โมงเช้า"        → [-0.71, 0.33, 0.02, ...]    ไกล ❌
```

> 💡 **เทียบกับวิศวคอม:** เหมือน hash function ที่ **ข้อมูลคล้ายกันได้ค่าที่ใกล้กัน**
> (hash ทั่วไปทำตรงข้าม คือเปลี่ยน input นิดเดียว ค่าก็ต่างกันมาก)

### วัดความใกล้ด้วย Cosine Similarity
$$\text{cos}(\vec{a}, \vec{b}) = \frac{\vec{a} \cdot \vec{b}}{|\vec{a}||\vec{b}|}$$

- ค่าเข้าใกล้ 1 = ทิศทางเดียวกัน (ความหมายใกล้กัน)
- ค่าเข้าใกล้ 0 = ไม่เกี่ยวข้องกัน

```python
import numpy as np

def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
```

นี่คือเรื่อง linear algebra ที่เรียนมาตอนปี 1 ครับ ได้ใช้จริงแล้ว

---

## 3. สร้าง Embedding ภาษาไทย (ฟรี รันในเครื่อง)

Claude API **ไม่มี** endpoint สำหรับ embedding จึงต้องใช้โมเดลอื่น

| ตัวเลือก | ข้อดี | ข้อเสีย |
|---|---|---|
| `intfloat/multilingual-e5-small` | ฟรี, เล็ก (~500MB), รองรับภาษาไทย | คุณภาพระดับกลาง |
| `BAAI/bge-m3` | ฟรี, ภาษาไทยดีมาก | ใหญ่ (~2GB), ช้าบน CPU |
| Voyage AI (API เสียเงิน) | คุณภาพสูง, Anthropic แนะนำ | มีค่าใช้จ่าย |

ในบทเรียนนี้จะใช้ **multilingual-e5-small** เพราะเครื่องทั่วไปรันได้

```powershell
pip install sentence-transformers chromadb numpy
```

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-small")   # ครั้งแรกจะดาวน์โหลดโมเดล

# โมเดลตระกูล e5 ต้องใส่ prefix: "query: " สำหรับคำถาม และ "passage: " สำหรับเอกสาร
docs = [
    "สามารถคืนสินค้าได้ภายใน 7 วัน หากสินค้ายังไม่ได้แกะกล่อง",
    "ร้านเปิดทำการทุกวัน 9:00-18:00 น. ยกเว้นวันอาทิตย์",
    "รับประกันเมาส์และคีย์บอร์ด 1 ปี",
    "จัดส่งฟรีเมื่อซื้อครบ 1,000 บาท",
]
doc_vecs = model.encode([f"passage: {d}" for d in docs], normalize_embeddings=True)

query = "ซื้อไปแล้วไม่ชอบ ขอเงินคืนได้ไหม"
q_vec = model.encode(f"query: {query}", normalize_embeddings=True)

scores = doc_vecs @ q_vec          # normalize แล้ว dot product = cosine
for score, doc in sorted(zip(scores, docs), reverse=True):
    print(f"{score:.3f}  {doc}")
```

ผลลัพธ์ที่คาดว่าจะได้: เอกสารเรื่องการคืนสินค้าได้คะแนนสูงสุด แม้ไม่มีคำไหนตรงกับคำถามเลย

---

## 4. Vector Database

ถ้ามีเอกสาร 4 ชิ้น ใช้ numpy ก็พอ แต่ถ้ามี 1 ล้านชิ้น การเทียบทุกชิ้นจะช้าเกินไป
**Vector DB** ใช้ดัชนีพิเศษ (เช่น HNSW) ที่ค้นหาเวกเตอร์ใกล้เคียงได้เร็วมาก (แลกกับความแม่นยำเล็กน้อย เรียกว่า approximate nearest neighbor)

| ตัวเลือก | เหมาะกับ |
|---|---|
| **Chroma** | เรียนรู้และโปรเจกต์เล็ก เป็นไฟล์ในเครื่อง ไม่ต้องตั้งเซิร์ฟเวอร์ |
| **pgvector** (Postgres) | production ที่ใช้ Postgres อยู่แล้ว (**แนะนำสำหรับงานจริง**) |
| **Qdrant / Weaviate / Milvus** | ระบบใหญ่ที่ต้องการฟีเจอร์เฉพาะทาง |

> 💡 ERPNext ใช้ MariaDB ส่วน vector DB ของ AI ให้แยกไว้ต่างหาก (Chroma หรือ Postgres)

### ใช้ Chroma
```python
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-small")
db = chromadb.PersistentClient(path="./chroma_db")          # เก็บเป็นไฟล์
col = db.get_or_create_collection("shop_docs", metadata={"hnsw:space": "cosine"})

def add_docs(docs: list[dict]):
    col.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        embeddings=model.encode([f"passage: {d['text']}" for d in docs],
                                normalize_embeddings=True).tolist(),
        metadatas=[{"source": d["source"]} for d in docs],
    )

def search(query: str, k: int = 3) -> list[dict]:
    q = model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=[q], n_results=k)
    return [
        {"text": t, "source": m["source"], "distance": d}
        for t, m, d in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]

add_docs([
    {"id": "p1", "text": "สามารถคืนสินค้าได้ภายใน 7 วัน", "source": "นโยบาย.pdf#1"},
    {"id": "p2", "text": "รับประกันเมาส์ 1 ปี", "source": "นโยบาย.pdf#2"},
])
print(search("ขอเงินคืน"))
```

**Metadata สำคัญมาก:** ใช้เก็บแหล่งที่มา (ไฟล์, หน้า), วันที่ และสิทธิ์การเข้าถึง
ใช้ทั้งอ้างอิงแหล่งที่มาในคำตอบ และกรองผลลัพธ์ เช่น `col.query(..., where={"source": "นโยบาย.pdf#1"})`

---

## 5. Hybrid Search = Keyword + Vector

การค้นด้วย vector อย่างเดียวมีจุดอ่อน: **ชื่อเฉพาะ รหัสสินค้า และตัวเลข**
เช่น ค้น "SKU-A1029" ด้วย vector อาจได้ "SKU-A1092" มาแทน เพราะความหมายดูใกล้กัน

**วิธีแก้:** ค้นทั้งสองแบบ แล้วรวมผลลัพธ์

| วิธี | เก่งเรื่อง |
|---|---|
| **BM25** (keyword) | คำตรงตัว, รหัส, ชื่อเฉพาะ |
| **Vector** | ความหมาย, คำพ้อง, ถามอ้อมๆ |

```python
# รวมผลด้วย Reciprocal Rank Fusion (RRF) เป็นวิธีง่ายที่ได้ผลดี
def rrf(rank_lists: list[list[str]], k: int = 60) -> list[str]:
    scores = {}
    for ranks in rank_lists:
        for i, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + i + 1)
    return sorted(scores, key=scores.get, reverse=True)

final = rrf([bm25_ids, vector_ids])
```

⚠️ **ภาษาไทยกับ BM25:** ภาษาไทยไม่เว้นวรรคระหว่างคำ ต้องตัดคำก่อน (บทที่ 8)

---

## 6. Reranking

การค้นรอบแรกเน้น **ความเร็ว** จึงดึงผู้สมัครมาเยอะ (เช่น 30 ชิ้น)
จากนั้นใช้โมเดลที่ช้ากว่าแต่แม่นกว่าจัดอันดับใหม่ แล้วเลือกมาใช้แค่ 5 ชิ้น

```
query ─▶ [Hybrid search: 30 ชิ้น] ─▶ [Reranker: จัดอันดับใหม่] ─▶ top 5 ─▶ LLM
```

ตัวเลือกของ reranker:
- **Cross-encoder** เช่น `BAAI/bge-reranker-v2-m3` (ฟรี รองรับหลายภาษา)
- **ใช้ Claude จัดอันดับเอง:** ส่งผู้สมัคร 30 ชิ้นแล้วให้เลือก 5 ชิ้นที่เกี่ยวข้องที่สุด (แพงกว่า แต่ไม่ต้องลงโมเดลเพิ่ม)

---

## 7. การวัดผลการค้นหา

อย่าวัดจากความรู้สึก ให้สร้างชุดทดสอบ (คำถาม → เอกสารที่ถูกต้อง)

| Metric | ความหมาย |
|---|---|
| **Recall@k** | ใน top k มีเอกสารที่ถูกต้องอยู่ไหม (สำคัญที่สุดสำหรับ RAG) |
| **MRR** | เอกสารที่ถูกต้องอยู่อันดับที่เท่าไร (ยิ่งอยู่อันดับต้นยิ่งดี) |

```python
TESTS = [("ขอเงินคืนได้ไหม", "p1"), ("เมาส์รับประกันกี่ปี", "p2")]
hits = sum(expected in [r["id"] for r in search_with_ids(q, k=3)] for q, expected in TESTS)
print(f"Recall@3 = {hits/len(TESTS):.0%}")
```

---

## สรุปบทที่ 7
1. Embedding แปลงข้อความเป็นเวกเตอร์ ความหมายใกล้กันจะได้เวกเตอร์ใกล้กัน
2. ใช้ cosine similarity วัดความใกล้
3. ภาษาไทยใช้โมเดล multilingual ได้ เช่น e5 หรือ bge-m3 ซึ่งฟรีและรันในเครื่องได้
4. Vector DB ช่วยให้ค้นเร็ว เก็บ metadata ไว้ใช้อ้างอิงและกรองผล
5. Hybrid (BM25 + vector) และ reranking ช่วยเพิ่มความแม่นยำ
6. วัดผลด้วย Recall@k

---

## แบบฝึกหัด
1. รันตัวอย่างในหัวข้อที่ 3 แล้วเพิ่มเอกสาร 10 ชิ้น พร้อมคำถาม 10 ข้อที่ถามแบบอ้อมๆ
2. คำนวณ Recall@1 และ Recall@3
3. ลองค้นด้วยรหัสสินค้า (เช่น "SKU-A1029") ดูว่า vector search พลาดไหม
4. ลองโมเดล `BAAI/bge-m3` (ไม่ต้องใส่ prefix) แล้วเทียบ Recall กับ e5
5. **Capstone:** รวบรวมเอกสารของ "ร้าน" คุณ (นโยบาย, FAQ, คู่มือสินค้า) อย่างน้อย 5 หน้า เพื่อใช้ในบทที่ 8

✅ ไปต่อที่ [บทที่ 8](../08-rag-thai/lesson.md)
