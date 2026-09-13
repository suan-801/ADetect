"""네이버 검색광고(광고주센터) 키워드도구 API — RelKwdStat (PRD §21-10).

DataLab(§7-9 상대 추이)과는 완전히 다른 발급 경로·인증 방식(License Key + Secret Key +
Customer ID, 요청마다 HMAC-SHA256 서명)을 사용합니다. 이 API 하나로 다음 두 가지를 모두
얻을 수 있습니다:
- 연관검색어(relKeyword) — §7-2 interest_keywords / §7-3 brand_related_keywords
- 최근 30일 절대 검색량(monthlyPcQcCnt/monthlyMobileQcCnt) — §7-9 브랜드 검색량 절대치

공식 문서: https://naver.github.io/searchad-apidoc/#/guides
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

import requests

from config import settings

_BASE_URL = "https://api.naver.com"
_URI = "/keywordstool"


class NaverAdApiError(RuntimeError):
    """검색광고 API 호출 실패 — §11 오류 처리 정책상 부분 실패로 처리해야 합니다."""


def _signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _headers(method: str, uri: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    return {
        "X-Timestamp": timestamp,
        "X-API-KEY": settings.NAVER_AD_API_KEY,
        "X-Customer": settings.NAVER_AD_CUSTOMER_ID,
        "X-Signature": _signature(timestamp, method, uri, settings.NAVER_AD_SECRET_KEY),
    }


def _to_int(value) -> int:
    """monthlyPcQcCnt 등은 검색량이 낮으면 숫자 대신 문자열 "< 10"으로 옵니다."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().startswith("<"):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def fetch_keyword_stats(hint_keyword: str) -> list[dict]:
    """RelKwdStat 원본 호출 — 연관키워드 + PC/모바일 월간 검색수.

    반환: [{"keyword": str, "monthly_pc": int, "monthly_mobile": int}, ...]
    hint_keyword 자기 자신이 첫 번째 항목으로 포함되는 경우가 많습니다(정확한 매칭 시).
    """
    if settings.NAVER_AD_MOCK:
        raise RuntimeError("NAVER_AD_MOCK=True — 목업 경로(core/scrapers/naver_api.py)를 사용하세요")

    try:
        resp = requests.get(
            f"{_BASE_URL}{_URI}",
            params={"hintKeywords": hint_keyword, "showDetail": "1"},
            headers=_headers("GET", _URI),
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise NaverAdApiError(f"검색광고 키워드도구 API 호출 실패: {exc}") from exc

    payload = resp.json()
    items = payload.get("keywordList", [])
    return [
        {
            "keyword": item.get("relKeyword", ""),
            "monthly_pc": _to_int(item.get("monthlyPcQcCnt")),
            "monthly_mobile": _to_int(item.get("monthlyMobileQcCnt")),
        }
        for item in items
    ]
