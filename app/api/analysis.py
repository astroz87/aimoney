"""영상 분석 및 검색어 생성 API.

POST /api/projects/{id}/analyze          → 분석 잡 시작
POST /api/projects/{id}/search-queries   → 한→중 검색어 생성(동기)
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from engine.ingest import generate_search_queries
from app.db.database import get_session
from app.db.models_orm import Project
from app.schemas import GenericJobResponse, SearchQueryRequest
from app.services import job_service, llm_service, project_service
from app.services.analysis_service import run_analysis

router = APIRouter(prefix="/api/projects/{product_id}", tags=["analysis"])


@router.post("/analyze", response_model=GenericJobResponse)
def analyze(
    product_id: str, bg: BackgroundTasks, db: Session = Depends(get_session)
):
    project = db.get(Project, product_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    job = job_service.create_job(db, product_id, "analyze")
    db.commit()
    job_id = job.id
    bg.add_task(job_service.run_job, job_id, lambda ctx: run_analysis(product_id, ctx))
    return GenericJobResponse(job_id=job_id, status="pending")


@router.post("/search-queries")
def search_queries(
    product_id: str, payload: SearchQueryRequest, db: Session = Depends(get_session)
):
    project = db.get(Project, product_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")

    product_ko = payload.product_ko or project.product_ko
    llm = llm_service.get_provider(task="search")
    result = generate_search_queries(llm, product_ko)

    # 결과 저장
    project.zh_search_queries = result.get("search_queries", [])
    if not project.product_zh and result.get("zh_product_names"):
        project.product_zh = result["zh_product_names"][0]
    project_service.write_snapshot(db, project)
    db.commit()
    return result
