"""내장 스타일 프리셋.

각 프리셋은 프로젝트에 적용 시 아래를 세팅한다:
 - subtitle_style : ASS 자막 스타일(폰트/크기/색/외곽선/박스/위치)
 - edit_settings  : 배경색/전환/BGM 볼륨 등
 - script_tone    : 대본 생성기에 주는 톤/구조 힌트

기성 상용 템플릿을 복제하지 않고, 흔한 숏폼 패턴을 자체 프리셋으로 구성한다.
색상은 ASS 포맷(&HAABBGGRR, AA=투명도 00=불투명).
"""

from __future__ import annotations

# ASS 색상 헬퍼 (참고용 상수)
WHITE = "&H00FFFFFF"
BLACK = "&H00000000"
YELLOW = "&H0000FFFF"
BOX_DARK = "&H80000000"     # 반투명 검정 박스
BOX_NONE = "&HFF000000"     # 박스 없음(완전 투명)

PRESETS: dict[str, dict] = {
    "info": {
        "id": "info",
        "name": "정보형",
        "description": "깔끔한 하단 자막 + 차분한 전환. 설명/정보 전달용.",
        "subtitle_style": {
            "font": "Noto Sans CJK KR", "size": 60, "primary": WHITE,
            "outline_color": BLACK, "box_color": BOX_DARK, "bold": 1,
            "border_style": 3, "outline": 2, "shadow": 1,
            "alignment": 2, "margin_v": 210, "wrap_max": 18,
        },
        "edit_settings": {
            "bg_color": "#12151b", "transition": "fade",
            "transition_duration": 0.25, "bgm_volume": 0.15,
        },
        "script_tone": "차분하고 신뢰감 있는 정보 전달, 과장 없이",
    },
    "review": {
        "id": "review",
        "name": "리뷰형",
        "description": "굵은 노란 강조 자막 + 빠른 전환. 후기/추천 톤.",
        "subtitle_style": {
            "font": "Noto Sans CJK KR", "size": 66, "primary": YELLOW,
            "outline_color": BLACK, "box_color": BOX_NONE, "bold": 1,
            "border_style": 1, "outline": 4, "shadow": 2,
            "alignment": 2, "margin_v": 240, "wrap_max": 15,
        },
        "edit_settings": {
            "bg_color": "#1a1200", "transition": "fade",
            "transition_duration": 0.18, "bgm_volume": 0.2,
        },
        "script_tone": "친근한 후기체, 실사용 느낌으로 추천",
    },
    "before_after": {
        "id": "before_after",
        "name": "전후비교",
        "description": "중앙 강조 자막 + 페이드. Before/After 변화 강조.",
        "subtitle_style": {
            "font": "Noto Sans CJK KR", "size": 70, "primary": WHITE,
            "outline_color": BLACK, "box_color": BOX_DARK, "bold": 1,
            "border_style": 3, "outline": 3, "shadow": 2,
            "alignment": 8, "margin_v": 120, "wrap_max": 14,
        },
        "edit_settings": {
            "bg_color": "#0e1116", "transition": "fade",
            "transition_duration": 0.35, "bgm_volume": 0.18,
        },
        "script_tone": "문제→해결 대비 강조, 전후 변화가 확 느껴지게",
    },
    "hook": {
        "id": "hook",
        "name": "훅강조",
        "description": "큼직한 세로 자막 + 빠른 컷. 첫 3초 임팩트 극대화.",
        "subtitle_style": {
            "font": "Noto Sans CJK KR", "size": 76, "primary": WHITE,
            "outline_color": BLACK, "box_color": BOX_NONE, "bold": 1,
            "border_style": 1, "outline": 5, "shadow": 3,
            "alignment": 2, "margin_v": 300, "wrap_max": 12,
        },
        "edit_settings": {
            "bg_color": "#000000", "transition": "none",
            "transition_duration": 0.0, "bgm_volume": 0.22,
        },
        "script_tone": "강한 후킹 위주, 짧고 임팩트 있는 문장",
    },
}


def list_presets() -> list[dict]:
    """UI 표시용 목록 (id/name/description)."""
    return [{"id": p["id"], "name": p["name"], "description": p["description"]}
            for p in PRESETS.values()]


def get_preset(template_id: str) -> dict | None:
    return PRESETS.get(template_id)
