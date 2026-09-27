"""PRD §7-1: 일별 검색지수 후처리와 독립적인 뉴스 수집."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from config import settings
from core.scrapers.naver_api import get_news, get_search_volume_trend
from core.analyzers.evidence import interpret


def seasonality(trend):
    monthly, weekdays = defaultdict(list), {"weekday": [], "weekend": []}
    for row in trend:
        try:
            d = date.fromisoformat(row["date"][:10])
            value = float(row["search_index"])
        except (ValueError, KeyError, TypeError):
            continue
        monthly[d.month].append(value)
        weekdays["weekend" if d.weekday() >= 5 else "weekday"].append(value)
    week = {k: mean(v) if v else None for k, v in weekdays.items()}
    gap = (week["weekend"] / week["weekday"] - 1) * 100 if week["weekday"] and week["weekend"] is not None else None
    return {"monthly": [{"month": m, "search_index": mean(v), "observations": len(v)} for m, v in sorted(monthly.items())],
            **week, "weekend_gap_pct": gap, "confidence": "low",
            "note": "관측 기간의 평균 상대지수입니다. 한 해의 데이터만으로 반복 계절성을 확정하지 않습니다."}


def news_windows(news):
    result = {}
    for label, days in (("12m", 365), ("3m", 90), ("1m", 30)):
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        result[label] = sorted([n for n in news if cutoff <= (n.get("published_at") or "")[:10] <= date.today().isoformat()],
                               key=lambda n: n["published_at"], reverse=True)[:10]
    return result


def reference_sources(category):
    rows = [("KOSIS", "https://kosis.kr", "통계"), ("RISS", "https://www.riss.kr", "학술"),
            ("DBpia", "https://www.dbpia.co.kr", "학술"), ("메조미디어", "https://www.mezzomedia.co.kr", "미디어리포트"),
            ("나스미디어", "https://www.nasmedia.co.kr", "미디어리포트")]
    if any(k in category for k in ("금융", "보험", "은행")):
        rows += [("금융감독원 금융통계정보시스템", "https://fisis.fss.or.kr", "통계"), ("보험연구원", "https://www.kiri.or.kr", "협회·연구")]
    if any(k in category for k in ("커머스", "유통", "소매", "쇼핑")):
        rows += [("대한상공회의소", "https://www.korcham.net", "협회"), ("한국온라인쇼핑협회", "https://www.kolsa.or.kr", "협회")]
    return [{"name": n, "url": u, "type": t, "note": "고정 출처 안내. 원문 미수집; 로그인·구독이 필요할 수 있습니다."} for n, u, t in rows]


def run_market_analysis(category, collect_news=True):
    from core.jobs import checkpoint
    checkpoint("검색지수 수집 중")
    errors, trend, news = [], [], []
    try:
        trend = get_search_volume_trend(category, months=12)
    except Exception:
        errors.append("검색지수 수집 실패")
    checkpoint("뉴스 수집 중", {"trend":trend,"category":category})
    if collect_news:
        try:
            news = get_news(category, scope="market", limit=100)
        except Exception:
            errors.append("뉴스 수집 실패")
    first = trend[0]["search_index"] if trend else None
    rate = (trend[-1]["search_index"] / first - 1) * 100 if first else None
    facts = [{"source": n["url"], "text": n["title"] + "\n" + n["summary"], "sample": settings.NAVER_SEARCH_MOCK} for n in news]
    checkpoint("시장 근거 분석 중", {"trend":trend,"news":news,"category":category})
    if trend and not settings.NAVER_DATALAB_MOCK:
        facts.append({"source":"NAVER DataLab", "text":f"검색지수 시작 {trend[0]['date']} {first}, 종료 {trend[-1]['date']} {trend[-1]['search_index']}; 구간 증감률 {rate}"})
    ai = interpret(["market_issues", "market_trend_judgement"], facts)
    # 뉴스 API의 발췌문에서 공식 발표와 미래 날짜가 동시에 확인되는 경우만 인용한다.
    import re
    changes=[]
    if not settings.NAVER_SEARCH_MOCK:
        for n in news:
            quote=n["title"]+"\n"+n["summary"]
            if not any(word in quote for word in ("공식 발표", "공식발표", "시행", "공포")):
                continue
            for match in re.finditer(r"(20\d{2})[년.\-/ ]+(\d{1,2})[월.\-/ ]+(\d{1,2})일?",quote):
                try:
                    announced_date=date(*map(int,match.groups()))
                except ValueError:
                    continue
                if announced_date > date.today():
                    changes.append({"date":announced_date.isoformat(),"insight":quote,"source":[n["url"]],"evidence":[quote],"confidence":"low",
                                    "verification_scope":"뉴스 API 원문 발췌 — 공식 발표 여부는 링크에서 재확인"})
                    break
    return {"status": "전체 실패" if not trend and errors else "부분 실패" if errors else "완료",
            "category": category, "trend": trend, "search_volume_trend": trend,
            "search_volume_change_rate": rate, "search_seasonality": seasonality(trend),
            "news": news, "top_news": news_windows(news), "reference_sources": reference_sources(category),
            "upcoming_changes": changes, "upcoming_changes_note": "공식 발표·일자가 함께 있는 뉴스 발췌만 인용합니다. 예측은 생성하지 않습니다.",
            "news_scope_note": "검색 API가 반환한 최근 최대 100건 내 기간별 TOP 10이며 전체 기사량이 아닙니다.",
            "errors": errors, "sample_sources": [k for k, v in (("trend", settings.NAVER_DATALAB_MOCK), ("news", collect_news and settings.NAVER_SEARCH_MOCK)) if v],
            "collected_at": datetime.now(timezone.utc).isoformat(), **ai}
