"""ASS/SRT 자막 생성.

요구사항: 2줄 이하, 하단 중앙, 외곽선+반투명 박스, scene별 caption_text,
타임라인 기준 시작/종료, 하드자막 렌더용.
9:16(1080x1920) 기준 스타일.
"""

from __future__ import annotations

# 9:16 세로 해상도
PLAY_W = 1080
PLAY_H = 1920

_ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_W}
PlayResY: {PLAY_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK KR,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,3,3,2,2,60,60,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


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


def build_ass(segments: list[dict], out_path: str) -> str:
    """segments: [{start, end, text}] → ASS 파일 작성. 경로 반환.

    text 는 caption_text.
    """
    lines = [_ASS_HEADER]
    for seg in segments:
        text = _wrap_two_lines(str(seg.get("text", "")))
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
