"""품질 지표 계산 — OpenCV 로 컷 구간의 프레임을 샘플링해 지표를 산출한다.

지표(모두 0~1 정규화):
  brightness_score : 평균 밝기 (너무 어둡/밝지 않은 중간값이 높음)
  sharpness_score  : Laplacian 분산 (선명도)
  motion_score     : 연속 샘플 프레임 간 차이(움직임)
  blur_score       : 흐림 정도 (1 - sharpness)
휴리스틱 태그: product_visible / hand_action / before_after (근사).
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _sample_frames(video_path: str, start: float, end: float, n: int = 6) -> list[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames: list[np.ndarray] = []
    if end <= start:
        end = start + 0.5
    times = np.linspace(start, max(start, end - 0.05), n)
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append(frame)
    cap.release()
    return frames


def _brightness(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()) / 255.0


def _sharpness(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    var = cv2.Laplacian(gray, cv2.CV_64F).var()
    # 경험적 정규화: 분산 1000 정도면 선명
    return float(min(1.0, var / 1000.0))


def _skin_ratio(frame: np.ndarray) -> float:
    """피부색 픽셀 비율 (손동작/사용 장면 추정용, 매우 근사)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 30, 60], dtype=np.uint8)
    upper = np.array([25, 160, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    return float(mask.mean()) / 255.0


def _center_edge_density(frame: np.ndarray) -> float:
    """중앙 영역 엣지 밀도 (제품 노출 추정용)."""
    h, w = frame.shape[:2]
    cy, cx = h // 2, w // 2
    crop = frame[cy - h // 4: cy + h // 4, cx - w // 4: cx + w // 4]
    if crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    return float(edges.mean()) / 255.0


def analyze_clip_metrics(video_path: str, start: float, end: float) -> dict:
    """단일 컷 구간의 지표와 태그를 계산한다."""
    frames = _sample_frames(video_path, start, end)
    if not frames:
        return {
            "brightness_score": 0.0, "sharpness_score": 0.0,
            "motion_score": 0.0, "blur_score": 1.0,
            "product_exposure": 0.0, "skin": 0.0,
            "tags": [], "description": "프레임 추출 실패",
        }

    brightness = float(np.mean([_brightness(f) for f in frames]))
    sharpness = float(np.mean([_sharpness(f) for f in frames]))
    product_exposure = float(np.mean([_center_edge_density(f) for f in frames]))
    skin = float(np.mean([_skin_ratio(f) for f in frames]))

    # 움직임: 연속 샘플 그레이 프레임 절대차 평균
    grays = [cv2.cvtColor(cv2.resize(f, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
             for f in frames]
    diffs = [np.abs(grays[i] - grays[i - 1]).mean() for i in range(1, len(grays))]
    motion = float(min(1.0, (np.mean(diffs) / 40.0) if diffs else 0.0))

    # before/after 근사: 첫 절반과 뒷 절반의 평균 밝기/구조 차이
    half = len(grays) // 2 or 1
    before = np.mean([g.mean() for g in grays[:half]])
    after = np.mean([g.mean() for g in grays[half:]]) if grays[half:] else before
    ba_change = min(1.0, abs(after - before) / 40.0)

    # --- 밝기 점수: 중간(0.5) 근처가 최고 ---
    brightness_score = 1.0 - min(1.0, abs(brightness - 0.5) * 2)
    blur_score = 1.0 - sharpness

    tags: list[str] = []
    if product_exposure > 0.08:
        tags.append("product_visible")
    if skin > 0.05 and motion > 0.15:
        tags.append("hand_action")
    if ba_change > 0.4:
        tags.append("before_after")
    if motion > 0.4:
        tags.append("high_motion")

    return {
        "brightness_score": round(brightness_score, 4),
        "sharpness_score": round(sharpness, 4),
        "motion_score": round(motion, 4),
        "blur_score": round(blur_score, 4),
        "product_exposure": round(product_exposure, 4),
        "skin": round(skin, 4),
        "ba_change": round(ba_change, 4),
        "tags": tags,
        "description": _describe(tags),
    }


def _describe(tags: list[str]) -> str:
    parts = []
    if "product_visible" in tags:
        parts.append("제품이 화면 중앙에 노출됨")
    if "hand_action" in tags:
        parts.append("손으로 사용/조작하는 장면")
    if "before_after" in tags:
        parts.append("정리 전후 변화가 보임")
    if "high_motion" in tags:
        parts.append("움직임이 큼")
    return ", ".join(parts) or "일반 장면"
