#!/usr/bin/env python3
"""네이버 로그인 세션 저장 스크립트 (로컬 전용).

실행하면 브라우저 창이 뜨고, 직접 네이버에 로그인하면 세션이
data/naver_auth.json 에 저장된다. 이후 대시보드의 "쇼핑커넥트 발급" 버튼이
이 세션을 사용한다. (자동 로그인은 계정 정지 리스크가 있어 지원하지 않음)

사용법:
    python naver_login.py
"""

from engine.ingest.naver_connect import login_and_save_session

if __name__ == "__main__":
    path = login_and_save_session()
    print(f"세션 저장 완료: {path}")
    print("이제 프로젝트 페이지의 '쇼핑커넥트 발급' 버튼을 사용할 수 있습니다.")
