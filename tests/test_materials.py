from core.materials import table_row, prioritized
from core.collection import record, run_stage
from config import settings


def test_datalab_sends_aliases_as_one_group(monkeypatch):
    from core.scrapers import search_history
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"results": [{"data": [{"period": "2026-08-01", "ratio": 100}]}]}
    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return Response()
    monkeypatch.setattr(settings, "NAVER_DATALAB_MOCK", False)
    monkeypatch.setattr(search_history.requests, "post", post)
    result = search_history.fetch_history("브랜드 묶음", keywords=["한샘", "한셈"])
    assert calls[0]["keywordGroups"] == [{"groupName": "브랜드 묶음", "keywords": ["한샘", "한셈"]}]
    assert result["grouped"] and result["keywords"] == ["한샘", "한셈"]
    import pytest
    with pytest.raises(ValueError):
        search_history.fetch_history("too many", keywords=[str(n) for n in range(21)])


def test_news_only_does_not_call_trend_or_volume(monkeypatch):
    from core.scrapers import search_history, naver_api, naver_ad_api
    monkeypatch.setattr(settings, "SAMPLE_MODE", True)
    def forbidden(*args, **kwargs): raise AssertionError("Unselected source was called")
    monkeypatch.setattr(search_history, "fetch_history", forbidden)
    monkeypatch.setattr(naver_ad_api, "fetch_keyword_stats", forbidden)
    calls = []
    def news(keyword, **kwargs):
        calls.append(keyword)
        return []
    monkeypatch.setattr(naver_api, "get_news", news)
    result = run_stage("market", {"brand_name":"한샘", "brand_keywords":["한샘","한셈"], "keyword_mode":"brand_group", "news_keywords":["한샘 실적"], "source_selection":["news"]})
    assert calls == ["한샘 실적"]
    assert all(p["state"] == "완료" for p in result["parts"].values())
    assert set(result["parts"]) == {"news:한샘 실적"}


def test_social_metrics_and_no_internal_ids_in_tables():
    from core.exporters.facts_report import report_tables
    ig = record("Instagram", "한샘", "https://example.com", "계정", followers=1234, post_count=None)
    yt = record("YouTube", "한샘", "https://example.com/yt", "채널", subscribers=None, videos=10)
    assert table_row(ig, True)["팔로워 수"] == "1234"
    assert table_row(yt, True)["구독자 수"] == "미제공 / 비공개"
    tables = report_tables({"schema_version":3,"records":[ig,yt],"parts":{}})
    assert tables["14_Instagram"][0]["팔로워 수"] == "1234" and "다운로드" not in tables["14_Instagram"][0]
    assert all("자료ID" not in row for rows in tables.values() for row in rows)


def test_rows_sort_by_kind_then_newest_without_review_priority():
    rows = [{"kind":"뉴스","review":"확인 필요","published_at":"Sun, 27 Sep 2026 09:00:00 +0900"},
            {"kind":"뉴스","review":"포함","published_at":"2025-01-01"},
            {"kind":"뉴스","published_at":"2026-09-28T00:00:00Z"}]
    assert prioritized(rows) == [rows[2], rows[0], rows[1]]
