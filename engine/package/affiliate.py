"""어필리에이트 프로바이더 매핑 및 링크 구조.

상품 카테고리 → 어필리에이트 프로바이더 우선순위. 실제 딥링크 발급은 각 플랫폼
Open API/인증이 필요하므로, MVP 는 raw_url + 슬러그 기반 tracking_url 구조만 만든다.
"""

from __future__ import annotations

from engine.models import (
    CATEGORY_AFFILIATE_MAP,
    DEFAULT_AFFILIATE_PROVIDERS,
    AffiliateLink,
    slugify,
)

PROVIDER_LABELS = {
    "coupang": "쿠팡파트너스",
    "naver_shopping_connect": "네이버 쇼핑커넥트",
    "ohouse": "오늘의집",
    "musinsa": "무신사",
}


def providers_for_category(category: str) -> list[str]:
    """카테고리에 맞는 어필리에이트 프로바이더 우선순위 리스트."""
    return CATEGORY_AFFILIATE_MAP.get(category, DEFAULT_AFFILIATE_PROVIDERS)


def build_affiliate_links(product_ko: str, category: str,
                          raw_urls: dict[str, str] | None = None) -> list[AffiliateLink]:
    """카테고리 기반 어필리에이트 링크 목록 생성.

    raw_urls: {provider: 실제 상품 URL} (있으면 부착). 없으면 raw_url 은 빈 값.
    """
    raw_urls = raw_urls or {}
    slug = slugify(product_ko)
    links = []
    for provider in providers_for_category(category):
        links.append(AffiliateLink(
            provider=provider,
            raw_url=raw_urls.get(provider, ""),
            tracking_url="",  # link_router 가 채움
            product_slug=slug,
        ))
    return links
