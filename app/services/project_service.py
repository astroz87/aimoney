"""ProjectService — 프로젝트 생성/조회/갱신 및 project.json 스냅샷.

product_id 규칙: YYYYMMDD_{slug}_{NNN}  (예: 20260708_cable_holder_001)
DB(진실원본) + data/projects/{id}/project.json (사람 읽기용 스냅샷) 이중화.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from engine.models import USAGE_UNKNOWN, slugify
from app.db.models_orm import Project, SourceAsset


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _en_slug(product_ko: str, source_site: str) -> str:
    """product_id 용 ASCII 슬러그. 한글만 있으면 source_site 기반 대체."""
    slug = slugify(product_ko)
    # 한글만 남은 경우 ASCII 로 치환 불가 → 사이트명+timestamp 조합
    ascii_slug = "".join(ch for ch in slug if ch.isascii() and (ch.isalnum() or ch == "-"))
    ascii_slug = ascii_slug.strip("-")
    if not ascii_slug:
        ascii_slug = (source_site or "item").lower()
    return ascii_slug


def generate_product_id(db: Session, product_ko: str, source_site: str) -> str:
    """오늘 날짜 + 슬러그 + 3자리 일련번호로 고유 product_id 생성."""
    date = _today()
    slug = _en_slug(product_ko, source_site)
    prefix = f"{date}_{slug}_"
    # 같은 prefix 로 시작하는 기존 id 개수 → 다음 번호
    existing = db.execute(
        select(Project.id).where(Project.id.like(f"{prefix}%"))
    ).scalars().all()
    seq = len(existing) + 1
    while True:
        candidate = f"{prefix}{seq:03d}"
        if candidate not in existing and db.get(Project, candidate) is None:
            return candidate
        seq += 1


def create_project(
    db: Session,
    *,
    product_ko: str = "",
    product_zh: str = "",
    category: str = "",
    source_site: str = "",
    source_url: str = "",
    selected_text: str = "",
    image_urls: list[str] | None = None,
    video_candidates: list[str] | None = None,
) -> Project:
    """새 프로젝트 생성 + 영상/이미지 후보를 source_assets 로 등록."""
    product_id = generate_product_id(db, product_ko, source_site)
    project = Project(
        id=product_id,
        product_ko=product_ko,
        product_zh=product_zh,
        category=category,
        source_site=source_site,
        source_url=source_url,
        selected_text=selected_text,
        usage_status=USAGE_UNKNOWN,
        status="created",
    )
    db.add(project)
    db.flush()  # id 확정

    for url in (video_candidates or []):
        db.add(SourceAsset(
            project_id=product_id, asset_type="video",
            source_url=url, usage_status=USAGE_UNKNOWN,
        ))
    for url in (image_urls or []):
        db.add(SourceAsset(
            project_id=product_id, asset_type="image",
            source_url=url, usage_status=USAGE_UNKNOWN,
        ))

    if video_candidates or image_urls:
        project.status = "sourced"

    _ensure_dirs(product_id)
    db.flush()
    write_snapshot(db, project)
    return project


def _ensure_dirs(product_id: str) -> None:
    base = settings.project_dir(product_id)
    for sub in ("raw", "clips", "tts"):
        (base / sub).mkdir(parents=True, exist_ok=True)


def get_project(db: Session, product_id: str) -> Project | None:
    return db.get(Project, product_id)


def list_projects(db: Session) -> list[Project]:
    return db.execute(
        select(Project).order_by(Project.created_at.desc())
    ).scalars().all()


def update_project(db: Session, product_id: str, fields: dict) -> Project | None:
    project = db.get(Project, product_id)
    if project is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(project, key):
            setattr(project, key, value)
    db.flush()
    write_snapshot(db, project)
    return project


def write_snapshot(db: Session, project: Project) -> None:
    """project.json 스냅샷을 data/projects/{id}/ 에 기록."""
    base = settings.project_dir(project.id)
    base.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "product_id": project.id,
        "product_ko": project.product_ko,
        "product_zh": project.product_zh,
        "category": project.category,
        "source_site": project.source_site,
        "source_url": project.source_url,
        "selected_text": project.selected_text,
        "zh_search_queries": project.zh_search_queries or [],
        "usage_status": project.usage_status,
        "status": project.status,
        "image_urls": [a.source_url for a in project.assets if a.asset_type == "image"],
        "video_candidates": [a.source_url for a in project.assets if a.asset_type == "video"],
    }
    (base / "project.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
