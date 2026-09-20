"""홈 Hero 영역 — 4차 리뉴얼: 사용자가 확정한 공식 Hero visual asset
(`ui/assets/home/background.png`)을 Hero의 atmospheric background + primary visual anchor로
사용한다(PROJECT_PLAN.md §8 "Hero Master Asset" 참고).

이 이미지는 임시 참고 이미지가 아니라 이번 리뉴얼의 source of truth다 — 비슷한 visual을 CSS로
다시 만들거나, 새 abstract visual을 임의로 추가하지 않는다. Intelligence Pipeline은 더 이상
Hero의 Main Illustration이 아니라(그 역할은 이제 background.png), 제품 구조를 알려주는 compact
secondary index(가로 rail)로 축소한다.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# Target은 독립 파이프라인 단계가 아니라 Synthesis 내부의 Target Insight다 — 사용자에게
# 보이는 Top-level flow는 항상 4단계로 통일한다 (Home Pipeline/Story, Workspace 탭, Status Index).
PIPELINE_STEPS = [
    ("01", "MARKET"),
    ("02", "BRAND"),
    ("03", "CREATIVE"),
    ("04", "SYNTHESIS"),
]

_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "home"
_BACKGROUND_WEBP = _ASSET_DIR / "background.webp"
_BACKGROUND_PNG = _ASSET_DIR / "background.png"


@st.cache_data(show_spinner=False)
def _hero_background_data_uri() -> str | None:
    """background.png(원본 마스터 에셋)를 WebP로 인라인 임베드한다 — Streamlit이 임의 정적
    파일을 URL로 서빙하지 않으므로, fragile한 static-serving 설정 대신 CSS data URI를 쓴다
    (안정적인 방식, §43 참고). WebP가 없으면 PNG 원본으로 폴백."""
    path = _BACKGROUND_WEBP if _BACKGROUND_WEBP.exists() else _BACKGROUND_PNG
    if not path.exists():
        return None
    mime = "image/webp" if path.suffix == ".webp" else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def render_hero_copy():
    """Hero 안전 영역(왼쪽) — wordmark eyebrow + headline + 짧은 설명.

    구 카피("시장 · 타겟 · 경쟁사 · 광고 소재를 연결해...")는 Target이 더 이상 독립 단계가
    아닌 지금 IA와 맞지 않아(§0 16차 개정) 제거했다 — 과거 5단계 IA를 연상시키는 표현을 쓰지
    않는다.
    """
    st.markdown(
        "<span class='adetect-hero-wordmark'><b>ADetect</b> · Brand Intelligence Engine</span>"
        "<p class='adetect-hero-title'>브랜드를 입력하면,<br>시장이 연결됩니다.</p>"
        "<p class='adetect-hero-sub'>시장, 브랜드, 광고 소재의 신호를 하나의 전략으로 연결합니다.</p>",
        unsafe_allow_html=True,
    )


def render_hero_visual():
    """background.png — decorative atmospheric layer. 카드/보더/그림자로 감싸지 않고 Hero
    scene 전체에 absolute full-bleed로 깐다(§43~48). 순수 장식이므로 pointer-events 없음."""
    data_uri = _hero_background_data_uri()
    if not data_uri:
        return
    st.markdown(
        f'<div class="adetect-hero-visual-layer" style="background-image:url({data_uri});" '
        f'role="presentation" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def render_pipeline_rail():
    """Intelligence Pipeline — Hero의 secondary information layer(§49~52). 4단계 전부를
    같은 비중(동일 색상)으로 보여준다 — 특정 단계만 강조하면 "지금 진행 중인 단계"처럼
    오독되므로 쓰지 않는다."""
    items = "".join(
        '<div class="adetect-pipeline-rail-item">'
        f'<span class="adetect-pipeline-rail-num">{num}</span>'
        f'<span class="adetect-pipeline-rail-label">{label}</span></div>'
        for num, label in PIPELINE_STEPS
    )
    st.markdown(
        "<span class='adetect-eyebrow' style='margin-bottom:0;'>Intelligence Pipeline</span>"
        f'<div class="adetect-pipeline-rail">{items}</div>',
        unsafe_allow_html=True,
    )
