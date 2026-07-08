"""런타임 설정 저장소.

우선순위: DB `settings` 테이블 > .env(config.settings) > 하드코딩 기본값.
API 키 등 민감 값은 조회 시 마스킹하여 노출한다(원문은 팩토리에서만 사용).
"""

from __future__ import annotations

from typing import Any

from config import settings as env_settings
from app.db.database import session_scope
from app.db.models_orm import Setting

# 설정 키 화이트리스트와 .env 폴백 매핑.
# key -> (env_settings 속성명 | None)
_KEYS: dict[str, str | None] = {
    "default_llm_provider": "default_llm_provider",
    "default_tts_provider": "default_tts_provider",
    "default_stock_provider": "default_stock_provider",
    # Pexels 스톡
    "pexels_api_key": "pexels_api_key",
    # 작업별 오버라이드 (비면 default 사용)
    "llm_provider_script": None,
    "llm_provider_search": None,
    # Claude
    "anthropic_api_key": "anthropic_api_key",
    "claude_model": "claude_model",
    # Gemini
    "gemini_api_key": "gemini_api_key",
    "gemini_model": "gemini_model",
    # OpenAI
    "openai_api_key": "openai_api_key",
    "openai_model": "openai_model",
    # TTS 옵션
    "tts_voice": None,
    "link_router_base": "link_router_base",
}

# 마스킹 대상 키 (부분 노출)
_SECRET_KEYS = {"anthropic_api_key", "gemini_api_key", "openai_api_key", "pexels_api_key"}


def _env_default(key: str) -> str:
    attr = _KEYS.get(key)
    if attr is None:
        return ""
    return str(getattr(env_settings, attr, "") or "")


def get(key: str, default: str = "") -> str:
    """단일 설정값 조회 (DB > .env > default). 원문 반환 (마스킹 없음)."""
    if key not in _KEYS:
        return default
    with session_scope() as db:
        row = db.get(Setting, key)
        if row is not None and row.value != "":
            return row.value
    env = _env_default(key)
    return env if env != "" else default


def get_all(masked: bool = True) -> dict[str, Any]:
    """전체 설정 조회. masked=True 이면 비밀 키를 부분 마스킹."""
    result: dict[str, Any] = {}
    with session_scope() as db:
        db_rows = {s.key: s.value for s in db.query(Setting).all()}
    for key in _KEYS:
        value = db_rows.get(key) or _env_default(key)
        if masked and key in _SECRET_KEYS and value:
            value = mask_secret(value)
        result[key] = value
    return result


def set_many(values: dict[str, str]) -> None:
    """여러 설정을 저장한다. 마스킹된 값(****)은 무시(변경 안 함)한다."""
    with session_scope() as db:
        for key, value in values.items():
            if key not in _KEYS:
                continue
            # 마스킹된 값이 그대로 되돌아온 경우 저장 스킵 (기존 값 보존)
            if key in _SECRET_KEYS and "*" in (value or ""):
                continue
            row = db.get(Setting, key)
            if row is None:
                db.add(Setting(key=key, value=value or ""))
            else:
                row.value = value or ""


def mask_secret(value: str) -> str:
    """API 키를 'sk-****abcd' 형태로 마스킹."""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def resolve_llm_provider(task: str | None = None) -> str:
    """작업(task)별 LLM 프로바이더 결정. task in {'script','search'} 오버라이드 우선."""
    if task:
        override = get(f"llm_provider_{task}")
        if override:
            return override
    return get("default_llm_provider", "mock")


def resolve_tts_provider() -> str:
    return get("default_tts_provider", "mock")


def resolve_stock_provider() -> str:
    return get("default_stock_provider", "mock")
