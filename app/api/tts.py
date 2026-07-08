"""TTS API.

POST /api/projects/{id}/tts   → TTS 생성 잡 시작
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models_orm import Project
from app.schemas import GenericJobResponse, TTSRequest
from app.services import job_service
from app.services.tts_service import run_tts

router = APIRouter(prefix="/api/projects/{product_id}/tts", tags=["tts"])


@router.post("", response_model=GenericJobResponse)
def create_tts(
    product_id: str, bg: BackgroundTasks,
    payload: TTSRequest | None = None,       # 바디 생략 시 기본 프로바이더 (render 와 동일한 관례)
    db: Session = Depends(get_session),
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    job = job_service.create_job(db, product_id, "tts")
    db.commit()
    job_id = job.id
    provider = payload.provider if payload else None
    bg.add_task(job_service.run_job, job_id, lambda ctx: run_tts(product_id, ctx, provider))
    return GenericJobResponse(job_id=job_id, status="pending")
