# ADetect

브랜드 전체 또는 특정 상품·캠페인의 1차 자료를 프로젝트별로 수집하고 출처·원본과 함께 정리하는 앱입니다. 제품 동작은 [PRD §0 18차 개정](PRD.md)이 기준입니다.

## 폴더 구성

| 위치 | 내용 |
|---|---|
| 루트 | `app.py`(진입점), `README.md`, `PRD.md`(제품 기준), `CLAUDE.md`/`AGENTS.md`(작업 지침), `requirements.txt`, `.env.example` |
| `pages/`, `ui/` | 화면 (`ui/project_workspace.py`가 프로젝트 화면, 레거시 UI는 파일 상단 `LEGACY` 표시) |
| `core/`, `database/`, `config/` | 수집·저장·내보내기 로직, SQLite, 설정 |
| `tests/` | 자동 테스트 (임시 DB 사용) |
| `docs/` | `PROJECT_PLAN.md`, `SETUP_GUIDE.md`(API 키 발급), 개발일지(pptx), 과거 계획서. `docs/design_reference/`는 외부 사이트 참고 이미지로 git에 올리지 않음 |
| `adetect_reference/` | 기존 워크스페이스에서 가져온 참고 코드 (PRD §4) |
| `storage/` (git 제외) | `adetect.db`, `exports/`, `evidence/`, `backups/`, `smoke/`(수동 테스트 DB), `temp/`(스크린샷·로그·테스트 DB·임시 산출물) |

## 실행

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m streamlit run app.py
```

127.0.0.1에서만 접속합니다. API 키는 `.env`에 설정하고 앱을 재시작하세요. 유료 기능은 기본 ON이며, 입력 과정에서 자동 호출하지 않고 수집/요약 버튼으로 실행합니다. 토큰 누락 시 `토큰 부족. 개발자에게 문의해주세요`를 표시합니다. 키 누락을 SAMPLE로 대체하지 않습니다.

외부 요청 없는 SAMPLE 검증:

```powershell
$env:ADETECT_SAMPLE_MODE="true"
.venv\Scripts\python.exe -m streamlit run app.py
```

실수집은 `ADETECT_SAMPLE_MODE=false`로 재시작합니다. 상세 설정은 [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)를 참고하세요.

## 사용 흐름

1. 홈에서 브랜드명을 입력하거나 프로젝트 목록에서 프로젝트를 만듭니다. 예: `한샘 — 리하우스 조사`, `메리츠화재 — TM 채용`. 쓰지 않는 프로젝트는 목록에서 보관·보관 해제합니다.
2. 브랜드/캠페인 검색어, 일반 검색어, 조사 페이지와 공식 계정을 입력합니다. 화면에서 각 검색어의 사용처를 설명합니다.
3. 8개 자료 종류 중 필요한 항목만 선택해 수집합니다. 기존 자료는 날짜·건수로 표시하며 체크 해제해도 삭제되지 않습니다.
4. 자료 확인·다운로드는 자료 종류별 최근 성공 버전을 자동으로 사용하고 종류·수집일·건수만 한 줄로 보여줍니다. 과거 버전은 `다른 시점 선택`을 열었을 때만 고릅니다. 수집일이 섞이면 화면과 파일에 날짜 혼합을 표시합니다. 포함/확인 필요/제외와 파일 선택은 따로 지정합니다.
5. 선택한 자료로 HTML/Excel/ZIP을 만듭니다. `01_수집정보`는 프로젝트명·검색어·공식 페이지·자료별 수집 시각·캐시·SAMPLE·유료 기능을 읽기 쉬운 `항목/값` 행으로 보여줍니다(API 키 미표시, 빈 값은 `미입력`).
6. 이력 탭은 각 수집 기록을 `결과·원본 모두 있음` / `결과만 있음 (일부 원본 없음)` / `이력만 있음`으로 표시하고, 없는 원본 목록·`이 시점 결과 열기`·`원본 보호`를 제공합니다.
7. 프로젝트 백업은 원본과 입력을 포함한 검증 가능한 ZIP으로 만들며, 복원은 기존 프로젝트를 덮어쓰지 않고 새 프로젝트로 가져옵니다.

기본 자료 선택은 검색 추이·검색량·뉴스·지정 공식 페이지입니다. 유료 기능은 기본 ON이며 키가 없을 때 `토큰 부족. 개발자에게 문의해주세요`가 표시됩니다.

## 팩트 중심 범위

- 완료된 36개월의 검색 추이, 월별 평균과 연도별 피크·저점. 검색어별 상대지수이며 서로 다른 검색어의 절대 규모 비교는 불가합니다. 누락 월은 0이 아닙니다.
- 검색량·관련 뉴스·공식 페이지·SNS 최근 게시물·Meta 광고 원문·이미지/영상·연결 URL.
- 홈페이지 캡처와 이미지 원본을 보존합니다. 이미지 속 문구 OCR은 아직 제공하지 않으며 원본에서 조건을 확인해야 합니다.
- Meta 최대 20건/페이지, 뉴스 최대 100건/검색어, SNS 최근 최대 5건. 전체 광고량·전체 기사량을 의미하지 않습니다.
- 타깃 추정·포지셔닝·전략 추천·광고/뉴스 점유율은 새 화면/내보내기에서 제외했습니다. 기존 분석 모듈은 과거 호환용입니다.

## 저장·다운로드 이력

| 대상 | 기본 위치 | 보관 정책 |
|---|---|---|
| 입력·결과·다운로드 요청 | storage/adetect.db | SQLite 영속 저장, 자동 삭제 없음 |
| HTML/Excel/ZIP | storage/exports | 최근 20개 실행·총 5GB LRU |
| 캡처·이미지·영상 | storage/evidence | 내용 해시로 중복 제거, 총 5GB 초과 시 추가 저장 중단 |

환경변수 `ADETECT_DB_PATH`, `ADETECT_EXPORT_DIR`, `ADETECT_EXPORT_MAX_RUNS`, `ADETECT_EXPORT_MAX_BYTES`, `ADETECT_EVIDENCE_DIR`, `ADETECT_EVIDENCE_MAX_BYTES`로 조절합니다. 현재 로컬 MVP는 별도 서버 없이 이 PC가 실행·보관 서버 역할을 합니다. 원격 DB·Storage 코드는 배포 검증 전 준비 상태이며 자동으로 활성화되지 않습니다.

다운로드 버튼을 누르면 요청 이벤트를 남깁니다. 파일 생성 이력과 구분하며 브라우저 저장 완료까지 확인한 기록은 아닙니다. 파일이 만료되어도 실행·요청 이력은 남고, 결과를 복원해 다시 생성할 수 있습니다. 원본 재포함에는 원본 폴더도 필요합니다. 백업은 앱 종료 후 DB·exports·evidence를 함께 복사하세요.

### 저장 공간 관리

프로젝트 화면 상단과 설정 화면에 파일·DB 사용량, 전체 한도, 사용률을 표시합니다. 80% 이상이면 경고, 90% 이상이면 정리 안내가 나오며, 저장 부족으로 수집·파일 생성이 막히면 `저장 공간 정리로 이동` 버튼이 나옵니다.

설정 > 저장 공간 관리: `정리 후보 보기`(종류·파일명·예상 용량, 삭제 없음) → 동의 체크 → `정리 실행`. 실행 결과와 삭제 항목, 사용량 변화를 표시합니다. 최근 성공 결과와 그 원본, 현재 연 프로젝트 결과의 원본, 수집 중 작업, 보호(pin)한 원본은 후보에서 제외됩니다.

### 백업과 과거 테스트 데이터

- 설정 > `DB 백업 만들기`: `storage/backups/adetect_<시각>.db`로 SQLite 사본을 만듭니다(기존 백업을 덮어쓰지 않음). 원본까지 보존하려면 앱을 종료한 뒤 `storage/evidence`, `storage/exports`도 함께 복사하세요.
- 수동 백업(앱 종료 후): `New-Item -ItemType Directory -Force storage/backups; Copy-Item storage/adetect.db storage/backups/adetect_manual.db`
- 설정 > 프로젝트 정리: 프로젝트를 `수집 이력 없음`/`SAMPLE 자료만 있음`/`실수집 자료 포함`/`구분 불가 (만료 기록만 있음)`으로 구분해 보여줍니다(저장된 사실 기준, 테스트 여부 추정 없음). 삭제는 프로젝트 단위로만, 영향 범위 확인·백업 확인·프로젝트 이름 재입력 후 가능합니다. 앱은 기존 프로젝트를 자동 삭제하지 않습니다.

### 테스트 DB 분리

`pytest`는 `tests/conftest.py`가 임시 DB·exports·evidence를 쓰므로 운영 DB(`storage/adetect.db`)를 건드리지 않습니다. 브라우저로 수동 스모크 테스트를 할 때는 별도 경로를 지정해 운영 데이터와 섞이지 않게 하세요.

```powershell
$env:ADETECT_SAMPLE_MODE="true"
$env:ADETECT_DB_PATH="storage/smoke/adetect_smoke.db"
$env:ADETECT_EXPORT_DIR="storage/smoke/exports"
$env:ADETECT_EVIDENCE_DIR="storage/smoke/evidence"
.venv\Scripts\python.exe -m streamlit run app.py
```

개별 원본 최대 25MB, 랜딩 이미지 최대 6MB/12개, ZIP 원본 합계 최대 250MB입니다. 누락 사유는 패키지에 표시합니다. 비밀 키는 결과·내보내기에 포함하지 않습니다.

## 다른 PC로 옮기기 (zip)

현재는 로컬 실행이 기준입니다. 다른 PC·네트워크에서 쓰려면 프로젝트 폴더를 zip으로 옮깁니다. 클라우드 배포 설정은 이번 범위에 포함하지 않습니다.

**zip에서 뺄 것**: `.venv/`(PC마다 새로 만들어야 함), `__pycache__/`, `.pytest_cache/`, `storage/temp/`, `storage/smoke/`

**상황에 따라 판단할 것**
- `.env`: API 키가 들어 있습니다. 본인 PC로만 옮길 때만 포함하고, 다른 사람에게 줄 때는 빼고 `.env.example`로 새로 만듭니다.
- `storage/`(adetect.db, evidence, exports, backups): 기존 프로젝트와 원본까지 가져가려면 **앱을 종료한 뒤** 폴더째 포함합니다. 빼면 새 PC에서 빈 상태로 시작합니다. 프로젝트 하나만 옮길 때는 이력 탭의 '프로젝트 백업' ZIP → 새 PC의 '백업에서 새 프로젝트 복원'을 써도 됩니다.

### zip을 받은 뒤 할 일 (Windows PowerShell, 압축 푼 ADetect 폴더에서)

**1. Python 확인** — 3.12 이상 (개발 PC는 3.14). 없으면 python.org에서 설치하고 "Add python.exe to PATH"를 체크합니다.

```powershell
python --version
```

**2. 가상환경 만들기와 패키지 설치** — `.venv`는 zip에 넣지 않으므로 PC마다 새로 만듭니다. `Activate.ps1`을 쓰지 않고 `.venv\Scripts\python.exe`를 직접 부르면 실행 정책(ExecutionPolicy) 오류를 피할 수 있습니다.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

`playwright install`은 공식 페이지 캡처·네이버 검색 화면에만 필요합니다. 회사망에서 다운로드가 막혀도 나머지 자료 수집은 동작합니다.

**3. `.env` 준비** — `.env`를 zip에 넣어 왔다면 이 단계를 건너뜁니다.

```powershell
Copy-Item .env.example .env
notepad .env
```

| 변수 | 필요할 때 | 발급 안내 |
|---|---|---|
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 검색 관심도 추이·관련 뉴스 | docs/SETUP_GUIDE.md 2절 |
| `NAVER_AD_API_KEY`, `NAVER_AD_SECRET_KEY`, `NAVER_AD_CUSTOMER_ID` | 월간 검색량·연관 검색어 | 3절 |
| `APIFY_API_TOKEN` | Meta 광고·Instagram (유료) | 4절 |
| `GEMINI_API_KEY` | 근거 요약 (유료) | 5절 |
| `YOUTUBE_API_KEY` | YouTube 공식 채널 | 하단 추가 설정 |
| `ADETECT_SAMPLE_MODE` | `true`면 외부 호출 없이 SAMPLE 자료, `false`면 실수집 | — |

- 키가 없는 자료는 수집되지 않고 상태로 안내됩니다(Apify/Gemini는 `토큰 부족. 개발자에게 문의해주세요`).
- 저장 위치를 바꾸려면 `ADETECT_DB_PATH`, `ADETECT_EXPORT_DIR`, `ADETECT_EVIDENCE_DIR`를 설정합니다. 비워두면 `storage/` 아래를 씁니다.
- `.env`를 고친 뒤에는 앱을 재시작해야 반영됩니다.

**4. 먼저 SAMPLE 모드로 화면 확인** — 실제 데이터와 섞이지 않게 별도 DB를 씁니다. 이 설정은 이 PowerShell 창에서만 유효합니다.

```powershell
$env:ADETECT_SAMPLE_MODE="true"
$env:ADETECT_DB_PATH="storage/smoke/adetect_smoke.db"
$env:ADETECT_EXPORT_DIR="storage/smoke/exports"
$env:ADETECT_EVIDENCE_DIR="storage/smoke/evidence"
.venv\Scripts\python.exe -m streamlit run app.py
```

브라우저에서 http://127.0.0.1:8501 을 열어 홈 → 프로젝트 생성 → 기본 자료 수집 → 자료 확인·다운로드 → HTML 생성까지 확인한 뒤, 터미널에서 `Ctrl+C`로 종료합니다.

**5. 실사용 실행** — 새 PowerShell 창을 열고 (4번의 임시 설정이 남지 않도록), `.env`의 `ADETECT_SAMPLE_MODE=false`를 확인한 뒤:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

**6. (선택) 자동 테스트** — 실제 API나 운영 DB를 쓰지 않습니다.

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

**문제가 생겼을 때**
- `python`을 찾을 수 없음: Python 설치 시 PATH 추가를 확인하거나 `py -3 -m venv .venv`로 만듭니다.
- 8501 포트가 사용 중: `.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502`
- 앱은 127.0.0.1에서만 열립니다(그 PC의 브라우저에서만 접속). 회사·외부 네트워크의 방화벽·프록시가 네이버/Apify/Gemini 호출을 막으면 해당 자료가 `실패`로 기록되며, 토큰 부족으로 표시하지 않습니다.

## 검증

```powershell
.venv\Scripts\python.exe -m pytest tests/test_smoke.py -v
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m compileall core database ui pages app.py
```

자동 테스트는 실제 계정 호출 없이 실행합니다. 3년 실데이터는 무료 네이버 API로 검증하며, 검색량이 적어 일부 월만 제공되는 사례도 처리합니다. Meta/Instagram/Gemini 유료 실검증은 별도 승인 후 진행합니다.

2026-09-27 검증: 자동 테스트 28개 통과. 프로젝트 생성·자료 선택·유료 기본 ON·뉴스 URL 중복 통합·입력 스냅샷을 확인했습니다. 실제 브라우저(SAMPLE 모드)에서 홈 → 프로젝트 설정 → 기본 자료 수집 → 수집 완료 자동 갱신 → 자료 선택 → HTML 생성·다운로드까지 확인했습니다. 기존 실수집 검증 기록은 보존하며 유료 API는 호출하지 않았습니다.

2026-09-27 18차 보완 검증: 자동 테스트 41개 통과(smoke 11개 포함), compileall 통과. 분리된 SAMPLE DB로 실제 브라우저에서 프로젝트 생성 → 기본 자료 수집 → 확인·다운로드 최근 버전 자동 선택·`다른 시점 선택` → 이력 3단계 표시(결과·원본 모두 있음/결과만 있음/이력만 있음) → 설정 저장 공간 표시·정리 후보 보기·동의 전 실행 버튼 비활성·정리 실행 결과 표시 → HTML 01_수집정보 행 표시를 확인했다. 운영 DB(`storage/adetect.db`, 세션 86개)는 변경하지 않았다.

## 현재 미구현·별도 검증 필요

클라우드 배포(Streamlit Community Cloud·Supabase 등)는 현재 범위에서 제외했습니다 — 로컬 실행 후 zip으로 다른 PC에 옮겨 씁니다. 원격 DB·Storage 코드(`database/remote.py`, `core/storage.py`)는 미검증 준비 상태입니다. 클라우드 인증·다중 사용자·signed URL·자동 백업·분산 작업 큐, 유료 Meta/Instagram/Gemini 실계정 호출, 이미지 OCR과 전략·타깃·포지셔닝 해석은 이번 구현에 포함하지 않았습니다.
