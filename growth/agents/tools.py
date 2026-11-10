"""
tools.py — สัญญาระหว่าง agent กับระบบภายนอก (ERPNext / Knowledge Base)

ทำไมต้องนิยาม tool เป็น contract ด้วย:
  ข้อมูลที่ Concierge ตอบลูกค้าเรื่องราคา/สต็อก/วันหมดอายุ ต้อง "ชี้แหล่งที่มาได้"
  ทุก ToolResult มี as_of — ถ้าเก่าเกิน staleness ที่กำหนด ห้ามเอาไปตอบ ต้องดึงใหม่

ทุก tool เป็น read-only ยกเว้นที่ระบุ — การเขียนลง ERPNext ไปทาง EffectDraft เท่านั้น
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from .common import Strict

ToolName = Literal[
    "erp.stock_lookup",
    "erp.batch_lookup",
    "erp.price_lookup",
    "erp.order_status",
    "erp.search_items",   # ลูกค้าพิมพ์ชื่อสินค้าไม่ตรงรหัส ต้องหาให้เจอก่อน
    "kb.search",
]

# ข้อมูลเก่ากว่านี้ = ห้ามใช้ตอบ ต้องเรียกใหม่ (วินาที)
MAX_STALENESS_S: dict[ToolName, int] = {
    "erp.stock_lookup": 60,      # สต็อกเปลี่ยนเร็ว บอกลูกค้าผิดแล้วเสียหาย
    "erp.batch_lookup": 300,
    "erp.price_lookup": 900,
    "erp.order_status": 60,
    "erp.search_items": 3600,    # รายการสินค้าไม่ค่อยเปลี่ยน
    "kb.search": 3600,
}


class ToolCall(Strict):
    name: ToolName
    args: dict[str, Any]
    why_th: str = Field(max_length=120)   # agent ต้องบอกได้ว่าเรียกทำไม


class ToolResult(Strict):
    name: ToolName
    args: dict[str, Any]
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    as_of: datetime
    source: str = "erpnext"

    @property
    def ref(self) -> str:
        """ใช้ใส่ใน grounded_on เช่น 'erp.stock_lookup:ONATO-500'"""
        key = self.args.get("erp_item_code") or self.args.get("query") or "-"
        return f"{self.name}:{key}"


# ─────────────────────────────────────────────────────────────
# รูปร่างของ data ในแต่ละ ToolResult
# ─────────────────────────────────────────────────────────────

class StockData(Strict):
    erp_item_code: str
    item_name_th: str
    warehouse: str
    qty_available: Decimal      # actual_qty - reserved_qty
    qty_reserved: Decimal = Decimal("0")
    uom: str = "ขวด"


class BatchRow(Strict):
    batch_no: str
    qty: Decimal
    expiry_date: date | None
    days_to_expiry: int | None


class BatchData(Strict):
    erp_item_code: str
    batches: list[BatchRow]
    nearest_expiry: date | None = None


class PriceData(Strict):
    erp_item_code: str
    price_list: str             # 'ขายปลีก' | 'ขายส่ง'
    rate: Decimal
    currency: str = "THB"
    valid_upto: date | None = None


class OrderStatusData(Strict):
    erp_sales_order: str
    status: str
    grand_total: Decimal
    delivery_status: str | None = None
    expected_delivery: date | None = None


class KbSearchArgs(Strict):
    query: str
    category: str | None = None
    top_k: int = 5


class KbSearchData(Strict):
    # ต้องกรอง valid_until < now ออกตั้งแต่ชั้นนี้
    # ไม่ใช่ปล่อยให้ agent เห็นโปรที่หมดอายุแล้วตัดสินใจเอง
    snippet_ids: list[UUID]
