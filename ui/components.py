"""탭/페이지 전반에서 재사용하는 UI 컴포넌트. 카드로 감싸지 않고,
여백/구분선/타이포/절제된 glow로 위계를 표현합니다 (design system, docs/PROJECT_PLAN.md §5).
"""
from __future__ import annotations

import html as _html

import streamlit as st

from config.theme import badge, eyebrow, section_title

STATUS_ICON = {
    "미실행": "○",
    "진행중": "●",
    "완료": "✓",
    "부분 실패": "△",
    "전체 실패": "✕",
    "취소": "취소",
    "잠금": "🔒",
}

_STATUS_CLASS = {
    "미실행": "st-idle",
    "진행중": "st-running",
    "완료": "st-done",
    "부분 실패": "st-partial",
    "전체 실패": "st-fail",
    "취소": "st-cancel",
    "잠금": "st-locked",
}


def status_icon(status: str) -> str:
    """PRD §16-2 상태 기호 (○/●/✓/△/✕/취소/🔒) — 규격화된 상태 표기."""
    return STATUS_ICON.get(status, "○")


def status_badge(status: str, label: str | None = None) -> str:
    """작은 컬러 도트 + 텍스트로 상태를 표현하는 HTML 조각 (StatusBadge 컴포넌트)."""
    cls = _STATUS_CLASS.get(status, "st-idle")
    text = label if label is not None else status
    return f'<span class="adetect-status-dot {cls}">{_html.escape(text)}</span>'


def render_insight_card(title: str, insight_obj: dict, kind: str = "AI"):
    """§8 insight/source/evidence/confidence 스키마 렌더링 — InsightBlock 컴포넌트.
    좌측 얇은 accent 라인 + badge + 근거는 expander 안에 접어 화면 밀도를 낮춥니다."""
    st.markdown(
        f'<div class="adetect-insight">'
        f'<div class="adetect-insight-head">{badge(kind)}<b>{_html.escape(title)}</b></div>'
        f'</div>',
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


def metric_row(items: list[tuple[str, str, str | None]]):
    """Metric 컴포넌트 — 숫자 + 작은 라벨 + trend. 카드 대신 가로로 나열합니다.
    items: [(label, value_html, trend)] — trend는 'up'/'down'/'flat'/None."""
    cells = []
    for label, value_html, trend in items:
        trend_html = ""
        if trend:
            arrow = {"up": "▲", "down": "▼", "flat": "–"}.get(trend, "–")
            trend_html = f'<div class="adetect-metric-trend {trend}">{arrow}</div>'
        cells.append(
            f'<div class="adetect-metric">'
            f'<div class="adetect-metric-label">{_html.escape(label)}</div>'
            f'<div class="adetect-metric-value">{value_html}</div>'
            f"{trend_html}</div>"
        )
    st.markdown(f'<div class="adetect-metric-row">{"".join(cells)}</div>', unsafe_allow_html=True)


def module_row(label: str, title: str, desc: str):
    """하위 호환용 — 얇은 구분선 에디토리얼 리스트 한 행 (더 이상 Home 기본 레이아웃은 아님)."""
    st.markdown(
        f'<div class="adetect-module">'
        f'<div class="adetect-module-label">{_html.escape(label)}</div>'
        f'<div><p class="adetect-module-title">{_html.escape(title)}</p>'
        f'<p class="adetect-module-desc">{_html.escape(desc)}</p></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def tab_header(label: str, title: str, status_text: str = ""):
    """탭 상단 헤더 — eyebrow + 제목 + 상태."""
    section_title(label, title, status_text)


def feature_intro(desc_lines: list[str]):
    """EmptyState 컴포넌트 — 탭의 '미실행'/게이트 잠금 상태에서 보여주는 설명. 박스 없이 텍스트만."""
    lines_html = "".join(f'<p class="adetect-empty-desc">{_html.escape(line)}</p>' for line in desc_lines)
    st.markdown(f'<div class="adetect-empty">{lines_html}</div>', unsafe_allow_html=True)


def brand_context_bar(session: dict, status_items: list[tuple[str, str]]):
    """Workspace 상단 Brand Context Bar — 브랜드명/카테고리/타겟 + 5개 기능 상태를 한 줄로.
    status_items: [(라벨, status 문자열 또는 '🔒')]."""
    target_display = session.get("confirmed_target") or "타겟 미확정"
    chips = []
    for label, status in status_items:
        if status == "🔒":
            chip_html = f'<span class="adetect-status-dot st-locked">잠금</span>'
        else:
            chip_html = status_badge(status)
        chips.append(f'<span class="adetect-context-chip"><b>{_html.escape(label)}</b>{chip_html}</span>')

    st.markdown(
        f'<div class="adetect-context-bar">'
        f'<span class="adetect-context-brand">{_html.escape(session["brand_name"])}</span>'
        f'<span class="adetect-context-meta">{_html.escape(session.get("category") or "카테고리 미지정")}</span>'
        f'<span class="adetect-context-meta">{_html.escape(target_display)}</span>'
        f'<div class="adetect-context-chips">{"".join(chips)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def section_header_block(eyebrow_text: str, title_html: str, desc: str | None = None):
    """Home 등에서 쓰는 큰 섹션 헤더 — eyebrow + display title (+ 선택 설명)."""
    desc_html = f'<p class="adetect-body-lg" style="margin-top:1rem;">{desc}</p>' if desc else ""
    st.markdown(
        f'{eyebrow(eyebrow_text)}<p class="adetect-display-title">{title_html}</p>{desc_html}',
        unsafe_allow_html=True,
    )


def feature_story(num: str, eyebrow_text: str, lead: str, desc: str, visual_svg: str, reverse: bool = False):
    """Home §3~6 — 기능 하나를 하나의 story section으로 표현. desktop에서 visual/copy를 번갈아 배치."""
    st.markdown(f'<div class="adetect-section-eyebrow-num">{_html.escape(num)}</div>', unsafe_allow_html=True)
    copy_col, visual_col = st.columns([1.05, 1], gap="large")
    if reverse:
        copy_col, visual_col = visual_col, copy_col
    with copy_col:
        st.markdown(
            f'<div class="adetect-story-copy">{eyebrow(eyebrow_text)}'
            f'<p class="adetect-story-lead">{lead}</p>'
            f'<p class="adetect-story-desc">{desc}</p></div>',
            unsafe_allow_html=True,
        )
    with visual_col:
        st.markdown(f'<div class="adetect-story-panel">{visual_svg}</div>', unsafe_allow_html=True)


def cta_section(title: str):
    st.markdown(f'<p class="adetect-cta-title">{title}</p>', unsafe_allow_html=True)
