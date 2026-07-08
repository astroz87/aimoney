"""플랫폼별 배포 패키지 생성 + 어필리에이트 + 경제적 이해관계 문구."""

from .disclosure import DISCLOSURE_TEXT, prepend_disclosure
from .affiliate import providers_for_category, build_affiliate_links
from .link_router import build_tracking_urls
from .package_builder import build_packages

__all__ = [
    "DISCLOSURE_TEXT", "prepend_disclosure",
    "providers_for_category", "build_affiliate_links",
    "build_tracking_urls", "build_packages",
]
