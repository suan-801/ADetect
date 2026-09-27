# ADetect

브랜드 전체 또는 특정 상품·캠페인의 1차 자료를 수집하고 출처·원본과 함께 정리하는 개인 PC용 앱입니다. 제품 동작은 [PRD §0 17차 개정](PRD.md)이 기준입니다.

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

실수집은 `ADETECT_SAMPLE_MODE=false`로 재시작합니다. 상세 설정은 [SETUP_GUIDE.md](SETUP_GUIDE.md)를 참고하세요.

## 사용 흐름

1. 브랜드명과 조사 대상(예: 메리츠화재 / TM사관학교 채용)을 입력합니다.
2. 브랜드/캠페인 검색어·일반 검색어 및 공식 랜딩·계정을 확인합니다. 검색어별 용도를 화면에 표시합니다.
3. 검색·뉴스 / 공식 페이지·SNS / 광고 소재를 개별 또는 한 번에 수집합니다. 실패 소스만 재시도할 수 있습니다.
4. 확인·정리에서 자료를 검색하고 포함/제외 여부를 정합니다. 선택한 원문에 한해 출처를 검증한 요약을 생성합니다.
5. 개별 또는 통합 HTML/Excel/ZIP을 만들고 이력에서 다시 다운로드·복원합니다.

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

환경변수 `ADETECT_DB_PATH`, `ADETECT_EXPORT_DIR`, `ADETECT_EXPORT_MAX_RUNS`, `ADETECT_EXPORT_MAX_BYTES`, `ADETECT_EVIDENCE_DIR`, `ADETECT_EVIDENCE_MAX_BYTES`로 조절합니다. 별도 서버 없이 이 PC가 실행·보관 서버 역할을 합니다. 앱을 끈 상태에서도 파일은 유지되지만 새 수집은 할 수 없습니다.

다운로드 버튼을 누르면 요청 이벤트를 남깁니다. 파일 생성 이력과 구분하며 브라우저 저장 완료까지 확인한 기록은 아닙니다. 파일이 만료되어도 실행·요청 이력은 남고, 결과를 복원해 다시 생성할 수 있습니다. 원본 재포함에는 원본 폴더도 필요합니다. 백업은 앱 종료 후 DB·exports·evidence를 함께 복사하세요.

개별 원본 최대 25MB, 랜딩 이미지 최대 6MB/12개, ZIP 원본 합계 최대 250MB입니다. 누락 사유는 패키지에 표시합니다. 비밀 키는 결과·내보내기에 포함하지 않습니다.

## 검증

```powershell
.venv\Scripts\python.exe -m pytest tests/test_smoke.py -v
.venv\Scripts\python.exe -m pytest tests -v
```

자동 테스트는 실제 계정 호출 없이 실행합니다. 3년 실데이터는 무료 네이버 API로 검증하며, 검색량이 적어 일부 월만 제공되는 사례도 처리합니다. Meta/Instagram/Gemini 유료 실검증은 별도 승인 후 진행합니다.

2026-09-27 검증: 자동 테스트 30개 통과, 실제 브라우저의 일괄 수집·통합 ZIP·다운로드 요청 이력·재시작 복원 확인. 지정 채용 랜딩의 전체 캡처와 이미지 원본 4개 저장을 확인했습니다.
