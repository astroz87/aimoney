"""썸네일 — 후킹 점수 1위 컷의 대표 프레임을 추출하고, 선택적으로 문구를 합성한다.

MVP: 프레임 추출 + (있으면) Pillow 텍스트 오버레이. 문구 없어도 허용.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

W, H = 1080, 1920


def make_thumbnail(video_path: str, out_path: str, *, at_sec: float = 0.0,
                   text: str = "") -> str:
    """video_path 의 at_sec 프레임을 추출해 out_path(jpg) 로 저장한다."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    frame = _extract_frame(video_path, at_sec)
    if frame is None:
        _placeholder(out, text)
        return str(out)

    try:
        from PIL import Image
        import cv2
        import numpy as np

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        img = _cover_resize(img, W, H)
        if text:
            img = _overlay_text(img, text)
        img.save(out, quality=90)
    except Exception as exc:  # noqa: BLE001
        logger.warning("썸네일 합성 실패(%s) → 원본 프레임 저장", exc)
        import cv2
        cv2.imwrite(str(out), frame)
    return str(out)


def _extract_frame(video_path: str, at_sec: float):
    try:
        import cv2
    except ImportError:
        return None
    if not video_path or not Path(video_path).exists():
        return None
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(max(0.0, at_sec) * fps))
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _cover_resize(img, w, h):
    from PIL import Image
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        new_h = h
        new_w = int(h * src_ratio)
    else:
        new_w = w
        new_h = int(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _overlay_text(img, text: str):
    from PIL import Image, ImageDraw, ImageFont

    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype(_find_font(), 84)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()

    # 하단 반투명 박스 + 텍스트
    text = text[:20]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (img.width - tw) // 2
    y = int(img.height * 0.72)
    draw.rectangle([x - 30, y - 20, x + tw + 30, y + th + 30], fill=(0, 0, 0, 150))
    # 외곽선
    for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return img


def _find_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


def _placeholder(out: Path, text: str) -> None:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (W, H), (32, 36, 48))
        if text:
            img = _overlay_text(img, text)
        img.save(out, quality=90)
    except Exception:  # noqa: BLE001
        out.write_bytes(b"")
