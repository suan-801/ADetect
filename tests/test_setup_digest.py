import json
from pathlib import Path
from types import SimpleNamespace as NS
from streamlit.testing.v1 import AppTest
from core import projects, project_discovery, project_backup
from core.analyzers import news_digest
from config import settings


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception


def test_wizard_prefill_edit_back_and_confirm(monkeypatch):
    calls = []
    def suggest(*args):
        calls.append(args)
        return {"status": "후보 생성 완료", "message": "확인 필요", "suggestions": {"own": {"name": "한샘", "terms": ["한샘", "한셈"], "homepage_candidates": ["https://example.com"]},
                "competitors": [], "market_keywords": ["인테리어"], "news_keywords": ["한샘 가구"]}}
    monkeypatch.setattr(project_discovery, "suggest", suggest)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app_pages/2_analyze.py"), default_timeout=30).run()
    at.text_input(key="new_brand").set_value("한샘").run()
    at.button(key="new_project").click().run()
    click(at, "초안 준비하고 다음")
    key = "setup_" + at.session_state["setup_id"] + "_b_own_terms"
    assert at.text_input(key=key).value == "한샘, 한셈"
    at.text_input(key=key).set_value("한샘, 한샘리하우스")
    click(at, "이전")
    click(at, "초안 준비하고 다음")
    assert len(calls) == 1 and at.text_input(key=key).value == "한샘, 한샘리하우스"
    click(at, "자사 정보 확인하고 다음")
    click(at, "선택한 경쟁사 확인 / 건너뛰기")
    next(c for c in at.checkbox if c.label == "브랜드·검색어·주소 후보를 확인했습니다").check()
    click(at, "확인하고 프로젝트 만들기")
    saved = projects.load(at.session_state["project_id"])
    assert saved["brands"][0]["terms"] == ["한샘", "한샘리하우스"]
    assert saved["news_keywords"] == ["한샘 가구"] and saved["setup_provenance"]["confirmed_at"]
    assert projects.histories(saved["id"]) == []


def test_discovery_success_cache_and_failure_retry(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)
    calls = []
    def generate(*args):
        calls.append(args)
        return {"suggestions": None} if len(calls) == 1 else {"suggestions": {"own": {"name": "A"}}}
    monkeypatch.setattr(project_discovery, "_generate", generate)
    assert not project_discovery.suggest("A")["suggestions"]
    assert project_discovery.suggest("A")["suggestions"]
    assert project_discovery.suggest(" A ")["cache_hit"] and len(calls) == 2


def test_discovery_rejects_unsupported_urls():
    parsed = project_discovery.ProjectSuggestions(own=project_discovery.SuggestedBrand(name="A", homepage_candidates=["http://localhost", "https://invented.example", "https://real.example"], instagram_candidate="https://instagram.com.attacker.example/a"))
    data = project_discovery.sanitize(parsed, {"http://localhost", "https://real.example"})
    assert data["own"]["homepage_candidates"] == ["https://real.example"]
    assert not data["own"]["instagram_candidate"]


def article():
    return {"id": "n1", "kind": "뉴스", "text": "조사기관은 2025년 가구 매출이 12% 증가했다고 발표했다.", "source_url": "https://news.example/a", "published_at": "2026-01-02", "brand": "A", "collected_at": "2026-01-03"}


def test_digest_validation_export_and_backup():
    row = article()
    good = news_digest.Highlight(article_id="n1", evidence=row["text"], value="12", unit="%", period="2025년", subject="가구")
    result = {"status": "완료", "highlights": news_digest.validate(news_digest.Digest(highlights=[good]), news_digest.inputs([row])), "processed": 1}
    assert result["highlights"]
    for bad in (good.model_copy(update={"value": "2"}), good.model_copy(update={"value": "15"}), good.model_copy(update={"article_id": "another"}), good.model_copy(update={"evidence": "주장에 없는 새로운 통계 수치입니다."})):
        assert not news_digest.validate(news_digest.Digest(highlights=[bad]), news_digest.inputs([row]))
    assert not news_digest.export_rows(result, [])
    assert news_digest.export_rows(result, [row])[0]["수치"] == "12"
    pid = projects.create("A", {"brand_name": "A"})
    from database.db import save_function_run
    rid = save_function_run(pid, "news", "완료", {"source": "news", "status": "완료", "schema_version": 4, "records": [row], "parts": {}})
    news_digest.save(rid, [row], result)
    assert news_digest.load(rid, [row]) == result
    assert news_digest.load(rid, [{**row, "text": "다른 내용"}]) is None
    clone = project_backup.restore([data for _, data in project_backup.make(pid)])
    restored_run = projects.histories(clone)[0]["run_id"]
    assert news_digest.load(restored_run, [row]) == result


def test_digest_batches_cache_and_sample_no_call(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)
    calls = []
    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return NS(text='{"highlights": []}')
    monkeypatch.setattr("core.analyzers.gemini_client.get_client", lambda: NS(models=Models()))
    rows = [{**article(), "id": str(i), "source_url": f"https://news.example/{i}"} for i in range(40)]
    assert news_digest.generate(rows)["processed"] == 30
    assert news_digest.generate(rows)["processed"] == 30 and len(calls) == 2
    assert news_digest.generate([{**article(), "sample": True}])["status"] == "대상 없음"
    assert len(calls) == 2


def test_comparison_only_selected_social_version():
    from core.project_view import comparison_rows
    p = projects.project_inputs({"brand_name": "A", "sources": {"A": {"instagram": "@a"}}})
    def snapshot(value, date):
        return {"source": "instagram", "created": date, "result": {"parts": {"instagram:own": {"state": "완료"}},
                "records": [{"kind": "Instagram", "brand_id": "own", "followers": value}]}}
    old = snapshot(10, "2025-01-01")
    new = snapshot(20, "2026-01-01")
    assert comparison_rows(p, [old], None)[0][0]["Instagram 팔로워"] == "10"
    assert comparison_rows(p, [new], None)[0][0]["Instagram 팔로워"] == "20"
