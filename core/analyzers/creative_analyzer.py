"""소재분석 오케스트레이터 — PRD §7-11-(4) (자사+경쟁사 통합, DA 전용).

'소재분석 시작하기' 버튼이 호출하는 최상위 함수가 run_creative_analysis()입니다.
core/scrapers/ad_library.py의 fetch_meta_ads_detail()이 브랜드별 개별 광고 목록을 반환하면,
이 모듈이 소구포인트 태깅(appeal_tags)·소구 비중 집계·운영기간 분석을 수행합니다.

지금은 Gemini 대신 결정론적 목업으로 appeal_tags를 부여하지만, 반환 shape은 실제 Gemini
Vision 연동 후에도 그대로 유지되도록 설계했습니다(§7-3 appeal_tags 참고).
"""
from __future__ import annotations

from typing import Callable

from core.analyzers.insight_synthesizer import build_insight
from core.scrapers.ad_library import fetch_meta_ads_detail
from core.scrapers.naver_api import seeded_random

APPEAL_TAGS = ["가격소구", "신뢰·전문성소구", "편의성소구", "사회적증거", "공포소구", "트렌드소구"]


def _tag_ad(ad: dict) -> list[str]:
    """소재 1건에 소구포인트 다중 라벨을 부여하는 목업(§7-3 appeal_tags).

    실제 연동 시 Gemini Vision이 소재 이미지/영상+카피를 보고 판단하지만, 이 함수의
    입출력 shape(ad dict → 태그 리스트)은 그대로 유지하면 됩니다.
    """
    rng = seeded_random(f"appeal:{ad['ad_id']}")
    k = rng.randint(1, 2)
    return rng.sample(APPEAL_TAGS, k=k)


def _running_days_bucket(days: int | None) -> str:
    if days is None:
        return "확인 불가"  # 실연동 시 게재 시작일 파싱에 실패한 경우(§7-3 ad_delivery_start_time 참고)
    if days < 14:
        return "단기(<14일)"
    if days <= 90:
        return "중기(14~90일)"
    return "장기(90일+)"


def _analyze_single_brand_creatives(brand_name: str, is_own: bool, page_override: str | None = None) -> dict:
    ads = fetch_meta_ads_detail(brand_name, page_override=page_override)
    for ad in ads:
        ad["appeal_tags"] = _tag_ad(ad)
        ad["running_days_bucket"] = _running_days_bucket(ad.get("ad_running_days"))

    tag_counts: dict[str, int] = {}
    for ad in ads:
        for tag in ad["appeal_tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    total_tags = sum(tag_counts.values())
    appeal_distribution = [
        {
            "appeal_tag": tag,
            "count": count,
            "pct_of_brand_total": round(count / total_tags * 100, 1) if total_tags else 0.0,
        }
        for tag, count in sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    bucket_ads: dict[str, list[dict]] = {}
    for ad in ads:
        bucket_ads.setdefault(ad["running_days_bucket"], []).append(ad)
    long_running_analysis = []
    for bucket, bucket_ad_list in bucket_ads.items():
        bucket_tag_counts: dict[str, int] = {}
        for ad in bucket_ad_list:
            for tag in ad["appeal_tags"]:
                bucket_tag_counts[tag] = bucket_tag_counts.get(tag, 0) + 1
        dominant = sorted(bucket_tag_counts, key=bucket_tag_counts.get, reverse=True)[:2]
        known_days = [a["ad_running_days"] for a in bucket_ad_list if a.get("ad_running_days") is not None]
        long_running_analysis.append({
            "running_days_bucket": bucket,
            "dominant_appeal_tags": dominant,
            "avg_running_days": round(sum(known_days) / len(known_days), 1) if known_days else None,
            "ad_count": len(bucket_ad_list),
        })

    return {
        "brand": brand_name,
        "is_own": is_own,
        "ads": ads,
        "ad_count": len(ads),
        "appeal_distribution": appeal_distribution,
        "long_running_analysis": long_running_analysis,
    }


def run_creative_analysis(
    brand_name: str,
    competitors: list[str],
    meta_overrides: dict[str, str] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """§6-1 function_run(소재분석) 실행 결과 — 자사 1건 + 경쟁사 N건.

    §6 기능별 상태 판정: 자사 또는 경쟁사 중 최소 1개 브랜드의 meta_ads 조회가 성공(0건 포함)하면
    완료. 지금은 목업 데이터가 항상 성공하므로 status는 항상 '완료'입니다.

    meta_overrides: {브랜드명: Meta Ads Library URL 또는 정확한 페이지명} — §7-10 자동 매칭이
    부정확할 때 사용자가 직접 지정한 값(ad_library.fetch_meta_ads_detail의 page_override로 전달).
    on_progress: 브랜드별 수집 진행 상황을 알리는 콜백(UI의 st.status 등에 연결).
    """
    meta_overrides = meta_overrides or {}
    targets = [(brand_name, True), *[(c, False) for c in competitors]]
    total = len(targets)
    all_brands = []
    for i, (name, is_own) in enumerate(targets, start=1):
        if on_progress:
            on_progress(f"{i}/{total} 브랜드 — {name} 광고 소재를 Meta Ads Library에서 수집하는 중...")
        all_brands.append(_analyze_single_brand_creatives(name, is_own, meta_overrides.get(name) or None))
    if on_progress:
        on_progress("수집한 데이터를 종합하는 중...")
    own, *competitor_results = all_brands

    top_brand = max(all_brands, key=lambda b: b["ad_count"])
    top_appeal = top_brand["appeal_distribution"][0] if top_brand["appeal_distribution"] else None
    long_running_own = [
        b for b in own["long_running_analysis"]
        if b["running_days_bucket"] == "장기(90일+)" and b["avg_running_days"] is not None
    ]

    if top_appeal:
        one_line = (
            f"{top_brand['brand']}는 광고의 {top_appeal['pct_of_brand_total']:.0f}%가 "
            f"'{top_appeal['appeal_tag']}' 소구이며, "
            + (
                f"90일 이상 장기 운영 소재는 평균 {long_running_own[0]['avg_running_days']:.0f}일 운영됨"
                if long_running_own
                else "장기 운영(90일+) 소재는 아직 없음"
            )
        )
    else:
        one_line = f"{brand_name} 및 경쟁사 전원의 활성 광고가 0건입니다."

    creative_key_visual = build_insight(
        insight=one_line,
        source=[f"Meta Ads Library {sum(b['ad_count'] for b in all_brands)}건 (자사+경쟁사)"],
        evidence=[f"{b['brand']}: {b['ad_count']}건" for b in all_brands],
        confidence="medium",
    )

    return {
        "status": "완료",
        "own": own,
        "competitors": competitor_results,
        "creative_key_visual": creative_key_visual,
    }
