"""SQLAlchemy ORM 테이블 정의.

계획 문서의 데이터 모델을 그대로 구현한다. JSON 성격의 필드는 SQLite JSON 컬럼을
사용하고, 상태/열거형은 문자열로 저장한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engine.models import USAGE_UNKNOWN
from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    # product_id 를 PK 로 사용 (예: "20260707_cable_holder_001")
    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_ko: Mapped[str] = mapped_column(String, default="")
    product_zh: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="")
    source_site: Mapped[str] = mapped_column(String, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    selected_text: Mapped[str] = mapped_column(Text, default="")
    zh_search_queries: Mapped[list] = mapped_column(JSON, default=list)
    usage_status: Mapped[str] = mapped_column(String, default=USAGE_UNKNOWN)
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    assets: Mapped[list["SourceAsset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    clips: Mapped[list["Clip"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    timeline_items: Mapped[list["TimelineItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    affiliate_links: Mapped[list["AffiliateLink"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    renders: Mapped[list["Render"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class SourceAsset(Base):
    __tablename__ = "source_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    asset_type: Mapped[str] = mapped_column(String, default="video")  # image | video
    source_url: Mapped[str] = mapped_column(Text, default="")  # ★권리 추적 필수
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_status: Mapped[str] = mapped_column(String, default=USAGE_UNKNOWN)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="assets")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    source_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_assets.id"), nullable=True
    )
    clip_id: Mapped[str] = mapped_column(String)  # "clip_001"
    source_video: Mapped[str] = mapped_column(Text, default="")
    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    brightness_score: Mapped[float] = mapped_column(Float, default=0.0)
    motion_score: Mapped[float] = mapped_column(Float, default=0.0)
    blur_score: Mapped[float] = mapped_column(Float, default=0.0)
    hook_score: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")

    project: Mapped["Project"] = relationship(back_populates="clips")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    scene_no: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String, default="hook")
    voice_text: Mapped[str] = mapped_column(Text, default="")
    caption_text: Mapped[str] = mapped_column(Text, default="")
    visual_need: Mapped[str] = mapped_column(Text, default="")
    target_duration: Mapped[float] = mapped_column(Float, default=3.0)
    emotion: Mapped[str] = mapped_column(String, default="neutral")
    pace: Mapped[str] = mapped_column(String, default="normal")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    # 편집기에서 수동 지정한 컷 (비면 매처 자동 선택)
    preferred_clip_id: Mapped[str] = mapped_column(String, default="")

    project: Mapped["Project"] = relationship(back_populates="scenes")
    tts_result: Mapped["TTSResult | None"] = relationship(
        back_populates="scene", cascade="all, delete-orphan", uselist=False
    )


class TTSResult(Base):
    __tablename__ = "tts_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id"))
    provider: Mapped[str] = mapped_column(String, default="")
    audio_path: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    scene: Mapped["Scene"] = relationship(back_populates="tts_result")


class TimelineItem(Base):
    __tablename__ = "timeline_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    scene_no: Mapped[int] = mapped_column(Integer)
    clip_id: Mapped[str] = mapped_column(String, default="")
    video_start: Mapped[float] = mapped_column(Float, default=0.0)
    video_end: Mapped[float] = mapped_column(Float, default=0.0)
    timeline_start: Mapped[float] = mapped_column(Float, default=0.0)
    timeline_end: Mapped[float] = mapped_column(Float, default=0.0)
    audio_path: Mapped[str] = mapped_column(Text, default="")

    project: Mapped["Project"] = relationship(back_populates="timeline_items")


class AffiliateLink(Base):
    __tablename__ = "affiliate_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    provider: Mapped[str] = mapped_column(String)
    raw_url: Mapped[str] = mapped_column(Text, default="")
    tracking_url: Mapped[str] = mapped_column(Text, default="")
    product_slug: Mapped[str] = mapped_column(String, default="")

    project: Mapped["Project"] = relationship(back_populates="affiliate_links")


class Render(Base):
    __tablename__ = "renders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    video_path: Mapped[str] = mapped_column(Text, default="")
    thumbnail_path: Mapped[str] = mapped_column(Text, default="")
    subtitle_path: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="pending")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="renders")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    job_type: Mapped[str] = mapped_column(String)  # analyze|tts|render|package
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|done|failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="jobs")


class Setting(Base):
    """런타임 설정 (LLM/TTS 프로바이더·모델·키). DB > .env > 기본값."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
