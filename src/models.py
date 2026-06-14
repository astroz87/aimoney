"""파이프라인 단계 간에 주고받는 데이터 구조 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ScrapedPost:
    """스레드에서 스크래핑한 단일 게시글."""

    url: str
    author: str = ""
    text: str = ""
    like_count: int = 0
    image_paths: list[Path] = field(default_factory=list)
    video_paths: list[Path] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.image_paths or self.video_paths)


@dataclass(slots=True)
class GeneratedContent:
    """Claude 가 생성한 마케팅 콘텐츠 + 발행에 필요한 모든 산출물."""

    hook_text: str
    full_caption: str
    coupang_link: str = ""
    media_paths: list[Path] = field(default_factory=list)
