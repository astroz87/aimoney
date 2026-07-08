"""웹 계층 (FastAPI 대시보드 + REST API).

하위 패키지:
    api       : REST 라우터
    services  : 오케스트레이션 (API ↔ engine 연결)
    db        : SQLAlchemy 엔진/세션 및 ORM 모델
    templates : Jinja2 템플릿
    static    : 정적 리소스
"""

__all__: list[str] = []
