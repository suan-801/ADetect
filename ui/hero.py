"""홈 Hero 영역 — Copy / Intelligence Pipeline 두 개의 독립 컴포넌트로 구성합니다.

3차 리뉴얼: 이전의 blue glow orb를 제거하고, ADetect의 실제 제품 구조(5단계 분석 파이프라인)를
thin line + number + typography로 표현하는 IntelligencePipeline으로 교체했다 — 장식이 아니라
제품이 실제로 무엇을 하는지 보여주는 visual이다.
"""
from __future__ import annotations

import streamlit as st

from ui.components import intelligence_pipeline

PIPELINE_STEPS = [
    ("01", "MARKET"),
    ("02", "AUDIENCE"),
    ("03", "BRAND"),
    ("04", "CREATIVE"),
    ("05", "SYNTHESIS"),
]


def render_hero_copy():
    """Hero 왼쪽의 eyebrow + headline + 보조 설명."""
    st.markdown(
        "<span class='adetect-eyebrow'>ADetect · Brand Intelligence</span>"
        "<p class='adetect-hero-title'>브랜드를 입력하면,<br>시장이 연결됩니다.</p>"
        "<p class='adetect-hero-sub'>시장 · 타겟 · 경쟁사 · 광고 소재를 연결해 "
        "실행 가능한 인사이트로 정리합니다.</p>",
        unsafe_allow_html=True,
    )


def render_hero_object():
    """Hero 오른쪽 — Intelligence Pipeline (5단계 분석 구조) visual."""
    intelligence_pipeline(PIPELINE_STEPS)
