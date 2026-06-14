"""CoupangConverter — 쿠팡 링크 변환 및 광고 고지 문구 삽입 담당.

쿠팡 상품 URL 에 파트너스 추적 태그를 부착해 제휴 링크로 변환하고,
공정거래위원회 권고에 따른 광고 고지(대가성 표시) 문구를 캡션에 삽입한다.

주의: 실제 쿠팡 파트너스 단축 링크(딥링크) 발급은 Open API 인증이 필요하다.
키가 설정되지 않은 경우, 추적 태그를 쿼리 파라미터로 부착하는 방식으로 폴백한다.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config import Settings

logger = logging.getLogger(__name__)

# 공정위 권장 광고 고지 문구
AD_DISCLOSURE = (
    "\n\n———\n"
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)


class CoupangConverter:
    """쿠팡 제휴 링크 변환기."""

    def __init__(self, settings: Settings) -> None:
        settings.require_coupang()
        self._settings = settings
        self._tag = settings.coupang_partner_tag

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    def convert_link(self, product_url: str) -> str:
        """쿠팡 상품 URL 을 파트너스 추적 태그가 부착된 제휴 링크로 변환한다."""
        parsed = urlparse(product_url)
        if "coupang.com" not in parsed.netloc:
            logger.warning("쿠팡 도메인이 아닌 URL 입니다: %s", product_url)

        query = dict(parse_qsl(parsed.query))
        # 파트너스 추적 파라미터 부착
        query["lptag"] = self._tag
        query["subid"] = "threads"  # 유입 채널 식별용 서브 ID

        new_query = urlencode(query)
        converted = urlunparse(parsed._replace(query=new_query))
        logger.info("쿠팡 링크 변환 완료: %s", converted)
        return converted

    def apply_disclosure(self, caption: str) -> str:
        """캡션 끝에 광고 고지 문구를 삽입한다 (중복 방지)."""
        if "쿠팡 파트너스" in caption:
            return caption
        return caption.rstrip() + AD_DISCLOSURE

    def build_caption(self, caption: str, product_url: str) -> tuple[str, str]:
        """캡션에 제휴 링크 + 광고 고지를 결합하여 최종 캡션을 만든다.

        Returns:
            ``(final_caption, converted_link)``
        """
        link = self.convert_link(product_url)
        body = caption.rstrip()
        body = f"{body}\n\n👉 {link}"
        final = self.apply_disclosure(body)
        return final, link
