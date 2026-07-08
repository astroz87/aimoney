"""링크 라우터 — 플랫폼별 트래킹 URL 을 생성한다.

본문에는 제휴 링크를 하드코딩하지 않고 /go/{slug}?src={platform} 형태만 노출한다.
MVP 는 실제 라우터 웹서비스 대신 tracking_urls.json 만 생성한다.
"""

from __future__ import annotations

from engine.models import slugify


def tracking_url(base: str, product_slug: str, platform: str) -> str:
    base = (base or "").rstrip("/")
    return f"{base}/{product_slug}?src={platform}"


def build_tracking_urls(base: str, product_ko: str,
                        platforms: list[str]) -> dict[str, str]:
    """{platform: tracking_url} 딕셔너리 생성."""
    slug = slugify(product_ko)
    return {p: tracking_url(base, slug, p) for p in platforms}
