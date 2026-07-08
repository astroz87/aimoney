"""스톡 영상 검색 (Pexels 등) Provider 추상화.

라이선스가 명확한 무료 스톡 영상을 검색·삽입해 컷 부족을 보완한다.
"""

from .base import StockProvider, StockVideo
from .factory import get_stock_provider

__all__ = ["StockProvider", "StockVideo", "get_stock_provider"]
