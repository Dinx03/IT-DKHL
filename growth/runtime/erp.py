"""
erp.py — ตัวเรียก ERPNext ตามสัญญาใน agents/tools.py

นี่คือหัวใจของทั้งโปรเจกต์: สิ่งที่ทำให้ AI ของเราตอบได้ว่า
"เหลือ 76 ขวด ล็อตนี้หมดอายุ ก.ย. 70" แทนที่จะตอบว่า "มีค่ะ เดี๋ยวเช็คให้"

กฎของไฟล์นี้:
  - อ่านอย่างเดียว ไม่เขียน ERPNext (การเขียนไปทาง EffectDraft → outbound_jobs)
  - ทุกผลลัพธ์ติด as_of มาเสมอ ข้อมูลเก่าเกิน MAX_STALENESS_S ห้ามเอาไปตอบ
  - ไม่มีการเดา ถ้าถามสินค้าที่ไม่มี ต้องบอกว่าไม่มี ไม่ใช่คืนศูนย์
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import requests

from ..agents.tools import (BatchData, BatchRow, PriceData, StockData,
                            ToolCall, ToolResult)
from .db import _load_env

_TIMEOUT = 10


class ErpError(RuntimeError):
    pass


def _cfg() -> tuple[str, str]:
    env = _load_env()
    base = os.environ.get("ERP_BASE_URL") or env.get("ERP_BASE_URL")
    token = os.environ.get("ERP_API_TOKEN") or env.get("ERP_API_TOKEN")
    if not base or not token:
        raise ErpError("ยังไม่ได้ตั้ง ERP_BASE_URL / ERP_API_TOKEN ใน growth/.env")
    return base.rstrip("/"), token


def _get(path: str, params: dict[str, Any]) -> Any:
    base, token = _cfg()
    r = requests.get(f"{base}{path}", params=params,
                     headers={"Authorization": f"token {token}",
                              "Accept": "application/json"},
                     timeout=_TIMEOUT)
    if r.status_code == 403:
        raise ErpError("ERPNext ปฏิเสธสิทธิ์ — ตรวจ role ของ growth-agent@ona.local")
    r.raise_for_status()
    return r.json().get("data")


def _ok(name, args, data) -> ToolResult:
    return ToolResult(name=name, args=args, ok=True,
                      data=data, as_of=datetime.now(timezone.utc))


def _fail(name, args, msg) -> ToolResult:
    return ToolResult(name=name, args=args, ok=False, error=msg,
                      as_of=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────

def stock_lookup(erp_item_code: str, warehouse: str | None = None) -> ToolResult:
    args = {"erp_item_code": erp_item_code, "warehouse": warehouse}
    try:
        item = _get("/api/resource/Item", {
            "filters": f'[["item_code","=","{erp_item_code}"]]',
            "fields": '["item_code","item_name","stock_uom","disabled"]', "limit_page_length": 1})
        if not item:
            return _fail("erp.stock_lookup", args, f"ไม่มีสินค้ารหัส {erp_item_code} ในระบบ")
        item = item[0]

        filters: list[list[Any]] = [["item_code", "=", erp_item_code]]
        if warehouse:
            filters.append(["warehouse", "=", warehouse])
        bins = _get("/api/resource/Bin", {
            "filters": str(filters).replace("'", '"'),
            "fields": '["warehouse","actual_qty","reserved_qty"]', "limit_page_length": 50})

        if not bins:
            return _ok("erp.stock_lookup", args, StockData(
                erp_item_code=erp_item_code, item_name_th=item["item_name"],
                warehouse=warehouse or "-", qty_available=Decimal(0),
                uom=item.get("stock_uom") or "ชิ้น").model_dump(mode="json"))

        actual = sum(Decimal(str(b.get("actual_qty") or 0)) for b in bins)
        reserved = sum(Decimal(str(b.get("reserved_qty") or 0)) for b in bins)
        return _ok("erp.stock_lookup", args, StockData(
            erp_item_code=erp_item_code, item_name_th=item["item_name"],
            warehouse=warehouse or ", ".join(b["warehouse"] for b in bins),
            qty_available=actual - reserved, qty_reserved=reserved,
            uom=item.get("stock_uom") or "ชิ้น").model_dump(mode="json"))
    except Exception as exc:                                   # noqa: BLE001
        return _fail("erp.stock_lookup", args, f"{type(exc).__name__}: {exc}")


def batch_lookup(erp_item_code: str) -> ToolResult:
    """ล็อตไหนหมดอายุก่อน — คำถามที่เครื่องมือการตลาดทั่วไปตอบไม่ได้
    เพราะไม่มีใครเห็นคลังของเรา"""
    args = {"erp_item_code": erp_item_code}
    try:
        rows = _get("/api/resource/Batch", {
            "filters": f'[["item","=","{erp_item_code}"]]',
            "fields": '["name","batch_qty","expiry_date"]',
            "order_by": "expiry_date asc", "limit_page_length": 100})
        today = date.today()
        out: list[BatchRow] = []
        for r in rows or []:
            exp = (datetime.strptime(r["expiry_date"], "%Y-%m-%d").date()
                   if r.get("expiry_date") else None)
            qty = Decimal(str(r.get("batch_qty") or 0))
            if qty <= 0:
                continue                       # ล็อตหมดแล้ว ไม่ต้องเอาไปตอบลูกค้า
            out.append(BatchRow(batch_no=r["name"], qty=qty, expiry_date=exp,
                                days_to_expiry=(exp - today).days if exp else None))
        nearest = next((b.expiry_date for b in out if b.expiry_date), None)
        return _ok("erp.batch_lookup", args, BatchData(
            erp_item_code=erp_item_code, batches=out,
            nearest_expiry=nearest).model_dump(mode="json"))
    except Exception as exc:                                   # noqa: BLE001
        return _fail("erp.batch_lookup", args, f"{type(exc).__name__}: {exc}")


def price_lookup(erp_item_code: str, price_list: str = "Standard Selling") -> ToolResult:
    args = {"erp_item_code": erp_item_code, "price_list": price_list}
    try:
        rows = _get("/api/resource/Item Price", {
            "filters": f'[["item_code","=","{erp_item_code}"],'
                       f'["price_list","=","{price_list}"]]',
            "fields": '["price_list_rate","currency","valid_upto"]',
            "order_by": "valid_from desc", "limit_page_length": 1})
        if not rows:
            return _fail("erp.price_lookup", args,
                         f"ยังไม่ได้ตั้งราคาของ {erp_item_code} ใน {price_list}")
        r = rows[0]
        return _ok("erp.price_lookup", args, PriceData(
            erp_item_code=erp_item_code, price_list=price_list,
            rate=Decimal(str(r["price_list_rate"])),
            currency=r.get("currency") or "THB",
            valid_upto=(datetime.strptime(r["valid_upto"], "%Y-%m-%d").date()
                        if r.get("valid_upto") else None)).model_dump(mode="json"))
    except Exception as exc:                                   # noqa: BLE001
        return _fail("erp.price_lookup", args, f"{type(exc).__name__}: {exc}")


def search_items(keyword: str, limit: int = 10) -> ToolResult:
    """ลูกค้าพิมพ์ชื่อสินค้าไม่ตรงรหัส ต้องหาให้เจอก่อนถึงจะเช็คสต็อกได้"""
    args = {"query": keyword}
    try:
        rows = _get("/api/resource/Item", {
            "or_filters": f'[["item_name","like","%{keyword}%"],'
                          f'["item_code","like","%{keyword}%"]]',
            "filters": '[["disabled","=",0]]',
            "fields": '["item_code","item_name","item_group","stock_uom"]',
            "limit_page_length": limit})
        return _ok("erp.search_items", args, {"items": rows or []})
    except Exception as exc:                                   # noqa: BLE001
        return _fail("erp.search_items", args, f"{type(exc).__name__}: {exc}")


DISPATCH = {
    "erp.stock_lookup": lambda a: stock_lookup(a["erp_item_code"], a.get("warehouse")),
    "erp.batch_lookup": lambda a: batch_lookup(a["erp_item_code"]),
    "erp.price_lookup": lambda a: price_lookup(a["erp_item_code"],
                                               a.get("price_list", "Standard Selling")),
}


def call(tc: ToolCall) -> ToolResult:
    """จุดเดียวที่ agent เรียก tool ได้ — ชื่อที่ไม่รู้จักต้องพังดังๆ ไม่ใช่เงียบ"""
    fn = DISPATCH.get(tc.name)
    if fn is None:
        return _fail(tc.name, tc.args, f"ไม่รู้จัก tool ชื่อ {tc.name}")
    return fn(tc.args)


# ─────────────────────────────────────────────────────────────
# การเขียนลง ERPNext — เรียกได้จาก worker เท่านั้น ไม่ใช่จาก agent
# agent เสนอผ่าน EffectDraft → เข้าคิว outbound_jobs → คนอนุมัติ → worker ทำ
# ─────────────────────────────────────────────────────────────

def _post(doctype: str, doc: dict[str, Any]) -> dict[str, Any]:
    base, token = _cfg()
    r = requests.post(f"{base}/api/resource/{doctype}", json=doc,
                      headers={"Authorization": f"token {token}",
                               "Content-Type": "application/json",
                               "Accept": "application/json"},
                      timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise ErpError(f"ERPNext ปฏิเสธ ({r.status_code}): {r.text[:300]}")
    return r.json().get("data", {})


def create_lead(payload: dict[str, Any]) -> dict[str, Any]:
    """สร้าง Lead ใน ERPNext — เรียกเมื่อคนกดอนุมัติแล้วเท่านั้น"""
    doc = {
        "doctype": "Lead",
        "lead_name": payload.get("lead_name") or "ลูกค้าจากแชท",
        "company_name": payload.get("lead_name") or "ลูกค้าจากแชท",
        "source": payload.get("source") or "Campaign",
        "status": "Lead",
        "notes": [{"note": payload.get("summary_th", "")}] if payload.get("summary_th") else [],
    }
    for k_in, k_out in (("mobile_no", "mobile_no"), ("email", "email_id"),
                        ("company", "company")):
        if payload.get(k_in):
            doc[k_out] = payload[k_in]
    return _post("Lead", doc)


WRITERS = {"create_erp_lead": create_lead}


def delete_doc(doctype: str, name: str) -> bool:
    """ลบ document — ใช้เก็บกวาดข้อมูลทดสอบเท่านั้น
    ห้ามเรียกจาก agent หรือ worker ในเส้นทางปกติ"""
    base, token = _cfg()
    r = requests.delete(f"{base}/api/resource/{doctype}/{name}",
                        headers={"Authorization": f"token {token}"},
                        timeout=_TIMEOUT)
    return r.status_code < 400
