"""설정 — API 키 연동 상태 확인 (PRD에는 상세 스펙 없음 → 최소 골격만 제공)."""
from __future__ import annotations

import streamlit as st

from config import settings

st.markdown(
    "<span class='adetect-eyebrow'>Settings</span>"
    "<p class='adetect-hero-title' style='font-size:1.7rem;'>설정</p>",
    unsafe_allow_html=True,
)
st.caption(".env 파일에 키를 채워 넣으면 자동으로 실제 연동 모드로 전환됩니다 (config/settings.py).")
st.write("")

st.markdown("<span class='adetect-eyebrow'>API 연동 상태</span>", unsafe_allow_html=True)

keys = [
    ("네이버 오픈API (DataLab/뉴스)", settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET),
    ("네이버 검색광고(키워드도구)", settings.NAVER_AD_API_KEY),
    ("Apify (Meta Ads/Instagram)", settings.APIFY_API_TOKEN),
    ("Google Gemini", settings.GEMINI_API_KEY),
]
for label, ok in keys:
    state = "연동됨" if ok else "미연동"
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;padding:0.6rem 0;"
        f"border-top:1px solid rgba(255,255,255,0.07);'>"
        f"<span>{label}</span><span style='color:#9A9A9E;'>{state}</span></div>",
        unsafe_allow_html=True,
    )

st.write("")
st.markdown("<span class='adetect-eyebrow'>현재 모드</span>", unsafe_allow_html=True)
if settings.USE_MOCK_DATA:
    st.caption("목업(mock) 데이터 모드 — 위 키를 모두 채우면 실제 연동 모드로 전환됩니다.")
else:
    st.caption("실제 연동 모드")
