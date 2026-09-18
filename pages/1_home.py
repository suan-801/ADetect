"""홈 — Cinematic / Spacious / Storytelling (PRD 대규모 리뉴얼, 2026-09).

Home은 Workspace보다 화면 밀도를 낮추고 여백/타이포/오리지널 일러스트 중심으로 구성합니다.
기능/카피는 PRD 기준(★ 15차 개정: 타겟 자동추천 문구 제거)이며, 5개 분석 기능은 카드 나열이
아니라 각각 하나의 story section(§3~6, Market→Audience→Brand→Creative→Synthesis)으로 표현합니다.
"""
from __future__ import annotations

import streamlit as st

from config.theme import cta_row_marker, glass_marker
from ui.components import cta_section, feature_story, section_header_block
from ui.hero import render_hero_copy, render_hero_object
from ui.illustrations import audience_visual, brand_visual, creative_visual, market_visual, synthesis_visual


def _command_bar(key_prefix: str, glow: bool = False):
    with st.container():
        glass_marker(glow=glow)
        st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.6rem;'>Brand</span>", unsafe_allow_html=True)
        brand_name = st.text_input(
            "브랜드명", placeholder="브랜드명을 입력하세요", label_visibility="collapsed", key=f"{key_prefix}_brand_input"
        )
        with st.expander("카테고리·경쟁사 직접 입력 (선택)"):
            category = st.text_input("카테고리", placeholder="비워두면 AI가 추천", key=f"{key_prefix}_category_input")
            competitors = st.text_input(
                "경쟁사", placeholder="쉼표로 구분, 비워두면 AI가 추천", key=f"{key_prefix}_competitors_input"
            )
        with st.container():
            cta_row_marker()
            st.caption("브랜드명만 입력해도 AI가 카테고리와 경쟁사를 추천합니다. 타겟은 분석 이후 추천됩니다.")
            start = st.button("분석하기 →", type="primary", key=f"{key_prefix}_start_btn")

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


# ── SECTION 01 · HERO ────────────────────────────────────────────────────
copy_col, object_col = st.columns([1.25, 1], gap="large")
with copy_col:
    render_hero_copy()
with object_col:
    render_hero_object()

st.write("")
_command_bar("hero", glow=True)

st.write("")
st.write("")

# ── SECTION 02 · VALUE PROPOSITION ───────────────────────────────────────
with st.container():
    st.markdown('<div class="adetect-section">', unsafe_allow_html=True)
    section_header_block(
        "Why ADetect",
        "파편화된 시장 데이터를<br>하나의 흐름으로.",
        "검색 트렌드, 경쟁사 프로필, 광고 소재, SNS 운영 현황 — 흩어진 소스를 "
        "하나의 분석 Workspace로 모으고, AI가 실행 가능한 인사이트로 정리합니다.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── SECTION 03~07 · ANALYSIS STORY ───────────────────────────────────────
stories = [
    ("01", "MARKET", "시장이 움직이는\n방향부터.", "검색량 추이와 계절성, 카테고리 뉴스와 시장 신호를 모아 "
     "지금 시장이 커지는지 정체되는지부터 확인합니다.", market_visual, False),
    ("02", "AUDIENCE", "누가 반응하는지\n확인합니다.", "시장·브랜드 분석 결과를 근거로 AI가 핵심 타겟을 먼저 추천합니다. "
     "연령·성별, 관심 키워드, AI Persona까지 확정된 타겟 기준으로 분석합니다.", audience_visual, True),
    ("03", "BRAND", "브랜드와 경쟁사를\n같은 눈높이에서.", "자사와 경쟁사의 검색량, 홈페이지 메시지, SNS·매체 운영 현황을 "
     "동일한 기준으로 나란히 비교합니다.", brand_visual, False),
    ("04", "CREATIVE", "지금 실제로 집행되는\n광고까지.", "Meta Ads Library에 노출 중인 실제 광고 소재를 수집해 "
     "메시지·표현 방식·운영 기간을 분석합니다.", creative_visual, True),
    ("05", "SYNTHESIS", "데이터를\n전략으로.", "앞선 네 가지 분석이 쌓이면, 별도 수집 없이 결과를 조합해 "
     "포지셔닝과 White Space, 핵심 기회를 한 줄 인사이트로 도출합니다.", synthesis_visual, False),
]
for num, eyebrow_text, lead, desc, visual_fn, reverse in stories:
    with st.container():
        st.markdown('<div class="adetect-section">', unsafe_allow_html=True)
        feature_story(num, eyebrow_text, lead.replace("\n", "<br>"), desc, visual_fn(), reverse=reverse)
        st.markdown("</div>", unsafe_allow_html=True)

# ── SECTION 07 · PRODUCT PREVIEW ─────────────────────────────────────────
with st.container():
    st.markdown('<div class="adetect-section">', unsafe_allow_html=True)
    section_header_block("Inside the Workspace", "분석은 탭 하나에서<br>끝까지 이어집니다.",
                          "수집 → 분석 → 다운로드가 화면 전환 없이 같은 Workspace 안에서 이어집니다.")
    st.write("")
    st.markdown(
        '<div class="adetect-preview-frame">'
        '<div class="adetect-preview-dots"><span></span><span></span><span></span></div>'
        '<div class="adetect-context-bar" style="margin-bottom:1.3rem;">'
        '<span class="adetect-context-brand">메리츠화재</span>'
        '<span class="adetect-context-meta">손해보험</span>'
        '<span class="adetect-context-meta">30~50대 남녀</span>'
        '<div class="adetect-context-chips">'
        '<span class="adetect-context-chip"><b>시장</b><span class="adetect-status-dot st-done">완료</span></span>'
        '<span class="adetect-context-chip"><b>브랜드</b><span class="adetect-status-dot st-done">완료</span></span>'
        '<span class="adetect-context-chip"><b>소재</b><span class="adetect-status-dot st-partial">부분 실패</span></span>'
        '<span class="adetect-context-chip"><b>타겟</b><span class="adetect-status-dot st-running">진행중</span></span>'
        '</div></div>'
        '<div class="adetect-metric-row" style="padding-bottom:0.8rem;">'
        '<div class="adetect-metric"><div class="adetect-metric-label">검색량 증감(3M)</div>'
        '<div class="adetect-metric-value">+18<span class="unit">%</span></div>'
        '<div class="adetect-metric-trend up">▲ 전월 대비 상승</div></div>'
        '<div class="adetect-metric"><div class="adetect-metric-label">활성 광고 소재</div>'
        '<div class="adetect-metric-value">42<span class="unit">건</span></div></div>'
        '<div class="adetect-metric"><div class="adetect-metric-label">SOV(뉴스)</div>'
        '<div class="adetect-metric-value">31<span class="unit">%</span></div></div>'
        '</div>'
        '<div class="adetect-insight">'
        '<div class="adetect-insight-head">'
        '<span class="adetect-badge adetect-badge-ai">AI INTERPRETATION</span><b>시장 인사이트</b></div>'
        '<p style="color:#9AA4B2;margin:0;font-size:0.9rem;line-height:1.7;">검색량은 증가하고 있지만 '
        '경쟁사 대비 브랜드 검색 유입 비중은 낮습니다.</p></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── SECTION 08 · CTA ──────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="adetect-section">', unsafe_allow_html=True)
    cta_section("분석할 브랜드가 있다면,<br>바로 시작하세요.")
    _command_bar("cta")
    st.markdown("</div>", unsafe_allow_html=True)
