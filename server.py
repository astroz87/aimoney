#!/usr/bin/env python3
"""멀티채널 숏폼 어필리에이트 자동화 시스템 — FastAPI 서버 진입점.

실행:
    uvicorn server:app --reload --port 8000
    또는
    python server.py
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db

app = FastAPI(title="숏폼 어필리에이트 자동화", version="0.1.0")

# 크롬 확장(로컬 파일/확장 오리진)에서의 POST 를 허용.
# MVP 로컬 단일사용자 전제 → 전체 허용. (운영 시 오리진 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --- 라우터 등록 ---
from app.api import pages, projects, sources  # noqa: E402

app.include_router(pages.router)
app.include_router(projects.router)
app.include_router(sources.router)


def _try_include(module_name: str) -> None:
    """점진 등록 — 아직 구현되지 않은 라우터는 조용히 건너뛴다."""
    import importlib

    try:
        mod = importlib.import_module(f"app.api.{module_name}")
        app.include_router(mod.router)
    except ImportError:
        pass


for _m in ("settings", "jobs", "assets", "analysis", "script", "tts",
           "render", "packages", "scenes", "audio"):
    _try_include(_m)

# --- 정적 파일 ---
_STATIC_DIR = Path(__file__).resolve().parent / "app" / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
