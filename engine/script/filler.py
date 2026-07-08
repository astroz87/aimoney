"""대본 채우기 — 이미 조립된 스토리라인(컷 순서)에 나레이션/자막을 얹는다.

"영상 먼저 믹스 → 그 위에 대본" 워크플로우용. 컷 순서/배정은 바꾸지 않고
각 씬의 voice_text/caption_text 만 생성한다. LLMProvider 주입, 실패 시 Mock 폴백.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_SYSTEM = (
    "너는 한국 숏폼 대본 작가다. 이미 편집된 영상 컷 순서가 주어지면, "
    "각 컷 화면에 맞는 나레이션과 자막을 컷 순서 그대로 작성한다. "
    "첫 컷은 강한 후킹, 마지막은 CTA. 과장광고는 피한다. JSON 배열만 출력."
)


def _role_caption(role: str, product: str, idx: int) -> tuple[str, str]:
    """Mock 폴백: 역할 기반 기본 문구."""
    table = {
        "hook": (f"{product}, 이 장면 하나면 끝.", f"{product}, 이거 하나면 끝"),
        "problem": ("이런 상황, 다들 한 번쯤 겪어보셨죠.", "이런 상황 겪어봤다면"),
        "solution": (f"{product}로 이렇게 해결됩니다.", "이걸로 해결"),
        "proof": ("쓰기 전과 후, 차이가 확실하죠.", "전후 차이가 확실"),
        "cta": ("자세한 정보는 아래에서 확인하세요.", "정보는 아래 확인"),
    }
    return table.get(role, (f"장면 {idx}입니다.", f"장면 {idx}"))


def fill_scene_texts(llm, *, product_ko: str, category: str, tone: str,
                     clips_info: list[dict]) -> dict[int, dict]:
    """clips_info: [{scene_no, role, clip_id, tags, description}] (영상 순서).

    Returns {scene_no: {"voice_text":..., "caption_text":...}} (컷 순서 유지).
    """
    if not clips_info:
        return {}

    prompt = _build_prompt(product_ko, category, tone, clips_info)
    try:
        raw = llm.complete(prompt, system=_SYSTEM, max_tokens=1500, temperature=0.8)
        parsed = _parse(raw)
        if parsed and len(parsed) >= 1:
            out = {}
            for i, ci in enumerate(clips_info):
                item = parsed[i] if i < len(parsed) else {}
                out[ci["scene_no"]] = {
                    "voice_text": str(item.get("voice_text", "")).strip()
                    or _role_caption(ci["role"], product_ko, i + 1)[0],
                    "caption_text": str(item.get("caption_text", item.get("voice_text", ""))).strip()
                    or _role_caption(ci["role"], product_ko, i + 1)[1],
                }
            return out
        logger.warning("대본 채우기 파싱 실패 → Mock 폴백")
    except Exception as exc:  # noqa: BLE001
        logger.warning("대본 채우기 실패(%s) → Mock 폴백", exc)

    # Mock 폴백
    out = {}
    for i, ci in enumerate(clips_info):
        v, c = _role_caption(ci["role"], product_ko, i + 1)
        out[ci["scene_no"]] = {"voice_text": v, "caption_text": c}
    return out


def _build_prompt(product_ko, category, tone, clips_info) -> str:
    tone_line = f"톤/스타일: {tone}\n" if tone else ""
    lines = "\n".join(
        f"{i+1}. [{ci['role']}] 컷 {ci['clip_id']} — 태그:{ci.get('tags', [])}, {ci.get('description', '')}"
        for i, ci in enumerate(clips_info)
    )
    return (
        f"상품명: {product_ko}\n카테고리: {category}\n{tone_line}"
        f"\n아래는 이미 편집된 영상 컷 순서다(순서 고정):\n{lines}\n\n"
        "각 컷에 맞는 나레이션(voice_text)과 짧은 자막(caption_text)을 "
        "컷 개수만큼, 같은 순서로 작성해라. 첫 컷은 12~25자 강한 후킹, "
        "마지막은 CTA. 아래 JSON 배열만 출력(설명 금지):\n"
        '[{"voice_text":"...","caption_text":"..."}, ...]'
    )


def _parse(text: str) -> list[dict]:
    text = (text or "").strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return [d for d in data if isinstance(d, dict)]
    except json.JSONDecodeError:
        return []
