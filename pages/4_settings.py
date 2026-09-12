"""설정 — API 키 연동 상태 확인 (ref.png 사이드바 구성 반영, PRD에는 상세 스펙 없음 → 최소 골격만 제공)."""
from __future__ import annotations

import streamlit as st

from config import settings

st.title("설정")

st.markdown("#### API 연동 상태")
st.caption(".env 파일에 키를 채워 넣으면 자동으로 실제 연동 모드로 전환됩니다 (config/settings.py).")

keys = [
    ("네이버 오픈API (DataLab/뉴스)", settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET),
    ("네이버 검색광고(키워드도구)", settings.NAVER_AD_API_KEY),
    ("Apify (Meta Ads/Instagram)", settings.APIFY_API_TOKEN),
    ("Google Gemini", settings.GEMINI_API_KEY),
]
for label, ok in keys:
    st.write(f"{'✅' if ok else '❌'} {label}")

st.divider()
st.markdown("#### 현재 모드")
if settings.USE_MOCK_DATA:
    st.warning("목업(mock) 데이터 모드 — 위 키를 모두 채우면 실제 연동 모드로 전환됩니다.")
else:
    st.success("실제 연동 모드")
