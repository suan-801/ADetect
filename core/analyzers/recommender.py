"""STEP 1 자동추천 — 카테고리/경쟁사 (PRD §9). 타겟은 여기서 추천하지 않습니다(§9-2 참고).

GEMINI_API_KEY가 있으면 Gemini로 실제 추천하고, 없으면(config.settings.GEMINI_MOCK) 결정론적
목업 규칙으로 대체합니다. Gemini 호출이 실패해도(quota/네트워크 등) 목업으로 조용히 폴백해
STEP 1 확인 화면 자체가 깨지지 않도록 합니다 — "추천 후 사용자 확인" 원칙(§9)은 그대로 유지됩니다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel

from config import settings
from core.scrapers.naver_api import seeded_random

_CATEGORY_POOL = ["종합 소매/유통", "패션/스포츠웨어", "금융/보험 서비스", "뷰티/헬스", "식음료"]

# 경쟁사 후보 — {"name": 브랜드명, "type": 내부 분류(§7-10) or None}.
# type은 사용자가 고르는 값이 아니라 추천 근거를 설명하기 위한 읽기 전용 참고 태그입니다(§7-10).
_COMPETITOR_POOL: list[list[dict]] = [
    [
        {"name": "경쟁사 A", "type": None},
        {"name": "경쟁사 B", "type": None},
        {"name": "경쟁사 C", "type": None},
        {"name": "경쟁사 D", "type": None},
    ],
    [
        {"name": "경쟁사 X", "type": "대체 채널"},
        {"name": "경쟁사 Y", "type": "인접 경쟁"},
        {"name": "경쟁사 Z", "type": "직접 경쟁"},
    ],
]


class _Competitor(BaseModel):
    name: str
    type: Literal["직접 경쟁", "인접 경쟁", "대체 채널"]


class _Recommendation(BaseModel):
    category: str
    competitors: list[_Competitor]


_PROMPT = """당신은 한국 시장을 잘 아는 마케팅 리서치 애널리스트입니다.
브랜드명 "{brand_name}"에 대해 다음을 한국어로 추천해주세요.

1. category: 이 브랜드가 속한 산업 카테고리를 한국 시장 기준 짧은 명사구로 (예: "손해보험 서비스", \
"H&B(헬스&뷰티) 리테일", "스포츠웨어").
2. competitors: 이 브랜드와 비교 분석할 만한, 실제로 존재하는 경쟁사 4~5개. 브랜드명 자체는 \
포함하지 마세요. 각 경쟁사는 다음 중 하나로 분류하세요:
   - "직접 경쟁": 동일 카테고리에서 정면으로 경쟁하는 브랜드
   - "인접 경쟁": 인접 카테고리에 있어 고객군 일부가 겹치는 브랜드
   - "대체 채널": 다른 방식으로 같은 소비자 니즈를 해결하는 대안 채널/브랜드
"""


@lru_cache(maxsize=64)
def _gemini_recommend(brand_name: str) -> _Recommendation | None:
    """Gemini 호출 결과를 브랜드명 기준으로 캐시 — recommend_category/recommend_competitors가
    같은 브랜드에 대해 매번 새로 호출하지 않고 이 캐시를 공유합니다. 실패 시 None을 반환해
    호출부가 목업으로 폴백하게 합니다."""
    try:
        from google.genai import types

        from core.analyzers.gemini_client import get_client

        client = get_client()
        resp = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=_PROMPT.format(brand_name=brand_name),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_Recommendation,
            ),
        )
        return _Recommendation.model_validate(json.loads(resp.text))
    except Exception:
        # §11 정책 — STEP 1 추천은 무료/즉시 단계라 실패해도 전체 실패로 취급하지 않고
        # 조용히 목업으로 대체한다(사용자는 어차피 §9에서 결과를 확인·수정할 수 있음).
        return None


def _mock_category(brand_name: str) -> str:
    rng = seeded_random(f"category:{brand_name}")
    return _CATEGORY_POOL[rng.randint(0, len(_CATEGORY_POOL) - 1)]


def _mock_competitors(brand_name: str, category: str) -> list[dict]:
    rng = seeded_random(f"competitors:{brand_name}:{category}")
    return _COMPETITOR_POOL[rng.randint(0, len(_COMPETITOR_POOL) - 1)]


def recommend_category(brand_name: str) -> str:
    if not settings.GEMINI_MOCK:
        rec = _gemini_recommend(brand_name)
        if rec is not None:
            return rec.category
    return _mock_category(brand_name)


def recommend_competitors(brand_name: str, category: str) -> list[dict]:
    """경쟁사 후보 목록 — 각 항목은 {"name", "type"} dict입니다(§7-10 내부 분류 참고)."""
    if not settings.GEMINI_MOCK:
        rec = _gemini_recommend(brand_name)
        if rec is not None:
            return [{"name": c.name, "type": c.type} for c in rec.competitors]
    return _mock_competitors(brand_name, category)
