"""대본 API.

POST /api/projects/{id}/script   → 대본 생성 (provider 선택)
PUT  /api/projects/{id}/script   → 편집된 대본 저장
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models_orm import Project
from app.schemas import ScriptRequest, ScriptSaveRequest
from app.services import script_service

router = APIRouter(prefix="/api/projects/{product_id}/script", tags=["script"])


@router.post("")
def generate_script(
    product_id: str, payload: ScriptRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    scenes = script_service.generate_script(product_id, provider=payload.provider)
    return {"scenes": scenes}


@router.put("")
def save_script(
    product_id: str, payload: ScriptSaveRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    script_service.save_scenes_from_dicts(product_id, payload.scenes)
    return {"saved": len(payload.scenes)}
