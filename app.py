"""ADetect — Streamlit 진입점. `streamlit run app.py`로 실행합니다.

전체 구조는 PRD §3(디렉터리)·§15(기술스택)·§16(화면 구성)을 따릅니다.
이 파일은 페이지 라우팅과 전역 스타일 주입만 담당하고, 실제 화면 로직은 pages/*.py에 있습니다.
"""
import streamlit as st

from config.settings import APP_NAME
from config.theme import inject_global_css
from database.db import init_db

st.set_page_config(
    page_title=APP_NAME,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()
init_db()

home = st.Page("pages/1_home.py", title="홈", icon="🏠", default=True)
analyze = st.Page("pages/2_analyze.py", title="분석하기", icon="🔍")
history = st.Page("pages/3_history.py", title="이력 관리", icon="🕒")
settings_page = st.Page("pages/4_settings.py", title="설정", icon="⚙️")

st.sidebar.markdown("### ADetect")
st.sidebar.caption("Brand Intelligence Engine")

nav = st.navigation([home, analyze, history, settings_page])
nav.run()
