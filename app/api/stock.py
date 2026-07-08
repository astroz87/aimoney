"""스톡 영상 검색/삽입 API.

GET  /api/stock/search?q=...&provider=...
POST /api/projects/{id}/stock/import  {video_url, source_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models_orm import Project
from app.services import stock_service

router = APIRouter(prefix="/api", tags=["stock"])


@router.get("/stock/search")
def stock_search(
    q: str = Query(..., min_length=1),
    provider: str | None = None,
    per_page: int = 12,
):
    try:
        results = stock_service.search(q, provider=provider, per_page=per_page)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"스톡 검색 실패: {exc}")
    return {"results": results, "count": len(results)}


class StockImportRequest(BaseModel):
    video_url: str
    source_id: str = ""


@router.post("/projects/{product_id}/stock/import")
def stock_import(
    product_id: str, payload: StockImportRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    try:
        result = stock_service.import_video(
            product_id, payload.video_url, source_id=payload.source_id
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"스톡 삽입 실패: {exc}")
    return result
