"""TTSService — scene 별 TTS 를 생성하고 실측 duration 을 저장한다."""

from __future__ import annotations

import logging

from config import settings
from engine.tts import get_tts_provider
from app.db.database import session_scope
from app.db.models_orm import Project, Scene, TTSResult
from app.services import settings_store
from app.services.job_service import JobContext

logger = logging.getLogger(__name__)


def _resolve_provider(provider: str | None):
    provider = provider or settings_store.resolve_tts_provider()
    voice = settings_store.get("tts_voice")
    if provider == "gemini":
        return get_tts_provider("gemini", voice=voice,
                                api_key=settings_store.get("gemini_api_key"),
                                model=settings_store.get("gemini_model")), provider
    return get_tts_provider(provider, voice=voice), provider


def run_tts(project_id: str, ctx: JobContext, provider: str | None = None) -> None:
    """프로젝트의 모든 scene 에 대해 TTS 를 생성한다."""
    with session_scope() as db:
        scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(
            Scene.order_index
        ).all()
        scene_data = [(s.id, s.scene_no, s.voice_text, s.emotion, s.pace) for s in scenes]

    if not scene_data:
        raise RuntimeError("대본이 없습니다. 먼저 대본을 생성하세요.")

    tts, used = _resolve_provider(provider)
    tts_dir = settings.project_dir(project_id) / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    n = len(scene_data)
    for i, (scene_id, scene_no, text, emotion, pace) in enumerate(scene_data):
        ctx.update(progress=int(i / n * 90) + 5, log=f"TTS {i+1}/{n} (scene {scene_no})")
        out_path = tts_dir / f"scene_{scene_no:03d}.mp3"
        result = tts.synthesize(text, emotion=emotion, pace=pace, output_path=str(out_path))
        with session_scope() as db:
            db.query(TTSResult).filter(TTSResult.scene_id == scene_id).delete()
            db.add(TTSResult(
                scene_id=scene_id, provider=used,
                audio_path=result["audio_path"], duration=result["duration"],
            ))

    with session_scope() as db:
        project = db.get(Project, project_id)
        if project:
            project.status = "voiced"
    ctx.update(progress=100, log=f"TTS 완료: {n}개 ({used})")


def synthesize_scene(project_id: str, scene_no: int, provider: str | None = None) -> dict:
    """단일 씬의 TTS 만 (재)생성한다. 편집기에서 한 씬을 고쳤을 때 사용.

    Returns {"scene": scene_no, "audio_path": ..., "duration": ...}
    """
    with session_scope() as db:
        scene = db.query(Scene).filter(
            Scene.project_id == project_id, Scene.scene_no == scene_no
        ).first()
        if scene is None:
            raise RuntimeError("씬을 찾을 수 없습니다")
        scene_id, text, emotion, pace = scene.id, scene.voice_text, scene.emotion, scene.pace

    tts, used = _resolve_provider(provider)
    tts_dir = settings.project_dir(project_id) / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    out_path = tts_dir / f"scene_{scene_no:03d}.mp3"
    result = tts.synthesize(text, emotion=emotion, pace=pace, output_path=str(out_path))

    with session_scope() as db:
        db.query(TTSResult).filter(TTSResult.scene_id == scene_id).delete()
        db.add(TTSResult(
            scene_id=scene_id, provider=used,
            audio_path=result["audio_path"], duration=result["duration"],
        ))
    return {"scene": scene_no, "audio_path": result["audio_path"],
            "duration": result["duration"], "provider": used}
