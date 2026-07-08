"""수집 엔드포인트 — 크롬 확장 / 수동 입력이 상품 정보를 보낸다.

POST /api/import-source
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.models import USAGE_UNKNOWN, SourcePayload
from app.db.database import get_session
from app.db.models_orm import Project, SourceAsset
from app.schemas import ImportSourceRequest, ProjectOut
from app.services import project_service

router = APIRouter(prefix="/api", tags=["sources"])


def _find_existing(db: Session, url: str) -> Project | None:
    """동일 source_url 로 이미 수집된 프로젝트를 찾는다 (중복 수집 방지)."""
    if not url.strip():
        return None
    return db.execute(
        select(Project).where(Project.source_url == url).order_by(Project.created_at.desc())
    ).scalars().first()


def _append_new_assets(
    db: Session, project: Project,
    image_urls: list[str], video_candidates: list[str],
) -> int:
    """기존 프로젝트에 아직 없는 자산 URL 만 추가한다."""
    known = {a.source_url for a in project.assets}
    added = 0
    for url in video_candidates:
        if url and url not in known:
            db.add(SourceAsset(project_id=project.id, asset_type="video",
                               source_url=url, usage_status=USAGE_UNKNOWN))
            known.add(url)
            added += 1
    for url in image_urls:
        if url and url not in known:
            db.add(SourceAsset(project_id=project.id, asset_type="image",
                               source_url=url, usage_status=USAGE_UNKNOWN))
            known.add(url)
            added += 1
    return added


@router.post("/import-source", response_model=ProjectOut)
def import_source(payload: ImportSourceRequest, db: Session = Depends(get_session)):
    """확장/수동 수집 데이터로 프로젝트 초안을 생성한다.

    - source_site 미지정 시 URL 로 자동 추정
    - product_ko 미지정 시 후보/제목에서 첫 값 사용
    - usage_status 는 항상 '확인 필요' 로 시작 (권리 확인 필수)
    - 동일 source_url 재수집 시 새 프로젝트를 만들지 않고 기존 프로젝트에
      새 자산만 추가해 반환한다 (중복 수집 방지)
    """
    existing = _find_existing(db, payload.url)
    if existing is not None:
        _append_new_assets(db, existing, payload.image_urls, payload.video_candidates)
        db.flush()  # autoflush=False 이므로 스냅샷 전에 관계 반영
        db.expire(existing, ["assets"])
        project_service.write_snapshot(db, existing)
        db.commit()
        db.refresh(existing)
        return existing

    sp = SourcePayload(
        url=payload.url,
        title=payload.title,
        selected_text=payload.selected_text,
        product_name_candidates=payload.product_name_candidates,
        image_urls=payload.image_urls,
        video_candidates=payload.video_candidates,
        source_site=payload.source_site,
    )
    site = sp.guess_source_site()

    product_ko = payload.product_ko.strip()
    if not product_ko:
        if payload.product_name_candidates:
            product_ko = payload.product_name_candidates[0].strip()
        else:
            product_ko = (payload.title or "미정 상품").strip()

    project = project_service.create_project(
        db,
        product_ko=product_ko,
        category=payload.category,
        source_site=site,
        source_url=payload.url,
        selected_text=payload.selected_text,
        image_urls=payload.image_urls,
        video_candidates=payload.video_candidates,
    )
    db.commit()
    db.refresh(project)
    return project
