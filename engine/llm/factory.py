"""LLM 프로바이더 팩토리.

engine 은 웹/DB 계층에 의존하지 않도록, 팩토리는 명시적 (provider, model, api_key)
만 받는다. 설정(DB>.env) 해석은 app/services 계층이 담당한 뒤 여기로 넘긴다.
키 없음/SDK 미설치 등으로 실패하면 MockLLMProvider 로 폴백한다.
"""

from __future__ import annotations

import logging

from .base import LLMError, LLMProvider
from .mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)

# 프로바이더별 사용 가능 모델 (설정 UI 드롭다운 참고용)
# claude-fable-5: 최상위 모델($10/$50 per 1M) — thinking 항상 켜짐, 30일 데이터보존 필요.
# 대본 생성 기본값은 claude-opus-4-8($5/$25) 권장.
AVAILABLE_MODELS: dict[str, list[str]] = {
    "claude": ["claude-opus-4-8", "claude-fable-5", "claude-sonnet-5", "claude-haiku-4-5"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
    "mock": ["mock"],
}


def get_llm_provider(
    provider: str, *, model: str = "", api_key: str = "", allow_fallback: bool = True
) -> LLMProvider:
    """프로바이더 인스턴스를 생성한다. 실패 시 Mock 폴백(allow_fallback)."""
    provider = (provider or "mock").lower()
    try:
        if provider == "claude":
            from .claude_provider import ClaudeLLMProvider
            return ClaudeLLMProvider(model=model, api_key=api_key)
        if provider == "gemini":
            from .gemini_provider import GeminiLLMProvider
            return GeminiLLMProvider(model=model, api_key=api_key)
        if provider == "openai":
            from .openai_provider import OpenAILLMProvider
            return OpenAILLMProvider(model=model, api_key=api_key)
        return MockLLMProvider(model="mock")
    except LLMError as exc:
        if allow_fallback:
            logger.warning("LLM 프로바이더 '%s' 생성 실패 → Mock 폴백: %s", provider, exc)
            return MockLLMProvider(model="mock")
        raise


def ping_provider(provider: str, *, model: str = "", api_key: str = "") -> tuple[bool, str]:
    """설정 테스트용: 폴백 없이 실제 프로바이더로 짧은 호출을 시도한다."""
    try:
        inst = get_llm_provider(provider, model=model, api_key=api_key, allow_fallback=False)
    except LLMError as exc:
        return False, str(exc)
    return inst.ping()
