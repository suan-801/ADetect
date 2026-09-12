"""환경 설정 로딩. (.env 값이 비어 있으면 자동으로 목업 모드로 동작)

PRD §21-8·§21-10: 네이버 DataLab/뉴스 API와 네이버 검색광고(키워드도구) API는
발급 경로가 서로 다른 별도 계정이므로 키를 따로 관리합니다.
"""
import os

from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

NAVER_AD_API_KEY = os.getenv("NAVER_AD_API_KEY", "")
NAVER_AD_SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY", "")
NAVER_AD_CUSTOMER_ID = os.getenv("NAVER_AD_CUSTOMER_ID", "")

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 하나라도 핵심 키가 비어 있으면 목업 데이터로 동작합니다.
# 실제 연동을 붙인 뒤에는 이 값이 자동으로 False가 되어 real 함수 경로를 타게 됩니다.
USE_MOCK_DATA = not all([NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, APIFY_API_TOKEN, GEMINI_API_KEY])

APP_NAME = "ADetect"
DB_PATH = os.getenv("ADETECT_DB_PATH", "storage/adetect.db")
