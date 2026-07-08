"""파이프라인 단계 간에 주고받는 도메인 데이터 구조 정의.

DB(ORM)와 별개로, 엔진 내부 계산 및 project.json 직렬화를 위한 순수 데이터클래스.
(기존 src/models.py 의 ScrapedPost/GeneratedContent 는 CLI 호환을 위해 그대로 유지)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


# ----------------------------------------------------------------------
# 열거형 성격의 상수
# ----------------------------------------------------------------------
USAGE_UNKNOWN = "확인 필요"
USAGE_CLEARED = "확인됨"
USAGE_EXCLUDED = "제외"

# 프로젝트 진행 상태머신
PROJECT_STATES = (
    "created",
    "sourced",
    "analyzed",
    "scripted",
    "voiced",
    "timelined",
    "rendered",
    "packaged",
)

# 대본 scene 역할
SCENE_ROLES = ("hook", "problem", "solution", "proof", "cta")

# 카테고리 → 어필리에이트 프로바이더 우선순위 (요구사항 기본 매칭)
CATEGORY_AFFILIATE_MAP: dict[str, list[str]] = {
    "살림템": ["coupang", "naver_shopping_connect", "ohouse"],
    "수납/정리": ["ohouse", "naver_shopping_connect", "coupang"],
    "육아템": ["coupang", "naver_shopping_connect"],
    "인테리어": ["ohouse", "naver_shopping_connect"],
    "패션잡화": ["musinsa", "coupang"],
    "차량용품": ["coupang", "naver_shopping_connect"],
}

# 어필리에이트 프로바이더 기본값 (카테고리 미매칭 시)
DEFAULT_AFFILIATE_PROVIDERS = ["coupang", "naver_shopping_connect"]

# 오디오/배경 편집 설정 기본값
DEFAULT_EDIT_SETTINGS = {
    "bg_color": "#202430",        # 컷이 없는 씬의 배경색
    "bgm_path": "",               # BGM 파일 경로 (비면 없음)
    "bgm_enabled": True,          # BGM 사용 여부
    "bgm_volume": 0.18,           # BGM 볼륨 (0~1)
    "transition": "none",         # none | fade
    "transition_duration": 0.3,   # 전환 길이(초)
    # --- 레이아웃/제목 ---
    "fit_mode": "cover",          # cover=꽉채우기 | contain=박스형
    "box_scale": 0.94,            # contain 영상 박스 가로 비율 (0.5~1.0)
    "box_h": 0.60,                # contain 영상 박스 세로 비율 (0.3~0.9)
    "box_y": 0.34,                # contain 영상 세로 위치 (0=상단, 0.5=중앙, 1=하단)
    "show_title": False,          # 상단 제목 표시 여부
    "title_text": "",             # 상단 제목 문구 (비면 hook 자막/상품명)
    "title_style": {},            # 상단 제목 스타일
    # --- 템플릿(스타일 프리셋) ---
    "template_id": "",            # 적용된 템플릿 id
    "subtitle_style": {},         # ASS 자막 스타일 오버라이드 (비면 기본)
    "script_tone": "",            # 대본 톤 힌트
}


def resolve_edit_settings(raw: dict | None) -> dict:
    """저장된 편집 설정에 기본값을 채워 반환한다."""
    merged = dict(DEFAULT_EDIT_SETTINGS)
    if raw:
        for k, v in raw.items():
            if k in merged and v is not None:
                merged[k] = v
    return merged


def now_iso() -> str:
    """UTC ISO8601 타임스탬프."""
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    """product_slug / product_id 용 슬러그화 (영숫자+하이픈)."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    return text.strip("-") or "item"


# ----------------------------------------------------------------------
# 수집 (import-source)
# ----------------------------------------------------------------------
@dataclass
class SourcePayload:
    """크롬 확장 / 수동 입력이 보내는 원시 수집 데이터."""

    url: str = ""
    title: str = ""
    selected_text: str = ""
    product_name_candidates: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    video_candidates: list[str] = field(default_factory=list)
    source_site: str = ""

    def guess_source_site(self) -> str:
        """URL 로 source_site 를 추정한다."""
        if self.source_site:
            return self.source_site
        host = self.url.lower()
        known = {
            "1688.com": "1688",
            "taobao.com": "taobao",
            "tmall.com": "tmall",
            "aliexpress.com": "aliexpress",
            "alibaba.com": "alibaba",
            "pinduoduo.com": "pinduoduo",
            "jd.com": "jd",
        }
        for domain, name in known.items():
            if domain in host:
                return name
        return "unknown"


# ----------------------------------------------------------------------
# 영상 분석 결과
# ----------------------------------------------------------------------
@dataclass
class Clip:
    """분석된 단일 컷."""

    clip_id: str
    source_video: str
    start: float
    end: float
    duration: float
    tags: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    brightness_score: float = 0.0
    motion_score: float = 0.0
    blur_score: float = 0.0
    hook_score: float = 0.0
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
# 대본 (scene 단위)
# ----------------------------------------------------------------------
@dataclass
class Scene:
    """대본 문장 단위."""

    scene: int
    role: str
    voice_text: str
    caption_text: str
    visual_need: str = ""
    target_duration: float = 3.0
    emotion: str = "neutral"
    pace: str = "normal"
    # 편집기에서 사용자가 수동 지정한 컷 (비면 매처가 자동 선택)
    preferred_clip_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
# TTS 결과
# ----------------------------------------------------------------------
@dataclass
class TTSResult:
    scene: int
    audio_path: str
    duration: float
    provider: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
# 타임라인 아이템
# ----------------------------------------------------------------------
@dataclass
class TimelineItem:
    scene: int
    clip_id: str
    video_start: float
    video_end: float
    audio_path: str
    timeline_start: float
    timeline_end: float

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
# 어필리에이트 / 트래킹
# ----------------------------------------------------------------------
@dataclass
class AffiliateLink:
    provider: str
    raw_url: str = ""
    tracking_url: str = ""
    product_slug: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
