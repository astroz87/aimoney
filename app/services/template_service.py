"""TemplateService — 스타일 프리셋(내장) + 커스텀 템플릿(저장) 목록/적용.

커스텀 템플릿은 data/custom_templates.json 에 저장한다(로컬 단일 사용자, 마이그레이션 불필요).
적용 시 프로젝트 edit_settings 에 자막/제목/레이아웃/전환/배경/톤을 병합(사용자 BGM 보존).
"""

from __future__ import annotations

import json

from config import settings
from engine.models import resolve_edit_settings, slugify
from engine.template import get_preset, list_presets
from app.db.database import session_scope
from app.db.models_orm import Project

# 커스텀 템플릿에 캡처하는 edit_settings 필드
_CAPTURE = [
    "bg_color", "transition", "transition_duration", "bgm_volume",
    "fit_mode", "box_scale", "box_h", "box_y", "show_title",
    "title_style", "subtitle_style", "script_tone",
]


def _store_path():
    return settings.data_dir / "custom_templates.json"


def _load_custom() -> list[dict]:
    p = _store_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _save_custom(items: list[dict]) -> None:
    _store_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def templates() -> list[dict]:
    """내장 + 커스텀 목록 (UI 표시용)."""
    built = [{**t, "is_custom": False} for t in list_presets()]
    custom = [{"id": c["id"], "name": c["name"],
               "description": c.get("description", ""), "is_custom": True}
              for c in _load_custom()]
    return built + custom


def _get_template_data(template_id: str) -> dict | None:
    preset = get_preset(template_id)
    if preset is not None:
        return preset
    for c in _load_custom():
        if c["id"] == template_id:
            return c
    return None


def apply_template(project_id: str, template_id: str) -> dict:
    data = _get_template_data(template_id)
    if data is None:
        raise RuntimeError(f"알 수 없는 템플릿: {template_id}")

    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")

        current = resolve_edit_settings(project.edit_settings)
        # 시각/전환 설정 병합 (사용자 BGM 파일/on-off 는 보존)
        for k, v in data.get("edit_settings", {}).items():
            current[k] = v
        # 커스텀 템플릿은 캡처 필드가 최상위에 있을 수 있음
        for k in _CAPTURE:
            if k in data:
                current[k] = data[k]
        current["subtitle_style"] = data.get("subtitle_style", current.get("subtitle_style", {}))
        current["title_style"] = data.get("title_style", current.get("title_style", {}))
        current["fit_mode"] = data.get("fit_mode", current.get("fit_mode", "cover"))
        current["show_title"] = data.get("show_title", current.get("show_title", False))
        current["script_tone"] = data.get("script_tone", current.get("script_tone", ""))
        current["template_id"] = template_id
        project.edit_settings = current

    return {"template_id": template_id, "applied": True}


def save_custom(project_id: str, name: str, description: str = "") -> dict:
    """현재 프로젝트의 스타일 설정을 커스텀 템플릿으로 저장한다."""
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")
        cfg = resolve_edit_settings(project.edit_settings)

    items = _load_custom()
    base_id = "custom_" + (slugify(name) or "template")
    tid, n = base_id, 2
    existing = {c["id"] for c in items}
    while tid in existing:
        tid = f"{base_id}_{n}"
        n += 1

    entry = {"id": tid, "name": name or "커스텀", "description": description,
             "is_custom": True}
    for k in _CAPTURE:
        entry[k] = cfg.get(k)
    items.append(entry)
    _save_custom(items)
    return {"id": tid, "name": entry["name"]}


def delete_custom(template_id: str) -> bool:
    items = _load_custom()
    new_items = [c for c in items if c["id"] != template_id]
    if len(new_items) == len(items):
        return False
    _save_custom(new_items)
    return True
