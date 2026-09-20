"""홈 — Hero 단일 화면 (2026-09-20 축소).

이전 리비전(4차 리뉴얼)은 Hero → Manifesto → Market → Brand → Creative → Synthesis →
Sample Output → Final CTA로 이어지는 긴 scroll scene이었으나, 사용자 피드백에 따라 첫
화면(Hero)만 남기고 그 뒤에 이어지던 Product Story/Sample Output/Final CTA 섹션은
제거했다. 기능(4단계 IA, STEP1 입력 플로우, Target Insight 구조)은 바뀌지 않는다 —
바뀌는 것은 Home의 화면 구성뿐이다.

Hero는 LAYER 1 LIVE PRODUCT ENTRY(Brand Input/CTA, 실제로 동작하는 유일한 interactive
영역)만 남은 상태다.
"""
from __future__ import annotations

import streamlit as st

from config.theme import command_marker, home_page_marker, scene_marker
from ui.hero import render_hero_copy, render_hero_visual, render_pipeline_rail

home_page_marker()


def _command_bar(key_prefix: str, label: str = "START HERE"):
    """LAYER 1 — Hero의 유일한 실제 interactive 영역(브랜드 입력 → 분석 시작)."""
    with st.container():
        command_marker()
        st.markdown(f"<span class='adetect-command-label'>{label}</span>", unsafe_allow_html=True)
        input_col, btn_col = st.columns([5, 1.3], vertical_alignment="bottom")
        with input_col:
            brand_name = st.text_input(
                "브랜드명", placeholder="브랜드명을 입력하세요", label_visibility="collapsed", key=f"{key_prefix}_brand_input"
            )
        with btn_col:
            start = st.button("분석 시작 →", type="primary", key=f"{key_prefix}_start_btn", width="stretch")

        with st.expander("+ 카테고리 · 경쟁사 직접 설정"):
            category = st.text_input("카테고리", placeholder="비워두면 AI가 추천", key=f"{key_prefix}_category_input")
            competitors = st.text_input(
                "경쟁사", placeholder="쉼표로 구분, 비워두면 AI가 추천", key=f"{key_prefix}_competitors_input"
            )

        if start:
            if not brand_name.strip():
                st.error("브랜드명을 입력해주세요.")
            else:
                st.session_state.prefill_brand = brand_name.strip()
                st.session_state.prefill_category = st.session_state.get(f"{key_prefix}_category_input", "").strip()
                st.session_state.prefill_competitors = st.session_state.get(f"{key_prefix}_competitors_input", "").strip()
                st.session_state.step = "input"
                st.session_state.session = None
                st.switch_page("pages/2_analyze.py")


# ── 01 · HERO SCENE ──────────────────────────────────────────────────────
# background.png(공식 Hero asset)가 atmosphere + primary visual anchor를 담당한다(§40~48).
# Visual priority: Headline > background.png > Brand Input > Intelligence Pipeline(§65).
with st.container():
    scene_marker("adetect-hero-scene adetect-bleed")
    render_hero_visual()
    with st.container():
        scene_marker("adetect-hero-content")
        render_hero_copy()
        st.write("")
        _command_bar("hero")
        render_pipeline_rail()
