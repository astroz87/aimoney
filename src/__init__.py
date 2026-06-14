"""Threads × Coupang Partners 마케팅 자동화 패키지.

모듈 구성:
    - scraper            : ThreadScraper      (게시글 분석 / 미디어 다운로드)
    - media_processor    : MediaProcessor     (영상 프레임 추출 / 썸네일 가공)
    - claude_generator   : ClaudeGenerator    (Claude 기반 후킹 문구 생성)
    - coupang_converter  : CoupangConverter    (쿠팡 링크 변환 / 광고 고지)
    - thread_poster      : ThreadPoster       (스레드 자동 발행)
    - cli_controller     : CLIController       (argparse 명령어 제어 타워)
"""

from .models import GeneratedContent, ScrapedPost

__all__ = ["ScrapedPost", "GeneratedContent"]

__version__ = "0.1.0"
