"""경제적 이해관계 표시 문구 — 모든 플랫폼 본문 첫 줄에 강제 삽입한다."""

from __future__ import annotations

# 공정위 권고 기반 기본 문구
DISCLOSURE_TEXT = (
    "이 콘텐츠는 제휴마케팅 활동으로 제작되었으며, "
    "링크를 통한 구매 실적에 따라 수수료를 지급받습니다."
)


def prepend_disclosure(body: str, *, disclosure: str = DISCLOSURE_TEXT) -> str:
    """본문 첫 줄에 경제적 이해관계 문구를 삽입한다(중복 방지)."""
    body = (body or "").strip()
    if disclosure.strip() and disclosure[:20] in body[:200]:
        return body  # 이미 포함
    if not body:
        return disclosure
    return f"{disclosure}\n\n{body}"
