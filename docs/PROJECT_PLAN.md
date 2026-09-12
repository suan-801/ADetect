# ADetect 개발 계획서 (뼈대/프로토타입 단계)

> 기준 문서: [`PRD.md`](../PRD.md) (15차 개정 — 브랜드 범용화 + 타겟 후추천 구조).
> 이 문서는 "그 PRD를 실제로 어떻게, 누가, 어떤 순서로 만들 것인가"만 다룹니다.

---

## 1. 지금까지 만든 것 (현재 상태)

| 영역 | 상태 | 위치 |
|---|---|---|
| 저장소 뼈대 (폴더 구조, .env, requirements) | ✅ 완료 | 루트 |
| 다크+골드 테마, Pretendard 폰트(CDN) | ✅ 완료 | `config/theme.py` |
| 홈 화면 (ref.png 참고) | ✅ 완료 | `pages/1_home.py` |
| STEP 1 브랜드 설정 (타겟 입력 없음) + AI 추천 확인 화면 | ✅ 완료 | `pages/2_analyze.py` |
| STEP 2 Workspace 5개 탭 골격 + 상태 스트립 | ✅ 완료 | `pages/2_analyze.py` |
| 시장분석 탭 | 🟡 목업 데이터로 동작 (담당자 확장 필요) | `ui/market_tab.py` |
| 타겟분석 탭 (게이트 + 추천/확정/분석 2단계) | 🟡 목업 데이터로 동작 (담당자 확장 필요) | `ui/target_tab.py`, `core/analyzers/target_recommender.py` |
| **브랜드분석 탭 (자사+경쟁사 통합)** | 🟢 **End-to-End 동작** (mock scraper → 실제 API로 교체만 하면 됨) | `ui/brand_tab.py`, `core/analyzers/brand_analyzer.py`, `core/scrapers/{naver_api,brand_site,ad_library}.py` |
| 소재분석 / 종합분석 탭 | ⚪ 화면 골격만 (담당자 미배정) | `ui/creative_tab.py`, `ui/synthesis_tab.py` |
| 이력 관리 / 설정 화면 | 🟡 골격만 (실제 재진입 기능 없음) | `pages/3_history.py`, `pages/4_settings.py` |
| SQLite 이력 저장 (`analysis_session`/`function_run`) | ✅ 완료 | `database/db.py` |

지금 `streamlit run app.py`로 실행하면 **브랜드명 입력 → STEP1 확인 → Workspace 진입 →
시장분석/브랜드분석 시작 → 타겟분석 자동 잠금해제 → 추천/확정/분석**까지 전부 클릭으로 눌러볼 수 있습니다
(전부 목업 데이터 기준).

---

## 2. 아키텍처 한 장 요약

```
app.py (라우팅 + 전역 CSS)
 └─ pages/1_home.py       — 홈(랜딩)
 └─ pages/2_analyze.py    — STEP1 입력 → STEP2 Workspace(5탭)
 │     └─ ui/market_tab.py     ─┐
 │     └─ ui/target_tab.py      │  각 탭은 session(dict)을 받아 그리고,
 │     └─ ui/brand_tab.py       │  core/analyzers/*.py 를 호출해 결과를 채움
 │     └─ ui/creative_tab.py    │
 │     └─ ui/synthesis_tab.py  ─┘
 └─ pages/3_history.py    — SQLite 이력 조회
 └─ pages/4_settings.py   — API 키 상태 확인

core/scrapers/*   — 실제 수집 (지금은 config.settings.USE_MOCK_DATA에 따라 mock 반환)
core/analyzers/*  — AI 판단/추천 (§8 FACT/AI/REC 스키마 공통 사용, insight_synthesizer.build_insight)
database/db.py    — analysis_session / function_run (PRD §6-1·§13)
```

**중요한 설계 원칙**: `ui/*_tab.py`는 화면만 그리고, 실제 로직은 항상 `core/analyzers/*.py`
함수 호출로 위임합니다. 그래서 **담당자는 core 쪽 함수 내부만 mock → 실제 구현으로 바꾸면 되고,
화면 코드는 거의 건드릴 필요가 없습니다.**

---

## 3. 모듈 분담 제안

| 파트 | 담당 파일 | 지금 할 일 |
|---|---|---|
| **시장분석** | `ui/market_tab.py`, `core/scrapers/naver_api.py`(`get_search_volume_trend`, `get_news`) | §7-1 `search_seasonality`/`reference_sources`/`market_issues`/`upcoming_changes` 추가, 실제 네이버 API 연동 |
| **브랜드분석** (진행자: 본인, 백엔드 포함) | `ui/brand_tab.py`, `core/analyzers/brand_analyzer.py`, `core/scrapers/{naver_api,brand_site,ad_library}.py` | 아래 §4 참고 |
| **타겟분석** | `ui/target_tab.py`, `core/analyzers/target_recommender.py` | §7-2-a AI Persona 3개 필드 근거 데이터 실측 연결, Gemini 프롬프트로 `recommend_target` 교체 |
| **소재분석** (미배정) | `ui/creative_tab.py` (신규 작성 필요) | §7-11-4 기준 appeal_tags 태깅, 장기운영 분석 |
| **종합분석** (미배정) | `ui/synthesis_tab.py` (신규 작성 필요) | §7-4 SOV/포지셔닝맵/White Space |

각자 자기 파일만 건드리면 되도록 나눠놨기 때문에 **브랜치를 나눠도 병합 충돌이 거의 안 납니다.**

### Git 브랜치 전략 (제안)

```
main                        — 항상 동작하는 상태만 유지 (지금 이 커밋)
├─ feature/market-analysis  — 시장분석 담당
├─ feature/brand-analysis   — 브랜드분석 담당 (본인)
├─ feature/target-analysis  — 타겟분석 담당
├─ feature/creative-analysis
└─ feature/synthesis
```
각자 브랜치에서 작업 → PR 생성 → 리뷰 후 `main` 머지. `ui/components.py`, `config/theme.py`,
`database/db.py`처럼 여러 명이 공유하는 파일을 바꿀 때만 미리 이야기하고 진행하세요.

---

## 4. 브랜드분석 파트 — 다음 단계 (본인 담당)

지금 `core/scrapers/naver_api.py` / `brand_site.py` / `ad_library.py`는 전부
`config.settings.USE_MOCK_DATA`가 True일 때 결정론적 목업 값을 반환합니다. 실제 연동 순서 제안:

1. `SETUP_GUIDE.md` 따라 네이버 오픈API 키 발급 → `.env`에 입력 → `USE_MOCK_DATA`가 자동으로 `False` 전환 확인
2. `core/scrapers/naver_api.py`의 `get_brand_search_volume()` 내부를 실제 DataLab `keywordGroups` 호출로 교체 (PRD §7-9 — 자사+경쟁사 한 번의 요청에 그룹으로 묶어야 비교 가능, 자사를 앵커로 고정)
3. `brand_site.py`의 `crawl_brand_website()`를 실제 Playwright 크롤링으로 교체 (PRD §7-3 — 대표 상세페이지 없으면 홈페이지/브랜드스토리 폴백)
4. `ad_library.py`의 `fetch_meta_ads()`/`fetch_instagram_profile()`을 실제 Apify 액터 호출로 교체
5. `core/analyzers/insight_synthesizer.py`의 목업 문구 생성을 실제 Gemini 프롬프트 호출로 교체 (반환 shape `insight/source/evidence/confidence`는 그대로 유지)
6. `run_brand_analysis()`의 반환 shape은 바꾸지 마세요 — `ui/brand_tab.py`가 그 shape을 그대로 렌더링하고 있습니다.

---

## 5. 디자인 관련 — 확인이 필요한 항목 (ref.png 재현 한계)

ref.png를 최대한 참고했지만, Streamlit 위젯의 구조적 한계로 아래 항목은 단순화했습니다.
**실제로 이 정도 차이가 괜찮은지, 아니면 더 정교하게(예: 커스텀 HTML 컴포넌트) 맞춰야 하는지 확인 부탁드립니다.**

1. **홈 히어로 우측의 3D 캡슐 오브젝트 그래픽** — 생략했습니다. 정적 이미지(PNG/WebP)를 만들어
   `templates/assets/`에 넣어주시면 배경 이미지로 넣는 정도는 쉽게 추가할 수 있습니다.
2. **사이드바 커스텀 아이콘 네비게이션** — Streamlit의 기본 `st.navigation` 위에 최소 CSS만
   입혔습니다. ref.png처럼 완전히 커스텀된 아이콘/hover 애니메이션까지는 기본 위젯으로는 한계가
   있어, 필요하시면 순수 HTML/CSS 사이드바(스트림릿 컴포넌트)로 바꾸는 방안을 검토하겠습니다.
3. **상단 우측 "History"/사용자 아바타 드롭다운 바** — 이번 스켈레톤에는 없고, 대신 좌측
   사이드바의 "이력 관리" 페이지로 대체했습니다. 상단 고정 바가 꼭 필요하면 알려주세요.
4. **"분석 시작하기" 버튼 색상** — ref.png는 밝은 화이트 계열 버튼인데, 지금 테마도 동일하게
   화이트 버튼 + 호버 시 골드로 맞췄습니다(하나만 확인 부탁드려요: 이 정도 톤이면 괜찮은지).

---

## 6. 마일스톤 제안

| 단계 | 목표 | 참고 |
|---|---|---|
| **M0 (지금)** | 뼈대 + 프로토타입 — 5개 기능이 눈에 보이고 클릭 가능 | 완료 |
| **M1** | 브랜드분석 실제 API 연동 (네이버+Apify+Gemini) | PRD §22 Phase 0~1 |
| **M2** | 시장분석 실제 API 연동 | PRD §22 Phase 1~2 |
| **M3** | 타겟분석 Gemini 프롬프트 연동 | PRD §22 Phase 1~2 |
| **M4** | 소재분석·종합분석 신규 구현 | PRD §22 Phase 2~3 |
| **M5** | Excel/HTML/ZIP 내보내기, 이력 재진입 | PRD §22 Phase 3~4 |
