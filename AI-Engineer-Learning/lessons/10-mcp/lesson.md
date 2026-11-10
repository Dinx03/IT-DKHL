# บทที่ 10 — MCP: สร้าง ERPNext MCP Server

⏱ ประมาณ 5 ชั่วโมง

## เป้าหมาย
- [ ] เข้าใจว่า MCP คืออะไร และแก้ปัญหาอะไร
- [ ] รู้จักองค์ประกอบของ MCP: host, client, server, tools, resources, prompts
- [ ] สร้าง ERPNext MCP server ด้วย Python (FastMCP)
- [ ] ใช้งาน server กับ Claude Desktop, Claude Code และโค้ดของเราเอง
- [ ] เข้าใจความเสี่ยงด้านความปลอดภัยของ MCP

---

## 1. ปัญหาที่ MCP แก้

ในบทที่ 9 เราเขียนเครื่องมือ ERPNext ไว้ **ใน agent ตัวเดียว**
แต่ถ้าอยากใช้เครื่องมือชุดเดียวกันใน Claude Desktop, Claude Code, เว็บแอปของเรา และ agent ตัวอื่น
ก็ต้องเขียนเครื่องมือซ้ำในทุกที่

**MCP (Model Context Protocol)** คือ **มาตรฐานกลาง** ที่ทำให้เขียนเครื่องมือครั้งเดียว แล้วใช้ได้กับทุกแอปที่รองรับ MCP

```
      ก่อนมี MCP: M แอป × N ระบบ = M×N integration

      หลังมี MCP:  แอป (M) ──┐                ┌── ERPNext server
                              ├── MCP ─────────┼── Google Drive server
                              │  (มาตรฐานเดียว)  ├── GitHub server
                              └────────────────┴── Database server
                 = M + N integration
```

> 💡 **เปรียบเทียบ:** MCP คือ **USB-C ของโลก AI**
> หรือถ้าเทียบกับวิศวคอม: คล้าย Language Server Protocol (LSP) ที่ทำให้ editor ทุกตัวรองรับภาษาไหนก็ได้

---

## 2. สถาปัตยกรรม

```
┌───────────────── Host (Claude Desktop / Claude Code / แอปของคุณ) ─────────────────┐
│   LLM  ◀──▶  MCP Client ─┬─────── stdio ──────▶ MCP Server A (ERPNext)            │
│                          └─ HTTP (streamable) ─▶ MCP Server B (บนคลาวด์)           │
└───────────────────────────────────────────────────────────────────────────────────┘
```

| ส่วน | หน้าที่ |
|---|---|
| **Host** | แอปที่ผู้ใช้ใช้งาน และเป็นเจ้าของ LLM |
| **Client** | ตัวเชื่อมต่อกับ server (1 client ต่อ 1 server) |
| **Server** | โปรแกรมที่เปิดให้ใช้เครื่องมือและข้อมูล (**ส่วนที่เราเขียน**) |

### Transport
| แบบ | ใช้เมื่อ |
|---|---|
| **stdio** | server รันเป็น process บนเครื่องเดียวกัน (host สั่ง start ให้เอง) |
| **Streamable HTTP** | server รันเป็นเว็บเซอร์วิส ให้หลายคนหรือหลายเครื่องใช้ร่วมกัน |

### สิ่งที่ server เปิดให้ใช้ได้ 3 ประเภท
| ประเภท | ใครเป็นคนเลือกใช้ | ตัวอย่าง |
|---|---|---|
| **Tools** | โมเดลเลือกเอง | `get_stock`, `create_quotation_draft` |
| **Resources** | แอปหรือผู้ใช้เลือก | นโยบายร้าน, รายชื่อคลังสินค้า |
| **Prompts** | ผู้ใช้เลือก (เหมือน slash command) | "/สรุปยอดขายประจำสัปดาห์" |

---

## 3. สร้าง ERPNext MCP Server

```powershell
pip install "mcp[cli]" requests python-dotenv
```

```python
# erpnext_mcp_server.py
import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

import erp_tools                       # จากบทที่ 9

# ⚠️ server แบบ stdio ห้าม print ลง stdout เพราะจะทำให้ข้อความของโปรโตคอลเสีย
# ให้ log ลง stderr แทน
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("erpnext-mcp")

mcp = FastMCP("erpnext")


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


# ---------------- Tools: อ่าน ----------------
@mcp.tool()
def search_items(keyword: str, limit: int = 10) -> str:
    """ค้นหาสินค้าใน ERPNext จากชื่อ คืนค่า item_code, item_name, item_group

    Args:
        keyword: คำค้น เช่น 'เมาส์'
        limit: จำนวนผลลัพธ์สูงสุด (ไม่เกิน 50)
    """
    return _json(erp_tools.search_items(keyword, min(limit, 50)))


@mcp.tool()
def get_stock(item_code: str) -> str:
    """ดูยอดคงเหลือของสินค้าแยกตามคลัง ต้องใช้ item_code (หาได้จาก search_items)

    Args:
        item_code: รหัสสินค้า เช่น 'MOUSE-01'
    """
    return _json(erp_tools.get_stock(item_code))


@mcp.tool()
def low_stock_items(threshold: float = 5) -> str:
    """รายการสินค้าที่คงเหลือน้อยกว่าเกณฑ์ เรียงจากน้อยไปมาก

    Args:
        threshold: เกณฑ์จำนวนคงเหลือ
    """
    return _json(erp_tools.low_stock_items(threshold))


@mcp.tool()
def sales_summary(start: str, end: str) -> str:
    """สรุปยอดขายจากใบแจ้งหนี้ที่ submit แล้ว ในช่วงวันที่ที่กำหนด

    Args:
        start: วันเริ่ม รูปแบบ YYYY-MM-DD
        end: วันสิ้นสุด รูปแบบ YYYY-MM-DD
    """
    return _json(erp_tools.sales_summary(start, end))


# ---------------- Tools: เขียน (Draft เท่านั้น) ----------------
@mcp.tool()
def create_quotation_draft(customer: str, items: list[dict]) -> str:
    """สร้างใบเสนอราคาแบบร่าง (Draft) ใน ERPNext ไม่มีผลทางบัญชีจนกว่าคนจะกด Submit

    Args:
        customer: ชื่อลูกค้า (name ของ Customer ใน ERPNext)
        items: รายการสินค้า เช่น [{"item_code": "MOUSE-01", "qty": 2}]
    """
    log.info("create_quotation_draft customer=%s items=%s", customer, items)
    return _json(erp_tools.create_quotation_draft(customer, items))


# ---------------- Resources ----------------
@mcp.resource("shop://policy")
def shop_policy() -> str:
    """นโยบายร้าน: การคืนสินค้า การรับประกัน การจัดส่ง"""
    with open("docs/policy.md", encoding="utf-8") as f:
        return f.read()


# ---------------- Prompts ----------------
@mcp.prompt()
def weekly_report(week_start: str) -> str:
    """สร้างรายงานผู้บริหารประจำสัปดาห์"""
    return (f"สร้างรายงานประจำสัปดาห์ที่เริ่ม {week_start}: "
            "1) ยอดขายและลูกค้าหลักจาก sales_summary "
            "2) สินค้าที่ต้องสั่งเพิ่มจาก low_stock_items "
            "3) ข้อเสนอแนะ 3 ข้อ ตอบเป็นภาษาไทย")


if __name__ == "__main__":
    mcp.run()          # ค่าเริ่มต้นคือ stdio
    # mcp.run(transport="streamable-http")   # ถ้าจะเปิดเป็นเว็บเซอร์วิส
```

**FastMCP สร้าง schema ให้อัตโนมัติ** จาก type hint และ docstring เหมือน tool runner ในบทที่ 3
**docstring จึงเป็น description ของเครื่องมือ** ต้องเขียนให้ดี

---

## 4. ทดสอบด้วย MCP Inspector

```powershell
mcp dev erpnext_mcp_server.py
```
คำสั่งนี้จะเปิดหน้าเว็บ Inspector ให้เห็นรายการ tools, resources และ prompts และให้กดเรียกทดสอบได้ **โดยไม่ต้องใช้ LLM**
ทดสอบที่นี่ให้ผ่านก่อนเสมอ แล้วค่อยต่อกับ Claude
(คำสั่งนี้ต้องมี Node.js ในเครื่อง)

---

## 5. ใช้กับ Claude Desktop และ Claude Code

### Claude Desktop
แก้ไฟล์ `claude_desktop_config.json` (เปิดได้จาก Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "erpnext": {
      "command": "C:\\Users\\User\\...\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\User\\...\\erpnext_mcp_server.py"],
      "env": {
        "ERP_URL": "http://192.168.x.x:8000",
        "ERP_API_KEY": "...",
        "ERP_API_SECRET": "..."
      }
    }
  }
}
```
จากนั้นรีสตาร์ท Claude Desktop แล้วถามได้เลย เช่น "สินค้าไหนใกล้หมด"

> ใช้ path เต็มของ `python.exe` ที่อยู่ใน venv เพื่อให้ server เห็นแพ็กเกจที่ติดตั้งไว้

### Claude Code
```bash
claude mcp add erpnext -- C:\path\to\.venv\Scripts\python.exe C:\path\to\erpnext_mcp_server.py
```

---

## 6. ใช้ MCP Server จากโค้ดของเราเอง

ในเว็บแอปของเรา (บทที่ 11) เราเป็น host เอง SDK ของ Anthropic มีตัวช่วยแปลงเครื่องมือจาก MCP เป็นเครื่องมือของ Claude ให้:

```powershell
pip install "anthropic[mcp]"
```

```python
import asyncio

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

client = AsyncAnthropic()
server = StdioServerParameters(command="python", args=["erpnext_mcp_server.py"])


async def main(question: str):
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools

            runner = client.beta.messages.tool_runner(
                model="claude-opus-5",
                max_tokens=16000,
                tools=[async_mcp_tool(t, session) for t in tools],
                messages=[{"role": "user", "content": question}],
            )
            async for message in runner:
                for block in message.content:
                    if block.type == "text":
                        print(block.text)

asyncio.run(main("สินค้าไหนใกล้หมดบ้าง"))
```

### Remote MCP บน API
ถ้า MCP server ของคุณเปิดเป็น HTTP บนอินเทอร์เน็ต Claude API สามารถเชื่อมต่อกับ server ได้เองผ่าน **MCP connector** (beta)
แต่ server ต้องเข้าถึงได้จากภายนอกและต้องมีการยืนยันตัวตน **อย่าเปิด ERPNext MCP server สู่สาธารณะโดยไม่มี auth**

---

## 7. ความปลอดภัยของ MCP

| ความเสี่ยง | คำอธิบาย | วิธีป้องกัน |
|---|---|---|
| **Server ที่ไม่น่าไว้ใจ** | MCP server คือโค้ดที่รันบนเครื่องคุณ | ติดตั้งเฉพาะจากแหล่งที่เชื่อถือได้ และอ่านโค้ดก่อน |
| **Tool poisoning** | description ของเครื่องมือมีคำสั่งแอบแฝง | อ่าน description ของ server ภายนอก |
| **สิทธิ์เกินจำเป็น** | server ถือ admin key | ใช้ user และสิทธิ์เฉพาะตามบทที่ 9 |
| **Prompt injection ผ่านข้อมูล** | ข้อมูลใน ERPNext อาจมีข้อความที่คนภายนอกกรอกเข้ามา | ใช้หลักการในบทที่ 6 |
| **HTTP ไม่มี auth** | ใครก็เรียกใช้ได้ | ใส่ OAuth หรือ token และใช้ HTTPS |

### Tool annotations
MCP กำหนดให้บอก host ได้ว่าเครื่องมือแต่ละตัว **อ่านอย่างเดียว** หรือ **ทำลายข้อมูลได้** (`readOnlyHint`, `destructiveHint`)
host อย่าง Claude Desktop จะใช้ข้อมูลนี้ตัดสินใจว่าต้องถามผู้ใช้ก่อนหรือไม่
แต่ **ห้ามพึ่ง annotation อย่างเดียว** ให้บังคับกฎในโค้ดของ server ด้วยเสมอ (เช่น Draft เท่านั้น)

---

## สรุปบทที่ 10
1. MCP = มาตรฐานกลาง เขียนเครื่องมือครั้งเดียว ใช้ได้ทุก host
2. Host → Client → Server ผ่าน stdio หรือ HTTP
3. Server เปิดให้ใช้ tools (โมเดลเลือก), resources (แอปเลือก), prompts (ผู้ใช้เลือก)
4. FastMCP สร้าง schema จาก type hint และ docstring
5. server แบบ stdio ห้าม print ลง stdout ให้ log ลง stderr
6. ทดสอบด้วย Inspector ก่อน แล้วค่อยต่อกับ Claude
7. บังคับความปลอดภัยใน server และไม่เปิด HTTP โดยไม่มี auth

---

## แบบฝึกหัด (โปรเจกต์ Portfolio ชิ้นที่ 2 ⭐)
1. สร้าง `erpnext_mcp_server.py` แล้วทดสอบทุกเครื่องมือใน Inspector
2. ต่อ server เข้ากับ Claude Desktop แล้วลองถามคำถามธุรกิจ 10 ข้อ
3. เพิ่ม resource `shop://warehouses` ที่คืนรายชื่อคลังสินค้าจาก ERPNext
4. เพิ่ม prompt `/reorder_plan` ที่ให้ AI วางแผนสั่งซื้อจากสต็อกต่ำและยอดขายย้อนหลัง
5. เพิ่มเครื่องมือ `search_docs` จากบทที่ 8 เข้าไปใน server เพื่อให้ server เดียวตอบได้ทั้งข้อมูลธุรกิจและนโยบาย
6. ทำ README พร้อมคลิปสาธิต แล้วขึ้น GitHub (**ห้ามมี `.env`**)

✅ ไปต่อที่ [บทที่ 11](../11-web-app/lesson.md)
