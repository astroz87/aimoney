"""LLM Provider 추상화.

대본 생성기·검색어 생성기는 SDK 를 직접 호출하지 않고 `LLMProvider` 만 사용한다.
설정(DB > .env)에서 프로바이더/모델/키를 읽어 `factory.get_llm_provider()` 로 생성.
키가 없거나 SDK 미설치 시 자동으로 MockLLMProvider 로 폴백한다.
"""

from .base import LLMProvider, LLMError
from .factory import get_llm_provider, ping_provider

__all__ = ["LLMProvider", "LLMError", "get_llm_provider", "ping_provider"]
