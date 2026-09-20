"""시장분석 탭 — PRD §7-1·§7-11-(1)·§16-2.

★ MARKET IMPLEMENTATION CONTRACT (담당: 시장분석 파트)

현재 상태 — 부분 실연동: `get_search_volume_trend()`/`get_news()`는 NAVER_CLIENT_ID/SECRET이
있으면 이미 실제 API를 호출한다(config/settings.NAVER_DATALAB_MOCK/NAVER_SEARCH_MOCK). 키가
없으면 결정론적 mock으로 조용히 폴백한다 — "지금 이 탭이 전부 mock"이라고 가정하지 말 것.

Required input: session["brand_name"], session["category"](없으면 brand_name으로 대체)
Required output(PRD §7-1): trend, news는 완료. search_seasonality/reference_sources/
market_issues/upcoming_changes(§7-1-a·§7-1-b)는 아직 화면·데이터 모두 없음 — 추가 필요.
Required states: 완료/부분 실패/전체 실패(§11) — 지금은 NaverApiError만 전체 실패로 처리.
"검색량은 성공, 뉴스만 실패" 같은 부분 실패 케이스는 아직 없음(§6 참고해 추가 검토).

Reference pattern: `ui/creative_tab.py`/`core/analyzers/creative_analyzer.py` — st.status
진행 표시, insight_synthesizer.build_insight() 스키마, HTML/Excel 다운로드(생성→다운로드
2단계) 패턴을 그대로 따르면 된다.

Do not:
- Workspace 1차 탭 순서(시장→브랜드→소재→종합)를 바꾸지 않는다.
- source/evidence/confidence 없는 AI 판단을 확정 결과처럼 보여주지 않는다(§8).
- 근거 없는 수치(세그먼트 인구통계 등)를 새로 지어내지 않는다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import settings
from core.scrapers.naver_api import NaverApiError, get_news, get_search_volume_trend
from ui.components import feature_intro, metric_row, prototype_notice, sample_data_notice, status_icon, tab_header


def render(session: dict):
    status = session.get("market_status", "미실행")
    tab_header("MARKET", "시장분석", status_icon(status))
    prototype_notice("프로토타입 화면 · 검색량 추이·뉴스는 실제 데이터 연동, 계절성/참고자료 등 나머지 지표는 연동 예정")

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
            st.line_chart(df.set_index("date")["search_index"], color="#5AA9E6")
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
    c1.button("HTML 다운로드 — 기능 개발 후 제공 예정", disabled=True, key="dl_html_market")
    c2.button("Excel 다운로드 — 기능 개발 후 제공 예정", disabled=True, key="dl_excel_market")
