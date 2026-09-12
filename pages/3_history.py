"""이력 관리 — PRD §16-6. 세션을 클릭하면 Workspace로 재진입합니다."""
from __future__ import annotations

import json

import streamlit as st

from database.db import list_sessions

st.markdown(
    "<span class='adetect-eyebrow'>History</span>"
    "<p class='adetect-hero-title' style='font-size:1.7rem;'>이력 관리</p>",
    unsafe_allow_html=True,
)
st.caption("최근 분석 세션 목록입니다. 세션을 클릭하면 그 Workspace로 재진입합니다 (다운로드는 각 탭 안에서).")
st.write("")

sessions = list_sessions()

if not sessions:
    st.caption("아직 분석 세션이 없습니다. '분석하기' 메뉴에서 새 분석을 시작해보세요.")
else:
    for s in sessions:
        competitors = json.loads(s["competitors_json"] or "[]")
        st.markdown(
            "<div style='border-top:1px solid rgba(255,255,255,0.07);padding:1.1rem 0;'>"
            f"<p style='margin:0;font-weight:500;'>{s['brand_name']}"
            f"<span style='color:#5C5C60;font-weight:350;'> · {s['category'] or '-'}</span></p>"
            f"<p style='margin:0.25rem 0 0 0;color:#9A9A9E;font-size:0.85rem;'>"
            f"경쟁사 {len(competitors)}개 · 생성일 {s['created_at'][:19]} · 타겟 {s['target_status']}</p>"
            "</div>",
            unsafe_allow_html=True,
        )
