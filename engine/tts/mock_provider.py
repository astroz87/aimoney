"""MockTTSProvider — 실제 음성 없이 추정 길이만큼의 무음 오디오를 생성한다.

파이프라인(렌더링 타이밍) 검증용. ffmpeg 로 무음 mp3 를 만든다.
ffmpeg 가 없으면 빈 파일 + 추정 길이만 반환한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from engine.media_utils import has_ffmpeg, probe_duration, run_ffmpeg
from .base import TTSProvider

logger = logging.getLogger(__name__)


class MockTTSProvider(TTSProvider):
    provider_id = "mock"

    def synthesize(self, text: str, *, emotion: str = "neutral",
                   pace: str = "normal", output_path: str) -> dict:
        dur = self.estimate_duration(text)
        # pace 반영: fast 는 짧게, slow 는 길게
        if pace == "fast":
            dur *= 0.85
        elif pace == "slow":
            dur *= 1.2
        dur = round(max(1.0, dur), 2)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if has_ffmpeg():
            proc = run_ffmpeg([
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(dur), "-q:a", "9", str(out),
            ], timeout=60)
            if proc.returncode == 0 and out.exists():
                measured = probe_duration(str(out)) or dur
                return {"audio_path": str(out), "duration": round(measured, 2)}
            logger.warning("Mock TTS ffmpeg 실패: %s", proc.stderr[-200:])

        out.write_bytes(b"")
        return {"audio_path": str(out), "duration": dur}
