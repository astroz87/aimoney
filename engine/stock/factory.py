"""스톡 프로바이더 팩토리. 명시적 (provider, api_key) 만 받는다."""

from __future__ import annotations

import logging

from .base import StockProvider
from .mock_provider import MockStockProvider

logger = logging.getLogger(__name__)


def get_stock_provider(provider: str, *, api_key: str = "",
                       allow_fallback: bool = True) -> StockProvider:
    provider = (provider or "mock").lower()
    try:
        if provider == "pexels":
            from .pexels_provider import PexelsStockProvider
            return PexelsStockProvider(api_key=api_key)
        return MockStockProvider()
    except Exception as exc:  # noqa: BLE001
        if allow_fallback:
            logger.warning("스톡 프로바이더 '%s' 실패 → Mock 폴백: %s", provider, exc)
            return MockStockProvider()
        raise
