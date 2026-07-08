"""플랫폼별 배포 패키지 생성.

output/{product_id}/ 아래에 공통 파일(final.mp4, thumbnail.jpg, script.json,
timeline.json, subtitle.ass) + 플랫폼별 폴더(txt) + affiliate/links.json +
tracking/tracking_urls.json 을 생성한다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .disclosure import DISCLOSURE_TEXT
from .link_router import build_tracking_urls
from .affiliate import PROVIDER_LABELS, build_affiliate_links

logger = logging.getLogger(__name__)


def build_packages(*, product_id: str, product_ko: str, category: str,
                   scenes: list[dict], out_dir: str, link_router_base: str,
                   platforms: list[str] | None = None,
                   affiliate_raw_urls: dict[str, str] | None = None) -> dict:
    """패키지를 생성하고 요약(dict)을 반환한다."""
    # 지연 임포트로 platforms ↔ engine.package 순환 참조 방지
    from platforms import PLATFORMS
    from platforms.base import build_field

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    platform_keys = platforms or list(PLATFORMS.keys())

    hook_caption = ""
    for s in scenes:
        if s.get("role") == "hook":
            hook_caption = s.get("caption_text", "")
            break
    if not hook_caption and scenes:
        hook_caption = scenes[0].get("caption_text", "")

    # 트래킹 URL (플랫폼별)
    tracking = build_tracking_urls(link_router_base, product_ko, platform_keys)

    created_platforms = []
    for key in platform_keys:
        spec = PLATFORMS.get(key)
        if not spec:
            continue
        pdir = out / key
        pdir.mkdir(parents=True, exist_ok=True)
        ctx = {
            "product_ko": product_ko,
            "category": category,
            "scenes": scenes,
            "hook_caption": hook_caption,
            "tracking_url": tracking.get(key, ""),
        }
        for filename in spec["files"]:
            content = build_field(filename, ctx, spec)
            (pdir / filename).write_text(content, encoding="utf-8")
        created_platforms.append(key)

    # 어필리에이트 링크 (카테고리 기반)
    links = build_affiliate_links(product_ko, category, affiliate_raw_urls)
    aff_dir = out / "affiliate"
    aff_dir.mkdir(parents=True, exist_ok=True)
    (aff_dir / "links.json").write_text(
        json.dumps({
            "category": category,
            "providers": [
                {**l.to_dict(), "label": PROVIDER_LABELS.get(l.provider, l.provider)}
                for l in links
            ],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 트래킹 URL json
    track_dir = out / "tracking"
    track_dir.mkdir(parents=True, exist_ok=True)
    (track_dir / "tracking_urls.json").write_text(
        json.dumps(tracking, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 검증: 본문 파일 첫 부분에 경제적 이해관계 문구가 들어갔는지 확인
    disclosure_ok = _verify_disclosure(out, created_platforms)

    return {
        "platforms": created_platforms,
        "affiliate_providers": [l.provider for l in links],
        "tracking_urls": tracking,
        "disclosure_ok": disclosure_ok,
    }


def _verify_disclosure(out: Path, platform_keys: list[str]) -> bool:
    """모든 본문 파일 첫 200자에 경제적 이해관계 문구가 있는지 검증."""
    from platforms.base import BODY_FILES

    marker = DISCLOSURE_TEXT[:20]
    for key in platform_keys:
        pdir = out / key
        for f in pdir.glob("*.txt"):
            if f.name in BODY_FILES:
                head = f.read_text(encoding="utf-8")[:200]
                if marker not in head:
                    logger.error("경제적 이해관계 문구 누락: %s", f)
                    return False
    return True
