# บทที่ 9 — เชื่อมต่อ ERPNext ผ่าน REST API

⏱ ประมาณ 5 ชั่วโมง · เริ่มสร้างส่วน "ข้อมูลธุรกิจจริง" ของ capstone

## เป้าหมาย
- [ ] เข้าใจโครงสร้างข้อมูลของ ERPNext (DocType, docstatus)
- [ ] สร้าง API key สำหรับ agent แบบสิทธิ์จำกัด
- [ ] อ่าน ค้นหา สร้าง และแก้ไขข้อมูลผ่าน REST API ด้วย Python
- [ ] เขียนคลาส `ERPClient` ที่จะใช้ต่อในบทที่ 10–12
- [ ] เปลี่ยนเครื่องมือจำลองในบทที่ 3–4 เป็นข้อมูลจริง

---

## 1. ERPNext ในมุมของนักพัฒนา

ERPNext สร้างบน **Frappe Framework** ทุกอย่างในระบบคือ **DocType** ซึ่งคล้ายกับตารางในฐานข้อมูล

| DocType | ข้อมูล | ใช้ในผู้ช่วยบริหารสำหรับ |
|---|---|---|
| `Item` | สินค้า | ค้นสินค้า, ดูราคา |
| `Bin` | ยอดคงเหลือต่อสินค้าต่อคลัง | ดูสต็อก |
| `Customer` | ลูกค้า | ค้นลูกค้า |
| `Quotation` | ใบเสนอราคา | ร่างใบเสนอราคา |
| `Sales Order` | ใบสั่งขาย | ติดตามคำสั่งซื้อ |
| `Sales Invoice` | ใบแจ้งหนี้ขาย | ดูยอดขายและหนี้ค้างรับ |
| `Purchase Order` | ใบสั่งซื้อ | สั่งของเข้า |
| `Item Price` | ราคาสินค้าตาม price list | ดูราคา |

### docstatus — สถานะของเอกสาร (สำคัญมาก)
| ค่า | ความหมาย | แก้ไขได้? |
|---|---|---|
| `0` | Draft (ร่าง) | ✅ แก้และลบได้ |
| `1` | Submitted (ยืนยันแล้ว) | ❌ มีผลทางบัญชีหรือสต็อกแล้ว ต้องยกเลิกเท่านั้น |
| `2` | Cancelled (ยกเลิก) | ❌ |

**กฎของผู้ช่วยบริหาร:** agent สร้างเอกสารได้แค่ **Draft (0)** ส่วนการ Submit ให้คนกดในระบบเอง
นี่คือการใช้หลักการในบทที่ 6 กับระบบจริง

---

## 2. เตรียม API Key แบบปลอดภัย

1. ใน ERPNext สร้าง **User ใหม่** เช่น `ai-assistant@yourshop.local`
2. ให้ **Role** เท่าที่จำเป็น เช่น `Stock User` และ `Sales User` (**ห้ามให้ System Manager**)
3. เปิดหน้า User นั้น ไปที่ส่วน **API Access** แล้วกด **Generate Keys**
4. เก็บ API Key และ API Secret ไว้ในไฟล์ `.env`

```ini
# .env
ERP_URL=http://192.168.x.x:8000
ERP_API_KEY=xxxxxxxxxxxxxxx
ERP_API_SECRET=xxxxxxxxxxxxxxx
```

> ⚠️ **เรื่องเฉพาะของเครื่องคุณ:** นาฬิกาของ VM ที่รัน ERPNext เคยเดินช้าไปหลายชั่วโมง
> ถ้าวันที่ของเอกสารที่สร้างผ่าน API ดูผิดปกติ ให้ตรวจเวลาของ VM ก่อน (`timedatectl`)

### ทดสอบการเชื่อมต่อ
```powershell
curl.exe -H "Authorization: token KEY:SECRET" http://ERP_URL/api/method/frappe.auth.get_logged_user
```
ถ้าได้ `{"message": "ai-assistant@yourshop.local"}` แปลว่าเชื่อมต่อสำเร็จ

---

## 3. REST API พื้นฐาน

รูปแบบการยืนยันตัวตน: header `Authorization: token <api_key>:<api_secret>`

| ทำอะไร | Method | URL |
|---|---|---|
| ค้นหาหลายรายการ | GET | `/api/resource/{DocType}?fields=[...]&filters=[...]&limit_page_length=20` |
| อ่าน 1 รายการ | GET | `/api/resource/{DocType}/{name}` |
| สร้าง | POST | `/api/resource/{DocType}` + JSON body |
| แก้ไข | PUT | `/api/resource/{DocType}/{name}` + JSON body |
| ลบ | DELETE | `/api/resource/{DocType}/{name}` |
| เรียกฟังก์ชันฝั่งเซิร์ฟเวอร์ | GET/POST | `/api/method/{dotted.path}` |

### Filters
```python
filters = [
    ["item_group", "=", "Computer Accessories"],
    ["actual_qty", "<", 5],
    ["posting_date", "between", ["2026-09-01", "2026-09-30"]],
    ["customer_name", "like", "%สมใจ%"],
]
```
ตัวดำเนินการที่ใช้ได้ เช่น `=`, `!=`, `<`, `>`, `<=`, `>=`, `like`, `in`, `not in`, `between`, `is` (`set` / `not set`)

---

## 4. ERPClient — คลาสที่ใช้ตลอดโปรเจกต์

```python
# erp_client.py
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()


class ERPError(Exception):
    pass


class ERPClient:
    def __init__(self):
        self.base = os.environ["ERP_URL"].rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {os.environ['ERP_API_KEY']}:{os.environ['ERP_API_SECRET']}",
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs):
        resp = self.session.request(method, f"{self.base}{path}", timeout=20, **kwargs)
        if not resp.ok:
            # Frappe มักส่งรายละเอียด error ไว้ใน _server_messages หรือ exception
            try:
                body = resp.json()
                detail = body.get("exception") or body.get("_server_messages") or body
            except ValueError:
                detail = resp.text[:300]
            raise ERPError(f"HTTP {resp.status_code}: {detail}")
        return resp.json()

    def get_list(self, doctype: str, fields=None, filters=None,
                 order_by: str | None = None, limit: int = 20) -> list[dict]:
        params = {
            "fields": json.dumps(fields or ["name"]),
            "filters": json.dumps(filters or []),
            "limit_page_length": limit,
        }
        if order_by:
            params["order_by"] = order_by
        return self._request("GET", f"/api/resource/{doctype}", params=params)["data"]

    def get_doc(self, doctype: str, name: str) -> dict:
        return self._request("GET", f"/api/resource/{doctype}/{name}")["data"]

    def create_doc(self, doctype: str, data: dict) -> dict:
        data = {**data, "docstatus": 0}           # 🔒 บังคับให้เป็น Draft เสมอ
        return self._request("POST", f"/api/resource/{doctype}", json=data)["data"]

    def update_doc(self, doctype: str, name: str, data: dict) -> dict:
        data.pop("docstatus", None)               # 🔒 ห้าม submit หรือ cancel ผ่าน agent
        return self._request("PUT", f"/api/resource/{doctype}/{name}", json=data)["data"]
```

**สังเกต:** กฎความปลอดภัย (Draft เท่านั้น) ถูกบังคับไว้ **ในโค้ด** ไม่ได้ฝากไว้ใน prompt

---

## 5. ฟังก์ชันธุรกิจที่ agent จะใช้

```python
# erp_tools.py
from datetime import date

from erp_client import ERPClient

erp = ERPClient()


def search_items(keyword: str, limit: int = 10) -> list[dict]:
    return erp.get_list(
        "Item",
        fields=["item_code", "item_name", "item_group", "stock_uom"],
        filters=[["item_name", "like", f"%{keyword}%"], ["disabled", "=", 0]],
        limit=limit,
    )


def get_stock(item_code: str) -> list[dict]:
    return erp.get_list(
        "Bin",
        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"],
        filters=[["item_code", "=", item_code]],
    )


def low_stock_items(threshold: float = 5) -> list[dict]:
    return erp.get_list(
        "Bin",
        fields=["item_code", "warehouse", "actual_qty"],
        filters=[["actual_qty", "<", threshold]],
        order_by="actual_qty asc",
        limit=50,
    )


def sales_summary(start: str, end: str) -> dict:
    invoices = erp.get_list(
        "Sales Invoice",
        fields=["name", "customer", "grand_total", "posting_date"],
        filters=[["docstatus", "=", 1], ["posting_date", "between", [start, end]]],
        limit=1000,
    )
    total = sum(i["grand_total"] for i in invoices)
    by_customer: dict[str, float] = {}
    for i in invoices:
        by_customer[i["customer"]] = by_customer.get(i["customer"], 0) + i["grand_total"]
    top = sorted(by_customer.items(), key=lambda x: -x[1])[:5]
    # ✅ สรุปก่อนส่งให้โมเดล (บทที่ 5) ไม่ส่ง invoice ดิบ 1,000 รายการ
    return {"period": f"{start} ถึง {end}", "invoice_count": len(invoices),
            "total": round(total, 2), "top_customers": top}


def create_quotation_draft(customer: str, items: list[dict]) -> dict:
    """items = [{"item_code": "MOUSE-01", "qty": 2}]"""
    doc = erp.create_doc("Quotation", {
        "quotation_to": "Customer",
        "party_name": customer,
        "transaction_date": date.today().isoformat(),
        "items": items,
    })
    return {"name": doc["name"], "grand_total": doc.get("grand_total"), "status": "Draft",
            "note": "สร้างเป็นร่างแล้ว ผู้ใช้ต้องตรวจและกด Submit ใน ERPNext เอง"}
```

### ข้อควรระวัง
- **`limit_page_length` ค่าเริ่มต้นคือ 20** ถ้าจะนับยอดขายทั้งเดือน ต้องตั้ง limit ให้พอ หรือแบ่งหน้า (`limit_start`)
  ถ้าข้อมูลเยอะมาก ให้ใช้ report หรือ query ฝั่งเซิร์ฟเวอร์แทน
- **ชื่อฟิลด์ต่างกันตามเวอร์ชัน** ให้ตรวจชื่อฟิลด์จริงได้ที่ `/api/resource/DocType/{ชื่อ}` หรือเมนู Customize Form
- **Child table** (เช่น `items` ใน Quotation) ส่งเป็น list ของ dict ในเอกสารแม่ได้เลย
- **Permission error (403)** หมายถึง user ของ agent ไม่มีสิทธิ์ ให้เพิ่ม Role อย่างระมัดระวัง

---

## 6. ต่อเข้ากับ Agent

แก้ `mini_agent.py` จากบทที่ 4 โดยเปลี่ยน `TOOLS` และ `HANDLERS`:

```python
from erp_tools import (create_quotation_draft, get_stock, low_stock_items,
                       sales_summary, search_items)
import json

def as_text(fn):
    """ห่อฟังก์ชันให้คืนค่าเป็น JSON string สำหรับ tool_result"""
    return lambda **kw: json.dumps(fn(**kw), ensure_ascii=False, default=str)

HANDLERS = {
    "search_items": as_text(search_items),
    "get_stock": as_text(get_stock),
    "low_stock_items": as_text(low_stock_items),
    "sales_summary": as_text(sales_summary),
    "create_quotation_draft": as_text(create_quotation_draft),
}
RISK = {"create_quotation_draft": "dangerous"}      # ถามผู้ใช้ก่อน (บทที่ 6)
```

System prompt ต้องบอก **วันที่ปัจจุบัน** ด้วย เพราะโมเดลไม่รู้ว่าวันนี้วันที่เท่าไร:
```python
SYSTEM = f"""คุณคือผู้ช่วยบริหารร้าน ... วันนี้คือ {date.today():%Y-%m-%d}
- ใช้ search_items หา item_code ก่อนเรียก get_stock เสมอ
- ตัวเลขทุกตัวต้องมาจากเครื่องมือ ห้ามประมาณเอง"""
```
(ถ้าใช้ prompt caching ให้วางวันที่ไว้ **ท้าย** system prompt หรือใส่ไว้ใน user message เพื่อไม่ให้ cache พลาดทุกวัน)

ตัวอย่างคำถามที่ควรลองถาม:
- "สินค้าไหนใกล้หมดบ้าง"
- "เดือนนี้ขายได้เท่าไร ลูกค้ารายไหนซื้อเยอะสุด"
- "ร่างใบเสนอราคาเมาส์ 5 ตัวให้บริษัท สมใจการช่าง"

---

## 7. Webhook — ให้ ERPNext เป็นฝ่ายแจ้งเตือน

นอกจากดึงข้อมูลจาก ERPNext แล้ว ERPNext ยังส่งข้อมูลมาหาเราได้ผ่าน **Webhook**
(ตั้งค่าที่ Integrations → Webhook) เช่น "เมื่อมี Sales Order ใหม่ ให้ POST มาที่ `http://my-app/hooks/order`"

ใช้ทำงานเชิงรุกได้ เช่น
- สต็อกต่ำกว่าเกณฑ์ → ให้ AI ร่างใบสั่งซื้อรอให้คนอนุมัติ
- ลูกค้าใหม่ → ให้ AI ร่างอีเมลต้อนรับ

(บทที่ 11 จะทำ endpoint ที่รับ webhook)

---

## สรุปบทที่ 9
1. ข้อมูลทุกอย่างใน ERPNext คือ DocType และ `docstatus` บอกว่าเอกสารแก้ไขได้หรือไม่
2. สร้าง user และ API key เฉพาะให้ agent พร้อมสิทธิ์น้อยที่สุด
3. REST API: `/api/resource/{DocType}` พร้อม fields, filters และ limit
4. บังคับให้ agent สร้างได้แค่ Draft ในโค้ด แล้วให้คนเป็นคน Submit
5. สรุปข้อมูลก่อนส่งให้โมเดล และใส่วันที่ปัจจุบันใน prompt

---

## แบบฝึกหัด
1. สร้าง user และ API key สำหรับ agent แล้วทดสอบด้วย curl
2. เขียน `erp_client.py` และ `erp_tools.py` แล้วทดสอบแต่ละฟังก์ชัน **โดยยังไม่ต้องใช้ AI**
3. เพิ่มฟังก์ชัน `overdue_invoices()` ที่ดึงใบแจ้งหนี้ที่เลยกำหนดชำระและยังไม่ได้จ่าย
   (ใบ้: ดูฟิลด์ `due_date` และ `outstanding_amount`)
4. ต่อเครื่องมือทั้งหมดเข้ากับ agent แล้วลองถามคำถาม 10 ข้อ บันทึกว่าตอบถูกกี่ข้อ
5. ลองสั่ง agent ว่า "submit ใบเสนอราคานั้นเลย" แล้วตรวจว่าระบบกันไว้ได้จริง

✅ ไปต่อที่ [บทที่ 10](../10-mcp/lesson.md)
