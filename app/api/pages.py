"""HTML 대시보드 페이지 (Jinja2)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.services import project_service, settings_store

router = APIRouter(tags=["pages"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_session)):
    projects = project_service.list_projects(db)
    return templates.TemplateResponse(
        request, "dashboard.html", {"projects": projects}
    )


@router.get("/projects/{product_id}", response_class=HTMLResponse)
def project_detail(product_id: str, request: Request, db: Session = Depends(get_session)):
    project = project_service.get_project(db, product_id)
    return templates.TemplateResponse(
        request, "project.html", {"project": project}
    )


@router.get("/projects/{product_id}/editor", response_class=HTMLResponse)
def editor_page(product_id: str, request: Request, db: Session = Depends(get_session)):
    project = project_service.get_project(db, product_id)
    return templates.TemplateResponse(
        request, "editor.html", {"project": project}
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(
        request, "settings.html", {"settings": settings_store.get_all()}
    )
