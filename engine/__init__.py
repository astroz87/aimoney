"""핵심 자동화 엔진 (웹 계층 비의존, 순수 파이썬).

하위 패키지:
    ingest     : 영상 후보 다운로드 / 한→중 검색어 생성
    analysis   : 컷 분할 / 품질 지표 / 후킹 점수
    llm        : LLM Provider 추상화 (claude/gemini/openai/mock)
    script     : 후킹 컷 기반 대본 생성
    tts        : TTS Provider 추상화 (mock/edge/gemini/typecast)
    timeline   : scene ↔ clip 매칭 및 타임라인 생성
    subtitle   : ASS/SRT 자막 생성
    render     : ffmpeg 렌더링
    thumbnail  : 썸네일 생성
    package    : 플랫폼별 배포 패키지 / 어필리에이트 / 경제적 이해관계 문구
"""

__all__: list[str] = []
