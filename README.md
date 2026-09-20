# ADetect

브랜드명만 입력하면 시장·브랜드·소재 데이터를 수집·분석해 인사이트를 제공하는 사내 마케팅 리서치 웹 서비스입니다.
4개의 Primary Analysis Function(Market · Brand · Creative · Synthesis)으로 구성되며, Target Insight는
독립 기능이 아니라 종합분석(Synthesis) 결과 안에서 시장+브랜드 데이터를 근거로 도출됩니다.
전체 요구사항/스키마/화면 설계는 **[PRD.md](./PRD.md)** 가 기준 문서입니다. 이 README는 실행 방법만 다룹니다.

**지금 개발 단계**: 4개 기능은 서로 다른 담당자가 병렬로 개발할 수 있게 나뉘어 있습니다. **소재분석(Creative)이
가장 진행이 앞서 있어 Reference Implementation** 역할을 하고, 시장/브랜드/종합분석은 아직 UI/UX skeleton
단계입니다(부분 실연동 포함 — 아래 표 참고). 자세한 기준은 [PRD.md §0-1](./PRD.md)과
[docs/PROJECT_PLAN.md §9~§10](./docs/PROJECT_PLAN.md)을 참고하세요.

## 5분 퀵스타트

```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
# Windows (Git Bash)
source .venv/Scripts/activate
# macOS/Linux
# source .venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. (선택) 실제 API 연동 시 .env 준비 — 지금은 안 해도 목업 데이터로 전체 화면이 동작합니다
cp .env.example .env

# 4. 앱 실행
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속하면 됩니다.

## 지금 이 프로토타입에서 할 수 있는 것

| 화면 | 상태 |
|---|---|
| 홈 | 완성 (Hero 단일 화면 — 브랜드 빠른 입력 폼 + CTA. 2026-09-20부로 기능 소개 섹션은 제거하고 Analyze로 바로 연결) |
| 분석하기 STEP 1 (브랜드 설정) | 완성 (타겟 입력 없음 — PRD §16-1). 카테고리·경쟁사 추천은 GEMINI_API_KEY가 있으면 실제 Gemini 호출로 동작. Home에서 시작한 경우 이 화면은 건너뛰고 바로 아래 확인 화면으로 진입 |
| 분석하기 STEP 2 · 시장분석 탭 | 🟡 UI/UX skeleton + 부분 실연동 — 검색량 추이는 NAVER_CLIENT_ID/SECRET(NCP)가 있으면 실연동(§21-8), 뉴스도 실연동. 없으면 목업. 계절성/참고자료/이슈 필드·다운로드는 미구현 |
| 분석하기 STEP 2 · 브랜드분석 탭 | 🟡 UI/UX skeleton + 부분 실연동 — 브랜드 검색량·Meta 광고 요약은 Naver/Apify 키가 있으면 실연동, 홈페이지 분석·Instagram·AI 해석 문구는 아직 목업 |
| 분석하기 STEP 2 · 소재분석 탭 | 🟢 **Reference Implementation (end-to-end)** — APIFY_API_TOKEN이 있으면 **Meta Ads Library 실연동**(§21-11) — 소재 ID 마우스오버 시 실제 이미지/영상 썸네일 미리보기 포함. 없으면 목업. **HTML/Excel/ZIP 다운로드 구현 완료**(§16-5). 소구포인트(Appeal Point) 태깅은 근거 없는 mock이라 MVP에서 제거함 |
| 분석하기 STEP 2 · 종합분석 탭 | 🟡 UI/UX skeleton + **Target Insight subsection만 구현 완료** — 시장분석+브랜드분석 결과가 있으면 근거 기반으로 생성, 근거 부족 시 임의 인구통계 대신 정직하게 안내. SOV/포지셔닝맵 등 나머지는 담당자 미배정, 결과 구조는 탭 안의 "결과 구조 미리보기"에서 확인 가능 |
| 이력 관리 | 화면 골격 — analysis_session(브랜드/카테고리/경쟁사)만 저장·복원. function_run(기능별 결과)은 아직 저장하지 않아 재진입 시 각 탭을 다시 실행해야 함 |
| 설정 | 화면 골격 — API 키 연동 상태 확인 |

자세한 개발 계획과 담당 분담은 [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) 를 참고하세요.
API 키 발급 방법은 [SETUP_GUIDE.md](./SETUP_GUIDE.md) 를 참고하세요.

## 프로젝트 구조

```
ADetect/
├── app.py                 — Streamlit 진입점 (라우팅 + 전역 스타일)
├── pages/                 — 화면 4개 (홈/분석하기/이력관리/설정)
├── ui/                    — 탭별 렌더링 로직 (시장/브랜드/소재/종합, Target Insight는 종합 탭 내부)
├── core/
│   ├── scrapers/          — 데이터 수집 (지금은 목업, .env 채우면 실제 연동으로 전환)
│   └── analyzers/         — AI 판단/추천 로직 (지금은 규칙 기반 목업)
├── database/db.py         — SQLite 이력 저장
├── config/                — 환경설정 + 디자인 시스템(theme.py)
└── PRD.md                 — 전체 요구사항/스키마 기준 문서
```
