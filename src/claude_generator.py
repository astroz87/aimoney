"""ClaudeGenerator — Anthropic Claude 모델을 통한 마케팅 문구 생성 담당.

원본 스레드 게시글의 내용과 타겟 독자(target audience)를 입력받아, 클릭을 유도하는
후킹(hook) 문구와 발행용 캡션을 생성한다. 비동기 SDK(`AsyncAnthropic`)를 사용한다.
"""

from __future__ import annotations

import logging

import anthropic

from config import Settings
from .models import ScrapedPost

logger = logging.getLogger(__name__)

# 시스템 프롬프트: 한국어 소셜 마케팅 카피라이터 페르소나
_SYSTEM_PROMPT = (
    "당신은 한국 소셜미디어(스레드/인스타그램) 바이럴 마케팅 전문 카피라이터입니다. "
    "원본 게시글의 핵심 매력을 살려 스크롤을 멈추게 하는 후킹 문구를 작성합니다. "
    "과장 광고나 허위 사실은 절대 쓰지 않고, 친근하고 진정성 있는 말투를 사용합니다. "
    "이모지를 적절히 활용하되 남발하지 않습니다."
)


class ClaudeGenerator:
    """Claude 기반 마케팅 카피 생성기."""

    def __init__(self, settings: Settings) -> None:
        settings.require_claude()
        self._settings = settings
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_model

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    async def generate(
        self,
        post: ScrapedPost,
        target_audience: str = "20~30대 일반 소비자",
        product_hint: str = "",
    ) -> tuple[str, str]:
        """후킹 문구와 전체 캡션을 생성하여 ``(hook_text, full_caption)`` 으로 반환한다.

        Args:
            post: 원본 스크래핑 게시글
            target_audience: 타겟 독자층 (예: "자취생", "육아맘")
            product_hint: 홍보 대상 상품에 대한 힌트 (선택)
        """
        user_prompt = self._build_prompt(post, target_audience, product_hint)
        logger.info("Claude(%s) 문구 생성 요청 (타겟: %s)", self._model, target_audience)

        # 긴 출력 가능성에 대비해 스트리밍으로 받고 최종 메시지를 취합한다.
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=2_000,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            message = await stream.get_final_message()

        text = self._extract_text(message)
        hook, caption = self._split_hook_and_caption(text)
        logger.info("문구 생성 완료 (후킹 %d자, 캡션 %d자)", len(hook), len(caption))
        return hook, caption

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------
    def _build_prompt(self, post: ScrapedPost, audience: str, hint: str) -> str:
        hint_line = f"- 홍보 상품 힌트: {hint}\n" if hint else ""
        return (
            "다음은 스레드에서 인기 있었던 원본 게시글입니다.\n"
            "이를 참고하여 쿠팡 파트너스 상품 홍보용 새 스레드 콘텐츠를 만들어주세요.\n\n"
            f"[원본 게시글]\n{post.text or '(본문 없음 — 미디어 위주 게시글)'}\n\n"
            "[요구사항]\n"
            f"- 타겟 독자: {audience}\n"
            f"{hint_line}"
            "- 첫 줄은 스크롤을 멈추게 하는 강력한 후킹 한 문장으로 작성\n"
            "- 이어서 상품의 매력을 자연스럽게 풀어내는 본문 2~4문장\n"
            "- 마지막에 행동을 유도하는 CTA 한 문장 (예: 링크 확인 권유)\n"
            "- 해시태그 3~5개 포함\n\n"
            "[출력 형식]\n"
            "첫 줄: 후킹 문구\n"
            "둘째 줄부터: 전체 캡션(후킹 포함 본문+CTA+해시태그)\n"
            "그 외 설명이나 머리말은 절대 붙이지 마세요."
        )

    @staticmethod
    def _extract_text(message: anthropic.types.Message) -> str:
        parts = [block.text for block in message.content if block.type == "text"]
        return "\n".join(parts).strip()

    @staticmethod
    def _split_hook_and_caption(text: str) -> tuple[str, str]:
        """모델 출력에서 후킹(첫 줄)과 전체 캡션을 분리한다."""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return "", ""
        hook = lines[0].strip()
        # 전체 캡션: 후킹을 포함한 전체 텍스트
        caption = text.strip()
        return hook, caption
