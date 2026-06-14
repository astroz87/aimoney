"""CLIController — argparse 를 활용한 터미널 명령어 제어 타워.

전체 파이프라인을 조율한다:
    scrape → process → generate → convert → post

서브커맨드:
    run       전 과정을 한 번에 실행 (스크래핑 → 가공 → 생성 → 변환 → 발행)
    scrape    스크래핑만 수행하고 결과 출력
    generate  주어진 텍스트로 문구만 생성
    post      준비된 캡션/미디어로 발행만 수행
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from config import settings
from .claude_generator import ClaudeGenerator
from .coupang_converter import CoupangConverter
from .media_processor import MediaProcessor
from .models import GeneratedContent, ScrapedPost
from .scraper import ThreadScraper
from .thread_poster import ThreadPoster

logger = logging.getLogger(__name__)


class CLIController:
    """CLI 진입점이자 파이프라인 오케스트레이터."""

    def __init__(self) -> None:
        self._settings = settings
        self.parser = self._build_parser()

    # ------------------------------------------------------------------
    # argparse 구성
    # ------------------------------------------------------------------
    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="aimoney",
            description="Threads × 쿠팡 파트너스 마케팅 자동화 CLI",
        )
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="상세 로그 출력"
        )
        sub = parser.add_subparsers(dest="command", required=True)

        # run: 전체 파이프라인
        p_run = sub.add_parser("run", help="전 과정 자동 실행")
        p_run.add_argument("--source", required=True, help="원본 스레드 게시글 URL")
        p_run.add_argument(
            "--coupang", required=True, help="홍보할 쿠팡 상품 URL"
        )
        p_run.add_argument(
            "--audience", default="20~30대 일반 소비자", help="타겟 독자층"
        )
        p_run.add_argument("--hint", default="", help="홍보 상품 힌트")
        p_run.add_argument(
            "--dry-run",
            action="store_true",
            help="발행 직전까지만 진행 (실제 게시 안 함)",
        )

        # scrape: 스크래핑만
        p_scrape = sub.add_parser("scrape", help="게시글 스크래핑만 수행")
        p_scrape.add_argument("--source", required=True, help="스레드 게시글 URL")

        # generate: 문구 생성만
        p_gen = sub.add_parser("generate", help="문구 생성만 수행")
        p_gen.add_argument("--text", required=True, help="원본 게시글 본문 텍스트")
        p_gen.add_argument(
            "--audience", default="20~30대 일반 소비자", help="타겟 독자층"
        )
        p_gen.add_argument("--hint", default="", help="홍보 상품 힌트")

        # post: 발행만
        p_post = sub.add_parser("post", help="준비된 캡션/미디어로 발행만 수행")
        p_post.add_argument("--caption", required=True, help="발행할 캡션 텍스트")
        p_post.add_argument(
            "--media", nargs="*", default=[], help="첨부할 이미지 경로(공백 구분)"
        )
        p_post.add_argument(
            "--dry-run", action="store_true", help="실제 게시 안 함"
        )

        return parser

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------
    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        try:
            return asyncio.run(self._dispatch(args))
        except KeyboardInterrupt:
            logger.warning("사용자에 의해 중단되었습니다.")
            return 130
        except Exception as exc:  # noqa: BLE001
            logger.error("실행 실패: %s", exc)
            if args.verbose:
                logger.exception("상세 스택트레이스:")
            return 1

    async def _dispatch(self, args: argparse.Namespace) -> int:
        handlers = {
            "run": self._cmd_run,
            "scrape": self._cmd_scrape,
            "generate": self._cmd_generate,
            "post": self._cmd_post,
        }
        return await handlers[args.command](args)

    # ------------------------------------------------------------------
    # 각 서브커맨드 핸들러
    # ------------------------------------------------------------------
    async def _cmd_run(self, args: argparse.Namespace) -> int:
        # 1) 스크래핑
        scraper = ThreadScraper(self._settings)
        post = await scraper.scrape(args.source)

        # 2) 미디어 가공
        processor = MediaProcessor(self._settings)
        media_paths = await processor.process_post(post)

        # 3) 문구 생성
        generator = ClaudeGenerator(self._settings)
        _hook, caption = await generator.generate(
            post, target_audience=args.audience, product_hint=args.hint
        )

        # 4) 쿠팡 링크 변환 + 광고 고지
        converter = CoupangConverter(self._settings)
        final_caption, link = converter.build_caption(caption, args.coupang)

        # 5) 발행
        content = GeneratedContent(
            hook_text=_hook,
            full_caption=final_caption,
            coupang_link=link,
            media_paths=media_paths,
        )
        poster = ThreadPoster(self._settings)
        ok = await poster.post(content, dry_run=args.dry_run)

        self._print_summary(final_caption, link, media_paths, ok)
        return 0 if ok else 1

    async def _cmd_scrape(self, args: argparse.Namespace) -> int:
        scraper = ThreadScraper(self._settings)
        post = await scraper.scrape(args.source)
        print("\n===== 스크래핑 결과 =====")
        print(f"작성자: @{post.author}")
        print(f"좋아요: {post.like_count}")
        print(f"본문:\n{post.text}")
        print(f"이미지: {[str(p) for p in post.image_paths]}")
        print(f"영상: {[str(p) for p in post.video_paths]}")
        return 0

    async def _cmd_generate(self, args: argparse.Namespace) -> int:
        generator = ClaudeGenerator(self._settings)
        post = ScrapedPost(url="(manual)", text=args.text)
        hook, caption = await generator.generate(
            post, target_audience=args.audience, product_hint=args.hint
        )
        print("\n===== 생성된 후킹 =====")
        print(hook)
        print("\n===== 전체 캡션 =====")
        print(caption)
        return 0

    async def _cmd_post(self, args: argparse.Namespace) -> int:
        content = GeneratedContent(
            hook_text="",
            full_caption=args.caption,
            media_paths=[Path(m) for m in args.media],
        )
        poster = ThreadPoster(self._settings)
        ok = await poster.post(content, dry_run=args.dry_run)
        print("발행 성공!" if ok else "발행 실패.")
        return 0 if ok else 1

    @staticmethod
    def _print_summary(
        caption: str, link: str, media: list[Path], ok: bool
    ) -> None:
        print("\n========== 실행 요약 ==========")
        print(f"제휴 링크: {link}")
        print(f"첨부 미디어: {[str(p) for p in media]}")
        print(f"발행 상태: {'성공' if ok else '실패'}")
        print("\n----- 최종 캡션 -----")
        print(caption)
        print("==============================\n")
