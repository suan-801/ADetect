"""AI 판단 vs 사실 데이터 구분 스키마 (PRD §8).

AI/REC로 분류되는 모든 필드는 insight/source/evidence/confidence 구조를 반드시 포함합니다.
지금은 실제 Gemini 호출 대신 규칙 기반 목업 문구를 생성합니다 — 함수 시그니처는
실제 연동 시에도 그대로 유지되도록 설계했습니다.
"""
from __future__ import annotations


def build_insight(insight: str, source: list[str], evidence: list[str], confidence: str = "medium") -> dict:
    """§8-2 AI/REC 필드 공통 스키마."""
    assert confidence in ("high", "medium", "low")
    return {
        "insight": insight,
        "source": source,
        "evidence": evidence,
        "confidence": confidence,
    }


def build_target_insight(
    market_result: dict | None,
    brand_result: dict | None,
    creative_result: dict | None = None,
) -> dict:
    """종합분석의 Target Insight subsection (PRD §14·§15).

    독립 function_run이 아니라 시장분석+브랜드분석의 기존 캐시 결과만 재사용하는 합성
    필드다 — 새로운 수집(스크래핑/API 호출)을 추가하지 않는다. 지금 데이터 모델에는
    연령/성별 등 세그먼트별 검색 데이터가 없으므로, 근거 없는 인구통계(예: "30~40대 여성")를
    지어내지 않는다 — 실제로 확인 가능한 시장/경쟁 신호만 근거로 쓰고, 세그먼트를 특정할
    수 없다는 사실 자체를 정직한 결론으로 제시한다.

    market_result/brand_result가 아예 없으면(시장·브랜드분석 미실행) insufficient_data.
    """
    market_ok = bool(market_result) and bool(market_result.get("trend"))
    brand_ok = bool(brand_result) and bool(brand_result.get("own"))
    if not (market_ok and brand_ok):
        return {
            "status": "insufficient_data",
            "message": "시장분석과 브랜드분석이 모두 완료되면 생성됩니다.",
        }

    trend = market_result["trend"]
    first_val, last_val = trend[0]["search_index"], trend[-1]["search_index"]
    change_pct = ((last_val - first_val) / first_val * 100) if first_val else 0.0
    trend_dir = "증가" if change_pct > 1 else "감소" if change_pct < -1 else "보합"

    competitors = brand_result.get("competitors", [])
    evidence = [
        f"카테고리 검색량 추이 {trend_dir} ({change_pct:+.1f}%, 시장분석)",
        f"경쟁사 {len(competitors)}개 브랜드와 비교(브랜드분석)",
    ]
    source = ["시장분석 search_volume_trend", "브랜드분석 경쟁 구도"]
    if creative_result:
        own_ads = creative_result.get("own", {}).get("ad_count")
        if own_ads is not None:
            evidence.append(f"자사 활성 광고 {own_ads}건(소재분석, 참고 근거)")
            source.append("소재분석 ad_count")

    insight = (
        "현재 수집된 데이터에는 연령·성별 등 세그먼트별 검색 데이터가 없어 특정 인구통계를 "
        f"핵심 타겟으로 확정할 근거가 부족합니다. 다만 카테고리 검색량은 {trend_dir} 추세이며, "
        f"경쟁사 {len(competitors)}개 브랜드 대비 자사 포지션을 참고 신호로 확인했습니다 — "
        "세그먼트별 검색 데이터가 수집되면 더 구체적인 타겟을 제시할 수 있습니다."
    )
    return build_insight(insight=insight, source=source, evidence=evidence, confidence="low")


def mock_promotion_interpretation(promotion_fact: str, conversion_objective: str) -> dict:
    """conversion_objective(§7-3-a)에 맞춰 서술 톤을 다르게 하는 목업 해석.

    실제 연동 시 Gemini 프롬프트로 교체되지만, 인터페이스(입력/출력 shape)는 동일하게 유지합니다.
    """
    return build_insight(
        insight=f"'{promotion_fact}' 문구는 {conversion_objective} 전환을 유도하기 위한 목적으로 판단됨 (샘플 해석)",
        source=["Mock Brand Website"],
        evidence=[promotion_fact],
        confidence="medium",
    )
