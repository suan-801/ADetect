"""홈 — Hero 단일 화면 (2026-09-20 축소).

이전 리비전(4차 리뉴얼)은 Hero → Manifesto → Market → Brand → Creative → Synthesis →
Sample Output → Final CTA로 이어지는 긴 scroll scene이었으나, 사용자 피드백에 따라 첫
화면(Hero)만 남기고 그 뒤에 이어지던 Product Story/Sample Output/Final CTA 섹션은
제거했다. 화면 구성만 바뀌며 제품 흐름(PRD §0 18차: 프로젝트 → 수집 → 확인·다운로드)은
Analyze 페이지가 담당한다.

Hero는 LAYER 1 LIVE PRODUCT ENTRY(Brand Input/CTA, 실제로 동작하는 유일한 interactive
영역)만 남은 상태다.
"""
from __future__ import annotations

import streamlit as st

from config.theme import command_marker, home_page_marker, scene_marker
from ui.hero import render_hero_copy, render_hero_visual, render_pipeline_rail

home_page_marker()


def _command_bar(key_prefix: str, label: str = "START HERE"):
    """LAYER 1 — Hero의 유일한 실제 interactive 영역(브랜드 입력 → 프로젝트 만들기).

    Home에서 브랜드명(+선택적으로 관심 주제)을 입력받았으므로 프로젝트 목록을 거치지 않고
    바로 프로젝트 설정 화면(step="config")으로 진입한다 — 같은 값을 다시 입력하라고 요구하는
    중복 스텝을 없앤다. draft["brand_name"]/draft["category"]를 ui/project_workspace._config가
    초기값으로 사용한다. 함께 조사할 브랜드(경쟁사)는 18차 개정의 프로젝트 단위(브랜드 1개)에
    없는 입력이므로 화면에 두지 않는다.
    """
    with st.container():
        command_marker()
        st.markdown(f"<span class='adetect-command-label'>{label}</span>", unsafe_allow_html=True)
        input_col, btn_col = st.columns([5, 1.3], vertical_alignment="bottom")
        with input_col:
            brand_name = st.text_input(
                "브랜드명", placeholder="브랜드명을 입력하세요", label_visibility="collapsed", key=f"{key_prefix}_brand_input"
            )
        with btn_col:
            start = st.button("자료 수집 시작 →", type="primary", key=f"{key_prefix}_start_btn", width="stretch")

        with st.expander("+ 관심 주제 설정"):
            category = st.text_input("관심 주제", placeholder="예: TM 채용 (선택)", key=f"{key_prefix}_category_input")

        if start:
            if not brand_name.strip():
                st.error("브랜드명을 입력해주세요.")
            else:
                for key in list(st.session_state):
                    if not key.startswith(key_prefix+"_"):
                        del st.session_state[key]
                st.session_state.draft = {
                    "brand_name": brand_name.strip(),
                    "category": st.session_state.get(f"{key_prefix}_category_input", "").strip(),
                }
                st.session_state.step = "config"
                st.switch_page("app_pages/2_analyze.py")


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
