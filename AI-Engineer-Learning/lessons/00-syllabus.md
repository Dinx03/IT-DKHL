# หลักสูตร AI Engineer 101 (สอนโดย Claude)

**เป้าหมายปลายทาง (Capstone):** ระบบบริหารธุรกิจที่ประกอบด้วย 3 ส่วน
**ERPNext (ข้อมูลธุรกิจ) + Web App (หน้าจอผู้ใช้) + AI Agent (ผู้ช่วยบริหาร)**

ทุกบทจะมีโค้ดที่ต่อยอดไปเป็น capstone เรียนจบแล้วจึงได้ portfolio ชิ้นใหญ่ 1 ชิ้นทันที

## รูปแบบแต่ละบท
1. **สไลด์ (Canva):** อธิบายแนวคิดพร้อมภาพ
2. **lesson.md:** เนื้อหาละเอียดสำหรับอ่านทบทวน
3. **lab/:** โค้ดให้รันเองและแก้เอง
4. **exercises.md:** โจทย์ท้ายบท ทำเสร็จแล้วส่งให้ Claude ตรวจ

---

## Module A — พื้นฐาน LLM
| บท | หัวข้อ | ผลลัพธ์ที่ได้ |
|---|---|---|
| 1 | LLM คืออะไร + เรียก API ครั้งแรก | สคริปต์คุยกับ Claude ได้ และเข้าใจเรื่อง token กับค่าใช้จ่าย |
| 2 | Prompt engineering + Structured output | ได้ JSON ที่ validate ด้วย Pydantic |
| 3 | Tool use (function calling) | Claude เรียกฟังก์ชัน Python ของเราได้ |

## Module B — Agent & Harness
| บท | หัวข้อ | ผลลัพธ์ที่ได้ |
|---|---|---|
| 4 | เขียน agent loop เองจากศูนย์ | mini-agent ประมาณ 100 บรรทัด |
| 5 | Context management + Memory | agent ที่ทำงานยาวๆ ได้โดยไม่หลุด context |
| 6 | Safety: permission, prompt injection | agent ที่ขอยืนยันก่อนทำสิ่งอันตราย |

## Module C — RAG (ความรู้ขององค์กร)
| บท | หัวข้อ | ผลลัพธ์ที่ได้ |
|---|---|---|
| 7 | Embeddings + Vector search | ค้นเอกสารตามความหมายได้ |
| 8 | RAG กับเอกสารภาษาไทย | Q&A จากคู่มือบริษัท พร้อมแหล่งอ้างอิง |

## Module D — เชื่อม ERPNext
| บท | หัวข้อ | ผลลัพธ์ที่ได้ |
|---|---|---|
| 9 | ERPNext REST API | อ่านและเขียนข้อมูลสต็อก ลูกค้า และใบขายด้วย Python |
| 10 | MCP: สร้าง MCP server | ERPNext MCP server ที่ Claude เรียกใช้ได้ |

## Module E — Web App + Production
| บท | หัวข้อ | ผลลัพธ์ที่ได้ |
|---|---|---|
| 11 | FastAPI + Chat UI (streaming) | เว็บแอปคุยกับ agent |
| 12 | Evals, Logging, Deploy | ระบบที่วัดผลได้และ deploy ได้ |

## Capstone — "ERPNext AI Business Assistant"
- Dashboard บนเว็บ + แชทสั่งงานด้วยภาษาไทย
- ถามได้ เช่น "สินค้าไหนใกล้หมด", "ยอดขายเดือนนี้เทียบเดือนก่อน", "ร่างใบเสนอราคาให้ลูกค้า A"
- มี RAG จากคู่มือบริษัท, มี permission (คนต้องยืนยันก่อนเขียนข้อมูล) และมี eval

---

## สารบัญ (ติ๊กเมื่อเรียนจบ)
- [ ] บทที่ 1 — [LLM คืออะไร + เรียก API ครั้งแรก](01-llm-basics/lesson.md) ← **เริ่มตรงนี้**
- [ ] บทที่ 2 — [Prompt Engineering + Structured Output](02-prompt-structured-output/lesson.md)
- [ ] บทที่ 3 — [Tool Use (Function Calling)](03-tool-use/lesson.md)
- [ ] บทที่ 4 — [เขียน Agent Loop เอง](04-agent-loop/lesson.md) ⭐
- [ ] บทที่ 5 — [Context Management + Memory](05-context-memory/lesson.md)
- [ ] บทที่ 6 — [ความปลอดภัย: Permission, Prompt Injection](06-safety/lesson.md) ⭐
- [ ] บทที่ 7 — [Embeddings + Vector Search](07-embeddings-vector-search/lesson.md)
- [ ] บทที่ 8 — [RAG กับเอกสารภาษาไทย](08-rag-thai/lesson.md) ⭐
- [ ] บทที่ 9 — [เชื่อม ERPNext REST API](09-erpnext-api/lesson.md)
- [ ] บทที่ 10 — [MCP: ERPNext MCP Server](10-mcp/lesson.md)
- [ ] บทที่ 11 — [Web App: FastAPI + Chat UI](11-web-app/lesson.md)
- [ ] บทที่ 12 — [Evals, Observability, Cost, Deploy](12-evals-production/lesson.md) ⭐
- [ ] Capstone — [ERPNext AI Business Assistant + เตรียมสัมภาษณ์](13-capstone/README.md)

📖 [อภิธานศัพท์](glossary.md) — เปิดดูเมื่อเจอคำที่ไม่คุ้น

⭐ = บทที่สำคัญเป็นพิเศษ ควรทำแบบฝึกหัดให้ครบ

## เวลาเรียนโดยประมาณ
- เนื้อหา 12 บท: ประมาณ 55–60 ชั่วโมง (ถ้าเรียนวันละ 2 ชั่วโมง จะใช้เวลาราว 1 เดือน)
- Capstone: 3–4 สัปดาห์
- **รวมประมาณ 2–3 เดือน** แล้วจะมี portfolio พร้อมสมัครงาน

## ค่าใช้จ่าย
- เนื้อหาทั้งหมดในโฟลเดอร์นี้: **ฟรี** อ่านได้แม้ไม่มีอินเทอร์เน็ต
- เครื่องมือ (Python, FastAPI, Chroma, pythainlp, โมเดล embedding): **ฟรี**
- **สิ่งเดียวที่มีค่าใช้จ่ายคือ Claude API** สำหรับรันแล็บ คาดว่าประมาณหลักร้อยบาทตลอดหลักสูตร
  ถ้าเปลี่ยน `MODEL` ใน `common.py` เป็น `claude-haiku-4-5` จะถูกลงอีกมาก
