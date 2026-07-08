"""컷 분할 — PySceneDetect 로 장면 전환 경계를 검출한다.

PySceneDetect 미설치/실패 시, 고정 간격 분할로 폴백한다.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def split_scenes(video_path: str, *, threshold: float = 27.0,
                 min_scene_len: float = 1.0) -> list[tuple[float, float]]:
    """(start, end) 초 단위 구간 리스트를 반환한다."""
    try:
        from scenedetect import detect, ContentDetector

        scenes = detect(
            video_path,
            ContentDetector(threshold=threshold, min_scene_len=int(min_scene_len * 15)),
        )
        result = [(s.get_seconds(), e.get_seconds()) for s, e in scenes]
        if result:
            return result
        logger.info("PySceneDetect: 장면 경계 없음 → 고정 간격 폴백")
    except Exception as exc:  # noqa: BLE001
        logger.warning("PySceneDetect 실패(%s) → 고정 간격 폴백", exc)

    return _fixed_interval_split(video_path)


def _fixed_interval_split(video_path: str, seg: float = 3.0) -> list[tuple[float, float]]:
    """OpenCV 로 총 길이를 구해 seg 초 간격으로 분할."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    duration = frames / fps if fps else 0.0
    if duration <= 0:
        return [(0.0, seg)]
    out: list[tuple[float, float]] = []
    t = 0.0
    while t < duration:
        out.append((t, min(t + seg, duration)))
        t += seg
    return out
