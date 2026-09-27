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


def test_project_screen_shows_storage_usage():
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    usage = [c.value for c in at.caption if c.value.startswith("저장 공간 · 파일")]
    assert usage and "DB" in usage[0] and "전체 한도" in usage[0] and "사용률" in usage[0]


def test_storage_warning_levels_link_to_cleanup(monkeypatch):
    from core import retention
    monkeypatch.setattr(retention, "usage", lambda: {"files": 95, "db": 1, "limits": {"files": 100, "db": 100}})
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    assert any("사용률 95%" in e.value for e in at.error)
    assert any(b.label == "저장 공간 정리로 이동" for b in at.button)
    monkeypatch.setattr(retention, "usage", lambda: {"files": 82, "db": 1, "limits": {"files": 100, "db": 100}})
    at.run()
    assert any("80%" in w.value for w in at.warning) and not any("사용률" in e.value for e in at.error)


def test_result_tab_uses_latest_version_and_other_time_on_demand():
    from core import projects
    from database.db import get_conn
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=60).run()
    enter_project(at, "메리츠화재")
    pid = at.session_state["project_id"]
    collect(at, pid, ("trend", "news"))
    old_trend = next(h for h in projects.histories(pid) if h["source"] == "trend")["run_id"]
    with get_conn() as conn:
        conn.execute("UPDATE function_run SET created_at='2026-01-02T00:00:00+00:00' WHERE id=?", (old_trend,))
    at.session_state["force_collection"] = True
    collect(at, pid, ("trend",))
    latest_trend = next(h for h in projects.histories(pid) if h["source"] == "trend")["run_id"]
    assert latest_trend != old_trend
    assert any(e.label == "다른 시점 선택" for e in at.expander)
    # 기본은 최근 성공 버전이며 다른 시점 표시·날짜 혼합 경고가 없다.
    summary = next(c.value for c in at.caption if "검색 관심도 추이" in c.value and "건" in c.value)
    assert "(다른 시점)" not in summary
    assert at.selectbox(key="version_" + pid + "trend").value == latest_trend
    at.selectbox(key="version_" + pid + "trend").set_value(old_trend).run()
    assert not at.exception
    assert any("(다른 시점)" in c.value for c in at.caption)
    assert any("날짜 혼합" in w.value for w in at.warning)


def test_history_tab_shows_three_availability_states():
    import json
    from core import projects
    from database.db import get_conn
    at = AppTest.from_file(str(ROOT / "pages/2_analyze.py"), default_timeout=60).run()
    enter_project(at, "한샘")
    pid = at.session_state["project_id"]
    collect(at, pid, ("trend", "news"))
    news = next(h for h in projects.histories(pid) if h["source"] == "news")
    with get_conn() as conn:
        conn.execute("UPDATE function_run SET result_json=? WHERE id=?", (json.dumps({"schema_version": 3, "source": "news", "status": "완료", "expired": True, "records": [], "parts": {}}), news["run_id"]))
    at.run()
    table = next(d for d in at.dataframe if "보유 상태" in d.value.columns)
    states = set(table.value["보유 상태"])
    assert states <= {"결과·원본 모두 있음", "결과만 있음 (일부 원본 없음)", "이력만 있음"}
    assert "이력만 있음" in states and "결과·원본 모두 있음" in states
    assert "결과 있음" not in states
    at.selectbox(key="history_choice_" + pid).set_value(news["run_id"]).run()
    assert any("백업에서 새 프로젝트 복원" in w.value and "새로 수집" in w.value for w in at.warning)


def test_settings_cleanup_requires_preview_and_confirmation():
    import os
    from core.evidence_store import save_bytes, root
    asset = save_bytes(b"orphan evidence", "png", "https://example.com/orphan")
    path = root() / asset["filename"]
    old = time.time() - 90 * 86400
    os.utime(path, (old, old))
    from database.db import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE stored_blob SET created=?", (old,))
    at = AppTest.from_file(str(ROOT / "pages/4_settings.py"), default_timeout=15).run()
    assert not at.exception
    assert any(c.value.startswith("저장 공간 · 파일") for c in at.caption)
    assert not any(b.label == "정리 실행" for b in at.button), "후보 보기 전에는 실행 버튼이 없다"
    at.button(key="cleanup_preview").click().run()
    candidates = next(d for d in at.dataframe if "예상 용량" in d.value.columns)
    assert asset["filename"] in set(candidates.value["파일명"])
    assert at.button(key="cleanup_apply").disabled
    assert path.exists()
    at.checkbox(key="cleanup_agree").check().run()
    at.button(key="cleanup_apply").click().run()
    assert not at.exception
    assert not path.exists()
    assert any("정리 완료" in s.value for s in at.success)
