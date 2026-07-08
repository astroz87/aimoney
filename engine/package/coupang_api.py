"""쿠팡 파트너스 Open API — 딥링크(단축 URL) 발급 클라이언트.

문서: https://developers.coupangcorp.com/hc/ko/articles/360033350531 (딥링크 생성)
표준 HMAC 서명 방식을 사용하며, 외부 의존성(requests) 없이 표준 라이브러리
(urllib/hmac/hashlib)만으로 구현한다.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

DOMAIN = "https://api-gateway.coupang.com"
DEEPLINK_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"


def _auth_header(method: str, path: str, query: str, access_key: str, secret_key: str,
                  *, now: datetime | None = None) -> str:
    """쿠팡 Open API 인증 헤더(HMAC-SHA256) 생성."""
    now = now or datetime.now(timezone.utc)
    signed_date = now.strftime("%y%m%dT%H%M%SZ")
    message = signed_date + method + path + query
    signature = hmac.new(
        secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={access_key}, "
        f"signed-date={signed_date}, signature={signature}"
    )


def create_deeplink(access_key: str, secret_key: str, url: str, *, sub_id: str = "") -> str:
    """상품 URL 을 쿠팡 파트너스 딥링크(단축 URL)로 변환한다.

    실패 시 RuntimeError 를 던진다.
    """
    body: dict = {"coupangUrls": [url]}
    if sub_id:
        body["subId"] = sub_id
    payload = json.dumps(body).encode("utf-8")

    auth = _auth_header("POST", DEEPLINK_PATH, "", access_key, secret_key)
    req = urllib.request.Request(
        f"{DOMAIN}{DEEPLINK_PATH}",
        data=payload,
        method="POST",
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # noqa: BLE001
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
        raise RuntimeError(f"쿠팡 딥링크 실패: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"쿠팡 딥링크 실패: {exc}") from exc

    try:
        return data["data"][0]["shortenUrl"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"쿠팡 딥링크 실패: 응답 파싱 오류 ({data})") from exc
