"""ThreadPoster — 생성된 콘텐츠를 내 스레드 계정에 자동 업로드 담당.

Playwright 로 스레드에 로그인하여 새 게시글(텍스트 + 이미지)을 발행한다.
로그인 세션은 ``auth_state.json`` 에 저장/재사용하여 매번 로그인하지 않도록 한다.

스레드 UI 셀렉터는 변경될 수 있으므로 다중 후보를 두고 폴백한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

from config import Settings
from .models import GeneratedContent

logger = logging.getLogger(__name__)

_THREADS_URL = "https://www.threads.net"


class ThreadPoster:
    """스레드 자동 발행기."""

    def __init__(self, settings: Settings) -> None:
        settings.require_threads()
        self._settings = settings
        self._auth_path = settings.work_dir / "auth_state.json"

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    async def post(self, content: GeneratedContent, dry_run: bool = False) -> bool:
        """콘텐츠를 스레드에 발행한다.

        Args:
            content: 발행할 캡션 + 미디어
            dry_run: True 이면 실제 발행 직전까지만 진행하고 게시는 하지 않는다.
        """
        logger.info("스레드 발행 시작 (dry_run=%s)", dry_run)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._settings.headless)
            try:
                context = await self._make_context(browser)
                page = await context.new_page()
                await self._ensure_login(page, context)
                ok = await self._compose_and_publish(page, content, dry_run)
                await context.storage_state(path=str(self._auth_path))
                return ok
            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------
    async def _make_context(self, browser) -> BrowserContext:
        kwargs: dict = {"locale": "ko-KR"}
        if self._auth_path.exists():
            kwargs["storage_state"] = str(self._auth_path)
            logger.debug("저장된 로그인 세션 재사용: %s", self._auth_path)
        return await browser.new_context(**kwargs)

    async def _ensure_login(self, page: Page, context: BrowserContext) -> None:
        await page.goto(_THREADS_URL, wait_until="networkidle", timeout=60_000)
        await page.wait_for_timeout(1_500)

        # 이미 로그인되어 있으면 작성 버튼이 보인다.
        if await self._is_logged_in(page):
            logger.info("기존 세션으로 로그인 상태 확인됨.")
            return

        logger.info("로그인을 진행합니다.")
        await self._do_login(page)
        await context.storage_state(path=str(self._auth_path))

    async def _is_logged_in(self, page: Page) -> bool:
        for selector in (
            "[aria-label*='작성'], [aria-label*='새 스레드']",
            "svg[aria-label*='New thread'], svg[aria-label*='Create']",
        ):
            try:
                if await page.query_selector(selector):
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _do_login(self, page: Page) -> None:
        # 인스타그램 계정 기반 로그인 플로우
        try:
            user_input = await page.wait_for_selector(
                "input[autocomplete='username'], input[name='username']",
                timeout=15_000,
            )
            await user_input.fill(self._settings.threads_username)

            pwd_input = await page.wait_for_selector(
                "input[type='password']", timeout=15_000
            )
            await pwd_input.fill(self._settings.threads_password)
            await pwd_input.press("Enter")

            await page.wait_for_timeout(5_000)
            if not await self._is_logged_in(page):
                logger.warning(
                    "로그인 후 작성 버튼을 찾지 못했습니다. 2단계 인증 등 추가 절차가 "
                    "필요할 수 있습니다 (HEADLESS=false 로 수동 확인 권장)."
                )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"스레드 로그인 실패: {exc}") from exc

    async def _compose_and_publish(
        self, page: Page, content: GeneratedContent, dry_run: bool
    ) -> bool:
        # 작성 창 열기
        if not await self._open_composer(page):
            logger.error("작성 창을 열지 못했습니다.")
            return False

        # 캡션 입력
        editor = await self._find_editor(page)
        if editor is None:
            logger.error("텍스트 입력 영역을 찾지 못했습니다.")
            return False
        await editor.click()
        await editor.type(content.full_caption, delay=10)

        # 미디어 첨부
        await self._attach_media(page, content.media_paths)

        if dry_run:
            logger.info("[dry-run] 발행 직전까지 완료 — 실제 게시는 생략합니다.")
            return True

        # 게시 버튼 클릭
        return await self._click_publish(page)

    async def _open_composer(self, page: Page) -> bool:
        for selector in (
            "[aria-label*='작성']",
            "[aria-label*='새 스레드']",
            "svg[aria-label*='Create']",
        ):
            try:
                el = await page.query_selector(selector)
                if el:
                    await el.click()
                    await page.wait_for_timeout(1_500)
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _find_editor(self, page: Page):
        for selector in (
            "div[contenteditable='true']",
            "textarea",
            "[role='textbox']",
        ):
            try:
                el = await page.wait_for_selector(selector, timeout=8_000)
                if el:
                    return el
            except Exception:  # noqa: BLE001
                continue
        return None

    async def _attach_media(self, page: Page, media_paths: list[Path]) -> None:
        if not media_paths:
            return
        try:
            file_input = await page.query_selector("input[type='file']")
            if file_input:
                await file_input.set_input_files([str(p) for p in media_paths])
                await page.wait_for_timeout(3_000)
                logger.info("미디어 %d개 첨부 완료", len(media_paths))
            else:
                logger.warning("파일 입력 요소를 찾지 못해 미디어 첨부를 건너뜁니다.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("미디어 첨부 실패: %s", exc)

    async def _click_publish(self, page: Page) -> bool:
        for selector in (
            "[aria-label*='게시']",
            "div[role='button']:has-text('게시')",
            "div[role='button']:has-text('Post')",
        ):
            try:
                el = await page.query_selector(selector)
                if el:
                    await el.click()
                    await page.wait_for_timeout(4_000)
                    logger.info("게시 완료!")
                    return True
            except Exception:  # noqa: BLE001
                continue
        logger.error("게시 버튼을 찾지 못했습니다.")
        return False
