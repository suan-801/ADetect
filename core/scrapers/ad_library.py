"""Meta Ads Library(광고 소재) + Instagram Profile(SNS 운영현황) 수집 (PRD §7-11-0).

이 파일에는 서로 다른 두 개념이 함께 있습니다(용어 혼동 주의, §7-11-0):
- fetch_meta_ads() / fetch_meta_ads_detail(): 활성 광고 소재 (FB+IG 노출 통합, "Instagram 전용 광고"는 별도로 없음)
- fetch_instagram_profile(): 광고가 아닌 SNS 계정 자체의 운영현황

Meta Ads는 Apify `curious_coder/facebook-ads-library-scraper` 액터로 실연동되어 있습니다
(§10·§21-11, 2026-09-13 실계정 검증). Instagram 프로필은 여전히 목업입니다 — 실제 Apify
Instagram 액터(apify/instagram-profile-scraper)는 브랜드명이 아니라 정확한 계정 handle을
입력받는데, 이 프로젝트에는 아직 브랜드명→handle 해석 단계가 없습니다(§7-10과 동일한 문제,
Meta는 §7-3-b의 "최빈 페이지" 근사로 우회했지만 Instagram은 대응하는 우회 신호가 없음).
"""
from __future__ import annotations

import base64
import html
import urllib.parse
from collections import Counter
from datetime import date, datetime, timedelta
from functools import lru_cache

import requests

from config import settings
from core.scrapers.naver_api import seeded_random as _seeded_random


class ApifyFetchError(RuntimeError):
    """Apify 액터 호출 실패 — 호출부에서 §11 '부분/전체 실패'로 처리해야 합니다."""


def _run_actor_sync(actor: str, run_input: dict) -> list[dict]:
    actor_path = actor.replace("/", "~")
    try:
        resp = requests.post(
            f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items",
            params={"token": settings.APIFY_API_TOKEN},
            json=run_input,
            timeout=180,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ApifyFetchError(f"Apify 액터({actor}) 호출 실패: {exc}") from exc

    items = resp.json()
    if items and isinstance(items[0], dict) and "error" in items[0] and len(items) == 1:
        raise ApifyFetchError(f"Apify 액터({actor}) 오류 응답: {items[0]['error']}")
    return items


def _resolve_brand_page(items: list[dict]) -> str | None:
    """브랜드명 키워드 검색 결과에는 리셀러·무관 광고주가 섞여 들어온다(§7-10 한계).

    정식 Page ID 확인 절차가 아직 없으므로, 검색 결과에서 가장 자주 등장한 page_name을
    실제 브랜드 페이지로 간주하는 근사 해석을 사용한다 — 정확한 Page 선택 UI(§7-10)가
    생기기 전까지의 임시 방편이며, 실제 사용 시 결과 화면에 어떤 페이지로 필터링됐는지
    항상 노출해야 한다(§13 투명성 원칙과 동일한 정신).
    """
    names = [it.get("page_name") for it in items if it.get("page_name")]
    if not names:
        return None
    return Counter(names).most_common(1)[0][0]


def _extract_media(snapshot: dict) -> tuple[str, str | None, str | None]:
    """(format, image_url, thumbnail_url) — thumbnail_url은 이미지/영상 공통 미리보기 1장."""
    videos = snapshot.get("videos") or []
    cards = snapshot.get("cards") or []
    images = snapshot.get("images") or []

    if videos:
        v = videos[0]
        image_url = v.get("video_hd_url") or v.get("video_sd_url")
        return "video", image_url, v.get("video_preview_image_url")
    if cards:
        c = cards[0]
        if c.get("video_hd_url") or c.get("video_sd_url"):
            return "carousel", c.get("video_hd_url") or c.get("video_sd_url"), c.get("video_preview_image_url")
        img = c.get("original_image_url") or c.get("resized_image_url")
        return "carousel", img, c.get("resized_image_url") or img
    if images:
        img = images[0]
        url = img.get("original_image_url") or img.get("resized_image_url")
        return "image", url, img.get("resized_image_url") or url
    return "unknown", None, None


@lru_cache(maxsize=64)
def _fetch_meta_ads_raw(
    brand_name: str, count: int = 20, page_override: str | None = None,
) -> tuple[str | None, tuple[dict, ...]]:
    """Apify 원본 호출 — 브랜드당(+page_override 조합당) 1회만 호출되도록 캐시(브랜드분석·소재분석이
    같은 세션에서 중복 과금되지 않게 함, §12 캐시 정책과 같은 취지). 반환: (resolved_page_name, ad dict 튜플).

    page_override(§7-10 최빈값 추정의 한계 보완용, STEP1 확인 화면 등에서 사용자가 직접 지정):
    - "http"로 시작하면 사용자가 Meta Ads Library에서 직접 복사한 검색 URL로 간주해 그대로 사용하고,
      최빈값 추정 없이 응답 전체를 그 페이지의 광고로 취급한다.
    - 그 외 문자열이면 그 값으로 검색하고, 최빈값 대신 정확히 그 페이지명과 일치하는 광고만 사용한다.
    """
    if page_override and page_override.startswith("http"):
        search_url = page_override
    else:
        query = urllib.parse.quote(page_override or brand_name)
        search_url = (
            "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            f"&country=KR&q={query}&search_type=keyword_unordered&media_type=all"
        )
    raw_items = _run_actor_sync(
        settings.APIFY_META_ADS_ACTOR,
        {"urls": [{"url": search_url}], "count": max(count, 10), "scrapeAdDetails": False},
    )
    if page_override and page_override.startswith("http"):
        resolved_page = raw_items[0].get("page_name") if raw_items else None
        page_items = raw_items
    elif page_override:
        resolved_page = page_override
        page_items = [it for it in raw_items if it.get("page_name") == page_override]
    else:
        resolved_page = _resolve_brand_page(raw_items)
        page_items = [it for it in raw_items if it.get("page_name") == resolved_page] if resolved_page else raw_items

    today = date.today()
    ads = []
    for it in page_items:
        snap = it.get("snapshot") or {}
        fmt, image_url, thumbnail_url = _extract_media(snap)
        body = snap.get("body")
        body_text = body if isinstance(body, str) else (body or {}).get("text", "")
        start_ts = it.get("start_date")
        start_date = datetime.fromtimestamp(start_ts).date() if start_ts else None
        ads.append({
            "ad_id": str(it.get("ad_archive_id") or it.get("ad_id") or ""),
            "brand": brand_name,
            "resolved_page_name": resolved_page,
            "platform": "meta",
            "publisher_platforms": ",".join(it.get("publisher_platform") or []),
            "format": fmt,
            "headline": snap.get("title") or snap.get("page_name") or "",
            "body": body_text or "",
            "cta": snap.get("cta_text") or "",
            "landing_url": snap.get("link_url") or "",
            "image_url": image_url,
            "thumbnail_url": thumbnail_url,
            "ad_delivery_start_time": start_date.isoformat() if start_date else None,
            "ad_running_days": (today - start_date).days if start_date else None,
            "collected_at": today.isoformat(),
        })
    return resolved_page, tuple(ads)


_HEADLINE_POOL = [
    "지금 바로 확인해보세요",
    "첫 구매 20% 할인 혜택",
    "이번 시즌 신제품 출시",
    "믿을 수 있는 선택",
    "지금이 가장 좋은 타이밍",
    "한정 수량, 서두르세요",
]
_BODY_POOL = [
    "많은 고객이 선택한 이유를 확인해보세요.",
    "전문가가 인정한 품질을 경험해보세요.",
    "지금 가입하면 특별한 혜택이 기다립니다.",
    "리뷰로 검증된 만족도를 직접 확인하세요.",
]
_CTA_POOL = ["지금 구매하기", "자세히 보기", "무료 상담 신청", "지금 가입하기"]
_THUMB_COLORS = ["#3B4252", "#4C566A", "#5E4B56", "#455A64", "#4E4436", "#3E4A45"]


def _mock_thumb_data_uri(label: str, seed_idx: int) -> str:
    """네트워크 호출 없이 즉석에서 만드는 목업 썸네일(SVG data URI).

    picsum.photos 같은 외부 이미지 서비스를 쓰면 목업 광고 수십 건마다 실제 네트워크
    요청이 발생해 HTML/ZIP 생성이 느려지거나(§16-5 다운로드), 오프라인 환경에서는 아예
    실패한다 — 그래서 목업은 항상 로컬에서 즉시 만들어지는 SVG로 대체한다.
    """
    color = _THUMB_COLORS[seed_idx % len(_THUMB_COLORS)]
    safe_label = html.escape(label[:14])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">'
        f'<rect width="160" height="160" fill="{color}"/>'
        f'<text x="50%" y="50%" font-size="13" fill="#F2F2F0" text-anchor="middle" '
        f'dy=".35em" font-family="sans-serif">{safe_label}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _mock_ads_detail(brand_name: str) -> list[dict]:
    rng = _seeded_random(f"meta_ads:{brand_name}")
    ad_count = rng.randint(0, 40)
    formats = ["image", "video", "carousel"]
    detail_rng = _seeded_random(f"meta_ads_detail:{brand_name}")
    today = date.today()

    ads = []
    for i in range(ad_count):
        start = today - timedelta(days=detail_rng.randint(1, 150))
        publisher_platforms = detail_rng.choice([["FACEBOOK"], ["INSTAGRAM"], ["FACEBOOK", "INSTAGRAM"]])
        fmt = detail_rng.choice(formats)
        ads.append({
            "ad_id": f"{brand_name}-{i:03d}",
            "brand": brand_name,
            "resolved_page_name": brand_name,
            "platform": "meta",
            "publisher_platforms": ",".join(publisher_platforms),
            "format": fmt,
            "headline": detail_rng.choice(_HEADLINE_POOL),
            "body": detail_rng.choice(_BODY_POOL),
            "cta": detail_rng.choice(_CTA_POOL),
            "landing_url": f"https://www.{brand_name.lower().replace(' ', '')}.example.com/lp/{i}?utm_campaign=meta",
            # 네트워크 호출 없는 로컬 SVG 플레이스홀더 — HTML/ZIP 생성이 외부 이미지 서비스
            # 가용성에 의존하지 않도록 한다(위 _mock_thumb_data_uri 참고).
            "image_url": _mock_thumb_data_uri(f"{brand_name} #{i}", i),
            "thumbnail_url": _mock_thumb_data_uri(f"{brand_name} #{i}", i),
            "ad_delivery_start_time": start.isoformat(),
            "ad_running_days": (today - start).days,
            "collected_at": today.isoformat(),
        })
    return ads


def fetch_meta_ads_detail(brand_name: str, page_override: str | None = None) -> list[dict]:
    """§7-11-(4) `09_Ads` — 소재분석 전용 개별 광고 상세 목록(브랜드당 1회, 캐시 공유).

    page_override: 자동 매칭(§7-10 최빈값 추정)이 부정확할 때 사용자가 직접 지정한 Meta Ads
    Library URL 또는 정확한 페이지명. 목업 모드에서는 실제 페이지 매칭이 존재하지 않아 무시한다.
    """
    if settings.APIFY_MOCK:
        return _mock_ads_detail(brand_name)
    _, ads = _fetch_meta_ads_raw(brand_name, page_override=page_override)
    return list(ads)


def fetch_meta_ads(brand_name: str) -> dict:
    """§7-3 meta_ads/ad_count/format_mix/key_message 등 — 브랜드분석에 필요한 요약 수준.

    실연동 시 fetch_meta_ads_detail()과 같은 캐시를 공유하므로, 브랜드분석·소재분석을 같은
    세션에서 둘 다 실행해도 Apify 호출은 브랜드당 1번만 발생합니다.
    """
    ads = fetch_meta_ads_detail(brand_name)
    ad_count = len(ads)
    format_mix = dict(Counter(a["format"] for a in ads))
    key_messages = list(dict.fromkeys(a["cta"] for a in ads if a["cta"]))[:3] or ["활성 광고 없음"]
    return {
        "brand": brand_name,
        "ad_count": ad_count,
        "format_mix": format_mix,
        "key_message": key_messages,
        "recent_activity": ad_count > 0,
        "is_active_only": True,
    }


def fetch_instagram_profile(brand_name: str) -> dict:
    """§7-3 instagram — 팔로워/포스팅 수 등 SNS 운영현황 (광고 아님).

    실제 Apify Instagram 프로필 액터는 handle 입력이 필수라 브랜드명→handle 해석이 먼저
    필요합니다(§7-10과 같은 미해결 문제). 그 전까지는 목업으로 유지합니다.
    """
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
