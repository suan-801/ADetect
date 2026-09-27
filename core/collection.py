"""팩트 수집 v2. 명시적 SAMPLE만 허용하며 유료 호출을 실행 단계에서 격리한다."""
import base64
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
from config import settings
from core.jobs import checkpoint, AnalysisCancelled
from core.runtime import persist_result, input_signature

TOKEN_MESSAGE="토큰 부족. 개발자에게 문의해주세요"
STAGES=("market","brand","creative","synthesis")
DEFAULT_OPTIONS={"news":True,"instagram":True,"youtube":True,"search_capture":True,"website":True,"meta":True,"summary":True}


def words(value):
    return list(dict.fromkeys(x.strip() for x in value.split(",") if x.strip()))


def query_groups(session):
    own=session.get("brand_keywords", session.get("variants",{}).get(session["brand_name"]) or [session["brand_name"]])
    general=session.get("general_keywords", session.get("generic_keywords") or ([session["category"]] if session.get("category") else []))
    return {"브랜드/캠페인":list(dict.fromkeys(own)),"일반":list(dict.fromkeys(general))}


def keyword_help(session):
    groups=query_groups(session)
    return [f"브랜드/캠페인 검색어: {', '.join(groups['브랜드/캠페인']) or '미입력'}을 기준으로 검색 추이·검색량·관련 뉴스·네이버 광고 화면을 수집합니다.",
            f"일반 검색어: {', '.join(groups['일반']) or '미입력'}을 기준으로 주제별 검색 추이·검색량·관련 뉴스·네이버 광고 화면을 수집합니다. 서로 다른 검색어를 합산하지 않습니다."]


def paid_problem(session, service):
    if not session.get("paid_enabled",True):
        return "유료 기능 OFF — 수집하지 않았습니다."
    if settings.SAMPLE_MODE:
        return None
    key=settings.APIFY_API_TOKEN if service=="Apify" else settings.GEMINI_API_KEY
    return None if key else TOKEN_MESSAGE


def error_message(exc):
    # Inspect, never persist raw SDK exceptions (which can include credentials).
    message=str(exc).lower()
    if TOKEN_MESSAGE in str(exc):
        return TOKEN_MESSAGE
    from core.retention import is_capacity_error, CAPACITY_MESSAGE
    if is_capacity_error(exc):
        return CAPACITY_MESSAGE
    cause=getattr(exc,"__cause__",None)
    if cause is not None:
        message += " " + str(cause).lower()
    if any(s in message for s in ("insufficient", "payment required", "quota exhausted", "credit", "token expired", "unauthorized", "401", "402")):
        return TOKEN_MESSAGE
    return "수집 실패 — 연결 상태·권한·수집 대상 주소를 확인해주세요."


def record(kind, brand, source_url, text, **metadata):
    stable=metadata.get("external_id") or source_url+"|"+metadata.get("keyword","")+"|"+(text if kind in ("검색량","연관 검색어") else "")
    return {"id":hashlib.sha256((kind+brand+stable).encode()).hexdigest()[:20],"kind":kind,"brand":brand,
            "source_url":source_url,"text":text,"collected_at":datetime.now(timezone.utc).isoformat(),
            "sample":settings.SAMPLE_MODE,"review":"확인 필요",**metadata}


def relevance(item, session):
    if not session.get("campaign"):
        return "포함", "브랜드 전체 조사"
    text=(item.get("text","")+" "+item.get("title","")).casefold()
    if any(w.casefold() in text for w in session.get("exclude_terms",[]) if w):
        return "제외", "설정한 제외 문구와 일치"
    target=session.get("sources",{}).get(session["brand_name"],{})
    landing=target.get("detail_url") or target.get("homepage")
    if landing and item.get("landing_url"):
        expected,actual=urlsplit(landing),urlsplit(item["landing_url"])
        if (expected.hostname,expected.path.rstrip('/'),expected.fragment)==(actual.hostname,actual.path.rstrip('/'),actual.fragment):
            return "포함", "조사 대상 랜딩 URL과 일치"
    if any(w.casefold() in text for w in session.get("include_terms",[]) if w):
        return "포함", "설정한 포함 문구와 일치"
    if item.get("kind")=="홈페이지":
        return "포함", "사용자가 지정한 조사 페이지"
    return "확인 필요", "캠페인 관련성을 자동 확인하지 못함"


def apply_reviews(rows, session):
    for row in rows:
        state,reason=relevance(row,session)
        row["review"],row["review_reason"]=state,reason
        saved=session.get("reviews",{}).get(row["id"])
        if saved:
            row.update(review=saved,review_reason="사용자 확인")
    return rows


def run_stage(stage, session, retry=False):
    options={**DEFAULT_OPTIONS,**session.get("collection_options",{})}
    old=session.get(stage+"_result",{}) if retry else {}
    parts={}
    def collect(key, label, fn, blocked=None):
        selected=session.get("source_selection")
        source={"trend":"trend","volume":"volume","news":"news","site":"website","search":"search_capture","instagram":"instagram","youtube":"youtube","meta":"meta"}.get(key.split(':')[0])
        if selected is not None and source not in selected:
            return
        checkpoint(label,{"schema_version":2,"parts":parts,"records":[r for p in parts.values() for r in p.get("records",[])]})
        if blocked:
            parts[key]={"label":label,"state":"미수집","message":blocked,"records":[]}
            return
        previous=old.get("parts",{}).get(key)
        if previous and previous.get("state")=="완료":
            parts[key]=previous
            return
        try:
            value=fn()
            parts[key]={"label":label,"state":"완료",**value}
        except AnalysisCancelled:
            raise
        except Exception as exc:
            parts[key]={"label":label,"state":"실패","message":error_message(exc),"records":[]}
    groups=query_groups(session)
    all_queries=list(dict.fromkeys(k for values in groups.values() for k in values))
    if stage=="market":
        from core.scrapers.search_history import fetch_history,summarize_history
        from core.scrapers.naver_api import get_news
        from core.scrapers.naver_ad_api import fetch_keyword_stats
        for keyword in all_queries:
            def history(k=keyword):
                series=fetch_history(k)
                return {"series":series,"seasonality":summarize_history(series),"records":[]}
            collect("trend:"+keyword,keyword+" · 3년 검색 추이",history, None if settings.SAMPLE_MODE or not settings.NAVER_DATALAB_MOCK else "검색 추이 API 키 미설정")
            def volume(k=keyword):
                if settings.SAMPLE_MODE:
                    rows=[{"keyword":k,"monthly_pc_display":"SAMPLE","monthly_mobile_display":"SAMPLE"}]
                else:
                    rows=fetch_keyword_stats(k.replace(" ",""))
                exact=[r for r in rows if r["keyword"].replace(" ","").casefold()==k.replace(" ","").casefold()]
                related=[r for r in rows if r not in exact][:20]
                result=[]
                for r in exact+related:
                    result.append(record("검색량" if r in exact else "연관 검색어",session["brand_name"],"https://searchad.naver.com/",r["keyword"],keyword=k,
                        pc=r.get("monthly_pc_display",r.get("monthly_pc")),mobile=r.get("monthly_mobile_display",r.get("monthly_mobile")),
                        note="조회 시점 API 월간 검색량. '<10'은 0이 아닙니다. 중복·연관어를 합산하지 않습니다."))
                return {"records":result,"message":"일치 검색어 미제공" if not exact else ""}
            collect("volume:"+keyword,keyword+" · 검색량",volume, None if settings.SAMPLE_MODE or not settings.NAVER_AD_MOCK else "검색광고 API 키 미설정")
            if options["news"]:
                def news(k=keyword):
                    rows=get_news(k,scope="market",limit=100)
                    return {"records":[record("뉴스",session["brand_name"],n["url"],n["title"]+"\n"+n["summary"],keyword=k,published_at=n.get("published_at"),note="뉴스 API 발췌문·최대 100건 표본. 기사 주장의 진위 확인은 별도.") for n in rows]}
                collect("news:"+keyword,keyword+" · 뉴스",news,None if settings.SAMPLE_MODE or not settings.NAVER_SEARCH_MOCK else "네이버 뉴스 API 키 미설정")
    elif stage=="brand":
        from core.scrapers.brand_site import crawl_brand_website
        from core.evidence_store import capture_website,save_bytes
        from core.scrapers.naver_serp import capture_search
        from core.scrapers.ad_library import fetch_instagram_profile
        from core.scrapers.youtube import fetch_youtube
        for brand in [session["brand_name"],*session.get("competitors",[])]:
            sources=session.get("sources",{}).get(brand,{})
            url=sources.get("detail_url") or sources.get("homepage")
            if options["website"]:
                def website(b=brand,u=url):
                    if settings.SAMPLE_MODE:
                        return {"records":[record("홈페이지",b,u or "https://example.com","SAMPLE 페이지 원문",coverage="SAMPLE — 실제 사이트 미수집",assets=[])]}
                    data=crawl_brand_website(b,u)
                    captured=capture_website(u, save_images=session.get("save_images",True))
                    return {"records":[record("홈페이지",b,captured["source_url"],captured["visible_text"],
                        raw_copy_snippets=data["raw_copy_snippets"],assets=captured["assets"],links=captured["links"],coverage=captured["coverage"],
                        image_count=captured["image_count"],warnings=captured["warnings"],note="페이지에 기재된 내용입니다. 혜택의 실제 이행 여부는 검증하지 않았습니다.")],
                        "state":"부분 완료" if captured["warnings"] else "완료"}
                collect("site:"+brand,brand+" · 홈페이지",website,None if url or settings.SAMPLE_MODE else "조사 페이지 URL 미입력")
            if options["instagram"]:
                handle=sources.get("instagram")
                def instagram(b=brand,h=handle):
                    if settings.SAMPLE_MODE:
                        data={"status":"available","followers":None,"recent_posts":[],"recent_caption_sample":"SAMPLE"}
                    else:
                        data=fetch_instagram_profile(b,h)
                    if data.get("status")!="available":
                        raise ValueError(data.get("message","Instagram 수집 실패"))
                    link=h if h and h.startswith("https://") else "https://www.instagram.com/"+(h or "sample").lstrip('@').strip('/')+"/"
                    posts=data.get("recent_posts",[])
                    rows=[record("Instagram",b,link,data.get("recent_caption_sample", ""),followers=data.get("followers"),post_count=data.get("posts"),note="확인된 계정의 최근 최대 5개 게시물 표본")]
                    rows += [record("Instagram 게시물",b,p.get("url") or link,p.get("caption", ""),published_at=p.get("timestamp"),external_id=str(p.get("id") or p.get("url"))) for p in posts]
                    return {"records":rows}
                collect("instagram:"+brand,brand+" · Instagram",instagram,paid_problem(session,"Apify") or (None if handle or settings.SAMPLE_MODE else "공식 Instagram 계정 미입력"))
            if options["youtube"]:
                channel=sources.get("youtube")
                def youtube(b=brand,c=channel):
                    if settings.SAMPLE_MODE:
                        return {"records":[]}
                    data=fetch_youtube(c)
                    if data.get("status")!="available":
                        raise ValueError("YouTube 수집 실패")
                    return {"records":[record("YouTube",b,data["source_url"],"공식 채널",subscribers=data.get("subscribers"),videos=data.get("videos"))]+
                            [record("YouTube 게시물",b,"https://www.youtube.com/watch?v="+str(v.get("video_id")),v["title"],published_at=v.get("published_at")) for v in data.get("recent_content",[])]}
                collect("youtube:"+brand,brand+" · YouTube",youtube,None if settings.SAMPLE_MODE or (channel and settings.YOUTUBE_API_KEY) else "공식 YouTube 채널 또는 API 키 미설정")
        if options["search_capture"]:
            for keyword in all_queries:
                def search(k=keyword):
                    if settings.SAMPLE_MODE:
                        return {"records":[record("검색 화면",session["brand_name"],"https://search.naver.com/", "SAMPLE 검색 화면",keyword=k,assets=[])]}
                    # Observation is a snapshot; do not infer rank or operation from a text match.
                    data=capture_search(k,session["brand_name"],observe_rotations=1)
                    encoded=data.get("capture_data_uri","")
                    if not encoded:
                        raise ValueError("검색 화면 캡처 실패")
                    asset=save_bytes(base64.b64decode(encoded.split(',',1)[1]),"png",data["source_url"])
                    return {"records":[record("검색 화면",session["brand_name"],data["source_url"],"관측 화면에서 광고 문구·광고주·랜딩을 직접 확인하세요. 자동 순위·미운영 판정은 제공하지 않습니다.",keyword=k,assets=[asset],observed_at=data["captured_at"])]}
                collect("search:"+keyword,keyword+" · 검색 화면",search)
    elif stage=="creative":
        from core.scrapers.ad_library import fetch_meta_ads_detail
        from core.evidence_store import fetch_asset
        if options["meta"]:
            for brand in [session["brand_name"],*session.get("competitors",[])]:
                page=session.get("sources",{}).get(brand,{}).get("meta_page")
                def ads(b=brand,p=page):
                    data=fetch_meta_ads_detail(b,page_override=p)
                    rows=[]
                    for ad in data:
                        checkpoint(b+" · 광고 원본 저장 중")
                        aid=str(ad["ad_id"])
                        assets=[]
                        note="Meta 요청당 최대 20건 표본. 전체 광고 수·성과가 아닙니다."
                        asset_url=ad.get("image_url")
                        if asset_url and not settings.SAMPLE_MODE and session.get("save_ad_assets",True):
                            try:
                                assets.append(fetch_asset(asset_url))
                            except Exception:
                                note+=" 원본 저장 실패 또는 25MB 한도 초과. 원문 링크에서 확인하세요."
                        rows.append(record("광고",b,"https://www.facebook.com/ads/library/?id="+aid,(ad.get("headline") or "")+"\n"+(ad.get("body") or ""),
                            external_id=aid,landing_url=ad.get("landing_url"),format=ad.get("format"),cta=ad.get("cta"),
                            start_date=ad.get("ad_delivery_start_time"),running_days=ad.get("ad_running_days"),placements=ad.get("publisher_platforms"),assets=assets,note=note))
                    return {"records":rows}
                collect("meta:"+brand,brand+" · Meta 광고",ads,paid_problem(session,"Apify") or (None if page or settings.SAMPLE_MODE else "공식 Meta 페이지 URL 미입력"))
    elif stage=="synthesis":
        return summarize_selected(session)
    records=list({r["id"]:r for p in parts.values() for r in p.get("records",[])}.values())
    apply_reviews(records,session)
    successful=sum(p["state"]=="완료" for p in parts.values())
    errors=[p["label"]+": "+p.get("message","일부 원본 미확보") for p in parts.values() if p["state"]!="완료"]
    previous=session.get(stage+"_result",{})
    old_records={r["id"]:r for r in previous.get("records",[])}
    current={r["id"]:r for r in records}
    changes=[]
    if previous.get("schema_version")==2:
        for rid,r in current.items():
            if rid not in old_records:
                changes.append({"자료ID":rid,"변화":"이번 수집에서 추가 관측","종류":r["kind"],"출처":r["source_url"]})
            elif any(r.get(k)!=old_records[rid].get(k) for k in ("text","landing_url","cta","pc","mobile","followers","subscribers")):
                changes.append({"자료ID":rid,"변화":"원문 또는 관측값 변경","종류":r["kind"],"출처":r["source_url"]})
        changes += [{"자료ID":rid,"변화":"이번 수집에서 미관측 (삭제 확정 아님)","종류":r["kind"],"출처":r["source_url"]} for rid,r in old_records.items() if rid not in current]
    return {"schema_version":2,"status":"완료" if not errors else "부분 실패" if successful or records else "전체 실패",
            "stage":stage,"records":records,"parts":parts,"errors":errors,"sample_sources":["SAMPLE"] if settings.SAMPLE_MODE else [],
            "changes":changes,
            "collected_at":datetime.now(timezone.utc).isoformat(),"inputs":{"groups":groups,"campaign":session.get("campaign"),"country":"KR"},
            "limitations":["기록된 시점·검색 조건의 수집 표본입니다. 누락은 미운영 또는 검색량 0을 뜻하지 않습니다."]}


def all_records(session):
    records={r["id"]:dict(r) for stage in STAGES[:3] for r in session.get(stage+"_result",{}).get("records",[])}
    return apply_reviews(list(records.values()),session)


def summarize_selected(session):
    from core.analyzers.evidence import interpret,unavailable
    rows=all_records(session)
    selected=set(session.get("selected_records",[]))
    chosen=[r for r in rows if r["id"] in selected and r["review"]!="제외"]
    problem=paid_problem(session,"Gemini")
    if not session.get("collection_options",{}).get("summary",True):
        problem="근거 요약 선택 해제"
    summary=unavailable(problem or "요약할 자료를 선택해주세요.")
    if chosen and not problem:
        summary=interpret(["fact_summary"],[{"source":r["source_url"],"text":r["text"],"sample":r.get("sample")} for r in chosen],
            "선택 자료에 실제로 적힌 내용과 공통 문구만 요약하세요. 효과·타깃·전략·차별화·미래·점유율을 추론하지 마세요. 브랜드 주장은 '페이지에 기재됨'으로 표현하고 조건을 생략하지 마세요.")["fact_summary"]
    return {"schema_version":2,"stage":"synthesis","status":"완료","records":chosen,"summary":summary,"errors":[],
            "parts":{},"sample_sources":["SAMPLE"] if any(r.get("sample") for r in chosen) else [],"input_signature":input_signature(session),
            "collected_at":datetime.now(timezone.utc).isoformat(),"note":"수집 완료와 선택적 AI 요약 상태는 별도입니다."}


def run_all(session, retry=False):
    for stage in STAGES[:3]:
        result=run_stage(stage,session,retry)
        persist_result(session,stage,result)
    return {"schema_version":2,"status":"완료" if all(session[s+"_status"]=="완료" for s in STAGES[:3]) else "부분 실패",
            "records":[],"errors":[],"message":"선택한 소스 수집이 끝났습니다. 확인·정리 탭에서 필요한 자료를 고르세요."}
