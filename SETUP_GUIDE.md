# SETUP_GUIDE

API 키 발급 및 환경 준비 가이드입니다. 이 문서가 단일 기준(single source of truth)이며,
다른 문서/스크립트는 이 내용을 복붙하지 않고 그때그때 이 문서를 참조합니다 (PRD §23).

## 이미 발급받은 키가 있다면 — 빠른 참고표

다른 사람에게 값을 전달받았거나 이미 발급된 키가 있다면, 아래처럼 `.env`에 넣으면 됩니다
(발급 자체가 필요하면 각 항목의 상세 절차로 건너뛰세요).

| 받은 값 | `.env` 변수명 | 비고 |
|---|---|---|
| 네이버 오픈API Client ID / Secret | `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 아래 "2." 항목 참고 |
| 네이버 검색광고 License Key / Secret Key / Customer ID | `NAVER_AD_API_KEY` / `NAVER_AD_SECRET_KEY` / `NAVER_AD_CUSTOMER_ID` | 아래 "3." 항목 참고 — DataLab과 별개 계정 |
| Apify API Token | `APIFY_API_TOKEN` | 아래 "4." 항목 참고 |
| Google Gemini API Key | `GEMINI_API_KEY` | 아래 "5." 항목 참고 |

절차:

```bash
cp .env.example .env   # 아직 .env가 없다면
```

`.env` 파일을 열어 해당 줄에 값을 붙여넣고 저장하면 끝입니다. 키를 채운 서비스만 자동으로
실연동으로 전환되고(`config/settings.py`의 서비스별 `_MOCK` 플래그), 나머지는 계속 목업으로
동작합니다 — 4개를 한 번에 다 채울 필요 없습니다. `GEMINI_MODEL`/`APIFY_META_ADS_ACTOR`/
`ADETECT_DB_PATH`는 선택 항목이며 비워두면 기본값을 씁니다(`.env.example` 하단 주석 참고).

`.env`는 `.gitignore`에 등록돼 있어 커밋되지 않습니다 — 절대 직접 커밋하거나 코드/로그에
값을 그대로 출력하지 마세요(맨 아래 "시크릿 관리 원칙" 참고).

## 지금 당장은 필요 없습니다

이 저장소는 **API 키가 하나도 없어도** `streamlit run app.py`로 전체 화면(홈/분석하기/이력관리/설정)이
목업(mock) 데이터로 동작하도록 만들어져 있습니다. `config/settings.py`의 `USE_MOCK_DATA` 플래그가
키 유무에 따라 자동으로 켜지고 꺼집니다. 실제 데이터 연동이 필요해지는 시점에 아래 절차를 따르세요.

## 1. .env 파일 준비

```bash
cp .env.example .env
```

`.env`는 git에 올라가지 않습니다(.gitignore). 절대 커밋하지 마세요.

## 2. 네이버 오픈API (DataLab 검색량 / 뉴스 검색) — NAVER Cloud Platform 콘솔 (PRD §21-8)

★ developers.naver.com(구 네이버 오픈API 개발자센터)은 2027-06-30 종료 예정이라, 신규 등록은
**NAVER Cloud Platform(NCP) 콘솔**에서 합니다.

1. https://console.ncloud.com 접속 → 로그인 → NAVER API HUB → Application 등록
2. 사용 API: **"NAVER 검색 · 뉴스"** + **"Data Lab · 검색어트렌드"** 둘 다 체크 (쇼핑인사이트는 아직 사용처가 없어 선택)
3. 발급받은 Client ID / Client Secret을 `.env`의 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`에 입력

**왜 이 방식인가**: DataLab 검색어트렌드 API는 `keywordGroups`로 브랜드명 표기 변형을 한 번에
합산 조회할 수 있어(PRD §7-9), 표기가 여러 개인 브랜드명 검색량 집계에 필수입니다.

**실제 호출 엔드포인트가 흔한 예제와 다릅니다**: 검색어트렌드는
`POST https://naverapihub.apigw.ntruss.com/search-trend/v1/search`, 뉴스 검색은
`GET https://naverapihub.apigw.ntruss.com/search/v1/news`이며, 인증 헤더는
`X-NCP-APIGW-API-KEY-ID`(Client ID) / `X-NCP-APIGW-API-KEY`(Client Secret)입니다. 인터넷에 많이
도는 예제의 `openapi.naver.com` + `X-Naver-Client-Id` 방식은 developers.naver.com 시절 것이라
NCP 콘솔에서 발급받은 키로는 401이 납니다(2026-09-13 실계정으로 직접 확인).

## 3. 네이버 검색광고(키워드도구) API — DataLab과 별도 계정 (PRD §21-10)

1. https://searchad.naver.com 광고주 계정 생성 (광고 집행 목적이 아니어도 계정 자체는 필요)
2. [도구] → [API 사용 관리]에서 License Key(=API Key) / Secret Key 발급, Customer ID 확인
3. `.env`의 `NAVER_AD_API_KEY` / `NAVER_AD_SECRET_KEY` / `NAVER_AD_CUSTOMER_ID`에 입력

**왜 별도 계정인가**: DataLab은 상대 검색지수만 주기 때문에, 절대 검색량(최근 30일 PC/모바일)은
이 API로만 얻을 수 있습니다. 요청마다 HMAC 서명이 필요해 DataLab보다 연동이 한 단계 더 복잡합니다.

## 4. Apify (Meta Ads Library / Instagram 프로필)

1. https://apify.com 가입 → Settings → Integrations에서 API Token 발급
2. `.env`의 `APIFY_API_TOKEN`에 입력
3. 사용 액터: `curious_coder/facebook-ads-library-scraper` (Meta Ads Library, 실연동 확인됨 — §21-11. 광고 1건당 $0.00075 과금, 별도 구독료 없음). Instagram 프로필은 `apify/instagram-profile-scraper` 액터가 있지만 브랜드명→handle 해석 문제로 아직 목업(§7-10)

**왜 프록시를 안 쓰는가**: Apify가 자체 프록시/큐로 스크래핑을 대행하므로 우리 쪽에서 별도
Residential Proxy를 구매하지 않습니다 (PRD §21-1).

## 5. Google Gemini (멀티모달 분석)

1. https://aistudio.google.com 에서 API 키 발급
2. `.env`의 `GEMINI_API_KEY`에 입력

## 시크릿 관리 원칙 (PRD §19-2)

- API 키는 `.env` 또는 Secret Manager에서만 관리 — 코드/커밋/로그에 절대 노출 금지
- 로그에 키가 출력되지 않도록 마스킹
- 산출물(HTML/Excel/ZIP)에 키가 포함되지 않도록 내보내기 직전 검사
