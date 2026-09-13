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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
# 실제 Meta Ads Library 스크래핑 액터 — §4 레퍼런스(adetect_reference/scrapers/fetch_ads.py)에서
# 실사용 검증된 액터. rental 액터라 최초 실행 시 별도 구독료가 부과될 수 있다(§10).
APIFY_META_ADS_ACTOR = os.getenv("APIFY_META_ADS_ACTOR", "curious_coder/facebook-ads-library-scraper")

# ── 서비스별 목업 플래그 ──────────────────────────────────────────────────
# 기존에는 4개 키가 "전부" 채워져야만 목업을 벗어나는 단일 USE_MOCK_DATA만 있었습니다.
# 이 경우 예를 들어 Naver 키만 채우고 Apify/Gemini를 아직 안 채웠다면, Apify/Gemini와
# 무관한 Naver 전용 함수까지 전부 NotImplementedError로 죽어버리는 문제가 있었습니다.
# 서비스별로 필요한 키가 채워졌는지만 독립적으로 판단하도록 분리합니다.
NAVER_DATALAB_MOCK = not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)  # 검색어트렌드 — naveropenapi.apigw.ntruss.com/datalab/v1/search
# '검색'(뉴스 등)은 NAVER API HUB(NCP)에서 데이터랩과 같은 애플리케이션에 추가하는 별도 상품이지만
# Client ID/Secret은 공유합니다. 같은 크리덴셜이 있다는 것은 그 애플리케이션에 최소 하나의 상품은
# 등록됐다는 뜻이므로 함께 실연동으로 전환합니다 — '검색' 상품 자체를 안 붙였다면 호출이 403으로
# 실패하고 §11 정책에 따라 부분/전체 실패로 처리될 뿐 앱이 죽지는 않습니다.
NAVER_SEARCH_MOCK = not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)
# 검색광고(광고주센터) 키워드도구 — DataLab과 별도 계정/인증(HMAC), §21-10. 연관검색어 + 절대 검색량.
NAVER_AD_MOCK = not (NAVER_AD_API_KEY and NAVER_AD_SECRET_KEY and NAVER_AD_CUSTOMER_ID)
APIFY_MOCK = not APIFY_API_TOKEN
GEMINI_MOCK = not GEMINI_API_KEY
# Playwright 브랜드 홈페이지 크롤링은 키가 아니라 구현 여부의 문제라 항상 목업입니다.
BRAND_SITE_MOCK = True

# 하위 호환용 — "무엇 하나라도 목업이면 True". 신규 코드는 위의 서비스별 플래그를 사용하세요.
USE_MOCK_DATA = NAVER_DATALAB_MOCK or NAVER_SEARCH_MOCK or NAVER_AD_MOCK or APIFY_MOCK or GEMINI_MOCK or BRAND_SITE_MOCK

APP_NAME = "ADetect"
DB_PATH = os.getenv("ADETECT_DB_PATH", "storage/adetect.db")
