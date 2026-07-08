"""프로젝트 CRUD API.

GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PATCH  /api/projects/{id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.schemas import (
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_session)):
    return project_service.list_projects(db)


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_session)):
    project = project_service.create_project(
        db,
        product_ko=payload.product_ko,
        product_zh=payload.product_zh,
        category=payload.category,
        source_site=payload.source_site,
        source_url=payload.source_url,
        selected_text=payload.selected_text,
        image_urls=payload.image_urls,
        video_candidates=payload.video_candidates,
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/{product_id}", response_model=ProjectDetailOut)
def get_project(product_id: str, db: Session = Depends(get_session)):
    project = project_service.get_project(db, product_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    # scene_no 순 정렬된 scenes 를 위해 detail 은 관계 로딩에 의존
    detail = ProjectDetailOut.model_validate(project)
    detail.scenes.sort(key=lambda s: s.scene_no)
    detail.clips.sort(key=lambda c: c.hook_score, reverse=True)
    return detail


@router.patch("/{product_id}", response_model=ProjectOut)
def update_project(
    product_id: str, payload: ProjectUpdate, db: Session = Depends(get_session)
):
    project = project_service.update_project(
        db, product_id, payload.model_dump(exclude_none=True)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    db.commit()
    db.refresh(project)
    return project
