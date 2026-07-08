"""TTS 프로바이더 팩토리.

명시적 (provider, voice, api_key, model) 만 받는다(engine 순수성). 실패 시 Mock 폴백.
"""

from __future__ import annotations

import logging

from .base import TTSProvider
from .mock_provider import MockTTSProvider

logger = logging.getLogger(__name__)

AVAILABLE_VOICES = {
    "edge": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-HyunsuNeural"],
    "mock": ["mock"],
}


def get_tts_provider(provider: str, *, voice: str = "", api_key: str = "",
                     model: str = "", allow_fallback: bool = True) -> TTSProvider:
    provider = (provider or "mock").lower()
    try:
        if provider == "edge":
            from .edge_provider import EdgeTTSProvider
            return EdgeTTSProvider(voice=voice)
        if provider == "gemini":
            from .gemini_provider import GeminiTTSProvider
            return GeminiTTSProvider(voice=voice, api_key=api_key, model=model)
        if provider == "typecast":
            from .typecast_provider import TypecastTTSProvider
            return TypecastTTSProvider(voice=voice, api_key=api_key)
        return MockTTSProvider()
    except Exception as exc:  # noqa: BLE001
        if allow_fallback:
            logger.warning("TTS 프로바이더 '%s' 생성 실패 → Mock 폴백: %s", provider, exc)
            return MockTTSProvider()
        raise
