"""API 요청/응답 Pydantic 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# 수집 (import-source) — 크롬 확장 / 수동 입력
# ----------------------------------------------------------------------
class ImportSourceRequest(BaseModel):
    url: str = ""
    title: str = ""
    selected_text: str = ""
    product_name_candidates: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    video_candidates: list[str] = Field(default_factory=list)
    source_site: str = ""
    # 선택: 사용자가 확장/대시보드에서 직접 지정
    product_ko: str = ""
    category: str = ""


# ----------------------------------------------------------------------
# 프로젝트
# ----------------------------------------------------------------------
class ProjectCreate(BaseModel):
    product_ko: str = ""
    product_zh: str = ""
    category: str = ""
    source_site: str = ""
    source_url: str = ""
    selected_text: str = ""
    image_urls: list[str] = Field(default_factory=list)
    video_candidates: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    product_ko: Optional[str] = None
    product_zh: Optional[str] = None
    category: Optional[str] = None
    usage_status: Optional[str] = None
    status: Optional[str] = None
    zh_search_queries: Optional[list[str]] = None


class AssetOut(BaseModel):
    id: int
    asset_type: str
    source_url: str
    local_path: Optional[str]
    usage_status: str

    class Config:
        from_attributes = True


class ClipOut(BaseModel):
    clip_id: str
    source_video: str
    start: float
    end: float
    duration: float
    tags: list[str]
    quality_score: float
    motion_score: float
    hook_score: float
    description: str

    class Config:
        from_attributes = True


class SceneOut(BaseModel):
    scene_no: int
    order_index: int = 0
    role: str
    voice_text: str
    caption_text: str
    visual_need: str
    target_duration: float
    emotion: str
    pace: str
    preferred_clip_id: str = ""
    sfx_path: str = ""

    class Config:
        from_attributes = True


class ProjectOut(BaseModel):
    id: str
    product_ko: str
    product_zh: str
    category: str
    source_site: str
    source_url: str
    selected_text: str
    zh_search_queries: list[str]
    usage_status: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailOut(ProjectOut):
    assets: list[AssetOut] = Field(default_factory=list)
    clips: list[ClipOut] = Field(default_factory=list)
    scenes: list[SceneOut] = Field(default_factory=list)


class JobOut(BaseModel):
    id: int
    project_id: str
    job_type: str
    status: str
    progress: int
    log: str

    class Config:
        from_attributes = True


# ----------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    """부분 업데이트: 전달된 키만 저장. 마스킹된 비밀값은 서버가 무시."""

    values: dict[str, str] = Field(default_factory=dict)


class SettingsTestRequest(BaseModel):
    provider: str  # claude | gemini | openai


# ----------------------------------------------------------------------
# 검색어 / 대본 / TTS / 렌더 / 패키지 요청
# ----------------------------------------------------------------------
class SearchQueryRequest(BaseModel):
    product_ko: str = ""


class ScriptRequest(BaseModel):
    provider: Optional[str] = None  # None → 설정 기본값


class ScriptSaveRequest(BaseModel):
    scenes: list[dict[str, Any]]


class TTSRequest(BaseModel):
    provider: Optional[str] = None


class GenericJobResponse(BaseModel):
    job_id: int
    status: str
