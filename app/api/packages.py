"""패키지 생성 및 다운로드 API.

POST /api/projects/{id}/package    → 패키지 생성 잡
GET  /api/projects/{id}/download   → output zip 다운로드
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from app.db.database import get_session
from app.db.models_orm import Project
from app.schemas import GenericJobResponse
from app.services import job_service
from app.services.package_service import run_package

router = APIRouter(prefix="/api/projects/{product_id}", tags=["packages"])


@router.post("/package", response_model=GenericJobResponse)
def create_package(
    product_id: str, bg: BackgroundTasks, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    job = job_service.create_job(db, product_id, "package")
    db.commit()
    job_id = job.id
    bg.add_task(job_service.run_job, job_id, lambda ctx: run_package(product_id, ctx))
    return GenericJobResponse(job_id=job_id, status="pending")


@router.get("/download")
def download_package(product_id: str, db: Session = Depends(get_session)):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    zip_path = settings.output_project_dir(product_id) / f"{product_id}_package.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="패키지가 아직 생성되지 않았습니다")
    return FileResponse(str(zip_path), filename=zip_path.name,
                        media_type="application/zip")
