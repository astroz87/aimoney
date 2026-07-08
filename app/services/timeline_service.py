"""TimelineService — scenes/clips/TTS 로 타임라인을 만들고 저장한다."""

from __future__ import annotations

import json
import logging

from config import settings
from engine.models import Clip as ClipDC
from engine.models import Scene as SceneDC
from engine.timeline import build_timeline
from app.db.database import session_scope
from app.db.models_orm import Clip as ClipORM
from app.db.models_orm import Project, Scene as SceneORM
from app.db.models_orm import TimelineItem as TLORM
from app.db.models_orm import TTSResult

logger = logging.getLogger(__name__)


def build_and_save(project_id: str) -> list[dict]:
    """타임라인을 계산해 timeline_items 테이블 + timeline.json 에 저장."""
    with session_scope() as db:
        scene_rows = db.query(SceneORM).filter(
            SceneORM.project_id == project_id
        ).order_by(SceneORM.order_index).all()
        clip_rows = db.query(ClipORM).filter(ClipORM.project_id == project_id).all()

        if not scene_rows:
            raise RuntimeError("대본이 없습니다")
        if not clip_rows:
            raise RuntimeError("분석된 컷이 없습니다")

        scenes = [SceneDC(
            scene=s.scene_no, role=s.role, voice_text=s.voice_text,
            caption_text=s.caption_text, visual_need=s.visual_need,
            target_duration=s.target_duration, emotion=s.emotion, pace=s.pace,
            preferred_clip_id=getattr(s, "preferred_clip_id", "") or "",
        ) for s in scene_rows]
        clips = [ClipDC(
            clip_id=c.clip_id, source_video=c.source_video, start=c.start, end=c.end,
            duration=c.duration, tags=c.tags or [], quality_score=c.quality_score,
            motion_score=c.motion_score, hook_score=c.hook_score, description=c.description,
        ) for c in clip_rows]

        # TTS 실측 duration: scene_no → duration, audio_path
        tts_map: dict[int, tuple[float, str]] = {}
        for s in scene_rows:
            tr = db.query(TTSResult).filter(TTSResult.scene_id == s.id).first()
            if tr:
                tts_map[s.scene_no] = (tr.duration, tr.audio_path)

    durations = {no: d for no, (d, _p) in tts_map.items()}
    timeline = build_timeline(scenes, clips, durations)

    # audio_path 채우기
    for item in timeline:
        item.audio_path = tts_map.get(item.scene, (0.0, ""))[1]

    with session_scope() as db:
        db.query(TLORM).filter(TLORM.project_id == project_id).delete()
        for it in timeline:
            db.add(TLORM(
                project_id=project_id, scene_no=it.scene, clip_id=it.clip_id,
                video_start=it.video_start, video_end=it.video_end,
                timeline_start=it.timeline_start, timeline_end=it.timeline_end,
                audio_path=it.audio_path,
            ))
        project = db.get(Project, project_id)
        if project:
            project.status = "timelined"

    base = settings.project_dir(project_id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "timeline.json").write_text(
        json.dumps([it.to_dict() for it in timeline], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return [it.to_dict() for it in timeline]
