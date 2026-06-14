"""ClaudeGenerator 의 순수 헬퍼(텍스트 분리) 단위 테스트.

실제 API 호출 없이 정적 메서드만 검증한다.
"""

from __future__ import annotations

from src.claude_generator import ClaudeGenerator


def test_split_hook_and_caption_basic() -> None:
    text = "이거 안 사면 손해!\n자취생이라면 꼭 필요한 미니 가습기.\n#가습기 #자취템"
    hook, caption = ClaudeGenerator._split_hook_and_caption(text)
    assert hook == "이거 안 사면 손해!"
    assert caption.startswith("이거 안 사면 손해!")
    assert "#자취템" in caption


def test_split_hook_and_caption_skips_blank_lines() -> None:
    text = "\n\n강력 후킹 한 줄\n\n본문입니다."
    hook, _caption = ClaudeGenerator._split_hook_and_caption(text)
    assert hook == "강력 후킹 한 줄"


def test_split_hook_and_caption_empty() -> None:
    hook, caption = ClaudeGenerator._split_hook_and_caption("   \n  ")
    assert hook == ""
    assert caption == ""
