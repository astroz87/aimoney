"""중앙 설정 모듈.

`python-dotenv` 를 사용해 `.env` 파일의 값을 읽어 들이고, 애플리케이션 전반에서
사용하는 설정값을 하나의 `Settings` 데이터클래스로 노출한다. API 키/계정 정보와
같은 민감 정보는 절대 소스코드에 하드코딩하지 않고 이 모듈을 통해서만 접근한다.

주의: 런타임 프로바이더/모델/키 선택은 DB `settings` 테이블이 이 파일의 .env 기본값을
오버라이드한다 (우선순위: DB > .env > 아래 기본값). 이 모듈은 부팅 기본값만 담당한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 모듈 임포트 시점에 .env 를 한 번 로드한다.
load_dotenv()

# 저장소 루트 (이 파일 위치 기준)
BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value: str | None, default: bool = False) -> bool:
    """문자열 환경 변수를 bool 로 변환한다."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class Settings:
    """런타임 설정 컨테이너 (부팅 기본값)."""

    # --- Claude (기존 CLI 호환 유지) ---
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-4-8"))

    # --- Gemini ---
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    # --- OpenAI (GPT) ---
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))

    # --- 스톡 영상 (Pexels) ---
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", ""))

    # --- 기본 프로바이더 선택 ---
    default_llm_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", "mock"))
    default_tts_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_TTS_PROVIDER", "mock"))
    default_stock_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_STOCK_PROVIDER", "mock"))

    # --- Threads 계정 (기존 CLI) ---
    threads_username: str = field(default_factory=lambda: os.getenv("THREADS_USERNAME", ""))
    threads_password: str = field(default_factory=lambda: os.getenv("THREADS_PASSWORD", ""))

    # --- 쿠팡 파트너스 (기존 CLI) ---
    coupang_partner_tag: str = field(default_factory=lambda: os.getenv("COUPANG_PARTNER_TAG", ""))
    coupang_access_key: str = field(default_factory=lambda: os.getenv("COUPANG_ACCESS_KEY", ""))
    coupang_secret_key: str = field(default_factory=lambda: os.getenv("COUPANG_SECRET_KEY", ""))

    # --- 링크 라우터 ---
    link_router_base: str = field(
        default_factory=lambda: os.getenv("LINK_ROUTER_BASE", "https://allmyinterest.com/go")
    )

    # --- 동작 옵션 ---
    headless: bool = field(default_factory=lambda: _as_bool(os.getenv("HEADLESS"), True))
    work_dir: Path = field(default_factory=lambda: Path(os.getenv("WORK_DIR", str(BASE_DIR / "output"))))

    # --- 데이터/산출물 경로 ---
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))))

    def __post_init__(self) -> None:
        # 주요 디렉터리 보장
        self.work_dir = Path(self.work_dir)
        self.data_dir = Path(self.data_dir)
        self.output_dir = Path(self.output_dir)
        for d in (self.work_dir, self.data_dir, self.output_dir, self.projects_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 파생 경로
    # ------------------------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    def project_dir(self, product_id: str) -> Path:
        """프로젝트별 작업 폴더 (raw/clips/tts/project.json)."""
        return self.projects_dir / product_id

    def output_project_dir(self, product_id: str) -> Path:
        """프로젝트별 최종 배포 패키지 폴더."""
        return self.output_dir / product_id

    # ------------------------------------------------------------------
    # 검증 헬퍼 (기존 CLI 호환)
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
