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
    for label in ("초안 준비하고 다음", "자사 정보 확인하고 다음", "선택한 경쟁사 확인 / 건너뛰기"):
        next(b for b in at.button if b.label == label).click().run()
        assert not at.exception
    next(c for c in at.checkbox if c.label == "브랜드·검색어·주소 후보를 확인했습니다").check()
    next(b for b in at.button if b.label == "확인하고 프로젝트 만들기").click().run()
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
    assert not AppTest.from_file(str(ROOT / "app_pages/1_home.py")).run().exception


def test_project_flow_has_collection_review_history_tabs():
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    assert [tab.label for tab in at.tabs] == ["자료 수집", "자료 확인·다운로드", "이력"]
    assert not at.exception


def test_project_collection_selection_is_explicit():
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
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
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    at.button(key="edit_project_button").click().run()
    at.text_input(key="project_campaign").set_value("리하우스").run()
    at.button(key="save_project").click().run()
    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["자료 수집", "자료 확인·다운로드", "이력"]


def test_selected_records_produce_downloadable_files():
    """생성 버튼 key가 rerun마다 바뀌면 클릭이 유실된다 — 실제 파일 생성까지 확인한다."""
    from core import projects
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=60).run()
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
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    usage = [c.value for c in at.caption if c.value.startswith("저장 공간 · 파일")]
    assert usage and "DB" in usage[0] and "전체 한도" in usage[0] and "사용률" in usage[0]


def test_storage_warning_levels_link_to_cleanup(monkeypatch):
    from core import retention
    monkeypatch.setattr(retention, "usage", lambda: {"files": 95, "db": 1, "limits": {"files": 100, "db": 100}})
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    assert any("사용률 95%" in e.value for e in at.error)
    assert any(b.label == "저장 공간 정리로 이동" for b in at.button)
    monkeypatch.setattr(retention, "usage", lambda: {"files": 82, "db": 1, "limits": {"files": 100, "db": 100}})
    at.run()
    assert any("80%" in w.value for w in at.warning) and not any("사용률" in e.value for e in at.error)


def test_result_tab_uses_latest_version_and_previous_versions_on_demand():
    from core import projects
    from database.db import get_conn
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=60).run()
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
    assert any(e.label.startswith("이전에 수집한 자료 보기") for e in at.expander)
    box = at.selectbox(key="version_" + pid + "trend")
    assert box.value == latest_trend
    assert all(len(o) < 60 and old_trend not in o for o in box.options), "내부 실행 ID를 노출하지 않음"
    box.set_value(old_trend).run()
    assert not at.exception
    assert any("이전 자료 표시 중" in e.label for e in at.expander)
    assert any("수집일이 다른 자료" in c.value for c in at.caption)


def test_history_tab_shows_three_availability_states():
    import json
    from core import projects
    from database.db import get_conn
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=60).run()
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
    at = AppTest.from_file(str(ROOT / "app_pages/4_settings.py"), default_timeout=15).run()
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


def test_config_saves_brands_competitors_market_and_news_settings():
    from core import projects
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    at.button(key="edit_project_button").click().run()
    prefix = "cfg_" + at.session_state["project_id"]
    cfg = prefix + "_b_own_"
    assert at.text_input(key=cfg + "terms").placeholder.startswith("예)")
    assert any("시장 조사를 원하는 검색어를 입력해주세요" in c.value for c in at.caption)
    assert not any("KOSIS" in (m.value or "") for m in at.markdown), "외부 통계 안내는 설정에서 제거"
    assert not any(t.label == "일반 검색어" for t in at.text_input)
    at.text_input(key=cfg + "terms").set_value("한샘, 한셈, 한샘").run()
    at.text_area(key=cfg + "official").set_value("https://a.example\nhttps://smartstore.naver.com/a").run()
    at.button(key="add_competitor").click().run()
    comp = next(b for b in at.session_state["cfg_brands"] if b["role"] == "competitor")["id"]
    at.text_input(key=f"{prefix}_b_{comp}_name").set_value("리바트").run()
    at.text_input(key=f"{prefix}_b_{comp}_terms").set_value("리바트, 한셈").run()
    assert any("함께 들어 있습니다" in w.value for w in at.warning), "브랜드 간 같은 검색어 경고"
    at.text_input(key=f"{prefix}_b_{comp}_terms").set_value("리바트, 현대리바트").run()
    at.text_input(key="project_market").set_value("인테리어, 리모델링").run()
    at.session_state["project_news"] = ""
    at.run()
    at.button(key="import_market_news").click().run()
    assert at.text_input(key="project_news").value == "인테리어, 리모델링", "후보는 버튼을 눌러야 반영"
    at.text_input(key="news_exclude").set_value("채용").run()
    at.button(key="save_project").click().run()
    assert not at.exception
    p = projects.project_inputs(projects.load(at.session_state["project_id"]))
    assert [(b["name"], b["role"], b["terms"]) for b in p["brands"]] == [("한샘", "own", ["한샘", "한셈"]), ("리바트", "competitor", ["리바트", "현대리바트"])]
    assert p["brands"][0]["sources"]["official_urls"] == ["https://a.example", "https://smartstore.naver.com/a"]
    assert p["market_keywords"] == ["인테리어", "리모델링"] and p["news_keywords"] == ["인테리어", "리모델링"]
    assert p["news_filter"] == {"include": [], "exclude": ["채용"]} and p["competitors"] == ["리바트"]


def test_website_collects_each_official_url():
    from core import projects
    from core.project_sources import collect
    p = projects.project_inputs({"brand_name": "A", "sources": {"A": {"official_urls": ["https://a.example", "https://b.example"], "detail_url": "https://a.example/event"}}})
    result = collect("website", p, {})
    assert len([k for k in result["parts"] if k.startswith("site:")]) == 3


def test_paid_toggle_off_locks_paid_sources_and_select_buttons_do_not_collect():
    from core import projects, project_jobs
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at)
    pid = at.session_state["project_id"]
    stored = projects.load(pid)
    stored["sources"] = {"한샘": {"instagram": "@hanssem", "meta_page": "https://www.facebook.com/ads/library/?view_all_page_id=1"}}
    stored.pop("brands", None)
    projects.update(pid, stored["name"], projects.to_storage(projects.project_inputs(stored)))
    at.run()
    assert not at.checkbox(key="select_" + pid + "meta").disabled
    at.button(key="select_all_sources").click().run()
    assert at.checkbox(key="select_" + pid + "instagram").value is True
    assert project_jobs.tasks(pid) == [], "전체 선택은 수집을 시작하지 않음"
    at.button(key="clear_sources").click().run()
    assert not any(c.value for c in at.checkbox if c.key and c.key.startswith("select_"))
    at.toggle(key="collection_paid").set_value(False).run()
    at.button(key="select_all_sources").click().run()
    assert at.checkbox(key="select_" + pid + "meta").disabled and at.checkbox(key="select_" + pid + "meta").value is False
    assert at.checkbox(key="select_" + pid + "instagram").value is False, "유료 OFF면 전체 선택해도 유료 호출 비활성"
    assert not at.checkbox(key="select_" + pid + "trend").disabled
    assert project_jobs.tasks(pid) == []


def test_project_list_checkbox_delete_with_confirmation():
    from core import projects
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=15).run()
    enter_project(at, "삭제대상")
    pid = at.session_state["project_id"]
    at.button(key="to_project_list").click().run()
    assert not any(b.key == "delete_picked" for b in at.button), "선택 전에는 삭제 버튼이 없다"
    at.checkbox(key="pick_" + pid).check().run()
    at.button(key="delete_picked").click().run()
    assert at.button(key="delete_confirm").disabled, "백업 확인 전에는 삭제 불가"
    at.checkbox(key="delete_backup_ok").check().run()
    at.button(key="delete_confirm").click().run()
    assert not at.exception
    assert all(r["id"] != pid for r in projects.overview())


def test_result_tab_has_comparison_trend_and_no_review_classification():
    at = AppTest.from_file(str(ROOT / "app_pages/2_analyze.py"), default_timeout=60).run()
    enter_project(at, "메리츠화재")
    pid = at.session_state["project_id"]
    collect(at, pid, ("trend", "volume", "news", "search_capture"))
    assert not at.exception
    sections = [m.value for m in at.markdown if "adetect-section" in (m.value or "")]
    order = ["브랜드 비교 요약", "검색 추이", "뉴스 핵심 내용·수치 요약", "뉴스 주제별 요약", "검색 화면과 광고 관측", "UTM 구조", "추가 정보를 찾아보세요", "다운로드"]
    assert [next(i for i, v in enumerate(sections) if name in v) for name in order] == sorted(range(len(order)))
    assert not any(m.label in ("포함", "확인 필요", "제외") for m in at.metric)
    assert not any("확인 상태" in str(d.value.columns.tolist()) for d in at.dataframe)
    assert not any("관측 화면에서 광고 문구·광고주·랜딩을 직접 확인하세요" in str(d.value) for d in at.dataframe)
    comparison = next(d for d in at.dataframe if "월간 검색량 합계" in d.value.columns)
    assert comparison.value["월간 검색량 합계"].iloc[0] not in ("0", "미수집")
    assert any("SAMPLE" in w.value for w in at.warning)


def test_settings_is_concise_and_backup_opens_done_dialog(tmp_path, monkeypatch):
    monkeypatch.setenv("ADETECT_BACKUP_DIR", str(tmp_path / "backups"))
    from core import projects
    projects.create("백업", {"brand_name": "A"})
    at = AppTest.from_file(str(ROOT / "app_pages/4_settings.py"), default_timeout=15).run()
    assert not any("이 PC의 자료 보관" in (h.value or "") for h in at.subheader)
    at.button(key="make_db_backup").click().run()
    assert not at.exception
    assert any(b.label == "바로 확인하기" for b in at.button)
    assert list((tmp_path / "backups").glob("adetect_*.db"))
