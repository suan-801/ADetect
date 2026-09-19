"""소재분석 오케스트레이터 — PRD §7-11-(4) (자사+경쟁사 통합, DA 전용).

'소재분석 시작하기' 버튼이 호출하는 최상위 함수가 run_creative_analysis()입니다.
core/scrapers/ad_library.py의 fetch_meta_ads_detail()이 브랜드별 개별 광고 목록을 반환하면,
이 모듈이 포맷 구성(format_mix)·운영기간 분석을 수행합니다.

[제거됨] 소구포인트(appeal_tags) 태깅은 이번 버전에서 사용자 화면·export 어디에도
노출하지 않습니다 — 이전 구현은 seeded_random()으로 태그를 무작위 샘플링하는 목업이었고,
실제 광고 카피/이미지를 해석한 결과가 아니었습니다(예: 프로모션 문구가 근거 없이
"공포소구"로 분류될 수 있었음). 실제 근거(evidence)·confidence 없는 AI classification을
확정 결과처럼 보여주지 않는다는 원칙(PRD §5 Guardrail)에 따라 제거했습니다. 재도입 조건은
PRD §11(taxonomy 정의, multi-label, evidence, confidence, low-confidence 숨김 등) 참고.
"""
from __future__ import annotations

from typing import Callable

from core.analyzers.insight_synthesizer import build_insight
from core.scrapers.ad_library import fetch_meta_ads_detail

_PLATFORM_LABELS = {
    "FACEBOOK": "Facebook", "INSTAGRAM": "Instagram",
    "AUDIENCE_NETWORK": "Audience Network", "MESSENGER": "Messenger",
}


def compact_platforms(raw: str | None) -> str:
    """publisher_platforms(콤마 구분 원본 문자열)를 "Instagram · Facebook · +2"처럼
    1줄 secondary metadata로 압축한다(§6 Placement 정보 위계 변경). UI/HTML export 공용."""
    if not raw:
        return "-"
    items = [p.strip() for p in raw.split(",") if p.strip()]
    if not items:
        return "-"
    labels = [_PLATFORM_LABELS.get(p.upper(), p.title()) for p in items]
    if len(labels) <= 2:
        return " · ".join(labels)
    return " · ".join(labels[:2]) + f" · +{len(labels) - 2}"


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
        ad["running_days_bucket"] = _running_days_bucket(ad.get("ad_running_days"))

    format_mix: dict[str, int] = {}
    for ad in ads:
        fmt = ad.get("format") or "unknown"
        format_mix[fmt] = format_mix.get(fmt, 0) + 1

    bucket_ads: dict[str, list[dict]] = {}
    for ad in ads:
        bucket_ads.setdefault(ad["running_days_bucket"], []).append(ad)
    long_running_analysis = []
    for bucket, bucket_ad_list in bucket_ads.items():
        known_days = [a["ad_running_days"] for a in bucket_ad_list if a.get("ad_running_days") is not None]
        long_running_analysis.append({
            "running_days_bucket": bucket,
            "avg_running_days": round(sum(known_days) / len(known_days), 1) if known_days else None,
            "ad_count": len(bucket_ad_list),
        })

    return {
        "brand": brand_name,
        "is_own": is_own,
        "ads": ads,
        "ad_count": len(ads),
        "format_mix": format_mix,
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

    # creative_key_visual은 실제로 확인 가능한 FACT 지표(활성 광고 수/포맷 구성/장기 운영 소재 수)만
    # 사용해 구성한다 — 근거 없는 소구포인트 해석 문장을 만들지 않는다(PRD §10 Guardrail).
    total_ads = sum(b["ad_count"] for b in all_brands)
    own_video = own["format_mix"].get("video", 0)
    own_long_running = next(
        (lr for lr in own["long_running_analysis"] if lr["running_days_bucket"] == "장기(90일+)"), None
    )
    own_long_running_count = own_long_running["ad_count"] if own_long_running else 0

    if own["ad_count"] > 0:
        one_line = (
            f"{brand_name}는 현재 활성 광고 {own['ad_count']}건을 운영 중이며, "
            f"이 중 영상 소재가 {own_video}건, 90일 이상 장기 운영 소재가 {own_long_running_count}건입니다."
        )
    else:
        one_line = f"{brand_name}의 활성 광고가 현재 0건입니다."

    creative_key_visual = build_insight(
        insight=one_line,
        source=[f"Meta Ads Library {total_ads}건 (자사+경쟁사)"],
        evidence=[
            f"{b['brand']}: 활성 {b['ad_count']}건 (영상 {b['format_mix'].get('video', 0)}건)"
            for b in all_brands
        ],
        confidence="high",
    )

    return {
        "status": "완료",
        "own": own,
        "competitors": competitor_results,
        "creative_key_visual": creative_key_visual,
    }
