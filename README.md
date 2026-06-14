# Threads × 쿠팡 파트너스 마케팅 자동화 CLI

스레드(Threads)의 인기 게시글을 분석하여 미디어(이미지/영상)를 추출하고, **Claude**
로 타겟 맞춤형 후킹 문구를 생성한 뒤, **쿠팡 파트너스** 링크와 광고 고지 문구와 함께
새 스레드로 자동 발행하는 전과정 자동화 CLI 프로그램입니다.

```
scrape → process → generate → convert → post
  (스크래핑)  (미디어가공)   (문구생성)   (링크변환)  (자동발행)
```

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 언어 | Python 3.10+ (`asyncio` 비동기) |
| 웹 자동화 | [Playwright](https://playwright.dev/python/) |
| AI 연동 | [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) (`claude-opus-4-8`) |
| 미디어 처리 | OpenCV (`opencv-python`), Pillow |
| 환경 변수 | `python-dotenv` |

## 아키텍처 (클래스 구조)

기능별로 모듈화된 Class 기반 구조입니다.

| 클래스 | 모듈 | 역할 |
| --- | --- | --- |
| `ThreadScraper` | `src/scraper.py` | 타겟 스레드 게시글 분석 및 미디어 다운로드 |
| `MediaProcessor` | `src/media_processor.py` | 영상 프레임 추출 및 썸네일 가공 |
| `ClaudeGenerator` | `src/claude_generator.py` | Claude 통한 마케팅 문구 생성 |
| `CoupangConverter` | `src/coupang_converter.py` | 쿠팡 링크 변환 및 광고 고지 삽입 |
| `ThreadPoster` | `src/thread_poster.py` | 콘텐츠를 내 스레드 계정에 자동 업로드 |
| `CLIController` | `src/cli_controller.py` | `argparse` 명령어 제어 타워 |

## 설치

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) Playwright 브라우저 설치
playwright install chromium

# 3) 환경 변수 설정
cp .env.example .env
#   .env 파일을 열어 API 키 / 계정 정보 / 쿠팡 파트너스 태그를 입력하세요.
```

## 환경 변수 (`.env`)

| 변수 | 설명 |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude API 키 (**필수**) |
| `CLAUDE_MODEL` | 사용할 모델 (기본 `claude-opus-4-8`) |
| `THREADS_USERNAME` / `THREADS_PASSWORD` | 발행할 스레드 계정 |
| `COUPANG_PARTNER_TAG` | 쿠팡 파트너스 추적 ID |
| `HEADLESS` | 브라우저 표시 여부 (`true`/`false`) |
| `WORK_DIR` | 산출물 저장 경로 (기본 `./output`) |

> 🔒 `.env` 는 절대 git 에 커밋하지 마세요. (`.gitignore` 에 포함되어 있습니다.)

## 사용법

### 전 과정 자동 실행

```bash
python main.py run \
  --source "https://www.threads.net/@someone/post/XXXX" \
  --coupang "https://www.coupang.com/vp/products/123456" \
  --audience "자취 1인가구" \
  --hint "미니 가습기" \
  --dry-run        # 발행 직전까지만 (실제 게시 생략)
```

### 단계별 실행

```bash
# 스크래핑만
python main.py scrape --source "<스레드_URL>"

# 문구 생성만
python main.py generate --text "원본 게시글 본문" --audience "육아맘"

# 발행만 (준비된 캡션/미디어)
python main.py post --caption "캡션 내용" --media ./output/processed/a_thumb.jpg
```

전역 옵션 `-v / --verbose` 로 상세 로그를 볼 수 있습니다.

## 테스트

순수 로직(쿠팡 링크 변환, 모델 분리 등)에 대한 단위 테스트:

```bash
python -m pytest tests/ -v
```

## 주의 사항 / 면책

- 스레드/쿠팡의 **이용약관과 로봇 정책**을 준수하여 사용하세요. 무분별한 자동
  스크래핑·발행은 계정 제재 사유가 될 수 있습니다.
- 스레드는 공식 게시 API 가 제한적이라 DOM 셀렉터에 의존합니다. UI 변경 시
  `scraper.py` / `thread_poster.py` 의 셀렉터를 갱신해야 할 수 있습니다.
- 모든 발행물에는 공정거래위원회 권고에 따른 **광고 고지 문구**가 자동 삽입됩니다.
- 2단계 인증이 설정된 계정은 최초 1회 `HEADLESS=false` 로 수동 로그인 후 세션
  (`output/auth_state.json`)을 재사용하는 것을 권장합니다.
