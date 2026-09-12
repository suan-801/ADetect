"""STEP 1 자동추천 — 카테고리/경쟁사 (PRD §9). 타겟은 여기서 추천하지 않습니다(§9-2 참고).

지금은 목업 규칙 기반입니다. 실제 구현 시 브랜드 홈페이지/뉴스/검색결과 기반 AI 추천으로 교체하되,
"추천 후 사용자 확인" 원칙(§9)은 그대로 유지해야 합니다 — 자동 확정 금지.
"""
from __future__ import annotations

from core.scrapers.naver_api import seeded_random

_CATEGORY_POOL = ["종합 소매/유통", "패션/스포츠웨어", "금융/보험 서비스", "뷰티/헬스", "식음료"]
_COMPETITOR_POOL = [
    ["경쟁사 A", "경쟁사 B", "경쟁사 C", "경쟁사 D"],
    ["대체 채널 X", "인접 경쟁 Y", "직접 경쟁 Z"],
]


def recommend_category(brand_name: str) -> str:
    rng = seeded_random(f"category:{brand_name}")
    return _CATEGORY_POOL[rng.randint(0, len(_CATEGORY_POOL) - 1)]


def recommend_competitors(brand_name: str, category: str) -> list[str]:
    rng = seeded_random(f"competitors:{brand_name}:{category}")
    pool = _COMPETITOR_POOL[rng.randint(0, len(_COMPETITOR_POOL) - 1)]
    return pool
