"""JobService — 비동기 작업(analyze/tts/render/package) 실행 및 상태 추적.

FastAPI BackgroundTasks 로 실행한다. 각 잡은 자체 DB 세션을 열어 progress/log/status
를 갱신한다. 클라이언트는 GET /api/jobs/{id} 로 폴링한다.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from typing import Callable

from app.db.database import session_scope
from app.db.models_orm import Job

logger = logging.getLogger(__name__)


class JobContext:
    """잡 실행 중 진행률/로그를 갱신하기 위한 핸들."""

    def __init__(self, job_id: int) -> None:
        self.job_id = job_id

    def update(self, *, progress: int | None = None, log: str | None = None,
               status: str | None = None) -> None:
        with session_scope() as db:
            job = db.get(Job, self.job_id)
            if job is None:
                return
            if progress is not None:
                job.progress = max(0, min(100, progress))
            if log is not None:
                job.log = log
            if status is not None:
                job.status = status


def create_job(db, project_id: str, job_type: str) -> Job:
    job = Job(project_id=project_id, job_type=job_type, status="pending", progress=0)
    db.add(job)
    db.flush()
    return job


def run_job(job_id: int, fn: Callable[[JobContext], None]) -> None:
    """BackgroundTasks 진입점. fn(ctx) 를 실행하며 상태를 관리한다."""
    ctx = JobContext(job_id)
    ctx.update(status="running", progress=1, log="시작")
    try:
        fn(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("job %s 실패", job_id)
        detail = f"{exc}"
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.log = detail[:2000]
                job.finished_at = datetime.now(timezone.utc)
                job.progress = 100
        return
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job and job.status != "failed":
            job.status = "done"
            job.progress = 100
            job.finished_at = datetime.now(timezone.utc)
            if not job.log or job.log == "시작":
                job.log = "완료"


def get_traceback() -> str:
    return traceback.format_exc()
