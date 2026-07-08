"""StockProvider 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass
class StockVideo:
    id: str
    preview_image: str      # 썸네일 URL
    video_url: str          # 다운로드용 mp4 URL
    duration: float
    width: int
    height: int
    provider: str
    author: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class StockProvider(ABC):
    provider_id: str = "base"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @abstractmethod
    def search(self, query: str, *, per_page: int = 12,
               orientation: str = "portrait") -> list[StockVideo]:
        """쿼리로 스톡 영상을 검색한다."""
        raise NotImplementedError
