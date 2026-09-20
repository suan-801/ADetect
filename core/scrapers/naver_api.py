"""네이버 DataLab(검색량 추이/성별·연령) / 뉴스 검색 / 검색광고 키워드도구 (PRD §3·§7-9·§21-8·§21-10).

지금은 config.settings.USE_MOCK_DATA가 True인 동안(=API 키 미설정) 결정론적 목업 데이터를 반환합니다.
실제 API 연동을 붙일 때는 각 함수의 반환 shape을 그대로 유지한 채 내부 구현만 교체하면 됩니다.
"""
from __future__ import annotations

import hashlib
import random
import re
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import requests

from config import settings
from core.scrapers import naver_ad_api


class NaverApiError(RuntimeError):
    """네이버 API 호출 실패 — 호출부(ui/*_tab.py)에서 §11 '부분 실패'로 처리해야 합니다."""


def seeded_random(key: str) -> random.Random:
    """다른 scraper 모듈에서도 재사용하는 결정론적 목업 난수 헬퍼.

    DO NOT PORT THIS TO PRODUCTION ANALYSIS LOGIC — 이 함수와 이를 사용하는 `_mock_*` 헬퍼는
    UI skeleton verification/테스트 fixture 전용이다. key 문자열의 해시로 값을 결정하기 때문에
    같은 입력에 항상 같은 mock을 반환할 뿐, 실제 시장/브랜드 판단 근거가 아니다.
    """
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(seed)


_seeded_random = seeded_random  # 내부 호환용 별칭


def _mock_search_volume_trend(keyword: str, months: int) -> list[dict]:
    rng = _seeded_random(keyword)
    base = rng.randint(30, 70)
    today = date.today()
    days = months * 30
    trend = []
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        weekday_boost = 8 if d.weekday() >= 5 else 0
        noise = rng.randint(-10, 10)
        idx = max(1, min(100, base + weekday_boost + noise))
        trend.append({"date": d.isoformat(), "search_index": idx})
    return trend


def get_search_volume_trend(keyword: str, months: int = 12) -> list[dict]:
    """일별 상대 검색지수(0~100). §7-1 search_volume_trend / §7-1-a 계절성 후처리 원본."""
    if settings.NAVER_DATALAB_MOCK:
        return _mock_search_volume_trend(keyword, months)

    end = date.today()
    start = end - timedelta(days=months * 30)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
    }
    try:
        resp = requests.post(
            # NAVER API HUB(NCP) 콘솔에서 "Data Lab · 검색어트렌드"로 신청한 경우의 실제 엔드포인트입니다.
            # ntruss.com 문서에 나오는 "naveropenapi.apigw.ntruss.com/datalab/v1/search"는 이 콘솔 기준으로는
            # 404/구독 필요 오류가 나서, 실제 계정으로 직접 검증해 이 경로로 확정했습니다(2026-09-13).
            # developers.naver.com(구 네이버 오픈API)에서 직접 발급받았다면 대신
            # "https://openapi.naver.com/v1/datalab/search" + X-Naver-Client-Id/Secret 헤더를 씁니다 — §21-8 참고.
            "https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
            headers={
                "X-NCP-APIGW-API-KEY-ID": settings.NAVER_CLIENT_ID,
                "X-NCP-APIGW-API-KEY": settings.NAVER_CLIENT_SECRET,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise NaverApiError(f"네이버 DataLab 검색어트렌드 API 호출 실패: {exc}") from exc

    results = resp.json().get("results", [])
    data = results[0]["data"] if results else []
    return [{"date": row["period"], "search_index": row["ratio"]} for row in data]


def get_brand_search_volume(brand_name: str, variants: list[str] | None = None) -> dict:
    """§7-9 브랜드 검색량 — 상대추이(DataLab) + 최근 30일 절대 검색량(검색광고 키워드도구)."""
    variants = variants or [brand_name]
    trend = get_search_volume_trend(brand_name, months=3)

    if settings.NAVER_AD_MOCK:
        rng = _seeded_random(brand_name)
        return {
            "brand": brand_name,
            "variants_used": variants,
            "relative_trend": trend,
            "absolute_30d_pc": rng.randint(800, 15000),
            "absolute_30d_mobile": rng.randint(2000, 40000),
            "gender_ratio": {"male": round(rng.uniform(0.3, 0.7), 2)},
            "confidence": "low",  # 성별/연령 비중은 실측 검증 전까지 참고용 (§7-9)
        }

    try:
        stats = naver_ad_api.fetch_keyword_stats(brand_name)
    except naver_ad_api.NaverAdApiError as exc:
        raise NaverApiError(str(exc)) from exc

    exact = next((s for s in stats if s["keyword"].replace(" ", "") == brand_name.replace(" ", "")), None)
    absolute_pc = exact["monthly_pc"] if exact else 0
    absolute_mobile = exact["monthly_mobile"] if exact else 0
    return {
        "brand": brand_name,
        "variants_used": variants,
        "relative_trend": trend,
        "absolute_30d_pc": absolute_pc,
        "absolute_30d_mobile": absolute_mobile,
        # 성별/연령 비중은 검색광고 키워드도구에 없는 지표라 DataLab 인구통계 필터 실측 전까지 미제공(§7-9)
        "gender_ratio": None,
        "confidence": "high" if exact else "low",
    }


def get_related_keywords(keyword: str, limit: int = 8) -> list[dict]:
    """§7-2 interest_keywords / §7-3 brand_related_keywords — 연관검색어 + 검색량 (검색광고 키워드도구)."""
    if settings.NAVER_AD_MOCK:
        rng = _seeded_random(keyword)
        suffixes = ["비교", "후기", "가격", "추천", "할인", "이벤트", "리뷰", "순위", "장단점", "가입조건"]
        rng.shuffle(suffixes)
        return [
            {"keyword": f"{keyword} {suf}", "volume": rng.randint(500, 20000)}
            for suf in suffixes[:limit]
        ]

    try:
        stats = naver_ad_api.fetch_keyword_stats(keyword)
    except naver_ad_api.NaverAdApiError as exc:
        raise NaverApiError(str(exc)) from exc

    related = [s for s in stats if s["keyword"].replace(" ", "") != keyword.replace(" ", "")]
    related.sort(key=lambda s: s["monthly_pc"] + s["monthly_mobile"], reverse=True)
    return [
        {"keyword": s["keyword"], "volume": s["monthly_pc"] + s["monthly_mobile"]}
        for s in related[:limit]
    ]


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    """네이버 검색 API는 매칭된 검색어를 <b>태그</b>로 감싸서 돌려준다 — 표시용으로 제거."""
    return _TAG_RE.sub("", text)


def _mock_news(keyword: str, scope: str, limit: int) -> list[dict]:
    rng = _seeded_random(f"{scope}:{keyword}")
    today = date.today()
    templates = [
        "{kw}, 최근 {n}개월 검색 관심도 상승",
        "'{kw}' 관련 신규 프로모션 소식",
        "업계 전문가가 본 '{kw}'의 향후 전망",
        "'{kw}', SNS에서 화제몰이",
        "'{kw}' 카테고리 시장 동향 리포트 발간",
    ]
    news = []
    for i, tmpl in enumerate(templates[:limit]):
        d = today - timedelta(days=rng.randint(1, 300))
        news.append({
            "title": tmpl.format(kw=keyword, n=rng.randint(1, 6)),
            "url": f"https://example-news.local/{keyword}-{i}",
            "summary": f"{keyword}에 대한 샘플 뉴스 요약입니다. (실제 연동 전 목업 데이터)",
            "published_at": d.isoformat(),
        })
    return sorted(news, key=lambda x: x["published_at"], reverse=True)


def get_news(keyword: str, scope: str = "market", limit: int = 5) -> list[dict]:
    """§7-1 top_news / §7-3 brand_news — 최근 뉴스.

    NAVER API HUB(NCP) '검색' 상품 — naverapihub.apigw.ntruss.com/search/v1/news.
    데이터랩과는 게이트웨이 도메인이 다르지만(§21-8), Client ID/Secret은 같은 애플리케이션 것을
    그대로 쓴다.
    """
    if settings.NAVER_SEARCH_MOCK:
        return _mock_news(keyword, scope, limit)

    try:
        resp = requests.get(
            "https://naverapihub.apigw.ntruss.com/search/v1/news",
            headers={
                "X-NCP-APIGW-API-KEY-ID": settings.NAVER_CLIENT_ID,
                "X-NCP-APIGW-API-KEY": settings.NAVER_CLIENT_SECRET,
            },
            params={"query": keyword, "display": limit, "sort": "date"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise NaverApiError(f"네이버 뉴스 검색 API 호출 실패: {exc}") from exc

    items = resp.json().get("items", [])
    news = []
    for item in items:
        try:
            published = parsedate_to_datetime(item.get("pubDate", "")).date().isoformat()
        except (TypeError, ValueError):
            published = None
        news.append({
            "title": _strip_tags(item.get("title", "")),
            "url": item.get("link") or item.get("originallink", ""),
            "summary": _strip_tags(item.get("description", "")),
            "published_at": published,
        })
    return news
