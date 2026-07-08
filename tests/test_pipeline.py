"""핵심 파이프라인 로직 단위 테스트 (ffmpeg/네트워크 불필요)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.models import Clip, Scene
from engine.timeline import build_timeline
from engine.tts.factory import get_tts_provider
from engine.tts.mock_provider import MockTTSProvider
from engine.models import resolve_edit_settings, DEFAULT_EDIT_SETTINGS
from engine.render.ffmpeg_renderer import _hex_to_ff
from engine.stock.factory import get_stock_provider
from engine.stock.mock_provider import MockStockProvider
from app.services.project_service import _en_slug
from engine.subtitle.ass_builder import build_ass, _ts, _wrap_two_lines
from engine.package.disclosure import DISCLOSURE_TEXT, prepend_disclosure
from engine.package.affiliate import providers_for_category, build_affiliate_links
from engine.package.link_router import build_tracking_urls
from engine.package import build_packages


def _clip(cid, start, end, hook=0.5, tags=None, q=0.8):
    return Clip(clip_id=cid, source_video="v.mp4", start=start, end=end,
                duration=end - start, tags=tags or [], quality_score=q,
                motion_score=0.5, hook_score=hook, description="")


# ---------------- 타임라인 ----------------
def test_timeline_hook_gets_highest_hook_clip():
    scenes = [
        Scene(scene=1, role="hook", voice_text="a", caption_text="a", target_duration=3),
        Scene(scene=2, role="problem", voice_text="b", caption_text="b", target_duration=4),
    ]
    clips = [_clip("clip_001", 0, 5, hook=0.2), _clip("clip_002", 5, 10, hook=0.95)]
    durations = {1: 3.0, 2: 4.0}
    tl = build_timeline(scenes, clips, durations)
    # hook scene 은 hook_score 최고(clip_002) 를 받아야 한다
    assert tl[0].scene == 1
    assert tl[0].clip_id == "clip_002"
    # 연속 타임라인
    assert tl[0].timeline_start == 0.0
    assert abs(tl[1].timeline_start - tl[0].timeline_end) < 1e-6


def test_timeline_uses_tts_duration_over_target():
    scenes = [Scene(scene=1, role="hook", voice_text="a", caption_text="a", target_duration=3)]
    clips = [_clip("clip_001", 0, 10, hook=0.9)]
    tl = build_timeline(scenes, clips, {1: 5.5})  # 실측 TTS 길이 우선
    assert abs((tl[0].timeline_end - tl[0].timeline_start) - 5.5) < 1e-6


def test_timeline_visual_need_matches_tags():
    scenes = [
        Scene(scene=1, role="hook", voice_text="a", caption_text="a", target_duration=3),
        Scene(scene=2, role="proof", voice_text="b", caption_text="b",
              visual_need="사용 전후 비교 장면", target_duration=3),
    ]
    clips = [
        _clip("clip_001", 0, 5, hook=0.9, tags=["product_visible"]),
        _clip("clip_002", 5, 10, hook=0.1, tags=["before_after"]),
    ]
    tl = build_timeline(scenes, clips, {1: 3.0, 2: 3.0})
    proof = next(t for t in tl if t.scene == 2)
    assert proof.clip_id == "clip_002"  # before_after 태그 매칭


# ---------------- 씬 편집기 (수동 컷/순서) ----------------
def test_timeline_honors_preferred_clip():
    scenes = [Scene(scene=1, role="hook", voice_text="a", caption_text="a",
                    target_duration=3, preferred_clip_id="clip_002")]
    clips = [_clip("clip_001", 0, 5, hook=0.95), _clip("clip_002", 5, 10, hook=0.1)]
    tl = build_timeline(scenes, clips, {1: 3.0})
    # hook_score 상 clip_001 이 유리하지만 수동 지정(clip_002)이 우선
    assert tl[0].clip_id == "clip_002"


def test_timeline_preserves_input_order():
    # 편집기 재정렬: scene 2 를 먼저 배치
    scenes = [
        Scene(scene=2, role="problem", voice_text="b", caption_text="b", target_duration=3),
        Scene(scene=1, role="hook", voice_text="a", caption_text="a", target_duration=3),
    ]
    clips = [_clip("clip_001", 0, 5, hook=0.9), _clip("clip_002", 5, 10, hook=0.5)]
    tl = build_timeline(scenes, clips, {1: 3.0, 2: 3.0})
    assert [t.scene for t in tl] == [2, 1]  # 입력 순서 보존


# ---------------- 오디오/배경 편집 설정 ----------------
def test_resolve_edit_settings_fills_defaults():
    s = resolve_edit_settings(None)
    assert s == DEFAULT_EDIT_SETTINGS
    s2 = resolve_edit_settings({"transition": "fade", "bgm_volume": 0.3})
    assert s2["transition"] == "fade" and s2["bgm_volume"] == 0.3
    assert s2["bg_color"] == DEFAULT_EDIT_SETTINGS["bg_color"]  # 나머지는 기본값


def test_hex_to_ff_color():
    assert _hex_to_ff("#101820") == "0x101820"
    assert _hex_to_ff("101820") == "0x101820"
    assert _hex_to_ff("bad") == "0x202430"      # 잘못된 값 → 기본색
    assert _hex_to_ff("") == "0x202430"


# ---------------- 스톡 프로바이더 ----------------
def test_stock_pexels_without_key_falls_back_to_mock():
    prov = get_stock_provider("pexels", api_key="", allow_fallback=True)
    assert isinstance(prov, MockStockProvider)


def test_stock_mock_search_returns_items():
    prov = get_stock_provider("mock")
    res = prov.search("cable", per_page=4)
    assert len(res) == 4
    assert all(v.video_url == "" for v in res)  # mock 은 실제 URL 없음


# ---------------- 자막 ----------------
def test_ass_timestamp_format():
    assert _ts(0) == "0:00:00.00"
    assert _ts(65.5) == "0:01:05.50"


def test_ass_wraps_long_caption_two_lines():
    wrapped = _wrap_two_lines("케이블 정리 이거 하나면 완전 끝이에요 정말", max_chars=10)
    assert "\\N" in wrapped
    assert wrapped.count("\\N") == 1  # 2줄 이하


def test_build_ass_writes_dialogue(tmp_path):
    out = tmp_path / "s.ass"
    build_ass([{"start": 0.0, "end": 3.0, "text": "안녕"}], str(out))
    content = out.read_text(encoding="utf-8")
    assert "Dialogue:" in content
    assert "PlayResY: 1920" in content


# ---------------- 경제적 이해관계 문구 ----------------
def test_disclosure_prepended_first_line():
    body = prepend_disclosure("본문 내용")
    assert body.startswith(DISCLOSURE_TEXT[:10])
    assert "본문 내용" in body


def test_disclosure_not_duplicated():
    once = prepend_disclosure("본문")
    twice = prepend_disclosure(once)
    assert twice.count(DISCLOSURE_TEXT[:20]) == 1


# ---------------- 어필리에이트 ----------------
def test_affiliate_category_mapping():
    assert providers_for_category("수납/정리")[0] == "ohouse"
    assert providers_for_category("패션잡화")[0] == "musinsa"
    # 미매칭 카테고리 → 기본값
    assert "coupang" in providers_for_category("알수없음")


def test_affiliate_links_have_slug():
    links = build_affiliate_links("케이블 홀더", "수납/정리")
    assert all(l.product_slug for l in links)
    assert links[0].provider == "ohouse"


# ---------------- 링크 라우터 ----------------
def test_tracking_urls_per_platform():
    urls = build_tracking_urls("https://x.com/go", "케이블 홀더", ["youtube_shorts", "threads"])
    assert urls["youtube_shorts"].endswith("?src=youtube_shorts")
    assert "/go/" in urls["threads"]


# ---------------- TTS 팩토리 폴백 (PR 리뷰) ----------------
def test_tts_stub_providers_fall_back_to_mock():
    # gemini/typecast 는 미구현 → 생성 시점에 실패하고 Mock 으로 폴백해야 한다
    assert isinstance(get_tts_provider("gemini", allow_fallback=True), MockTTSProvider)
    assert isinstance(get_tts_provider("typecast", allow_fallback=True), MockTTSProvider)
    # 폴백 비활성 시에는 예외 전파
    import pytest
    with pytest.raises(Exception):
        get_tts_provider("gemini", allow_fallback=False)


# ---------------- product_id 슬러그 정규화 (PR 리뷰) ----------------
def test_en_slug_sanitizes_dirty_source_site():
    # 한글 전용 상품명 → source_site 폴백. '/'·공백·구두점이 있어도 안전해야 한다
    slug = _en_slug("케이블 정리 홀더", "1688/특가 세일!")
    assert "/" not in slug and " " not in slug
    assert all(c.isalnum() or c == "-" for c in slug)
    assert slug  # 비어있지 않음


def test_en_slug_prefers_ascii_product_name():
    assert _en_slug("Cable Holder", "1688") == "cable-holder"


# ---------------- 패키지 빌더 (통합) ----------------
def test_build_packages_full(tmp_path):
    scenes = [
        {"scene": 1, "role": "hook", "voice_text": "훅", "caption_text": "훅 캡션"},
        {"scene": 2, "role": "problem", "voice_text": "문제 설명", "caption_text": "문제"},
        {"scene": 3, "role": "solution", "voice_text": "해결책", "caption_text": "해결"},
    ]
    summary = build_packages(
        product_id="test_001", product_ko="케이블 홀더", category="수납/정리",
        scenes=scenes, out_dir=str(tmp_path), link_router_base="https://x.com/go",
        platforms=["naver_clip", "instagram_reels", "tiktok_lite"],
    )
    assert summary["disclosure_ok"] is True
    assert set(summary["platforms"]) == {"naver_clip", "instagram_reels", "tiktok_lite"}
    # 필수 파일 존재
    assert (tmp_path / "instagram_reels" / "caption.txt").exists()
    assert (tmp_path / "tiktok_lite" / "hashtags.txt").exists()
    assert (tmp_path / "affiliate" / "links.json").exists()
    assert (tmp_path / "tracking" / "tracking_urls.json").exists()
    # 본문 첫 줄 경제적 이해관계 문구
    caption = (tmp_path / "instagram_reels" / "caption.txt").read_text(encoding="utf-8")
    assert caption.startswith(DISCLOSURE_TEXT[:10])
    # 어필리에이트 순서(수납/정리 → ohouse 우선)
    aff = json.loads((tmp_path / "affiliate" / "links.json").read_text(encoding="utf-8"))
    assert aff["providers"][0]["provider"] == "ohouse"
