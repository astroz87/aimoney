"""LLM 서비스 — 설정(DB>.env)을 해석해 engine.llm 팩토리로 프로바이더를 만든다.

engine 계층의 순수성을 지키기 위한 얇은 어댑터.
"""

from __future__ import annotations

from engine.llm import get_llm_provider as _factory
from engine.llm import ping_provider as _ping
from engine.llm.base import LLMProvider
from app.services import settings_store


def _model_and_key(provider: str) -> tuple[str, str]:
    provider = (provider or "mock").lower()
    if provider == "claude":
        return settings_store.get("claude_model"), settings_store.get("anthropic_api_key")
    if provider == "gemini":
        return settings_store.get("gemini_model"), settings_store.get("gemini_api_key")
    if provider == "openai":
        return settings_store.get("openai_model"), settings_store.get("openai_api_key")
    return "mock", ""


def get_provider(task: str | None = None, provider: str | None = None) -> LLMProvider:
    """작업(task: 'script'|'search')용 프로바이더를 반환. provider 명시 시 우선."""
    provider = provider or settings_store.resolve_llm_provider(task)
    model, api_key = _model_and_key(provider)
    return _factory(provider, model=model, api_key=api_key, allow_fallback=True)


def test_provider(provider: str) -> tuple[bool, str]:
    model, api_key = _model_and_key(provider)
    return _ping(provider, model=model, api_key=api_key)
