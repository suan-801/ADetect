# 2026-09-26 설정 변경 안내 (아래 과거 설명보다 우선)

새 자료 수집 화면은 유료 기능 기본 ON입니다. .env에 Apify/Gemini 키가 없으면 '토큰 부족. 개발자에게 문의해주세요'를 표시하고 해당 소스를 미수집으로 남깁니다. 입력 확인 화면에서는 API를 호출하지 않습니다. SAMPLE은 ADETECT_SAMPLE_MODE=true로 명시해야 하며, 실사용 중 키 누락을 목업으로 대체하지 않습니다.

개인 PC 서버 주소는 127.0.0.1입니다. SQLite와 storage/exports, storage/evidence를 같은 PC에 저장합니다. 기본 보관 한도와 백업 방법은 README를 참고하세요. 다운로드 요청 기록은 파일 생성과 별도이며 실제 디스크 저장 완료를 의미하지 않습니다.

네이버 검색 추이는 NAVER API HUB에서 완료된 최근 36개월을 월간 단위로 요청합니다. 검색어에 따라 일부 월만 제공될 수 있으며 그 달들을 0으로 바꾸지 않습니다. 실제 값이 없는 경우 피크·저점 확정을 하지 않습니다.

---

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


## 2026-09-26 추가 설정

- YouTube 선택 수집: Google Cloud에서 YouTube Data API v3를 활성화하고 `YOUTUBE_API_KEY`를 설정합니다.
  STEP 1에서 공식 채널 ID(`UC...`) 또는 `@handle`을 입력합니다. 계정을 브랜드명으로 추측하지 않습니다.
- Instagram: STEP 1에 공식 handle/URL을 입력하거나 공식 홈페이지의 Instagram 링크를 사용합니다.
  `apify/instagram-profile-scraper`를 호출하므로 Apify 권한과 과금 설정을 확인합니다.
- 네이버 캡처: `python -m playwright install chromium` 설치가 필요합니다. 차단·DOM 미감지는 미확인으로 기록합니다.
- 명시적 오프라인 분석: `ADETECT_SAMPLE_MODE=true`를 설정한 뒤 앱을 재시작합니다.
- 파일 보관: `ADETECT_EXPORT_MAX_RUNS=20`, `ADETECT_EXPORT_MAX_BYTES=5368709120`이 기본입니다.

구현 근거 문서: [Naver DataLab](https://developers.naver.com/docs/serviceapi/datalab/search/search.md),
[Instagram 입력](https://apify.com/apify/instagram-profile-scraper/input-schema),
[YouTube 채널 조회](https://developers.google.com/youtube/v3/docs/channels/list),
[Playwright Page](https://playwright.dev/python/docs/api/class-page).
키 설정 여부가 연동 성공을 보장하지 않으며 실제 권한과 사이트별 응답은 별도 수용 검증이 필요합니다.
