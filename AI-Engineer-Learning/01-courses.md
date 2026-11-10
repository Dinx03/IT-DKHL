# รายการคอร์สแยกตามเฟส

สัญลักษณ์: 🆓 ฟรี · 🎓 มี certificate · 💰 เสียเงิน (ไม่บังคับ)

---

<a id="phase-0"></a>
## เฟส 0 — ปูพื้น (2–3 สัปดาห์)

จบวิศวคอมมาแล้ว เฟสนี้จึงเป็นการ **ทบทวน** ข้ามส่วนที่แน่นอยู่แล้วได้เลย

| หัวข้อ | สิ่งที่ต้องทำได้ |
|---|---|
| Python | function, class, type hints, `async/await`, virtualenv/`uv`, `pip` |
| Git + GitHub | branch, commit, PR, เขียน README |
| HTTP / REST API | เรียก API ด้วย `httpx`/`requests`, อ่าน JSON, เข้าใจ status code |
| FastAPI | สร้าง API endpoint ง่ายๆ ได้ |
| SQL + Postgres | SELECT/JOIN พื้นฐาน |

แหล่งเรียน:
- 🆓 [roadmap.sh – AI Engineer](https://roadmap.sh/ai-engineer) ใช้เป็นแผนที่ภาพรวม คลิกแต่ละหัวข้อจะเจอลิงก์บทเรียน
- 🆓 [roadmap.sh – Python](https://roadmap.sh/python) ใช้ทบทวน Python

**งานส่งท้ายเฟส:** CLI หรือ FastAPI เล็กๆ 1 ตัว ขึ้น GitHub

---

<a id="phase-1"></a>
## เฟส 1 — LLM พื้นฐาน + API (3 สัปดาห์)

| คอร์ส | ประเภท | ทำไมต้องเรียน |
|---|---|---|
| [Anthropic Academy – Claude Platform 101](https://anthropic.skilljar.com/) | 🆓🎓 | ปูพื้นการเรียก API |
| [Anthropic Academy – Building with the Claude API](https://anthropic.skilljar.com/) | 🆓🎓 | ยาว 8+ ชั่วโมง ครอบคลุม tool use, streaming, prompt caching, error handling และ retry **เป็นคอร์สหลักของเฟสนี้** |
| [Anthropic Academy – AI Capabilities and Limitations](https://anthropic.skilljar.com/) | 🆓🎓 | ให้รู้ว่า LLM ทำอะไรได้และทำอะไรไม่ได้ |

หัวข้อที่ต้องเข้าใจ: token, context window, temperature, system prompt, structured output (JSON), tool/function calling, prompt caching และค่าใช้จ่ายต่อ token

**งานส่งท้ายเฟส:** chatbot ที่ตอบคำถามเฉพาะเรื่อง และคืนผลเป็น JSON ที่ validate ด้วย Pydantic

---

<a id="phase-2"></a>
## เฟส 2 — RAG (3 สัปดาห์)

RAG (Retrieval-Augmented Generation) คือการค้นเอกสารที่เกี่ยวข้องมาก่อน แล้วใส่เข้า context ให้โมเดลตอบจากข้อมูลนั้น
**บริษัทไทยต้องการงานประเภทนี้มากที่สุด** เช่น chatbot ตอบคำถามจากเอกสารภายใน

หัวข้อที่ต้องเข้าใจ: embeddings, chunking, vector DB (pgvector, Chroma, Qdrant), hybrid search (BM25 + vector), reranking, citation

แหล่งเรียน:
- 🆓 [roadmap.sh – AI Engineer](https://roadmap.sh/ai-engineer) (หมวด RAG / Embeddings / Vector DB)
- 🆓 [Hamel Husain – Open course on LLMs](https://hamel.dev/blog/posts/course/) มีคลิปจากผู้ใช้งานจริงกว่า 40 ชั่วโมง ให้เลือกดูหมวด RAG
- 🆓 [DeepLearning.AI short courses](https://www.deeplearning.ai/courses) มีคอร์สสั้นเรื่อง RAG / vector DB หลายตัว (1–2 ชั่วโมงต่อคอร์ส)

**ข้อควรระวังเรื่องภาษาไทย:** ภาษาไทยไม่มีช่องว่างระหว่างคำ การตัด chunk และการค้นแบบ keyword จึงต้องใช้ตัวตัดคำ เช่น `pythainlp` ถ้าแก้ปัญหานี้ได้จะเป็นจุดเด่นใน portfolio

**งานส่งท้ายเฟส:** โปรเจกต์ที่ 1–2 ใน [02-projects.md](02-projects.md)

---

<a id="phase-3"></a>
## เฟส 3 — Agents, Tool use, MCP (4 สัปดาห์) ⭐

เฟสนี้ต่อยอดจากเรื่อง agent harness ที่เราคุยกันไว้

| คอร์ส | ประเภท | หมายเหตุ |
|---|---|---|
| [DeepLearning.AI – Agentic AI (Andrew Ng)](https://learn.deeplearning.ai/courses/agentic-ai/lesson/pu5xbv/welcome!) | 🆓🎓 | **เริ่มที่คอร์สนี้** สอน 4 design patterns (reflection, tool use, planning, multi-agent) และเน้นเรื่อง eval กับ error analysis |
| [Hugging Face – AI Agents Course](https://huggingface.co/learn/agents-course/unit0/introduction) | 🆓🎓 | ปูพื้นเรื่อง Thought → Action → Observation และลองใช้ smolagents, LangGraph, LlamaIndex มี final challenge สำหรับรับ certificate |
| [Anthropic Academy – Introduction to Model Context Protocol](https://anthropic.skilljar.com/) | 🆓🎓 | สร้าง MCP server/client ด้วย Python |
| [Anthropic Academy – MCP: Advanced Topics](https://anthropic.skilljar.com/) | 🆓🎓 | sampling, notifications, transport |
| [Hugging Face – MCP Course](https://huggingface.co/learn/mcp-course/en/unit0/introduction) | 🆓🎓 | ทำร่วมกับ Anthropic เน้นลงมือทำ |
| [Anthropic Academy – Introduction to subagents / agent skills](https://anthropic.skilljar.com/) | 🆓🎓 | ใช้ศึกษา harness จริงอย่าง Claude Code |
| [Anthropic Academy – Claude Code in Action](https://anthropic.skilljar.com/) | 🆓🎓 | ใช้ AI ช่วยเขียนโค้ดแบบมืออาชีพ ซึ่งบริษัทเริ่มคาดหวังทักษะนี้แล้ว |
| [roadmap.sh – AI Agents](https://roadmap.sh/ai-agents) | 🆓 | แผนที่ภาพรวมของหัวข้อ agent |

**แบบฝึกที่สำคัญที่สุด:** เขียน agent loop เองด้วย SDK ตรงๆ โดยไม่ใช้ framework ก่อน (ประมาณ 100 บรรทัด) แล้วจึงค่อยไปลอง LangGraph
การเข้าใจว่า framework ทำอะไรอยู่เบื้องหลังคือสิ่งที่ทำให้ตอบคำถามสัมภาษณ์ได้

**งานส่งท้ายเฟส:** โปรเจกต์ที่ 3–4

---

<a id="phase-4"></a>
## เฟส 4 — Evals + Production (3 สัปดาห์)

เฟสนี้คือสิ่งที่แยก **คนทำ demo** ออกจาก **คนที่บริษัทจ้าง**

| หัวข้อ | สิ่งที่ต้องทำได้ |
|---|---|
| Evals | สร้างชุดทดสอบ, ใช้ LLM-as-judge, ทำ error analysis, วัดผลก่อนและหลังแก้ prompt |
| Observability | log/trace ทุกการเรียก LLM (เช่น Langfuse, OpenTelemetry) |
| Deploy | Docker, FastAPI, deploy ขึ้น cloud (Render/Railway/Fly.io/GCP) |
| Cost & latency | prompt caching, streaming, เลือกโมเดลให้เหมาะกับงาน |
| Security | prompt injection, ไม่ hardcode API key, จำกัดสิทธิ์เครื่องมือ |

แหล่งเรียน:
- 🆓 [Hamel Husain – Open course](https://hamel.dev/blog/posts/course/) (หมวด Evals) และ [บล็อกของ Hamel](https://hamel.dev/) ซึ่งมีบทความเรื่อง eval ที่ดีมาก
- 🆓 [Full Stack LLM Bootcamp](https://www.kaggle.com/general/409920) เนื้อหาเก่าบ้าง แต่หลักการ production ยังใช้ได้
- 💰 [AI Evals For Engineers & PMs (Maven)](https://maven.com/parlance-labs/evals) เสียเงิน ไว้เรียนเมื่อมีงานแล้ว

**งานส่งท้ายเฟส:** โปรเจกต์ที่ 5 และเพิ่ม eval กับการ deploy ให้โปรเจกต์ก่อนหน้า

---

## คอร์สเสียเงิน (ไม่บังคับ)

ถ้าอยากเรียนแบบมีคนพาทำตลอดหลักสูตร Udemy มีคอร์สรวมครบชุด ราคาลดบ่อยจนเหลือหลักร้อยบาท:
- 💰 [AI Engineer Bootcamp 2026: LLMs, RAG, AI Agents & Vector DBs](https://www.udemy.com/course/llm-engineering/)
- 💰 [AI Engineer Agentic Track: The Complete Agent & MCP Course](https://www.udemy.com/course/the-complete-agentic-ai-engineering-course/)

> แนะนำให้เรียนของฟรีข้างบนก่อน ของฟรีชุดนี้ครอบคลุมเนื้อหาพอสำหรับการหางานแล้ว

## Roadmap อื่นๆ ไว้เทียบ
- [musamaanjum/ai-engineer-roadmap (GitHub)](https://github.com/musamaanjum/ai-engineer-roadmap) มี 5 โปรเจกต์และหัวข้อเตรียมสัมภาษณ์
- [Dataquest – AI Engineer Roadmap](https://www.dataquest.io/blog/ai-engineer-roadmap/)
- [dataskew.io – AI Engineering Roadmap](https://dataskew.io/roadmaps/ai-engineering/)
