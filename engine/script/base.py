"""ScriptGenerator 인터페이스 및 공통 대본 규칙."""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.models import Clip, Scene

# 한국어 TTS 평균 발화 속도(초당 글자 수). voice_text 길이 ↔ target_duration 연동 기준.
CHARS_PER_SEC = 5.5

# 대본 생성 규칙 (LLM 프롬프트/Mock 양쪽에서 공유)
# 목표 + 제약 + 좋은 예시 1개 형태 — 최신 모델은 규칙 나열보다 이 구조에서 더 잘 쓴다.
SCRIPT_RULES = f"""[목표]
시청자가 첫 3초 안에 손을 멈추고 끝까지 보게 만드는 30~45초 쇼핑 숏폼 대본.

[제약]
- 구조: hook → problem → solution → proof → cta 순서.
- 첫 문장(hook)은 12~25자. "오늘 소개할 제품은" 같은 약한 오프닝 금지.
- voice_text 글자 수 ≈ target_duration(초) × {CHARS_PER_SEC} 로 맞춘다.
  예: 3초 씬 → 약 16자, 4초 씬 → 약 22자. 길면 TTS가 영상보다 길어져 싱크가 깨진다.
- caption_text 는 voice_text 요지를 15자 내외로 압축한 화면 자막.
- 과장·확정적 효능 표현 금지. 문제 상황 → 해결 흐름을 우선한다.
- 플랫폼별 CTA 문구는 넣지 않는다(본문 생성 단계에서 분리).

[좋은 예시 — hook 씬 1개]
{{"scene":1,"role":"hook","voice_text":"선 정리 때문에 책상 포기한 사람?","caption_text":"책상 위 선 지옥 탈출","target_duration":3.0}}"""


class ScriptGenerator(ABC):
    """대본 생성기 공통 인터페이스."""

    @abstractmethod
    def generate(self, *, product_ko: str, category: str,
                 top_clips: list[Clip], selected_text: str = "",
                 tone: str = "", product_zh: str = "",
                 source_site: str = "") -> list[Scene]:
        """후킹 컷과 상품 정보로 Scene 리스트를 생성한다.

        tone=템플릿 톤 힌트, product_zh/source_site=수집 원문 컨텍스트(선택).
        """
        raise NotImplementedError
