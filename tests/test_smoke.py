"""전체 클릭 흐름 스모크 테스트 (STEP1 입력 → 확인 → Workspace → 시장/브랜드/소재/종합).

Target은 더 이상 독립 탭이 아니라 종합분석 탭 안의 Target Insight subsection이다(PRD §12·§15).
이 테스트는 다음을 함께 확인한다:
- standalone target tab이 Workspace에 없고, 1차 탭이 4개(시장/브랜드/소재/종합)인지
- 소재분석 결과에 랜덤 Appeal Point(appeal_tags/appeal_distribution)가 노출되지 않는지
- Target Insight가 시장+브랜드 결과가 있을 때만 생성되고, 근거 없는 인구통계를 만들지 않는지

실행: `pytest tests/test_smoke.py -v`
"""
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def explicit_sample(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings,"SAMPLE_MODE",True)

from streamlit.testing.v1 import AppTest

from core.analyzers.insight_synthesizer import build_target_insight

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "pages"


def _enter_workspace(at: AppTest, brand_name: str) -> AppTest:
    at.text_input(key="input_brand_name").set_value(brand_name)
    at.run()
    at.button(key="btn_step1_next").click().run()
    assert not at.exception
    assert at.session_state["step"] == "confirm"

    at.button(key="btn_confirm_go").click().run()
    assert not at.exception
    assert at.session_state["step"] == "workspace"
    return at


def test_home_page_loads():
    at = AppTest.from_file(str(PAGES / "1_home.py")).run()
    assert not at.exception


def test_workspace_has_4_primary_tabs_no_standalone_target():
    at = AppTest.from_file(str(PAGES / "2_analyze.py"), default_timeout=15).run()
    _enter_workspace(at, "나이키")

    tab_labels = [t.label for t in at.tabs]
    assert tab_labels == ["01 검색·뉴스", "02 공식 페이지·SNS", "03 광고 소재", "04 확인·정리"]
    assert not any("타겟" in label for label in tab_labels)

    # Analysis Status Index — 항상 4개 항목(§17), 5번째(구 타겟) 행이 남아있지 않은지 확인.
    status_html = "\n".join(m.value for m in at.markdown)
    assert status_html.count("adetect-status-row") == 4


def test_full_flow_market_brand_creative_synthesis():
    at = AppTest.from_file(str(PAGES / "2_analyze.py"), default_timeout=15).run()
    _enter_workspace(at, "메리츠화재")

    _run_analysis(at, "market")
    assert not at.exception
    assert at.session_state["session"]["market_status"] == "완료"

    _run_analysis(at, "brand")
    assert not at.exception
    assert at.session_state["session"]["brand_status"] == "완료"

    _run_analysis(at, "creative")
    assert not at.exception
    creative_result = at.session_state["session"]["creative_result"]
    assert at.session_state["session"]["creative_status"] == "완료"
    assert creative_result["schema_version"] == 2
    assert creative_result["records"]
    assert all("appeal_tags" not in ad for ad in creative_result["records"])
    assert not at.exception


def test_target_insight_insufficient_when_no_data():
    result = build_target_insight(None, None)
    assert result["status"] == "insufficient_data"


def test_target_insight_insufficient_when_only_market_done():
    market_result = {
        "trend": [{"date": "2026-01-01", "search_index": 100}, {"date": "2026-01-31", "search_index": 120}],
        "news": [],
        "category": "손해보험",
    }
    result = build_target_insight(market_result, None)
    assert result["status"] == "insufficient_data"


def test_target_insight_no_random_demographic_when_data_available():
    market_result = {
        "trend": [{"date": "2026-01-01", "search_index": 100}, {"date": "2026-01-31", "search_index": 120}],
        "news": [],
        "category": "손해보험",
    }
    brand_result = {"own": {"brand": "메리츠화재"}, "competitors": [{"brand": "삼성화재"}]}
    result = build_target_insight(market_result, brand_result)

    assert result.get("status") != "insufficient_data"
    assert "insight" in result and "evidence" in result and "confidence" in result
    # 근거 없는 연령/성별 세그먼트를 지어내지 않는다 (구 recommend_target()의 random mock 재현 금지).
    for forbidden in ("20대", "30대", "40대", "50대", "여성", "남성"):
        assert forbidden not in result["insight"]


def test_history_and_settings_pages_load():
    at = AppTest.from_file(str(PAGES / "3_history.py")).run()
    assert not at.exception

    at = AppTest.from_file(str(PAGES / "4_settings.py")).run()
    assert not at.exception


def _run_analysis(at, function):
    from core.jobs import get_job
    at.button(key="btn_start_"+function).click().run()
    jid = at.session_state["session"].get(function+"_job")
    if jid:
        get_job(jid)["future"].result(timeout=20)
        at.run()
    assert not at.exception


def test_synthesis_and_downloads_restore():
    from core.runtime import restore_results
    at = AppTest.from_file(str(PAGES / "2_analyze.py"), default_timeout=15).run()
    _enter_workspace(at, "검증브랜드")
    _run_analysis(at, "market")
    _run_analysis(at, "brand")
    choices = at.session_state["session"]["market_result"]["records"]
    at.multiselect(key="summary_selection").set_value([choices[0]["id"]]).run()
    _run_analysis(at, "synthesis")
    for function in ("market", "brand", "synthesis"):
        at.button(key=f"gen_html_{function}").click().run()
        at.button(key=f"gen_xlsx_{function}").click().run()
        assert not at.exception
        result = at.session_state["session"]
        assert result[f"{function}_export_html"].startswith("<!doctype")
        assert result[f"{function}_export_xlsx"][:2] == b"PK"
    saved = dict(at.session_state["session"])
    restored = restore_results({"id":saved["id"],"reviews":saved.get("reviews",{}),"selected_records":saved.get("selected_records",[])})
    assert restored["market_result"] == saved["market_result"]
    assert restored["synthesis_status"] == "완료"
