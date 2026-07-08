"""어필리에이트 링크 관리 API — 프로바이더별 원본 URL 등록 및 쿠팡 딥링크 발급.

GET  /api/projects/{id}/affiliate-links
PUT  /api/projects/{id}/affiliate-links
POST /api/projects/{id}/affiliate-links/coupang-deeplink
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from engine.models import slugify
from engine.package import coupang_api
from engine.package.affiliate import PROVIDER_LABELS, providers_for_category
from app.db.database import get_session
from app.db.models_orm import AffiliateLink, Project
from app.services import settings_store

router = APIRouter(prefix="/api/projects/{product_id}", tags=["affiliate"])


def _require(db: Session, product_id: str) -> Project:
    p = db.get(Project, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return p


class AffiliateLinkIn(BaseModel):
    provider: str
    raw_url: str = ""


class AffiliateLinksUpdate(BaseModel):
    links: list[AffiliateLinkIn] = Field(default_factory=list)


class CoupangDeeplinkRequest(BaseModel):
    url: str


def _serialize(db: Session, product: Project) -> dict:
    """카테고리 우선순위 프로바이더 + DB 저장 링크를 병합해 응답을 만든다."""
    slug = slugify(product.product_ko)
    base = settings_store.get("link_router_base").rstrip("/")
    rows = {
        row.provider: row
        for row in db.query(AffiliateLink).filter(
            AffiliateLink.project_id == product.id
        ).all()
    }
    providers = list(providers_for_category(product.category))
    # DB 에는 있지만 카테고리 우선순위 목록에 없는 프로바이더도 노출
    for provider in rows:
        if provider not in providers:
            providers.append(provider)

    links = []
    for provider in providers:
        row = rows.get(provider)
        links.append({
            "provider": provider,
            "label": PROVIDER_LABELS.get(provider, provider),
            "raw_url": row.raw_url if row else "",
            "tracking_url": f"{base}/{slug}",
        })
    return {"slug": slug, "links": links}


@router.get("/affiliate-links")
def get_affiliate_links(product_id: str, db: Session = Depends(get_session)):
    product = _require(db, product_id)
    return _serialize(db, product)


@router.put("/affiliate-links")
def update_affiliate_links(
    product_id: str, payload: AffiliateLinksUpdate, db: Session = Depends(get_session)
):
    product = _require(db, product_id)
    slug = slugify(product.product_ko)
    for link in payload.links:
        row = db.query(AffiliateLink).filter(
            AffiliateLink.project_id == product_id,
            AffiliateLink.provider == link.provider,
        ).first()
        if row is None:
            row = AffiliateLink(project_id=product_id, provider=link.provider)
            db.add(row)
        row.raw_url = link.raw_url
        row.product_slug = slug
    db.commit()
    return _serialize(db, product)


@router.post("/affiliate-links/coupang-deeplink")
def create_coupang_deeplink(
    product_id: str, payload: CoupangDeeplinkRequest, db: Session = Depends(get_session)
):
    product = _require(db, product_id)
    access_key = settings_store.get("coupang_access_key")
    secret_key = settings_store.get("coupang_secret_key")
    if not access_key or not secret_key:
        raise HTTPException(
            status_code=400,
            detail="쿠팡 파트너스 API 키가 없습니다. 설정에서 입력하세요.",
        )
    try:
        deeplink = coupang_api.create_deeplink(access_key, secret_key, payload.url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    slug = slugify(product.product_ko)
    row = db.query(AffiliateLink).filter(
        AffiliateLink.project_id == product_id,
        AffiliateLink.provider == "coupang",
    ).first()
    if row is None:
        row = AffiliateLink(project_id=product_id, provider="coupang")
        db.add(row)
    row.raw_url = deeplink
    row.product_slug = slug
    db.commit()
    return {"provider": "coupang", "raw_url": deeplink}
