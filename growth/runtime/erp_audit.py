"""
erp_audit.py — ตรวจว่าข้อมูลใน ERPNext พร้อมให้ AI ขายของหรือยัง

    py -m growth.runtime.erp_audit

ทำไมต้องมี:
  AI ตอบได้แค่ตามข้อมูลที่มี ถ้าสินค้ามีของจริงแต่สต็อกใน ERP เป็น 0
  ระบบจะบอกลูกค้าว่า "หมดแล้วค่ะ" แล้วลูกค้าก็ไป — เสียยอดขายจริง
  สคริปต์นี้บอกว่าต้องไปแก้อะไรบ้างก่อนเปิดใช้กับลูกค้า

ไม่แก้ไขอะไรใน ERPNext — อ่านอย่างเดียว
"""

from __future__ import annotations

import sys

from . import db, erp

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

OK, WARN, BAD = "พร้อม", "ขาด", "ไม่พร้อม"


def main() -> None:
    with db.connect() as conn:
        _, brand_id = db.resolve_brand(conn)
        rows = conn.execute(
            """select erp_item_code, title from knowledge_docs
                where category = 'product' and erp_item_code is not null
                order by erp_item_code"""
        ).fetchall()

    print(f"\nตรวจสินค้าที่ขายได้ {len(rows)} รายการ\n")
    print(f"  {'รหัส':<19}{'ชื่อไทย':<24}{'สต็อก':>10}  {'ราคา':>9}  ล็อต")
    print("  " + "─" * 74)

    no_stock, no_price, no_batch = [], [], []

    for r in rows:
        code, title = r["erp_item_code"], r["title"]
        s, p, b = (erp.stock_lookup(code), erp.price_lookup(code),
                   erp.batch_lookup(code))

        qty = float(s.data["qty_available"]) if s.ok else -1
        qty_txt = f"{qty:,.0f} {s.data['uom']}" if s.ok else "อ่านไม่ได้"
        if qty <= 0:
            no_stock.append((code, title))

        price_txt = f"{float(p.data['rate']):,.0f}฿" if p.ok else "ไม่มีราคา"
        if not p.ok:
            no_price.append((code, title))

        if b.ok and b.data["batches"]:
            nb = b.data["batches"][0]
            batch_txt = (f"{nb['batch_no'][-9:]} หมดอายุอีก {nb['days_to_expiry']} วัน"
                         if nb["expiry_date"] else "ไม่ระบุวันหมดอายุ")
        else:
            batch_txt = "ไม่มีล็อต"
            no_batch.append((code, title))

        flag = " " if (qty > 0 and p.ok) else "!"
        print(f" {flag}{code:<19}{title[:22]:<24}{qty_txt:>10}  {price_txt:>9}  {batch_txt}")

    print("\n" + "═" * 76)
    print("สรุปสิ่งที่ต้องแก้ก่อนเปิดใช้กับลูกค้าจริง\n")

    if no_stock:
        print(f"  [{BAD}] สต็อกเป็น 0 — AI จะบอกลูกค้าว่า 'หมดแล้ว' ({len(no_stock)} รายการ)")
        for code, title in no_stock:
            print(f"          {code:<19} {title}")
        print("          → ถ้ามีของจริง ต้องรับเข้าสต็อกใน ERPNext ก่อน\n")

    if no_price:
        print(f"  [{WARN}] ไม่มีราคาใน Standard Selling ({len(no_price)} รายการ)")
        for code, title in no_price:
            print(f"          {code:<19} {title}")
        print("          → AI จะตอบสต็อกได้ แต่ตอบราคาไม่ได้ ต้องส่งต่อคนทุกครั้ง\n")

    if no_batch:
        print(f"  [{WARN}] ไม่มีล็อต/วันหมดอายุ ({len(no_batch)} รายการ)")
        for code, title in no_batch:
            print(f"          {code:<19} {title}")
        print("          → ตอบคำถาม 'หมดอายุเมื่อไหร่' ไม่ได้ ซึ่งเป็นจุดขายของเรา\n")

    ready = len(rows) - len({c for c, _ in no_stock} | {c for c, _ in no_price})
    print(f"  พร้อมขายผ่าน AI ได้จริงตอนนี้: {ready} จาก {len(rows)} รายการ")
    print()


if __name__ == "__main__":
    main()
