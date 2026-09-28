import copy
from io import BytesIO
from html.parser import HTMLParser

from PIL import Image
from config import settings
from core import projects, project_sources, project_view, utm
from core.evidence_store import save_bytes, read_bytes
from core.exporters import facts_report, visual_report
from core.exporters.image_preview import compress
from core.result_insights import annual_extremes, news_sections


def test_yearly_extremes_keep_missing_years_ties_zero_and_partial_year():
    series = {"start": "2023-01-01", "end": "2026-08-31", "rows": [
        {"date": "2023-01-01", "search_index": 0}, {"date": "2023-02-01", "search_index": 60},
        {"date": "2023-03-01", "search_index": 60}, {"date": "2026-08-01", "search_index": 25},
        {"date": "2026-09-01", "search_index": 100}]}
    rows = annual_extremes(series)
    assert rows[0] == {"연도": "2023", "최저": "1월 · 지수 0", "최고": "2월, 3월 · 지수 60"}
    assert rows[1] == {"연도": "2024", "최저": "미제공", "최고": "미제공"}
    assert rows[-1]["최고"] == "8월 · 지수 25"


def test_search_ads_use_ad_domain_and_saved_brand_inputs_for_generic_keywords():
    brands = [{"name": "A", "sources": {"official_urls": ["https://a.example"]}},
              {"name": "B", "sources": {"official_urls": ["https://smartstore.naver.com/brand-b"]}}]
    row = {"kind": "검색 화면", "keyword": "시승이벤트", "selection_id": "saved/row", "ads": [
        {"area": "powerlink", "text": "A 광고", "links": ["https://a.example/event"]},
        {"area": "powerlink", "text": "다른 광고", "display_url": "https://a.example.attacker.test"},
        {"area": "powerlink", "text": "다른 판매자", "display_url": "https://smartstore.naver.com/other"},
        {"area": "powerlink", "text": "잘못된 URL", "display_url": "https://[invalid"},
        {"area": "powerlink", "text": "A 언급만 있고 도메인 없음"}],
        "ai_read": {"ads": [{"area": "brand_search", "copy_visible": "B 광고", "confidence": "high",
                            "display_url_visible": "smartstore.naver.com/brand-b/event"}]}}
    inputs = {"brands": [{"id": "own", "name": "X", "sources": {"official_urls": ["https://changed.example"]}}],
              "versions": [{"run_id": "saved", "source": "search_capture", "inputs": {"brands": brands}}]}
    original = copy.deepcopy(row)
    filtered = project_view.search_ad_rows([row], inputs)
    assert [r["브랜드"] for r in filtered] == ["A", "B"]
    assert filtered[1]["신뢰도"] == "high" and row == original
    result = {"schema_version": 6, "records": [row], "inputs": inputs, "parts": {}}
    assert facts_report.tables_for(result)["09_검색광고문구"] == filtered
    markup = facts_report.report_html({}, result)
    assert "다른 광고" not in markup and "A 광고" in markup
    assert len(facts_report.tables_for(result)["26_검색광고원문"]) == 6


def test_compressed_image_budget_is_configurable_and_original_is_unchanged(monkeypatch):
    source = BytesIO()
    Image.new("RGB", (3200, 1800), "#abcdef").save(source, "PNG")
    original = source.getvalue()
    asset = save_bytes(original, "png", "https://example.test/image")
    preview = compress(original)
    with Image.open(BytesIO(preview)) as image:
        assert max(image.size) <= 1600 and image.format == "JPEG"
    assert len(preview) <= 220_000 and read_bytes(asset) == original
    monkeypatch.setenv("ADETECT_HTML_IMAGE_MAX_MB", "0.001")
    assert "용량 한도" in visual_report.Images().render({"assets": [asset]})
    monkeypatch.setenv("ADETECT_HTML_IMAGE_MAX_MB", "40")
    assert "data:image/jpeg;base64," in visual_report.Images().render({"assets": [asset], "format": "video"})
    assert compress(b"not an image") is None


def test_video_collects_supplied_thumbnail_without_extra_api(monkeypatch):
    calls = []
    def fetch(url, maximum=None):
        calls.append(url)
        return {"filename": "preview.jpg" if url.endswith("jpg") else "original.mp4", "source_url": url}
    monkeypatch.setattr(settings, "SAMPLE_MODE", False)
    monkeypatch.setattr("core.evidence_store.fetch_asset", fetch)
    monkeypatch.setattr("core.scrapers.ad_library.fetch_meta_ads_detail", lambda *a, **k: [{"ad_id": "v", "format": "video",
        "image_url": "https://media.test/v.mp4", "thumbnail_url": "https://media.test/v.jpg"}])
    brand = {"id": "own", "name": "A"}
    ad = project_sources._social("meta", brand, "confirmed")["records"][0]
    assert calls == ["https://media.test/v.jpg", "https://media.test/v.mp4"]
    assert ad["assets"][0]["role"] == "썸네일" and ad["thumbnail_url"].endswith("jpg")
    monkeypatch.setattr("core.scrapers.youtube.fetch_youtube", lambda *a: {"status": "available", "source_url": "https://youtube.com/@a",
        "recent_content": [{"video_id": "id", "title": "영상", "thumbnail_url": "https://media.test/y.jpg"}]})
    video = project_sources._social("youtube", brand, "@a")["records"][1]
    assert video["assets"][0]["role"] == "썸네일"
    calls.clear()
    assert project_sources._thumbnail(None) == ([], []) and not calls


def test_news_hierarchy_compact_report_and_closed_details():
    def article(i, brand):
        return {"id": str(i), "kind": "뉴스", "title": f"시장 프로모션 {i}개 발표", "text": "발췌는 Excel에서만",
                "excerpt": "발췌는 Excel에서만", "found_brands": [brand] if brand else [], "published_at": "2026-09-29",
                "source_url": f"https://news.example/{i}"}
    rows = [article(i, "A") for i in range(7)] + [article(8, None)]
    sections = news_sections(rows)
    assert len(sections) == 1 and [s["title"] for s in sections[0]["subjects"]] == ["A", "시장·기타"]
    structures = utm.structure_rows([utm.parse("https://a.example/?utm_source=meta&utm_medium=paid", "A", "fixture")])
    rows += [{"kind": "Instagram 게시물", "brand": "A", "text": "Instagram 본문", "source_url": "https://instagram.com/p/observed"}]
    result = {"schema_version": 6, "records": rows, "inputs": {}, "parts": {}, "utm_structures": structures}
    markup = facts_report.report_html({}, result)
    class Details(HTMLParser):
        opened = []
        def handle_starttag(self, tag, attrs):
            if tag == "details" and "open" in dict(attrs): self.opened.append(attrs)
    parser = Details()
    parser.feed(markup)
    assert not parser.opened and "나머지 제목 2개" in markup
    assert "발췌는 Excel에서만" not in markup and "Instagram 본문" not in markup
    assert "https://instagram.com/p/observed" in markup
    assert "추정 구조" not in markup and "근거 URL 수" not in markup and "전체 관측값·근거 URL·표본 한계" not in markup
    assert 'href="#top"' in markup and 'id="top"' in markup
    assert [r["브랜드"] for r in utm.display_structures(structures)] == ["A", ""]
    assert facts_report.tables_for(result)["07_뉴스"][0]["원문"] == "발췌는 Excel에서만"


def test_previous_results_still_use_readable_export():
    for version in (4, 5, 6):
        markup = facts_report.report_html({}, {"schema_version": version, "records": [], "parts": {}, "inputs": {}})
        assert "최상단으로" in markup
