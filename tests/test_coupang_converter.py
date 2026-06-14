"""CoupangConverter 순수 로직 단위 테스트 (외부 서비스 불필요)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from config import Settings
from src.coupang_converter import AD_DISCLOSURE, CoupangConverter


@pytest.fixture()
def converter(tmp_path) -> CoupangConverter:
    settings = Settings(coupang_partner_tag="AF1234567", work_dir=tmp_path)
    return CoupangConverter(settings)


def test_convert_link_attaches_tag(converter: CoupangConverter) -> None:
    url = "https://www.coupang.com/vp/products/123456?itemId=999"
    converted = converter.convert_link(url)
    qs = parse_qs(urlparse(converted).query)
    assert qs["lptag"] == ["AF1234567"]
    assert qs["subid"] == ["threads"]
    # 기존 파라미터는 보존
    assert qs["itemId"] == ["999"]


def test_apply_disclosure_appends_once(converter: CoupangConverter) -> None:
    caption = "이 가습기 진짜 좋아요!"
    once = converter.apply_disclosure(caption)
    assert AD_DISCLOSURE.strip() in once
    # 중복 적용 방지
    twice = converter.apply_disclosure(once)
    assert twice.count("쿠팡 파트너스") == 1


def test_build_caption_combines_link_and_disclosure(converter: CoupangConverter) -> None:
    caption = "최고의 선택!"
    final, link = converter.build_caption(caption, "https://www.coupang.com/vp/products/1")
    assert link in final
    assert "쿠팡 파트너스" in final
    assert "👉" in final


def test_requires_partner_tag(tmp_path) -> None:
    settings = Settings(coupang_partner_tag="", work_dir=tmp_path)
    with pytest.raises(RuntimeError):
        CoupangConverter(settings)
