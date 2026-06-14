"""ThreadScraper — 타겟 스레드 게시글 분석 및 미디어 다운로드 담당.

Playwright 로 스레드 게시글 페이지를 열어 본문/작성자/좋아요 수를 추출하고,
게시글에 포함된 이미지·영상을 비동기로 다운로드한다.

스레드(Threads)는 비공식 API 만 존재하므로 DOM 셀렉터에 의존한다. 셀렉터는
서비스 변경에 따라 깨질 수 있으므로 다중 후보를 두고 폴백하도록 작성했다.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from playwright.async_api import Browser, async_playwright

from config import Settings
from .models import ScrapedPost

logger = logging.getLogger(__name__)


class ThreadScraper:
    """스레드 게시글 스크래퍼."""

    # 본문 텍스트 추출용 후보 셀렉터 (위에서부터 순서대로 시도)
    _TEXT_SELECTORS = (
        "div[data-pressable-container] span[dir='auto']",
        "article span[dir='auto']",
        "div[role='article'] span",
    )

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._media_dir = settings.work_dir / "downloads"
        self._media_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    async def scrape(self, url: str) -> ScrapedPost:
        """게시글 URL 하나를 스크래핑하여 :class:`ScrapedPost` 로 반환한다."""
        logger.info("스레드 게시글 스크래핑 시작: %s", url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._settings.headless)
            try:
                post = await self._scrape_with_browser(browser, url)
            finally:
                await browser.close()

        # 미디어 다운로드 (이미지 + 영상)
        await self._download_all_media(post)
        logger.info(
            "스크래핑 완료: 본문 %d자, 이미지 %d개, 영상 %d개",
            len(post.text),
            len(post.image_paths),
            len(post.video_paths),
        )
        return post

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------
    async def _scrape_with_browser(self, browser: Browser, url: str) -> ScrapedPost:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        # 동적 로딩 콘텐츠 안정화 대기
        await page.wait_for_timeout(2_000)

        post = ScrapedPost(url=url)
        post.text = await self._extract_text(page)
        post.author = await self._extract_author(page, url)
        post.like_count = await self._extract_like_count(page)

        image_urls, video_urls = await self._extract_media_urls(page)
        # URL 만 임시 저장; 실제 파일 경로는 다운로드 단계에서 채운다.
        post.image_paths = [Path(u) for u in image_urls]  # placeholder (URL 보관)
        post.video_paths = [Path(u) for u in video_urls]
        return post

    async def _extract_text(self, page) -> str:
        for selector in self._TEXT_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                texts = [(await el.inner_text()).strip() for el in elements]
                texts = [t for t in texts if t]
                if texts:
                    # 가장 긴 텍스트 블록을 본문으로 간주
                    return max(texts, key=len)
            except Exception as exc:  # noqa: BLE001 - 셀렉터 폴백
                logger.debug("텍스트 셀렉터 실패(%s): %s", selector, exc)
        logger.warning("본문 텍스트를 추출하지 못했습니다.")
        return ""

    async def _extract_author(self, page, url: str) -> str:
        # 스레드 URL 패턴: https://www.threads.net/@username/post/XXXX
        match = re.search(r"@([A-Za-z0-9_.]+)", url)
        if match:
            return match.group(1)
        try:
            title = await page.title()
            m = re.search(r"@([A-Za-z0-9_.]+)", title)
            if m:
                return m.group(1)
        except Exception:  # noqa: BLE001
            pass
        return ""

    async def _extract_like_count(self, page) -> int:
        try:
            # "좋아요 1,234개" 형태의 aria-label 탐색
            handle = await page.query_selector("[aria-label*='좋아요'], [aria-label*='like']")
            if handle:
                label = await handle.get_attribute("aria-label") or ""
                digits = re.sub(r"[^0-9]", "", label)
                if digits:
                    return int(digits)
        except Exception as exc:  # noqa: BLE001
            logger.debug("좋아요 수 추출 실패: %s", exc)
        return 0

    async def _extract_media_urls(self, page) -> tuple[list[str], list[str]]:
        image_urls: list[str] = []
        video_urls: list[str] = []

        # 이미지: 콘텐츠 이미지 (프로필/아이콘 제외를 위해 크기 기준 필터)
        for img in await page.query_selector_all("img"):
            src = await img.get_attribute("src")
            if not src or src.startswith("data:"):
                continue
            # 프로필 사진 등 작은 이미지 배제
            if "cdninstagram" in src or "fbcdn" in src:
                if src not in image_urls:
                    image_urls.append(src)

        # 영상: <video> 태그의 src 또는 source
        for video in await page.query_selector_all("video"):
            src = await video.get_attribute("src")
            if src and src not in video_urls:
                video_urls.append(src)
            for source in await video.query_selector_all("source"):
                s = await source.get_attribute("src")
                if s and s not in video_urls:
                    video_urls.append(s)

        return image_urls, video_urls

    async def _download_all_media(self, post: ScrapedPost) -> None:
        # placeholder Path 객체에서 원본 URL 문자열 복원
        image_urls = [str(p) for p in post.image_paths]
        video_urls = [str(p) for p in post.video_paths]
        post.image_paths = []
        post.video_paths = []

        async with aiohttp.ClientSession() as session:
            img_tasks = [
                self._download_one(session, u, f"img_{i}")
                for i, u in enumerate(image_urls)
            ]
            vid_tasks = [
                self._download_one(session, u, f"vid_{i}")
                for i, u in enumerate(video_urls)
            ]
            img_results = await asyncio.gather(*img_tasks, return_exceptions=True)
            vid_results = await asyncio.gather(*vid_tasks, return_exceptions=True)

        for r in img_results:
            if isinstance(r, Path):
                post.image_paths.append(r)
        for r in vid_results:
            if isinstance(r, Path):
                post.video_paths.append(r)

    async def _download_one(
        self, session: aiohttp.ClientSession, url: str, name_hint: str
    ) -> Path | None:
        try:
            ext = Path(urlparse(url).path).suffix or ".bin"
            target = self._media_dir / f"{name_hint}{ext}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                resp.raise_for_status()
                data = await resp.read()
            target.write_bytes(data)
            logger.debug("미디어 다운로드 완료: %s (%d bytes)", target, len(data))
            return target
        except Exception as exc:  # noqa: BLE001
            logger.warning("미디어 다운로드 실패(%s): %s", url, exc)
            return None
