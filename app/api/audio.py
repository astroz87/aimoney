"""오디오/배경 편집 API — BGM/효과음 업로드, 편집 설정(배경색/전환/볼륨).

GET    /api/projects/{id}/edit-settings
PUT    /api/projects/{id}/edit-settings
POST   /api/projects/{id}/audio/bgm         (multipart)
DELETE /api/projects/{id}/audio/bgm
POST   /api/projects/{id}/scenes/{no}/sfx   (multipart)
DELETE /api/projects/{id}/scenes/{no}/sfx
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from engine.models import resolve_edit_settings
from app.db.database import get_session
from app.db.models_orm import Project, Scene

router = APIRouter(prefix="/api/projects/{product_id}", tags=["audio"])

_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def _require(db: Session, product_id: str) -> Project:
    p = db.get(Project, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return p


def _save_audio(uf: UploadFile, dest_dir: Path, stem: str) -> str:
    ext = Path(uf.filename or "a.mp3").suffix.lower()
    if ext not in _AUDIO_EXT:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 오디오 형식: {ext}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    # 기존 동일 stem 파일 정리
    for old in dest_dir.glob(f"{stem}.*"):
        old.unlink(missing_ok=True)
    dest = dest_dir / f"{stem}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(uf.file, f)
    return str(dest)


class EditSettingsUpdate(BaseModel):
    bg_color: str | None = None
    bgm_enabled: bool | None = None
    bgm_volume: float | None = None
    bgm_ducking: bool | None = None
    transition: str | None = None            # none | fade | crossfade
    transition_duration: float | None = None
    # 레이아웃/제목/자막 스타일 (자막 스타일은 모든 자막에 일괄 적용됨)
    fit_mode: str | None = None              # cover | contain
    box_scale: float | None = None
    box_h: float | None = None
    box_y: float | None = None
    show_title: bool | None = None
    title_text: str | None = None
    subtitle_style: dict | None = None
    title_style: dict | None = None


@router.get("/edit-settings")
def get_edit_settings(product_id: str, db: Session = Depends(get_session)):
    p = _require(db, product_id)
    resolved = resolve_edit_settings(p.edit_settings)
    resolved["bgm_present"] = bool(resolved.get("bgm_path")) and Path(resolved["bgm_path"]).exists()
    return resolved


@router.put("/edit-settings")
def update_edit_settings(
    product_id: str, payload: EditSettingsUpdate, db: Session = Depends(get_session)
):
    p = _require(db, product_id)
    current = resolve_edit_settings(p.edit_settings)
    for k, v in payload.model_dump(exclude_none=True).items():
        current[k] = v
    if current.get("transition") not in ("none", "fade", "crossfade"):
        current["transition"] = "none"
    if current.get("fit_mode") not in ("cover", "contain"):
        current["fit_mode"] = "cover"
    current["bgm_volume"] = max(0.0, min(1.0, float(current.get("bgm_volume", 0.18))))
    current["transition_duration"] = max(0.0, min(2.0, float(current.get("transition_duration", 0.3))))
    p.edit_settings = current
    db.commit()
    return current


@router.post("/audio/bgm")
def upload_bgm(
    product_id: str, file: UploadFile = File(...), db: Session = Depends(get_session)
):
    p = _require(db, product_id)
    audio_dir = settings.project_dir(product_id) / "audio"
    path = _save_audio(file, audio_dir, "bgm")
    current = resolve_edit_settings(p.edit_settings)
    current["bgm_path"] = path
    current["bgm_enabled"] = True
    p.edit_settings = current
    db.commit()
    return {"bgm_path": path, "bgm_enabled": True}


@router.delete("/audio/bgm")
def delete_bgm(product_id: str, db: Session = Depends(get_session)):
    p = _require(db, product_id)
    current = resolve_edit_settings(p.edit_settings)
    old = current.get("bgm_path")
    if old and Path(old).exists():
        Path(old).unlink(missing_ok=True)
    current["bgm_path"] = ""
    p.edit_settings = current
    db.commit()
    return {"bgm_path": ""}


@router.post("/scenes/{scene_no}/sfx")
def upload_sfx(
    product_id: str, scene_no: int, file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    _require(db, product_id)
    scene = db.query(Scene).filter(
        Scene.project_id == product_id, Scene.scene_no == scene_no
    ).first()
    if scene is None:
        raise HTTPException(status_code=404, detail="씬을 찾을 수 없습니다")
    sfx_dir = settings.project_dir(product_id) / "audio" / "sfx"
    path = _save_audio(file, sfx_dir, f"scene_{scene_no:03d}")
    scene.sfx_path = path
    db.commit()
    return {"scene_no": scene_no, "sfx_path": path}


@router.delete("/scenes/{scene_no}/sfx")
def delete_sfx(product_id: str, scene_no: int, db: Session = Depends(get_session)):
    _require(db, product_id)
    scene = db.query(Scene).filter(
        Scene.project_id == product_id, Scene.scene_no == scene_no
    ).first()
    if scene is None:
        raise HTTPException(status_code=404, detail="씬을 찾을 수 없습니다")
    if scene.sfx_path and Path(scene.sfx_path).exists():
        Path(scene.sfx_path).unlink(missing_ok=True)
    scene.sfx_path = ""
    db.commit()
    return {"scene_no": scene_no, "sfx_path": ""}
