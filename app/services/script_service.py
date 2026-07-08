"""ScriptService — 대본 생성/저장 및 script.json 스냅샷."""

from __future__ import annotations

import json
import logging

from config import settings
from engine.models import Clip as ClipDC
from engine.script import LLMScriptGenerator, MockScriptGenerator
from app.db.database import session_scope
from app.db.models_orm import Clip as ClipORM
from app.db.models_orm import Project, Scene as SceneORM
from app.services import llm_service

logger = logging.getLogger(__name__)


def _top_clips(db, project_id: str, limit: int = 8) -> list[ClipDC]:
    rows = db.query(ClipORM).filter(ClipORM.project_id == project_id).order_by(
        ClipORM.hook_score.desc()
    ).limit(limit).all()
    return [ClipDC(
        clip_id=r.clip_id, source_video=r.source_video, start=r.start, end=r.end,
        duration=r.duration, tags=r.tags or [], quality_score=r.quality_score,
        motion_score=r.motion_score, hook_score=r.hook_score, description=r.description,
    ) for r in rows]


def generate_script(project_id: str, provider: str | None = None) -> list[dict]:
    """대본을 생성해 scenes 테이블과 script.json 에 저장하고 dict 리스트 반환."""
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")
        product_ko = project.product_ko
        product_zh = project.product_zh
        category = project.category
        source_site = project.source_site
        selected = project.selected_text
        tone = (project.edit_settings or {}).get("script_tone", "")
        top = _top_clips(db, project_id)

    # 프로바이더 결정: mock 이면 규칙 기반, 아니면 LLM
    resolved = provider or __import__(
        "app.services.settings_store", fromlist=["resolve_llm_provider"]
    ).resolve_llm_provider("script")

    if resolved == "mock":
        gen = MockScriptGenerator()
    else:
        gen = LLMScriptGenerator(llm_service.get_provider(task="script", provider=resolved))

    scenes = gen.generate(
        product_ko=product_ko, category=category,
        top_clips=top, selected_text=selected, tone=tone,
        product_zh=product_zh, source_site=source_site,
    )

    _save_scenes(project_id, scenes)
    return [s.to_dict() for s in scenes]


def save_scenes_from_dicts(project_id: str, scene_dicts: list[dict]) -> None:
    """편집된 대본(dict 리스트)을 저장한다."""
    from engine.models import Scene

    scenes = [Scene(
        scene=int(d.get("scene", i + 1)),
        role=str(d.get("role", "hook")),
        voice_text=str(d.get("voice_text", "")),
        caption_text=str(d.get("caption_text", d.get("voice_text", ""))),
        visual_need=str(d.get("visual_need", "")),
        target_duration=float(d.get("target_duration", 3.0) or 3.0),
        emotion=str(d.get("emotion", "neutral")),
        pace=str(d.get("pace", "normal")),
    ) for i, d in enumerate(scene_dicts)]
    _save_scenes(project_id, scenes)


def _save_scenes(project_id: str, scenes) -> None:
    with session_scope() as db:
        db.query(SceneORM).filter(SceneORM.project_id == project_id).delete()
        for idx, s in enumerate(scenes):
            db.add(SceneORM(
                project_id=project_id, scene_no=s.scene, role=s.role,
                voice_text=s.voice_text, caption_text=s.caption_text,
                visual_need=s.visual_need, target_duration=s.target_duration,
                emotion=s.emotion, pace=s.pace, order_index=idx,
            ))
        project = db.get(Project, project_id)
        if project:
            project.status = "scripted"

    # script.json 스냅샷
    base = settings.project_dir(project_id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "script.json").write_text(
        json.dumps([s.to_dict() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
