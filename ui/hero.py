"""홈 Hero 영역 — Copy / Object 두 개의 독립 컴포넌트로 구성합니다.

Analysis Form은 session_state·페이지 전환 로직과 얽혀 있어 pages/1_home.py에 그대로 두지만,
Hero Copy와 Hero Object는 그 로직과 무관하므로 이 모듈로 분리했습니다.

Hero Object는 오리지널 abstract SVG(ui/illustrations.hero_visual)를 사용합니다 — 레퍼런스
이미지의 오브젝트를 복제하지 않고 ADetect 고유 팔레트(ice/cyan/violet)로 구성했습니다.
실제 3D 렌더 에셋(PNG/WebP)으로 교체하려면 render_hero_object()의 svg 변수를
`<img src="...">`로 바꾸기만 하면 되고, 레이아웃(.adetect-hero-visual)은 그대로 재사용됩니다.
"""
from __future__ import annotations

import streamlit as st

from ui.illustrations import hero_visual


def render_hero_copy():
    """Hero 왼쪽의 eyebrow + headline + 보조 설명."""
    st.markdown(
        "<span class='adetect-eyebrow'>ADetect · Brand Intelligence</span>"
        "<p class='adetect-hero-title'>브랜드 하나로,<br>시장을 읽다.</p>"
        "<p class='adetect-hero-sub'>브랜드명 하나로 시장·타겟·경쟁사·광고 소재를 연결하고, "
        "AI가 실행 가능한 인사이트로 정리합니다.</p>",
        unsafe_allow_html=True,
    )


def render_hero_object():
    """Hero 오른쪽의 3D visual anchor 역할을 하는 오리지널 abstract SVG."""
    st.markdown(f'<div class="adetect-hero-visual">{hero_visual()}</div>', unsafe_allow_html=True)
