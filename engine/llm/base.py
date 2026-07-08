"""LLMProvider 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    """LLM 호출 실패."""


class LLMProvider(ABC):
    """모든 LLM 프로바이더의 공통 인터페이스.

    구현체는 `complete()` 하나만 제공하면 된다. 대본/검색어 생성기는 이 메서드로
    JSON 또는 텍스트를 받아 파싱한다.
    """

    provider_id: str = "base"

    def __init__(self, model: str = "", api_key: str = "") -> None:
        self.model = model
        self._api_key = api_key

    @abstractmethod
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        """프롬프트를 보내고 모델의 텍스트 응답을 반환한다."""
        raise NotImplementedError

    def ping(self) -> tuple[bool, str]:
        """유효성 확인용 짧은 호출. (성공여부, 상세메시지)."""
        try:
            out = self.complete("Reply with the single word: OK", max_tokens=10)
            return True, (out or "").strip()[:40]
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:200]
