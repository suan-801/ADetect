"""설정 — API 키 연동 상태, 저장 공간 관리(정리 후보·정리 실행), DB 백업, 프로젝트 단위 정리.

Utility page이므로 과도한 visual storytelling 없이 semantic status indicator 중심으로 구성합니다.
"""
from __future__ import annotations

import html

import streamlit as st

from config import settings
from ui.components import section_header_block, status_badge
from ui.storage_panel import backup_panel, cleanup_panel

section_header_block("Settings", "설정")
st.caption("API 키는 .env에서 설정합니다.")
st.write("")

st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>API 연동 상태</span>", unsafe_allow_html=True)

keys = [
    ("NAVER API HUB (검색 추이/뉴스)", bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)),
    ("네이버 검색광고 (키워드도구)", bool(settings.NAVER_AD_API_KEY and settings.NAVER_AD_SECRET_KEY and settings.NAVER_AD_CUSTOMER_ID)),
    ("Apify (Meta Ads/Instagram)", bool(settings.APIFY_API_TOKEN)),
    ("Google Gemini", bool(settings.GEMINI_API_KEY)),
    ("YouTube Data API", bool(settings.YOUTUBE_API_KEY)),
]
for label, ok in keys:
    dot = status_badge("완료" if ok else "미실행", label="키 설정됨" if ok else "키 미설정")
    st.markdown(
        f'<div class="adetect-kv-row"><span class="label">{html.escape(label)}</span>{dot}</div>',
        unsafe_allow_html=True,
    )

st.write("")
st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>현재 모드</span>", unsafe_allow_html=True)
if settings.SAMPLE_MODE:
    st.warning("SAMPLE 모드 — 외부 API를 호출하지 않고 가상 자료를 씁니다. 실행 창에 ADETECT_SAMPLE_MODE=true가 남아 있으면 새 PowerShell 창에서 다시 실행하세요.")
else:
    st.caption("실제 수집 모드")
    if not settings.APIFY_API_TOKEN or not settings.GEMINI_API_KEY:
        st.warning("토큰 부족. 개발자에게 문의해주세요")

st.write("")
cleanup_panel()
st.write("")
backup_panel()
