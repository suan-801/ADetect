"""탭 전반에서 재사용하는 작은 UI 조각들. 카드로 감싸지 않고, 여백/구분선/타이포로 위계를 표현합니다."""
from __future__ import annotations

import streamlit as st

from config.theme import badge, section_title

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
    """PRD §16-2 상태 기호 (○/●/✓/△/✕/취소/🔒) — 장식용 이모지가 아니라 규격화된 상태 표기입니다.
    tab_header()의 상태 텍스트로 쓰일 때는 옅은 회색의 아주 작은 텍스트로만 표시됩니다."""
    return STATUS_ICON.get(status, "○")


def render_insight_card(title: str, insight_obj: dict, kind: str = "AI"):
    """§8 insight/source/evidence/confidence 스키마 렌더링 — 박스가 아니라 얇은 상단 구분선."""
    st.markdown(
        f'<div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:0.9rem;margin-top:0.6rem;">'
        f'{badge(kind)}<b>{title}</b></div>',
        unsafe_allow_html=True,
    )
    st.write(insight_obj.get("insight", ""))
    conf = insight_obj.get("confidence")
    if conf:
        st.caption(f"Confidence — {conf}")
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


def module_row(label: str, title: str, desc: str):
    """홈 화면의 '주요 분석 기능' — 동일한 카드 4개 나열이 아니라 얇은 구분선의 에디토리얼 리스트."""
    st.markdown(
        f'<div class="adetect-module">'
        f'<div class="adetect-module-label">{label}</div>'
        f'<div><p class="adetect-module-title">{title}</p>'
        f'<p class="adetect-module-desc">{desc}</p></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def tab_header(label: str, title: str, status_text: str = ""):
    """탭 상단 헤더 — st.subheader(emoji + 텍스트) 대신 eyebrow + 제목 + 상태."""
    section_title(label, title, status_text)


def feature_intro(desc_lines: list[str]):
    """탭의 '미실행' 상태에서 보여주는 짧은 설명 — 박스 없이 텍스트만."""
    for line in desc_lines:
        st.markdown(f'<p class="adetect-module-desc">{line}</p>', unsafe_allow_html=True)
