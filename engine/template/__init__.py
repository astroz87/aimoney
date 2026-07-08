"""숏폼 스타일 템플릿 (프리셋).

하나의 템플릿 = 자막 스타일 + 배경/전환/BGM + 대본 톤 의 재사용 프리셋.
Level 1(스타일 프리셋)만 다룬다. 비주얼 오버레이 템플릿(Level 2)은 별도.
"""

from .presets import PRESETS, get_preset, list_presets

__all__ = ["PRESETS", "get_preset", "list_presets"]
