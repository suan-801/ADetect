"""자사·경쟁사 동일 스키마, 소스별 실패 격리, 근거 없는 판단 금지."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from config import settings
from core.analyzers.recommender import recommend_search_inputs
from core.analyzers.evidence import interpret, unavailable
from core.analyzers.market_analyzer import news_windows
from core.scrapers.naver_api import get_comparable_brand_trends, get_brand_keyword_metrics, get_news
from core.scrapers.ad_library import fetch_meta_ads_detail, fetch_instagram_profile
from core.scrapers.brand_site import crawl_brand_website
from core.scrapers.youtube import fetch_youtube
from core.scrapers.naver_serp import capture_search


def run_brand_analysis(brand_name, competitors, *, collect_instagram=True, collect_youtube=False,
                       collect_naver_sa=True, collect_news=True, sources=None, variants=None, on_progress=None, representative_keyword=None, generic_keywords=None):
    from core.jobs import checkpoint
    checkpoint("공통 검색지수 조회 중")
    sources, variants = sources or {}, variants or {}
    demo = settings.NAVER_DATALAB_MOCK and settings.APIFY_MOCK and settings.GEMINI_MOCK
    names = list(dict.fromkeys([brand_name, *competitors]))
    for competitor in names[1:]:
        variants.setdefault(competitor, recommend_search_inputs(competitor)["variants"])
    trends = get_comparable_brand_trends(brand_name, names[1:], variants)
    profiles, errors = [], []
    for name in names:
        checkpoint(f"{name} 브랜드 수집 중", {"own": profiles[0] if profiles else {}, "competitors":profiles[1:]})
        if on_progress:
            on_progress(f"{name} — 검색·홈페이지·광고 수집")
        configured = sources.get(name, {})
        problems = []
        sv = {**trends[name], "gender_ratio": None, "demographics": "unavailable"}
        if sv.get("status") == "not_available":
            problems.append("검색지수 수집 실패")
        try:
            metrics = get_brand_keyword_metrics(name, variants.get(name))
        except Exception:
            metrics = {"absolute_30d_pc": None, "absolute_30d_mobile": None, "related_keywords": [], "status": "not_available"}
        sv.update(metrics)
        checkpoint(f"{name} 홈페이지 수집 중")
        website = crawl_brand_website(name, configured.get("detail_url"), configured.get("homepage"))
        try:
            if name == brand_name and not settings.APIFY_MOCK and not configured.get("meta_page"):
                raise ValueError("자사 Meta 페이지 확인 필요")
            ads = fetch_meta_ads_detail(name, page_override=configured.get("meta_page") or None)
            ads_status = "available"
        except Exception:
            ads, ads_status = [], "not_available"
            problems.append("Meta 광고 수집 실패")
        try:
            news = get_news(name, scope="brand", limit=100) if collect_news else []
            news_status = "available" if collect_news else "not_collected"
        except Exception:
            news, news_status = [], "not_available"
            problems.append("뉴스 수집 실패")
        checkpoint(f"{name} SNS 수집 중")
        handle = configured.get("instagram") or next((u for u in website["social_links"] if "instagram.com" in u), None)
        instagram = fetch_instagram_profile(name, handle) if collect_instagram else {"status": "not_collected", "not_collected": True}
        youtube = fetch_youtube(configured.get("youtube")) if collect_youtube else {"status": "not_collected"}
        keywords = list(dict.fromkeys([representative_keyword or brand_name, *(generic_keywords or [])]))
        rankings = [capture_search(k, name, "brand_rep" if i == 0 else "generic", configured.get("homepage"), observe_rotations=3 if k == name else 1) for i,k in enumerate(keywords)] if collect_naver_sa else []
        brand_capture = next((r for r in rankings if r["keyword"] == name), None)
        if collect_naver_sa and brand_capture is None:
            brand_capture = capture_search(name,name,"brand_rep",configured.get("homepage"),observe_rotations=3)
        brand_search = (brand_capture or {}).get("brand_search") or unavailable("브랜드검색 광고를 확인하지 못했습니다.", "not_available" if collect_naver_sa else "not_collected")
        website_facts = [{"source": website["source_url"], "text": t} for t in website["raw_copy_snippets"]]
        ad_facts = [] if settings.APIFY_MOCK else [{"source": "Meta:"+str(a["ad_id"]), "text": (a.get("headline") or "")+"\n"+(a.get("body") or "")} for a in ads]
        checkpoint(f"{name} 근거 분석 중")
        context_fields = ["brand_type", "business_model", "offering_type", "conversion_objective"]
        site_ai = interpret(["brand_website_target_message", "promotion_interpretation", *context_fields], website_facts,
                            "브랜드 유형은 정해진 선택지로 강제하지 마세요. 프로모션을 의미하는 원문이 없다면 해석하지 마세요.")
        context = {k: site_ai[k].get("insight", "unknown") for k in context_fields}
        context.update(analysis_scope="brand", confidence="low", evidence={k:site_ai[k] for k in context_fields})
        ai = {k:site_ai[k] for k in ("brand_website_target_message", "promotion_interpretation")}
        ai.update(interpret(["key_message", "usp", "creative_type"], ad_facts,
                            "여러 메시지 패턴이 있으면 하나로 합치지 말고 모두 서술하세요."))
        if not demo:
            required = {"홈페이지":website.get("status"), "절대 검색량":metrics.get("status")}
            if collect_instagram:
                required["Instagram"] = instagram.get("status")
            if collect_youtube:
                required["YouTube"] = youtube.get("status")
            if collect_naver_sa and any(r.get("status") != "available" for r in rankings):
                problems.append("네이버 광고 일부 미확인")
            for source, state in required.items():
                if state not in ("available", "channel_not_found"):
                    problems.append(source+" 미수집 또는 실패")
            if any(value.get("status") for value in ai.values()):
                problems.append("일부 AI 해석 근거 부족 또는 호출 실패")
        format_mix = {}
        utm = []
        for ad in ads:
            fmt = ad.get("format") or "unknown"
            format_mix[fmt] = format_mix.get(fmt, 0)+1
            params = parse_qs(urlsplit(ad.get("landing_url") or "").query)
            utm.append({"brand": name, "ad_id": ad.get("ad_id"), **{k: v[0] for k,v in params.items() if k.startswith("utm_")}})
        p = {"brand": name, "is_own": name == brand_name, "brand_search_volume": sv,
             "brand_related_keywords": metrics["related_keywords"], "brand_website_facts": website,
             "brand_news": news, "brand_news_windows": news_windows(news), "news_status": news_status,
             "meta_ads": {"ads": ads, "status": ads_status}, "ads": ads, "ad_count": len(ads) if ads_status == "available" else None,
             "format_mix": format_mix, "collection_scope": "Meta 최대 20건 수집 표본", "instagram": instagram, "brand_context": context,
             "youtube": youtube,
             "naver_brand_search": brand_search,
             "naver_sa_ranking": rankings, "meta_utm": utm,
             "media_operation_matrix_row": {"naver_sa": True if any(r.get("has_ad") is True for r in rankings) else False if rankings and all(r.get("has_ad") is False for r in rankings) else None, "naver_brand_search": brand_search.get("has_ad"),
                 "meta_ads": bool(ads) if ads_status == "available" else None,
                 "instagram_profile": True if instagram.get("profile_found") else None, "youtube_channel": True if youtube.get("status") == "available" else False if youtube.get("status") == "channel_not_found" else None},
             "sample_sources": [k for k,v in (("search",settings.NAVER_DATALAB_MOCK), ("meta_ads",settings.APIFY_MOCK), ("news",collect_news and settings.NAVER_SEARCH_MOCK)) if v],
             "errors": problems, "collected_at": datetime.now(timezone.utc).isoformat(), **ai}
        profiles.append(p)
        errors.extend(f"{name}: {e}" for e in problems)
    own = profiles[0]
    any_core = any(p["brand_search_volume"].get("relative_trend") or p["meta_ads"]["status"] == "available" for p in profiles)
    return {"status": "전체 실패" if not any_core else "부분 실패" if errors else "완료", "own": own,
            "competitors": profiles[1:], "errors": errors, "brand_context": own["brand_context"],
            "comparison_insight": unavailable("종합분석에서 수집 근거를 비교합니다."),
            "sample_sources": sorted(set(s for p in profiles for s in p["sample_sources"]))}
