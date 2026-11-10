# แล็บบทที่ 1

## ขั้นที่ 0 — เตรียมเครื่อง (ทำครั้งเดียว)

1. Python — เครื่องนี้มี Python 3.14 อยู่แล้ว แต่เรียกผ่านคำสั่ง `py` (คำสั่ง `python` เฉยๆ จะเปิด Microsoft Store)
2. สมัครและรับ API key ที่ https://console.anthropic.com (ต้องเติมเครดิตเอง ขั้นต่ำประมาณ $5)
   > ⚠️ API key เปรียบเหมือนรหัสผ่าน **ห้ามส่งให้ใคร ห้าม commit ขึ้น GitHub และห้ามวางในแชท**
3. เปิด PowerShell ในโฟลเดอร์นี้ แล้วรัน:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1   # หลัง activate แล้ว ใช้คำสั่ง python ได้ตามปกติ
pip install -U -r requirements.txt
```

4. ตั้งค่า API key สำหรับหน้าต่าง PowerShell นี้ (พิมพ์เองในเครื่อง):

```powershell
$env:ANTHROPIC_API_KEY = "วาง-key-ของคุณ-ตรงนี้"
```

## ขั้นที่ 1–4 — รันทีละไฟล์ อ่านโค้ดให้เข้าใจก่อนรัน

| ไฟล์ | เรียนเรื่อง |
|---|---|
| `01_first_call.py` | เรียก API ครั้งแรก, อ่าน `stop_reason` และ `usage`, คำนวณเงิน |
| `02_system_prompt.py` | ผลของ system prompt ต่อคำตอบ |
| `03_streaming.py` | ข้อความขึ้นทีละส่วน |
| `04_chat_memory.py` | แชทที่จำบทสนทนาได้ (และดู token ที่เพิ่มขึ้นทุกรอบ) |
| `05_effort.py` | เปรียบเทียบ effort `low` กับ `high` |

```powershell
python 01_first_call.py
```

รันเสร็จแล้วไปทำโจทย์ต่อที่ [../exercises.md](../exercises.md)

## เจอ error?
| Error | สาเหตุ |
|---|---|
| `AuthenticationError` | API key ผิด หรือยังไม่ได้ตั้ง `$env:ANTHROPIC_API_KEY` |
| `NotFoundError` | ชื่อโมเดลผิด |
| `BadRequestError` ที่พูดถึง credit | เครดิตในบัญชีหมด |
| `TypeError: ... unexpected keyword 'fallbacks'` | SDK เก่าเกินไป ให้รัน `pip install -U anthropic` |
| `.ps1 cannot be loaded` | รัน `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` ก่อน |

ถ้ายังแก้ไม่ได้ ให้คัดลอก error มาถาม Claude ได้เลย
