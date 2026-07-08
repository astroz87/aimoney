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


def _hex_to_ff(color: str) -> str:
    """'#RRGGBB' → ffmpeg color 'RRGGBB'. 잘못된 값은 기본색."""
    c = (color or "").lstrip("#")
    if len(c) in (6, 8) and all(ch in "0123456789abcdefABCDEF" for ch in c):
        return f"0x{c}"
    return "0x202430"


def _even(n: float) -> int:
    """짝수로 내림 (libx264 요구)."""
    v = int(n)
    return v - (v % 2)


def _scene_clip(spec: dict, out: Path, *, bg_color: str = "#202430",
                transition: str = "none", transition_duration: float = 0.3,
                fit_mode: str = "cover", box_scale: float = 0.94,
                box_h: float = 0.60, box_y: float = 0.34) -> Path:
    """단일 scene 정규화 클립 생성 (배경색/전환/효과음/맞춤모드 지원).

    fit_mode: cover=꽉 채우기(크롭), contain=박스형(배경색 여백에 제목·자막 공간).
    """
    video_path = spec.get("video_path")
    v_start = float(spec.get("v_start", 0.0))
    v_end = float(spec.get("v_end", 0.0))
    audio_path = spec.get("audio_path")
    sfx_path = spec.get("sfx_path")
    dur = float(spec.get("duration", 3.0)) or 3.0
    seg = max(0.1, v_end - v_start)
    pad = max(0.0, dur - seg) + 0.5

    inputs: list[str] = []
    if video_path and Path(video_path).exists():
        inputs += ["-ss", f"{v_start:.3f}", "-t", f"{seg:.3f}", "-i", str(video_path)]
    else:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}",
                   "-i", f"color=c={_hex_to_ff(bg_color)}:s={W}x{H}:r={FPS}"]
    idx = 1

    has_audio = bool(audio_path) and Path(audio_path).exists() and Path(audio_path).stat().st_size > 0
    if has_audio:
        inputs += ["-i", str(audio_path)]
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    tts_idx = idx
    idx += 1

    has_sfx = bool(sfx_path) and Path(sfx_path or "").exists() and Path(sfx_path).stat().st_size > 0
    if has_sfx:
        inputs += ["-i", str(sfx_path)]
        sfx_idx = idx
        idx += 1

    # 비디오 필터: 맞춤 모드 → 정규화 + (옵션) 페이드 전환
    ffcolor = _hex_to_ff(bg_color)
    if fit_mode == "contain":
        # 박스형: box_scale×box_h 영역에 맞춰 축소 후 배경색 여백에 배치.
        # box_y 로 세로 위치 조절(상단으로 올리면 하단 자막 공간 확보).
        tw = max(2, _even(W * min(1.0, max(0.3, box_scale))))
        th = max(2, _even(H * min(0.95, max(0.3, box_h))))
        by = min(1.0, max(0.0, box_y))
        base = (
            f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)*{by:.3f}:color={ffcolor}"
        )
    else:
        base = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}"
        )
    vf = f"{base},setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration={pad:.2f}"
    if transition == "fade" and transition_duration > 0:
        d = min(transition_duration, dur / 2)
        st = max(0.0, dur - d)
        vf += f",fade=t=in:st=0:d={d:.2f},fade=t=out:st={st:.2f}:d={d:.2f}"

    fc = f"[0:v]{vf}[v]"
    if has_sfx:
        fc += (
            f";[{tts_idx}:a]aresample=44100[tts]"
            f";[{sfx_idx}:a]volume=0.6,aresample=44100[sfx]"
            f";[tts][sfx]amix=inputs=2:duration=first:normalize=0[a]"
        )
        a_map = "[a]"
    else:
        a_map = f"{tts_idx}:a"

    cmd = [
        *inputs,
        "-filter_complex", fc,
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
                 opts: dict | None = None, progress_cb=None) -> dict:
    """전체 렌더링을 수행하고 {'video_path','duration'} 반환.

    opts: bg_color, transition, transition_duration, bgm_volume, bgm_enabled
    """
    if not has_ffmpeg():
        raise RenderError("ffmpeg 가 설치되어 있지 않습니다")
    if not scene_specs:
        raise RenderError("렌더할 scene 이 없습니다")

    opts = opts or {}
    bg_color = opts.get("bg_color", "#202430")
    transition = opts.get("transition", "none")
    transition_duration = float(opts.get("transition_duration", 0.3) or 0.3)
    bgm_volume = float(opts.get("bgm_volume", 0.18) or 0.18)
    bgm_enabled = opts.get("bgm_enabled", True)
    fit_mode = opts.get("fit_mode", "cover")
    box_scale = float(opts.get("box_scale", 0.94) or 0.94)
    box_h = float(opts.get("box_h", 0.60) or 0.60)
    box_y = float(opts.get("box_y", 0.34))

    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1) scene 별 클립
    clip_paths: list[Path] = []
    n = len(scene_specs)
    for i, spec in enumerate(scene_specs):
        cp = _scene_clip(spec, work / f"scene_{i+1:03d}.mp4",
                         bg_color=bg_color, transition=transition,
                         transition_duration=transition_duration, fit_mode=fit_mode,
                         box_scale=box_scale, box_h=box_h, box_y=box_y)
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

    use_bgm = bool(bgm_enabled) and bool(bgm_path) and Path(bgm_path or "").exists()

    final_args = ["-i", str(src)]
    if use_bgm:
        final_args += ["-stream_loop", "-1", "-i", str(bgm_path)]

    if not use_bgm:
        if filters:
            final_args += ["-vf", ",".join(filters)]
    else:
        # 원본 오디오 + BGM 믹스 (자막은 filter_complex 로 함께 처리)
        vchain = f"[0:v]{','.join(filters)}[v]" if filters else "[0:v]copy[v]"
        final_args += [
            "-filter_complex",
            f"{vchain};[1:a]volume={bgm_volume:.2f}[bg];"
            "[0:a][bg]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "[v]", "-map", "[a]",
        ]
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
