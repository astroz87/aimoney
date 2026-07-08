"""템플릿 API.

GET  /api/templates                       내장 프리셋 목록
POST /api/projects/{id}/apply-template     프로젝트에 템플릿 적용
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models_orm import Project
from app.services import template_service

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/templates")
def list_templates():
    return {"templates": template_service.templates()}


class ApplyTemplateRequest(BaseModel):
    template_id: str


@router.post("/projects/{product_id}/apply-template")
def apply_template(
    product_id: str, payload: ApplyTemplateRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    try:
        result = template_service.apply_template(product_id, payload.template_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return result


class SaveTemplateRequest(BaseModel):
    name: str
    description: str = ""


@router.post("/projects/{product_id}/save-template")
def save_template(
    product_id: str, payload: SaveTemplateRequest, db: Session = Depends(get_session)
):
    if db.get(Project, product_id) is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    try:
        return template_service.save_custom(product_id, payload.name, payload.description)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    if not template_service.delete_custom(template_id):
        raise HTTPException(status_code=404, detail="커스텀 템플릿을 찾을 수 없습니다")
    return {"deleted": template_id}
