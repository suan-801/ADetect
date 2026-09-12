"""홈 — ref.png 디자인 참고, 콘텐츠/문구는 PRD 기준 (★ 15차 개정: 타겟 자동추천 문구 제거).

구현 난이도로 단순화한 부분:
- ref.png 우측의 3D 캡슐 오브젝트 그래픽은 생략했습니다 (Streamlit에서 정적 이미지/Lottie 없이는
  동일하게 재현하기 어려움 — 필요하시면 이미지 에셋을 만들어 넣거나, 실제 이미지를 templates/assets에
  추가해 배경으로 넣는 방식으로 확장할 수 있습니다).
- 사이드바 커스텀 아이콘 네비게이션은 Streamlit 기본 st.navigation 스타일 위에 최소한의 CSS만 입혔습니다.
"""
from __future__ import annotations

import streamlit as st

from core.analyzers.recommender import recommend_category
from ui.components import feature_card

st.markdown("<span class='adetect-eyebrow'>ADetect</span>", unsafe_allow_html=True)
st.markdown(
    "<p class='adetect-hero-title'>Brand data,<br>AI insight,<br>"
    "<span style='color:#9A9AA3;'>in minutes.</span></p>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='adetect-hero-sub'>브랜드명만 입력하면 시장부터 소재까지,<br>"
    "AI가 분석하여 경쟁사 인사이트와 실행 가능한 전략을 제안합니다.</p>",
    unsafe_allow_html=True,
)

st.write("")
with st.container(border=True):
    st.markdown("#### 브랜드 분석 시작하기")
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1.4])
    brand_name = c1.text_input("브랜드명", placeholder="브랜드명을 입력하세요", label_visibility="collapsed")
    category = c2.text_input("카테고리 (선택)", placeholder="카테고리 (선택)", label_visibility="collapsed")
    competitors = c3.text_input("경쟁사 (선택)", placeholder="경쟁사 (선택, 쉼표로 구분)", label_visibility="collapsed")
    start = c4.button("분석 시작하기 →", type="primary", width="stretch")

    st.caption("ⓘ 브랜드명만 입력해도 AI가 카테고리와 경쟁사를 추천해드립니다. (타겟은 시장·브랜드 분석 이후 추천됩니다)")

    if start:
        if not brand_name.strip():
            st.error("브랜드명을 입력해주세요.")
        else:
            st.session_state.prefill_brand = brand_name.strip()
            st.session_state.prefill_category = category.strip()
            st.session_state.prefill_competitors = competitors.strip()
            st.session_state.step = "input"
            st.session_state.session = None
            st.switch_page("pages/2_analyze.py")

st.write("")
st.markdown("### 주요 분석 기능")
cols = st.columns(5)
features = [
    ("📊", "시장분석", "시장 규모, 검색량, 트렌드, 경쟁 환경을 분석합니다."),
    ("🎯", "타겟분석", "시장·브랜드 분석 결과를 근거로 타겟을 추천하고 분석합니다."),
    ("🧭", "브랜드분석", "브랜드 메시지, USP, 핵심 키워드를 분석합니다."),
    ("🖼️", "소재분석", "광고 소재, 크리에이티브, 소구 포인트를 분석합니다."),
    ("🏁", "종합분석", "SOV, 포지셔닝, White Space, 한 줄 총평을 제공합니다."),
]
for col, (icon, title, desc) in zip(cols, features):
    with col:
        feature_card(icon, title, desc)

st.write("")
st.divider()
f1, f2, f3 = st.columns(3)
f1.caption("⚡ 빠르고 정확한 데이터 수집")
f2.caption("🤖 AI 기반 인사이트 분석")
f3.caption("📄 맞춤형 리포트 제공")
