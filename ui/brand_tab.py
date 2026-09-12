"""브랜드분석 탭 — PRD §7-3·§7-11-(3)·§16-3. 자사+경쟁사 통합 스키마.

★ 담당: 브랜드분석 파트 (백엔드 포함).
core/analyzers/brand_analyzer.py의 run_brand_analysis()를 호출해 렌더링합니다.
지금은 core/scrapers/*가 목업 데이터를 반환하지만(§ config.settings.USE_MOCK_DATA),
.env에 실제 키(NAVER_*, APIFY_API_TOKEN, GEMINI_API_KEY)를 채우면 scraper 내부 구현만
바꿔도 이 탭은 그대로 동작하도록 설계했습니다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.analyzers.brand_analyzer import run_brand_analysis
from ui.components import feature_card, render_insight_card, sample_data_notice, status_icon


def render(session: dict):
    status = session.get("brand_status", "미실행")
    st.subheader(f"{status_icon(status)} 브랜드분석")

    if status == "미실행":
        feature_card(
            "🧭", "이 기능은 다음을 분석합니다",
            "· 브랜드 검색량 (자사+경쟁사)   · 홈페이지 분석\n"
            "· 브랜드 뉴스                  · SNS 프로필\n"
            "· 네이버 SA/브랜드검색          · 매체 운영 현황",
        )
        with st.expander("선택 수집 옵션"):
            st.checkbox("Instagram", value=True, key="brand_opt_ig")
            st.checkbox("YouTube", value=False, key="brand_opt_yt")
            st.checkbox("네이버 SA/브랜드검색", value=True, key="brand_opt_naver_sa")
            st.checkbox("뉴스", value=True, key="brand_opt_news")

        if st.button("브랜드분석 시작하기", type="primary", key="btn_start_brand"):
            with st.spinner("자사 및 경쟁사 브랜드 데이터를 수집·분석하는 중..."):
                result = run_brand_analysis(session["brand_name"], session.get("competitors", []))
                session["brand_result"] = result
                session["brand_status"] = result["status"]
            st.rerun()
        return

    result = session["brand_result"]
    own = result["own"]
    competitors = result["competitors"]
    ctx = result["brand_context"]

    tabs = st.tabs(["개요", "브랜드 검색량", "홈페이지 분석", "광고 운영", "SNS 분석", "AI 인사이트"])

    with tabs[0]:
        sample_data_notice()
        st.write(
            f"**{own['brand']}** vs 경쟁사 {len(competitors)}개 브랜드를 동일한 기준으로 비교했습니다."
        )
        st.caption(
            f"내부 판단(비노출): brand_type={ctx['brand_type']} · "
            f"conversion_objective={ctx['conversion_objective']}"
        )
        render_insight_card("브랜드 비교 총평", result["comparison_insight"])

    with tabs[1]:
        rows = []
        for b in [own, *competitors]:
            sv = b["brand_search_volume"]
            rows.append({
                "브랜드": b["brand"] + (" (자사)" if b["is_own"] else ""),
                "최근 30일 PC": sv["absolute_30d_pc"],
                "최근 30일 모바일": sv["absolute_30d_mobile"],
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        own_trend = pd.DataFrame(own["brand_search_volume"]["relative_trend"])
        if not own_trend.empty:
            own_trend["date"] = pd.to_datetime(own_trend["date"])
            st.line_chart(own_trend.set_index("date")["search_index"])

    with tabs[2]:
        for b in [own, *competitors]:
            label = f"{b['brand']}" + (" (자사)" if b["is_own"] else "")
            with st.expander(label, expanded=b["is_own"]):
                st.write(f"USP 요약: {b['brand_website_facts']['usp_summary']}")
                st.write(f"프로모션: {b['promotion_fact']}")
                render_insight_card("타겟·메시지 해석", b["brand_website_target_message"])
                render_insight_card("프로모션 해석", b["promotion_interpretation"])

    with tabs[3]:
        rows = []
        for b in [own, *competitors]:
            m = b["media_operation_matrix_row"]
            rows.append({
                "브랜드": b["brand"] + (" (자사)" if b["is_own"] else ""),
                "네이버 SA": "●" if m["naver_sa"] else "X",
                "네이버 브랜드검색": "●" if m["naver_brand_search"] else "X",
                "Meta Ads": "●" if m["meta_ads"] else "X",
                "Instagram 프로필": "●" if m["instagram_profile"] else "X",
                "YouTube": "●" if m["youtube_channel"] else "X",
                "활성 광고 수": b["ad_count"],
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    with tabs[4]:
        for b in [own, *competitors]:
            ig = b["instagram"]
            label = f"{b['brand']}" + (" (자사)" if b["is_own"] else "")
            if not ig.get("profile_found"):
                st.write(f"**{label}**: 공식 Instagram 프로필을 찾지 못함 (정상 처리, §6)")
                continue
            st.write(f"**{label}**: 팔로워 {ig['followers']:,} · 게시물 {ig['posts']:,}")
            st.caption(ig["recent_caption_sample"])

    with tabs[5]:
        for b in [own, *competitors]:
            label = f"{b['brand']}" + (" (자사)" if b["is_own"] else "")
            st.markdown(f"**{label}** 핵심 메시지: {', '.join(b['key_message'])}")

    st.divider()
    c1, c2 = st.columns(2)
    c1.button("HTML 다운로드 (준비 중)", disabled=True, key="dl_html_brand")
    c2.button("Excel 다운로드 (준비 중)", disabled=True, key="dl_excel_brand")
