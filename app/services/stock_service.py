"""StockService — 스톡 영상 검색 및 프로젝트로 삽입(다운로드→자산등록→분석)."""

from __future__ import annotations

import hashlib
import logging

from config import settings
from engine.ingest import download_video
from engine.stock import get_stock_provider
from app.db.database import session_scope
from app.db.models_orm import Project, SourceAsset
from app.services import settings_store
from app.services.analysis_service import analyze_single_asset

logger = logging.getLogger(__name__)


def _provider(provider: str | None = None):
    provider = provider or settings_store.resolve_stock_provider()
    api_key = settings_store.get("pexels_api_key") if provider == "pexels" else ""
    return get_stock_provider(provider, api_key=api_key)


def search(query: str, *, provider: str | None = None, per_page: int = 12) -> list[dict]:
    prov = _provider(provider)
    return [v.to_dict() for v in prov.search(query, per_page=per_page)]


def import_video(project_id: str, video_url: str, *, source_id: str = "",
                 analyze: bool = True) -> dict:
    """스톡 영상을 다운로드해 자산으로 등록하고(옵션) 분석해 컷을 추가한다.

    스톡(Pexels 등)은 라이선스가 명확하므로 usage_status='확인됨'.
    """
    if not video_url:
        raise RuntimeError("영상 URL 이 없습니다 (mock 프로바이더는 삽입 불가)")

    raw_dir = settings.project_dir(project_id) / "raw"
    fname = f"stock_{hashlib.md5(video_url.encode()).hexdigest()[:12]}.mp4"
    dest = download_video(video_url, raw_dir / fname)

    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")
        asset = SourceAsset(
            project_id=project_id, asset_type="video",
            source_url=video_url, local_path=str(dest),
            usage_status="확인됨",  # 스톡 라이선스 보유 전제
            meta_json={"origin": "stock", "source_id": source_id},
        )
        db.add(asset)
        db.flush()
        asset_id = asset.id
        if project.status == "created":
            project.status = "sourced"

    added = 0
    if analyze:
        added = analyze_single_asset(project_id, asset_id)

    return {"asset_id": asset_id, "local_path": str(dest), "clips_added": added}
