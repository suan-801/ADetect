"""홈 Hero 영역 — Copy / Object 두 개의 독립 컴포넌트로 구성합니다.

Analysis Form은 session_state·페이지 전환 로직과 얽혀 있어 pages/1_home.py에 그대로 두지만,
Hero Copy와 Hero Object는 그 로직과 무관하므로 이 모듈로 분리했습니다. hero_object.png를
다른 이미지로 교체하려면 이 파일의 HERO_OBJECT_PATH만 바꾸면 되고, Hero 레이아웃(pages/1_home.py)은
건드릴 필요가 없습니다.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

HERO_OBJECT_PATH = Path(__file__).resolve().parent / "assets" / "hero_object.png"


def render_hero_copy():
    """Hero 왼쪽의 eyebrow + headline + 보조 설명."""
    st.markdown(
        "<span class='adetect-eyebrow'>ADetect · Brand Intelligence</span>"
        "<p class='adetect-hero-title'>Detect AD<br>in minutes.</p>"
        "<p class='adetect-hero-sub'>브랜드명만 입력하면 시장부터 소재까지, "
        "AI가 분석해 경쟁사 인사이트와 실행 가능한 전략을 제안합니다.</p>",
        unsafe_allow_html=True,
    )


def render_hero_object(image_path: Path | None = None):
    """Hero 오른쪽의 3D visual anchor. 이미지가 없으면 조용히 아무것도 렌더링하지 않습니다."""
    path = image_path or HERO_OBJECT_PATH
    if not path.exists():
        return
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    st.markdown(
        f'<div class="adetect-hero-object"><img src="data:image/png;base64,{encoded}" alt="" /></div>',
        unsafe_allow_html=True,
    )
