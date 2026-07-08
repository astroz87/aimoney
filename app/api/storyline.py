"""스토리라인 워크플로우 API (영상 먼저 조립 → 대본 넣기).

POST /api/projects/{id}/storyline     컷으로 스토리라인 조립
POST /api/projects/{id}/fill-script   조립된 스토리라인에 대본 채우기
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models_orm import Project
from app.services import storyline_service

router = APIRouter(prefix="/api/projects/{product_id}", tags=["storyline"])


class StorylineRequest(BaseModel):
    clip_ids: list[str] | None = None    # 지정 시 그 순서, 없으면 후킹순 자동
    count: int = 6


class FillScriptRequest(BaseModel):
    provider: str | None = None


@router.post("/storyline")
def build_storyline(
    product_id: str, payload: StorylineRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    try:
        scenes = storyline_service.build_storyline(
            product_id, clip_ids=payload.clip_ids, count=payload.count
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return {"scenes": scenes}


@router.post("/fill-script")
def fill_script(
    product_id: str, payload: FillScriptRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    try:
        scenes = storyline_service.fill_script(product_id, provider=payload.provider)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return {"scenes": scenes}
