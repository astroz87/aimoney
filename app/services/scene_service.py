"""SceneService — 씬 편집기용 씬 CRUD/재정렬 및 script.json 재기록.

scene_no = 안정적 고유 ID(TTS 파일명 scene_NNN.mp3 기준), order_index = 재생 순서.
편집 후에는 항상 script.json 스냅샷을 갱신한다.
"""

from __future__ import annotations

import json

from config import settings
from app.db.database import session_scope
from app.db.models_orm import Project, Scene as SceneORM

# 편집 가능한 필드 화이트리스트
_EDITABLE = {
    "role", "voice_text", "caption_text", "visual_need",
    "target_duration", "emotion", "pace", "preferred_clip_id",
}


def list_scenes(db, project_id: str) -> list[SceneORM]:
    return db.query(SceneORM).filter(
        SceneORM.project_id == project_id
    ).order_by(SceneORM.order_index).all()


def update_scene(db, project_id: str, scene_no: int, fields: dict) -> SceneORM | None:
    scene = _get(db, project_id, scene_no)
    if scene is None:
        return None
    for key, value in fields.items():
        if key in _EDITABLE and value is not None:
            if key == "target_duration":
                value = max(0.5, float(value))
            setattr(scene, key, value)
    db.flush()
    _snapshot(db, project_id)
    return scene


def add_scene(db, project_id: str, *, after_scene_no: int | None = None,
              role: str = "solution") -> SceneORM:
    scenes = list_scenes(db, project_id)
    next_no = (max((s.scene_no for s in scenes), default=0)) + 1
    # order_index: after_scene_no 뒤에 삽입
    if after_scene_no is not None:
        anchor = next((s for s in scenes if s.scene_no == after_scene_no), None)
        insert_at = (anchor.order_index + 1) if anchor else len(scenes)
    else:
        insert_at = len(scenes)
    # 뒤쪽 order_index 밀기
    for s in scenes:
        if s.order_index >= insert_at:
            s.order_index += 1
    scene = SceneORM(
        project_id=project_id, scene_no=next_no, role=role,
        voice_text="", caption_text="", visual_need="",
        target_duration=3.0, emotion="neutral", pace="normal",
        order_index=insert_at,
    )
    db.add(scene)
    db.flush()
    _snapshot(db, project_id)
    return scene


def delete_scene(db, project_id: str, scene_no: int) -> bool:
    scene = _get(db, project_id, scene_no)
    if scene is None:
        return False
    removed_order = scene.order_index
    db.delete(scene)
    db.flush()
    # order_index 재압축
    for s in list_scenes(db, project_id):
        if s.order_index > removed_order:
            s.order_index -= 1
    db.flush()
    _snapshot(db, project_id)
    return True


def reorder_scenes(db, project_id: str, ordered_scene_nos: list[int]) -> None:
    """scene_no 리스트 순서대로 order_index 를 0..N 으로 재설정."""
    by_no = {s.scene_no: s for s in list_scenes(db, project_id)}
    idx = 0
    for no in ordered_scene_nos:
        s = by_no.get(no)
        if s is not None:
            s.order_index = idx
            idx += 1
    # 리스트에 없던 씬은 뒤로
    for no, s in by_no.items():
        if no not in ordered_scene_nos:
            s.order_index = idx
            idx += 1
    db.flush()
    _snapshot(db, project_id)


def _get(db, project_id: str, scene_no: int) -> SceneORM | None:
    return db.query(SceneORM).filter(
        SceneORM.project_id == project_id, SceneORM.scene_no == scene_no
    ).first()


def _snapshot(db, project_id: str) -> None:
    scenes = list_scenes(db, project_id)
    data = [{
        "scene": s.scene_no, "role": s.role, "voice_text": s.voice_text,
        "caption_text": s.caption_text, "visual_need": s.visual_need,
        "target_duration": s.target_duration, "emotion": s.emotion, "pace": s.pace,
        "preferred_clip_id": s.preferred_clip_id or "",
    } for s in scenes]
    base = settings.project_dir(project_id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "script.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
