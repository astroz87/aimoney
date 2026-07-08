"""타임라인 및 렌더 API.

POST /api/projects/{id}/timeline   → 타임라인 매칭(동기)
POST /api/projects/{id}/render     → 렌더 잡 시작
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models_orm import Project
from app.schemas import GenericJobResponse
from app.services import job_service, timeline_service
from app.services.render_service import run_render

router = APIRouter(prefix="/api/projects/{product_id}", tags=["render"])


@router.post("/timeline")
def make_timeline(product_id: str, db: Session = Depends(get_session)):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    try:
        timeline = timeline_service.build_and_save(product_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return {"timeline": timeline}


@router.post("/render", response_model=GenericJobResponse)
def render(product_id: str, bg: BackgroundTasks, db: Session = Depends(get_session)):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    job = job_service.create_job(db, product_id, "render")
    db.commit()
    job_id = job.id
    bg.add_task(job_service.run_job, job_id, lambda ctx: run_render(product_id, ctx))
    return GenericJobResponse(job_id=job_id, status="pending")
