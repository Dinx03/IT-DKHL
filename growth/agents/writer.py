"""
writer.py — เขียนคอนเทนต์ต่อแพลตฟอร์ม

คู่กับ Reach Guard เป็น generator ⇄ critic:
    Writer เขียน → Guard ค้าน → Writer เขียนใหม่ตาม fix_hint → Guard ตรวจซ้ำ

Writer ไม่เคยตรวจงานตัวเองว่าผ่านกฎไหม และ Guard ไม่เคยเขียนแทน
ถ้ารวมสองบทบาทเข้าด้วยกัน มันจะแก้ให้ผ่านการตรวจของตัวเอง การตรวจก็หมดความหมาย

WriterInput บังคับไว้แล้วว่า attempt > 1 ต้องแนบ guard_feedback
ไม่งั้นรอบสองจะเขียนผิดซ้ำเดิมแล้วเสียค่าโมเดลฟรี
"""

from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from .agents import DraftMedia, WriterInput, WriterOutput
from .common import AgentError, AgentResult, EventDraft, Usage


class WriterDraft(BaseModel):
    """รูปร่างที่ให้โมเดลกรอก — แยกจาก WriterOutput เพื่อไม่เอา field
    ที่โมเดลไม่ควรตัดสินใจเอง (เช่น ธง AIGC ซึ่งมาจาก metadata ของสื่อจริง)"""

    body: str = Field(description="เนื้อโพสต์ พร้อมโพสต์ได้เลย")
    hashtags: list[str] = Field(default_factory=list, description="3-6 อัน ไม่ต้องมี #")
    self_check_th: list[str] = Field(default_factory=list,
                                     description="สั้นๆ ว่าเลี่ยงอะไรไปบ้าง")


def _render(template: str, inp: WriterInput) -> str:
    f = inp.dna.facets
    voice = f.get("voice", {})
    tone = voice.get("tone_by_platform", {}).get(inp.platform, {})
    fb = ""
    if inp.guard_feedback:
        g = inp.guard_feedback
        fb = ("## รอบที่แล้วไม่ผ่านการตรวจ\n"
              + "\n".join(f"- {m}" for m in g.findings_th)
              + "\n\nต้องแก้แบบนี้:\n"
              + "\n".join(f"- {h}" for h in g.fix_hints_th)
              + ("\n\nห้ามใช้คำเหล่านี้อีก: " + ", ".join(g.must_not_repeat)
                 if g.must_not_repeat else "")
              + "\n\nเขียนใหม่ทั้งโพสต์ ไม่ใช่แก้เฉพาะจุด")
    return (template
            .replace("{brand_name}", f.get("identity", {}).get("display_name", "แบรนด์"))
            .replace("{platform}", inp.platform)
            .replace("{identity}", json.dumps(f.get("identity", {}), ensure_ascii=False))
            .replace("{audience}", json.dumps(f.get("audience", {}), ensure_ascii=False))
            .replace("{platform_voice}", json.dumps(tone, ensure_ascii=False))
            .replace("{avoid}", "\n".join(f"- {x}" for x in voice.get("avoid_phrases_th", [])))
            .replace("{claims}", json.dumps(f.get("claims_policy", {}), ensure_ascii=False))
            .replace("{topic}", inp.brief.topic_th)
            .replace("{angle}", inp.brief.angle_th)
            .replace("{strategy}", inp.brief.strategy)
            .replace("{must_include}", ", ".join(inp.brief.must_include_th) or "-")
            .replace("{feedback}", fb))


def run(inp: WriterInput, *, provider, prompt_template: str,
        model: str, media: list[DraftMedia] | None = None) -> AgentResult[WriterOutput]:
    started = time.perf_counter()
    system = _render(prompt_template, inp)
    user = (f"เขียนโพสต์สำหรับ {inp.platform} ตามโจทย์ข้างบน"
            + (f" (รอบที่ {inp.attempt})" if inp.attempt > 1 else ""))

    try:
        draft, usage = provider.parse(
            model=model, system=system,
            messages=[{"role": "user", "content": user}],
            schema=WriterDraft, max_tokens=2000)
    except Exception as exc:                                   # noqa: BLE001
        return AgentResult[WriterOutput](
            ok=False,
            error=AgentError(code="model_error", message=f"{type(exc).__name__}: {exc}",
                             retryable=True),
            usage=Usage(model=model,
                        latency_ms=int((time.perf_counter() - started) * 1000)),
            events=[EventDraft(type="agent.failed", actor_id="writer",
                               payload={"attempt": inp.attempt, "error": str(exc)})])

    ms = media or []
    # ธง AIGC มาจาก metadata ของสื่อจริง ไม่ใช่คำบอกของโมเดล
    # Reach Guard จะตรวจซ้ำอิสระอีกชั้นอยู่ดี
    needs_label = any(m.generator and m.generator.startswith("ai:")
                      and (m.depicts_realistic_person or m.depicts_realistic_scene)
                      for m in ms)

    out = WriterOutput(
        body=draft.body.strip(),
        hashtags=[h.lstrip("#") for h in draft.hashtags][:6],
        media=ms,
        aigc_label_required=needs_label,
        grounded_on=[str(k.doc_id) for k in inp.knowledge],
        self_check_th=draft.self_check_th)

    return AgentResult[WriterOutput](
        ok=True, output=out, usage=usage,
        events=[EventDraft(
            type="content.generated", subject_type="content_variant",
            actor_id="writer",
            payload={"platform": inp.platform, "attempt": inp.attempt,
                     "topic": inp.brief.topic_th, "chars": len(out.body),
                     "hashtags": out.hashtags,
                     "had_feedback": inp.guard_feedback is not None})])
