"""전체 클릭 흐름 스모크 테스트 (STEP1 입력 → 확인 → Workspace → 시장/브랜드 분석 → 타겟 추천/확정/분석).

각자 담당 파트를 mock에서 실제 구현으로 바꿀 때, 이 테스트가 계속 통과하는지로
"화면이 안 깨졌는지"를 빠르게 확인할 수 있습니다.

실행: `pytest tests/test_smoke.py -v`
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "pages"


def test_home_page_loads():
    at = AppTest.from_file(str(PAGES / "1_home.py")).run()
    assert not at.exception


def test_full_flow_up_to_target_analysis():
    at = AppTest.from_file(str(PAGES / "2_analyze.py")).run()
    assert not at.exception

    at.text_input(key="input_brand_name").set_value("메리츠화재")
    at.run()
    at.button(key="btn_step1_next").click().run()
    assert not at.exception
    assert at.session_state["step"] == "confirm"

    at.button(key="btn_confirm_go").click().run()
    assert not at.exception
    assert at.session_state["step"] == "workspace"

    at.button(key="btn_start_market").click().run()
    assert not at.exception
    assert at.session_state["session"]["market_status"] == "완료"

    at.button(key="btn_start_brand").click().run()
    assert not at.exception
    assert at.session_state["session"]["brand_status"] == "완료"

    at.button(key="btn_start_creative").click().run()
    assert not at.exception
    assert at.session_state["session"]["creative_status"] == "완료"
    assert at.session_state["session"]["creative_result"]["own"]["ad_count"] >= 0

    # 게이트 통과 직후 자동 추천되어 있어야 함 (PRD §7-2·§9-2)
    assert at.session_state["session"]["target_status"] == "recommended"

    at.button(key="btn_confirm_target").click().run()
    assert not at.exception
    assert at.session_state["session"]["target_status"] == "confirmed"

    at.button(key="btn_start_target_analysis").click().run()
    assert not at.exception
    assert at.session_state["session"]["target_result"] is not None


def test_history_and_settings_pages_load():
    at = AppTest.from_file(str(PAGES / "3_history.py")).run()
    assert not at.exception

    at = AppTest.from_file(str(PAGES / "4_settings.py")).run()
    assert not at.exception
