"""TemplateService — 스타일 프리셋 목록/적용.

적용 시 프로젝트의 edit_settings 에 subtitle_style/전환/배경/BGM볼륨/톤 을 병합한다.
BGM 파일 경로/사용여부 등 사용자가 이미 설정한 값은 보존한다.
"""

from __future__ import annotations

from engine.models import resolve_edit_settings
from engine.template import get_preset, list_presets
from app.db.database import session_scope
from app.db.models_orm import Project


def templates() -> list[dict]:
    return list_presets()


def apply_template(project_id: str, template_id: str) -> dict:
    preset = get_preset(template_id)
    if preset is None:
        raise RuntimeError(f"알 수 없는 템플릿: {template_id}")

    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError("프로젝트를 찾을 수 없습니다")

        current = resolve_edit_settings(project.edit_settings)
        # 시각/전환 설정 병합 (사용자 BGM 파일/on-off 는 보존)
        for k, v in preset.get("edit_settings", {}).items():
            current[k] = v
        current["subtitle_style"] = preset.get("subtitle_style", {})
        current["title_style"] = preset.get("title_style", {})
        current["fit_mode"] = preset.get("fit_mode", "cover")
        current["show_title"] = preset.get("show_title", False)
        current["script_tone"] = preset.get("script_tone", "")
        current["template_id"] = preset["id"]
        project.edit_settings = current

    return {"template_id": template_id, "applied": True}
