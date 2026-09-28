"""3년 전 1월부터 직전 완료 월까지의 월간 검색지수. 0과 미제공을 구분한다."""
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
import requests
from config import settings
from core.jobs import source_cache


def period_bounds(months=None, today=None):
    today = today or date.today()
    end = today.replace(day=1) - timedelta(days=1)
    if months is None:
        return date(today.year-3, 1, 1).isoformat(), end.isoformat()
    offset = end.year * 12 + end.month - months
    start = date(offset // 12, offset % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def fetch_history(keyword, months=None, keywords=None):
    return _fetch_history(keyword, *period_bounds(months), keywords)


@source_cache("monthly_history_calendar_v3")
def _fetch_history(keyword, start, end, keywords=None):
    terms=list(dict.fromkeys(keywords if keywords is not None else [keyword]))
    if not terms or len(terms)>20 or any(not isinstance(t,str) or not t.strip() for t in terms):
        raise ValueError("주제어별 검색어는 1~20개가 필요합니다.")
    months = month_count(start, end)
    if settings.SAMPLE_MODE:
        # Explicit fixture, never used merely because a credential is absent.
        rows = []
        y, m = map(int, start[:7].split("-"))
        for i in range(months):
            offset = y*12+m-1+i
            rows.append({"date": f"{offset//12:04d}-{offset%12+1:02d}-01", "search_index": [20,30,55,60,40,25,15,20,50,70,45,30][offset%12]})
    else:
        if settings.NAVER_DATALAB_MOCK:
            raise ValueError("네이버 검색 추이 키 미설정")
        response = requests.post("https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
            headers={"X-NCP-APIGW-API-KEY-ID":settings.NAVER_CLIENT_ID,"X-NCP-APIGW-API-KEY":settings.NAVER_CLIENT_SECRET},
            json={"startDate":start,"endDate":end,"timeUnit":"month","keywordGroups":[{"groupName":keyword,"keywords":terms}]}, timeout=20)
        response.raise_for_status()
        groups = response.json().get("results", [])
        rows = [{"date":v["period"],"search_index":v["ratio"]} for v in (groups[0].get("data",[]) if groups else [])]
    return {"keyword":keyword,"keywords":terms,"grouped":keywords is not None,"start":start,"end":end,"rows":rows,"sample":settings.SAMPLE_MODE,
            "source_url":"https://datalab.naver.com/keyword/trendSearch.naver",
            "note":"이 주제어 묶음의 조회 기간 내 최고 월=100인 상대지수이며 검색 횟수가 아닙니다. 별도 요청한 주제어끼리 절대 규모 비교는 불가합니다. 미제공 월은 0으로 채우지 않습니다."}


def fetch_comparison(groups, months=None):
    return _fetch_comparison(groups, *period_bounds(months))


@source_cache("brand_comparison_calendar_v2")
def _fetch_comparison(groups, start, end):
    """자사·경쟁사 검색어 묶음을 한 요청(최대 5개 주제)으로 조회한다.

    같은 요청 안에서는 모든 주제가 같은 기준(요청 전체 최고 월=100)을 쓰므로 브랜드끼리 비교할 수 있다.
    표기별 지수를 더하지 않고, 누락 월을 0으로 채우지 않는다. 응답의 모든 주제를 그대로 보존한다.
    """
    if not 1 <= len(groups) <= 5:
        raise ValueError("검색 추이 비교는 1~5개 브랜드만 한 요청으로 조회할 수 있습니다.")
    for g in groups:
        if not g.get("terms") or len(g["terms"]) > 20:
            raise ValueError(f"{g.get('name')} 검색어 묶음은 1~20개가 필요합니다.")
    months = month_count(start, end)
    request = {"startDate": start, "endDate": end, "timeUnit": "month",
               "keywordGroups": [{"groupName": g["name"], "keywords": list(g["terms"])} for g in groups]}
    if settings.SAMPLE_MODE:
        # 명시적 SAMPLE 전용 고정값. 키가 없다는 이유로 쓰지 않는다.
        y, m = map(int, start[:7].split("-"))
        results = []
        for n, g in enumerate(groups):
            data = []
            for i in range(months):
                offset = y*12+m-1+i
                data.append({"period": f"{offset//12:04d}-{offset%12+1:02d}-01", "ratio": round([20,30,55,60,40,25,15,20,50,70,45,30][offset%12] * (1 - n*0.18) + (100 if n == 0 and i == months-5 else 0) * 0.3, 3)})
            results.append({"title": g["name"], "keywords": g["terms"], "data": data})
        top = max(v["ratio"] for r in results for v in r["data"])
        for r in results:  # 실제 응답처럼 요청 전체 최고 월을 100으로 맞춘다.
            for v in r["data"]:
                v["ratio"] = round(v["ratio"] * 100 / top, 3)
    else:
        if settings.NAVER_DATALAB_MOCK:
            raise ValueError("네이버 검색 추이 키 미설정")
        response = requests.post("https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
            headers={"X-NCP-APIGW-API-KEY-ID":settings.NAVER_CLIENT_ID,"X-NCP-APIGW-API-KEY":settings.NAVER_CLIENT_SECRET},
            json=request, timeout=20)
        response.raise_for_status()
        results = response.json().get("results", [])
    series = []
    for n, g in enumerate(groups):
        # 응답 순서는 요청 순서를 따른다. 제목이 다르면 해당 주제를 미제공으로 둔다(다른 브랜드 값으로 채우지 않음).
        item = results[n] if n < len(results) and results[n].get("title", g["name"]) == g["name"] else next((r for r in results if r.get("title") == g["name"]), None)
        rows = [{"date": v["period"], "search_index": v["ratio"]} for v in (item or {}).get("data", [])]
        series.append({"brand_id": g["id"], "name": g["name"], "terms": list(g["terms"]), "rows": rows, "provided": item is not None})
    return {"request": request, "start": start, "end": end, "series": series, "sample": settings.SAMPLE_MODE,
            "source_url": "https://datalab.naver.com/keyword/trendSearch.naver",
            "note": "한 요청 안의 전체 최고 월=100인 상대지수입니다. 검색 횟수가 아니며, 미제공 월은 0이 아닙니다."}


# 이전 테스트·확장 코드가 캐시를 우회할 수 있도록 공개 함수에도 원래의 unwrap 계약을 유지한다.
fetch_history.__wrapped__ = lambda keyword, months=None, keywords=None: _fetch_history.__wrapped__(keyword, *period_bounds(months), keywords)
fetch_comparison.__wrapped__ = lambda groups, months=None: _fetch_comparison.__wrapped__(groups, *period_bounds(months))


def month_count(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    return (last.year-first.year)*12 + last.month-first.month + 1


def summarize_history(series):
    by_month, by_year = defaultdict(list), defaultdict(list)
    start, end = series["start"], series["end"]
    seen = set()
    for row in series["rows"]:
        try:
            d = date.fromisoformat(row["date"])
            value = float(row["search_index"])
            if not 0 <= value <= 100 or not start <= d.isoformat() <= end or d.strftime("%Y-%m") in seen:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        seen.add(d.strftime("%Y-%m"))
        by_month[d.month].append(value)
        by_year[d.year].append((d.month,value))
    monthly = [{"월":m,"평균 검색지수":round(mean(v),3),"제공 연도 수":len(v)} for m,v in sorted(by_month.items())]
    yearly = []
    for y, rows in sorted(by_year.items()):
        high, low = max(v for _,v in rows), min(v for _,v in rows)
        informative = high > low
        yearly.append({"연도":y,"제공 월수":len(rows),"피크 월":", ".join(str(m) for m,v in rows if v==high) if informative else "차이 없음",
                       "저점 월":", ".join(str(m) for m,v in rows if v==low) if informative else "차이 없음",
                       "범위":"12개월" if len(rows)==12 else "일부 월만 관측"})
    complete = len(seen)==month_count(start, end)
    high = max((r["평균 검색지수"] for r in monthly),default=0)
    low = min((r["평균 검색지수"] for r in monthly),default=0)
    return {"monthly":monthly,"yearly":yearly,"observed_months":len(seen),"complete":complete,
            "peak_months":[r["월"] for r in monthly if r["평균 검색지수"]==high] if complete and high>low else [],
            "low_months":[r["월"] for r in monthly if r["평균 검색지수"]==low] if complete and high>low else [],
            "note":"조회 기간을 같은 기준으로 관측한 월별 평균입니다. 피크 반복은 비교할 수 있으나 원인·미래 계절성을 확정하지 않습니다. 월간 값은 일평균 검색량이 아닙니다."}
