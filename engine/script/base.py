"""ScriptGenerator 인터페이스 및 공통 대본 규칙."""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.models import Clip, Scene

# 대본 생성 규칙 (LLM 프롬프트/Mock 양쪽에서 공유)
SCRIPT_RULES = """대본 생성 규칙:
- 첫 3초는 가장 강한 후킹 컷과 직접 연결한다.
- 첫 문장(hook)은 12~25자 수준의 강한 자막 문장으로 만든다.
- "오늘 소개할 제품은" 같은 약한 오프닝은 절대 금지.
- 과장 광고 표현을 줄이고 문제해결형 표현을 우선한다.
- 전체 길이 30~45초 쇼츠 기준.
- 구조: hook → problem → solution → proof → cta 순서.
- 각 문장의 예상 발화 길이를 target_duration(초)로 둔다.
- 플랫폼별 CTA 문구는 여기서 넣지 않는다(본문 생성 단계에서 분리)."""


class ScriptGenerator(ABC):
    """대본 생성기 공통 인터페이스."""

    @abstractmethod
    def generate(self, *, product_ko: str, category: str,
                 top_clips: list[Clip], selected_text: str = "",
                 tone: str = "") -> list[Scene]:
        """후킹 컷과 상품 정보로 Scene 리스트를 생성한다. tone=템플릿 톤 힌트."""
        raise NotImplementedError
