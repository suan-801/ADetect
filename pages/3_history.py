"""이력 관리 — PRD §16-6. 세션을 클릭하면 Workspace로 재진입합니다."""
from __future__ import annotations

import json

import streamlit as st

from database.db import list_sessions

st.title("이력 관리")
st.caption("최근 분석 세션 목록입니다. 세션을 클릭하면 그 Workspace로 재진입합니다 (다운로드는 각 탭 안에서).")

sessions = list_sessions()

if not sessions:
    st.info("아직 분석 세션이 없습니다. '분석하기' 메뉴에서 새 분석을 시작해보세요.")
else:
    for s in sessions:
        competitors = json.loads(s["competitors_json"] or "[]")
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{s['brand_name']}** · {s['category'] or '-'}")
                st.caption(f"경쟁사 {len(competitors)}개 · 생성일 {s['created_at'][:19]} · 타겟: {s['target_status']}")
            with c2:
                st.button("Workspace 열기 (준비 중)", disabled=True, key=f"open_{s['id']}")
