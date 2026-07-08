@echo off
rem ============================================================
rem  aimoney 로컬 실행 런처 (Windows)
rem  더블클릭하면: 의존성 설치(최초 1회) -> ffmpeg 확인 -> 서버 시작
rem  브라우저에서 http://127.0.0.1:8000 이 자동으로 열립니다.
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo [aimoney] 멀티채널 숏폼 어필리에이트 대시보드
echo.

rem --- 1) Python 확인 ---
where python >nul 2>nul
if errorlevel 1 (
    echo [오류] Python 을 찾을 수 없습니다.
    echo        https://www.python.org/downloads/ 에서 3.10 이상을 설치하고
    echo        설치 시 "Add python.exe to PATH" 를 반드시 체크하세요.
    pause
    exit /b 1
)

rem --- 2) 의존성 설치 (최초 1회, .deps_installed 마커로 스킵) ---
if not exist ".deps_installed" (
    echo [설치] 파이썬 패키지를 설치합니다. 몇 분 걸릴 수 있습니다...
    python -m pip install --upgrade pip >nul
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [오류] 패키지 설치에 실패했습니다. 네트워크 상태를 확인하세요.
        pause
        exit /b 1
    )
    echo ok> .deps_installed
    echo [설치] 완료.
)

rem --- 3) ffmpeg 확인 (렌더링 필수) ---
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [경고] ffmpeg 를 찾을 수 없습니다. 영상 렌더링이 실패합니다.
    echo        https://www.gyan.dev/ffmpeg/builds/ 에서 release full 을 받아
    echo        압축 해제 후 bin 폴더를 PATH 에 추가하세요.
    echo        (설치 없이 대시보드/대본 기능은 사용 가능)
    echo.
)

rem --- 4) 브라우저 자동 열기 + 서버 시작 ---
start "" http://127.0.0.1:8000
echo [실행] 서버를 시작합니다. 이 창을 닫으면 서버가 종료됩니다.
echo        중지: Ctrl+C
echo.
python -m uvicorn server:app --host 127.0.0.1 --port 8000

pause
