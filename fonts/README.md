# fonts/ — 자막 폰트 폴더

이 폴더에 한국어 폰트 파일(`.ttf` / `.otf`)을 넣으면 렌더링 시
시스템 폰트보다 **우선 사용**됩니다 (ffmpeg `fontsdir` 자동 적용).

## 기본 동작 (폰트를 넣지 않아도 됨)

| 환경 | 기본 폰트 |
|---|---|
| Windows | Malgun Gothic (맑은 고딕, 기본 내장) |
| Linux/Mac | Noto Sans CJK KR |

## 폰트를 직접 넣고 싶을 때

1. 무료 폰트 다운로드 (예시):
   - [Pretendard](https://github.com/orioncactus/pretendard/releases) — `Pretendard-Bold.ttf`
   - [Noto Sans KR](https://fonts.google.com/noto/specimen/Noto+Sans+KR)
   - [에스코어드림](https://s-core.co.kr/company/font/) 등 상업용 무료 폰트
2. `.ttf`/`.otf` 파일을 이 폴더에 복사
3. 편집기 → 텍스트 스타일 패널에서 폰트 이름을 해당 폰트의 **패밀리명**으로 지정
   (예: `Pretendard`)

> 주의: 폰트 파일 자체는 저장소에 커밋하지 않습니다(라이선스/용량).
> 이 폴더의 `*.ttf`, `*.otf` 는 gitignore 처리되어 있습니다.
