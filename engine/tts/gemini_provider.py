"""GeminiTTSProvider — 스텁.

구조만 잡아둔다. 실제 Gemini TTS 연동 시 이 클래스의 synthesize 를 구현한다.
현재는 미구현이므로 명확한 에러를 던져 팩토리가 폴백하도록 한다.
"""

from __future__ import annotations

from .base import TTSProvider


class GeminiTTSProvider(TTSProvider):
    provider_id = "gemini"

    def __init__(self, voice: str = "", api_key: str = "", model: str = "") -> None:
        super().__init__(voice=voice)
        self._api_key = api_key
        self._model = model
        # 미구현: 생성 시점에 실패시켜 팩토리가 Mock 으로 폴백하도록 한다
        # (그래야 백그라운드 TTS 잡이 synthesize 단계에서 늦게 죽지 않는다).
        raise NotImplementedError(
            "GeminiTTSProvider 는 아직 미구현입니다. 설정에서 edge 또는 mock 을 사용하세요."
        )

    def synthesize(self, text: str, *, emotion: str = "neutral",
                   pace: str = "normal", output_path: str) -> dict:
        raise NotImplementedError(
            "GeminiTTSProvider 는 아직 미구현입니다. 설정에서 edge 또는 mock 을 사용하세요."
        )
