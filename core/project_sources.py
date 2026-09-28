"""프로젝트 흐름의 자료 종류별 수집 (결과 schema_version=6).

- 비교에 필요한 자료(검색 추이·검색량·SNS)는 브랜드 단위로, 추가 자료(공식 페이지·Meta 광고·검색 화면)는
  사용자가 고른 브랜드만 수집한다. 선택하지 않은 자료 종류는 호출하지 않는다.
- 검색 추이는 자사·경쟁사 검색어 묶음을 한 요청으로 조회해 같은 기준으로 비교한다.
- 수집 원본과 표시 필터(뉴스 필터)는 분리한다. 필터 변경은 API를 다시 부르지 않는다.
"""
import base64
import copy
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit

from config import settings
from core import projects
from core.collection import record, error_message, paid_problem, TOKEN_MESSAGE, official_urls
from core.jobs import checkpoint, AnalysisCancelled

COMPARE_SOURCES = ("trend", "volume", "instagram", "youtube")
EXTRA_SOURCES = ("website", "meta", "search_capture")
PAID_SOURCES = {"instagram": "Apify", "meta": "Apify"}
# 여러 브랜드가 함께 쓰는 호스트는 경로 첫 부분까지 봐야 같은 판매자인지 알 수 있다.
SHARED_HOSTS = ("smartstore.naver.com", "m.smartstore.naver.com", "brand.naver.com", "m.brand.naver.com", "shopping.naver.com")
AD_STATES = ("관측 시 노출 확인", "이번 화면에서 미관측", "판독 불가")


def _host(url):
    try:
        return (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def official_targets(brand):
    """공식 도메인 근거 목록 [(host, 경로 첫 부분 또는 None)]."""
    src = brand.get("sources", {})
    targets = []
    for url in official_urls(src):
        host = _host(url)
        if not host:
            continue
        first = urlsplit(url if "://" in url else "https://" + url).path.strip("/").split("/")[0].lower()
        targets.append((host, first if host.removeprefix("m.") in [h.removeprefix("m.") for h in SHARED_HOSTS] and first else None))
    return list(dict.fromkeys(targets))


def _domain_match(value, targets):
    if not value:
        return None
    host = _host(value)
    try:
        path = urlsplit(value if "://" in value else "https://" + value).path.strip("/").split("/")[0].lower()
    except ValueError:
        return None
    for t_host, t_path in targets:
        same = host == t_host or host.endswith("." + t_host) or host.removeprefix("m.") == t_host.removeprefix("m.")
        if same and (t_path is None or path == t_path):
            return value
    return None


def ad_status(observation, brand):
    """한 번의 관측에서 브랜드 광고 노출 상태. 캡처 실패·차단·영역 식별 실패는 '판독 불가'다."""
    if observation.get("state") not in ("captured", "sample"):
        return {"state": "판독 불가", "evidence": observation.get("message") or "캡처 실패"}
    areas = observation.get("areas", {})
    ads = [dict(ad, area=name, method="페이지 직접 추출") for name, a in areas.items() if a.get("identified") for ad in a.get("ads", [])]
    ads += [dict(text=" ".join(x for x in (ad.get("advertiser_visible"), ad.get("copy_visible")) if x), display_url=ad.get("display_url_visible"),
                 links=[], area=ad["area"], method="AI 판독")
            for ad in (observation.get("ai_read") or {}).get("ads", [])]
    identified = any(a.get("identified") for a in areas.values()) or (observation.get("ai_read") or {}).get("state") == "완료"
    if not identified:
        return {"state": "판독 불가", "evidence": "광고 영역을 식별하지 못함"}
    targets = official_targets(brand)
    mentioned = []
    for ad in ads:
        # 광고주 근거: 표시 URL·링크의 공식 도메인. 브랜드 표기만 일치하면 광고주를 확정하지 않는다.
        hit = _domain_match(ad.get("display_url"), targets) or next((l for l in ad.get("links", []) if _domain_match(l, targets)), None)
        if hit:
            return {"state": "관측 시 노출 확인", "evidence": f"{ad['area']} · 공식 도메인 {hit} ({ad['method']})"}
        if any(projects.term_key(t) in projects.term_key(ad.get("text", "")) for t in brand.get("terms", [])):
            mentioned.append(ad)
    if mentioned:
        return {"state": "판독 불가", "evidence": f"브랜드 표기가 있는 광고 {len(mentioned)}건 — 공식 도메인 근거 없음(광고주 미확정)"}
    return {"state": "이번 화면에서 미관측", "evidence": "식별한 광고 영역에서 공식 도메인·브랜드 표기 없음 (한 번의 관측, 미운영 판정 아님)"}


def _key_ok(source):
    if settings.SAMPLE_MODE:
        return True
    return {"trend": not settings.NAVER_DATALAB_MOCK, "volume": not settings.NAVER_AD_MOCK, "news": not settings.NAVER_SEARCH_MOCK,
            "youtube": bool(settings.YOUTUBE_API_KEY), "instagram": bool(settings.APIFY_API_TOKEN), "meta": bool(settings.APIFY_API_TOKEN)}.get(source, True)


def capture_keywords(p, brand_ids):
    """검색 화면 관측 검색어: 선택 브랜드의 대표 표기(첫 검색어) + 시장 관심 검색어. 같은 검색어는 한 번만."""
    chosen = [b for b in p["brands"] if b["id"] in brand_ids]
    return projects.clean_terms([b["terms"][0] for b in chosen if b.get("terms")] + list(p.get("market_keywords", [])))


def readiness(source, p, paid_enabled=True):
    """(실행 가능 여부, 이유). 전체 선택·수집 전 안내에 쓰며 API를 호출하지 않는다."""
    brands = p["brands"]
    if source in PAID_SOURCES and not paid_enabled:
        return False, "유료 기능 OFF"
    if not _key_ok(source):
        return False, TOKEN_MESSAGE if source in PAID_SOURCES else "API 키 미설정 (설정 화면 확인)"
    if source == "news" and not p.get("news_keywords"):
        return False, "뉴스 검색어 미입력"
    field = {"website": None, "instagram": "instagram", "youtube": "youtube", "meta": "meta_page"}.get(source)
    if source == "website" and not any(official_urls(b.get("sources", {})) for b in brands):
        return False, "공식 URL 미입력"
    if field and not any(b.get("sources", {}).get(field) for b in brands):
        return False, "입력한 계정·페이지 없음"
    return True, ""


def default_brands(source, p, history=()):
    """자료 종류별 기본 수집 브랜드. 추가 자료는 자사만, 유료 SNS는 저장 자료가 없는 브랜드만."""
    field = {"instagram": "instagram", "youtube": "youtube", "meta": "meta_page"}.get(source)
    brands = [b for b in p["brands"] if not field or b.get("sources", {}).get(field)]
    if source == "website":
        brands = [b for b in brands if official_urls(b.get("sources", {}))]
    if source in EXTRA_SOURCES:
        brands = [b for b in brands if b["role"] == "own"]
    if source in PAID_SOURCES:
        done = {r.get("brand_id") for h in history if h["source"] == source and projects.available(h) for r in h["result"].get("records", [])}
        missing = [b for b in brands if b["id"] not in done]
        brands = missing or brands
    return [b["id"] for b in brands]


class _Run:
    def __init__(self):
        self.parts = {}

    def step(self, key, label, fn, blocked=None):
        checkpoint(label)
        if blocked:
            self.parts[key] = {"label": label, "state": "설정 필요", "message": blocked, "records": []}
            return
        try:
            value = fn()
            self.parts[key] = {"label": label, "state": value.pop("state", "완료"), **value}
        except AnalysisCancelled:
            raise
        except Exception as exc:
            self.parts[key] = {"label": label, "state": "실패", "message": error_message(exc), "records": []}


def _rec(kind, brand, source_url, text, **meta):
    return record(kind, brand["name"], source_url, text, brand_id=brand["id"], **meta)


def _sample_volume(term):
    seed = int(hashlib.sha256(term.encode()).hexdigest()[:6], 16)
    pc, mobile = 300 + seed % 4000, 900 + seed % 12000
    rows = [{"keyword": term, "monthly_pc_display": pc if seed % 5 else "< 10", "monthly_mobile_display": mobile}]
    return rows + [{"keyword": term + " 후기", "monthly_pc_display": 120, "monthly_mobile_display": 480}]


def _sample_observation(keyword):
    return {"keyword": keyword, "source_url": "https://search.naver.com/search.naver?query=" + keyword, "captured_at": datetime.now(timezone.utc).isoformat(),
            "environment": "SAMPLE — 실제 화면 미수집", "state": "sample", "screenshot": None,
            "areas": {"powerlink": {"identified": True, "ads": [{"title": f"SAMPLE {keyword} 광고", "text": f"SAMPLE {keyword} 광고 문구", "display_url": "sample.example.com", "links": ["https://sample.example.com/lp?utm_source=naver&utm_medium=cpc&utm_campaign=sample"]}]},
                      "brand_search": {"identified": False, "ads": []}}}


def collect(source, p, options=None):
    """자료 종류 하나를 수집해 v6 결과로 반환한다. p는 projects.project_inputs() 결과."""
    from core.evidence_store import save_bytes
    options = options or {}
    paid_enabled = p.get("paid_enabled", True)
    chosen_ids = options.get("brands") or default_brands(source, p)
    scoped = [b for b in p["brands"] if b["id"] in chosen_ids]
    own = projects.own_brand(p)
    run = _Run()
    if source == "trend":
        from core.scrapers.search_history import fetch_comparison, fetch_history, summarize_history
        blocked = None if _key_ok("trend") else "검색 추이 API 키 미설정"
        groups = [{"id": b["id"], "name": b["name"], "terms": b["terms"]} for b in p["brands"]]

        def compare():
            data = fetch_comparison(groups)
            data["signature"] = projects.comparison_signature(p["brands"])
            data["seasonality"] = {s["brand_id"]: summarize_history({"start": data["start"], "end": data["end"], "rows": s["rows"]}) for s in data["series"]}
            missing = [s["name"] for s in data["series"] if not s["provided"]]
            return {"comparison": data, "records": [], "state": "부분 완료" if missing else "완료",
                    **({"message": "응답에 없는 브랜드: " + ", ".join(missing)} if missing else {})}
        run.step("trend:compare", "브랜드 검색 추이 비교 (" + ", ".join(g["name"] for g in groups) + ")", compare, blocked)
        for kw in p.get("market_keywords", []):
            def market(k=kw):
                series = fetch_history(k)
                return {"series": series, "seasonality": summarize_history(series), "records": []}
            run.step("trend:market:" + kw, kw + " · 시장 관심 검색어 추이", market, blocked)
    elif source == "volume":
        from core.scrapers.naver_ad_api import fetch_keyword_stats
        blocked = None if _key_ok("volume") else "검색광고 API 키 미설정"
        targets = [(b, b["terms"]) for b in p["brands"]]
        market = {"id": "market", "name": "시장 관심 검색어", "role": "market"}
        targets += [(market, list(p.get("market_keywords", [])))] if p.get("market_keywords") else []
        for brand, terms in targets:
            def volume(b=brand, ts=terms):
                records, statuses = [], []
                for term in projects.clean_terms(ts):
                    checkpoint(b["name"] + " · " + term + " 검색량")
                    try:
                        rows = _sample_volume(term) if settings.SAMPLE_MODE else fetch_keyword_stats(term.replace(" ", ""))
                    except AnalysisCancelled:
                        raise
                    except Exception as exc:
                        statuses.append({"term": term, "state": "실패", "message": error_message(exc)})
                        continue
                    exact = [r for r in rows if projects.term_key(r["keyword"]) == projects.term_key(term)]
                    if exact:
                        r = exact[0]
                        pc, mobile = r.get("monthly_pc_display", r.get("monthly_pc")), r.get("monthly_mobile_display", r.get("monthly_mobile"))
                        statuses.append({"term": term, "state": "완료", "pc": pc, "mobile": mobile})
                        records.append(_rec("검색량", b, "https://searchad.naver.com/", term, keyword=term, pc=pc, mobile=mobile))
                    else:
                        statuses.append({"term": term, "state": "미제공"})
                    related = [r for r in rows if projects.term_key(r["keyword"]) != projects.term_key(term)][:10]
                    records += [_rec("연관 검색어", b, "https://searchad.naver.com/", r["keyword"], keyword=term,
                                     pc=r.get("monthly_pc_display", r.get("monthly_pc")), mobile=r.get("monthly_mobile_display", r.get("monthly_mobile"))) for r in related]
                bad = [s for s in statuses if s["state"] != "완료"]
                return {"records": records, "terms": statuses, "brand_id": b["id"],
                        "state": "완료" if not bad else "부분 완료" if len(bad) < len(statuses) else "실패",
                        **({"message": f"{len(bad)}개 검색어 미제공·실패"} if bad else {})}
            run.step("volume:" + brand["id"], brand["name"] + " · 월간 검색량", volume, blocked)
    elif source == "news":
        from core.scrapers.naver_api import get_news
        if not p.get("news_keywords"):
            run.step("news", "관련 뉴스", None, "뉴스 검색어가 없어 요청하지 않았습니다.")
        blocked = None if _key_ok("news") else "네이버 뉴스 API 키 미설정"
        for kw in p.get("news_keywords", []):
            def news(k=kw):
                rows = []
                for n in get_news(k, scope="market", limit=100):
                    text = n["title"] + "\n" + n["summary"]
                    found = [b["name"] for b in p["brands"] if any(projects.term_key(t) in projects.term_key(text) for t in b["terms"])]
                    rows.append(_rec("뉴스", own, n["url"], text, keyword=k, title=n["title"], excerpt=n["summary"],
                                     published_at=n.get("published_at"), found_brands=found))
                return {"records": rows}
            run.step("news:" + kw, kw + " · 뉴스", news, blocked)
    elif source == "website":
        from core.scrapers.brand_site import crawl_brand_website
        from core.evidence_store import capture_website
        for brand in scoped:
            targets = official_urls(brand.get("sources", {}))
            if not targets:
                run.step("site:" + brand["id"], brand["name"] + " · 공식 페이지", None, "공식 URL 미입력")
            for i, url in enumerate(targets):
                def website(b=brand, u=url):
                    if settings.SAMPLE_MODE:
                        return {"records": [_rec("홈페이지", b, u, "SAMPLE 페이지 원문", coverage="SAMPLE — 실제 사이트 미수집", assets=[])]}
                    data = crawl_brand_website(b["name"], u)
                    captured = capture_website(u, save_images=p.get("save_images", True))
                    return {"records": [_rec("홈페이지", b, captured["source_url"], captured["visible_text"], raw_copy_snippets=data["raw_copy_snippets"],
                                             assets=captured["assets"], links=captured["links"], coverage=captured["coverage"], image_count=captured["image_count"],
                                             warnings=captured["warnings"])],
                            "state": "부분 완료" if captured["warnings"] else "완료"}
                run.step(f"site:{brand['id']}:{i}", brand["name"] + " · " + (_host(url) or url), website)
    elif source == "search_capture":
        from core.scrapers.naver_serp import observe_search
        ai_allowed = options.get("ai_read", True) and paid_enabled and not paid_problem(p, "Gemini")
        for kw in capture_keywords(p, chosen_ids):
            def search(k=kw):
                obs = _sample_observation(k) if settings.SAMPLE_MODE else observe_search(k)
                if obs["state"] not in ("captured", "sample"):
                    raise ValueError(obs.get("message") or "검색 화면 캡처 실패")
                assets = []
                if obs.get("screenshot"):
                    assets.append({**save_bytes(obs["screenshot"], "png", obs["source_url"]), "role": "첫 화면"})
                for name, area in obs["areas"].items():
                    if area.get("screenshot"):
                        assets.append({**save_bytes(area["screenshot"], "png", obs["source_url"]), "role": {"powerlink": "파워링크 영역", "brand_search": "브랜드검색 영역"}[name]})
                if ai_allowed:
                    from core.capture_reader import needs_reading, read_capture
                    shot = next((a.get("screenshot") for a in obs["areas"].values() if needs_reading(a) and a.get("screenshot")), None) or (
                        obs.get("screenshot") if any(needs_reading(a) for a in obs["areas"].values()) else None)
                    if shot:
                        obs["ai_read"] = read_capture(shot)
                statuses = {b["id"]: {"name": b["name"], **ad_status(obs, b)} for b in p["brands"]}
                ads = [{"area": name, "method": "페이지 직접 추출", **{k: ad.get(k) for k in ("title", "text", "display_url", "links")}}
                       for name, a in obs["areas"].items() for ad in a.get("ads", [])]
                found = sum(len(a.get("ads", [])) for a in obs["areas"].values())
                areas = ", ".join(f"{ {'powerlink': '파워링크', 'brand_search': '브랜드검색'}[n] } {'식별' if a.get('identified') else '식별 실패'}" for n, a in obs["areas"].items())
                return {"records": [_rec("검색 화면", own, obs["source_url"], f"광고 {found}건 직접 추출 · {areas}", keyword=k,
                                         environment=obs["environment"], observed_at=obs["captured_at"], capture_state=obs["state"],
                                         areas={n: {"identified": a.get("identified", False)} for n, a in obs["areas"].items()},
                                         ads=ads, ai_read=obs.get("ai_read"), brand_status=statuses, assets=assets)]}
            run.step("search:" + kw, kw + " · 검색 화면", search)
    elif source in ("instagram", "youtube", "meta"):
        field = {"instagram": "instagram", "youtube": "youtube", "meta": "meta_page"}[source]
        problem = paid_problem(p, PAID_SOURCES[source]) if source in PAID_SOURCES else (None if _key_ok("youtube") else "YouTube API 키 미설정")
        for brand in scoped:
            account = brand.get("sources", {}).get(field)
            blocked = problem or (None if account else "계정·페이지 미입력 — 건너뜀")
            run.step(f"{source}:{brand['id']}", brand["name"] + " · " + projects.SOURCES[source][0], lambda b=brand, a=account: _social(source, b, a), blocked)
    else:
        raise ValueError("알 수 없는 자료 종류")
    records = [r for part in run.parts.values() for r in part.get("records", [])]
    result = {"schema_version": projects.RESULT_VERSION, "source": source, "parts": run.parts, "records": records,
              "errors": [pt["label"] + ": " + pt.get("message", "") for pt in run.parts.values() if pt["state"] not in ("완료",)],
              "sample_sources": ["SAMPLE"] if settings.SAMPLE_MODE else [], "collected_at": datetime.now(timezone.utc).isoformat(),
              "options": {"brands": [b["id"] for b in scoped] if source not in ("trend", "volume", "news") else [b["id"] for b in p["brands"]],
                          "ai_read": bool(options.get("ai_read", True)) if source == "search_capture" else None}}
    return projects.normalize(result, source, projects.to_storage(p))


def _social(source, brand, account):
    now = datetime.now(timezone.utc).isoformat()
    if source == "instagram":
        from core.scrapers.ad_library import fetch_instagram_profile
        data = {"status": "available", "followers": 12000, "posts": 340, "recent_posts": [], "source_url": "https://www.instagram.com/sample/"} if settings.SAMPLE_MODE else fetch_instagram_profile(brand["name"], account)
        if data.get("status") != "available":
            raise ValueError(data.get("message") or "Instagram 계정 조회 실패 (비공개·미존재 포함)")
        link = data.get("source_url") or account
        rows = [_rec("Instagram", brand, link, "공식 계정", followers=data.get("followers"), post_count=data.get("posts"), observed_at=now)]
        rows += [_rec("Instagram 게시물", brand, x.get("url") or link, x.get("caption", ""), published_at=x.get("timestamp"), external_id=str(x.get("id") or x.get("url"))) for x in data.get("recent_posts", [])]
        return {"records": rows}
    if source == "youtube":
        from core.scrapers.youtube import fetch_youtube
        data = {"status": "available", "source_url": "https://www.youtube.com/@sample", "subscribers": "15000", "videos": "210", "recent_content": []} if settings.SAMPLE_MODE else fetch_youtube(account)
        if data.get("status") != "available":
            raise ValueError(data.get("message") or ("채널을 찾을 수 없음" if data.get("status") == "channel_not_found" else "YouTube 조회 실패"))
        rows = [_rec("YouTube", brand, data["source_url"], "공식 채널", subscribers=data.get("subscribers"), videos=data.get("videos"), observed_at=now,
                     note="YouTube 구독자 수는 API가 반올림한 값을 제공합니다.")]
        for v in data.get("recent_content", []):
            if not v.get("video_id"): continue
            assets, warnings = _thumbnail(v.get("thumbnail_url"))
            rows.append(_rec("YouTube 게시물", brand, "https://www.youtube.com/watch?v=" + str(v["video_id"]), v["title"],
                             published_at=v.get("published_at"), format="video", assets=assets,
                             thumbnail_url=v.get("thumbnail_url"), warnings=warnings))
        return {"records": rows}
    from core.scrapers.ad_library import fetch_meta_ads_detail
    from core.evidence_store import fetch_asset
    rows = []
    for ad in fetch_meta_ads_detail(brand["name"], page_override=account):
        checkpoint(brand["name"] + " · 광고 원본 저장 중")
        assets, warnings = _thumbnail(ad.get("thumbnail_url"))
        if ad.get("image_url") and not settings.SAMPLE_MODE:
            try:
                if not any(a.get("source_url") == ad["image_url"] for a in assets):
                    assets.append(fetch_asset(ad["image_url"]))
            except Exception:
                warnings.append("광고 원본 저장 실패 · 광고 원문에서 확인하세요.")
        rows.append(_rec("광고", brand, "https://www.facebook.com/ads/library/?id=" + str(ad["ad_id"]), (ad.get("headline") or "") + "\n" + (ad.get("body") or ""),
                         external_id=str(ad["ad_id"]), landing_url=ad.get("landing_url"), format=ad.get("format"), cta=ad.get("cta"),
                         start_date=ad.get("ad_delivery_start_time"), running_days=ad.get("ad_running_days"), placements=ad.get("publisher_platforms"),
                         assets=assets, thumbnail_url=ad.get("thumbnail_url"), warnings=warnings))
    return {"records": rows}


def _thumbnail(url):
    """수집 응답에 실제 포함된 미리보기만 저장한다. AI·추가 API 호출 없음."""
    if not url or settings.SAMPLE_MODE: return [], []
    from core.evidence_store import fetch_asset
    try:
        asset = fetch_asset(url, maximum=6*1024**2)
        if not asset["filename"].lower().endswith((".png", ".jpg", ".webp", ".gif")):
            return [], ["썸네일 응답이 이미지가 아닙니다."]
        return [{**asset, "role": "썸네일"}], []
    except Exception:
        return [], ["썸네일 저장 실패 · 원문에서 확인하세요."]


def utm_rows(p, records):
    """UTM 분석 대상: 수집된 광고 랜딩, 검색 화면 광고 링크, 프로젝트의 캠페인 상세 URL, 사용자가 추가한 URL."""
    from core import utm
    rows = []
    names = {b["id"]: b["name"] for b in p["brands"]}
    for r in records:
        if r.get("kind") == "광고" and r.get("landing_url"):
            rows.append(utm.parse(r["landing_url"], r.get("brand") or names.get(r.get("brand_id"), ""), "Meta 광고 랜딩"))
        if r.get("kind") == "검색 화면":
            for ad in r.get("ads", []):
                for link in ad.get("links", [])[:3]:
                    matched = [b["name"] for b in p["brands"] if _domain_match(link, official_targets(b))]
                    rows.append(utm.parse(link, ", ".join(matched) or "브랜드 미확정", "네이버 검색 광고 · " + r.get("keyword", "")))
    for b in p["brands"]:
        src = b.get("sources", {})
        if src.get("detail_url"):
            rows.append(utm.parse(src["detail_url"], b["name"], "프로젝트 입력 · 캠페인 상세 URL"))
        for url in src.get("utm_urls", []) or []:
            rows.append(utm.parse(url, b["name"], "프로젝트 입력 · 분석 대상 URL"))
    seen, output = set(), []
    for row in rows:
        key = (row["브랜드"], row["원본 URL"])
        if key not in seen and utm.has_values(row):
            seen.add(key); output.append(row)
    return output
