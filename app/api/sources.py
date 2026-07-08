"""수집 엔드포인트 — 크롬 확장 / 수동 입력이 상품 정보를 보낸다.

POST /api/import-source
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.models import SourcePayload
from app.db.database import get_session
from app.schemas import ImportSourceRequest, ProjectOut
from app.services import project_service

router = APIRouter(prefix="/api", tags=["sources"])


@router.post("/import-source", response_model=ProjectOut)
def import_source(payload: ImportSourceRequest, db: Session = Depends(get_session)):
    """확장/수동 수집 데이터로 프로젝트 초안을 생성한다.

    - source_site 미지정 시 URL 로 자동 추정
    - product_ko 미지정 시 후보/제목에서 첫 값 사용
    - usage_status 는 항상 '확인 필요' 로 시작 (권리 확인 필수)
    """
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
