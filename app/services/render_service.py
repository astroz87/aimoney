"""RenderService — 타임라인 + TTS + 자막을 ffmpeg 로 합성한다.

권리 게이트: 프로젝트 usage_status 가 '확인됨' 이 아니면 렌더링을 차단한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings
from engine.models import USAGE_CLEARED, resolve_edit_settings
from engine.render import render_video
from engine.subtitle import build_ass, build_srt
from app.db.database import session_scope
from app.db.models_orm import Clip as ClipORM
from app.db.models_orm import Project, Render, Scene as SceneORM
from app.db.models_orm import TimelineItem as TLORM
from app.services.job_service import JobContext
from app.services.timeline_service import build_and_save

logger = logging.getLogger(__name__)


def run_render(project_id: str, ctx: JobContext) -> None:
    # --- 권리 게이트 ---
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")
        if project.usage_status != USAGE_CLEARED:
            raise RuntimeError(
                f"권리 미확인: usage_status='{project.usage_status}'. "
                "'확인됨' 으로 변경해야 렌더링할 수 있습니다."
            )
        edit_opts = resolve_edit_settings(project.edit_settings)

    # --- 타임라인 보장 (없으면 생성) ---
    with session_scope() as db:
        has_tl = db.query(TLORM).filter(TLORM.project_id == project_id).count()
    if not has_tl:
        ctx.update(progress=5, log="타임라인 생성 중")
        build_and_save(project_id)

    # --- 렌더 스펙 수집 ---
    ctx.update(progress=10, log="렌더 준비")
    specs, sub_segments = _collect_specs(project_id)
    if not specs:
        raise RuntimeError("렌더할 타임라인이 없습니다")

    out_dir = settings.output_project_dir(project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = settings.project_dir(project_id) / "render_tmp"

    # --- 상단 제목 결정 (edit_settings.title_text → 없으면 hook 자막 → 상품명) ---
    title_text = ""
    if edit_opts.get("show_title"):
        title_text = (edit_opts.get("title_text") or "").strip()
        if not title_text and sub_segments:
            title_text = sub_segments[0].get("text", "")
        if not title_text:
            with session_scope() as db:
                proj = db.get(Project, project_id)
                title_text = proj.product_ko if proj else ""

    # --- 자막 (템플릿 스타일 + 상단 제목 반영) ---
    total_end = max((s["end"] for s in sub_segments), default=0.0)
    ass_path = out_dir / "subtitle.ass"
    build_ass(
        sub_segments, str(ass_path),
        style=edit_opts.get("subtitle_style") or None,
        title=title_text,
        title_style=(edit_opts.get("title_style") if edit_opts.get("show_title") else None),
        total_end=total_end,
    )
    build_srt(sub_segments, str(out_dir / "subtitle.srt"))

    # --- 렌더 ---
    ctx.update(progress=15, log="ffmpeg 렌더링")
    out_path = out_dir / "final.mp4"

    def _pcb(p):
        ctx.update(progress=15 + int(p * 0.8), log=f"렌더링 {p}%")

    bgm_path = edit_opts.get("bgm_path") or None
    result = render_video(specs, str(ass_path), str(out_path),
                          str(work_dir), bgm_path=bgm_path, opts=edit_opts,
                          progress_cb=_pcb)

    with session_scope() as db:
        db.query(Render).filter(Render.project_id == project_id).delete()
        db.add(Render(
            project_id=project_id, video_path=result["video_path"],
            subtitle_path=str(ass_path), duration=result["duration"], status="done",
        ))
        project = db.get(Project, project_id)
        if project:
            project.status = "rendered"
    ctx.update(progress=100, log=f"렌더 완료: {result['duration']}s")


def _collect_specs(project_id: str):
    """타임라인 → 렌더 스펙 + 자막 세그먼트."""
    with session_scope() as db:
        items = db.query(TLORM).filter(
            TLORM.project_id == project_id
        ).order_by(TLORM.timeline_start).all()

        # clip_id → source video local path
        clip_paths: dict[str, str] = {}
        clips = db.query(ClipORM).filter(ClipORM.project_id == project_id).all()
        for c in clips:
            path = None
            if c.source_asset_id:
                from app.db.models_orm import SourceAsset
                a = db.get(SourceAsset, c.source_asset_id)
                if a:
                    path = a.local_path
            clip_paths[c.clip_id] = path or ""

        # scene_no → (caption_text, sfx_path)
        captions = {}
        sfx = {}
        for s in db.query(SceneORM).filter(SceneORM.project_id == project_id).all():
            captions[s.scene_no] = s.caption_text
            sfx[s.scene_no] = getattr(s, "sfx_path", "") or ""

        specs = []
        segments = []
        for it in items:
            dur = max(0.1, it.timeline_end - it.timeline_start)
            specs.append({
                "video_path": clip_paths.get(it.clip_id, ""),
                "v_start": it.video_start,
                "v_end": it.video_end,
                "audio_path": it.audio_path,
                "sfx_path": sfx.get(it.scene_no, ""),
                "duration": dur,
            })
            segments.append({
                "start": it.timeline_start,
                "end": it.timeline_end,
                "text": captions.get(it.scene_no, ""),
            })
    return specs, segments
