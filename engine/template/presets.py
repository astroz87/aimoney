"""내장 스타일 프리셋.

각 프리셋 적용 시 프로젝트에 세팅되는 값:
 - fit_mode        : cover(꽉채우기) | contain(박스형: 배경 여백에 제목/자막)
 - show_title      : 상단 고정 제목 표시 여부
 - title_style     : 상단 제목 ASS 스타일
 - subtitle_style  : 하단 자막 ASS 스타일
 - edit_settings   : 배경색/전환/BGM 볼륨
 - script_tone     : 대본 생성기 톤 힌트

상용 템플릿을 복제하지 않고, 흔한 숏폼 패턴을 자체 프리셋으로 구성한다.
색상은 ASS(&HAABBGGRR, AA=투명도 00=불투명).
"""

from __future__ import annotations

WHITE = "&H00FFFFFF"
BLACK = "&H00000000"
YELLOW = "&H0000FFFF"
GREEN = "&H0000FF00"        # 민트/그린 자동자막
NEAR_BLACK = "&H00202020"
BOX_DARK = "&H80000000"     # 반투명 검정 박스
BOX_NONE = "&HFF000000"     # 박스 없음(완전 투명)


def _title(size=78, primary=YELLOW, box=BOX_NONE, align=8, mv=120, outline=4, wrap=16):
    return {
        "font": "Noto Sans CJK KR", "size": size, "primary": primary,
        "outline_color": BLACK, "box_color": box, "bold": 1,
        "border_style": 1 if box == BOX_NONE else 3, "outline": outline, "shadow": 2,
        "alignment": align, "margin_v": mv, "wrap_max": wrap,
    }


def _cap(size=62, primary=WHITE, box=BOX_NONE, align=2, mv=220, outline=4, wrap=15):
    return {
        "font": "Noto Sans CJK KR", "size": size, "primary": primary,
        "outline_color": BLACK, "box_color": box, "bold": 1,
        "border_style": 1 if box == BOX_NONE else 3, "outline": outline, "shadow": 2,
        "alignment": align, "margin_v": mv, "wrap_max": wrap,
    }


PRESETS: dict[str, dict] = {
    # --- 쇼핑 쇼츠 기본: 영상 꽉 채우고 하단 자막만 ---
    "basic": {
        "id": "basic",
        "name": "기본 (자막만)",
        "description": "영상을 꽉 채우고 하단 자막만. 쇼핑/제품 쇼츠 기본값.",
        "fit_mode": "cover", "show_title": False,
        "title_style": {},
        "subtitle_style": _cap(size=60, primary=WHITE, box=BOX_DARK, mv=210, outline=2, wrap=18),
        "edit_settings": {"bg_color": "#000000", "transition": "none",
                          "transition_duration": 0.0, "bgm_volume": 0.18},
        "script_tone": "제품 장점을 간결하게, 문제해결형",
    },
    # --- 박스형 이슈/카드뉴스 (흰 배경) ---
    "issue_card": {
        "id": "issue_card",
        "name": "이슈카드 (박스·흰배경)",
        "description": "박스형 영상 + 흰 배경. 상단 검정 제목 + 하단 자막. 이슈/사연형.",
        "fit_mode": "contain", "show_title": True,
        "title_style": _title(size=72, primary=BLACK, box=BOX_NONE, align=8, mv=90, outline=3, wrap=17),
        "subtitle_style": _cap(size=60, primary=NEAR_BLACK, box=BOX_NONE, align=2, mv=150, outline=3, wrap=18),
        "edit_settings": {"bg_color": "#f4f4f4", "transition": "fade",
                          "transition_duration": 0.2, "bgm_volume": 0.15},
        "script_tone": "이슈/사연 전달, 궁금증 유발",
    },
    # --- 드라마·클립 민트 자막 (검정 배경, 노랑 제목) ---
    "drama_mint": {
        "id": "drama_mint",
        "name": "드라마·민트자막",
        "description": "노랑 상단 제목 + 민트 그린 하단 자막(검정 외곽선). 드라마/클립 반응형.",
        "fit_mode": "contain", "show_title": True,
        "title_style": _title(size=76, primary=YELLOW, box=BOX_NONE, align=8, mv=110, outline=4, wrap=16),
        "subtitle_style": _cap(size=64, primary=GREEN, box=BOX_NONE, align=2, mv=170, outline=5, wrap=15),
        "edit_settings": {"bg_color": "#000000", "transition": "fade",
                          "transition_duration": 0.2, "bgm_volume": 0.2},
        "script_tone": "몰입감 있는 사연/드라마 나레이션",
    },
    # --- 건강/정보형 (노랑 2줄 제목 + 흰 자막) ---
    "health_info": {
        "id": "health_info",
        "name": "건강/정보형",
        "description": "노랑 상단 2줄 제목 + 흰 하단 자막. 운동/건강/정보 전달.",
        "fit_mode": "contain", "show_title": True,
        "title_style": _title(size=80, primary=YELLOW, box=BOX_NONE, align=8, mv=100, outline=5, wrap=13),
        "subtitle_style": _cap(size=62, primary=WHITE, box=BOX_NONE, align=2, mv=180, outline=4, wrap=16),
        "edit_settings": {"bg_color": "#000000", "transition": "fade",
                          "transition_duration": 0.25, "bgm_volume": 0.18},
        "script_tone": "차분하고 신뢰감 있는 정보 전달",
    },
    # --- 기존 스타일 프리셋 (cover, 제목 없음) ---
    "review": {
        "id": "review",
        "name": "리뷰형",
        "description": "굵은 노란 강조 자막 + 빠른 전환. 후기/추천 톤.",
        "fit_mode": "cover", "show_title": False, "title_style": {},
        "subtitle_style": _cap(size=66, primary=YELLOW, box=BOX_NONE, mv=240, outline=4, wrap=15),
        "edit_settings": {"bg_color": "#1a1200", "transition": "fade",
                          "transition_duration": 0.18, "bgm_volume": 0.2},
        "script_tone": "친근한 후기체, 실사용 느낌으로 추천",
    },
    "before_after": {
        "id": "before_after",
        "name": "전후비교",
        "description": "중앙 강조 자막 + 페이드. Before/After 변화 강조.",
        "fit_mode": "cover", "show_title": False, "title_style": {},
        "subtitle_style": _cap(size=70, primary=WHITE, box=BOX_DARK, align=8, mv=120, outline=3, wrap=14),
        "edit_settings": {"bg_color": "#0e1116", "transition": "fade",
                          "transition_duration": 0.35, "bgm_volume": 0.18},
        "script_tone": "문제→해결 대비 강조, 전후 변화가 확 느껴지게",
    },
    "hook": {
        "id": "hook",
        "name": "훅강조",
        "description": "큼직한 세로 자막 + 빠른 컷. 첫 3초 임팩트 극대화.",
        "fit_mode": "cover", "show_title": False, "title_style": {},
        "subtitle_style": _cap(size=76, primary=WHITE, box=BOX_NONE, mv=300, outline=5, wrap=12),
        "edit_settings": {"bg_color": "#000000", "transition": "none",
                          "transition_duration": 0.0, "bgm_volume": 0.22},
        "script_tone": "강한 후킹 위주, 짧고 임팩트 있는 문장",
    },
}


def list_presets() -> list[dict]:
    return [{"id": p["id"], "name": p["name"], "description": p["description"]}
            for p in PRESETS.values()]


def get_preset(template_id: str) -> dict | None:
    return PRESETS.get(template_id)
