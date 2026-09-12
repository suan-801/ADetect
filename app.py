"""ADetect — Streamlit 진입점. `streamlit run app.py`로 실행합니다.

전체 구조는 PRD §3(디렉터리)·§15(기술스택)·§16(화면 구성)을 따릅니다.
이 파일은 페이지 라우팅과 전역 스타일 주입만 담당하고, 실제 화면 로직은 pages/*.py에 있습니다.
아이콘은 이모지 대신 Streamlit 내장 Material Symbols(선 아이콘, `:material/...:`)만 사용합니다.
"""
import streamlit as st

from config.settings import APP_NAME
from config.theme import inject_global_css
from database.db import init_db

st.set_page_config(
    page_title=APP_NAME,
    page_icon=":material/lens:",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()
init_db()

home = st.Page("pages/1_home.py", title="홈", icon=":material/home:", default=True)
analyze = st.Page("pages/2_analyze.py", title="분석하기", icon=":material/search:")
history = st.Page("pages/3_history.py", title="이력 관리", icon=":material/history:")
settings_page = st.Page("pages/4_settings.py", title="설정", icon=":material/tune:")

st.sidebar.markdown(
    "<div style='font-weight:500;font-size:1rem;letter-spacing:0.02em;'>ADetect</div>"
    "<div style='color:#5C5C60;font-size:0.75rem;margin-top:2px;margin-bottom:1.2rem;'>"
    "Brand Intelligence Engine</div>",
    unsafe_allow_html=True,
)

nav = st.navigation([home, analyze, history, settings_page])
nav.run()
