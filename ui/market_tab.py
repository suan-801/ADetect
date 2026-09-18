"""시장분석 탭 — PRD §7-1·§7-11-(1)·§16-2.

★ 담당: 시장분석 파트. 지금은 화면 골격 + 목업 데이터로만 채워져 있습니다.
실제 구현 시 core/scrapers/naver_api.py의 get_search_volume_trend()/get_news()를
실제 API 호출로 교체하고, market_issues/upcoming_changes 등 AI 필드를 추가하면 됩니다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import settings
from core.scrapers.naver_api import NaverApiError, get_news, get_search_volume_trend
from ui.components import feature_intro, metric_row, sample_data_notice, status_icon, tab_header


def render(session: dict):
    status = session.get("market_status", "미실행")
    tab_header("MARKET", "시장분석", status_icon(status))

    if status in ("미실행", "전체 실패"):
        feature_intro([
            "검색량 추이(최근 12/3/1개월) 및 계절성",
            "카테고리 주요 뉴스 — 최근 1년/3개월/1개월",
            "전문 통계·리포트 참고자료 출처",
        ])
        # 현재는 선택 수집 소스가 뉴스 하나뿐이라 옵션 UI를 노출하지 않고 기본값(수집)으로 둔다.
        # 향후 블로그/커뮤니티 등 소스가 늘어나면 여기에 "선택 수집 옵션" expander를 다시 추가하면 된다.
        st.session_state.setdefault("market_opt_news", True)
        if status == "전체 실패":
            st.error("시장 데이터 수집에 실패했습니다. 네이버 API 키/권한을 확인한 뒤 다시 시도해주세요.")
        if st.button("시장분석 시작하기", type="primary", key="btn_start_market"):
            category = session.get("category") or session["brand_name"]
            try:
                with st.spinner("시장 데이터를 수집하는 중..."):
                    trend = get_search_volume_trend(category, months=3)
                    news = (
                        get_news(category, scope="market")
                        if st.session_state.get("market_opt_news", True)
                        else []
                    )
                session["market_result"] = {"trend": trend, "news": news, "category": category}
                session["market_status"] = "완료"
            except NaverApiError as exc:
                # §11 오류 처리 정책 — 핵심 데이터(검색량 추이) 수집 시도 자체가 실패했으므로 전체 실패(§6)
                session["market_result"] = {"trend": [], "news": [], "category": category}
                session["market_status"] = "전체 실패"
                st.error(f"검색량 데이터 수집 실패: {exc}")
            st.rerun()
        return

    result = session.get("market_result", {})
    tabs = st.tabs(["개요", "검색량 추이", "시장 뉴스"])

    with tabs[0]:
        if settings.NAVER_DATALAB_MOCK:
            sample_data_notice()
        trend = result.get("trend", [])
        if trend:
            first_val = trend[0]["search_index"]
            last_val = trend[-1]["search_index"]
            change_pct = ((last_val - first_val) / first_val * 100) if first_val else 0
            trend_dir = "up" if change_pct > 1 else "down" if change_pct < -1 else "flat"
            metric_row([
                ("검색지수(최근)", str(last_val), None),
                ("증감률(구간)", f"{change_pct:+.1f}<span class='unit'>%</span>", trend_dir),
                ("주요 뉴스", str(len(result.get("news", []))), None),
            ])
        st.write(
            f"**{result.get('category')}** 카테고리의 최근 3개월 검색량 추이와 관련 뉴스를 확인할 수 있습니다."
        )

    with tabs[1]:
        df = pd.DataFrame(result.get("trend", []))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            st.line_chart(df.set_index("date")["search_index"])
        else:
            st.caption("데이터가 없습니다.")

    with tabs[2]:
        news = result.get("news", [])
        if not news:
            st.caption("뉴스 수집 옵션이 꺼져 있거나 뉴스가 없습니다.")
        for n in news:
            st.markdown(f"**[{n['title']}]({n['url']})**  \n{n['summary']}  \n`{n['published_at']}`")

    st.divider()
    c1, c2 = st.columns(2)
    c1.button("HTML 다운로드 (준비 중)", disabled=True, key="dl_html_market")
    c2.button("Excel 다운로드 (준비 중)", disabled=True, key="dl_excel_market")
