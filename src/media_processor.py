"""MediaProcessor — 영상 프레임 추출 및 썸네일 이미지 가공 담당.

OpenCV 로 영상에서 대표 프레임을 추출하고, Pillow 로 썸네일을 가공한다.
(리사이즈, 정사각형 크롭 등 스레드 업로드에 적합한 형태로 정규화)

OpenCV 작업은 CPU 바운드이므로 `asyncio.to_thread` 로 별도 스레드에서 실행해
이벤트 루프를 막지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import cv2
from PIL import Image, ImageOps

from config import Settings
from .models import ScrapedPost

logger = logging.getLogger(__name__)


class MediaProcessor:
    """미디어(영상/이미지) 가공기."""

    def __init__(self, settings: Settings, thumb_size: int = 1080) -> None:
        self._settings = settings
        self._thumb_size = thumb_size
        self._out_dir = settings.work_dir / "processed"
        self._out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    async def process_post(self, post: ScrapedPost) -> list[Path]:
        """게시글의 미디어를 가공하여 발행용 이미지 경로 목록을 반환한다.

        - 영상: 대표 프레임을 뽑아 썸네일로 변환
        - 이미지: 정사각형 정규화 썸네일로 변환
        """
        results: list[Path] = []

        # 영상 → 프레임 추출 → 썸네일
        for video in post.video_paths:
            frame = await self.extract_keyframe(video)
            if frame:
                thumb = await self.make_thumbnail(frame)
                if thumb:
                    results.append(thumb)

        # 이미지 → 썸네일
        for image in post.image_paths:
            thumb = await self.make_thumbnail(image)
            if thumb:
                results.append(thumb)

        logger.info("미디어 가공 완료: %d개 산출", len(results))
        return results

    async def extract_keyframe(self, video_path: Path, position: float = 0.3) -> Path | None:
        """영상에서 대표 프레임 한 장을 추출한다.

        Args:
            video_path: 입력 영상 경로
            position: 0.0~1.0, 영상 길이 기준 추출 지점 (기본 30% 지점)
        """
        return await asyncio.to_thread(self._extract_keyframe_sync, video_path, position)

    def _extract_keyframe_sync(self, video_path: Path, position: float) -> Path | None:
        cap = cv2.VideoCapture(str(video_path))
        try:
            if not cap.isOpened():
                logger.warning("영상을 열 수 없습니다: %s", video_path)
                return None
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            target_frame = max(0, int(total * position)) if total > 0 else 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ok, frame = cap.read()
            if not ok or frame is None:
                # 폴백: 첫 프레임
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
                if not ok or frame is None:
                    logger.warning("프레임을 읽을 수 없습니다: %s", video_path)
                    return None
            out_path = self._out_dir / f"{video_path.stem}_frame.jpg"
            cv2.imwrite(str(out_path), frame)
            logger.debug("키프레임 추출: %s (frame %d/%d)", out_path, target_frame, total)
            return out_path
        finally:
            cap.release()

    async def make_thumbnail(self, image_path: Path) -> Path | None:
        """이미지를 정사각형으로 크롭·리사이즈한 썸네일로 변환한다."""
        return await asyncio.to_thread(self._make_thumbnail_sync, image_path)

    def _make_thumbnail_sync(self, image_path: Path) -> Path | None:
        try:
            with Image.open(image_path) as im:
                im = im.convert("RGB")
                # EXIF 회전 보정
                im = ImageOps.exif_transpose(im)
                # 중앙 정사각형 크롭 후 리사이즈
                size = (self._thumb_size, self._thumb_size)
                thumb = ImageOps.fit(im, size, method=Image.LANCZOS)
                out_path = self._out_dir / f"{image_path.stem}_thumb.jpg"
                thumb.save(out_path, format="JPEG", quality=90)
            logger.debug("썸네일 생성: %s", out_path)
            return out_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("썸네일 생성 실패(%s): %s", image_path, exc)
            return None
