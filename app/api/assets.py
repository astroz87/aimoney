"""소스 자산 API — 영상 업로드 / 로컬·URL 등록 / 후보 다운로드.

POST /api/projects/{id}/assets/upload    (multipart 파일 업로드)
POST /api/projects/{id}/assets/register  (로컬 경로 또는 URL 등록/다운로드)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from engine.ingest import download_video
from engine.models import USAGE_UNKNOWN
from app.db.database import get_session
from app.db.models_orm import Project, SourceAsset

router = APIRouter(prefix="/api/projects/{product_id}/assets", tags=["assets"])


def _require_project(db: Session, product_id: str) -> Project:
    project = db.get(Project, product_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return project


@router.post("/upload")
async def upload_videos(
    product_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_session),
):
    """영상 파일을 업로드해 data/projects/{id}/raw/ 에 저장하고 자산으로 등록한다."""
    project = _require_project(db, product_id)
    raw_dir = settings.project_dir(product_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for uf in files:
        safe_name = Path(uf.filename or "video.mp4").name
        dest = raw_dir / safe_name
        with open(dest, "wb") as f:
            shutil.copyfileobj(uf.file, f)
        asset = SourceAsset(
            project_id=product_id, asset_type="video",
            source_url=f"upload://{safe_name}", local_path=str(dest),
            usage_status="확인됨",  # 사용자가 직접 업로드 → 권리 보유 전제
            meta_json={"origin": "upload"},
        )
        db.add(asset)
        saved.append(safe_name)

    if project.status == "created":
        project.status = "sourced"
    db.commit()
    return {"saved": saved, "count": len(saved)}


class RegisterRequest(BaseModel):
    source_url: str = ""
    local_path: str = ""
    download: bool = False


@router.post("/register")
def register_asset(
    product_id: str, payload: RegisterRequest, db: Session = Depends(get_session)
):
    """로컬 경로를 등록하거나, download=True 이면 URL 을 다운로드해 등록한다.

    권리 확인 전제: URL 다운로드 자산은 usage_status='확인 필요' 로 시작한다.
    """
    _require_project(db, product_id)
    local_path = payload.local_path
    usage = USAGE_UNKNOWN

    if payload.download and payload.source_url:
        raw_dir = settings.project_dir(product_id) / "raw"
        fname = f"dl_{abs(hash(payload.source_url)) % 10**8}.mp4"
        try:
            dest = download_video(payload.source_url, raw_dir / fname)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"다운로드 실패: {exc}")
        local_path = str(dest)
    elif local_path:
        if not Path(local_path).exists():
            raise HTTPException(status_code=400, detail="local_path 가 존재하지 않습니다")
        usage = "확인됨"  # 사용자가 로컬 파일 지정 → 보유 전제

    asset = SourceAsset(
        project_id=product_id, asset_type="video",
        source_url=payload.source_url or f"local://{local_path}",
        local_path=local_path or None,
        usage_status=usage,
        meta_json={"origin": "download" if payload.download else "local"},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"asset_id": asset.id, "local_path": local_path, "usage_status": usage}
