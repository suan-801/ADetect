"""완료된 36개월의 월간 검색지수. 0과 미제공을 구분한다."""
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
import requests
from config import settings
from core.jobs import source_cache


def period_bounds(months=36, today=None):
    end = (today or date.today()).replace(day=1) - timedelta(days=1)
    offset = end.year * 12 + end.month - months
    start = date(offset // 12, offset % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


@source_cache("monthly_history_v2")
def fetch_history(keyword, months=36):
    start, end = period_bounds(months)
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
            json={"startDate":start,"endDate":end,"timeUnit":"month","keywordGroups":[{"groupName":keyword,"keywords":[keyword]}]}, timeout=20)
        response.raise_for_status()
        groups = response.json().get("results", [])
        rows = [{"date":v["period"],"search_index":v["ratio"]} for v in (groups[0].get("data",[]) if groups else [])]
    return {"keyword":keyword,"start":start,"end":end,"rows":rows,"sample":settings.SAMPLE_MODE,
            "source_url":"https://datalab.naver.com/keyword/trendSearch.naver",
            "note":"검색어별 36개월 내 최고 월=100. 서로 다른 검색어의 지수를 절대 규모로 비교할 수 없습니다. 미제공 월은 0으로 채우지 않습니다."}


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
    complete = len(seen)==36
    high = max((r["평균 검색지수"] for r in monthly),default=0)
    low = min((r["평균 검색지수"] for r in monthly),default=0)
    return {"monthly":monthly,"yearly":yearly,"observed_months":len(seen),"complete":complete,
            "peak_months":[r["월"] for r in monthly if r["평균 검색지수"]==high] if complete and high>low else [],
            "low_months":[r["월"] for r in monthly if r["평균 검색지수"]==low] if complete and high>low else [],
            "note":"36개월을 같은 기준으로 관측한 월별 평균입니다. 피크 반복은 비교할 수 있으나 원인·미래 계절성을 확정하지 않습니다. 월간 값은 일평균 검색량이 아닙니다."}
