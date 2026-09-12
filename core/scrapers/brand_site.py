"""브랜드 홈페이지/대표 상세페이지 크롤링 (PRD §7-3 brand_website_facts).

카테고리 구조 분류·상품 리뷰 분석은 범위 밖입니다(§7-3-c 랜딩페이지 수동 체크 팁 참고).
"""
from __future__ import annotations

from config import settings


def crawl_brand_website(brand_name: str, url: str | None = None) -> dict:
    """§7-3 brand_website_facts — 원문 카피(USP·가격·프로모션 등) 발췌.

    대표 상세페이지가 없는 브랜드(리테일러 등)는 홈페이지/브랜드스토리로 폴백합니다(정상 처리, §6).
    """
    if not settings.USE_MOCK_DATA:
        raise NotImplementedError("실제 Playwright 크롤링 연동 필요")

    fallback_used = url is None
    return {
        "brand": brand_name,
        "source_url": url or f"https://www.{brand_name.lower().replace(' ', '')}.example.com",
        "fallback_used": fallback_used,
        "usp_summary": f"{brand_name}은(는) 신뢰할 수 있는 품질과 빠른 대응을 핵심 가치로 내세우고 있음 (샘플)",
        "promotion_fact": f"{brand_name} 첫 구매/가입 시 특별 혜택 제공 (샘플 문구)",
        "raw_copy_snippets": [
            f"{brand_name}과 함께라면 더 나은 선택",
            "지금 바로 확인해보세요",
        ],
    }
