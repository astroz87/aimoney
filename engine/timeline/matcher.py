"""타임라인 매처 — scene 별 TTS 길이에 맞춰 컷을 선택/배치한다.

로직:
 1. hook 역할에는 hook_score 최고 컷을 우선 배치.
 2. 그 외 scene 은 visual_need ↔ clip.tags/description 유사도로 매칭.
 3. 동일 컷 반복 사용 최소화(사용된 컷에 페널티).
 4. TTS 길이에 맞춰 컷 구간을 자른다(부족하면 컷 전체 사용).
 5. 최종 TimelineItem 리스트(연속 타임라인)를 만든다.
"""

from __future__ import annotations

from engine.models import Clip, Scene, TimelineItem

# visual_need 키워드 → 태그 매핑 (한국어 힌트 → 태그)
_KEYWORD_TAGS = {
    "전후": "before_after", "변화": "before_after", "비교": "before_after",
    "손": "hand_action", "사용": "hand_action", "조작": "hand_action",
    "제품": "product_visible", "클로즈업": "product_visible", "노출": "product_visible",
    "움직": "high_motion",
}


def _need_tags(visual_need: str) -> set[str]:
    tags = set()
    for kw, tag in _KEYWORD_TAGS.items():
        if kw in (visual_need or ""):
            tags.add(tag)
    return tags


def _match_score(scene: Scene, clip: Clip, used: dict[str, int]) -> float:
    need = _need_tags(scene.visual_need)
    overlap = len(need & set(clip.tags))
    score = overlap * 2.0 + clip.quality_score
    if scene.role == "hook":
        score += clip.hook_score * 3.0
    # 중복 사용 페널티
    score -= used.get(clip.clip_id, 0) * 1.5
    return score


def build_timeline(scenes: list[Scene], clips: list[Clip],
                   durations: dict[int, float]) -> list[TimelineItem]:
    """scenes/clips/TTS길이(scene_no→duration)로 타임라인을 만든다."""
    if not clips:
        raise ValueError("사용할 컷이 없습니다")

    used: dict[str, int] = {}
    timeline: list[TimelineItem] = []
    cursor = 0.0

    # hook 우선 처리를 위해 정렬(원래 순서 유지하되 hook 먼저 컷 확보)
    ordered = sorted(scenes, key=lambda s: (s.role != "hook", s.scene))
    assignment: dict[int, Clip] = {}
    for scene in ordered:
        best = max(clips, key=lambda c: _match_score(scene, c, used))
        assignment[scene.scene] = best
        used[best.clip_id] = used.get(best.clip_id, 0) + 1

    # 원래 scene 순서로 타임라인 구성
    for scene in sorted(scenes, key=lambda s: s.scene):
        clip = assignment[scene.scene]
        need = durations.get(scene.scene, scene.target_duration) or scene.target_duration
        avail = max(0.1, clip.end - clip.start)
        seg = min(need, avail)
        # 컷이 TTS 보다 짧으면 컷 전체 사용(렌더 시 마지막 프레임 유지/루프는 렌더러 처리)
        v_start = clip.start
        v_end = clip.start + seg
        timeline.append(TimelineItem(
            scene=scene.scene, clip_id=clip.clip_id,
            video_start=round(v_start, 3), video_end=round(v_end, 3),
            audio_path="",  # 렌더 단계에서 채움
            timeline_start=round(cursor, 3),
            timeline_end=round(cursor + need, 3),
        ))
        cursor += need

    return timeline
