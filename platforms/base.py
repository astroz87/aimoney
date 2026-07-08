"""플랫폼 콘텐츠 생성 공통 헬퍼.

package_builder 는 각 플랫폼 SPEC 의 files 목록을 순회하며 build_field() 로 내용을 만든다.
경제적 이해관계 문구는 본문형 파일(description/caption/post)의 첫 줄에 강제 삽입된다.
"""

from __future__ import annotations

from engine.package.disclosure import prepend_disclosure

# 본문(경제적 이해관계 문구가 들어가야 하는) 파일들
BODY_FILES = {"description.txt", "caption.txt", "post.txt", "pinned_comment.txt"}


def make_title(ctx: dict, max_len: int, suffix: str = "") -> str:
    hook = ctx.get("hook_caption") or ctx.get("product_ko") or "쇼츠"
    title = hook.strip()
    if suffix:
        title = f"{title} {suffix}".strip()
    return title[:max_len]


def _as_tag(raw: str) -> str:
    """해시태그 정규화: 공백/슬래시 제거, '#' 접두어 보장."""
    t = (raw or "").lstrip("#")
    t = t.replace(" ", "").replace("/", "").replace("-", "")
    return f"#{t}" if t else ""


def make_hashtags(ctx: dict, base_tags: list[str], count: int) -> str:
    product = ctx.get("product_ko", "")
    tags = []
    if product:
        tags.append(_as_tag(product))
    cat = ctx.get("category", "")
    if cat:
        tags.append(_as_tag(cat))
    tags += [_as_tag(t) for t in base_tags]
    # 빈 태그 제거, 중복 제거, 개수 제한
    seen, out = set(), []
    for t in tags:
        if t and t != "#" and t not in seen:
            seen.add(t)
            out.append(t)
    return " ".join(out[:count])


def make_body(ctx: dict, *, cta: str, include_disclosure: bool = True) -> str:
    """후킹 → 문제/해결 요약 → CTA → 트래킹 링크. 첫 줄에 경제적 이해관계 문구."""
    scenes = ctx.get("scenes", [])
    hook = ctx.get("hook_caption", "")
    lines: list[str] = []
    if hook:
        lines.append(hook)
    # 본문: 대본에서 voice_text 요약 (hook 제외 problem/solution/proof)
    body_scenes = [s for s in scenes if s.get("role") in ("problem", "solution", "proof")]
    for s in body_scenes[:3]:
        vt = s.get("voice_text", "").strip()
        if vt:
            lines.append(vt)
    if cta:
        lines.append("")
        lines.append(cta)
    tracking = ctx.get("tracking_url", "")
    if tracking:
        lines.append(f"👉 {tracking}")

    body = "\n".join(lines).strip()
    if include_disclosure:
        body = prepend_disclosure(body)
    return body


def build_field(filename: str, ctx: dict, spec: dict) -> str:
    """SPEC 규칙에 따라 파일 내용을 생성한다."""
    if filename == "title.txt":
        return make_title(ctx, spec.get("title_max", 100), spec.get("title_suffix", ""))
    if filename == "hashtags.txt":
        return make_hashtags(ctx, spec.get("hashtags", []), spec.get("hashtag_count", 10))
    if filename in ("description.txt", "caption.txt", "post.txt"):
        return make_body(ctx, cta=spec.get("cta", ""),
                         include_disclosure=True)
    if filename == "pinned_comment.txt":
        # 고정댓글: 링크 + 문구 (첫 줄 경제적 이해관계 포함)
        tracking = ctx.get("tracking_url", "")
        base = f"구매 정보 👇\n{tracking}" if tracking else "구매 정보는 프로필/설명 참고"
        return prepend_disclosure(base)
    return ""
