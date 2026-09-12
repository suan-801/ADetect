"""타겟분석 탭 — 게이트형 + 추천/분석 2단계 (PRD §6-1·§7-2·§9-2·§16-2).

★ 담당: 타겟분석 파트.
핵심 규칙(반드시 유지):
1) STEP 1에서 타겟을 입력받지 않습니다 — 이 탭은 시장분석+브랜드분석이 끝나야 열립니다.
2) "추천"(자동, 무료)과 "분석"(확정 후 실행, function_run)은 서로 다른 단계입니다.
"""
from __future__ import annotations

import streamlit as st

from core.analyzers.target_recommender import analyze_confirmed_target, recommend_target
from ui.components import feature_intro, render_insight_card, sample_data_notice, status_icon, tab_header


def render(session: dict):
    market_ok = session.get("market_status") in ("완료", "부분 실패")
    brand_ok = session.get("brand_status") in ("완료", "부분 실패")
    gated = not (market_ok and brand_ok)

    status = session.get("target_status", "not_set")
    status_text = "🔒" if gated else status_icon("완료" if status == "confirmed" else "미실행")
    tab_header("AUDIENCE", "타겟분석", status_text)

    if gated:
        feature_intro(["시장분석과 브랜드분석 결과를 근거로 핵심 타겟을 추천합니다."])
        st.caption(f"{'✓' if market_ok else '·'} 시장분석 완료 필요")
        st.caption(f"{'✓' if brand_ok else '·'} 브랜드분석 완료 필요")
        st.caption("두 기능이 각각 완료(또는 부분 실패)되면 이 탭이 자동으로 열립니다.")
        return

    # 게이트 통과 — 추천 단계 (자동, 무료)
    if status == "not_set":
        rec = recommend_target(session["brand_name"], session["market_result"], session["brand_result"])
        session["recommended_target"] = rec
        session["target_status"] = "recommended"
        st.rerun()

    if session.get("target_status") == "recommended":
        rec = session["recommended_target"]
        sample_data_notice()
        st.markdown(f"#### {rec['segment']}")
        render_insight_card("추천 근거", rec, kind="AI")

        col1, col2 = st.columns([1, 1])
        if col1.button("확정", type="primary", key="btn_confirm_target"):
            session["confirmed_target"] = rec["segment"]
            session["target_status"] = "confirmed"
            st.rerun()
        with col2.popover("수정"):
            edited = st.text_input("타겟을 직접 입력하세요", value=rec["segment"], key="edit_target_input")
            if st.button("수정한 값으로 확정", key="btn_confirm_edited_target"):
                session["confirmed_target"] = edited
                session["target_status"] = "confirmed"
                st.rerun()
        return

    # 확정 후 — 실제 타겟분석(function_run)
    st.caption(f"확정 타겟 — {session['confirmed_target']} (사용자 확정)")

    if session.get("target_result") is None:
        if st.button("타겟분석 시작하기", type="primary", key="btn_start_target_analysis"):
            with st.spinner("확정된 타겟을 기준으로 분석하는 중..."):
                session["target_result"] = analyze_confirmed_target(
                    session["confirmed_target"], session.get("category")
                )
            st.rerun()
        return

    result = session["target_result"]
    tabs = st.tabs(["개요", "관심 키워드", "AI Persona"])
    with tabs[0]:
        sample_data_notice()
        st.write(f"확정 타겟 **{result['confirmed_target']}** 기준 분석 결과입니다.")
    with tabs[1]:
        for kw in result["interest_keywords"]:
            st.write(f"- {kw['keyword']} (검색량 {kw['volume']:,})")
    with tabs[2]:
        st.caption(result["ai_persona"]["disclaimer"])
        render_insight_card("성향", result["ai_persona"]["target_disposition"])
        render_insight_card("선호 상황", result["ai_persona"]["preferred_situation"])
        render_insight_card("전환 트리거", result["ai_persona"]["conversion_trigger_context"])

    st.divider()
    c1, c2 = st.columns(2)
    c1.button("HTML 다운로드 (준비 중)", disabled=True, key="dl_html_target")
    c2.button("Excel 다운로드 (준비 중)", disabled=True, key="dl_excel_target")
