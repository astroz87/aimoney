"""SQLAlchemy 엔진/세션 관리.

SQLite 로컬 파일(app.db)을 사용한다. FastAPI 의존성 주입용 `get_session` 과
스크립트/서비스용 컨텍스트 매니저 `session_scope` 를 함께 제공한다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스."""


# SQLite 는 기본적으로 스레드 간 커넥션 공유를 막으므로 check_same_thread=False.
_engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record) -> None:
    """커넥션마다 SQLite 안정성 PRAGMA 적용.

    - WAL: 백그라운드 잡(렌더/TTS)과 웹 요청이 동시에 써도 락 충돌 최소화
    - busy_timeout: 잠금 시 즉시 실패 대신 5초 대기
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()

SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """모든 테이블을 생성한다 (idempotent). 모델 임포트 후 호출."""
    # 모델 등록을 위해 임포트 (순환참조 방지 위해 함수 내부 임포트)
    from . import models_orm  # noqa: F401

    Base.metadata.create_all(bind=_engine)
    _run_light_migrations()


def _run_light_migrations() -> None:
    """SQLite create_all 은 기존 테이블에 컬럼을 추가하지 않으므로,
    누락된 컬럼을 ALTER TABLE 로 보강한다(간단한 전진 마이그레이션)."""
    from sqlalchemy import text

    # (table, column, DDL 타입/기본값)
    wanted = [
        ("scenes", "preferred_clip_id", "VARCHAR DEFAULT ''"),
        ("scenes", "sfx_path", "VARCHAR DEFAULT ''"),
        ("projects", "edit_settings", "JSON DEFAULT '{}'"),
    ]
    with _engine.begin() as conn:
        for table, column, ddl in wanted:
            cols = {row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))}
            if column not in cols:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl}'))


def get_session() -> Iterator[Session]:
    """FastAPI 의존성: 요청 스코프 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """서비스/스크립트용: 커밋/롤백을 자동 처리하는 세션 컨텍스트."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
