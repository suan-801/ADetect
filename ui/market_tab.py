"""시장분석: 12개월 원본, 기간별 추이, 계절성, 출처와 기능별 산출물."""
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from core.analyzers.market_analyzer import run_market_analysis
from ui.job_control import start, pending
from ui.analysis_shared import notices, insight, downloads
from ui.components import tab_header, status_icon


def render(session):
    status = session.get("market_status", "미실행")
    tab_header("MARKET", "시장분석", status_icon(status))
    if pending(session, "market"):
        return
    if status in ("미실행", "전체 실패", "취소"):
        session["market_force"] = st.checkbox("24시간 캐시 무시하고 새로 수집", value=False, key="fresh_market")
        news = st.checkbox("뉴스 수집", value=True, key="market_opt_news")
        if st.button("시장분석 시작하기", type="primary", key="btn_start_market"):
            start(session, "market", lambda snapshot: run_market_analysis(snapshot.get("category") or snapshot["brand_name"], news),
                  {"category": session.get("category") or session["brand_name"], "news": news})
        if session.get("market_result"):
            notices(session["market_result"])
        return
    result = session["market_result"]
    notices(result)
    tabs = st.tabs(["개요", "검색량 추이", "시장 뉴스", "참고자료"])
    with tabs[0]:
        st.write(result.get("category"))
        rate = result.get("search_volume_change_rate")
        st.metric("검색지수 증감률", f"{rate:+.1f}%" if rate is not None else "데이터 부족")
        season = result["search_seasonality"]
        st.caption(season["note"])
        st.dataframe(pd.DataFrame(season["monthly"]), hide_index=True)
        st.write({k: season[k] for k in ("weekday", "weekend", "weekend_gap_pct")})
        insight("시장 이슈", result["market_issues"])
        insight("시장 추세 해석", result["market_trend_judgement"])
        st.caption(result["upcoming_changes_note"])
        for change in result.get("upcoming_changes", []):
            insight("예정된 변화 · "+change["date"], change)
    with tabs[1]:
        months = st.selectbox("기간(개월)", [12, 3, 1], key="market_period")
        cutoff = (date.today()-timedelta(days=months*30)).isoformat()
        df = pd.DataFrame([r for r in result["trend"] if r["date"] >= cutoff])
        if not df.empty:
            st.line_chart(df.set_index("date")["search_index"])
        st.caption("절대 검색 횟수가 아닌 공통 기간 최고치 대비 상대지수입니다.")
    with tabs[2]:
        period = st.selectbox("뉴스 기간", ["12m", "3m", "1m"], key="market_news_period")
        st.caption(result["news_scope_note"])
        for n in result["top_news"][period]:
            st.write(n["title"])
            st.caption(n.get("published_at"))
            st.write(n["summary"])
            if n["url"].startswith(("https://", "http://")):
                st.link_button("원문", n["url"])
    with tabs[3]:
        for r in result["reference_sources"]:
            st.link_button(r["name"], r["url"])
            st.caption(r["note"])
    downloads(session, "market", result)
