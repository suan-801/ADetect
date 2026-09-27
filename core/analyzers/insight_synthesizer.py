"""AI 판단 vs 사실 데이터 구분 스키마 (PRD §8).

AI/REC로 분류되는 모든 필드는 insight/source/evidence/confidence 구조를 반드시 포함합니다.
종합 해석은 검증된 원문을 Gemini에 전달하고 응답의 출처·인용을 확인합니다.
Target Insight는 기존 검색 추이와 비교 대상만 사용하는 경량 파생 결과입니다.
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
    change_pct = ((last_val - first_val) / first_val * 100) if first_val else None
    trend_dir = (
        "판단 불가(기준 지수 0)" if change_pct is None
        else "증가" if change_pct > 1 else "감소" if change_pct < -1 else "보합"
    )
    change_label = f"{change_pct:+.1f}%" if change_pct is not None else "증감률 미제공"

    competitors = brand_result.get("competitors", [])
    evidence = [
        f"카테고리 검색량 추이 {trend_dir} ({change_label}, 시장분석)",
        f"경쟁사 {len(competitors)}개 브랜드와 비교(브랜드분석)",
    ]
    source = ["시장분석 search_volume_trend", "브랜드분석 경쟁 구도"]
    if creative_result:
        own_ads = creative_result.get("own", {}).get("ad_count")
        if own_ads is not None and not creative_result.get("own", {}).get("collection_failed"):
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


def run_synthesis(session, axes=None):
    """동일 세션 최신 결과만 소비. 분모가 불완전하거나 0이면 점유율을 만들지 않는다."""
    from datetime import date, datetime, timedelta, timezone
    from core.analyzers.evidence import interpret, unavailable
    from core.runtime import input_signature
    from core.analyzers.positioning import score_positions
    market = session.get("market_result") if session.get("market_status") in ("완료", "부분 실패") else None
    brand = session.get("brand_result") if session.get("brand_status") in ("완료", "부분 실패") else None
    creative = session.get("creative_result") if session.get("creative_status") in ("완료", "부분 실패") else None
    if not any((market, brand, creative)):
        return {"status": "전체 실패", "errors": ["완료된 입력 결과가 없습니다."]}
    profiles = [brand["own"], *brand.get("competitors", [])] if brand else []
    ads_profiles = [creative["own"], *creative.get("competitors", [])] if creative else profiles
    names = list(dict.fromkeys([session["brand_name"], *session.get("competitors", [])]))
    sov = [{"brand": n, "share_of_search": None, "share_of_ads": None, "share_of_voice_news": None} for n in names]
    def apply_share(field, values):
        if any(values.get(n) is None for n in names):
            return
        total = sum(values[n] for n in names)
        if total <= 0:
            return
        for row in sov:
            row[field] = round(values[row["brand"]] / total * 100, 3)
    apply_share("share_of_search", {p["brand"]: sum(v["search_index"] for v in p["brand_search_volume"].get("relative_trend", []))
               if p["brand_search_volume"].get("comparable") and p["brand_search_volume"].get("relative_trend") else None for p in profiles})
    apply_share("share_of_ads", {p["brand"]: p.get("ad_count") if not p.get("collection_failed") else None for p in ads_profiles})
    apply_share("share_of_voice_news", {p["brand"]: len({n["url"] for n in p.get("brand_news", []) if (n.get("published_at") or "")[:10] >= (date.today()-timedelta(days=90)).isoformat()})
               if p.get("news_status") == "available" else None for p in profiles})
    facts = []
    for p in profiles:
        website = p.get("brand_website_facts", {})
        facts += [{"source": website.get("source_url"), "text": t} for t in website.get("raw_copy_snippets", [])]
    for p in ads_profiles:
        if "meta_ads" not in p.get("sample_sources", []) and not (creative and creative.get("sample_sources")):
            facts += [{"source": "Meta:"+str(a.get("ad_id")), "text": (a.get("headline") or "")+"\n"+(a.get("body") or "")} for a in p.get("ads", [])]
    if market and "news" not in market.get("sample_sources", []):
        facts += [{"source": n["url"], "text": n["title"]+"\n"+n["summary"]} for n in market.get("news", [])]
    fields = ["competitive_landscape", "common_message", "differentiation_point", "white_space", "recommended_angle", "one_line_summary"]
    ai = interpret(fields, facts, "White Space는 수집된 자료의 범위 내에서만 가설로 설명하세요. 성과가 검증됐다고 주장하지 마세요.")
    samples = sorted(set(s for r in (market, brand, creative) if r for s in r.get("sample_sources", [])))
    errors = [f"{k}: AI 호출·검증 실패" for k,v in ai.items() if v.get("status") == "not_available"]
    return {"status": "부분 실패" if errors else "완료", "errors":errors, "sov": sov, **ai,
            "target_insight": build_target_insight(market, brand, creative),
            "positioning_map": score_positions(brand, axes) if brand and axes else unavailable("두 개 이상 브랜드의 근거와 사용자 확인 축이 필요합니다."),
            "sample_sources": samples, "input_signature": input_signature(session),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "limitations": ["Share of Ads는 브랜드별 최대 20건 수집 표본의 비율이며 전체 활성 광고·광고비·노출·성과 점유율이 아닙니다.",
                            "뉴스 비율은 수집된 최근 3개월 기사 표본 기준이며 전체 언론 점유율이 아닙니다.",
                            "서로 비교 가능한 검색지수만 사용합니다. 누락된 브랜드·0 분모는 미제공합니다."]}
