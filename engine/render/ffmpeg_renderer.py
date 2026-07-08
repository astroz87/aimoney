"""ffmpeg 렌더러 — scene 별 컷+TTS 를 합성하고 자막을 번인해 9:16 영상을 만든다.

파이프라인:
 1) scene 별 정규화 클립 생성 (1080x1920, 30fps, h264+aac, 길이=TTS duration)
    - 컷이 TTS 보다 짧으면 마지막 프레임을 clone 하여 채운다(tpad).
    - 오디오가 없으면 무음으로 채운다.
 2) concat demuxer 로 결합
 3) ASS 자막 하드번인 (+ 선택 BGM 믹스)
중간 산출물은 work_dir 에, 최종만 out_path.
"""

from __future__ import annotations

import logging
from pathlib import Path

from engine.media_utils import ffmpeg_bin, has_ffmpeg, probe_duration, run_ffmpeg

logger = logging.getLogger(__name__)

W, H, FPS = 1080, 1920, 30


class RenderError(RuntimeError):
    pass


def _scene_clip(spec: dict, out: Path) -> Path:
    """단일 scene 정규화 클립 생성."""
    video_path = spec.get("video_path")
    v_start = float(spec.get("v_start", 0.0))
    v_end = float(spec.get("v_end", 0.0))
    audio_path = spec.get("audio_path")
    dur = float(spec.get("duration", 3.0)) or 3.0
    seg = max(0.1, v_end - v_start)
    pad = max(0.0, dur - seg) + 0.5

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS},"
        f"tpad=stop_mode=clone:stop_duration={pad:.2f}"
    )

    args: list[str] = []
    if video_path and Path(video_path).exists():
        args += ["-ss", f"{v_start:.3f}", "-t", f"{seg:.3f}", "-i", str(video_path)]
        v_label = "0:v"
    else:
        # 소스 없음 → 단색 배경
        args += ["-f", "lavfi", "-t", f"{dur:.3f}",
                 "-i", f"color=c=0x202430:s={W}x{H}:r={FPS}"]
        v_label = "0:v"

    has_audio = bool(audio_path) and Path(audio_path).exists() and Path(audio_path).stat().st_size > 0
    if has_audio:
        args += ["-i", str(audio_path)]
        a_map = "1:a"
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        a_map = f"{1 if video_path and Path(video_path).exists() else 1}:a"

    filt = f"[{v_label}]{vf}[v]"
    cmd = [
        *args,
        "-filter_complex", filt,
        "-map", "[v]", "-map", a_map,
        "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-r", str(FPS), "-vsync", "cfr",
        str(out),
    ]
    proc = run_ffmpeg(cmd, timeout=300)
    if proc.returncode != 0 or not out.exists():
        raise RenderError(f"scene 클립 실패: {proc.stderr[-500:]}")
    return out


def render_video(scene_specs: list[dict], subtitle_path: str | None,
                 out_path: str, work_dir: str, *, bgm_path: str | None = None,
                 progress_cb=None) -> dict:
    """전체 렌더링을 수행하고 {'video_path','duration'} 반환."""
    if not has_ffmpeg():
        raise RenderError("ffmpeg 가 설치되어 있지 않습니다")
    if not scene_specs:
        raise RenderError("렌더할 scene 이 없습니다")

    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1) scene 별 클립
    clip_paths: list[Path] = []
    n = len(scene_specs)
    for i, spec in enumerate(scene_specs):
        cp = _scene_clip(spec, work / f"scene_{i+1:03d}.mp4")
        clip_paths.append(cp)
        if progress_cb:
            progress_cb(int((i + 1) / n * 60))

    # 2) concat
    concat_list = work / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{cp.resolve()}'\n" for cp in clip_paths), encoding="utf-8"
    )
    combined = work / "combined.mp4"
    proc = run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(combined),
    ], timeout=300)
    if proc.returncode != 0 or not combined.exists():
        # copy 실패 시 재인코딩 폴백
        proc = run_ffmpeg([
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(combined),
        ], timeout=600)
        if proc.returncode != 0 or not combined.exists():
            raise RenderError(f"concat 실패: {proc.stderr[-500:]}")
    if progress_cb:
        progress_cb(75)

    # 3) 자막 번인 (+ BGM)
    src = combined
    filters = []
    if subtitle_path and Path(subtitle_path).exists():
        # ass 필터: 경로 이스케이프
        esc = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
        filters.append(f"ass='{esc}'")

    final_args = ["-i", str(src)]
    if bgm_path and Path(bgm_path).exists():
        final_args += ["-stream_loop", "-1", "-i", str(bgm_path)]

    if filters:
        vf = ",".join(filters)
        final_args += ["-vf", vf]
    if bgm_path and Path(bgm_path).exists():
        # 원본 오디오 + BGM(-18dB) 믹스
        final_args += [
            "-filter_complex", "[1:a]volume=0.18[bg];[0:a][bg]amix=inputs=2:duration=first[a]",
            "-map", "0:v", "-map", "[a]",
        ]
        # -vf 와 filter_complex 동시 사용 불가 → 자막은 filter_complex 로 이동
        if filters:
            final_args = ["-i", str(src), "-stream_loop", "-1", "-i", str(bgm_path),
                          "-filter_complex",
                          f"[0:v]{','.join(filters)}[v];"
                          "[1:a]volume=0.18[bg];[0:a][bg]amix=inputs=2:duration=first[a]",
                          "-map", "[v]", "-map", "[a]"]
    final_args += [
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", str(out),
    ]
    proc = run_ffmpeg(final_args, timeout=900)
    if proc.returncode != 0 or not out.exists():
        raise RenderError(f"자막/최종 렌더 실패: {proc.stderr[-500:]}")
    if progress_cb:
        progress_cb(100)

    return {"video_path": str(out), "duration": round(probe_duration(str(out)), 2)}
