"""TTS Provider 추상화 (mock/edge/gemini/typecast)."""

from .base import TTSProvider, TTSResult
from .factory import get_tts_provider

__all__ = ["TTSProvider", "TTSResult", "get_tts_provider"]
