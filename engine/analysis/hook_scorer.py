"""후킹 점수 계산 및 영상 분석 오케스트레이션.

HookScore = w1·제품노출 + w2·움직임 + w3·장면변화 + w4·선명도 + w5·시각적특이성
휴리스틱 기반. 각 항목 0~1, 가중합 후 0~1 로 정규화.
"""

from __future__ import annotations

import logging

from engine.models import Clip
from .scene_splitter import split_scenes
from .metrics import analyze_clip_metrics

logger = logging.getLogger(__name__)

# 가중치 (합 = 1.0)
W_PRODUCT = 0.30      # 제품 노출도
W_MOTION = 0.20       # 움직임
W_CHANGE = 0.20       # 장면 변화(before/after)
W_SHARP = 0.20        # 선명도
W_SPECIAL = 0.10      # 시각적 특이성(피부/손동작 등)


def _hook_score(m: dict) -> float:
    special = min(1.0, m.get("skin", 0.0) * 3 + (0.3 if "hand_action" in m.get("tags", []) else 0))
    score = (
        W_PRODUCT * min(1.0, m.get("product_exposure", 0.0) * 4)
        + W_MOTION * m.get("motion_score", 0.0)
        + W_CHANGE * m.get("ba_change", 0.0)
        + W_SHARP * m.get("sharpness_score", 0.0)
        + W_SPECIAL * special
    )
    return round(min(1.0, score), 4)


def _quality_score(m: dict) -> float:
    """종합 화질 점수: 밝기 + 선명도 위주."""
    return round(
        0.5 * m.get("sharpness_score", 0.0) + 0.5 * m.get("brightness_score", 0.0), 4
    )


def analyze_video(video_path: str, *, source_label: str = "",
                  clip_id_offset: int = 0,
                  min_dur: float = 0.6, max_dur: float = 8.0,
                  progress_cb=None) -> list[Clip]:
    """영상 하나를 컷 분할 + 지표 계산하여 Clip 리스트로 반환한다."""
    scenes = split_scenes(video_path)
    label = source_label or video_path
    clips: list[Clip] = []
    total = len(scenes) or 1
    idx = clip_id_offset
    for i, (start, end) in enumerate(scenes):
        dur = end - start
        if dur < min_dur:
            continue
        if dur > max_dur:
            end = start + max_dur
            dur = max_dur
        m = analyze_clip_metrics(video_path, start, end)
        idx += 1
        clips.append(Clip(
            clip_id=f"clip_{idx:03d}",
            source_video=label,
            start=round(start, 3),
            end=round(end, 3),
            duration=round(dur, 3),
            tags=m["tags"],
            quality_score=_quality_score(m),
            brightness_score=m["brightness_score"],
            motion_score=m["motion_score"],
            blur_score=m["blur_score"],
            hook_score=_hook_score(m),
            description=m["description"],
        ))
        if progress_cb:
            progress_cb(int((i + 1) / total * 100))
    return clips


def score_clips(clips: list[Clip]) -> list[Clip]:
    """hook_score 내림차순 정렬."""
    return sorted(clips, key=lambda c: c.hook_score, reverse=True)
