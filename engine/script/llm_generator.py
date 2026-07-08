"""LLMScriptGenerator — 주입된 LLMProvider 로 문장 단위 대본 JSON 을 생성한다.

실패/파싱오류 시 MockScriptGenerator 로 폴백한다.
"""

from __future__ import annotations

import json
import logging
import re

from engine.models import Clip, Scene, SCENE_ROLES
from .base import SCRIPT_RULES, ScriptGenerator
from .mock_generator import MockScriptGenerator

logger = logging.getLogger(__name__)

_SYSTEM = (
    "너는 한국 숏폼(쇼츠/릴스) 대본 작가다. 문제해결형·후킹 중심으로 "
    "짧고 강한 문장을 쓴다. 과장광고 표현은 피한다. 반드시 JSON 배열만 출력한다."
)


class LLMScriptGenerator(ScriptGenerator):
    def __init__(self, llm) -> None:
        self._llm = llm

    def generate(self, *, product_ko: str, category: str,
                 top_clips: list[Clip], selected_text: str = "",
                 tone: str = "", product_zh: str = "",
                 source_site: str = "") -> list[Scene]:
        prompt = self._build_prompt(
            product_ko, category, top_clips, selected_text, tone,
            product_zh=product_zh, source_site=source_site,
        )
        try:
            raw = self._llm.complete(prompt, system=_SYSTEM, max_tokens=1500)
            scenes = self._parse(raw)
            if scenes:
                return scenes
            logger.warning("대본 파싱 실패 → Mock 폴백")
        except Exception as exc:  # noqa: BLE001
            logger.warning("대본 생성 실패(%s) → Mock 폴백", exc)
        return MockScriptGenerator().generate(
            product_ko=product_ko, category=category,
            top_clips=top_clips, selected_text=selected_text, tone=tone,
            product_zh=product_zh, source_site=source_site,
        )

    def _build_prompt(self, product_ko, category, top_clips, selected_text, tone="",
                      *, product_zh="", source_site="") -> str:
        clip_lines = "\n".join(
            f"- {c.clip_id}: 길이 {c.duration:.1f}초, hook={c.hook_score}, tags={c.tags}, {c.description}"
            for c in top_clips[:6]
        ) or "- (분석된 컷 없음)"
        tone_line = f"톤/스타일 가이드: {tone}\n" if tone else ""
        zh_line = f"상품명(중국어 원문): {product_zh}\n" if product_zh else ""
        site_line = f"수집 사이트: {source_site}\n" if source_site else ""
        return (
            f"상품명: {product_ko}\n{zh_line}카테고리: {category}\n{site_line}{tone_line}"
            f"상품 설명(원문 발췌): {selected_text[:300]}\n\n"
            f"후킹 컷 후보:\n{clip_lines}\n\n"
            f"{SCRIPT_RULES}\n\n"
            f"scene 역할(role)은 다음 중 하나: {', '.join(SCENE_ROLES)}\n"
            "아래 형식의 JSON 배열만 출력해라(설명·마크다운 금지):\n"
            '[{"scene":1,"role":"hook","voice_text":"...","caption_text":"...",'
            '"visual_need":"...","target_duration":3.2,"emotion":"energetic","pace":"fast"}]'
        )

    def _parse(self, text: str) -> list[Scene]:
        text = (text or "").strip()
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
        scenes: list[Scene] = []
        for i, item in enumerate(data, 1):
            if not isinstance(item, dict):
                continue
            scenes.append(Scene(
                scene=int(item.get("scene", i)),
                role=str(item.get("role", "hook")),
                voice_text=str(item.get("voice_text", "")),
                caption_text=str(item.get("caption_text", item.get("voice_text", ""))),
                visual_need=str(item.get("visual_need", "")),
                # LLM 이 준 값을 신뢰하지 않고 씬 길이로 유효한 범위로 클램프
                target_duration=min(15.0, max(1.0, float(item.get("target_duration", 3.0) or 3.0))),
                emotion=str(item.get("emotion", "neutral")),
                pace=str(item.get("pace", "normal")),
            ))
        return scenes
