"""설정 — API 키 연동 상태, 저장 공간 관리(정리 후보·정리 실행), DB 백업, 프로젝트 단위 정리.

Utility page이므로 과도한 visual storytelling 없이 semantic status indicator 중심으로 구성합니다.
"""
from __future__ import annotations

import html

import streamlit as st

from config import settings
from ui.components import section_header_block, status_badge
from ui.storage_panel import backup_panel, cleanup_panel, project_cleanup_panel

section_header_block("Settings", "설정")
st.caption("키는 .env에서 설정합니다. 유료 기능은 기본 ON이며 수집·요약 버튼을 눌렀을 때 호출합니다. 키 값은 화면이나 산출물에 표시하지 않습니다.")
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
    st.caption("명시적 SAMPLE 모드입니다. 실제 수집과 유료 API 호출을 하지 않습니다.")
else:
    st.caption("실제 수집 모드입니다. 누락된 키를 SAMPLE로 대체하지 않습니다. 키 존재 여부만 확인했으며 잔액·권한·수집 성공은 실행 결과에서 확인하세요.")
    if not settings.APIFY_API_TOKEN or not settings.GEMINI_API_KEY:
        st.warning("토큰 부족. 개발자에게 문의해주세요")

st.subheader("이 PC의 자료 보관")
from core.evidence_store import root as _evidence_root
from core.exporters.artifact_store import root as _export_root
st.write(f"입력·수집 결과·다운로드 요청: {settings.DB_PATH} · 산출물: {_export_root()} · 원본: {_evidence_root()} (환경변수로 변경 가능)")
st.caption("산출물은 최근 20개 실행·총 5GB 기준으로 오래된 파일부터 만료합니다. 원본은 기본 5GB까지 저장하고 초과하면 새 저장을 중단합니다. DB 이력은 자동 삭제하지 않습니다. 백업할 때 DB와 두 폴더를 함께 복사하세요.")

st.write("")
cleanup_panel()
st.write("")
backup_panel()
st.write("")
project_cleanup_panel()
