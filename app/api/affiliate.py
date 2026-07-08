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


class NaverConnectRequest(BaseModel):
    query: str  # 센터 상품 검색어(상품명) 또는 스마트스토어 상품 URL


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


@router.get("/affiliate-links/naver-session")
def naver_session_status(product_id: str, db: Session = Depends(get_session)):
    """네이버 로그인 세션(naver_login.py 로 저장) 존재 여부."""
    _require(db, product_id)
    from engine.ingest.naver_connect import has_session

    return {"has_session": has_session()}


@router.post("/affiliate-links/naver-connect")
def create_naver_connect_link(
    product_id: str, payload: NaverConnectRequest, db: Session = Depends(get_session)
):
    """쇼핑커넥트 센터에서 링크 발급을 자동 시도한다 (반자동 — 세션 필요).

    실패 시 메시지와 함께 400/502 — 센터에서 수동 발급 후 붙여넣기로 폴백.
    """
    product = _require(db, product_id)
    from engine.ingest.naver_connect import NaverConnectError, create_connect_link, has_session

    if not has_session():
        raise HTTPException(
            status_code=400,
            detail="네이버 로그인 세션이 없습니다. 로컬에서 `python naver_login.py` 를 "
                   "실행해 로그인한 뒤 다시 시도하세요.",
        )
    try:
        link = create_connect_link(payload.query)
    except NaverConnectError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — Playwright 미설치/브라우저 문제 등
        raise HTTPException(status_code=502, detail=f"쇼핑커넥트 발급 실패: {exc}") from exc

    slug = slugify(product.product_ko)
    row = db.query(AffiliateLink).filter(
        AffiliateLink.project_id == product_id,
        AffiliateLink.provider == "naver_shopping_connect",
    ).first()
    if row is None:
        row = AffiliateLink(project_id=product_id, provider="naver_shopping_connect")
        db.add(row)
    row.raw_url = link
    row.product_slug = slug
    db.commit()
    return {"provider": "naver_shopping_connect", "raw_url": link}
