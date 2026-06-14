#!/usr/bin/env python3
"""Threads × 쿠팡 파트너스 마케팅 자동화 CLI 진입점.

사용 예:
    python main.py run --source <스레드_URL> --coupang <쿠팡_상품_URL>
    python main.py scrape --source <스레드_URL>
    python main.py generate --text "원본 본문" --audience "자취생"
    python main.py post --caption "캡션" --media a.jpg b.jpg --dry-run
"""

from __future__ import annotations

import sys

from src.cli_controller import CLIController


def main() -> int:
    return CLIController().run()


if __name__ == "__main__":
    sys.exit(main())
