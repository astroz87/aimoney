"""씬 편집기 API — 씬 CRUD/재정렬, 단일 씬 TTS, 클립 썸네일.

PUT    /api/projects/{id}/scenes/{scene_no}        씬 수정
POST   /api/projects/{id}/scenes                   씬 추가
DELETE /api/projects/{id}/scenes/{scene_no}        씬 삭제
POST   /api/projects/{id}/scenes/reorder           재정렬
POST   /api/projects/{id}/scenes/{scene_no}/tts    단일 씬 TTS
GET    /api/projects/{id}/scenes/{scene_no}/tts.mp3 씬 TTS 오디오 미리듣기
GET    /api/projects/{id}/clips/{clip_id}/thumb.jpg 클립 썸네일
GET    /api/projects/{id}/clips/{clip_id}/video     클립 원본 영상 미리보기
PATCH  /api/projects/{id}/clips/{clip_id}          클립 컷 구간(트림) 수정
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from engine.media_utils import probe_duration
from engine.thumbnail import make_clip_thumb
from app.db.database import get_session
from app.db.models_orm import Clip, Project, Scene, SourceAsset, TTSResult
from app.services import scene_service
from app.services.tts_service import synthesize_scene

router = APIRouter(prefix="/api/projects/{product_id}", tags=["scenes"])


class SceneUpdate(BaseModel):
    role: str | None = None
    voice_text: str | None = None
    caption_text: str | None = None
    visual_need: str | None = None
    target_duration: float | None = None
    emotion: str | None = None
    pace: str | None = None
    preferred_clip_id: str | None = None


class SceneAdd(BaseModel):
    after_scene_no: int | None = None
    role: str = "solution"


class ReorderRequest(BaseModel):
    order: list[int]


class SceneTTSRequest(BaseModel):
    provider: str | None = None


class ClipTrim(BaseModel):
    start: float | None = None
    end: float | None = None


def _clamp_clip_range(start: float, end: float, src_dur: float = 0.0) -> tuple[float, float]:
    """컷 구간을 유효 범위로 보정한다. src_dur>0 이면 원본 길이 내로 클램프."""
    start = max(0.0, float(start))
    end = float(end)
    if src_dur > 0:
        end = min(end, src_dur)
        start = min(start, max(0.0, src_dur - 0.2))
    if end < start + 0.2:
        end = start + 0.2
    return round(start, 3), round(end, 3)


def _require(db: Session, product_id: str) -> Project:
    p = db.get(Project, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return p


@router.put("/scenes/{scene_no}")
def update_scene(product_id: str, scene_no: int, payload: SceneUpdate,
                 db: Session = Depends(get_session)):
    _require(db, product_id)
    scene = scene_service.update_scene(
        db, product_id, scene_no, payload.model_dump(exclude_none=True)
    )
    if scene is None:
        raise HTTPException(status_code=404, detail="씬을 찾을 수 없습니다")
    db.commit()
    return {"scene_no": scene.scene_no, "ok": True}


@router.post("/scenes")
def add_scene(product_id: str, payload: SceneAdd, db: Session = Depends(get_session)):
    _require(db, product_id)
    scene = scene_service.add_scene(
        db, product_id, after_scene_no=payload.after_scene_no, role=payload.role
    )
    db.commit()
    return {"scene_no": scene.scene_no, "order_index": scene.order_index}


@router.delete("/scenes/{scene_no}")
def delete_scene(product_id: str, scene_no: int, db: Session = Depends(get_session)):
    _require(db, product_id)
    ok = scene_service.delete_scene(db, product_id, scene_no)
    if not ok:
        raise HTTPException(status_code=404, detail="씬을 찾을 수 없습니다")
    db.commit()
    return {"deleted": scene_no}


@router.post("/scenes/reorder")
def reorder(product_id: str, payload: ReorderRequest, db: Session = Depends(get_session)):
    _require(db, product_id)
    scene_service.reorder_scenes(db, product_id, payload.order)
    db.commit()
    return {"order": payload.order}


@router.post("/scenes/{scene_no}/tts")
def scene_tts(product_id: str, scene_no: int, payload: SceneTTSRequest,
              db: Session = Depends(get_session)):
    _require(db, product_id)
    try:
        result = synthesize_scene(product_id, scene_no, provider=payload.provider)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/clips/{clip_id}/thumb.jpg")
def clip_thumb(product_id: str, clip_id: str, db: Session = Depends(get_session)):
    _require(db, product_id)
    clip = db.query(Clip).filter(
        Clip.project_id == product_id, Clip.clip_id == clip_id
    ).first()
    if clip is None:
        raise HTTPException(status_code=404, detail="클립을 찾을 수 없습니다")

    thumb_dir = settings.project_dir(product_id) / "clips"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{clip_id}.jpg"

    if not thumb_path.exists():
        video_path = ""
        if clip.source_asset_id:
            a = db.get(SourceAsset, clip.source_asset_id)
            if a and a.local_path:
                video_path = a.local_path
        make_clip_thumb(video_path, str(thumb_path), at_sec=clip.start)

    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="썸네일 생성 실패")
    return FileResponse(str(thumb_path), media_type="image/jpeg")


@router.get("/scenes/{scene_no}/tts.mp3")
def scene_tts_audio(product_id: str, scene_no: int, db: Session = Depends(get_session)):
    """씬 TTS 오디오 미리듣기용 서빙."""
    _require(db, product_id)
    scene = db.query(Scene).filter(
        Scene.project_id == product_id, Scene.scene_no == scene_no
    ).first()
    if scene is None:
        raise HTTPException(status_code=404, detail="씬을 찾을 수 없습니다")

    result = db.query(TTSResult).filter(TTSResult.scene_id == scene.id).first()
    if result is None or not result.audio_path or not Path(result.audio_path).exists():
        raise HTTPException(status_code=404, detail="TTS 가 없습니다. 먼저 생성하세요.")
    return FileResponse(result.audio_path, media_type="audio/mpeg")


@router.get("/clips/{clip_id}/video")
def clip_video(product_id: str, clip_id: str, db: Session = Depends(get_session)):
    """클립 원본 영상 서빙 (씬 미리보기용)."""
    _require(db, product_id)
    clip = db.query(Clip).filter(
        Clip.project_id == product_id, Clip.clip_id == clip_id
    ).first()
    if clip is None:
        raise HTTPException(status_code=404, detail="클립을 찾을 수 없습니다")

    asset = db.get(SourceAsset, clip.source_asset_id) if clip.source_asset_id else None
    if asset is None or not asset.local_path or not Path(asset.local_path).exists():
        raise HTTPException(status_code=404, detail="원본 영상이 없습니다")
    return FileResponse(asset.local_path, media_type="video/mp4")


@router.patch("/clips/{clip_id}")
def trim_clip(product_id: str, clip_id: str, payload: ClipTrim,
              db: Session = Depends(get_session)):
    """클립 구간(컷 트림) 수정. 트림 후 타임라인/렌더는 재렌더 시 재계산된다."""
    _require(db, product_id)
    clip = db.query(Clip).filter(
        Clip.project_id == product_id, Clip.clip_id == clip_id
    ).first()
    if clip is None:
        raise HTTPException(status_code=404, detail="클립을 찾을 수 없습니다")

    new_start = clip.start if payload.start is None else payload.start
    new_end = clip.end if payload.end is None else payload.end

    src_dur = 0.0
    if clip.source_asset_id:
        asset = db.get(SourceAsset, clip.source_asset_id)
        if asset and asset.local_path and Path(asset.local_path).exists():
            src_dur = probe_duration(asset.local_path)

    new_start, new_end = _clamp_clip_range(new_start, new_end, src_dur)

    clip.start = new_start
    clip.end = new_end
    clip.duration = new_end - new_start
    db.commit()

    # 구간이 바뀌었으니 캐시된 썸네일을 지워 새 시작점으로 재생성되게 한다
    thumb_path = settings.project_dir(product_id) / "clips" / f"{clip_id}.jpg"
    thumb_path.unlink(missing_ok=True)

    return {
        "clip_id": clip_id,
        "start": clip.start,
        "end": clip.end,
        "duration": clip.duration,
    }
