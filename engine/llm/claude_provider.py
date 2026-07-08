"""ClaudeLLMProvider — Anthropic Claude 동기 호출 래퍼."""

from __future__ import annotations

from .base import LLMError, LLMProvider


class ClaudeLLMProvider(LLMProvider):
    provider_id = "claude"

    def __init__(self, model: str = "claude-opus-4-8", api_key: str = "") -> None:
        super().__init__(model=model or "claude-opus-4-8", api_key=api_key)
        if not api_key:
            raise LLMError("Claude API 키가 없습니다")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic SDK 미설치 (pip install anthropic)") from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Claude 호출 실패: {exc}") from exc
        parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
