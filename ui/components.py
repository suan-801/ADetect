"""탭 전반에서 재사용하는 작은 UI 조각들. (PRD §16 공통 컴포넌트)"""
from __future__ import annotations

import streamlit as st

from config.theme import badge

STATUS_ICON = {
    "미실행": "○",
    "진행중": "●",
    "완료": "✓",
    "부분 실패": "△",
    "전체 실패": "✕",
    "취소": "취소",
    "잠금": "🔒",
}


def status_icon(status: str) -> str:
    return STATUS_ICON.get(status, "○")


def render_insight_card(title: str, insight_obj: dict, kind: str = "AI"):
    """§8 insight/source/evidence/confidence 스키마를 카드 형태로 렌더링."""
    with st.container(border=True):
        st.markdown(f"{badge(kind)} **{title}**", unsafe_allow_html=True)
        st.write(insight_obj.get("insight", ""))
        conf = insight_obj.get("confidence")
        if conf:
            st.caption(f"Confidence: {conf}")
        with st.expander("근거 보기 (source / evidence)"):
            st.write("**Source**")
            for s in insight_obj.get("source", []):
                st.write(f"- {s}")
            st.write("**Evidence**")
            for e in insight_obj.get("evidence", []):
                st.write(f"- {e}")


def sample_data_notice():
    st.markdown(badge("SAMPLE"), unsafe_allow_html=True)
    st.caption("지금 보이는 수치/문구는 실제 수집 데이터가 아닌 프로토타입용 샘플입니다.")


def feature_card(icon: str, title: str, desc: str):
    with st.container(border=True):
        st.markdown(f"### {icon} {title}")
        st.write(desc)
