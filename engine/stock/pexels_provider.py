"""PexelsStockProvider — Pexels Video API 검색.

Pexels 무료 라이선스(상업적 사용 가능, 출처 표기 권장). 세로 숏폼용으로 portrait 우선.
API 문서: https://www.pexels.com/api/documentation/#videos-search
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from .base import StockProvider, StockVideo

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.pexels.com/videos/search"


class PexelsError(RuntimeError):
    pass


class PexelsStockProvider(StockProvider):
    provider_id = "pexels"

    def __init__(self, api_key: str = "") -> None:
        super().__init__(api_key=api_key)
        if not api_key:
            raise PexelsError("Pexels API 키가 없습니다")

    def search(self, query: str, *, per_page: int = 12,
               orientation: str = "portrait") -> list[StockVideo]:
        params = urllib.parse.urlencode({
            "query": query or "product",
            "per_page": max(1, min(40, per_page)),
            "orientation": orientation,
        })
        req = urllib.request.Request(
            f"{_ENDPOINT}?{params}",
            headers={"Authorization": self._api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise PexelsError(f"Pexels 검색 실패: {exc}") from exc

        results: list[StockVideo] = []
        for v in data.get("videos", []):
            best = _best_file(v.get("video_files", []))
            if not best:
                continue
            results.append(StockVideo(
                id=str(v.get("id", "")),
                preview_image=v.get("image", ""),
                video_url=best["link"],
                duration=float(v.get("duration", 0) or 0),
                width=int(best.get("width", 0) or 0),
                height=int(best.get("height", 0) or 0),
                provider="pexels",
                author=(v.get("user") or {}).get("name", ""),
            ))
        return results


def _best_file(files: list[dict]) -> dict | None:
    """세로(높이>너비) HD 파일을 우선 선택. 없으면 가장 큰 파일."""
    if not files:
        return None
    portrait = [f for f in files if (f.get("height", 0) or 0) >= (f.get("width", 0) or 0)]
    pool = portrait or files
    # 너무 큰 4K 는 피하고 720~1080 선호
    def score(f):
        h = f.get("height", 0) or 0
        return -abs(h - 1280)
    return sorted(pool, key=score)[0]
