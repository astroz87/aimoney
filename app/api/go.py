"""트래킹 링크 라우터 + 클릭 성과 집계.

GET /go/{slug}            — 카테고리 우선순위에 따라 어필리에이트 링크로 302 리다이렉트
GET /api/stats/clicks     — slug×platform 클릭 집계
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from engine.package.affiliate import providers_for_category
from app.db.database import get_session
from app.db.models_orm import AffiliateLink, ClickEvent, Project

router = APIRouter(tags=["go"])


def _pick_link(rows: list, priority: list[str]):
    """우선순위 순으로 raw_url 이 있는 첫 링크. 우선순위 밖 프로바이더는 뒤로."""
    if not rows:
        return None

    def _rank(row) -> int:
        try:
            return priority.index(row.provider)
        except ValueError:
            return len(priority)  # 우선순위 밖 → 뒤로

    return sorted(rows, key=_rank)[0]


@router.get("/go/{slug}")
def go(slug: str, src: str = "", db: Session = Depends(get_session)):
    rows = db.query(AffiliateLink).filter(
        AffiliateLink.product_slug == slug, AffiliateLink.raw_url != ""
    ).all()

    priority: list[str] = []
    if rows:
        project = db.get(Project, rows[0].project_id)
        priority = providers_for_category(project.category if project else "")

    picked = _pick_link(rows, priority)

    if picked is not None:
        db.add(ClickEvent(
            slug=slug, platform=src, provider=picked.provider, target_url=picked.raw_url,
        ))
        db.commit()
        return RedirectResponse(picked.raw_url, status_code=302)

    db.add(ClickEvent(slug=slug, platform=src, provider="", target_url=""))
    db.commit()
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;text-align:center;padding:60px;'>"
        f"<h2>{slug}</h2><p>구매 링크 준비 중입니다.</p></body></html>",
        status_code=200,
    )


@router.get("/api/stats/clicks")
def click_stats(slug: str = "", db: Session = Depends(get_session)):
    q = db.query(
        ClickEvent.slug,
        ClickEvent.platform,
        func.count(ClickEvent.id).label("clicks"),
        func.max(ClickEvent.created_at).label("last_click"),
    ).group_by(ClickEvent.slug, ClickEvent.platform)
    if slug:
        q = q.filter(ClickEvent.slug == slug)
    rows = q.all()
    return [
        {"slug": r.slug, "platform": r.platform, "clicks": r.clicks, "last_click": r.last_click}
        for r in rows
    ]
