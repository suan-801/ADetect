"""설정 — API 키 연동 상태 확인 (PRD에는 상세 스펙 없음 → 최소 골격만 제공).

Utility page이므로 과도한 visual storytelling 없이 semantic status indicator 중심으로 구성합니다.
"""
from __future__ import annotations

import html

import streamlit as st

from config import settings
from ui.components import section_header_block, status_badge

section_header_block("Settings", "설정")
st.caption(".env 파일에 키를 채워 넣으면 자동으로 실제 연동 모드로 전환됩니다 (config/settings.py).")
st.write("")

st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>API 연동 상태</span>", unsafe_allow_html=True)

keys = [
    ("네이버 오픈API (DataLab/뉴스)", bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)),
    ("네이버 검색광고 (키워드도구)", bool(settings.NAVER_AD_API_KEY)),
    ("Apify (Meta Ads/Instagram)", bool(settings.APIFY_API_TOKEN)),
    ("Google Gemini", bool(settings.GEMINI_API_KEY)),
]
for label, ok in keys:
    dot = status_badge("완료" if ok else "미실행", label="연동됨" if ok else "미연동")
    st.markdown(
        f'<div class="adetect-kv-row"><span class="label">{html.escape(label)}</span>{dot}</div>',
        unsafe_allow_html=True,
    )

st.write("")
st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>현재 모드</span>", unsafe_allow_html=True)
if settings.USE_MOCK_DATA:
    st.caption("일부 서비스가 목업(mock) 데이터 모드입니다 — 위 키를 모두 채우면 전체 실제 연동 모드로 전환됩니다.")
else:
    st.caption("전체 실제 연동 모드입니다.")
