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
from engine.subtitle.ass_builder import build_ass, _ts, _wrap_two_lines, _style_line
from engine.template import get_preset, list_presets
from engine.script.filler import fill_scene_texts
from app.services.storyline_service import _assign_role
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


# ---------------- 스토리라인 워크플로우 (영상→대본) ----------------
class _FakeClaude:
    """Claude 역할: 컷 순서에 맞춘 대본 JSON 을 반환한다(실제 키 없이 경로 검증)."""
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    def complete(self, prompt, *, system="", max_tokens=2000, temperature=0.7):
        self.calls += 1
        return self._payload


def test_fill_scene_texts_uses_llm_output_in_order():
    clips_info = [
        {"scene_no": 1, "role": "hook", "clip_id": "clip_001", "tags": ["before_after"], "description": "전후"},
        {"scene_no": 2, "role": "cta", "clip_id": "clip_002", "tags": [], "description": "제품"},
    ]
    claude = _FakeClaude(
        '[{"voice_text":"이 장면 보고 바로 샀어요","caption_text":"보고 바로 샀다"},'
        '{"voice_text":"자세한 건 아래 링크에서","caption_text":"아래 링크 확인"}]'
    )
    out = fill_scene_texts(claude, product_ko="케이블 홀더", category="수납/정리",
                           tone="후기체", clips_info=clips_info)
    assert claude.calls == 1
    assert out[1]["voice_text"] == "이 장면 보고 바로 샀어요"     # 컷1 = LLM 첫 항목
    assert out[2]["caption_text"] == "아래 링크 확인"             # 컷2 = LLM 둘째 항목


def test_fill_scene_texts_falls_back_on_bad_llm():
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("no key")
    clips_info = [{"scene_no": 1, "role": "hook", "clip_id": "c1", "tags": [], "description": ""}]
    out = fill_scene_texts(Boom(), product_ko="상품", category="", tone="", clips_info=clips_info)
    assert out[1]["voice_text"]  # Mock 폴백으로 비어있지 않음


def test_storyline_role_assignment():
    assert _assign_role(0, 5) == "hook"
    assert _assign_role(4, 5) == "cta"
    assert _assign_role(1, 5) in ("problem", "solution", "proof")


# ---------------- LLM 모델 목록 (Fable 5 반영) ----------------
def test_claude_models_include_fable_and_valid_ids():
    from engine.llm.factory import AVAILABLE_MODELS
    claude = AVAILABLE_MODELS["claude"]
    assert "claude-fable-5" in claude
    assert claude[0] == "claude-opus-4-8"  # 기본 권장 모델 유지
    # 잘못된(날짜 접미사) ID 가 목록에 없어야 함
    assert all(not m.endswith("20251001") for m in claude)


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


def test_build_ass_renders_persistent_title(tmp_path):
    out = tmp_path / "s.ass"
    build_ass([{"start": 0, "end": 3, "text": "자막"}], str(out),
              title="상단 제목", title_style={"primary": "&H0000FFFF"}, total_end=3.0)
    content = out.read_text(encoding="utf-8")
    assert "Style: Title" in content
    assert ",Title,," in content       # 제목 Dialogue 존재
    assert "상단 제목" in content


def test_build_ass_no_title_when_style_absent(tmp_path):
    out = tmp_path / "s.ass"
    build_ass([{"start": 0, "end": 3, "text": "자막"}], str(out), title="무시됨")
    content = out.read_text(encoding="utf-8")
    assert "Style: Title" not in content  # title_style 없으면 제목 미표시


def test_build_ass_applies_template_style(tmp_path):
    out = tmp_path / "s.ass"
    build_ass([{"start": 0, "end": 2, "text": "x"}], str(out),
              style={"size": 88, "primary": "&H0000FFFF"})
    style_line = [l for l in out.read_text(encoding="utf-8").splitlines()
                  if l.startswith("Style: Caption")][0]
    assert ",88," in style_line and "&H0000FFFF" in style_line


# ---------------- 템플릿 프리셋 ----------------
def test_template_presets_have_required_fields():
    ids = {t["id"] for t in list_presets()}
    assert {"basic", "issue_card", "drama_mint", "review"} <= ids
    p = get_preset("drama_mint")
    assert p["subtitle_style"]["primary"] and "edit_settings" in p
    assert p["fit_mode"] == "contain" and p["show_title"] is True
    # 기본(자막만)은 cover + 제목 없음
    b = get_preset("basic")
    assert b["fit_mode"] == "cover" and b["show_title"] is False
    assert get_preset("nope") is None


def test_style_line_reflects_overrides():
    from engine.subtitle.ass_builder import DEFAULT_SUBTITLE_STYLE
    line = _style_line("Caption", {"size": 99, "alignment": 8}, DEFAULT_SUBTITLE_STYLE)
    assert ",99," in line and line.startswith("Style: Caption,")


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


# ---------------- 렌더러: 슬로모/크로스페이드 (Fable 리뷰 A) ----------------
def test_slowmo_stretch_within_limit():
    from engine.render.ffmpeg_renderer import _slowmo

    # 2초 컷을 3초로: 1.5배 슬로모, 패딩 없음
    slow, pad = _slowmo(2.0, 3.0)
    assert abs(slow - 1.5) < 1e-6
    assert pad == 0

def test_slowmo_caps_at_max_and_pads_rest():
    from engine.render.ffmpeg_renderer import _slowmo

    # 2초 컷을 5초로: 최대 2배 → 4초, 나머지 1초는 tpad
    slow, pad = _slowmo(2.0, 5.0)
    assert slow == 2.0
    assert abs(pad - 1.0) < 1e-6

def test_slowmo_no_stretch_when_long_enough():
    from engine.render.ffmpeg_renderer import _slowmo

    slow, pad = _slowmo(5.0, 3.0)
    assert slow == 1.0 and pad == 0

def test_xfade_offsets_preserve_total_duration():
    from engine.render.ffmpeg_renderer import _xfade_filter

    # 핵심 불변식: xfade offset_i = 앞 씬 길이 누적합 → 총 길이 = Σdur (자막/TTS 싱크 유지)
    fc, vlabel = _xfade_filter([3.0, 4.0, 2.0], 0.3)
    assert "offset=3.000" in fc
    assert "offset=7.000" in fc
    assert vlabel == "vx2"
    # 오디오는 씬 길이 그대로 잘라 concat (tail 은 비디오 전용)
    assert "atrim=0:3.000" in fc and "atrim=0:4.000" in fc and "atrim=0:2.000" in fc
    assert "concat=n=3:v=0:a=1[aout]" in fc


# ---------------- 프롬프트: 발화 길이 연동 (Fable 리뷰 C) ----------------
def test_script_rules_contain_chars_per_sec():
    from engine.script.base import CHARS_PER_SEC, SCRIPT_RULES

    assert CHARS_PER_SEC == 5.5
    assert str(CHARS_PER_SEC) in SCRIPT_RULES
    assert "target_duration" in SCRIPT_RULES

def test_filler_prompt_includes_char_budget():
    from engine.script.filler import _build_prompt

    p = _build_prompt("케이블 홀더", "살림템", "", [
        {"scene_no": 1, "role": "hook", "clip_id": "clip_001",
         "tags": [], "description": "", "duration": 3.0},
    ], product_zh="桌面理线器")
    assert "약 16자" in p         # 3.0초 × 5.5자 ≈ 16자
    assert "桌面理线器" in p       # C3: 중국어 원문 컨텍스트

def test_llm_parse_clamps_target_duration():
    from engine.script.llm_generator import LLMScriptGenerator

    gen = LLMScriptGenerator(llm=None)
    scenes = gen._parse(
        '[{"scene":1,"role":"hook","voice_text":"a","target_duration":60},'
        '{"scene":2,"role":"cta","voice_text":"b","target_duration":0.2}]'
    )
    assert scenes[0].target_duration == 15.0
    assert scenes[1].target_duration == 1.0


# ---------------- ASS 타임스탬프 반올림 (백엔드 결함 수정) ----------------
def test_ass_ts_rounds_to_valid_timestamp():
    from engine.subtitle.ass_builder import _ts

    assert _ts(59.999) == "0:01:00.00"  # 59.999초는 60.00초가 아니라 다음 분으로 반올림
    assert _ts(0.0) == "0:00:00.00"
    assert _ts(3661.5) == "1:01:01.50"


# ---------------- SceneOut order_index 노출 (백엔드 결함 수정) ----------------
def test_scene_out_exposes_order_index():
    from app.schemas import SceneOut

    assert "order_index" in SceneOut.model_fields
