"""OpenAILLMProvider — OpenAI GPT 동기 호출 래퍼."""

from __future__ import annotations

from .base import LLMError, LLMProvider


class OpenAILLMProvider(LLMProvider):
    provider_id = "openai"

    def __init__(self, model: str = "gpt-4o", api_key: str = "") -> None:
        super().__init__(model=model or "gpt-4o", api_key=api_key)
        if not api_key:
            raise LLMError("OpenAI API 키가 없습니다")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("openai SDK 미설치 (pip install openai)") from exc
        self._client = OpenAI(api_key=api_key)

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"OpenAI 호출 실패: {exc}") from exc
        return (resp.choices[0].message.content or "").strip()
