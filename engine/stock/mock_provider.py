"""MockStockProvider — 키/네트워크 없이 UI 흐름을 검증하기 위한 더미.

실제 다운로드 가능한 URL 은 없으므로 import 는 실패할 수 있으나, 검색 UI/그리드
렌더링과 오프라인 개발에 사용한다.
"""

from __future__ import annotations

from .base import StockProvider, StockVideo


class MockStockProvider(StockProvider):
    provider_id = "mock"

    def search(self, query: str, *, per_page: int = 12,
               orientation: str = "portrait") -> list[StockVideo]:
        n = min(per_page, 6)
        return [StockVideo(
            id=f"mock_{i}",
            preview_image="",
            video_url="",  # 다운로드 불가 (오프라인 데모)
            duration=8.0,
            width=1080, height=1920, provider="mock",
            author=f"mock/{query}",
        ) for i in range(n)]
