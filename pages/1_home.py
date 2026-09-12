"""홈 — Premium AI Intelligence / Black Monochrome / Minimal Glassmorphism.

콘텐츠/기능은 PRD 기준(★ 15차 개정: 타겟 자동추천 문구 제거), 비주얼은 팀 디자인 피드백
(docs/PROJECT_PLAN.md §5) 기준입니다: 카드 나열 대신 여백 + 얇은 구분선의 에디토리얼 레이아웃,
이모지 대신 typography 중심, 종합분석은 메인 모듈에서 빼고 4개 분석이 쌓이면 자동 제공되는
결과로 안내합니다.
"""
from __future__ import annotations

import streamlit as st

from config.theme import glass_marker
from ui.components import module_row

st.markdown(
    "<span class='adetect-eyebrow'>ADetect · Brand Intelligence</span>"
    "<p class='adetect-hero-title'>AI insight,<br>in minutes.</p>"
    "<p class='adetect-hero-sub'>브랜드명만 입력하면 시장부터 소재까지, "
    "AI가 분석해 경쟁사 인사이트와 실행 가능한 전략을 제안합니다.</p>",
    unsafe_allow_html=True,
)

st.write("")
st.write("")

with st.container():
    glass_marker()
    st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.6rem;'>Brand</span>", unsafe_allow_html=True)
    brand_name = st.text_input(
        "브랜드명", placeholder="브랜드명을 입력하세요", label_visibility="collapsed", key="home_brand_input"
    )

    with st.expander("카테고리·경쟁사 직접 입력 (선택)"):
        category = st.text_input("카테고리", placeholder="비워두면 AI가 추천", key="home_category_input")
        competitors = st.text_input(
            "경쟁사", placeholder="쉼표로 구분, 비워두면 AI가 추천", key="home_competitors_input"
        )

    left, right = st.columns([3, 1])
    left.caption("브랜드명만 입력해도 AI가 카테고리와 경쟁사를 추천합니다. 타겟은 분석 이후 추천됩니다.")
    start = right.button("Analyze →", type="primary")

    if start:
        if not brand_name.strip():
            st.error("브랜드명을 입력해주세요.")
        else:
            st.session_state.prefill_brand = brand_name.strip()
            st.session_state.prefill_category = st.session_state.get("home_category_input", "").strip()
            st.session_state.prefill_competitors = st.session_state.get("home_competitors_input", "").strip()
            st.session_state.step = "input"
            st.session_state.session = None
            st.switch_page("pages/2_analyze.py")

st.write("")
st.write("")
st.write("")

modules = [
    ("MARKET", "Market Intelligence", "시장 규모, 검색량 추이, 트렌드와 경쟁 환경을 분석합니다."),
    ("BRAND", "Brand Intelligence", "브랜드 메시지, USP, 핵심 키워드와 매체 운영 현황을 분석합니다."),
    ("CREATIVE", "Creative Intelligence", "광고 소재, 크리에이티브 패턴, 소구 포인트를 분석합니다."),
    ("AUDIENCE", "Audience Intelligence", "시장·브랜드 분석 결과를 근거로 타겟을 추천하고 분석합니다."),
]
for label, title, desc in modules:
    module_row(label, title, desc)

st.caption("네 가지 분석 결과가 쌓이면 Share of Search·포지셔닝·White Space를 담은 종합 인사이트가 자동으로 제공됩니다.")
