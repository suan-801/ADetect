import copy
import json
from types import SimpleNamespace as NS
import pytest
from config import settings
from core import research_analysis as ra, projects, project_backup


def result():
    return {"schema_version": 7, "records": [{"id": "n1", "kind": "뉴스", "title": "시장 조사 발표", "text": "공개 조사에서 구매 전 체험 수요가 나타났다고 발표했다.", "source_url": "https://news.example/a", "published_at": "2026-09-01"}], "parts": {}, "inputs": {}}


BRIEF = {"market": "가구", "region": "한국", "period": "2026", "goal": "상담 신청"}


def parsed(payload):
    ref = payload["evidence"][0]
    return ra.Analysis(sections=[ra.AnalysisSection(title=name, items=[ra.Insight(
        title="체험 메시지 검증", observation=ref["text"], interpretation="체험 수요에 대한 가설",
        action="두 메시지 비교", audience="구매를 고민하는 고객", message="체험 안내", channel="검색의 관심 포착",
        landing="체험 조건 안내", validation="신청 전환율 비교", limitation="실제 전환 자료 없음",
        citations=[ra.Citation(evidence_id=ref["id"], quote=ref["text"])])]) for name in ra.SECTIONS])


def test_grounding_rejects_fabricated_quotes_and_urls():
    payload = ra.packet(result(), BRIEF)
    data = parsed(payload)
    assert len(ra.validate(data, payload)) == 5
    data.sections[0].items[0].citations[0].quote = "없는 수치 100퍼센트 증가했다"
    with pytest.raises(ValueError): ra.validate(data, payload)
    data = parsed(payload)
    data.sections[0].items[0].interpretation = "https://invented.example"
    with pytest.raises(ValueError): ra.validate(data, payload)


def test_fingerprint_all_selection_and_brief_changes():
    r = result()
    key = ra.fingerprint(r, BRIEF)
    assert ra.fingerprint({**r, "collected_at": "later", "ai_analysis": {}}, BRIEF) == key
    assert ra.fingerprint({**r, "records": []}, BRIEF) != key
    assert ra.fingerprint(r, {**BRIEF, "goal": "구매"}) != key
    assert ra.fingerprint({**r, "inputs": {"versions": ["changed"]}}, BRIEF) != key


def test_generation_cache_usage_limits_and_no_sample_calls(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)
    calls = []
    class Models:
        def count_tokens(self, **kw): return NS(total_tokens=1000)
        def generate_content(self, **kw):
            calls.append(kw)
            return NS(text=parsed(ra.packet(result(), BRIEF)).model_dump_json(), usage_metadata=NS(prompt_token_count=1000, candidates_token_count=500, thoughts_token_count=100, total_token_count=1600))
    monkeypatch.setattr("core.analyzers.gemini_client.get_client", lambda: NS(models=Models()))
    a = ra.generate({}, result(), BRIEF)
    assert a["status"] == "완료" and a["usage"]["total"] == 1600
    assert ra.generate({}, result(), BRIEF) == a and len(calls) == 1
    assert ra.generate({}, {**result(), "sample_sources": ["SAMPLE"]}, BRIEF)["status"] == "설정 필요"
    monkeypatch.setattr(Models, "count_tokens", lambda self, **kw: NS(total_tokens=20001))
    assert ra.generate({}, result(), {**BRIEF, "goal": "다른 목표"})["status"] == "입력 한도"
    assert len(calls) == 1


def test_balanced_news_deduplicates_and_preserves_brands():
    base = result()["records"][0]
    rows = [{**base, "id": str(i), "source_url": f"https://news.example/{i}", "found_brands": ["A"]} for i in range(40)]
    rows.append({**base, "id": "B", "found_brands": ["B"], "text": "B 신제품 출시 소식을 공개했다.", "title": "B 신제품 출시"})
    before = copy.deepcopy(rows)
    chosen = ra.balanced(rows)
    assert len(chosen) == 2 and rows == before


def test_backup_analysis_export_and_delete():
    pid = projects.create("A", {"brand_name": "A"})
    analysis = {"status": "완료", "brief": BRIEF, "sections": ra.validate(parsed(ra.packet(result(), BRIEF)), ra.packet(result(), BRIEF))}
    ra.save(pid, {"brief": BRIEF, "analysis": analysis})
    clone = project_backup.restore([data for _, data in project_backup.make(pid)])
    assert ra.load(clone) == ra.load(pid)
    from core.exporters import facts_report
    tables = facts_report.tables_for({**result(), "ai_analysis": analysis})
    assert len(tables["27_AI종합분석"]) == 5
    html = facts_report.report_html({}, {**result(), "ai_analysis": analysis})
    assert "AI 핵심 결론" in html and "AI 종합 분석" in html and "<details open" not in html
    projects.delete(pid, "A")
    assert ra.load(pid) == {}


def test_market_research_accepts_only_supported_segments(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)
    metadata = NS(grounding_chunks=[NS(web=NS(uri="https://agency.example/report"))], grounding_supports=[NS(segment=NS(text="시장 보고서의 근거 문장입니다."), grounding_chunk_indices=[0])])
    response = NS(candidates=[NS(grounding_metadata=metadata)], usage_metadata=None)
    monkeypatch.setattr("core.analyzers.gemini_client.get_client", lambda: NS(models=NS(generate_content=lambda **kw: response)))
    r = ra.research({}, BRIEF)
    assert r["status"] == "완료" and r["evidence"][0]["source"] == "https://agency.example/report"
    assert len(ra.packet(result(), {**BRIEF, "goal": "changed"}, r)["evidence"]) == 1
    metadata.grounding_supports = []
    assert ra.research({}, BRIEF)["status"] == "실패"


def test_quota_error_does_not_claim_balance_exhaustion():
    class Quota(Exception): code = 429
    assert "한도" in ra.failure(Quota())["message"]
    assert "토큰 부족" not in ra.failure(Quota())["message"]


def test_saved_analysis_ui_and_stale_exclusion():
    from streamlit.testing.v1 import AppTest
    pid = projects.create("A", {"brand_name": "A"})
    r = result()
    stored = {"status": "완료", "sections": ra.validate(parsed(ra.packet(r, BRIEF)), ra.packet(r, BRIEF)),
              "brief": BRIEF, "fingerprint": ra.fingerprint(r, BRIEF), "created": "2026-09-29", "model": "test"}
    ra.save(pid, {"brief": BRIEF, "analysis": stored})
    script = f'''import streamlit as st
from ui.research_analysis import render
from core import projects
result = {r!r}
st.session_state.current_analysis = render(projects.load({pid!r}), {{"paid_enabled": False}}, result, st.empty())
'''
    at = AppTest.from_string(script).run()
    assert not at.exception and at.session_state.current_analysis["status"] == "완료"
    assert any("AI 핵심 결론" in m.value for m in at.markdown)
    ra.save(pid, {"brief": {**BRIEF, "goal": "새 목표"}, "analysis": stored})
    at.run()
    assert not at.exception and at.session_state.current_analysis is None
    assert any("갱신" in w.value for w in at.warning)
