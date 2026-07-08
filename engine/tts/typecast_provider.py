"""TypecastTTSProvider — 스텁.

구조만 잡아둔다. 실제 Typecast API 연동 시 synthesize 를 구현한다.
"""

from __future__ import annotations

from .base import TTSProvider


class TypecastTTSProvider(TTSProvider):
    provider_id = "typecast"

    def __init__(self, voice: str = "", api_key: str = "") -> None:
        super().__init__(voice=voice)
        self._api_key = api_key
        # 미구현: 생성 시점에 실패시켜 팩토리가 Mock 으로 폴백하도록 한다.
        raise NotImplementedError(
            "TypecastTTSProvider 는 아직 미구현입니다. 설정에서 edge 또는 mock 을 사용하세요."
        )

    def synthesize(self, text: str, *, emotion: str = "neutral",
                   pace: str = "normal", output_path: str) -> dict:
        raise NotImplementedError(
            "TypecastTTSProvider 는 아직 미구현입니다. 설정에서 edge 또는 mock 을 사용하세요."
        )
