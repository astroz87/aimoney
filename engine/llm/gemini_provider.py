"""GeminiLLMProvider — Google Gemini 동기 호출 래퍼.

google-generativeai 미설치 시 명확한 에러로 폴백을 유도한다.
"""

from __future__ import annotations

from .base import LLMError, LLMProvider


class GeminiLLMProvider(LLMProvider):
    provider_id = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash", api_key: str = "") -> None:
        super().__init__(model=model or "gemini-2.5-flash", api_key=api_key)
        if not api_key:
            raise LLMError("Gemini API 키가 없습니다")
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("google-generativeai 미설치 (pip install google-generativeai)") from exc
        genai.configure(api_key=api_key)
        self._genai = genai

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        try:
            model = self._genai.GenerativeModel(
                self.model, system_instruction=system or None
            )
            resp = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini 호출 실패: {exc}") from exc
        return (getattr(resp, "text", "") or "").strip()
