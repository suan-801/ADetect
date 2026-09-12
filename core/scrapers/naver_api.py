"""네이버 DataLab(검색량 추이/성별·연령) / 뉴스 검색 / 검색광고 키워드도구 (PRD §3·§7-9·§21-8·§21-10).

지금은 config.settings.USE_MOCK_DATA가 True인 동안(=API 키 미설정) 결정론적 목업 데이터를 반환합니다.
실제 API 연동을 붙일 때는 각 함수의 반환 shape을 그대로 유지한 채 내부 구현만 교체하면 됩니다.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from config import settings


def seeded_random(key: str) -> random.Random:
    """다른 scraper 모듈에서도 재사용하는 결정론적 목업 난수 헬퍼."""
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(seed)


_seeded_random = seeded_random  # 내부 호환용 별칭


def get_search_volume_trend(keyword: str, months: int = 12) -> list[dict]:
    """일별 상대 검색지수(0~100). §7-1 search_volume_trend / §7-1-a 계절성 후처리 원본."""
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 네이버 DataLab 연동 필요 (config/settings.py 키 설정 후 구현)")

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


def get_brand_search_volume(brand_name: str, variants: list[str] | None = None) -> dict:
    """§7-9 브랜드 검색량 — 상대추이 + 최근 30일 절대 검색량(근사) + 성별/연령(가능한 경우)."""
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 네이버 DataLab/검색광고 키워드도구 연동 필요")

    rng = _seeded_random(brand_name)
    variants = variants or [brand_name]
    trend = get_search_volume_trend(brand_name, months=3)
    return {
        "brand": brand_name,
        "variants_used": variants,
        "relative_trend": trend,
        "absolute_30d_pc": rng.randint(800, 15000),
        "absolute_30d_mobile": rng.randint(2000, 40000),
        "gender_ratio": {"male": round(rng.uniform(0.3, 0.7), 2)},
        "confidence": "low",  # 성별/연령 비중은 실측 검증 전까지 참고용 (§7-9)
    }


def get_related_keywords(keyword: str, limit: int = 8) -> list[dict]:
    """§7-2 interest_keywords — 연관검색어 + 검색량."""
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 네이버 연관검색어/검색량 API 연동 필요")

    rng = _seeded_random(keyword)
    suffixes = ["비교", "후기", "가격", "추천", "할인", "이벤트", "리뷰", "순위", "장단점", "가입조건"]
    rng.shuffle(suffixes)
    return [
        {"keyword": f"{keyword} {suf}", "volume": rng.randint(500, 20000)}
        for suf in suffixes[:limit]
    ]


def get_news(keyword: str, scope: str = "market", limit: int = 5) -> list[dict]:
    """§7-1 top_news / §7-3 brand_news — 최근 뉴스 목업."""
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 네이버 뉴스 검색 API 연동 필요")

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
