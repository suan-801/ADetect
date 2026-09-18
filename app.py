"""ADetect — Streamlit 진입점. `streamlit run app.py`로 실행합니다.

전체 구조는 PRD §3(디렉터리)·§15(기술스택)·§16(화면 구성)을 따릅니다.
이 파일은 페이지 라우팅과 전역 스타일 주입만 담당하고, 실제 화면 로직은 pages/*.py에 있습니다.
아이콘은 이모지 대신 Streamlit 내장 Material Symbols(선 아이콘, `:material/...:`)만 사용합니다.

Navigation은 sidebar가 아니라 공식 `st.navigation(position="top")` API로 구현합니다
(Framework Audit 결론 — Streamlit 1.42+ 공식 기능, DOM hack 불필요, docs/PROJECT_PLAN.md 참고).
"""
from pathlib import Path

import streamlit as st

from config.settings import APP_NAME
from config.theme import inject_global_css
from database.db import init_db

st.set_page_config(
    page_title=APP_NAME,
    page_icon=":material/lens:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_global_css()
init_db()

_LOGO_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "logo.svg"
if _LOGO_PATH.exists():
    st.logo(str(_LOGO_PATH), size="medium")

home = st.Page("pages/1_home.py", title="Home", icon=None, default=True)
analyze = st.Page("pages/2_analyze.py", title="Analyze", icon=None)
history = st.Page("pages/3_history.py", title="History", icon=None)
settings_page = st.Page("pages/4_settings.py", title="Settings", icon=None)

nav = st.navigation([home, analyze, history, settings_page], position="top")
nav.run()
