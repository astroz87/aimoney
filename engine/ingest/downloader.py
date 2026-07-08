"""영상 후보 다운로드.

mp4 등 직접 파일: urllib 스트리밍. m3u8 스트리밍: ffmpeg 로 remux.
캡챠/로그인/DRM 우회는 하지 않는다. 실패는 예외로 알린다.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def download_video(url: str, dest: Path, *, timeout: int = 60) -> Path:
    """url 을 dest 로 다운로드한다. 성공 시 dest 경로 반환."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ".m3u8" in url.lower():
        return _download_m3u8(url, dest)
    return _download_direct(url, dest, timeout=timeout)


def _download_direct(url: str, dest: Path, *, timeout: int) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"빈 파일 다운로드: {url}")
    return dest


def _download_m3u8(url: str, dest: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("m3u8 다운로드에는 ffmpeg 가 필요합니다")
    if dest.suffix.lower() != ".mp4":
        dest = dest.with_suffix(".mp4")
    cmd = [
        "ffmpeg", "-y", "-user_agent", _UA, "-i", url,
        "-c", "copy", "-bsf:a", "aac_adtstoasc", str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(f"m3u8 다운로드 실패: {proc.stderr[-400:]}")
    return dest
