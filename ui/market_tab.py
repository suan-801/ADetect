"""시장분석 탭 — PRD §7-1·§7-11-(1)·§16-2.

★ 담당: 시장분석 파트. 지금은 화면 골격 + 목업 데이터로만 채워져 있습니다.
실제 구현 시 core/scrapers/naver_api.py의 get_search_volume_trend()/get_news()를
실제 API 호출로 교체하고, market_issues/upcoming_changes 등 AI 필드를 추가하면 됩니다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.scrapers.naver_api import get_news, get_search_volume_trend
from ui.components import feature_card, sample_data_notice, status_icon


def render(session: dict):
    status = session.get("market_status", "미실행")
    st.subheader(f"{status_icon(status)} 시장분석")

    if status == "미실행":
        feature_card(
            "📊", "이 기능은 다음을 분석합니다",
            "· 검색량 추이(최근 12/3/1개월) 및 계절성\n"
            "· 카테고리 주요 뉴스 (최근 1년/3개월/1개월)\n"
            "· 전문 통계·리포트 참고자료 출처",
        )
        with st.expander("선택 수집 옵션"):
            st.checkbox("뉴스", value=True, key="market_opt_news")
        if st.button("시장분석 시작하기", type="primary", key="btn_start_market"):
            with st.spinner("시장 데이터를 수집하는 중..."):
                category = session.get("category") or session["brand_name"]
                trend = get_search_volume_trend(category, months=3)
                news = get_news(category, scope="market") if st.session_state.get("market_opt_news", True) else []
                session["market_result"] = {"trend": trend, "news": news, "category": category}
                session["market_status"] = "완료"
            st.rerun()
        return

    result = session.get("market_result", {})
    tabs = st.tabs(["개요", "검색량 추이", "시장 뉴스"])

    with tabs[0]:
        sample_data_notice()
        st.write(
            f"**{result.get('category')}** 카테고리의 최근 3개월 검색량 추이와 관련 뉴스를 확인할 수 있습니다."
        )

    with tabs[1]:
        df = pd.DataFrame(result.get("trend", []))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            st.line_chart(df.set_index("date")["search_index"])
        else:
            st.info("데이터가 없습니다.")

    with tabs[2]:
        news = result.get("news", [])
        if not news:
            st.info("뉴스 수집 옵션이 꺼져 있거나 뉴스가 없습니다.")
        for n in news:
            st.markdown(f"**[{n['title']}]({n['url']})**  \n{n['summary']}  \n`{n['published_at']}`")

    st.divider()
    c1, c2 = st.columns(2)
    c1.button("HTML 다운로드 (준비 중)", disabled=True, key="dl_html_market")
    c2.button("Excel 다운로드 (준비 중)", disabled=True, key="dl_excel_market")
