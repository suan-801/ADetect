import copy
import json
from datetime import date
from io import BytesIO
from types import SimpleNamespace as NS
from zipfile import ZipFile, ZIP_DEFLATED

from config import settings
from core import projects, project_sources, project_discovery, project_backup, stat_discovery, utm
from core.result_insights import trend_facts, news_sections
from core.scrapers import search_history
from core.exporters import facts_report, visual_report


def series(rows):
    return {"name": "A", "keyword": "A", "start": "2026-01-01", "end": "2026-06-30",
            "rows": [{"date": "2026-" + month + "-01", "search_index": value} for month, value in rows]}


def article(identity, title, brand="A"):
    return {"id": identity, "kind": "뉴스", "brand": brand, "found_brands": [brand], "title": title,
            "excerpt": "원문 발췌입니다. 별도 해석을 추가하지 않습니다.", "text": title + "\n원문 발췌입니다. 별도 해석을 추가하지 않습니다.",
            "source_url": "https://news.example/" + identity, "published_at": "2026-09-02", "collected_at": "2026-09-03"}


def test_calendar_period_complete_and_month_boundary_cache(monkeypatch):
    assert search_history.period_bounds(today=date(2026, 1, 1)) == ("2023-01-01", "2025-12-31")
    assert search_history.period_bounds(today=date(2024, 3, 5)) == ("2021-01-01", "2024-02-29")
    monkeypatch.setattr(settings, "SAMPLE_MODE", True)
    monkeypatch.setattr(search_history, "period_bounds", lambda *a: ("2023-01-01", "2026-08-31"))
    first = search_history.fetch_history("A")
    assert len(first["rows"]) == 44 and search_history.summarize_history(first)["complete"]
    monkeypatch.setattr(search_history, "period_bounds", lambda *a: ("2023-01-01", "2026-09-30"))
    second = search_history.fetch_history("A")
    assert second["end"] == "2026-09-30" and len(second["rows"]) == 45


def test_facts_keep_ties_zeros_and_skip_gaps_and_invalid_values():
    s = series([("01", 0), ("02", 10), ("04", 90), ("05", 100), ("06", 100)])
    facts = trend_facts(s)
    high = next(f for f in facts if f["항목"] == "최고")
    assert "2026-05" in high["관측 사실"] and "2026-06" in high["관측 사실"]
    rise = next(f for f in facts if f["항목"] == "최대 전월 상승")["관측 사실"]
    assert "2026-01 → 2026-02" in rise and "2026-04 → 2026-05" in rise and "+80" not in rise
    assert any("1개월 미제공" in f["관측 사실"] for f in facts)
    assert len(trend_facts(series([("01", None), ("02", float("nan")), ("03", float("inf"))]))) == 0
    assert trend_facts(series([("01", 0), ("02", 0)]))[0]["항목"] == "변동 없음"
    chart = visual_report.chart([s], s["start"], s["end"])
    assert chart.count("<polyline") == 2  # February-to-April is not connected.


def test_news_groups_conservatively_and_preserves_all_sources():
    a = article("1", "르노코리아 9월 특별 프로모션 실시")
    b = article("2", "르노코리아, 9월 특별 프로모션 실시")
    c = article("3", "르노코리아 10월 특별 프로모션 실시")
    d = article("4", "르노코리아 차량 리콜 발표")
    rows = [a, b, c, d]
    before = copy.deepcopy(rows)
    sections = news_sections(rows)
    promo = next(s for s in sections if "프로모션" in s["title"])
    assert sorted(len(g["articles"]) for g in promo["groups"]) == [1, 2]
    assert sum(s["count"] for s in sections) == 4 and rows == before
    assert "악재" not in json.dumps(sections, ensure_ascii=False)


def test_utm_only_nonempty_values_separate_parameters_and_brand_attribution():
    p = projects.project_inputs({"brand_name": "A", "sources": {"A": {"official_urls": ["https://a.example"], "utm_urls": [
        "https://a.example/?utm_source=&utm_medium=", "https://a.example/?gclid=click",
        "https://a.example/?utm_source=&utm_source=meta&utm_content=summer_2026_banner&api_key=secret",
        "https://a.example/?utm_custom=abc"]}}})
    rows = project_sources.utm_rows(p, [{"kind": "검색 화면", "keyword": "A", "ads": [{"links": ["https://a.example/?utm_medium=cpc", "https://other.example/?utm_source=naver"]}]}])
    assert len(rows) == 4
    assert any(r["브랜드"] == "브랜드 미확정" for r in rows)
    public = utm.public(rows)
    assert all(utm.has_values(r) for r in public)
    assert "secret" not in json.dumps(public)
    structures = utm.structure_rows(rows)
    assert all("조합" not in r for r in structures)
    assert next(r for r in structures if r["UTM 항목"] == "utm_content")["추정 구조"] == "{문자열}_{숫자}_{문자열}"
    assert not utm.has_values(utm.parse("https://[malformed"))


def test_social_grounding_profiles_and_competitor_site_links(monkeypatch):
    good_ig = "https://www.instagram.com/official/"
    good_yt = "https://www.youtube.com/@official/videos"
    parsed = project_discovery.ProjectSuggestions(own=project_discovery.SuggestedBrand(name="A", instagram_candidate=good_ig, youtube_candidate=good_yt),
        competitors=[project_discovery.SuggestedBrand(name="B", instagram_candidate="https://instagram.com/p/post/", homepage_candidates=["https://b.example"])])
    result = project_discovery.sanitize(parsed, {good_ig, good_yt, "https://instagram.com/p/post/", "https://b.example"})
    assert result["own"]["instagram_candidate"] == good_ig and result["own"]["youtube_candidate"] == "@official"
    assert not result["competitors"][0]["instagram_candidate"]
    monkeypatch.setattr("core.scrapers.brand_site.fetch_public_html", lambda u: ('<a href="https://instagram.com/brandb/">IG</a>', u))
    assert project_discovery.site_links(result)["competitors"][0]["instagram_candidate"] == "https://www.instagram.com/brandb/"


def test_visual_export_raw_text_safe_links_observed_only_and_brand_zip():
    from core.evidence_store import save_bytes
    asset = save_bytes(b"fixture", "png", "https://a.example")
    ad = {"id": "ad", "kind": "광고", "brand": "A/B", "source_url": "https://ad.example", "landing_url": "javascript:alert(1)", "text": "<script>alert(1)</script>" + "문구"*400, "collected_at": "now", "assets": [asset]}
    other = {**ad, "id": "other", "brand": "A?B"}
    news = article("n", "A 프로모션")
    capture = {"id": "capture", "kind": "검색 화면", "brand": "A/B", "source_url": "https://search.example", "text": "관측", "collected_at": "now", "brand_status": {"own": {"name": "A", "state": "이번 화면에서 미관측"}}}
    result = {"schema_version": 5, "records": [ad, other, news, capture], "parts": {}, "inputs": {"project": "가독성 검증"}, "sample_sources": ["SAMPLE"]}
    tables = facts_report.project_tables(result)
    assert "08_검색화면광고관측" not in tables
    assert tables["24_검색관측전체상태"][0]["노출 상태"] == "이번 화면에서 미관측"
    assert tables["10_Meta광고"][0]["전체 문구"] == ad["text"]
    markup = facts_report.report_html({"brand_name": "A"}, result)
    assert "원본 데이터" in markup and "SAMPLE" in markup and "media-card" in markup
    assert '<script>' not in markup and 'href="javascript:' not in markup
    with ZipFile(BytesIO(facts_report.package({"brand_name": "A"}, result))) as archive:
        originals = [n for n in archive.namelist() if n.startswith("originals/")]
        assert len(originals) == 2 and len({n.split("/")[1] for n in originals}) == 2
        assert all(".." not in n for n in originals)
        manifest = json.loads(archive.read("원본_경로목록.json"))
        assert all(r["ZIP 경로"] in archive.namelist() for r in manifest)
        assert all(archive.read(n) == b"fixture" for n in originals)


def test_stat_recommendations_validate_cache_backup_and_no_paid_calls(monkeypatch):
    p = projects.project_inputs({"brand_name": "A", "market_keywords": ["자동차"]})
    calls = []
    url = "https://industry.example/statistics"
    evidence = "산업협회의 월별 자동차 등록 통계 자료입니다."
    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            if len(calls) % 2:
                return NS(text=evidence, candidates=[NS(grounding_metadata=NS(grounding_chunks=[NS(web=NS(uri=url))]))])
            return NS(text=json.dumps({"resources": [{"title": "자동차 등록", "url": url, "reason": "자동차 시장 자료", "evidence": evidence, "confidence": "medium"}]}))
    monkeypatch.setattr("core.analyzers.gemini_client.get_client", lambda: NS(models=Models()))
    assert stat_discovery.generate(p)["status"] == "설정 필요" and not calls
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(settings, "GEMINI_MOCK", False)
    result = stat_discovery.generate(p)
    assert result["status"] == "완료" and len(calls) == 2
    assert stat_discovery.generate(p) == result and len(calls) == 2
    forged = stat_discovery.Resources(resources=[stat_discovery.Resource(title="fake", url="https://fake.example", reason="", evidence=evidence)])
    assert not stat_discovery.validate(forged, {url}, evidence)
    pid = projects.create("A", projects.to_storage(p))
    stat_discovery.save(pid, p, result)
    assert stat_discovery.load(pid, p) == result
    assert not stat_discovery.load(pid, {**p, "market_keywords": ["가구"]})
    clone = project_backup.restore([data for _, data in project_backup.make(pid)])
    assert stat_discovery.load(clone, p) == result
    projects.delete(clone, projects.load(clone)["name"])
    assert stat_discovery.load(clone, p) is None
    monkeypatch.setattr(settings, "SAMPLE_MODE", True)
    assert stat_discovery.generate(p)["status"] == "설정 필요" and len(calls) == 2


def test_previous_backup_envelope_still_restores():
    pid = projects.create("Legacy", {"brand_name": "A"})
    packages = project_backup.make(pid)
    old = []
    for _, raw in packages:
        out = BytesIO()
        with ZipFile(BytesIO(raw)) as src, ZipFile(out, "w", ZIP_DEFLATED) as dst:
            for name in src.namelist():
                data = src.read(name)
                if name == "manifest.json":
                    manifest = json.loads(data)
                    manifest["schema_version"] = 3
                    data = json.dumps(manifest).encode()
                dst.writestr(name, data)
        old.append(out.getvalue())
    assert projects.load(project_backup.restore(old))["brand_name"] == "A"
