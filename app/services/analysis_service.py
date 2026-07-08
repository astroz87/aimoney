"""AnalysisService — 소스 자산의 영상을 분석해 clips 테이블을 채운다."""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings
from engine.analysis import analyze_video
from app.db.database import session_scope
from app.db.models_orm import Clip as ClipORM
from app.db.models_orm import Project, SourceAsset
from app.services.job_service import JobContext

logger = logging.getLogger(__name__)


def analyze_single_asset(project_id: str, asset_id: int) -> int:
    """단일 자산(신규 삽입 등)만 분석해 clips 에 append 한다. 추가된 컷 수 반환.

    기존 clips 는 지우지 않고, clip_id 번호는 현재 최대 뒤에서 이어 붙인다.
    """
    with session_scope() as db:
        asset = db.get(SourceAsset, asset_id)
        if asset is None or not asset.local_path or not Path(asset.local_path).exists():
            raise RuntimeError("분석할 로컬 영상이 없습니다")
        path = asset.local_path
        existing = db.query(ClipORM).filter(ClipORM.project_id == project_id).count()

    clips = analyze_video(path, source_label=Path(path).name, clip_id_offset=existing)
    with session_scope() as db:
        for c in clips:
            db.add(ClipORM(
                project_id=project_id, source_asset_id=asset_id,
                clip_id=c.clip_id, source_video=c.source_video,
                start=c.start, end=c.end, duration=c.duration, tags=c.tags,
                quality_score=c.quality_score, brightness_score=c.brightness_score,
                motion_score=c.motion_score, blur_score=c.blur_score,
                hook_score=c.hook_score, description=c.description,
            ))
    return len(clips)


def run_analysis(project_id: str, ctx: JobContext) -> None:
    """프로젝트의 로컬 영상 자산을 모두 분석한다."""
    with session_scope() as db:
        assets = db.query(SourceAsset).filter(
            SourceAsset.project_id == project_id,
            SourceAsset.asset_type == "video",
        ).all()
        video_paths = [(a.id, a.local_path) for a in assets if a.local_path and Path(a.local_path).exists()]

    if not video_paths:
        raise RuntimeError("분석할 로컬 영상이 없습니다. 먼저 영상을 업로드하거나 다운로드하세요.")

    # 기존 clips 삭제 (재분석 idempotent)
    with session_scope() as db:
        db.query(ClipORM).filter(ClipORM.project_id == project_id).delete()

    offset = 0
    n = len(video_paths)
    for i, (asset_id, path) in enumerate(video_paths):
        ctx.update(progress=int(i / n * 90) + 5, log=f"영상 분석 {i+1}/{n}: {Path(path).name}")
        clips = analyze_video(path, source_label=Path(path).name, clip_id_offset=offset)
        offset += len(clips)
        with session_scope() as db:
            for c in clips:
                db.add(ClipORM(
                    project_id=project_id,
                    source_asset_id=asset_id,
                    clip_id=c.clip_id,
                    source_video=c.source_video,
                    start=c.start, end=c.end, duration=c.duration,
                    tags=c.tags,
                    quality_score=c.quality_score,
                    brightness_score=c.brightness_score,
                    motion_score=c.motion_score,
                    blur_score=c.blur_score,
                    hook_score=c.hook_score,
                    description=c.description,
                ))

    with session_scope() as db:
        project = db.get(Project, project_id)
        if project:
            project.status = "analyzed"
    ctx.update(progress=100, log=f"분석 완료: {offset}개 컷")
