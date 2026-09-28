"""v4 프로젝트 흐름: 경쟁사 공동 비교, 검색량 합계, 뉴스 전용 필터, 선택·다운로드 일치, 광고 관측, UTM, 호환."""
import json

import pytest

from config import settings
from core import projects, project_sources, project_view, utm


def project(**extra):
    base = {"brand_name": "한샘", "input_version": 4, "paid_enabled": True,
            "brands": [{"id": "own", "name": "한샘", "role": "own", "terms": ["한샘", "한셈", "한샘리하우스"],
                        "sources": {"official_urls": ["https://www.hanssem.com", "https://smartstore.naver.com/hanssem"], "instagram": "@hanssem"}},
                       {"id": "c1", "name": "리바트", "role": "competitor", "terms": ["리바트", "현대리바트"], "sources": {"instagram": "@livart", "official_urls": ["https://www.hyundailivart.co.kr"]}}],
            "market_keywords": ["인테리어"], "news_keywords": ["한샘"], "news_filter": {"include": [], "exclude": []}}
    return projects.project_inputs({**base, **extra})


class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


def test_brand_terms_go_as_one_group_and_brands_share_one_request(monkeypatch):
    from core.scrapers import search_history
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs["json"])
        # 경쟁사 응답 누락을 흉내낸다: 누락 브랜드를 다른 브랜드 값으로 채우면 안 된다.
        return Response({"results": [{"title": "한샘", "data": [{"period": "2026-07-01", "ratio": 100}, {"period": "2026-08-01", "ratio": 80}]}]})
    monkeypatch.setattr(settings, "NAVER_DATALAB_MOCK", False)
    monkeypatch.setattr(search_history.requests, "post", post)
    p = project()
    groups = [{"id": b["id"], "name": b["name"], "terms": b["terms"]} for b in p["brands"]]
    data = search_history.fetch_comparison(groups)
    assert len(calls) == 1, "자사·경쟁사는 한 요청"
    assert calls[0]["keywordGroups"] == [{"groupName": "한샘", "keywords": ["한샘", "한셈", "한샘리하우스"]},
                                         {"groupName": "리바트", "keywords": ["리바트", "현대리바트"]}]
    assert [s["name"] for s in data["series"]] == ["한샘", "리바트"], "모든 요청 그룹을 보존"
    assert data["series"][1]["provided"] is False and data["series"][1]["rows"] == []
    assert [r["search_index"] for r in data["series"][0]["rows"]] == [100, 80], "표기별 합산·0 채움 없음"


def test_comparison_limits_and_legacy_trend_not_merged():
    with pytest.raises(ValueError):
        from core.scrapers.search_history import fetch_comparison
        fetch_comparison([{"id": str(i), "name": str(i), "terms": ["x"]} for i in range(6)])
    p = project()
    legacy = {"result": {"parts": {"trend:한샘": {"series": {"keyword": "한샘", "rows": [{"date": "2026-01-01", "search_index": 50}]}}}}}
    assert project_view.trend_view(legacy, p)["kind"] == "legacy"
    compare = {"result": {"parts": {"trend:compare": {"comparison": {"signature": projects.comparison_signature(p["brands"]), "series": []}}}}}
    assert project_view.trend_view(compare, p)["stale"] is False
    changed = {**p, "brands": p["brands"][:1]}
    assert project_view.trend_view(compare, changed)["stale"] is True, "비교 구성이 바뀌면 재조회 안내"


def test_volume_total_excludes_duplicates_related_and_keeps_lt10_missing():
    p = project()
    item = {"created": "2026-09-27T00:00:00+00:00", "result": {"parts": {
        "volume:own": {"brand_id": "own", "terms": [
            {"term": "한샘", "state": "완료", "pc": 1000, "mobile": 3000},
            {"term": "한 샘", "state": "완료", "pc": 1000, "mobile": 3000},   # 공백만 다른 중복
            {"term": "한셈", "state": "완료", "pc": "< 10", "mobile": 20},
            {"term": "한샘리하우스", "state": "미제공"}]},
        "volume:c1": {"brand_id": "c1", "terms": [{"term": "리바트", "state": "완료", "pc": 500, "mobile": 700}, {"term": "현대리바트", "state": "실패"}]}}}}
    totals = {r["brand_id"]: r for r in project_view.volume_totals(item, p["brands"])}
    assert totals["own"]["검색어 수"] == 3
    assert totals["own"]["PC"] == "확인된 값 합계 1,000 · 일부 값 미제공 1개"
    assert totals["own"]["합계"] == "확인된 값 합계 4,020 · 일부 값 미제공 2개"
    assert not totals["own"]["정확한 합계"]
    assert project_view.format_total(1000, 1, 0) == "1,000~1,009 (<10 1개 포함 범위)"
    assert project_view.format_total(1200, 0, 0) == "1,200"
    assert "미제공" in totals["c1"]["합계"], "실패를 0으로 만들지 않음"


def test_volume_collector_uses_exact_match_only(monkeypatch):
    from core.scrapers import naver_ad_api
    monkeypatch.setattr(settings, "NAVER_AD_MOCK", False)
    rows = {"한샘": [{"keyword": "한샘", "monthly_pc_display": 100, "monthly_mobile_display": 200}, {"keyword": "한샘가구", "monthly_pc_display": 9999, "monthly_mobile_display": 9999}],
            "한셈": [{"keyword": "한셈몰", "monthly_pc_display": 5, "monthly_mobile_display": 5}], "한샘리하우스": [], "리바트": [], "현대리바트": [], "인테리어": []}
    monkeypatch.setattr(naver_ad_api, "fetch_keyword_stats", lambda k: rows[k])
    result = project_sources.collect("volume", project(), {})
    own = result["parts"]["volume:own"]
    assert [t["state"] for t in own["terms"]] == ["완료", "미제공", "미제공"]
    item = {"created": "2026-09-27", "result": result}
    total = {r["brand_id"]: r for r in project_view.volume_totals(item, project()["brands"])}["own"]
    assert "9,999" not in total["합계"] and total["합계"].startswith("확인된 값 합계 300"), "연관 검색어는 합계 제외"


def test_news_filter_rules_and_scope():
    brand_only = {"include": ["리하우스"], "exclude": ["채용"]}
    news = lambda text: {"kind": "뉴스", "text": text}
    assert projects.news_passes(news("한샘 리하우스 출시"), brand_only)
    assert not projects.news_passes(news("한샘 신제품"), brand_only), "꼭 들어갈 문구가 없으면 숨김"
    assert not projects.news_passes(news("리하우스 채용 공고"), brand_only), "겹치면 제외 우선"
    assert projects.news_passes(news("아무 기사"), {"include": [], "exclude": []}), "조건 없음"
    assert projects.news_passes({"kind": "광고", "text": "채용 광고"}, brand_only), "다른 자료에는 적용하지 않음"
    # 조사 대상(campaign)이 없어도 레거시 분류도 제외 문구를 먼저 확인한다.
    from core.collection import relevance
    assert relevance({"text": "한샘 채용"}, {"brand_name": "한샘", "exclude_terms": ["채용"]})[0] == "제외"


def test_legacy_project_loads_as_single_brand_and_filter_becomes_news_only():
    old = {"brand_name": "메리츠화재", "brand_keywords": ["메리츠화재", "메리츠"], "general_keywords": ["보험"], "include_terms": ["TM"], "exclude_terms": ["주가"],
           "sources": {"메리츠화재": {"homepage": "https://www.meritzfire.com"}}, "competitors": []}
    p = projects.project_inputs(old)
    assert [(b["id"], b["role"], b["terms"]) for b in p["brands"]] == [("own", "own", ["메리츠화재", "메리츠"])]
    assert p["market_keywords"] == ["보험"] and p["news_filter"] == {"include": ["TM"], "exclude": ["주가"]} and p["legacy_filter_converted"]
    assert old["include_terms"] == ["TM"], "원본 입력은 바꾸지 않음"
    stored = projects.to_storage(p)
    assert stored["input_version"] == 4 and stored["competitors"] == [] and stored["brand_keywords"] == ["메리츠화재", "메리츠"]


def test_validation_limits_and_conflicts():
    p = project()
    p["brands"][1]["terms"] = ["리바트", "한샘"]
    assert projects.term_conflicts(p["brands"]) == [("한샘", ["리바트", "한샘"])]
    many = {**p, "brands": p["brands"][:1] + [{"id": f"c{i}", "name": f"경쟁{i}", "role": "competitor", "terms": ["x" + str(i)], "sources": {}} for i in range(5)]}
    assert any("최대 4개" in e for e in projects.validate_inputs(many))


def test_unselected_sources_are_not_called(monkeypatch):
    from core.scrapers import search_history, naver_ad_api, naver_api, ad_library, youtube, naver_serp
    monkeypatch.setattr(settings, "SAMPLE_MODE", True)
    def forbidden(*a, **k): raise AssertionError("선택하지 않은 자료가 호출됨")
    for module, name in ((search_history, "fetch_comparison"), (search_history, "fetch_history"), (naver_ad_api, "fetch_keyword_stats"),
                         (ad_library, "fetch_instagram_profile"), (ad_library, "fetch_meta_ads_detail"), (youtube, "fetch_youtube"), (naver_serp, "observe_search")):
        monkeypatch.setattr(module, name, forbidden)
    calls = []
    monkeypatch.setattr(naver_api, "get_news", lambda k, **kw: calls.append(k) or [{"title": "한샘 리바트 협업", "summary": "요약", "url": "https://n.example/a?utm_source=x", "published_at": "2026-09-01"}])
    result = project_sources.collect("news", project(news_keywords=["한샘", "리바트"]), {})
    assert calls == ["한샘", "리바트"]
    assert len(result["records"]) == 1, "같은 기사는 한 행"
    row = result["records"][0]
    assert set(row["matched_queries"]) == {"한샘", "리바트"} and set(row["found_brands"]) == {"한샘", "리바트"}, "발견 관계 보존"
    empty = project_sources.collect("news", project(news_keywords=[]), {})
    assert empty["status"] == "설정 필요" and "요청하지 않았습니다" in empty["parts"]["news"]["message"]


def test_competitor_addition_does_not_expand_paid_scope():
    p = project()
    assert project_sources.default_brands("meta", {**p, "brands": [{**b, "sources": {**b["sources"], "meta_page": "x"}} for b in p["brands"]]}) == ["own"]
    assert project_sources.default_brands("website", p) == ["own"]
    history = [{"source": "instagram", "created": "2026-09-27", "result": {"status": "완료", "records": [{"kind": "Instagram", "brand_id": "own"}]}}]
    assert project_sources.default_brands("instagram", p, history) == ["c1"], "이미 수집한 자사 계정은 기본에서 제외"
    assert project_sources.readiness("instagram", p, paid_enabled=False) == (False, "유료 기능 OFF")


def test_capture_failure_or_unidentified_area_is_not_no_ad():
    brand = project()["brands"][0]
    assert project_sources.ad_status({"state": "failed", "message": "캡처 실패"}, brand)["state"] == "판독 불가"
    assert project_sources.ad_status({"state": "blocked"}, brand)["state"] == "판독 불가"
    unidentified = {"state": "captured", "areas": {"powerlink": {"identified": False, "ads": []}}}
    assert project_sources.ad_status(unidentified, brand)["state"] == "판독 불가"
    seen = {"state": "captured", "areas": {"powerlink": {"identified": True, "ads": [{"text": "한샘 리모델링", "display_url": "www.hanssem.com/event", "links": []}]}}}
    assert project_sources.ad_status(seen, brand)["state"] == "관측 시 노출 확인"
    store = {"state": "captured", "areas": {"powerlink": {"identified": True, "ads": [{"text": "가구", "display_url": "smartstore.naver.com/otherstore", "links": []}]}}}
    assert project_sources.ad_status(store, brand)["state"] == "이번 화면에서 미관측", "공유 호스트는 판매자 경로까지 일치해야 함"
    name_only = {"state": "captured", "areas": {"powerlink": {"identified": True, "ads": [{"text": "한샘 가구 최저가", "display_url": "cheap.example.com", "links": []}]}}}
    assert project_sources.ad_status(name_only, brand)["state"] == "판독 불가", "브랜드명 문자열만으로 광고주 확정 금지"


def test_gemini_failure_keeps_capture_and_direct_extraction(monkeypatch):
    from core import capture_reader
    from core.scrapers import naver_serp
    failed = capture_reader.read_capture(b"png-bytes", caller=lambda img, prompt: (_ for _ in ()).throw(RuntimeError("503")))
    assert failed["state"] == "실패" and failed["ads"] == []
    ok = capture_reader.read_capture(b"png-2", caller=lambda img, prompt: json.dumps({"ads": [
        {"area": "powerlink", "advertiser_visible": "한샘", "copy_visible": "리하우스 상담", "display_url_visible": None, "image_description": None, "confidence": "medium", "landing_url": "https://invented.example"},
        {"area": "powerlink", "advertiser_visible": None, "copy_visible": None, "confidence": "high"}]}))
    assert len(ok["ads"]) == 1 and "landing_url" not in ok["ads"][0], "근거 없는 판독·URL 생성 제거"
    obs = {"keyword": "한샘", "source_url": "https://search.naver.com/search.naver?query=한샘", "captured_at": "2026-09-27T00:00:00+00:00",
           "environment": "PC", "state": "captured", "screenshot": b"\x89PNGfirst",
           "areas": {"powerlink": {"identified": True, "ads": [{"title": "t", "text": "", "display_url": "www.hanssem.com", "links": []}], "screenshot": b"\x89PNGarea"}}}
    monkeypatch.setattr(naver_serp, "observe_search", lambda k: obs)
    monkeypatch.setattr(capture_reader, "read_capture", lambda img, caller=None: {"state": "실패", "ads": [], "method": "Gemini"})
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "x" * 12)
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)
    result = project_sources.collect("search_capture", project(market_keywords=[]), {"brands": ["own"], "ai_read": True})
    row = result["records"][0]
    assert row["ai_read"]["state"] == "실패"
    assert [a["role"] for a in row["assets"]] == ["첫 화면", "파워링크 영역"] and row["ads"][0]["display_url"] == "www.hanssem.com"
    assert row["brand_status"]["own"]["state"] == "관측 시 노출 확인"


def test_utm_parsing_rules():
    row = utm.parse("https://Www.Hanssem.com/ev?UTM_Source=meta&utm_medium=&utm_campaign=%EB%A6%AC%ED%95%98%EC%9A%B0%EC%8A%A4&utm_campaign=b&access_token=SECRET&fbclid=abc", "한샘", "Meta")
    assert row["utm_source"] == "meta" and row["utm_medium"] == "" and row["utm_campaign"] == "리하우스"
    assert "SECRET" not in json.dumps(row, ensure_ascii=False)
    for note in ("대소문자 표기 차이", "빈 값: utm_medium", "중복 키: utm_campaign (값 다름)"):
        assert note in row["특이사항"]
    assert "fbclid=abc" in row["기타 추적 파라미터"]
    assert utm.parse("https://www.hanssem.com/", "한샘")["상태"] == "확인한 URL에 UTM 없음"
    assert utm.parse("https://ad.search.naver.com/click?x=1", "한샘")["상태"].startswith("최종 URL 미확보")
    groups = utm.campaign_groups([utm.parse("https://a.com/?utm_campaign=Sale&utm_source=meta", "A"), utm.parse("https://a.com/?utm_campaign=sale&utm_source=naver", "A")])
    assert groups[0]["근거 URL 수"] == 2 and "meta" in groups[0]["조합"] and "naver" in groups[0]["조합"]
    # 뉴스 중복 제거용 URL 정리는 광고 원본 UTM을 지우지 않는다.
    assert "utm_campaign=x" in projects.normalize({"records": [{"id": "a", "kind": "광고", "brand": "A", "source_url": "https://f.com/1", "text": "", "landing_url": "https://a.com/?utm_campaign=x"}], "parts": {}}, "meta", {"input_version": 4})["records"][0]["landing_url"]


def test_selection_and_download_follow_the_same_filter():
    pid = projects.create("한샘", projects.to_storage(project()))
    from database.db import save_function_run, get_conn
    news = [{"id": "n1", "kind": "뉴스", "brand": "한샘", "source_url": "https://n/1", "text": "한샘 채용 소식", "collected_at": "x"},
            {"id": "n2", "kind": "뉴스", "brand": "한샘", "source_url": "https://n/2", "text": "한샘 리하우스", "collected_at": "x"},
            {"id": "n3", "kind": "뉴스", "brand": "한샘", "source_url": "https://n/3", "text": "한샘 가구", "collected_at": "x"}]
    rid = save_function_run(pid, "news", "완료", {"schema_version": 4, "source": "news", "status": "완료", "records": news, "parts": {}})
    with get_conn() as conn:
        projects.schema(conn)
        conn.execute("INSERT INTO project_review VALUES(?,?,?)", (rid, "n3", "제외"))  # 이전 화면에서 사용자가 직접 제외
    snaps = [h for h in projects.histories(pid) if projects.available(h)]
    selected = projects.default_selection(snaps)
    assert rid + "/n3" not in selected, "과거 수동 제외는 기본 다운로드에 되살리지 않음"
    result = projects.selection_result(projects.load(pid), snaps, selected, {"include": [], "exclude": ["채용"]})
    assert [r["id"] for r in result["records"]] == ["n2"] and result["hidden_by_news_filter"] == 1
    assert all("review" not in r for r in result["records"]) and result["schema_version"] == projects.RESULT_VERSION
    from core.exporters import facts_report
    tables = facts_report.tables_for(result)
    assert [r["제목"] for r in tables["07_뉴스"]] == ["한샘 리하우스"]
    assert all("자료ID" not in row and "selection_id" not in row for rows in tables.values() for row in rows)
    info = {r["항목"]: r["값"] for r in tables["17_수집조건"]}
    assert info["뉴스 결과 좁히기 · 빼고 싶은 문구"] == "채용" and info["경쟁사 · 리바트 검색어 묶음"] == "리바트, 현대리바트"
    assert list(tables)[0] == "07_뉴스" or list(tables).index("17_수집조건") > list(tables).index("07_뉴스"), "상세 → 수집 조건 순서"


def test_old_backup_without_brands_restores(tmp_path):
    from core import project_backup
    old_inputs = {"brand_name": "한샘", "brand_keywords": ["한샘"], "general_keywords": [], "sources": {}, "paid_enabled": True}
    pid = projects.create("옛 프로젝트", old_inputs)
    from database.db import save_function_run
    save_function_run(pid, "news", "완료", {"schema_version": 3, "source": "news", "status": "완료", "records": [
        {"id": "a", "kind": "뉴스", "brand": "한샘", "source_url": "https://n/a", "text": "기사", "collected_at": "x", "review": "포함"}], "parts": {}})
    packages = project_backup.make(pid)
    new_pid = project_backup.restore([data for _, data in packages])
    restored = projects.load(new_pid)
    assert projects.project_inputs(restored)["brands"][0]["name"] == "한샘"
    assert len(projects.histories(new_pid)) == 1


def test_ui_without_keys_and_with_legacy_results_does_not_break():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from database.db import save_function_run
    old = {"brand_name": "한샘", "brand_keywords": ["한샘"], "general_keywords": ["인테리어"], "include_terms": ["리하우스"], "sources": {}}
    pid = projects.create("옛 프로젝트", old)
    save_function_run(pid, "trend", "완료", {"schema_version": 3, "source": "trend", "status": "완료", "records": [],
                                            "parts": {"trend:한샘": {"label": "t", "state": "완료", "series": {"keyword": "한샘", "start": "2023-09-01", "end": "2026-08-31", "rows": [{"date": "2026-01-01", "search_index": 40}]}}}})
    save_function_run(pid, "news", "완료", {"schema_version": 3, "source": "news", "status": "완료", "parts": {},
                                           "records": [{"id": "a", "kind": "뉴스", "brand": "한샘", "source_url": "https://n/a", "text": "한샘 리하우스", "collected_at": "x", "review": "포함"}]})
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app_pages/2_analyze.py"), default_timeout=30)
    at.session_state["project_id"] = pid
    at.session_state["step"] = "workspace"
    at.run()
    assert not at.exception
    assert any("선택 불가" in (m.value or "") for m in at.markdown), "키가 없는 자료는 이유 표시"
    assert any("이전 방식" in i.value for i in at.info), "과거 개별 추이는 비교 차트에 섞지 않음"
    assert not any("SAMPLE 모드" in w.value for w in at.warning)
    assert any("뉴스 전용 필터" in i.value for i in at.info) is False  # 설정 화면에서만 안내


def test_ai_project_discovery_never_falls_back_to_fake_data(monkeypatch):
    from core import project_discovery
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_MOCK", True)
    result = project_discovery.suggest("한샘", "인테리어")
    assert result["suggestions"] is None
    assert result["status"] == "설정 필요"


def test_ai_project_discovery_accepts_structured_candidates(monkeypatch):
    from core import project_discovery
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)

    from types import SimpleNamespace as NS
    class Response:
        candidates = [NS(grounding_metadata=NS(grounding_chunks=[NS(web=NS(uri="https://www.hanssem.com"))]))]
        text = json.dumps({"category": "인테리어", "market_keywords": ["리모델링"], "news_keywords": ["한샘 리하우스"],
                           "own": {"name": "한샘", "terms": ["한샘", "한셈"], "homepage_candidates": ["https://www.hanssem.com"],
                                    "evidence_urls": ["https://www.hanssem.com"]},
                           "competitors": []}, ensure_ascii=False)
    class Models:
        def generate_content(self, **kwargs): return Response()
    class Client:
        models = Models()
    monkeypatch.setattr(project_discovery, "site_links", lambda data: data)
    monkeypatch.setattr(project_discovery, "get_client", lambda: Client(), raising=False)
    monkeypatch.setattr("core.analyzers.gemini_client.get_client", lambda: Client())
    result = project_discovery.suggest("한샘", "인테리어")
    assert result["status"] == "후보 생성 완료"
    assert result["suggestions"]["own"]["homepage_candidates"] == ["https://www.hanssem.com"]


def test_manual_exclusion_survives_backup_restore():
    from core import project_backup
    from database.db import save_function_run, get_conn
    pid = projects.create("제외 보존", {"brand_name": "A", "sources": {}})
    rid = save_function_run(pid, "news", "완료", {"schema_version": 3, "source": "news", "status": "완료", "parts": {}, "records": [
        {"id": "keep", "kind": "뉴스", "brand": "A", "source_url": "https://n/1", "text": "A1", "collected_at": "x"},
        {"id": "drop", "kind": "뉴스", "brand": "A", "source_url": "https://n/2", "text": "A2", "collected_at": "x"}]})
    projects.set_reviews(rid, {"drop": "제외"})
    new_pid = project_backup.restore([data for _, data in project_backup.make(pid)])
    snaps = [h for h in projects.histories(new_pid) if projects.available(h)]
    assert [s.rsplit("/", 1)[1] for s in projects.default_selection(snaps)] == ["keep"]
