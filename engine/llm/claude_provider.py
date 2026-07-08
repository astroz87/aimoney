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
        # 주의: temperature/top_p 는 최신 Claude(Fable 5, Opus 4.8/4.7, Sonnet 5)에서
        # 400 으로 거부되므로 보내지 않는다. 변주는 프롬프트로 유도한다.
        # Fable 5 는 thinking 이 항상 켜져 있으므로 thinking 파라미터도 전달하지 않는다.
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Claude 호출 실패: {exc}") from exc
        # 안전 분류기 거절(Fable 5 등): content 가 비었을 수 있음 → 명시적 에러로
        # 올려 상위(대본 생성기)가 Mock 폴백하도록 한다.
        if getattr(msg, "stop_reason", "") == "refusal":
            raise LLMError("Claude 가 요청을 거절했습니다 (stop_reason=refusal)")
        parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
