"""설정 API — LLM/TTS 프로바이더·모델·키 관리.

GET  /api/settings         (마스킹된 값)
PUT  /api/settings         (부분 업데이트)
POST /api/settings/test    (프로바이더 유효성 핑)
"""

from __future__ import annotations

from fastapi import APIRouter

from engine.llm.factory import AVAILABLE_MODELS
from app.schemas import SettingsTestRequest, SettingsUpdate
from app.services import llm_service, settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    return {"values": settings_store.get_all(masked=True), "available_models": AVAILABLE_MODELS}


@router.put("")
def update_settings(payload: SettingsUpdate):
    settings_store.set_many(payload.values)
    return {"values": settings_store.get_all(masked=True)}


@router.post("/test")
def test_settings(payload: SettingsTestRequest):
    ok, detail = llm_service.test_provider(payload.provider)
    return {"ok": ok, "detail": detail}
