from datetime import date
from io import BytesIO
from zipfile import ZipFile
from openpyxl import load_workbook
from core.collection import run_stage, relevance, TOKEN_MESSAGE
from core.scrapers.search_history import period_bounds,summarize_history


def test_calendar_month_bounds_and_missing_data():
    assert period_bounds(today=date(2026,9,26))==("2023-01-01","2026-08-31")
    assert period_bounds(today=date(2024,3,5))[1]=="2024-02-29"
    data={"start":"2023-01-01","end":"2025-12-31","rows":[{"date":"2023-01-01","search_index":0},{"date":"2023-02-01","search_index":20}]}
    result=summarize_history(data)
    assert result["observed_months"]==2
    assert result["peak_months"]==[]
    assert result["monthly"][0]["평균 검색지수"]==0
    assert result["yearly"][0]["저점 월"]=="1"


def test_paid_missing_does_not_call_apify_or_return_sample(monkeypatch):
    from core.scrapers import ad_library
    monkeypatch.setattr(ad_library,"fetch_meta_ads_detail",lambda *a,**k:(_ for _ in ()).throw(AssertionError("API called")))
    result=run_stage("creative",{"brand_name":"A","sources":{"A":{"meta_page":"https://www.facebook.com/ads/library/?view_all_page_id=123"}}})
    assert TOKEN_MESSAGE in str(result["parts"])
    assert not result["records"] and not result["sample_sources"]


def test_campaign_relevance_exclusions_and_exact_landing():
    s={"brand_name":"A","campaign":"채용","include_terms":["TM사관학교"],"exclude_terms":["보험 가입"],"sources":{"A":{"detail_url":"https://example.com/recruit#!/"}}}
    assert relevance({"text":"TM사관학교 모집"},s)[0]=="포함"
    assert relevance({"text":"보험 가입 TM사관학교"},s)[0]=="제외"
    assert relevance({"text":"","landing_url":"https://example.com/recruit?utm_source=fb#!/"},s)[0]=="포함"
    assert relevance({"text":"","landing_url":"https://example.com/insurance"},s)[0]=="확인 필요"


def test_retry_only_failed_sources(monkeypatch):
    from config import settings
    from core.scrapers import search_history
    monkeypatch.setattr(settings,"SAMPLE_MODE",True)
    s={"brand_name":"A","brand_keywords":["A"],"general_keywords":[],"collection_options":{"news":False}}
    first=run_stage("market",s)
    s["market_result"]=first
    monkeypatch.setattr(search_history,"fetch_history",lambda *a,**k:(_ for _ in ()).throw(AssertionError("must reuse")))
    second=run_stage("market",s,True)
    assert second["parts"]["trend:A"]==first["parts"]["trend:A"]


def test_download_requests_persist_without_render_side_effect():
    from core.exporters.artifact_store import save_artifact,read_artifact,record_download,download_events
    aid=save_artifact("run","market","html","hello")
    assert read_artifact(aid,touch=False)==b"hello"
    assert download_events(aid)==[]
    record_download(aid)
    assert len(download_events(aid))==1
    record_download(aid)
    assert len(download_events(aid))==2


def test_missing_paid_token_ui_defaults_on_without_api_calls():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    page=Path(__file__).resolve().parents[1]/"app_pages/2_analyze.py"
    at=AppTest.from_file(str(page)).run()
    at.text_input(key="new_brand").set_value("A").run()
    at.button(key="new_project").click().run()
    for label in ("초안 준비하고 다음", "자사 정보 확인하고 다음", "선택한 경쟁사 확인 / 건너뛰기"):
        next(b for b in at.button if b.label == label).click().run()
    next(c for c in at.checkbox if c.label == "브랜드·검색어·주소 후보를 확인했습니다").check()
    next(b for b in at.button if b.label == "확인하고 프로젝트 만들기").click().run()
    assert not at.exception
    assert at.toggle(key="collection_paid").value is True


def test_fact_package_contains_originals_and_safe_excel(tmp_path,monkeypatch):
    from core.evidence_store import save_bytes
    from core.exporters.facts_report import package
    monkeypatch.setenv("ADETECT_EVIDENCE_DIR",str(tmp_path/"evidence"))
    asset=save_bytes(b"image test","png","https://example.com")
    row={"id":"a","kind":"광고","brand":"A","source_url":"https://example.com","text":"=1+1","collected_at":"now","assets":[asset]}
    data=package({"brand_name":"A"},{"records":[row],"parts":{}})
    with ZipFile(BytesIO(data)) as z:
        entry = next(name for name in z.namelist() if name.startswith("originals/") and name.endswith(asset["filename"]))
        assert z.read(entry)==b"image test"
        wb=load_workbook(BytesIO(z.read("자료.xlsx")))
        assert wb["02_자료목록"]["G2"].data_type=="s"
