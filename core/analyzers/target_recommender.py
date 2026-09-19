"""[DEPRECATED — 더 이상 신규 UI에서 호출하지 않음] 타겟 추천/타겟분석 — 구 PRD §7-2·§9-2.

recommend_target()은 seeded_random()으로 성별+연령 세그먼트를 무작위 선택하는 목업이며,
실제 근거(evidence) 없이 확정적인 타겟처럼 보이는 문장을 만든다 — 이 로직을 그대로
Synthesis의 Target Insight로 옮기면 안 된다(PRD §14). Target Insight는
core/analyzers/insight_synthesizer.build_target_insight()가 시장분석/브랜드분석의
실제 캐시 데이터만으로 생성하며, 근거가 없는 인구통계는 추정하지 않는다.

이 모듈은 ui/target_tab.py(더 이상 Workspace에서 render되지 않음)와의 하위 호환을 위해서만
남겨둔다. 신규 코드에서는 사용하지 마세요.
"""
from __future__ import annotations

from core.analyzers.insight_synthesizer import build_insight
from core.scrapers.naver_api import get_related_keywords, seeded_random


def recommend_target(brand_name: str, market_result: dict, brand_result: dict) -> dict:
    """§7-2 recommended_target — 게이트 통과 직후 자동 생성(무료), function_run 아님."""
    rng = seeded_random(f"target:{brand_name}")
    segments = ["20~30대 여성", "30~40대 남성", "40~50대 남성", "20~30대 남녀", "30~50대 여성"]
    segment = segments[rng.randint(0, len(segments) - 1)]

    competitor_names = [c["brand"] for c in brand_result.get("competitors", [])] or ["경쟁사"]
    conversion_objective = brand_result.get("brand_context", {}).get("conversion_objective", "구매")

    insight = build_insight(
        insight=(
            f"경쟁사({', '.join(competitor_names)})는 주로 다른 연령대에 집중하고 있으나, "
            f"자사 검색 세그먼트 지수상 상대적으로 공략이 낮은 '{segment}' 구간에서 "
            f"시장 성장세 대비 경쟁 밀도가 낮아 이 구간을 선점하는 것을 추천 — "
            f"이 구간에서의 핵심 전환 목표는 '{conversion_objective}'"
        ),
        source=["시장분석 검색량 추이(샘플)", "브랜드분석 경쟁 구도(샘플)"],
        evidence=[f"{segment} 세그먼트 검색 지수 상대적 우위(샘플)"],
        confidence="medium",
    )
    return {"segment": segment, **insight}


def analyze_confirmed_target(confirmed_target: str, category: str) -> dict:
    """§6-1 function_run(타겟분석) — confirmed_target 확정 후 실행하는 실제 분석."""
    keywords = get_related_keywords(category or confirmed_target)
    disclaimer = "실제 소비자 조사가 아닌 검색행동·시의성 기반 간접 추정입니다."
    persona = {
        "target_disposition": build_insight(
            insight="가격 비교보다 신뢰/후기 기반 의사결정을 선호하는 경향 (샘플)",
            source=["interest_keywords(샘플)"],
            evidence=[k["keyword"] for k in keywords[:3]],
            confidence="low",
        ),
        "preferred_situation": build_insight(
            insight="주말 및 월말에 관련 탐색이 몰리는 경향 (샘플)",
            source=["search_seasonality(샘플)"],
            evidence=["주말 검색 지수 평일 대비 우위(샘플)"],
            confidence="low",
        ),
        "conversion_trigger_context": build_insight(
            insight="제도/가격 변경 뉴스가 결정을 가속시킬 수 있음 (샘플)",
            source=["top_news(샘플)"],
            evidence=["관련 제도 변경 뉴스(샘플)"],
            confidence="low",
        ),
        "disclaimer": disclaimer,
    }
    return {"confirmed_target": confirmed_target, "interest_keywords": keywords, "ai_persona": persona}
