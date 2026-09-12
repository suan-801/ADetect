"""Meta Ads Library(광고 소재) + Instagram Profile(SNS 운영현황) 수집 (PRD §7-11-0).

★ 이 파일에는 서로 다른 두 개념이 함께 있습니다(용어 혼동 주의, §7-11-0):
- fetch_meta_ads(): 활성 광고 소재 (FB+IG 노출 통합, "Instagram 전용 광고"는 별도로 없음)
- fetch_instagram_profile(): 광고가 아닌 SNS 계정 자체의 운영현황

브랜드분석 탭에서 필요한 요약 수준까지만 구현했고, 소재(Creative) 상세 분석(appeal_tags 등)은
'소재분석' 담당자가 §7-11-4 기준으로 별도 확장합니다.
"""
from __future__ import annotations

from config import settings
from core.scrapers.naver_api import seeded_random as _seeded_random


def fetch_meta_ads(brand_name: str) -> dict:
    """§7-3 meta_ads/ad_count/format_mix/key_message 등 — 브랜드분석에 필요한 요약 수준."""
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 Apify facebook-ads-library-scraper 연동 필요")

    rng = _seeded_random(f"meta_ads:{brand_name}")
    ad_count = rng.randint(0, 40)
    formats = ["image", "video", "carousel"]
    format_mix = {f: rng.randint(0, ad_count) for f in formats}
    candidates = ["가격 프로모션", "신뢰·전문성 강조", "신제품 알림", "시즌 세일", "후기/사회적 증거"]
    key_messages = rng.sample(candidates, k=rng.randint(1, 3))
    return {
        "brand": brand_name,
        "ad_count": ad_count,
        "format_mix": format_mix,
        "key_message": key_messages,
        "recent_activity": ad_count > 0,
        "is_active_only": True,
    }


def fetch_instagram_profile(brand_name: str) -> dict:
    """§7-3 instagram — 팔로워/포스팅 수 등 SNS 운영현황 (광고 아님)."""
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 Apify Instagram 프로필 스크래퍼 연동 필요")

    rng = _seeded_random(f"ig_profile:{brand_name}")
    has_profile = rng.random() > 0.1
    if not has_profile:
        return {"brand": brand_name, "profile_found": False}
    return {
        "brand": brand_name,
        "profile_found": True,
        "followers": rng.randint(500, 300_000),
        "posts": rng.randint(20, 3000),
        "recent_caption_sample": f"{brand_name}의 최근 소식을 확인해보세요 (샘플 캡션)",
    }
