"""테스트는 로컬 .env에 실제 키가 있어도 항상 목업 데이터로 결정론적으로 동작해야 합니다.

config.settings가 처음 import되기 전에 관련 환경변수를 빈 문자열로 고정해, 그 안의
load_dotenv()(override=False)가 .env의 실제 값으로 덮어쓰지 못하게 막습니다. 그렇지 않으면
개발자가 로컬에 실제 API 키를 채워둔 상태에서 테스트를 돌릴 때마다 실제 네트워크 호출이
발생해 테스트가 키 유효성/네트워크 상태에 따라 흔들리게 됩니다.
"""
import os

for _key in (
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
    "NAVER_AD_API_KEY",
    "NAVER_AD_SECRET_KEY",
    "NAVER_AD_CUSTOMER_ID",
    "APIFY_API_TOKEN",
    "GEMINI_API_KEY",
    "YOUTUBE_API_KEY",
):
    os.environ[_key] = ""


import pytest

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    import database.db as db
    from config import settings
    monkeypatch.setattr(settings,"SAMPLE_MODE",False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADETECT_EXPORT_DIR",str(tmp_path / "exports"))
    yield
    from core.jobs import _jobs
    for job in list(_jobs.values()):
        job["future"].result(timeout=20)
