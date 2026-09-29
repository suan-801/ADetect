# PROJECT_PLAN — 현재 구조와 유지보수·검증 기준

제품 동작은 [PRD.md](../PRD.md)를 따른다. 이 문서는 코드가 어떻게 나뉘어 있는지, 무엇을 바꿀 때 무엇을 함께 확인해야 하는지를 정리한다.

## 1. 구조

```
app.py                      상단 메뉴(홈·프로젝트·설정), 전역 CSS, 프로젝트·설정 화면 전용 CSS
app_pages/1_home.py         Home Hero (ui/hero.py, ui/assets/home/background.png)
app_pages/2_analyze.py      → ui/project_workspace.render()
app_pages/4_settings.py     API 키 상태·모드 → ui/storage_panel (저장 공간 정리·DB 백업)

ui/project_workspace.py     프로젝트 목록·삭제 팝업, 프로젝트 설정, 자료 수집 탭, 자료 확인·다운로드 탭, 이력 탭
ui/storage_panel.py         사용량 표시, 정리 후보·실행, DB 백업 팝업

core/projects.py            프로젝트 저장소, v4 입력 정규화(project_inputs/to_storage), 검증, 비교 서명,
                            뉴스 필터(news_passes), 이력(histories), 표시 자료·기본 선택·선택 결과(selection_result)
core/project_jobs.py        단일 백그라운드 워커. 자료 종류별 작업 기록(project_task), 실행 결과(function_run) 저장, 중단
core/project_sources.py     자료 종류별 수집(collect), 실행 가능 여부(readiness), 기본 브랜드 범위, 광고 노출 상태(ad_status), UTM 대상
core/project_view.py        브랜드 비교 요약, 검색량 합계, 검색 추이 표시 정보, 뉴스·광고 관측 표시
core/result_insights.py     검색 추이 사실·연도별 최저/최고 계산, 뉴스 주제→브랜드·시장→유사 제목 묶음 (화면·파일 공유)
core/stat_discovery.py      검색 근거가 있는 통계 자료 후보, 캐시·저장·검증
core/materials.py           종류별 표 행·한 줄 요약·정렬, 뉴스 검색어 후보
core/utm.py                 UTM 파싱·마스킹·브랜드별 파라미터 문자 구조 추정
core/capture_reader.py      검색 광고 영역 Gemini 보완 판독 (검증·캐시)
core/scrapers/              search_history(검색 추이·공동 비교), naver_ad_api(검색량), naver_api(뉴스),
                            naver_serp(검색 화면 관측), brand_site(공식 페이지), ad_library(Meta·Instagram), youtube
core/evidence_store.py      원본 저장(내용 해시), 공식 페이지 캡처
core/exporters/facts_report.py   HTML·Excel·브랜드별 ZIP (v4/v5/v6/v7 표: project_tables, 이전 형식: report_tables)
core/exporters/visual_report.py  SVG 차트·이미지 카드·원본 전환을 포함한 독립 HTML
core/exporters/artifact_store.py 산출물 저장·LRU·다운로드 요청 기록
core/retention.py           사용량·정리·보유 상태·원본 보호
core/project_backup.py      프로젝트 백업 ZIP 생성·검증·새 프로젝트 복원
core/db_backup.py           SQLite 온라인 백업
core/jobs.py                24시간 소스 캐시(source_cache), 협력적 중단(checkpoint)
core/collection.py          공통 헬퍼(record, error_message, paid_problem, official_urls)와 이전 단계형 수집(run_stage, 레거시 결과·테스트용)
database/db.py              SQLite 연결·기본 테이블(analysis_session, function_run)
config/settings.py          .env 로딩, 서비스별 키 존재 플래그, SAMPLE 모드
config/theme.py             색상 토큰, 전역 CSS, Workspace CSS
```

`pages/` 폴더 이름은 쓰지 않는다. `app.py` 옆에 `pages/`가 있으면 Streamlit이 자동 페이지 탐색을 켜서 첫 접속 시 `app.py`를 거치지 않고 화면을 열 수 있다.

### 사용하지 않는 레거시 코드

파일 상단에 `LEGACY` 주석이 있고 런타임에서 import되지 않는다: `app_pages/3_history.py`(메뉴 미등록, URL로도 열리지 않음), `ui/facts_workspace.py`, `ui/{market,brand,creative,synthesis,target}_tab.py`, `ui/analysis_shared.py`, `ui/job_control.py`, `core/analyzers/*`(이전 분석·테스트용. 단 `gemini_client.py`와 `news_digest.py`는 현재 AI 기능에서 사용), `core/exporters/{report_builder,html_builder,excel_builder,packager}.py`(이전 단계형 결과용). 새 화면에 다시 연결하지 않는다. 삭제는 이전 결과 호환 테스트를 정리한 뒤 판단한다.

## 2. 데이터 흐름

1. 설정 저장: 화면 입력 → `projects.to_storage()` → `analysis_session.inputs_json` (v4)
2. 수집: `project_jobs.submit(project, sources, force, options)` → 작업마다 입력 사본 저장 → `project_sources.collect()` → `projects.normalize()`(뉴스 URL 통합·상태 계산) → `function_run`(source별 결과, `schema_version=7`)
3. 표시: `projects.histories()`(v2/v3/v4/v5/v6/v7 읽기) → 종류별 최근 성공 또는 사용자가 고른 이전 결과 → `project_view`·`materials`·`result_insights`로 계산 → 화면
4. 다운로드: `projects.selection_result()`(선택 ∩ 뉴스 필터, 비교 요약·UTM 포함) → `facts_report`

## 3. 바꿀 때 함께 확인할 것

| 바꾸는 것 | 함께 확인 |
|---|---|
| 입력 필드 | `INPUTS`, `project_inputs`(이전 프로젝트 읽기), `to_storage`, 백업·복원, PRD §3·§15 |
| 수집 결과 구조 | `schema_version`, `histories`, `project_view`, 내보내기 표, PRD §12·§15 |
| 내보내기 표 | HTML 시각 요약과 원본 탭·Excel의 데이터 일치, 전체 원문·내부 ID 미노출, PRD §12 |
| 화면 순서·메뉴 | smoke 테스트, PRD §2·§11, README 사용 흐름 |
| 유료 호출 경로 | 유료 토글·키 누락 문구, 전체 선택이 유료를 켜지 않는지 |
| 저장·보관 | `retention`, 설정 화면, README 표 |

문서는 현재 동작만 적는다. 과거 사양을 "아래보다 우선" 식으로 쌓지 않고 해당 절을 고친다.

## 4. 검증 기준

```powershell
.venv\Scripts\python.exe -m pytest tests/test_smoke.py -v
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m compileall core database ui app_pages app.py
```

테스트는 `tests/conftest.py`가 임시 DB·exports·evidence 경로와 빈 API 키를 쓰므로 실제 데이터와 외부 API를 건드리지 않는다.

화면 확인(수동): 운영 DB와 분리한 경로로 실행(README SAMPLE 실행)해 홈 → 프로젝트 설정(경쟁사 추가·중복 검색어 경고·뉴스 설정) → 자료 수집(기본/전체 선택·해제, 유료 OFF) → 자료 확인(비교 요약·검색 추이·상세·검색 화면·UTM·다운로드·추가 정보) → HTML/Excel 생성 → 이력을 확인한다. 검정 배경 위 입력칸·글자 대비를 실제 브라우저에서 본다.

실계정 검증은 모의 응답 테스트와 구분해 기록한다. 유료 API(Apify·Gemini)는 대상·호출 범위·비용 상한을 정해 승인받은 뒤 호출한다.

### 검증 기록

- 2026-09-27: 자동 테스트 67개 통과. 무료 네이버 API 실호출(한샘·현대리바트 검색어 묶음 공동 검색 추이, 검색량 합계, 뉴스 100건)과 네이버 PC 검색 화면 캡처(파워링크 10건 직접 추출, 브랜드검색 영역 식별, 공식 도메인 근거로 노출 확인)를 별도 DB에서 확인. 실제 브라우저(SAMPLE·실데이터)에서 설정·수집·결과·다운로드 화면 확인. Apify·Gemini·YouTube는 모의 응답 테스트만 수행.

## 5. 운영 원칙

- Git은 `main` 단일 브랜치로 운영한다.
- 개인 PC 로컬 실행이 기준이다. 다른 PC는 폴더를 옮겨 실행한다. 클라우드 배포 설정은 요청이 있을 때만 다룬다.
- 실제 사용자 DB(`storage/adetect.db`)와 파일은 테스트 목적으로 지우거나 바꾸지 않는다. 정리·삭제 전에는 DB 백업을 안내한다.

## 신규 설정·뉴스 근거 기능 유지보수

- `ui/project_setup.py`: 신규 전용 4단계 폼. 각 단계 제출 시 초안을 갱신한다. 브랜드·범위 변경은 명시적 교체, 기존 편집은 `project_workspace._config`를 유지한다.
- `core/project_discovery.py`: 검색 grounding → 구조화 2회 요청, 검색 근거 URL 검증, 자사·경쟁사 홈페이지 SNS 연결 확인, 프로필 URL 정규화, 성공 캐시와 호출 잠금. 공식 여부는 자동 인증하지 않는다.
- `core/analyzers/news_digest.py`: 주제·브랜드·월별 대표 최대 30건/1,800자/15건 배치, 직접 인용·수치 부분 문자열 검증, 성공 캐시, 파생 결과 저장. 기존 수집 워커는 유지하며 뉴스 요약은 명시적 버튼 요청에만 실행한다.
- `project_digest`는 수집 기록당 1개, 원본과 별도 저장한다. 백업 시 포함하고 복원 시 새 run_id에 연결한다. 결과 정리·프로젝트 삭제 시 함께 정리한다. 입력 v4를 유지하며 새 결과는 v7, 과거 수집 사본은 수정하지 않는다.
- `project_resource`는 프로젝트당 통계 후보 1개를 별도 저장한다. 브랜드·시장·모델·방식 지문이 맞을 때만 표시하며 백업 v5에 포함하고 삭제 시 함께 정리한다. 백업 v3/v4도 읽는다.
- 비교표는 화면에서 선택한 SNS 버전을 사용한다. 다른 시점 결과를 몰래 결합하지 않는다.
- 회귀 검증: 성공 AI 프리필→수정→뒤로→저장, 무키 수동 생성, 성공 캐시/실패 재시도, 근거 없는 URL 거부, 뉴스 허위 수치/출처 거부, 버전·필터 변경, 선택 다운로드, 요약 백업·복원.
- 유료 실호출 없이 모의 응답으로 검증한다. Gemini 계정별 검색 도구 지원·실제 제안 품질·비용은 별도 승인된 실계정 검증 대상이다.

- HTML 미리보기: `image_preview.compress`로 저장 원본을 압축하며 AI·외부 요청 없이 생성한다. Meta·YouTube 수집 시 실제 응답의 썸네일을 별도 저장한다. 검색 문구 필터는 `project_view.search_ad_rows`를 화면·파일에서 공유하며 수집 당시 입력 사본을 쓴다. 상세 원문은 Excel/JSON에 남긴다.


## 종합 분석 구조

`core/research_analysis.py`는 조사 조건·근거 균형 선정·프롬프트·인용 검증·토큰 계수·사용량·캐시를 담당합니다. `ui/research_analysis.py`는 저장 조건과 명시적인 분석/시장 검색 버튼, `core/exporters/analysis_report.py`는 화면과 HTML의 공통 안전한 표시를 담당합니다. LEGACY 분석기는 연결하지 않습니다.

`project_analysis`는 프로젝트별 조건·검색·분석·최근 요청 결과를 저장합니다. 수집 입력 v4는 그대로이며 결과 v7, 백업 v5를 사용합니다. 변경 자료의 지문이 다르면 현재 결과로 내보내지 않습니다. 프로젝트 삭제·백업 복원 경로에 포함됩니다. 웹 결과는 grounding support의 문장-출처 연결을 검증하고, 통계 후보는 자동으로 확정 근거가 되지 않습니다.

검증: `tests/test_research_analysis.py`의 가짜 인용/URL 거부, 자료 변경 지문, SAMPLE/키 차단, 사용량/입력 상한/캐시, 검색 출처 연결, 백업·삭제·HTML·Excel을 확인합니다. 실제 Gemini 출력 품질과 계정 무료 한도는 승인된 별도 실계정 검증 대상입니다.
