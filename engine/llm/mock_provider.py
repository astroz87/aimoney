"""MockLLMProvider — 키/네트워크 없이 파이프라인을 검증하기 위한 더미 프로바이더.

프롬프트에 'JSON' 이 포함되면 최소한의 유효한 JSON 골격을 돌려주려 시도한다.
실제 생성 품질은 없지만 E2E 흐름(대본/검색어)이 끊기지 않도록 한다.
"""

from __future__ import annotations

from .base import LLMProvider


class MockLLMProvider(LLMProvider):
    provider_id = "mock"

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        # 검색어 요청 힌트
        if "검색어" in prompt or "search" in prompt.lower():
            return (
                '{"zh_product_names": ["示例产品", "产品神器"], '
                '"search_queries": ["示例产品 视频", "产品神器 使用视频"]}'
            )
        # 대본 요청 힌트
        if "대본" in prompt or "scene" in prompt.lower() or "script" in prompt.lower():
            return (
                '[{"scene":1,"role":"hook","voice_text":"이 장면 하나면 설명 끝.",'
                '"caption_text":"이 장면 하나면 끝","visual_need":"가장 강한 변화 장면",'
                '"target_duration":3.0,"emotion":"energetic","pace":"fast"}]'
            )
        return "OK"

    def ping(self) -> tuple[bool, str]:
        return True, "mock (항상 사용 가능)"
