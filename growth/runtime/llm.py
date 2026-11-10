"""
llm.py — ชั้นเชื่อมโมเดล

ทำไมต้องมีชั้นนี้ แทนที่จะเรียก SDK ตรงๆ จากใน agent:
  1. ทดสอบได้โดยไม่ต้องมีคีย์และไม่เสียเงิน — StubProvider ให้ผลเดิมทุกครั้ง
  2. เปลี่ยนผู้ให้บริการได้โดยไม่ต้องแก้ agent สักตัว
  3. คิดต้นทุนเป็นบาทที่จุดเดียว แล้วส่งเข้า agent_runs

ตอนนี้มี provider จริง 1 ตัว (Anthropic) เพราะยังไม่ได้เลือกเจ้าอื่น
ถ้าจะเพิ่มเจ้าใหม่ ให้ทำตาม Protocol ข้างล่างพอ ไม่ต้องแตะ agent
"""

from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel

from ..agents.common import Strict, Usage
from .db import _load_env

# ── ราคาต่อ 1 ล้าน token (USD) ────────────────────────────────
# ⚠️ ต้องอัปเดตเมื่อผู้ให้บริการเปลี่ยนราคา — ตัวเลขนี้ไหลเข้า agent_runs.cost_thb
PRICING_USD: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-opus-5":         (5.00, 25.00),
    "claude-sonnet-5":       (2.00, 10.00),
    "claude-haiku-4-5":      (1.00, 5.00),
    # Google — ai.google.dev/gemini-api/docs/pricing ตรวจเมื่อ 13 ก.ย. 2026
    "gemini-3.5-flash":      (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3-flash":        (0.50, 3.00),
    "gemini-2.5-flash":      (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro":        (1.25, 10.00),
    "gemini-3.1-pro":        (2.00, 12.00),
}
USD_THB = Decimal("36")          # อัตราแลกเปลี่ยนโดยประมาณ ปรับได้ใน .env

# โมเดลที่ใช้ต่อ agent — แก้ที่นี่จุดเดียว
# เลือกเจ้าไหนก็ได้ต่อ agent — Router ดูจากชื่อโมเดลเอง
# ตอนนี้ใช้ Gemini ทั้งหมดเพราะมีแค่คีย์นั้น สลับกลับเป็น claude-* ได้ทันทีถ้ามีคีย์
MODEL_FOR: dict[str, str] = {
    "concierge":  "gemini-3.5-flash",       # ตอบลูกค้า + เรียก tool ต้องแม่น
    "scorer":     "gemini-2.5-flash-lite",  # จัดประเภท งานแคบ เรียกบ่อยสุด ถูกสุด
    "closer":     "gemini-2.5-flash-lite",  # สรุป 3 บรรทัดให้คนกดอนุมัติอ่าน
    "writer":     "gemini-3.5-flash",
    "strategist": "gemini-3.5-flash",
    "analyst":    "gemini-3.5-flash",
}

_FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1"}


class ToolUse(Strict):
    id: str
    name: str
    input: dict[str, Any]


class Completion(Strict):
    text: str = ""
    tool_uses: list[ToolUse] = []
    stop_reason: str = "end_turn"
    refusal_category: str | None = None
    usage: Usage
    raw_content: list[Any] = []      # ส่งกลับเข้า messages ในรอบถัดไปแบบไม่แก้


def _cost_thb(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    inp, out = PRICING_USD.get(model, (0.0, 0.0))
    usd = (Decimal(prompt_tokens) / 1_000_000 * Decimal(str(inp))
           + Decimal(completion_tokens) / 1_000_000 * Decimal(str(out)))
    return (usd * USD_THB).quantize(Decimal("0.0001"))


class LLMProvider(Protocol):
    name: str

    def complete(self, *, model: str, system: str, messages: list[dict],
                 tools: list[dict] | None = None,
                 max_tokens: int = 4096) -> Completion: ...

    def parse(self, *, model: str, system: str, messages: list[dict],
              schema: type[BaseModel], max_tokens: int = 2048) -> tuple[Any, Usage]: ...


# ─────────────────────────────────────────────────────────────
# Provider จริง
# ─────────────────────────────────────────────────────────────

class AnthropicProvider:
    """ต้องมี ANTHROPIC_API_KEY ใน growth/.env หรือ environment"""

    name = "anthropic"

    def __init__(self) -> None:
        import anthropic                                  # import แบบ lazy
        key = os.environ.get("ANTHROPIC_API_KEY") or _load_env().get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ยังไม่มี ANTHROPIC_API_KEY — ใส่ใน growth/.env "
                "หรือใช้ StubProvider ไปก่อน (ดู get_provider)")
        self._c = anthropic.Anthropic(api_key=key, timeout=60.0)

    def complete(self, *, model, system, messages, tools=None, max_tokens=4096) -> Completion:
        started = time.perf_counter()
        kw: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens, "system": system,
            "messages": messages, "thinking": {"type": "adaptive"},
        }
        if tools:
            kw["tools"] = tools

        if model in _FALLBACK_MODELS:
            # ถ้าโมเดลปฏิเสธคำขอ ให้เซิร์ฟเวอร์สลับไปรุ่นอื่นให้อัตโนมัติ
            # ดีกว่าปล่อยให้ลูกค้าเจอความเงียบ
            r = self._c.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
        else:
            r = self._c.messages.create(**kw)

        latency = int((time.perf_counter() - started) * 1000)
        usage = Usage(
            model=model,
            prompt_tokens=r.usage.input_tokens,
            completion_tokens=r.usage.output_tokens,
            cached_tokens=getattr(r.usage, "cache_read_input_tokens", 0) or 0,
            cost_thb=_cost_thb(model, r.usage.input_tokens, r.usage.output_tokens),
            latency_ms=latency,
        )

        # ต้องเช็ค stop_reason ก่อนอ่าน content เสมอ
        if r.stop_reason == "refusal":
            cat = getattr(getattr(r, "stop_details", None), "category", None)
            return Completion(stop_reason="refusal", refusal_category=cat, usage=usage)

        text = "".join(b.text for b in r.content if b.type == "text")
        tool_uses = [ToolUse(id=b.id, name=b.name, input=dict(b.input))
                     for b in r.content if b.type == "tool_use"]
        return Completion(text=text, tool_uses=tool_uses, stop_reason=r.stop_reason,
                          usage=usage, raw_content=list(r.content))

    def parse(self, *, model, system, messages, schema, max_tokens=2048):
        started = time.perf_counter()
        r = self._c.messages.parse(
            model=model, max_tokens=max_tokens, system=system,
            messages=messages, output_format=schema)
        usage = Usage(
            model=model, prompt_tokens=r.usage.input_tokens,
            completion_tokens=r.usage.output_tokens,
            cost_thb=_cost_thb(model, r.usage.input_tokens, r.usage.output_tokens),
            latency_ms=int((time.perf_counter() - started) * 1000))
        return r.parsed_output, usage


# ─────────────────────────────────────────────────────────────
# Google Gemini
# ─────────────────────────────────────────────────────────────

def _gemini_schema(schema: dict, defs: dict | None = None) -> dict:
    """แปลง JSON Schema ของ Pydantic เป็นรูปที่ Gemini รับ

    Gemini ไม่รับ $ref / $defs / anyOf และต้องการชื่อชนิดเป็นตัวพิมพ์ใหญ่
    ตัวแปลงนี้คลี่ $ref ออกและเลือกชนิดที่ไม่ใช่ null จาก anyOf
    (ทดสอบกับ ScorerOutput ที่มี model ซ้อนแล้วผ่าน)"""
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return _gemini_schema(defs[schema["$ref"].split("/")[-1]], defs)
    if "anyOf" in schema:
        real = [x for x in schema["anyOf"] if x.get("type") != "null"]
        return _gemini_schema(real[0], defs) if real else {"type": "STRING"}
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "string")
    out: dict[str, Any] = {}
    if t:
        out["type"] = t.upper()
    if schema.get("description"):
        out["description"] = schema["description"][:300]
    if schema.get("enum"):
        out["enum"] = [str(e) for e in schema["enum"]]
    if t == "object":
        out["properties"] = {k: _gemini_schema(v, defs)
                             for k, v in (schema.get("properties") or {}).items()}
        if schema.get("required"):
            out["required"] = list(schema["required"])
    if t == "array":
        out["items"] = _gemini_schema(schema.get("items") or {"type": "string"}, defs)
    return out


class GeminiProvider:
    """ต้องมี GEMINI_API_KEY ใน growth/.env

    ใช้ REST ตรงแทน SDK เพราะไม่อยากเพิ่ม dependency และรูปร่างที่ต้องใช้จริง
    มีแค่ 3 อย่าง (ข้อความ · structured output · function calling) ซึ่งตรวจสอบแล้ว
    """

    name = "gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self) -> None:
        key = os.environ.get("GEMINI_API_KEY") or _load_env().get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("ยังไม่มี GEMINI_API_KEY ใน growth/.env")
        self._h = {"x-goog-api-key": key, "Content-Type": "application/json"}
        self._tool_names: dict[str, str] = {}

    def _post(self, model: str, body: dict) -> dict:
        import requests
        r = requests.post(f"{self.BASE}/{model}:generateContent", headers=self._h,
                          timeout=90, data=json.dumps(body, ensure_ascii=False).encode())
        if not r.ok:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _usage(self, model: str, d: dict, started: float) -> Usage:
        u = d.get("usageMetadata") or {}
        inp = int(u.get("promptTokenCount") or 0)
        # token ที่ใช้ "คิด" คิดเงินในอัตรา output — ไม่นับรวมคือประเมินต่ำกว่าจริงมาก
        out = int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0)
        return Usage(model=model, prompt_tokens=inp, completion_tokens=out,
                     cached_tokens=int(u.get("cachedContentTokenCount") or 0),
                     cost_thb=_cost_thb(model, inp, out),
                     latency_ms=int((time.perf_counter() - started) * 1000))

    def _contents(self, messages: list[dict]) -> list[dict]:
        """แปลงข้อความรูปแบบ Anthropic เป็นรูปแบบ Gemini

        agent เขียนขึ้นในรูปเดียว ไม่ต้องรู้ว่าปลายทางเป็นเจ้าไหน
        การแปลงอยู่ที่นี่จุดเดียว"""
        out: list[dict] = []
        for m in messages:
            role = "model" if m.get("role") == "assistant" else "user"
            c = m.get("content")
            if isinstance(c, str):
                out.append({"role": role, "parts": [{"text": c}]})
                continue
            parts: list[dict] = []
            for b in (c or []):
                if not isinstance(b, dict):
                    continue
                if "functionCall" in b or "thoughtSignature" in b or (
                        "text" in b and "type" not in b):
                    parts.append(b)
                elif b.get("type") == "tool_result":
                    name = self._tool_names.get(b.get("tool_use_id", ""), "unknown")
                    try:
                        resp = json.loads(b.get("content") or "{}")
                    except Exception:                              # noqa: BLE001
                        resp = {"result": str(b.get("content"))}
                    if not isinstance(resp, dict):
                        resp = {"result": resp}
                    parts.append({"functionResponse": {"name": name, "response": resp}})
                elif b.get("type") == "text":
                    parts.append({"text": b.get("text", "")})
            if parts:
                out.append({"role": role, "parts": parts})
        while out and out[0]["role"] != "user":
            out.pop(0)
        return out or [{"role": "user", "parts": [{"text": "-"}]}]

    def complete(self, *, model, system, messages, tools=None, max_tokens=4096) -> Completion:
        started = time.perf_counter()
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self._contents(messages),
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t["name"], "description": t.get("description", ""),
                 "parameters": _gemini_schema(t["input_schema"])} for t in tools]}]

        d = self._post(model, body)
        usage = self._usage(model, d, started)
        cands = d.get("candidates") or []
        if not cands:
            fb = (d.get("promptFeedback") or {}).get("blockReason")
            return Completion(stop_reason="refusal", refusal_category=fb or "no_candidate",
                              usage=usage)

        cand = cands[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if "text" in p)
        tool_uses = []
        for p in parts:
            fc = p.get("functionCall")
            if fc:
                tid = fc.get("id") or f"gm-{len(self._tool_names)}"
                self._tool_names[tid] = fc["name"]
                tool_uses.append(ToolUse(id=tid, name=fc["name"],
                                         input=dict(fc.get("args") or {})))
        if len(self._tool_names) > 500:
            self._tool_names.clear()

        if cand.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            return Completion(stop_reason="refusal",
                              refusal_category=cand["finishReason"], usage=usage)
        return Completion(text=text, tool_uses=tool_uses,
                          stop_reason="tool_use" if tool_uses else "end_turn",
                          usage=usage, raw_content=parts)

    def parse(self, *, model, system, messages, schema, max_tokens=2048):
        started = time.perf_counter()
        d = self._post(model, {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self._contents(messages),
            "generationConfig": {"maxOutputTokens": max_tokens,
                                 "responseMimeType": "application/json",
                                 "responseSchema": _gemini_schema(schema.model_json_schema())},
        })
        usage = self._usage(model, d, started)
        cands = d.get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini ไม่คืนคำตอบ: {str(d)[:200]}")
        txt = "".join(p.get("text", "")
                      for p in (cands[0].get("content") or {}).get("parts") or [])
        return schema.model_validate_json(txt), usage


# ─────────────────────────────────────────────────────────────
# ตัวเลือกเส้นทาง — ดูจากชื่อโมเดลว่าส่งไปเจ้าไหน
# ─────────────────────────────────────────────────────────────

class Router:
    """ทุกการเรียกมี model มาด้วยอยู่แล้ว จึงเลือกปลายทางจากชื่อโมเดลได้เลย
    ผสมสองเจ้าในระบบเดียวได้ — Concierge ใช้เจ้าหนึ่ง Scorer ใช้อีกเจ้า
    agent ไม่ต้องรู้เรื่องนี้เลยสักตัว"""

    name = "router"

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def _pick(self, model: str):
        family = "gemini" if str(model).startswith("gemini") else "anthropic"
        if family not in self._cache:
            try:
                self._cache[family] = (GeminiProvider() if family == "gemini"
                                       else AnthropicProvider())
            except Exception:                                      # noqa: BLE001
                self._cache[family] = StubProvider()
        return self._cache[family]

    def complete(self, *, model, **kw) -> Completion:
        return self._pick(model).complete(model=model, **kw)

    def parse(self, *, model, **kw):
        return self._pick(model).parse(model=model, **kw)


# ─────────────────────────────────────────────────────────────
# Provider ปลอม — ทดสอบทั้งระบบได้โดยไม่ต้องมีคีย์และไม่เสียเงิน
# ─────────────────────────────────────────────────────────────

class StubProvider:
    """เลียนแบบพฤติกรรมโมเดลแบบตายตัว เพื่อทดสอบ "ท่อ" ว่าต่อถูก

    ไม่ได้เลียนแบบความฉลาด — เลียนแบบ *รูปร่างของคำตอบ* เท่านั้น
    ใช้ตรวจว่า tool loop ทำงาน · grounding ถูกบังคับ · ต้นทุนถูกบันทึก
    """

    name = "stub"

    def __init__(self, script: list[Completion] | None = None) -> None:
        self._script = script or []
        self._i = 0

    def complete(self, *, model, system, messages, tools=None, max_tokens=4096) -> Completion:
        if self._i < len(self._script):
            c = self._script[self._i]
            self._i += 1
            return c

        last = messages[-1]
        has_tool_result = (isinstance(last.get("content"), list)
                           and any(isinstance(b, dict) and b.get("type") == "tool_result"
                                   for b in last["content"]))
        u = Usage(model=model, prompt_tokens=800, completion_tokens=120,
                  cost_thb=_cost_thb(model, 800, 120), latency_ms=5)

        if has_tool_result and tools:
            # รอบที่ 2: มีผล tool แล้ว ประกอบคำตอบ
            facts = []
            for b in last["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    facts.append(str(b.get("content"))[:300])
            return Completion(
                text="[stub] ตอบจากข้อมูลที่ดึงมา: " + " | ".join(facts),
                stop_reason="end_turn", usage=u)

        if tools:
            # รอบแรก: ขอข้อมูลก่อน
            return Completion(
                tool_uses=[ToolUse(id="stub-1", name="erp_stock_lookup",
                                   input={"erp_item_code": "ONATO-JUICE-75"})],
                stop_reason="tool_use", usage=u)

        return Completion(text="[stub] ตอบแบบไม่ใช้ tool", stop_reason="end_turn", usage=u)

    def parse(self, *, model, system, messages, schema, max_tokens=2048):
        u = Usage(model=model, prompt_tokens=400, completion_tokens=60,
                  cost_thb=_cost_thb(model, 400, 60), latency_ms=4)
        name = schema.__name__

        if name == "WriterDraft":
            # สคริปต์เพื่อพิสูจน์ว่าลูป generator→critic ทำงานจริง ไม่ใช่ความฉลาด:
            # รอบแรกจงใจเขียนคำที่ผิดกฎ รอบสอง (มี feedback แล้ว) เขียนให้ผ่าน
            retry = "รอบที่แล้วไม่ผ่านการตรวจ" in system
            if retry:
                body = ("[stub] มะเขือเทศจากสวนเราเก็บตอนเช้าแล้วคั้นในวันเดียวกัน "
                        "ไม่เติมน้ำตาลและไม่ผสมน้ำ ดื่มวันละขวดตอนเช้าก่อนอาหาร\n"
                        "คุณดื่มน้ำผักผลไม้ตอนไหนของวัน")
                checks = ["ไม่ขอ engagement ตรงๆ", "ไม่เคลมผลลัพธ์", "เปลี่ยนเป็นคำถามปลายเปิด"]
            else:
                body = ("[stub] แท็กเพื่อนที่อยากผิวขาวใสใน 7 วัน "
                        "คอมเมนต์คำว่าสนใจ แล้วเราจะทักไปหา")
                checks = ["(stub รอบแรก จงใจใส่คำผิดกฎเพื่อทดสอบด่านตรวจ)"]
            return schema.model_validate(
                {"body": body, "hashtags": ["onahealthy", "น้ำมะเขือเทศ", "ของดีจากสวน"],
                 "self_check_th": checks}), u

        if name == "LlmVerdict":
            body = " ".join(str(m.get("content", "")) for m in messages)
            if "โพสต์เดิมของแบรนด์" in body:
                new, _, olds = body.partition("## โพสต์เดิมของแบรนด์")
                new = new.split("## โพสต์ใหม่ที่จะลง")[-1].strip()
                core = "".join(ch for ch in new if ch.isalnum())[:60]
                dup = bool(core) and core in "".join(
                    ch for ch in olds if ch.isalnum())
                return schema.model_validate(
                    {"risk": 90 if dup else 15,
                     "quote_th": new[:60] if dup else "",
                     "reason_th": ("[stub] ข้อความเหมือนโพสต์เดิมเกือบทั้งหมด"
                                   if dup else "[stub] ไม่ซ้ำกับของเดิม")}), u
            hard = ["รักษา", "หาย", "ป้องกันโรค", "การันตี", "ลดน้ำหนัก",
                    "ขาวขึ้น", "แก้สิว", "ดีกว่ายา"]
            soft = ["ดีท็อกซ์", "ล้างสารพิษ", "เร่งการเผาผลาญ", "งานวิจัย"]
            hit = next((w for w in hard if w in body), None)
            if hit:
                return schema.model_validate(
                    {"risk": 85, "quote_th": hit,
                     "reason_th": "[stub] เคลมสรรพคุณเกินที่ อย. อนุญาต "
                                  "ให้เปลี่ยนเป็นพูดถึงส่วนประกอบและวิธีใช้แทน"}), u
            hit = next((w for w in soft if w in body), None)
            if hit:
                return schema.model_validate(
                    {"risk": 55, "quote_th": hit,
                     "reason_th": "[stub] คำกว้างที่ตีความเป็นเคลมสุขภาพได้"}), u
            return schema.model_validate(
                {"risk": 10, "quote_th": "", "reason_th": "[stub] ไม่พบเคลมที่มีปัญหา"}), u

        if name == "AnalystReport":
            # จงใจเสนอ 1 ข้อที่ผิดกฎ (แตะ claims_policy) เพื่อพิสูจน์ว่า validator ตัดทิ้งจริง
            return schema.model_validate({
                "digest_th": "[stub] คำที่โดน Reach Guard จับบ่อยที่สุดคือ engagement bait "
                             "ควรเพิ่มเข้ารายการคำต้องห้ามเพื่อไม่ให้ Writer เขียนซ้ำ",
                "changes": [
                    {"facet_path": "/voice/avoid_phrases_th/-", "operation": "add",
                     "value_json": "\"ผิวขาวใสใน 7 วัน\"",
                     "rationale_th": "[stub] โดนกฎ meta.bait จับซ้ำหลายครั้งในรอบ 30 วัน",
                     "evidence_refs": ["guard_stats:meta.bait.comment"], "confidence": 0.85},
                    {"facet_path": "/claims_policy/banned_claim_types/-", "operation": "add",
                     "value_json": "\"detox\"",
                     "rationale_th": "[stub] จงใจผิดกฎเพื่อทดสอบ guardrail",
                     "evidence_refs": ["x"], "confidence": 0.9},
                    {"facet_path": "/learned/top_questions_th", "operation": "replace",
                     "value_json": "[\"ยังมีของไหม\", \"ราคาเท่าไหร่\"]",
                     "rationale_th": "[stub] สองคำถามนี้ถามบ่อยที่สุด",
                     "evidence_refs": ["questions"], "confidence": 0.4}
                ]}), u

        if name == "_Summary":
            return schema.model_validate(
                {"summary_th": "[stub] ลูกค้าสนใจน้ำมะเขือเทศ แจ้งจำนวนแล้ว "
                               "ถามวิธีโอน ยังไม่ได้แจ้งที่อยู่จัดส่ง"}), u

        if name == "StrategistPlan":
            import re as _re
            from datetime import date as _d, timedelta as _td
            m = _re.search(r"เริ่มจาก (\d{4}-\d{2}-\d{2})", system)
            start = _d.fromisoformat(m.group(1)) if m else _d.today()
            # เลือกเฉพาะสินค้าที่ "มีของ" จาก inventory ที่ฝังมาใน system
            in_stock = _re.findall(r"- ([A-Z0-9-]+) \(.*?คงเหลือ ([0-9.]+)", system)
            have = [c for c, q in in_stock if float(q) > 0]
            gone = [c for c, q in in_stock if float(q) <= 0]
            briefs = [{
                "slot_date": str(start), "platforms": ["instagram"],
                "topic_th": "ที่มาของมะเขือเทศในขวด", "angle_th": "เล่ากระบวนการเก็บและคั้น",
                "strategy": "ให้ความรู้", "product_refs": have[:1],
                "must_include_th": ["บอกที่มาของวัตถุดิบ"],
                "rationale_th": "[stub] สินค้าตัวนี้มีของจริงในคลัง จึงดันได้",
            }, {
                "slot_date": str(start + _td(days=1)), "platforms": ["facebook"],
                "topic_th": "วิธีดื่มให้ได้ประโยชน์", "angle_th": "แนะนำช่วงเวลาและปริมาณ",
                "strategy": "ขายตรง", "product_refs": have[:1],
                "must_include_th": ["บอกวิธีดื่มและปริมาณที่แนะนำ"],
                "rationale_th": "[stub] มีของพร้อมส่ง จึงชวนซื้อได้",
            }]
            if gone:
                # จงใจใส่แผนผิดกฎ 1 อัน เพื่อพิสูจน์ว่าด่านตรวจหลังโมเดลตัดทิ้งจริง
                briefs.append({
                    "slot_date": str(start + _td(days=2)), "platforms": ["instagram"],
                    "topic_th": "โปรโมตสินค้าที่หมดสต็อก", "angle_th": "ชวนซื้อ",
                    "strategy": "ขายตรง", "product_refs": gone[:1],
                    "must_include_th": [], "rationale_th": "[stub] จงใจผิดกฎเพื่อทดสอบ"})
            return schema.model_validate(
                {"briefs": briefs,
                 "digest_th": "[stub] แผนตัวอย่างจากสต็อกจริง"}), u

        text = json.dumps(messages, ensure_ascii=False)
        # ให้คะแนนตามคำบ่งชี้ เพื่อให้เทสต์คาดเดาผลได้
        score = 20
        for kw, pts in (("สั่ง", 40), ("โอน", 30), ("เท่าไหร่", 15), ("ส่งเมื่อไหร่", 15)):
            if kw in text:
                score += pts
        return schema.model_validate({
            "score": min(score, 100),
            "signals": {"intent": "ready_to_buy" if score >= 70 else "browsing",
                        "items": [], "qty": None, "budget_signal": "โอน" in text,
                        "urgency": "now" if "ด่วน" in text else "none",
                        "blockers_th": []},
            "rationale_th": "[stub] ให้คะแนนจากคำบ่งชี้",
        }), u


_cached: LLMProvider | None = None


def get_provider(force_stub: bool = False) -> LLMProvider:
    """คืน Router ที่เลือกเจ้าตามชื่อโมเดล — เจ้าไหนไม่มีคีย์จะตกไปใช้ stub
    ระบบจึงรันได้เสมอ และคำตอบจาก stub ขึ้นต้นด้วย [stub] เห็นชัด"""
    global _cached
    if force_stub:
        return StubProvider()
    if _cached is None:
        _cached = Router()
    return _cached


def provider_is_real(model: str | None = None) -> bool:
    """มีคีย์จริงสำหรับโมเดลที่ระบุหรือยัง (ค่าเริ่มต้นดูของ Concierge)"""
    p = get_provider()
    if not isinstance(p, Router):
        return p.name != "stub"
    return p._pick(model or MODEL_FOR["concierge"]).name != "stub"
