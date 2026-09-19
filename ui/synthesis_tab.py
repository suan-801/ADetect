"""종합분석 탭 — PRD §7-4·§7-11-(5)·§15. 시장/브랜드/소재 3개 기능 중 최소 1개 완료 시 잠금 해제(§6-1).

Target Insight는 독립 function_run이 아니라 이 탭의 subsection이다(§15) — 시장분석과
브랜드분석이 모두 완료(또는 부분 실패)여야 생성되며, 근거가 부족하면 임의 인구통계를
만들지 않고 insufficient_data 또는 정직한 안내 문구로 처리한다.
"""
from __future__ import annotations

import streamlit as st

from core.analyzers.insight_synthesizer import build_target_insight
from ui.components import feature_intro, render_insight_card, tab_header


def render(session: dict):
    unlocked = any(
        session.get(k) in ("완료", "부분 실패")
        for k in ("market_status", "brand_status", "creative_status")
    )

    tab_header("SYNTHESIS", "종합분석", "○" if unlocked else "🔒")

    if not unlocked:
        feature_intro(["시장/브랜드/소재 중 최소 1개 이상이 완료되면 잠금 해제됩니다."])
        return

    feature_intro([
        "Share of Search / Share of Ads / Share of Voice(뉴스)",
        "포지셔닝맵, White Space",
        "한 줄 총평 (AI Recommendation)",
    ])
    st.button("종합분석 시작하기 (준비 중)", disabled=True, key="btn_start_synthesis")
    st.caption("시장·브랜드·소재 결과가 쌓이면 별도 수집 없이 조합만으로 산출합니다.")

    st.divider()
    st.markdown('<div class="adetect-section-label">TARGET INSIGHT</div>', unsafe_allow_html=True)
    market_ok = session.get("market_status") in ("완료", "부분 실패")
    brand_ok = session.get("brand_status") in ("완료", "부분 실패")
    if not (market_ok and brand_ok):
        st.caption("시장분석과 브랜드분석이 모두 완료되면 생성됩니다.")
    else:
        target_insight = build_target_insight(
            session.get("market_result"), session.get("brand_result"), session.get("creative_result")
        )
        if target_insight.get("status") == "insufficient_data":
            st.caption(target_insight["message"])
        else:
            render_insight_card("핵심 타겟", target_insight, kind="AI")
