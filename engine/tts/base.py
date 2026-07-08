"""TTSProvider 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TTSResult:
    audio_path: str
    duration: float


class TTSProvider(ABC):
    """모든 TTS 프로바이더의 공통 인터페이스."""

    provider_id: str = "base"

    def __init__(self, voice: str = "") -> None:
        self.voice = voice

    @abstractmethod
    def synthesize(self, text: str, *, emotion: str = "neutral",
                   pace: str = "normal", output_path: str) -> dict:
        """text 를 음성으로 합성해 output_path 에 저장한다.

        Returns: {"audio_path": str, "duration": float}
        """
        raise NotImplementedError

    @staticmethod
    def estimate_duration(text: str) -> float:
        """한국어 기준 대략적인 발화 길이 추정 (~5.5자/초)."""
        chars = len((text or "").replace(" ", ""))
        return max(1.0, round(chars / 5.5, 2))
