"""프로젝트형 팩트 수집 MVP의 화면 smoke tests."""
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def sample_mode(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "SAMPLE_MODE", True)


def enter_project(at, brand="한샘"):
    at.text_input(key="new_brand").set_value(brand).run()
    at.button(key="new_project").click().run()
    assert at.session_state["step"] == "config"
    at.button(key="save_project").click().run()
    assert at.session_state["step"] == "workspace"
    assert not at.exception


def collect(at, pid, sources=("trend", "volume", "news")):
    from core import project_jobs
    for source in projects_sources():
        at.session_state["select_" + pid + source] = source in sources
    at.run()
    at.button(key="start_project_collection").click().run()
    deadline = time.time() + 60
    while time.time() < deadline:
        if not any(task["state"] in ("대기", "수집 중") for task in project_jobs.tasks(pid)):
            break
        time.sleep(0.2)
    at.run()
    assert not at.exception


def projects_sources():
    from core import projects
    return list(projects.SOURCES)


def test_home_page_loads():
    assert not AppTest.from_file(str(ROOT / "pages/1_home.py")).run().exception


def test_project_flow_has_collection_review_history_tabs():
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    assert [tab.label for tab in at.tabs] == ["자료 수집", "자료 확인·다운로드", "이력"]
    assert not at.exception


def test_project_collection_selection_is_explicit():
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at, "메리츠화재")
    assert any(x.key.endswith("trend") for x in at.checkbox)
    assert any("유료 기능" in x.label for x in at.toggle)
    assert not any("타겟" in (x.label or "") for x in at.tabs)


def test_project_repository_keeps_input_snapshot_and_deduplicates_news(tmp_path, monkeypatch):
    import database.db as db
    from core import projects
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "project.db"))
    inputs = {"brand_name": "한샘", "campaign": "리하우스", "category": "인테리어", "competitors": [],
              "brand_keywords": ["한샘"], "general_keywords": ["인테리어"], "sources": {},
              "paid_enabled": True, "save_images": True, "save_ad_assets": True}
    pid = projects.create("한샘 조사", inputs)
    loaded = projects.load(pid)
    assert loaded["brand_keywords"] == ["한샘"]
    result = {"records": [{"id": "a", "kind": "뉴스", "brand": "한샘", "source_url": "https://news.example/a?utm_source=x", "text": "A", "keyword": "한샘"},
                          {"id": "b", "kind": "뉴스", "brand": "한샘", "source_url": "https://news.example/a", "text": "A", "keyword": "인테리어"}], "parts": {"news:한샘": {"state": "완료", "records": []}}}
    normalized = projects.normalize(result, "news", loaded)
    assert len(normalized["records"]) == 1
    assert set(normalized["records"][0]["matched_queries"]) == {"한샘", "인테리어"}


def test_project_settings_save_returns_to_workspace():
    """설정 저장 후에도 설정 화면에 갇히지 않는다 (edit_project 플래그 해제)."""
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    at.button(key="edit_project_button").click().run()
    at.text_input(key="project_campaign").set_value("리하우스").run()
    at.button(key="save_project").click().run()
    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["자료 수집", "자료 확인·다운로드", "이력"]


def test_selected_records_produce_downloadable_files():
    """생성 버튼 key가 rerun마다 바뀌면 클릭이 유실된다 — 실제 파일 생성까지 확인한다."""
    from core import projects
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=60).run()
    enter_project(at, "메리츠화재")
    pid = at.session_state["project_id"]
    collect(at, pid)
    snapshots = [h for h in projects.histories(pid) if projects.available(h)]
    assert snapshots
    at.session_state["download_selection"] = [r["selection_id"] for h in snapshots for r in projects.review_rows(h)]
    at.run()
    for label, prefix in (("HTML 생성", b"<!do"), ("XLSX 생성", b"PK"), ("ZIP 생성", b"PK")):
        button = next(b for b in at.button if b.label == label)
        button.click().run()
        assert not at.exception and not at.error
        saved = at.session_state["last_artifact_" + label.split()[0].lower()]
        assert at.session_state["artifact_" + saved[1]].startswith(prefix)
    assert len(at.get("download_button")) == 3
