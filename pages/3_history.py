"""이력 관리 — PRD §16-6. 세션을 클릭하면 Workspace로 재진입합니다.

카드 grid 대신 row 기반 compact list로 표현합니다 — 최근 분석이 가장 위에 오고,
브랜드/카테고리/생성일/타겟 상태를 한 줄에서 훑어볼 수 있게 합니다.
"""
from __future__ import annotations

import html
import json

import streamlit as st

from database.db import list_sessions
from ui.components import section_header_block

section_header_block("History", "이력 관리")
st.caption(
    "최근 분석 세션 목록입니다. '열기'를 누르면 같은 브랜드/카테고리/경쟁사 기준으로 Workspace를 다시 엽니다 — "
    "기능별 실행 결과 자동 복원은 아직 준비 중이라(function_run 저장 미구현) 각 탭은 다시 실행해야 합니다."
)
st.write("")

sessions = list_sessions()

if not sessions:
    st.markdown(
        '<div class="adetect-empty"><p class="adetect-empty-desc">'
        "아직 분석 세션이 없습니다. 'Analyze' 메뉴에서 새 분석을 시작해보세요.</p></div>",
        unsafe_allow_html=True,
    )
else:
    target_status_label = {"not_set": "타겟 미확정", "recommended": "타겟 추천됨", "confirmed": "타겟 확정"}
    for s in sessions:
        competitors = json.loads(s["competitors_json"] or "[]")
        row_col, action_col = st.columns([5, 1], vertical_alignment="center")
        with row_col:
            st.markdown(
                '<div class="adetect-row">'
                '<div class="adetect-row-main">'
                f'<p class="adetect-row-brand">{html.escape(s["brand_name"])}'
                f'<span style="color:#667080;font-weight:380;"> · {html.escape(s["category"] or "카테고리 미지정")}</span></p>'
                f'<p class="adetect-row-meta">경쟁사 {len(competitors)}개 · 생성일 {html.escape(s["created_at"][:19])} · '
                f'{target_status_label.get(s["target_status"], s["target_status"])}</p>'
                "</div></div>",
                unsafe_allow_html=True,
            )
        with action_col:
            if st.button("열기 →", key=f"reenter_{s['id']}"):
                st.session_state.session = {
                    "id": s["id"],
                    "brand_name": s["brand_name"],
                    "category": s["category"],
                    "competitors": competitors,
                    "market_status": "미실행",
                    "brand_status": "미실행",
                    "creative_status": "미실행",
                    "target_status": s["target_status"],
                    "confirmed_target": s["confirmed_target"],
                }
                st.session_state.step = "workspace"
                st.switch_page("pages/2_analyze.py")
