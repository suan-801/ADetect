"""브랜드분석 오케스트레이터 — PRD §7-3(브랜드 프로필, 자사+경쟁사 동일 스키마) 구현.

'브랜드분석 시작하기' 버튼이 호출하는 최상위 함수가 run_brand_analysis()입니다.
지금은 core/scrapers/*가 전부 목업(mock) 데이터를 반환하지만, 이 함수의 반환 shape과
ui/brand_tab.py의 렌더링 방식은 실제 API 연동 후에도 그대로 유지됩니다 — scraper 내부만
config.settings.USE_MOCK_DATA 분기에 따라 실제 호출로 교체하면 됩니다.
"""
from __future__ import annotations

from core.analyzers.insight_synthesizer import build_insight, mock_promotion_interpretation
from core.scrapers.ad_library import fetch_instagram_profile, fetch_meta_ads
from core.scrapers.brand_site import crawl_brand_website
from core.scrapers.naver_api import get_brand_search_volume, get_news, seeded_random


def infer_brand_context(brand_name: str) -> dict:
    """§7-3-a brand_context — 내부 판단 필드(비노출). 브랜드명만으로 성격을 추정하는 목업.

    실제 연동 시에는 브랜드 홈페이지·뉴스·검색결과를 근거로 Gemini가 판단하되,
    이 함수의 반환 shape(브랜드 유형/전환 목표 등)은 그대로 유지합니다.
    """
    rng = seeded_random(f"brand_context:{brand_name}")
    presets = [
        {
            "brand_type": "멀티카테고리 제품 브랜드",
            "business_model": "단일 브랜드 직접판매",
            "offering_type": "물리적 상품",
            "conversion_objective": "구매",
        },
        {
            "brand_type": "손해보험/금융 서비스 브랜드",
            "business_model": "상담·가입·계약형 서비스",
            "offering_type": "금융상품",
            "conversion_objective": "상담/견적/가입/계약",
        },
        {
            "brand_type": "멀티브랜드 리테일 플랫폼",
            "business_model": "여러 브랜드가 입점하는 플랫폼형",
            "offering_type": "복합(다품목 물리적 상품)",
            "conversion_objective": "상품 탐색/구매/재방문",
        },
    ]
    preset = presets[rng.randint(0, len(presets) - 1)]
    return {**preset, "analysis_scope": "brand", "confidence": "medium"}


def _analyze_single_brand(brand_name: str, is_own: bool, brand_context: dict) -> dict:
    """§7-3 필드셋 — 자사/경쟁사 동일 스키마로 브랜드 1건을 채웁니다."""
    search_volume = get_brand_search_volume(brand_name)
    website = crawl_brand_website(brand_name)
    news = get_news(brand_name, scope="brand", limit=5)
    meta_ads = fetch_meta_ads(brand_name)
    instagram = fetch_instagram_profile(brand_name)

    website_target_message = build_insight(
        insight=f"{brand_name}은(는) 홈페이지 카피 상 '{website['usp_summary']}'를 중심으로 "
                f"{brand_context['conversion_objective']} 전환을 유도하는 메시지를 사용 중 (샘플 해석)",
        source=["Mock Brand Website"],
        evidence=website["raw_copy_snippets"],
        confidence="medium",
    )
    promotion_interpretation = mock_promotion_interpretation(
        website["promotion_fact"], brand_context["conversion_objective"]
    )

    return {
        "brand": brand_name,
        "is_own": is_own,
        "brand_search_volume": search_volume,
        "brand_website_facts": website,
        "brand_website_target_message": website_target_message,
        "brand_news": news,
        "meta_ads": meta_ads,
        "instagram": instagram,
        "promotion_fact": website["promotion_fact"],
        "promotion_interpretation": promotion_interpretation,
        "key_message": meta_ads["key_message"],
        "ad_count": meta_ads["ad_count"],
        "format_mix": meta_ads["format_mix"],
        "media_operation_matrix_row": {
            "naver_sa": rng_bool(brand_name, "sa"),
            "naver_brand_search": rng_bool(brand_name, "brand_search"),
            "meta_ads": meta_ads["ad_count"] > 0,
            "instagram_profile": instagram.get("profile_found", False),
            "youtube_channel": rng_bool(brand_name, "youtube"),
        },
    }


def rng_bool(brand_name: str, salt: str) -> bool:
    return seeded_random(f"{brand_name}:{salt}").random() > 0.4


def run_brand_analysis(brand_name: str, competitors: list[str]) -> dict:
    """§6-1 function_run(브랜드분석) 실행 결과 — 자사 1건 + 경쟁사 N건.

    완료/부분실패 판정은 §6 "기능별 상태 판정" 표를 따르되, 이 스켈레톤에서는
    목업 데이터가 항상 성공하므로 status는 항상 '완료'로 반환합니다.
    """
    brand_context = infer_brand_context(brand_name)

    own_profile = _analyze_single_brand(brand_name, is_own=True, brand_context=brand_context)
    competitor_profiles = [
        _analyze_single_brand(c, is_own=False, brand_context=brand_context) for c in competitors
    ]

    comparison_insight = build_insight(
        insight=f"경쟁사 {len(competitor_profiles)}개사와 비교했을 때, {brand_name}의 광고 소재는 "
                f"'{', '.join(own_profile['key_message'])}' 메시지에 집중되어 있음 (샘플 총평)",
        source=[f"Meta Ads Library {own_profile['ad_count']}건 (자사)"],
        evidence=own_profile["key_message"],
        confidence="medium",
    )

    return {
        "status": "완료",
        "brand_context": brand_context,
        "own": own_profile,
        "competitors": competitor_profiles,
        "comparison_insight": comparison_insight,
    }
