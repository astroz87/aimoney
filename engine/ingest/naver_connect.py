"""네이버 쇼핑커넥트 링크 발급 (반자동, Playwright).

쇼핑커넥트는 쿠팡파트너스와 달리 공개 API 가 없다. 링크는 브랜드커넥트/
쇼핑커넥트 센터(웹)에서 로그인 후 상품을 검색해 [링크 발급] 버튼으로 만든다.

이 모듈의 전략 (계정 안전 우선):
 1. 로그인은 사람이 직접 한다 — `python naver_login.py` 로 headful 브라우저를
    띄워 네이버 로그인 후 세션(storage_state)을 data/naver_auth.json 에 저장.
    (자동 로그인은 캡차/봇탐지에 걸리기 쉽고 계정 정지 리스크가 있어 하지 않음)
 2. 발급은 저장된 세션으로 센터를 열어 자동 시도한다. 센터 DOM 은 예고 없이
    바뀔 수 있으므로 셀렉터는 아래 상수(다중 후보)로 분리 — 실패 시 명확한
    에러를 돌려주고, 사용자는 센터에서 수동 발급 후 붙여넣기로 폴백한다.

주의: 자동화 접근은 네이버 약관과 충돌할 수 있다. 발급량이 적으면 수동 발급을
권장하며, 이 모듈은 사용자의 판단과 책임 하에 로컬에서만 사용한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

# 세션(storage_state) 저장 위치 — gitignore 대상(*.json 은 data/ 아래라 이미 제외)
AUTH_STATE_PATH = settings.data_dir / "naver_auth.json"

# 브랜드커넥트(쇼핑커넥트) 센터 진입 URL 후보 — 개편 시 여기만 수정
CENTER_URLS = [
    "https://brandconnect.naver.com/shoppingconnect",
    "https://brandconnect.naver.com",
]

# 셀렉터 후보 (텍스트 기반 우선 — DOM 클래스명 변경에 상대적으로 강함)
SEARCH_INPUT_SELECTORS = [
    "input[type='search']",
    "input[placeholder*='검색']",
    "input[placeholder*='상품']",
]
ISSUE_BUTTON_TEXTS = ["링크 발급", "링크발급", "링크 만들기", "URL 복사"]
RESULT_LINK_SELECTORS = [
    "input[readonly][value*='naver.me']",
    "input[readonly][value*='http']",
]

_LOGIN_URL = "https://nid.naver.com/nidlogin.login"


class NaverConnectError(RuntimeError):
    pass


def has_session() -> bool:
    """저장된 로그인 세션 파일이 있는지."""
    return AUTH_STATE_PATH.exists() and AUTH_STATE_PATH.stat().st_size > 0


def login_and_save_session(timeout_sec: int = 300) -> str:
    """headful 브라우저를 띄워 사용자가 직접 로그인하게 하고 세션을 저장한다.

    로컬(데스크톱) 환경 전용. 로그인 완료(nid 쿠키 확인) 또는 timeout 까지 대기.
    """
    from playwright.sync_api import sync_playwright

    AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(_LOGIN_URL)
        print("브라우저 창에서 네이버 로그인을 완료하세요 (캡차/2단계 포함).")
        print(f"로그인이 감지되면 자동으로 세션을 저장합니다 (최대 {timeout_sec}초 대기).")

        # NID_AUT 쿠키가 생기면 로그인 성공으로 판단
        import time
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            cookies = {c["name"] for c in context.cookies("https://naver.com")}
            if "NID_AUT" in cookies:
                break
            time.sleep(2)
        else:
            browser.close()
            raise NaverConnectError("로그인 대기 시간 초과 — 다시 시도하세요.")

        context.storage_state(path=str(AUTH_STATE_PATH))
        browser.close()
    logger.info("네이버 세션 저장: %s", AUTH_STATE_PATH)
    return str(AUTH_STATE_PATH)


def create_connect_link(product_query: str, *, headless: bool = True,
                        timeout_ms: int = 20000) -> str:
    """저장된 세션으로 쇼핑커넥트 센터에서 링크 발급을 자동 시도한다.

    product_query: 센터 상품 검색어(상품명) 또는 스마트스토어 상품 URL.
    성공 시 발급된 링크 문자열 반환, 실패 시 NaverConnectError (수동 폴백 안내).
    """
    if not has_session():
        raise NaverConnectError(
            "네이버 로그인 세션이 없습니다. 먼저 `python naver_login.py` 를 실행해 "
            "로그인하세요."
        )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=str(AUTH_STATE_PATH))
        page = context.new_page()
        try:
            # 1) 센터 진입 (후보 URL 순회)
            for url in CENTER_URLS:
                try:
                    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                    break
                except Exception:  # noqa: BLE001
                    continue
            else:
                raise NaverConnectError("쇼핑커넥트 센터 접속 실패 — CENTER_URLS 를 확인하세요.")

            # 로그인 풀림 감지
            if "nidlogin" in page.url:
                raise NaverConnectError(
                    "세션이 만료되었습니다. `python naver_login.py` 로 다시 로그인하세요."
                )

            # 2) 상품 검색
            search = None
            for sel in SEARCH_INPUT_SELECTORS:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    search = loc
                    break
            if search is None:
                raise NaverConnectError(
                    "상품 검색창을 찾지 못했습니다 — 센터 UI 가 변경된 것 같습니다. "
                    "engine/ingest/naver_connect.py 의 SEARCH_INPUT_SELECTORS 를 갱신하세요."
                )
            search.fill(product_query)
            search.press("Enter")
            page.wait_for_timeout(2500)

            # 3) 첫 결과의 [링크 발급] 버튼
            issue_btn = None
            for text in ISSUE_BUTTON_TEXTS:
                loc = page.get_by_text(text, exact=False).first
                if loc.count() > 0:
                    issue_btn = loc
                    break
            if issue_btn is None:
                raise NaverConnectError(
                    "'링크 발급' 버튼을 찾지 못했습니다. 제휴 가능한 상품이 아니거나 "
                    "센터 UI 가 변경되었습니다. 센터에서 수동 발급 후 붙여넣으세요."
                )
            issue_btn.click()
            page.wait_for_timeout(2000)

            # 4) 발급 결과 링크 추출
            for sel in RESULT_LINK_SELECTORS:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    value = (loc.get_attribute("value") or "").strip()
                    if value.startswith("http"):
                        return value
            # readonly input 이 아니면 클립보드형 UI 일 수 있음 → 본문에서 naver.me 탐색
            import re
            m = re.search(r"https?://naver\.me/\S+", page.content())
            if m:
                return m.group(0).rstrip('"\'<>')

            raise NaverConnectError(
                "발급된 링크를 화면에서 찾지 못했습니다. 센터에서 수동 발급 후 붙여넣으세요."
            )
        finally:
            browser.close()
