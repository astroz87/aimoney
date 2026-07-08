# 멀티채널 숏폼 어필리에이트 자동화 시스템

중국 쇼핑 사이트 상품을 수집해 **후킹 컷 분석 → 대본 → TTS → 자막 → 9:16 렌더링 →
플랫폼별 업로드 패키지**까지 자동 생성하는 로컬 웹 대시보드 기반 시스템입니다.

> **설계 원칙:** 완전 자동 배포는 하지 않습니다. MVP 는 "업로드 패키지 생성 + 수동 검수"
> 까지이며, 저작권(권리 확인)과 경제적 이해관계 표시(공정위)를 코드 레벨에서 강제합니다.

```
수집(확장) → 프로젝트 → 영상분석 → 대본 → TTS → 타임라인 → 렌더링 → 패키지
  content.js   /import    hook cut   scene   mp3    matcher    ffmpeg    platforms/
```

## 구성 요소

| 계층 | 위치 | 역할 |
| --- | --- | --- |
| 로컬 웹 대시보드 | `server.py`, `app/` | FastAPI + Jinja2. 프로젝트/파이프라인 제어 |
| 핵심 엔진 | `engine/` | 분석·대본·TTS·타임라인·자막·렌더·패키지 (웹 비의존) |
| 플랫폼 규칙 | `platforms/` | 플랫폼별 제목/캡션/해시태그 규칙 (파일 하나로 관리) |
| 크롬 확장 | `extension/` | 상품 페이지 수집 → 대시보드 전송 (MV3) |
| 기존 CLI | `src/`, `main.py` | Threads × 쿠팡 단일채널 CLI (보존) |

## 기술 스택

- **웹**: FastAPI + Uvicorn + Jinja2 (+ 바닐라 JS)
- **DB**: SQLite (SQLAlchemy) — `data/app.db`
- **영상 분석**: OpenCV + PySceneDetect (컷 분할, 후킹 점수 휴리스틱)
- **렌더링**: ffmpeg (9:16, 자막 번인, TTS 합성)
- **LLM**: Provider 추상화 — Claude / Gemini / GPT / Mock (설정창 선택)
- **TTS**: Provider 추상화 — Mock / Edge TTS / Gemini·Typecast(스텁)
- **자막**: ASS 우선, SRT 보조

## 설치

```bash
# 1) 파이썬 의존성
pip install -r requirements.txt

# 2) ffmpeg (렌더링 필수)
#   Ubuntu:  sudo apt-get install -y ffmpeg
#   macOS:   brew install ffmpeg

# 3) (선택) LLM SDK — 해당 프로바이더를 쓸 때만
pip install anthropic                 # Claude
pip install google-generativeai       # Gemini
pip install openai                    # GPT

# 4) 환경 변수
cp .env.example .env    # 필요 시 편집 (또는 설정창에서 관리)
```

## 실행

```bash
uvicorn server:app --port 8000
# 대시보드:  http://localhost:8000
# 설정창:    http://localhost:8000/settings
```

### 크롬 확장 설치

`chrome://extensions` → 개발자 모드 → **압축해제된 확장 프로그램 로드** → `extension/` 폴더.
자세한 내용은 [`extension/README.md`](extension/README.md).

## 사용 흐름

1. **수집**: 상품 페이지에서 확장 클릭 → 전송. (또는 대시보드에서 직접 생성)
2. **권리 확인**: 프로젝트 상세에서 `usage_status` 를 **확인됨** 으로 변경.
   (⚠️ 확인됨이 아니면 렌더링이 차단됩니다.)
3. **영상 등록**: 파일 업로드 또는 URL 다운로드. (업로드 = 권리 보유 전제)
4. **파이프라인**: 검색어 → 분석 → 대본 → TTS → 타임라인 → 렌더링 → 패키지.
5. **결과**: `output/{product_id}/` 에 아래가 생성됩니다.

```
output/{product_id}/
  final.mp4  thumbnail.jpg  subtitle.ass  subtitle.srt
  script.json  timeline.json  package_summary.json
  naver_clip/       title.txt  description.txt  hashtags.txt
  instagram_reels/  caption.txt  hashtags.txt
  tiktok_lite/      caption.txt  hashtags.txt
  youtube_shorts/   title.txt  description.txt  pinned_comment.txt  hashtags.txt
  naver_tv/ · facebook_reels/ · threads/
  affiliate/links.json
  tracking/tracking_urls.json
  {product_id}_package.zip
```

## 설정창 (LLM / TTS)

`/settings` 에서 Claude·Gemini·GPT 의 **API 키와 모델**을 지정하고 기본 프로바이더를
선택합니다. 대본·검색어 생성기는 여기서 고른 프로바이더를 주입받아 동작하며,
**키가 없으면 자동으로 Mock 으로 폴백**해 오프라인에서도 전체 흐름이 검증됩니다.
API 키는 저장 시 마스킹되어 표시됩니다. 우선순위: **DB 설정 > .env > 기본값**.

## 지원 플랫폼

- **필수(1순위)**: 네이버 클립 · 인스타 릴스 · 틱톡 라이트
- **확장(2순위)**: 유튜브 쇼츠 · 네이버TV · 페이스북 릴스 · 스레드

플랫폼 규칙은 `platforms/{name}.py` 하나로 관리되어 추가/수정이 쉽습니다.

## 어필리에이트 · 경제적 이해관계 표시

- 카테고리 → 프로바이더 매핑(쿠팡파트너스 / 네이버 쇼핑커넥트 / 오늘의집 / 무신사).
- 링크는 본문에 하드코딩하지 않고 `/go/{slug}?src={platform}` 트래킹 URL 로만 노출
  (`tracking/tracking_urls.json`).
- **경제적 이해관계 표시 문구**는 모든 플랫폼 본문 첫 줄에 자동 삽입되며,
  누락 시 패키지 생성이 실패합니다.

## API 요약

| Method | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/import-source` | 확장/수동 수집 → 프로젝트 생성 |
| GET/POST | `/api/projects` | 목록 / 생성 |
| GET/PATCH | `/api/projects/{id}` | 상세 / 수정(usage_status 등) |
| POST | `/api/projects/{id}/search-queries` | 한→중 검색어 |
| POST | `/api/projects/{id}/assets/upload`·`/register` | 영상 업로드/등록 |
| POST | `/api/projects/{id}/analyze` | 영상 분석 잡 |
| POST/PUT | `/api/projects/{id}/script` | 대본 생성/편집 |
| POST | `/api/projects/{id}/tts` | TTS 잡 |
| POST | `/api/projects/{id}/timeline` | 타임라인 매칭 |
| POST | `/api/projects/{id}/render` | 렌더 잡 |
| POST | `/api/projects/{id}/package` | 패키지 생성 잡 |
| GET | `/api/projects/{id}/download` | 패키지 ZIP |
| GET | `/api/jobs/{id}` | 잡 상태 폴링 |
| GET/PUT/POST | `/api/settings`·`/test` | 프로바이더/키 관리·유효성 |

## 테스트

```bash
python -m pytest tests/ -v
```

핵심 파이프라인 로직(타임라인 매칭, ASS 자막, 경제적 이해관계 문구, 어필리에이트
매핑, 패키지 빌더)은 ffmpeg/네트워크 없이 검증됩니다 — `tests/test_pipeline.py`.

## 범위 밖 (MVP 제외)

완전 자동 업로드 · 실제 구매전환 데이터 연동 · 전 사이트 자동 크롤링 ·
캡챠/로그인/DRM 우회 · 고급 비전 모델 · SaaS 배포.

## 주의 / 면책

- 중국 사이트 영상은 **권리 확인이 필요**합니다. 시스템은 도구를 제공할 뿐,
  사용 책임은 사용자에게 있습니다. (`source_url` · `usage_status` 필드로 추적)
- 틱톡 라이트 등 일부 플랫폼의 외부링크/리워드 정책은 상이하므로, 패키지 생성 후
  **수동 검수**로 업로드 가능 여부를 확인하세요.
- 실제 Gemini/Typecast TTS 는 스텁이며, MVP 실동작 TTS 는 Edge TTS(무료)입니다.
