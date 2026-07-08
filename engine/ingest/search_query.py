"""한국어 상품명 → 중국어 검색어 후보 생성.

LLMProvider 를 주입받아 사용한다(SDK 직접 호출 금지). Mock 프로바이더면 더미 반환.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_SYSTEM = (
    "너는 중국 쇼핑몰(1688/타오바오) 검색 전문가다. 한국어 상품명을 받아 "
    "중국어 상품명 후보와 영상 검색에 쓸 검색어를 생성한다. 반드시 JSON 만 출력한다."
)

_PROMPT_TMPL = (
    "한국어 상품명: {product_ko}\n\n"
    "아래 형식의 JSON 만 출력해라(설명 금지):\n"
    '{{"zh_product_names": ["중국어명1","중국어명2","중국어명3","중국어명4"], '
    '"search_queries": ["검색어1 视频","검색어2 使用视频","검색어3","검색어4"]}}'
)


def generate_search_queries(llm, product_ko: str) -> dict:
    """{'zh_product_names': [...], 'search_queries': [...]} 반환."""
    prompt = _PROMPT_TMPL.format(product_ko=product_ko or "상품")
    try:
        raw = llm.complete(prompt, system=_SYSTEM, max_tokens=500, temperature=0.7)
        data = _parse_json(raw)
        if data and isinstance(data.get("search_queries"), list):
            return {
                "zh_product_names": data.get("zh_product_names", [])[:6],
                "search_queries": data.get("search_queries", [])[:6],
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("검색어 생성 실패(%s) → 폴백", exc)
    # 폴백: 상품명 그대로
    return {"zh_product_names": [product_ko], "search_queries": [product_ko, f"{product_ko} 视频"]}


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
