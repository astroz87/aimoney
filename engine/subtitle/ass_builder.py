"""ASS/SRT 자막 생성.

요구사항: 2줄 이하, 하단 중앙, 외곽선+반투명 박스, scene별 caption_text,
타임라인 기준 시작/종료, 하드자막 렌더용.
9:16(1080x1920) 기준 스타일.
"""

from __future__ import annotations

import sys

# 9:16 세로 해상도
PLAY_W = 1080
PLAY_H = 1920

# 플랫폼별 한국어 기본 폰트.
# fonts/ 폴더에 .ttf/.otf 를 두면 렌더러가 fontsdir 로 우선 사용한다(fonts/README.md 참고).
DEFAULT_FONT = "Malgun Gothic" if sys.platform.startswith("win") else "Noto Sans CJK KR"

# 기본 자막 스타일 (템플릿에서 오버라이드 가능)
DEFAULT_SUBTITLE_STYLE = {
    "font": DEFAULT_FONT,
    "size": 64,
    "primary": "&H00FFFFFF",      # 글자색 (ASS BGR, 흰색)
    "outline_color": "&H00000000",  # 외곽선색 (검정)
    "box_color": "&H80000000",    # 박스 배경(반투명 검정)
    "bold": 1,
    "border_style": 3,            # 1=외곽선, 3=박스
    "outline": 3,
    "shadow": 2,
    "alignment": 2,               # 2=하단중앙, 5=상단중앙, 8=중앙
    "margin_v": 220,
    "wrap_max": 16,               # 2줄 줄바꿈 기준 글자수
}


# 상단 제목(persistent) 기본 스타일 (레퍼런스 템플릿의 상단 헤드라인)
DEFAULT_TITLE_STYLE = {
    "font": DEFAULT_FONT,
    "size": 78,
    "primary": "&H0000FFFF",      # 노란색
    "outline_color": "&H00000000",
    "box_color": "&HFF000000",    # 박스 없음
    "bold": 1,
    "border_style": 1,
    "outline": 4,
    "shadow": 2,
    "alignment": 8,               # 상단 중앙
    "margin_v": 120,
    "wrap_max": 16,
}


def _style_line(name: str, style: dict, defaults: dict) -> str:
    s = {**defaults, **(style or {})}
    return (
        f"Style: {name},{s['font']},{s['size']},{s['primary']},&H000000FF,"
        f"{s['outline_color']},{s['box_color']},{s['bold']},0,0,0,100,100,0,0,"
        f"{s['border_style']},{s['outline']},{s['shadow']},{s['alignment']},60,60,{s['margin_v']},1"
    )


def _header(style: dict, title_style: dict | None = None) -> str:
    style_lines = _style_line("Caption", style, DEFAULT_SUBTITLE_STYLE)
    if title_style is not None:
        style_lines += "\n" + _style_line("Title", title_style, DEFAULT_TITLE_STYLE)
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {PLAY_W}\n"
        f"PlayResY: {PLAY_H}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{style_lines}\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _ts(seconds: float) -> str:
    """초 → ASS 타임스탬프 h:mm:ss.cs"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        cs = 0
        s += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _wrap_two_lines(text: str, max_chars: int = 16) -> str:
    """긴 캡션을 2줄 이하로 줄바꿈(ASS \\N)."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    words = text.split(" ")
    if len(words) > 1:
        line1, line2, cur = [], [], 0
        mid = len(text) / 2
        acc = 0
        for w in words:
            if acc < mid:
                line1.append(w)
            else:
                line2.append(w)
            acc += len(w) + 1
        return " ".join(line1) + "\\N" + " ".join(line2)
    # 공백 없는 긴 문자열: 중간에서 자름
    mid = len(text) // 2
    return text[:mid] + "\\N" + text[mid:]


def build_ass(segments: list[dict], out_path: str, *, style: dict | None = None,
              title: str = "", title_style: dict | None = None,
              total_end: float | None = None) -> str:
    """segments: [{start, end, text}] → ASS 파일 작성. 경로 반환.

    text 는 caption_text. style 로 하단 자막 스타일을 오버라이드(템플릿).
    title 이 있으면 상단에 영상 전체 길이 동안 고정 표시(레퍼런스 템플릿의 상단 제목).
    """
    style = {**DEFAULT_SUBTITLE_STYLE, **(style or {})}
    wrap_max = int(style.get("wrap_max", 16))
    show_title = bool(title) and title_style is not None
    lines = [_header(style, title_style if show_title else None)]

    # 상단 제목 (persistent) — 0 ~ 전체 길이
    if show_title:
        end = total_end
        if end is None:
            end = max((s.get("end", 0) for s in segments), default=3.0)
        t_wrap = int((title_style or {}).get("wrap_max", 16))
        ttext = _wrap_two_lines(str(title), max_chars=t_wrap).replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{_ts(0.0)},{_ts(end)},Title,,0,0,0,,{ttext}")

    for seg in segments:
        text = _wrap_two_lines(str(seg.get("text", "")), max_chars=wrap_max)
        text = text.replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{_ts(seg['start'])},{_ts(seg['end'])},Caption,,0,0,0,,{text}"
        )
    content = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def _srt_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments: list[dict], out_path: str) -> str:
    """SRT 보조 자막 생성."""
    blocks = []
    for i, seg in enumerate(segments, 1):
        blocks.append(
            f"{i}\n{_srt_ts(seg['start'])} --> {_srt_ts(seg['end'])}\n{seg.get('text','')}\n"
        )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocks))
    return out_path
