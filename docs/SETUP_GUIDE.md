# SETUP_GUIDE — API 설정·키 발급·확인·오류 해결

키는 프로젝트 폴더의 `.env`에만 넣습니다(`.gitignore` 등록). 코드·커밋·스크린샷·보고서에 키를 넣지 마세요.
앱은 키 값을 화면·산출물에 표시하지 않고, 파일 생성 직전에 키가 섞였는지 검사합니다.

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env`를 고친 뒤에는 앱을 다시 실행합니다. 설정 화면의 'API 연동 상태'는 키가 **입력되어 있는지**만 보여줍니다. 권한·잔액·실제 수집 성공 여부는 수집 결과에서 확인합니다.

신규 프로젝트의 AI 초안은 `GEMINI_API_KEY`가 있을 때 사용자가 다음 버튼으로 요청합니다. 검색 근거가 있는 후보도 공식 여부는 직접 확인해야 합니다. 키 없음·실패 시 직접 입력으로 계속 진행할 수 있습니다.

## 자료 종류별 필요한 키

| 자료 | 변수 | 비용 |
|---|---|---|
| 검색 관심도 추이, 관련 뉴스 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 무료(호출량 제한 있음) |
| 월간 검색량 | `NAVER_AD_API_KEY`, `NAVER_AD_SECRET_KEY`, `NAVER_AD_CUSTOMER_ID` | 무료 |
| Meta 광고 소재 | `APIFY_API_TOKEN` (+ 선택 `APIFY_META_ADS_ACTOR`) | 유료 (Apify 사용량 과금) |
| Instagram | `APIFY_API_TOKEN` | 유료 (Apify 사용량 과금) |
| 검색 화면 AI 보완 판독 | `GEMINI_API_KEY` (+ 선택 `GEMINI_MODEL`) | 유료 (Gemini 사용량 과금) |
| YouTube | `YOUTUBE_API_KEY` | 무료(할당량 제한) |
| 공식 페이지, 네이버 검색 화면 | 키 없음 — Playwright Chromium 설치 필요 | 무료 |

키가 없는 자료는 수집 탭에서 '선택 불가: API 키 미설정'으로 표시되고 요청하지 않습니다. 유료 자료(Apify·Gemini) 키가 없으면 `토큰 부족. 개발자에게 문의해주세요`가 표시됩니다. 키가 없다는 이유로 가상 자료를 대신 쓰지 않습니다(SAMPLE은 `ADETECT_SAMPLE_MODE=true`로 명시할 때만).

## 1. 네이버 API HUB (검색 추이·뉴스)

1. https://console.ncloud.com → NAVER API HUB → Application 등록
2. 사용 API로 **Data Lab · 검색어트렌드**와 **NAVER 검색 · 뉴스**를 모두 추가
3. 발급된 Client ID / Client Secret을 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`에 입력

앱이 쓰는 주소와 인증 헤더(흔한 예제의 `openapi.naver.com` 방식과 다름):
- 검색어트렌드: `POST https://naverapihub.apigw.ntruss.com/search-trend/v1/search`
- 뉴스: `GET https://naverapihub.apigw.ntruss.com/search/v1/news`
- 헤더: `X-NCP-APIGW-API-KEY-ID`(Client ID), `X-NCP-APIGW-API-KEY`(Client Secret)

검색 추이는 자사·경쟁사 검색어 묶음을 한 요청(최대 5개 주제, 주제당 최대 20개 검색어)으로 보냅니다.

## 2. 네이버 검색광고 API (월간 검색량)

데이터랩과 별도 계정입니다.
1. https://searchad.naver.com 광고주 계정 생성(광고 집행 없이도 가능)
2. 도구 → API 사용 관리에서 API License Key / Secret Key 발급, Customer ID 확인
3. `NAVER_AD_API_KEY` / `NAVER_AD_SECRET_KEY` / `NAVER_AD_CUSTOMER_ID`에 입력

요청마다 HMAC 서명을 붙여 `https://api.naver.com/keywordstool`을 호출합니다. 값이 `< 10`이면 그대로 보존하며 0으로 바꾸지 않습니다.

## 3. Apify (Meta 광고·Instagram, 유료)

1. https://apify.com → Settings → Integrations에서 API Token 발급 → `APIFY_API_TOKEN`
2. 사용 액터
   - Meta 광고: `APIFY_META_ADS_ACTOR` (기본 `curious_coder/facebook-ads-library-scraper`). 대여형 액터는 별도 요금이 붙을 수 있으니 Apify 콘솔에서 확인하세요.
   - Instagram: `apify/instagram-profile-scraper` (코드에 고정)
3. 프로젝트 설정에 입력한 계정·페이지만 조회합니다.
   - Instagram: `@handle` 또는 `https://www.instagram.com/handle`
   - Meta: facebook.com/ads/library에서 브랜드 페이지의 '모든 광고 보기' 주소 (`view_all_page_id=숫자` 포함)

유료 기능 토글이 OFF이면 호출하지 않습니다.

## 4. Google Gemini (설정 초안·광고 판독·뉴스 근거 요약, 유료)

1. https://aistudio.google.com 에서 API 키 발급 → `GEMINI_API_KEY`
2. 모델은 `GEMINI_MODEL`(기본 `gemini-flash-latest`)

광고 판독 기능에서는 직접 추출이 부족한 검색 광고 영역 캡처만 판독합니다. 수집 탭의 '광고 영역 AI 보완 판독' 체크를 끄거나 유료 기능을 끄면 호출하지 않습니다.

## 5. YouTube Data API v3

1. Google Cloud 콘솔에서 YouTube Data API v3 활성화 → API 키 발급 → `YOUTUBE_API_KEY`
2. 프로젝트 설정의 공식 YouTube 채널에 `UC`로 시작하는 채널 ID 또는 `@handle` 입력

## 6. Playwright (공식 페이지·검색 화면 캡처)

```powershell
.venv\Scripts\python.exe -m playwright install chromium
```

## 7. 저장·실행 관련 변수 (선택)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `ADETECT_SAMPLE_MODE` | `false` | `true`면 외부 요청 없이 가상 자료 (화면에 SAMPLE 표시) |
| `ADETECT_DB_PATH` | `storage/adetect.db` | SQLite 위치 |
| `ADETECT_EXPORT_DIR` | `storage/exports` | HTML/Excel/ZIP |
| `ADETECT_EXPORT_MAX_RUNS` / `ADETECT_EXPORT_MAX_BYTES` | 20 / 5GB | 산출물 보관 한도 |
| `ADETECT_EVIDENCE_DIR` / `ADETECT_EVIDENCE_MAX_BYTES` | `storage/evidence` / 5GB | 원본 파일 |
| `ADETECT_BACKUP_DIR` | `storage/backups` | DB 백업 |
| `ADETECT_STORAGE_MAX_BYTES` / `ADETECT_DB_MAX_BYTES` | 5GB / 500MB | 저장 공간 사용률 기준 |

`ADETECT_DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ADETECT_STORAGE_BUCKET`은 검증되지 않은 원격 저장 코드용입니다. 설정하면 앱이 원격 모드로 바뀌므로 로컬 사용에서는 비워 둡니다.

## 8. 키 동작 확인

1. 설정 화면에서 필요한 키가 '키 설정됨'인지 확인
2. 테스트용 프로젝트를 만들고 무료 자료(검색 추이·월간 검색량·관련 뉴스)만 선택해 수집
3. 자료 수집 탭의 '최근 수집에서 실패·건너뜀' 목록과 결과 탭의 상태 문구 확인
4. 유료 자료는 필요한 브랜드 하나만 선택해 소량으로 먼저 확인

운영 DB와 분리하려면 README의 SAMPLE 실행처럼 `ADETECT_DB_PATH` 등을 별도 경로로 지정해 실행합니다.

## 9. 오류 해결

| 화면 문구 | 의미 / 조치 |
|---|---|
| `토큰 부족. 개발자에게 문의해주세요` | 유료 API 키 없음 또는 인증·잔액 문제(401/402 등). 키와 계정 잔액 확인 |
| `수집 실패 — 연결 상태·권한·수집 대상 주소를 확인해주세요.` | 네트워크·방화벽·권한·주소 문제. 토큰 부족과 다름 |
| `선택 불가: API 키 미설정` | 해당 자료의 키가 `.env`에 없음 |
| `선택 불가: 입력한 계정·페이지 없음` | 프로젝트 설정에 계정·페이지가 없음 |
| `view_all_page_id가 있는 페이지별 Ads Library URL을 입력하세요.` | Meta 주소 형식 확인 |
| `UC로 시작하는 채널 ID 또는 @handle을 입력하세요.` | YouTube 채널 입력 형식 확인 |
| 검색 화면 `판독 불가` | 캡처 실패·차단·광고 영역 식별 실패. Chromium 설치 확인 후 재수집. 광고 미노출이 아님 |
| 저장 공간 상한 | 설정 > 저장 공간 관리에서 정리 |
| 계속 SAMPLE 자료만 나옴 | 실행 창에 `ADETECT_SAMPLE_MODE=true`가 남아 있음. 새 PowerShell 창에서 실행 |

## 10. AI 설정 초안·뉴스 근거 요약·맞춤 통계 검색

세 기능 모두 `.env`의 `GEMINI_API_KEY`와 `GEMINI_MODEL`을 사용합니다. 설정 변경 후 서버를 재시작하세요.

- 설정 초안: Google Search 도구를 지원하는 모델이 필요합니다. 검색 요청 1회 + 구조화 요청 1회로 자사·경쟁사의 홈페이지·Instagram·YouTube를 함께 찾고, 각 홈페이지 연결 링크를 확인할 수 있습니다. 근거가 없는 주소는 자동으로 채우지 않습니다. 성공 결과는 24시간 재사용합니다.
- 뉴스 요약: 구조화 응답을 지원하는 모델이 필요합니다. 최신 최대 30건을 15건씩 최대 2회 요청합니다. 기사 전문을 수집하지 않으며 제목·발췌의 인용 근거만 정리합니다.
- 맞춤 통계 자료: 결과 화면의 버튼에서 Google Search 1회 + 구조화 1회로 현재 시장·브랜드 관련 출처를 최대 5개 추천합니다. 검색 근거 URL과 인용문을 검증하고 성공 결과를 24시간 재사용합니다. 유료 OFF·키 없음·SAMPLE에서는 실제 호출하지 않습니다. 뉴스 주제 묶음·검색 추이 사실 요약·UTM 문자 구조 점검에는 AI 비용이 없습니다.
- SAMPLE에서는 실제 AI 요청을 하지 않습니다. 유료 기능 OFF이면 뉴스 요약을 실행할 수 없습니다. 설정 마법사의 AI 제안은 별도 선택란으로 끌 수 있습니다.
- API 키가 없거나 모델이 검색 기능을 지원하지 않거나 실패하면 직접 입력으로 진행할 수 있습니다. 실패 응답은 캐시하지 않습니다.
- 실제 비용은 사용 모델과 Google 계정 조건에 따라 달라집니다. 자동 테스트는 모의 응답을 쓰며, 실계정 검증은 별도로 진행해야 합니다.
