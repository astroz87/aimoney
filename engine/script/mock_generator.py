"""MockScriptGenerator — 규칙 기반 대본 생성 (LLM 없이 동작).

상품명/카테고리/후킹컷 태그를 조합해 hook→problem→solution→proof→cta 5장면을
템플릿으로 채운다. 실제 카피 품질은 낮지만 파이프라인 검증과 오프라인 사용에 충분하다.
"""

from __future__ import annotations

from engine.models import Clip, Scene
from .base import ScriptGenerator


class MockScriptGenerator(ScriptGenerator):
    def generate(self, *, product_ko: str, category: str,
                 top_clips: list[Clip], selected_text: str = "",
                 tone: str = "") -> list[Scene]:
        name = product_ko or "이 제품"
        top = top_clips[0] if top_clips else None
        hook_need = "가장 강한 변화(before/after)가 보이는 장면"
        if top and "before_after" in top.tags:
            hook_need = "정리 전후 변화가 가장 뚜렷한 장면"
        elif top and "hand_action" in top.tags:
            hook_need = "손으로 사용하는 순간이 보이는 장면"

        scenes = [
            Scene(
                scene=1, role="hook",
                voice_text=f"{name}, 이 장면 하나면 설명 끝.",
                caption_text=f"{name}, 이거 하나면 끝",
                visual_need=hook_need,
                target_duration=3.0, emotion="energetic", pace="fast",
            ),
            Scene(
                scene=2, role="problem",
                voice_text="매번 정리해도 금방 다시 지저분해지고, 찾기도 불편했죠.",
                caption_text="매번 정리해도 도로 지저분",
                visual_need="지저분하거나 불편한 상황 장면",
                target_duration=5.0, emotion="relatable", pace="normal",
            ),
            Scene(
                scene=3, role="solution",
                voice_text=f"{name}는 그 문제를 한 번에 해결해 줍니다.",
                caption_text="이걸로 한 번에 해결",
                visual_need="제품을 실제로 사용하는 장면",
                target_duration=4.5, emotion="confident", pace="normal",
            ),
            Scene(
                scene=4, role="proof",
                voice_text="쓰기 전과 후를 비교하면 차이가 확실하게 보여요.",
                caption_text="사용 전후 차이가 확실",
                visual_need="before/after 비교 또는 결과 장면",
                target_duration=4.5, emotion="satisfied", pace="normal",
            ),
            Scene(
                scene=5, role="cta",
                voice_text="자세한 정보는 아래에서 확인해 보세요.",
                caption_text="정보는 아래 확인",
                visual_need="제품 클로즈업",
                target_duration=3.0, emotion="friendly", pace="normal",
            ),
        ]
        return scenes
