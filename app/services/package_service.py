"""PackageService — 최종 배포 패키지(output/{id}/) 를 조립한다.

- 공통 파일 복사(final.mp4, script.json, timeline.json, subtitle.ass)
- 썸네일 생성(후킹 1위 컷 프레임)
- 플랫폼별 txt + affiliate/links.json + tracking/tracking_urls.json
- zip 아카이브 생성
"""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from pathlib import Path

from config import settings
from engine.package import build_packages
from engine.thumbnail import make_thumbnail
from app.db.database import session_scope
from app.db.models_orm import (
    Clip as ClipORM,
    Project,
    Render,
    Scene as SceneORM,
    SourceAsset,
)
from app.services.job_service import JobContext

logger = logging.getLogger(__name__)


def run_package(project_id: str, ctx: JobContext) -> None:
    ctx.update(progress=5, log="패키지 준비")
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")
        product_ko = project.product_ko
        category = project.category
        scenes = [{
            "scene": s.scene_no, "role": s.role, "voice_text": s.voice_text,
            "caption_text": s.caption_text,
        } for s in db.query(SceneORM).filter(
            SceneORM.project_id == project_id
        ).order_by(SceneORM.order_index).all()]
        render = db.query(Render).filter(Render.project_id == project_id).first()
        render_ok = bool(
            render and render.status == "done"
            and render.video_path and Path(render.video_path).exists()
        )

    if not scenes:
        raise RuntimeError("대본이 없습니다")
    # 최종 렌더가 없으면 패키지 생성을 거부한다(빈 final.mp4 로 packaged 표시 방지).
    if not render_ok:
        raise RuntimeError(
            "렌더링된 final.mp4 가 없습니다. 먼저 렌더링을 완료한 뒤 패키지를 생성하세요."
        )

    proj_dir = settings.project_dir(project_id)
    out_dir = settings.output_project_dir(project_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- 공통 파일 복사 ---
    ctx.update(progress=20, log="공통 파일 복사")
    for name in ("script.json", "timeline.json"):
        src = proj_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)
    # final.mp4/subtitle.ass 는 render_service 가 이미 out_dir 에 생성

    # --- 썸네일 ---
    ctx.update(progress=40, log="썸네일 생성")
    _make_thumb(project_id, out_dir, scenes)

    # --- 플랫폼 패키지 ---
    ctx.update(progress=70, log="플랫폼별 패키지 생성")
    summary = build_packages(
        product_id=project_id,
        product_ko=product_ko,
        category=category,
        scenes=scenes,
        out_dir=str(out_dir),
        link_router_base=settings.link_router_base,
    )
    if not summary.get("disclosure_ok"):
        raise RuntimeError("경제적 이해관계 표시 문구 삽입 검증 실패 — 패키지 중단")

    # --- zip ---
    ctx.update(progress=90, log="zip 아카이브 생성")
    zip_path = _make_zip(out_dir, project_id)

    with session_scope() as db:
        project = db.get(Project, project_id)
        if project:
            project.status = "packaged"

    (out_dir / "package_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ctx.update(progress=100,
               log=f"패키지 완료: {len(summary['platforms'])}개 플랫폼, zip={Path(zip_path).name}")


def _make_thumb(project_id: str, out_dir: Path, scenes: list[dict]) -> None:
    """후킹 점수 1위 컷의 프레임으로 썸네일 생성."""
    with session_scope() as db:
        top = db.query(ClipORM).filter(ClipORM.project_id == project_id).order_by(
            ClipORM.hook_score.desc()
        ).first()
        video_path = ""
        at = 0.0
        if top:
            at = top.start
            if top.source_asset_id:
                a = db.get(SourceAsset, top.source_asset_id)
                if a and a.local_path:
                    video_path = a.local_path

    hook_text = ""
    for s in scenes:
        if s.get("role") == "hook":
            hook_text = s.get("caption_text", "")
            break

    # 렌더된 final.mp4 를 폴백 소스로 사용
    if not video_path:
        final = out_dir / "final.mp4"
        if final.exists():
            video_path = str(final)
            at = 0.5

    make_thumbnail(video_path, str(out_dir / "thumbnail.jpg"), at_sec=at, text=hook_text)


def _make_zip(out_dir: Path, project_id: str) -> str:
    zip_path = out_dir / f"{project_id}_package.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.rglob("*"):
            if f.is_file() and f != zip_path:
                zf.write(f, f.relative_to(out_dir))
    return str(zip_path)
