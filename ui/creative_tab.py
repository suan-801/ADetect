"""소재분석 탭 — PRD §7-11-(4). 이번 스프린트에서는 담당자 미배정, 화면 골격만 제공."""
from __future__ import annotations

import streamlit as st

from ui.components import feature_intro, tab_header


def render(session: dict):
    tab_header("CREATIVE", "소재분석", "○")
    feature_intro([
        "Meta Ads Library 활성 광고 소재 (FB+IG 노출 포함)",
        "소구포인트 다중 라벨 태깅 및 비중",
        "운영기간 분석 (단기/중기/장기)",
    ])
    st.button("소재분석 시작하기", disabled=True, key="btn_start_creative")
    st.caption("담당자 배정 후 core/scrapers/ad_library.py 확장 + core/analyzers에 소구 태깅 로직을 추가하면 됩니다.")
