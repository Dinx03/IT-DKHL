"""ค่าตั้งต้นที่ทุกแล็บใช้ร่วมกัน"""
import anthropic

# เปลี่ยนเป็น "claude-sonnet-5" หรือ "claude-haiku-4-5" ได้ถ้าอยากประหยัด
MODEL = "claude-opus-5"

# ราคา USD ต่อ 1 ล้าน token (input, output) ข้อมูล ณ มิ.ย. 2026
PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# ถ้า Opus 5 ปฏิเสธคำขอ ให้ API ส่งต่อไปโมเดลสำรองอัตโนมัติ (beta)
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# อ่าน API key จาก environment variable ANTHROPIC_API_KEY (ห้าม hardcode key ในโค้ด)
client = anthropic.Anthropic()


def create(**kwargs):
    """เรียก messages.create พร้อมเปิด refusal fallback"""
    kwargs.setdefault("model", MODEL)
    return client.beta.messages.create(
        betas=[FALLBACK_BETA], fallbacks="default", **kwargs
    )


def stream(**kwargs):
    """เรียก messages.stream พร้อมเปิด refusal fallback"""
    kwargs.setdefault("model", MODEL)
    return client.beta.messages.stream(
        betas=[FALLBACK_BETA], fallbacks="default", **kwargs
    )


def text_of(response) -> str:
    """ดึงเฉพาะข้อความออกจาก content blocks (ข้าม thinking block)"""
    return "".join(b.text for b in response.content if b.type == "text")


def cost_usd(usage, model: str) -> float:
    price_in, price_out = PRICES.get(model, PRICES["claude-opus-5"])
    return (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000


def report(response) -> None:
    """พิมพ์สถิติของคำตอบ"""
    u = response.usage
    print("-" * 50)
    print(f"model        : {response.model}")
    print(f"stop_reason  : {response.stop_reason}")
    print(f"input tokens : {u.input_tokens}")
    print(f"output tokens: {u.output_tokens}")
    print(f"cost         : ${cost_usd(u, response.model):.5f}")
