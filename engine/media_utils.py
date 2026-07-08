"""ffmpeg/ffprobe 공통 유틸리티."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    return shutil.which("ffprobe") or "ffprobe"


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def probe_duration(path: str) -> float:
    """미디어 파일의 길이(초)를 ffprobe 로 측정한다. 실패 시 0.0."""
    try:
        out = subprocess.run(
            [ffprobe_bin(), "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        return float(data.get("format", {}).get("duration", 0.0) or 0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffprobe 실패(%s): %s", path, exc)
        return 0.0


def run_ffmpeg(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    """ffmpeg 를 실행하고 CompletedProcess 를 반환한다(체크는 호출측)."""
    cmd = [ffmpeg_bin(), "-y", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
