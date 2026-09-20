"""탭/페이지 전반에서 재사용하는 UI 컴포넌트 (3차 리뉴얼 — Brand Intelligence Platform).

카드로 감싸지 않고, 여백/구분선/타이포/절제된 accent로 위계를 표현합니다. glow/gradient/
과도한 radius는 config/theme.py에서 전면 제거했고, 이 파일의 컴포넌트들도 그 규칙을 따릅니다.
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

# Analysis Status 인덱스에서 쓰는 표시 라벨(§9) — 데이터를 지어내지 않고 실제 status 값만 재표기.
_STATUS_DISPLAY_LABEL = {
    "미실행": "대기",
    "완료": "완료",
    "부분 실패": "부분 실패",
    "전체 실패": "실패",
    "취소": "취소",
    "잠금": "잠금",
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

    "AI INTERPRETATION" 같은 굵은 배지 대신 작은 INSIGHT 라벨을 먼저 보여주고, 실제 분석
    문장을 가장 먼저 읽히게 한다. Evidence는 소스 칩으로, AI 생성 여부는 하단 작은 meta로.
    """
    kind_label = {"FACT": "FACT", "AI": "INSIGHT", "REC": "RECOMMENDATION", "SAMPLE": "SAMPLE DATA"}.get(kind, kind)
    kind_cls = {"AI": "kind-ai", "REC": "kind-rec"}.get(kind, "")
    st.markdown(
        f'<div class="adetect-insight">'
        f'<div class="adetect-insight-label {kind_cls}">{_html.escape(kind_label)}</div>'
        f'<div class="adetect-insight-title">{_html.escape(title)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.write(insight_obj.get("insight", ""))

    sources = insight_obj.get("source", [])
    if sources:
        chips = "".join(f'<span class="adetect-evidence-chip">{_html.escape(str(s))}</span>' for s in sources)
        st.markdown(f'<div class="adetect-evidence-chips">{chips}</div>', unsafe_allow_html=True)

    evidence = insight_obj.get("evidence", [])
    if evidence:
        with st.expander("근거 상세 보기"):
            for e in evidence:
                st.write(f"- {e}")

    meta_bits = []
    conf = insight_obj.get("confidence")
    if conf:
        meta_bits.append(f"Confidence — {conf}")
    if kind == "AI":
        meta_bits.append("AI generated")
    if meta_bits:
        st.markdown(f'<div class="adetect-insight-meta">{" · ".join(meta_bits)}</div>', unsafe_allow_html=True)


def sample_data_notice():
    st.markdown(badge("SAMPLE"), unsafe_allow_html=True)
    st.caption("지금 보이는 수치/문구는 실제 수집 데이터가 아닌 프로토타입용 샘플입니다.")


def prototype_notice(text: str):
    """탭 헤더 바로 아래에 붙이는 개발 진행 상태 caption — Market/Brand/Synthesis처럼 일부만
    실연동된 탭에서, 어디까지 실제 데이터고 어디부터 화면 골격뿐인지 작게 알려준다.

    sample_data_notice()가 "지금 보이는 이 숫자가 샘플이다"를 알리는 sub-tab 단위 배지라면,
    이 함수는 탭 전체 단위로 "이 탭이 지금 어느 정도까지 구현됐는가"를 알리는 한 줄 caption이다
    — 큰 warning box 대신 작은 metadata로만 노출한다(개발 상태를 사용자에게 과장해서 보여주지
    않는다는 원칙). Creative처럼 이미 end-to-end로 동작하는 탭에는 붙이지 않는다.
    """
    st.caption(text)


def metric_row(items: list[tuple[str, str, str | None]]):
    """Metric 컴포넌트 — 전체 폭을 균등 분할하고 vertical divider로 구분합니다.
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


def tab_header(label: str, title: str, status_text: str = ""):
    """탭 상단 헤더 — eyebrow + Analysis headline + 상태."""
    section_title(label, title, status_text)


def feature_intro(desc_lines: list[str]):
    """EmptyState 컴포넌트 — 탭의 '미실행'/게이트 잠금 상태에서 보여주는 설명. 박스 없이 텍스트만."""
    lines_html = "".join(f'<p class="adetect-empty-desc">{_html.escape(line)}</p>' for line in desc_lines)
    st.markdown(f'<div class="adetect-empty">{lines_html}</div>', unsafe_allow_html=True)


def brand_context_header(session: dict):
    """BrandContextHeader 컴포넌트 — Analysis Header 왼쪽 블록(브랜드/카테고리/경쟁사).

    Target은 더 이상 독립 설정/분석 단계가 아니므로(§16) 여기서 "타겟 미확정" 문구를
    보여주지 않는다 — Target Insight는 종합분석 탭 결과 안에서만 노출한다.
    """
    competitors = session.get("competitors") or []
    meta_bits = [f"<b>{_html.escape(session.get('category') or '카테고리 미지정')}</b>"]
    if competitors:
        meta_bits.append(f"경쟁사 {len(competitors)}개")
    st.markdown(
        '<div class="adetect-context-block">'
        f'<p class="adetect-context-brand">{_html.escape(session["brand_name"])}</p>'
        f'<p class="adetect-context-meta">{" · ".join(meta_bits)}</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def analysis_status_index(status_items: list[tuple[str, str]]):
    """AnalysisStatus 컴포넌트 — Analysis Header 오른쪽 블록.
    가로로 길게 나열하던 상태 목록을 01~N vertical index로 재구성했다(N=Primary Analysis
    Function 개수, 현재 4개 — 시장/브랜드/소재/종합. Target은 독립 항목이 아니다, §17).
    status_items: [(기능명, status 문자열 또는 '🔒')]."""
    done_count = sum(1 for _, s in status_items if s in ("완료", "부분 실패"))
    rows = []
    for i, (label, status) in enumerate(status_items, start=1):
        st_key = "잠금" if status == "🔒" else status
        cls = _STATUS_CLASS.get(st_key, "st-idle")
        display = _STATUS_DISPLAY_LABEL.get(st_key, st_key)
        rows.append(
            f'<div class="adetect-status-row">'
            f'<span class="adetect-status-num">{i:02d}</span>'
            f'<span class="adetect-status-name">{_html.escape(label)}</span>'
            f'<span class="adetect-status-value {cls}">{_html.escape(display)}</span>'
            f'</div>'
        )
    st.markdown(
        '<div class="adetect-status-header">'
        '<span class="adetect-status-label">Analysis Status</span>'
        f'<span class="adetect-status-count">{done_count} / {len(status_items)}</span>'
        '</div>' + "".join(rows),
        unsafe_allow_html=True,
    )


def section_header_block(eyebrow_text: str, title_html: str, desc: str | None = None):
    """Home 등에서 쓰는 섹션 헤더 — eyebrow + Section headline (+ 선택 설명)."""
    desc_html = f'<p class="adetect-body-lg" style="margin-top:1rem;">{desc}</p>' if desc else ""
    st.markdown(
        f'{eyebrow(eyebrow_text)}<p class="adetect-display-title">{title_html}</p>{desc_html}',
        unsafe_allow_html=True,
    )


