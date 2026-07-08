"""StorylineService — '영상 먼저 조립 → 대본 넣기' 워크플로우.

build_storyline: 분석된 컷으로 씬(스토리라인)을 직접 만든다(컷 배정·순서 확정, 텍스트 비움).
fill_script    : 조립된 스토리라인의 각 씬에 나레이션/자막을 채운다(컷/순서 불변).
"""

from __future__ import annotations

import json
import logging

from config import settings
from engine.script.filler import fill_scene_texts
from app.db.database import session_scope
from app.db.models_orm import Clip as ClipORM
from app.db.models_orm import Project, Scene as SceneORM
from app.services import llm_service, settings_store

logger = logging.getLogger(__name__)

# 컷 개수에 따른 역할 배정 (첫=hook, 끝=cta, 중간 순환)
_MIDDLE_ROLES = ["problem", "solution", "proof"]


def _assign_role(idx: int, total: int) -> str:
    if idx == 0:
        return "hook"
    if idx == total - 1:
        return "cta"
    return _MIDDLE_ROLES[(idx - 1) % len(_MIDDLE_ROLES)]


def build_storyline(project_id: str, clip_ids: list[str] | None = None,
                    count: int = 6) -> list[dict]:
    """컷으로 스토리라인(씬)을 만든다. clip_ids 지정 시 그 순서, 아니면 hook_score 상위."""
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")

        all_clips = {c.clip_id: c for c in
                     db.query(ClipORM).filter(ClipORM.project_id == project_id).all()}
        if not all_clips:
            raise RuntimeError("분석된 컷이 없습니다. 먼저 영상을 분석하세요.")

        if clip_ids:
            chosen = [all_clips[cid] for cid in clip_ids if cid in all_clips]
        else:
            chosen = sorted(all_clips.values(), key=lambda c: c.hook_score, reverse=True)[:count]
            # 후킹 1위를 처음에 두되 나머지는 원래(영상) 순서로
            rest = sorted(chosen[1:], key=lambda c: c.start)
            chosen = chosen[:1] + rest
        if not chosen:
            raise RuntimeError("선택된 컷이 없습니다")

        total = len(chosen)
        # 기존 씬 교체
        db.query(SceneORM).filter(SceneORM.project_id == project_id).delete()
        for idx, clip in enumerate(chosen):
            db.add(SceneORM(
                project_id=project_id, scene_no=idx + 1,
                role=_assign_role(idx, total),
                voice_text="", caption_text="", visual_need=clip.description or "",
                target_duration=min(6.0, max(1.5, clip.duration)),
                emotion="neutral", pace="normal", order_index=idx,
                preferred_clip_id=clip.clip_id,
            ))
        project.status = "scripted"

    _snapshot(project_id)
    return _dump(project_id)


def fill_script(project_id: str, provider: str | None = None) -> list[dict]:
    """조립된 스토리라인의 각 씬에 나레이션/자막을 채운다(컷/순서 유지)."""
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")
        product_ko, category = project.product_ko, project.category
        product_zh = project.product_zh
        tone = (project.edit_settings or {}).get("script_tone", "")

        scenes = db.query(SceneORM).filter(
            SceneORM.project_id == project_id
        ).order_by(SceneORM.order_index).all()
        if not scenes:
            raise RuntimeError("스토리라인이 없습니다. 먼저 스토리라인을 만드세요.")

        clip_meta = {c.clip_id: c for c in
                     db.query(ClipORM).filter(ClipORM.project_id == project_id).all()}
        clips_info = []
        for s in scenes:
            clip = clip_meta.get(s.preferred_clip_id or "")
            clips_info.append({
                "scene_no": s.scene_no, "role": s.role,
                "clip_id": s.preferred_clip_id or "",
                "tags": (clip.tags if clip else []) or [],
                "description": clip.description if clip else "",
                # 씬별 나레이션 글자 수 예산 산정용 (초당 5.5자)
                "duration": s.target_duration or (clip.duration if clip else 0),
            })

    resolved = provider or settings_store.resolve_llm_provider("script")
    llm = llm_service.get_provider(task="script", provider=resolved)
    texts = fill_scene_texts(
        llm, product_ko=product_ko, category=category, tone=tone,
        clips_info=clips_info, product_zh=product_zh,
    )

    with session_scope() as db:
        for s in db.query(SceneORM).filter(SceneORM.project_id == project_id).all():
            t = texts.get(s.scene_no)
            if t:
                s.voice_text = t["voice_text"]
                s.caption_text = t["caption_text"]

    _snapshot(project_id)
    return _dump(project_id)


def _dump(project_id: str) -> list[dict]:
    with session_scope() as db:
        scenes = db.query(SceneORM).filter(
            SceneORM.project_id == project_id
        ).order_by(SceneORM.order_index).all()
        return [{
            "scene": s.scene_no, "role": s.role, "voice_text": s.voice_text,
            "caption_text": s.caption_text, "visual_need": s.visual_need,
            "target_duration": s.target_duration, "preferred_clip_id": s.preferred_clip_id or "",
        } for s in scenes]


def _snapshot(project_id: str) -> None:
    data = _dump(project_id)
    base = settings.project_dir(project_id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "script.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
