"""플랫폼별 배포 규칙.

각 플랫폼 모듈은 SPEC(dict) 을 노출한다. package_builder 가 이를 읽어 파일을 생성한다.
필수 3종(naver_clip, instagram_reels, tiktok_lite) 우선, 이후 4종 확장.
"""

from . import (
    naver_clip,
    instagram_reels,
    tiktok_lite,
    youtube_shorts,
    naver_tv,
    facebook_reels,
    threads,
)

# 등록 순서 = 생성 우선순위 (필수 3종 먼저)
PLATFORMS = {
    "naver_clip": naver_clip.SPEC,
    "instagram_reels": instagram_reels.SPEC,
    "tiktok_lite": tiktok_lite.SPEC,
    "youtube_shorts": youtube_shorts.SPEC,
    "naver_tv": naver_tv.SPEC,
    "facebook_reels": facebook_reels.SPEC,
    "threads": threads.SPEC,
}

# 필수 플랫폼 (1순위)
REQUIRED_PLATFORMS = ["naver_clip", "instagram_reels", "tiktok_lite"]

__all__ = ["PLATFORMS", "REQUIRED_PLATFORMS"]
