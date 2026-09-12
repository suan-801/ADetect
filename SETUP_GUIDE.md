# SETUP_GUIDE

API 키 발급 및 환경 준비 가이드입니다. 이 문서가 단일 기준(single source of truth)이며,
다른 문서/스크립트는 이 내용을 복붙하지 않고 그때그때 이 문서를 참조합니다 (PRD §23).

## 지금 당장은 필요 없습니다

이 저장소는 **API 키가 하나도 없어도** `streamlit run app.py`로 전체 화면(홈/분석하기/이력관리/설정)이
목업(mock) 데이터로 동작하도록 만들어져 있습니다. `config/settings.py`의 `USE_MOCK_DATA` 플래그가
키 유무에 따라 자동으로 켜지고 꺼집니다. 실제 데이터 연동이 필요해지는 시점에 아래 절차를 따르세요.

## 1. .env 파일 준비

```bash
cp .env.example .env
```

`.env`는 git에 올라가지 않습니다(.gitignore). 절대 커밋하지 마세요.

## 2. 네이버 오픈API (DataLab 검색량 / 뉴스 검색)

1. https://developers.naver.com 접속 → 로그인 → "Application 등록"
2. 사용 API: "검색" + "데이터랩(검색어트렌드)" 체크
3. 발급받은 Client ID / Client Secret을 `.env`의 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`에 입력

**왜 이 방식인가**: DataLab 통합검색어트렌드 API는 `keywordGroups`로 브랜드명 표기 변형을 한 번에
합산 조회할 수 있어(PRD §7-9), 표기가 여러 개인 브랜드명 검색량 집계에 필수입니다.

## 3. 네이버 검색광고(키워드도구) API — DataLab과 별도 계정 (PRD §21-10)

1. https://searchad.naver.com 광고주 계정 생성 (광고 집행 목적이 아니어도 계정 자체는 필요)
2. [도구] → [API 사용 관리]에서 License Key(=API Key) / Secret Key 발급, Customer ID 확인
3. `.env`의 `NAVER_AD_API_KEY` / `NAVER_AD_SECRET_KEY` / `NAVER_AD_CUSTOMER_ID`에 입력

**왜 별도 계정인가**: DataLab은 상대 검색지수만 주기 때문에, 절대 검색량(최근 30일 PC/모바일)은
이 API로만 얻을 수 있습니다. 요청마다 HMAC 서명이 필요해 DataLab보다 연동이 한 단계 더 복잡합니다.

## 4. Apify (Meta Ads Library / Instagram 프로필)

1. https://apify.com 가입 → Settings → Integrations에서 API Token 발급
2. `.env`의 `APIFY_API_TOKEN`에 입력
3. 사용 액터: `facebook-ads-library-scraper` (광고 소재), Instagram 프로필 스크래퍼 액터(팀 내 확정 필요)

**왜 프록시를 안 쓰는가**: Apify가 자체 프록시/큐로 스크래핑을 대행하므로 우리 쪽에서 별도
Residential Proxy를 구매하지 않습니다 (PRD §21-1).

## 5. Google Gemini (멀티모달 분석)

1. https://aistudio.google.com 에서 API 키 발급
2. `.env`의 `GEMINI_API_KEY`에 입력

## 시크릿 관리 원칙 (PRD §19-2)

- API 키는 `.env` 또는 Secret Manager에서만 관리 — 코드/커밋/로그에 절대 노출 금지
- 로그에 키가 출력되지 않도록 마스킹
- 산출물(HTML/Excel/ZIP)에 키가 포함되지 않도록 내보내기 직전 검사
