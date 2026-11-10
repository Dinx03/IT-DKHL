# แก้ปุ่ม Download ในตารางย่อย (Bulk Edit) ให้ใส่ BOM
# ไฟล์นี้สร้างในเบราว์เซอร์ด้วย JavaScript จึงไม่เกี่ยวกับการแก้ฝั่งเซิร์ฟเวอร์
import shutil

P = "/home/frappe/frappe-bench/apps/frappe/frappe/public/js/frappe/utils/tools.js"
shutil.copy(P, "/tmp/tools.js.backup")

s = open(P, encoding="utf-8").read()

if "ONA Healthy" in s:
    print("ALREADY_PATCHED")
else:
    old1 = 'var blob_object = new Blob([csv_data], { type: "text/csv;charset=UTF-8" });'
    new1 = ('// ONA Healthy: \\ufeff = BOM ทำให้ Excel บน Windows อ่านภาษาไทยถูก\n'
            '\t\tvar blob_object = new Blob(["\\ufeff" + csv_data], { type: "text/csv;charset=UTF-8" });')

    old2 = 'a.href = "data:attachment/csv," + encodeURIComponent(csv_data);'
    new2 = ('a.href = "data:attachment/csv," + encodeURIComponent("\\ufeff" + csv_data); '
            '// ONA Healthy: BOM')

    n = 0
    if old1 in s:
        s = s.replace(old1, new1, 1)
        n += 1
    else:
        print("WARN: ไม่พบ blob_object")
    if old2 in s:
        s = s.replace(old2, new2, 1)
        n += 1
    else:
        print("WARN: ไม่พบ data:attachment")

    open(P, "w", encoding="utf-8").write(s)
    print("PATCHED_COUNT:", n)

for i, line in enumerate(open(P, encoding="utf-8"), 1):
    if "ufeff" in line or "ONA Healthy" in line:
        print(f"  {i}: {line.rstrip()[:100]}")
