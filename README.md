# ADetect

브랜드명만 입력하면 시장·타겟·브랜드·소재 데이터를 수집·분석해 인사이트를 제공하는 사내 마케팅 리서치 웹 서비스입니다.
전체 요구사항/스키마/화면 설계는 **[PRD.md](./PRD.md)** 가 기준 문서입니다. 이 README는 실행 방법만 다룹니다.

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
| 홈 | 완성 (브랜드 빠른 입력 폼 + 5개 기능 소개) |
| 분석하기 STEP 1 (브랜드 설정) | 완성 (타겟 입력 없음 — PRD §16-1). 카테고리·경쟁사 추천은 GEMINI_API_KEY가 있으면 실제 Gemini 호출로 동작 |
| 분석하기 STEP 2 · 시장분석 탭 | 검색량 추이는 NAVER_CLIENT_ID/SECRET(NCP)가 있으면 실연동(§21-8), 뉴스도 실연동. 없으면 목업 |
| 분석하기 STEP 2 · 타겟분석 탭 | 게이트/추천/확정/분석 흐름 동작. 관심 키워드는 NAVER_AD_* 키가 있으면 실연동(§21-10), AI Persona 해석은 아직 목업 |
| 분석하기 STEP 2 · 브랜드분석 탭 | 브랜드 검색량·Meta 광고 요약은 Naver/Apify 키가 있으면 실연동, 홈페이지 분석·Instagram은 아직 목업 |
| 분석하기 STEP 2 · 소재분석 탭 | APIFY_API_TOKEN이 있으면 **Meta Ads Library 실연동**(§21-11) — 소재 ID 마우스오버 시 실제 이미지/영상 썸네일 미리보기 포함. 없으면 목업. **HTML/Excel/ZIP 다운로드 구현 완료**(§16-5) — 다른 4개 탭 다운로드는 아직 미구현 |
| 분석하기 STEP 2 · 종합분석 탭 | 화면 골격만 (담당자 미배정) |
| 이력 관리 / 설정 | 화면 골격 |

자세한 개발 계획과 담당 분담은 [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) 를 참고하세요.
API 키 발급 방법은 [SETUP_GUIDE.md](./SETUP_GUIDE.md) 를 참고하세요.

## 프로젝트 구조

```
ADetect/
├── app.py                 — Streamlit 진입점 (라우팅 + 전역 스타일)
├── pages/                 — 화면 4개 (홈/분석하기/이력관리/설정)
├── ui/                    — 탭별 렌더링 로직 (시장/타겟/브랜드/소재/종합)
├── core/
│   ├── scrapers/          — 데이터 수집 (지금은 목업, .env 채우면 실제 연동으로 전환)
│   └── analyzers/         — AI 판단/추천 로직 (지금은 규칙 기반 목업)
├── database/db.py         — SQLite 이력 저장
├── config/                — 환경설정 + 디자인 시스템(theme.py)
└── PRD.md                 — 전체 요구사항/스키마 기준 문서
```
