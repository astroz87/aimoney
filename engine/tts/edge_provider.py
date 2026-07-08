"""EdgeTTSProvider — Microsoft Edge TTS(무료) 로 한국어 음성을 생성한다.

emotion/pace 를 rate 파라미터로 매핑한다. 실제 음성 MVP 경로.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from engine.media_utils import probe_duration
from .base import TTSProvider

logger = logging.getLogger(__name__)

# 기본 한국어 음성
_DEFAULT_VOICE = "ko-KR-SunHiNeural"

_PACE_RATE = {"fast": "+15%", "normal": "+0%", "slow": "-15%"}


class EdgeTTSProvider(TTSProvider):
    provider_id = "edge"

    def __init__(self, voice: str = "") -> None:
        super().__init__(voice=voice or _DEFAULT_VOICE)

    def synthesize(self, text: str, *, emotion: str = "neutral",
                   pace: str = "normal", output_path: str) -> dict:
        try:
            import edge_tts
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("edge-tts 미설치 (pip install edge-tts)") from exc

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        rate = _PACE_RATE.get(pace, "+0%")

        async def _run() -> None:
            communicate = edge_tts.Communicate(text or " ", self.voice, rate=rate)
            await communicate.save(str(out))

        try:
            asyncio.run(_run())
        except RuntimeError:
            # 이미 이벤트 루프가 도는 환경 대비
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

        duration = probe_duration(str(out)) or self.estimate_duration(text)
        return {"audio_path": str(out), "duration": round(duration, 2)}
