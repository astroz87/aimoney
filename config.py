"""중앙 설정 모듈.

`python-dotenv` 를 사용해 `.env` 파일의 값을 읽어 들이고, 애플리케이션 전반에서
사용하는 설정값을 하나의 `Settings` 데이터클래스로 노출한다. API 키/계정 정보와
같은 민감 정보는 절대 소스코드에 하드코딩하지 않고 이 모듈을 통해서만 접근한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 모듈 임포트 시점에 .env 를 한 번 로드한다.
load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    """문자열 환경 변수를 bool 로 변환한다."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class Settings:
    """런타임 설정 컨테이너."""

    # --- Claude ---
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-4-8"))

    # --- Threads 계정 ---
    threads_username: str = field(default_factory=lambda: os.getenv("THREADS_USERNAME", ""))
    threads_password: str = field(default_factory=lambda: os.getenv("THREADS_PASSWORD", ""))

    # --- 쿠팡 파트너스 ---
    coupang_partner_tag: str = field(default_factory=lambda: os.getenv("COUPANG_PARTNER_TAG", ""))
    coupang_access_key: str = field(default_factory=lambda: os.getenv("COUPANG_ACCESS_KEY", ""))
    coupang_secret_key: str = field(default_factory=lambda: os.getenv("COUPANG_SECRET_KEY", ""))

    # --- 동작 옵션 ---
    headless: bool = field(default_factory=lambda: _as_bool(os.getenv("HEADLESS"), True))
    work_dir: Path = field(default_factory=lambda: Path(os.getenv("WORK_DIR", "./output")))

    def __post_init__(self) -> None:
        # 작업 디렉터리 보장
        self.work_dir = Path(self.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 검증 헬퍼
    # ------------------------------------------------------------------
    def require_claude(self) -> None:
        if not self.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요."
            )

    def require_threads(self) -> None:
        if not (self.threads_username and self.threads_password):
            raise RuntimeError(
                "THREADS_USERNAME / THREADS_PASSWORD 가 설정되지 않았습니다. .env 파일을 확인하세요."
            )

    def require_coupang(self) -> None:
        if not self.coupang_partner_tag:
            raise RuntimeError(
                "COUPANG_PARTNER_TAG 가 설정되지 않았습니다. .env 파일을 확인하세요."
            )


# 전역 싱글턴처럼 사용할 인스턴스
settings = Settings()
