# ADetect 개발 계획서 (뼈대/프로토타입 단계)

> 기준 문서: [`PRD.md`](../PRD.md) (16차 개정 — 4개 Primary Analysis Function + Target Insight 구조).
> 이 문서는 "그 PRD를 실제로 어떻게, 누가, 어떤 순서로 만들 것인가"만 다룹니다.

---

## 1. 지금까지 만든 것 (현재 상태, 2026-09-19 갱신)

| 영역 | 상태 | 위치 |
|---|---|---|
| 저장소 뼈대 (폴더 구조, .env, requirements) | ✅ 완료 | 루트 |
| 디자인 시스템 — Cinematic Editorial Intelligence(4차 리뉴얼, §8 Active Design Direction) | ✅ 완료 | `config/theme.py`, `.streamlit/config.toml` |
| 홈 화면 — Cinematic Brand Experience(Hero/Manifesto/Story/Sample Output/Final CTA scene 구성) | ✅ 완료 | `pages/1_home.py`, `ui/hero.py`, `ui/components.py` |
| STEP 1 브랜드 설정 + AI 추천 확인 화면 | ✅ 완료 — **카테고리/경쟁사 추천 Gemini 실연동**(GEMINI_API_KEY 있으면), 실패해도 목업으로 조용히 폴백. 타겟 입력 필드 없음 | `pages/2_analyze.py`, `core/analyzers/recommender.py` |
| STEP 2 Workspace **4개 탭** 골격 + 상태 스트립 | ✅ 완료 (16차 개정 — 독립 타겟분석 탭 제거) | `pages/2_analyze.py` |
| 시장분석 탭 | 🟡 **부분 실연동** — 검색량 추이(DataLab)·뉴스는 NAVER 키 있으면 실동작. `search_seasonality`/`reference_sources`/`market_issues`/`upcoming_changes`(§7-1) 및 다운로드는 아직 미구현 | `ui/market_tab.py`, `core/scrapers/naver_api.py` |
| **브랜드분석 탭 (자사+경쟁사 통합)** | 🟡 **부분 실연동** — 브랜드 검색량(절대치 포함)·Meta 광고 요약은 Naver/Apify 키 있으면 실동작. 홈페이지 크롤링(Playwright)·Instagram 프로필·`brand_context`/해석 문구는 아직 목업(Gemini 미연동) | `ui/brand_tab.py`, `core/analyzers/brand_analyzer.py`, `core/scrapers/{naver_api,naver_ad_api,brand_site,ad_library}.py` |
| **소재분석 탭** | 🟢 **End-to-End 동작** — Meta Ads Library 실연동(APIFY_API_TOKEN), 자동 페이지 매칭이 부정확할 때 URL/페이지명 직접 지정 폴백, 브랜드별 수집 진행상황(st.status) 표시, HTML/Excel/ZIP 다운로드 완료. **소구포인트(appeal_tags) 태깅은 근거 없는 mock이라 16차 개정에서 제거**(§0) — `creative_key_visual`은 FACT 지표(활성 광고 수/포맷 구성/장기 운영 소재 수)만 사용 | `ui/creative_tab.py`, `core/analyzers/creative_analyzer.py`, `core/scrapers/ad_library.py`, `core/exporters/*.py` |
| 종합분석 탭 | 🟡 **Target Insight 구현 완료** — 시장분석+브랜드분석 결과가 있으면 근거 기반 insight 생성, 근거 부족 시 `insufficient_data`/정직한 안내로 처리(임의 인구통계 생성 없음). SOV/포지셔닝맵/White Space 등 나머지 필드는 화면 골격만(담당자 미배정) | `ui/synthesis_tab.py`, `core/analyzers/insight_synthesizer.py` |
| 이력 관리 / 설정 화면 | 🟡 골격만 (실제 재진입 기능 없음, API 키 상태 표시만 동작) | `pages/3_history.py`, `pages/4_settings.py` |
| SQLite 이력 저장 (`analysis_session`/`function_run`) | ✅ 완료 (레거시 `target_status`/`recommended_target`/`confirmed_target` 컬럼은 destructive migration 없이 유지, 신규 UI는 사용 안 함) | `database/db.py` |
| [DEPRECATED] `ui/target_tab.py`, `core/analyzers/target_recommender.py` | ⚫ 코드는 유지하되 Workspace에서 import/render하지 않음 — `recommend_target()`은 seeded_random mock이라 재사용 금지(§0·§14) | `ui/target_tab.py`, `core/analyzers/target_recommender.py` |

지금 `streamlit run app.py`로 실행하면 **브랜드명 입력 → STEP1 확인(키 있으면 Gemini 실추천) → Workspace 진입 →
시장분석/브랜드분석/소재분석 시작(키 있으면 부분 실연동) → 종합분석 탭 진입 시 Target Insight 자동 표시**까지
전부 클릭으로 눌러볼 수 있습니다. API 키 발급 방법은 [`SETUP_GUIDE.md`](../SETUP_GUIDE.md) 참고 —
키를 하나도 안 채워도 전체 화면이 목업 데이터로 그대로 동작합니다.

> ⚠️ **다른 문서와의 정합성**: 위 표는 각 화면을 직접 열어보고 확인한 실제 상태입니다. 앞으로
> 이 표가 또 실제와 어긋나지 않도록, 목업→실연동 전환처럼 눈에 보이는 변화가 생기면 이 표부터
> 갱신해주세요 — README.md의 표는 이 표를 사용자 관점으로 요약한 것이라 함께 갱신이 필요합니다.

---

## 2. 아키텍처 한 장 요약

```
app.py (라우팅 + 전역 CSS)
 └─ pages/1_home.py       — 홈(랜딩)
 └─ pages/2_analyze.py    — STEP1 입력 → STEP2 Workspace(4탭)
 │     └─ ui/market_tab.py     ─┐
 │     └─ ui/brand_tab.py       │  각 탭은 session(dict)을 받아 그리고,
 │     └─ ui/creative_tab.py    │  core/analyzers/*.py 를 호출해 결과를 채움
 │     └─ ui/synthesis_tab.py  ─┘  (Target Insight는 synthesis_tab 안의 subsection)
 └─ pages/3_history.py    — SQLite 이력 조회
 └─ pages/4_settings.py   — API 키 상태 확인

core/scrapers/*   — 실제 수집 (서비스별 config.settings.*_MOCK 플래그에 따라 개별적으로 mock↔실연동 전환)
core/analyzers/*  — AI 판단/추천 (§8 FACT/AI/REC 스키마 공통 사용, insight_synthesizer.build_insight/build_target_insight)
core/exporters/*  — 결과 내보내기 (지금은 소재분석 전용 HTML/Excel/ZIP만 존재)
database/db.py    — analysis_session / function_run (PRD §6-1·§13)

[DEPRECATED, Workspace에서 import/render하지 않음] ui/target_tab.py, core/analyzers/target_recommender.py
— 과거 세션/DB 호환용으로만 코드베이스에 남아있음(§0 16차 개정).
```

**중요한 설계 원칙**: `ui/*_tab.py`는 화면만 그리고, 실제 로직은 항상 `core/analyzers/*.py`
함수 호출로 위임합니다. 그래서 **담당자는 core 쪽 함수 내부만 mock → 실제 구현으로 바꾸면 되고,
화면 코드는 거의 건드릴 필요가 없습니다.**

---

## 3. 모듈 분담 제안

| 파트 | 담당 파일 | 지금 할 일 |
|---|---|---|
| **시장분석** (신규 합류 예정) | `ui/market_tab.py`, `core/scrapers/naver_api.py`(`get_search_volume_trend`, `get_news`) | 검색량 추이·뉴스는 이미 실연동 완료 — §7-1 `search_seasonality`/`reference_sources`/`market_issues`/`upcoming_changes` 추가 및 HTML/Excel 다운로드가 남은 작업 |
| **브랜드분석** (신규 합류 예정 — 지금까지는 본인이 진행) | `ui/brand_tab.py`, `core/analyzers/brand_analyzer.py`, `core/scrapers/{naver_api,naver_ad_api,brand_site,ad_library}.py` | 아래 §4 참고 — 검색량/Meta 광고는 이미 실연동, 홈페이지·Instagram·Gemini 해석이 남은 작업 |
| **소재분석** (미배정, 진행 상황 좋음) | `ui/creative_tab.py`, `core/analyzers/creative_analyzer.py`, `core/scrapers/ad_library.py` | Meta Ads Library 실연동 + 페이지 직접 지정 폴백 + HTML/Excel/ZIP 다운로드까지 완료. 소구포인트(appeal_tags) 태깅은 근거 없는 mock이라 16차 개정에서 완전히 제거함(Gemini Vision으로 교체하지 않음) — 남은 작업은 없음 |
| **종합분석** (미배정) | `ui/synthesis_tab.py`, `core/analyzers/insight_synthesizer.py` | Target Insight subsection은 구현 완료(`build_target_insight`, §7-2) — 남은 작업은 §7-4 SOV/포지셔닝맵/White Space |

> **타겟분석 파트는 더 이상 존재하지 않습니다** (16차 개정) — 독립 탭·독립 담당 영역이 아니라 종합분석 파트의 Target Insight subsection으로 흡수됐습니다. `ui/target_tab.py`/`core/analyzers/target_recommender.py`는 과거 DB 호환용으로만 남아있고 신규 작업 대상이 아닙니다.

각자 자기 파일만 건드리면 되도록 나눠놨기 때문에 **브랜치를 나눠도 병합 충돌이 거의 안 납니다.**
단, `ui/components.py`·`config/theme.py`·`app.py`·`pages/1_home.py`·`pages/2_analyze.py`는
디자인 시스템을 공유하는 파일이라 여러 명이 동시에 건드리면 충돌하기 쉽습니다 — 바꿀 일이 있으면 먼저 알리세요.

> ⚠️ **소재분석 작업은 지금 `feature/creative-analysis`가 아니라 `feature/brand-analysis`
> 브랜치에 들어가 있습니다** (전담자가 배정되기 전까지 임시로 이 브랜치에서 진행됨). 소재분석
> 담당자가 정해지면 `feature/brand-analysis`에서 `feature/creative-analysis`를 새로 따서
> 이어가거나, `main` 머지 후 새로 시작하는 쪽을 미리 정해주세요.

### Git 브랜치 전략 (제안)

```
main                        — 항상 동작하는 상태만 유지 (지금 이 커밋)
├─ feature/market-analysis  — 시장분석 담당 (신규 합류 예정)
├─ feature/brand-analysis   — 브랜드분석 담당 (신규 합류 예정, 현재 소재분석 작업도 여기 포함)
├─ feature/creative-analysis — 소재분석 전담자 배정 시 여기로 분리
└─ feature/synthesis        — 종합분석 담당 (미배정, Target Insight 포함)
```
> `feature/target-analysis` 브랜치는 16차 개정으로 담당 영역 자체가 없어졌습니다(Target은 종합분석에
> 흡수됨) — 기존 브랜치를 강제로 삭제하지는 않았으니, 정리가 필요하면 별도로 확인 후 처리하세요.
각자 브랜치에서 작업 → PR 생성 → 리뷰 후 `main` 머지. `ui/components.py`, `config/theme.py`,
`database/db.py`처럼 여러 명이 공유하는 파일을 바꿀 때만 미리 이야기하고 진행하세요.

---

## 4. 브랜드분석 파트 — 다음 단계 (신규 합류자 인계 예정, 지금까지는 본인이 진행)

각 서비스는 `config/settings.py`의 서비스별 `_MOCK` 플래그(`NAVER_DATALAB_MOCK`/`NAVER_AD_MOCK`/
`APIFY_MOCK`/`GEMINI_MOCK`/`BRAND_SITE_MOCK`)에 따라 개별적으로 실연동 여부가 갈립니다.
진행 상황:

1. ✅ `SETUP_GUIDE.md` 따라 네이버 오픈API/검색광고 키 발급 → `.env`에 입력하는 절차는 정리됨
2. ✅ `core/scrapers/naver_api.py`의 `get_brand_search_volume()` — DataLab `keywordGroups`(상대추이) +
   `core/scrapers/naver_ad_api.py`(RelKwdStat, 절대 검색량·연관검색어) 실연동 완료 (PRD §7-9·§21-10)
3. ⬜ `brand_site.py`의 `crawl_brand_website()` — 아직 목업(`BRAND_SITE_MOCK = True` 고정). 실제
   Playwright 크롤링으로 교체 필요 (PRD §7-3 — 대표 상세페이지 없으면 홈페이지/브랜드스토리 폴백)
4. 🟡 `ad_library.py`의 `fetch_meta_ads()` — Apify 실연동 완료(§21-11). `fetch_instagram_profile()`은
   브랜드명→handle 해석 문제로 아직 목업(§7-10과 동일한 미해결 문제)
5. ⬜ `infer_brand_context()`(`brand_analyzer.py`)와 `core/analyzers/insight_synthesizer.py`의 목업
   문구 생성 — 아직 전부 규칙 기반 템플릿. 실제 Gemini 프롬프트 호출로 교체 필요 (반환 shape
   `insight/source/evidence/confidence`는 그대로 유지). STEP1의 `core/analyzers/recommender.py`가
   Gemini 실연동의 참고 예시가 될 수 있습니다 (구조화된 JSON 응답 스키마 + 실패 시 목업 폴백 패턴).
6. `run_brand_analysis()`의 반환 shape은 바꾸지 마세요 — `ui/brand_tab.py`가 그 shape을 그대로 렌더링하고 있습니다.

---

## 5. [Design History — 1차 리디자인, 현재 지침 아님] "Premium AI Intelligence / Black Monochrome / Minimal Glassmorphism"

> ⚠️ 이 절은 **1차 리디자인 기록**이다. 이후 2차("Luminous Dark", ice blue/violet)와 3차("Brand
> Intelligence Platform / Editorial Technology", flat black + orange, §7 최근 변경 이력 최상단
> 항목)를 거치며 대부분 교체됐다. **현재 Active Design Direction은 §8(Flat Black / Orange
> accent / No gradient·glow·glassmorphism / 작은 radius)와 `config/theme.py`의 실제 코드가
> 기준**이다 — 아래 표의 "Glassmorphism"·"골드"·"ice blue" 관련 서술은 과거 방향이며 지금 코드와
> 다르다. 새로 합류하는 사람은 이 절 대신 §8과 `config/theme.py`를 먼저 확인할 것.

1차 프로토타입(다크+골드, 카드 나열형)이 "전형적인 SaaS 관리자 대시보드"처럼 보인다는 피드백을 받아
전면 리디자인했습니다. 기능/데이터 구조는 전혀 건드리지 않았고 Layout·Typography·Color·Glassmorphism·
Navigation·Cards·Input·Buttons·Iconography만 수정했습니다.

### 5-1. 피드백 대비 적용 요약

| 피드백 항목 | 적용 내용 |
|---|---|
| 1. 전체 컨셉 (Black monochrome / Premium / Editorial) | 배경 `#070707` 고정, 색상 팔레트를 black/white/gray로 통일 |
| 2. 카드로 감싸지 않기 | `st.container(border=True)` 전면 제거. 얇은 상단 구분선(hairline) + 여백으로 위계 표현 (`ui/components.py`의 `module_row`/`render_insight_card`) |
| 3. Background — 순수 CSS, 은은한 depth | 이미지 없이 아주 옅은(4~4.5% 불투명도) radial-gradient 2겹만 사용 (`config/theme.py`) |
| 4. Glassmorphism 스펙 | bg `rgba(255,255,255,0.035)` / border `rgba(255,255,255,0.07)` / `backdrop-filter: blur(20px)` — 요청 범위 그대로 적용, 브랜드 입력 커맨드바 등 실제 위젯이 필요한 곳에만 한정 적용 |
| 5. Typography — 가볍고 정제 | `.streamlit/config.toml`의 `headingFontSizes`/`headingFontWeights`/`baseFontWeight`로 앱 전체 헤딩·본문 폰트를 한 단계씩 축소 |
| 6. Iconography — 이모지 제거 | 📊🎯🧭🖼️🏁🏠🔍🕘⚙ 전부 제거. 사이드바는 Streamlit 내장 Material Symbols 선(line) 아이콘(`:material/home:` 등), 나머지는 텍스트만 사용. (단, PRD §16-2가 정의한 상태 기호 ○●✓△✕🔒은 기능 표기이므로 유지) |
| 7. Hero — eyebrow + headline | "ADetect · Brand Intelligence" eyebrow + "AI insight, in minutes." 헤드라인 + 짧은 설명 1줄로 축소 |
| 8. Brand Input — Command Interface | 카테고리/경쟁사를 접이식(`st.expander`)으로 감추고 브랜드명 입력 + "Analyze →" 중심의 glass surface 하나로 재구성 |
| 9. 주요 분석 기능 — 4개 모듈 | 홈 화면의 기능 소개를 5개 카드 → MARKET/BRAND/CREATIVE/AUDIENCE 4개 에디토리얼 리스트로 변경, 종합분석은 "4개 분석이 쌓이면 자동 제공"이라는 안내 문구로 대체 (Workspace의 실제 5탭 구조·기능은 유지) |
| 10. Layout — 여백 확대 | 본문 최대 폭 1080px 중앙 정렬 + 좌우 2rem 패딩, 섹션 간 여백 확대 |
| 11. Color — neutral | `primaryColor`를 골드에서 오프화이트(`#F2F2F0`)로 변경, 버튼을 white/black 기반으로 재설계. accent color(`#C9A227`)는 FACT/AI/REC 배지처럼 PRD가 요구하는 최소 지점에만 남김 |
| 12. Sidebar — 조용한 내비게이션 | 폭 축소(15rem), active 상태를 회색 박스 대신 얇은 좌측 라인으로 표현 |
| 13-14. 전체 인상 / 기능 변경 금지 | 기능·데이터 구조 변경 없음. `tests/test_smoke.py` 전체 통과 확인 |

### 5-2. 알려진 한계 (브라우저로 직접 확인 필요)

이번 세션에서는 브라우저 자동화 도구를 사용할 수 없어 **실제 렌더링을 시각적으로 캡처해 대조하지
못했습니다.** 대신 Streamlit 컴파일된 프론트엔드 번들에서 실제 DOM 속성(data-testid)을 확인해
CSS를 작성했고, `.streamlit/config.toml`의 테마 값이 정상 로드되는지, 전체 클릭 플로우가 예외 없이
동작하는지는 확인했습니다. `streamlit run app.py` 실행 후 아래를 직접 봐주세요:

- 브랜드 입력 영역의 glass 효과(`backdrop-filter: blur`)가 기대한 만큼 보이는지 (CSS `:has()` 선택자 기반이라 브라우저 호환성에 좌우될 수 있음)
- 사이드바 active 상태의 얇은 라인 표시가 의도대로 보이는지
- 전체적으로 "SaaS 대시보드" 느낌이 충분히 빠졌는지

추가로 다듬을 부분이 있으면 알려주시면 바로 반영하겠습니다.

<details>
<summary>원본 피드백 전문 (참고용, 접힘)</summary>

```
현재 구현된 ADetect의 기능과 데이터 구조는 최대한 유지하고, UI/UX 디자인을 전면적으로 리디자인해줘.

현재 결과물은 기능적으로는 괜찮지만, 전형적인 SaaS 관리자 대시보드처럼 보이고 내가 의도한
프리미엄 AI Intelligence Tool의 느낌이 부족하다.

이번 작업의 최우선 목표는 "기능 추가"가 아니라 "비주얼 퀄리티 개선"이다.

1. 전체 디자인 컨셉: "Premium AI Intelligence / Black Monochrome / Minimal Glassmorphism"
   Apple, Linear, Perplexity 참고. 흔한 SaaS Dashboard처럼 보이면 안 됨.
   키워드: Black monochrome / Minimal / Premium / Sophisticated / Quiet luxury /
   AI Intelligence / Glassmorphism / Editorial / Spacious / Subtle depth / High-end technology

2. 가장 중요한 디자인 원칙: 모든 요소를 카드로 감싸지 않는다.
   피할 것: 모든 영역 1px border, 동일한 카드 형태 반복, 강한 그림자/glow, 과도한 gradient,
   네온, 컬러풀한 UI, 이모지 아이콘, 큰 노란색 버튼, 너무 두꺼운 폰트, 일반적인 Admin Dashboard.
   대신: 여백, 얇고 거의 안 보이는 경계, 반투명 glass surface, subtle blur, 아주 약한 빛과
   깊이감, 흰/회색 중심 monochrome, 필요한 곳에만 accent color.

3. Background: 이미지 사용 안 함. 순수 CSS 기반 매우 어두운 black(#050505~#0A0A0A) +
   아주 미세한 radial gradient depth. 빛 효과가 장식이 되면 안 됨.

4. Glassmorphism: background rgba(255,255,255,0.025~0.05), border rgba(255,255,255,0.08 이하),
   backdrop-filter blur(16~24px), shadow 매우 약하게. "반짝이는 유리판"이 아니라 살짝 뜬 반투명 surface.

5. Typography: 큰 제목을 무조건 굵고 크게 만들지 않음. eyebrow/label → headline → description
   → (필요시) 큰 숫자 순의 위계. font-weight 전체적으로 한 단계 낮춤. 특히 "주요 분석 기능",
   "시장분석", "타겟분석"이 너무 크고 무거움.

6. Iconography: 이모지(📊 🎯 🧭 🖼️ 🏁 등) 전부 제거. Lucide/SVG/아주 얇은 line icon 또는
   아이콘 없이 typography만 사용. 아이콘은 보조 요소일 뿐 주인공이 아님.

7. Main Hero: 상단을 훨씬 여유 있게. "AI insight, in minutes."를 작은 eyebrow + elegant
   headline 구조로. 설명은 짧고 정제되게, 텍스트 과다 노출 금지.

8. Brand Input 영역: 큰 사각 박스 대신 "AI 분석을 시작하는 Command Interface"처럼. Brand/
   Category/Competitors가 하나의 elegant glass surface 안에 자연스럽게 연결.

9. 주요 분석 기능: 5개 동일 카드 가로 나열 지양. 핵심 4개(시장/브랜드/소재/타겟)를 category
   label + 큰 제목 + 짧은 설명의 Intelligence Module 형태로. 종합분석은 메인 카드에서 빼거나
   분석 완료 후 결과 영역으로.

10. Layout: 카드로 화면을 꽉 채우지 않음. 좌우 padding/섹션 간 여백/카드 간 간격 확대, 콘텐츠
    폭 제한, 빈 공간 적극 활용. "여백이 많은 premium intelligence workspace"처럼.

11. Color: black/white/gray 중심. Primary #050505~#0A0A0A, Surface #101010~#161616,
    Text #F5F5F5, Secondary #8A8A8A, Border white 5~8% opacity. Accent 최소화, 강한 yellow
    버튼 제거, 버튼도 white/black 기반 neutral.

12. Sidebar: 더 얇고 미니멀하게. 이모지(🏠🔍🕘⚙) 대신 Lucide line icon 또는 텍스트. 화면의
    주인공이 아니라 조용한 navigation. width 축소, active state는 subtle highlight로.

13. 전체적인 시각적 인상: "일반적인 대시보드가 아니다", "고급 Intelligence Platform이다",
    "화려하지 않은데 비싸 보인다", "정보가 많지 않아도 공간과 typography로 완성도가 느껴진다",
    "검은색+카드+노란 버튼 SaaS 화면처럼 보이면 안 된다."

14. 중요: 기능을 새로 추가하지 않는다. 현재 구현된 기능과 데이터 구조는 유지한다. Layout/
    Typography/Spacing/Color/Glassmorphism/Navigation/Cards/Input/Buttons/Iconography만 수정.
    reference image의 넓은 여백/black monochrome/subtle glass/restrained lighting/minimal
    typography/premium technology aesthetic/low visual noise를 가장 중요하게 반영.
```

</details>

---

## 6. 마일스톤 제안

| 단계 | 목표 | 상태 | 참고 |
|---|---|---|---|
| **M0** | 뼈대 + 프로토타입 — 4개 기능이 눈에 보이고 클릭 가능 (16차 개정 전에는 5개였음) | ✅ 완료 | |
| **M1** | 브랜드분석 실제 API 연동 (네이버+Apify+Gemini) | 🟡 부분 완료 — 네이버·Apify는 실연동, Gemini(brand_context/해석 문구)는 아직 | PRD §22 Phase 0~1 |
| **M2** | 시장분석 실제 API 연동 | 🟡 부분 완료 — 검색량·뉴스는 실연동, 계절성/참고자료/이슈 필드는 아직 | PRD §22 Phase 1~2 |
| ~~M3~~ | ~~타겟분석 Gemini 프롬프트 연동~~ — **폐기(16차 개정)**. Target Insight는 종합분석(M4)의 일부로 구현 완료 | ⚫ 폐기 | §0 |
| **M4** | 소재분석·종합분석 신규 구현 | 🟡 부분 완료 — 소재분석은 Meta 실연동+다운로드까지 완료(appeal_tags는 근거 없는 mock이라 재도입 없이 완전 제거), 종합분석은 Target Insight 구현 완료, SOV/포지셔닝맵은 미착수 | PRD §22 Phase 2~3 |
| **M5** | Excel/HTML/ZIP 내보내기, 이력 재진입 | 🟡 부분 완료 — 소재분석 다운로드만 완료, 나머지 3개 탭 다운로드·이력 재진입은 아직 | PRD §22 Phase 3~4 |

---

## 7. 최근 변경 이력 (요약)

각 세션마다 이 문서를 계속 갱신하지 못하면 실제 코드와 계획서가 어긋나기 쉬워서, 굵직한 변경만
간단히 누적 기록합니다. 자세한 내용은 `git log`/커밋 메시지를 참고하세요.

- **2026-09-20**: **4차 리뉴얼 — "Cinematic Editorial Intelligence" (Home 시각 경험 전면 개편)**.
  3차 리뉴얼("Brand Intelligence Platform / Editorial Technology")이 기술적으로는 정돈됐지만
  "잘 만든 SaaS 대시보드"처럼 보인다는 피드백에 따라, Home을 "브랜드 존재감이 있는 Cinematic
  Brand Experience"로 재구성했다. **기능/IA/analyzer·scraper 로직/DB 스키마/Export 로직은 전혀
  변경하지 않음** — 이번 리뉴얼은 Home visual experience 중심이다. 주요 변경:
  (1) 사용자가 확정한 공식 Hero asset(`ui/assets/home/background.png`, WebP 변환본 병행 보관)을
  Hero의 atmospheric background + primary visual anchor로 채택 — `ui/hero.py`가 base64 data URI로
  인라인 임베드(Streamlit이 임의 정적 파일을 URL로 서빙하지 않아 fragile한 static-serving 설정
  대신 선택, §8 Hero Master Asset), (2) Color System 재검증 — `accent_surface`가 `#B23A1F`(rust/
  brown 톤, R/G 채널 비율이 forbidden 계열과 가까웠음)에서 `#CD351D`(WCAG AA 4.5:1 이상 재확인)로,
  `text_faint`가 대비 3.5:1(AA 미달)이던 `#5F6670`에서 4.88:1인 `#797C84`로 교체, (3) Gradient/Glow
  전면 금지 원칙을 "Home의 large-scale atmospheric visual(Hero/Manifesto/Final CTA)에 한해서만
  허용, UI 컴포넌트는 여전히 금지"로 완화(§8 재정의), (4) Intelligence Pipeline을 Hero의 Main
  Illustration에서 secondary compact rail(가로 index, moving-line 애니메이션 제거)로 축소,
  (5) Market/Brand/Creative/Synthesis 4개 Story section에 서로 다른 composition(split vs
  full-width banner) + 거대 배경 숫자(§8) 적용, Synthesis에 가장 dramatic한 atmosphere glow,
  (6) 기존 "Inside the Workspace" 브라우저 프레임 mockup을 제거하고 "SAMPLE OUTPUT" 라벨 +
  포스터형 큰 타이포그래피의 Editorial Product Showcase로 교체 — 실제 기능처럼 보이지 않게
  `pointer-events:none` 적용, (7) Home 전용 wide container(`home_page_marker()`) 도입 — Workspace
  (Analyze/History/Settings)의 1200px 규칙은 그대로 유지, (8) **버그 수정**: 과거
  `pipeline_wrap_marker()`가 존재하지 않는 data-testid(`column`, 실제는 `stColumn`)를 셀렉터로
  써서 조용히 무효화돼 있던 것을 발견 — 신규 `scene_marker()` 범용 헬퍼로 교체하며 함께 정리.
  `pytest tests/test_smoke.py -v` 7개 전체 통과, `streamlit run app.py` 기동 후 Home(1440/1280/
  768/390 대응 확인)·Analyze(Workspace 4탭)·History·Settings를 브라우저로 직접 확인 — 회귀 없음.
- **2026-09-19**: **PRD 16차 개정 — Information Architecture 변경** (PRD.md §0). 5개 독립
  기능(시장/타겟/브랜드/소재/종합) → **4개 Primary Analysis Function**(시장/브랜드/소재/종합)으로
  축소, Target은 독립 탭·독립 `function_run`이 아니라 **종합분석 탭 안의 Target Insight
  subsection**으로 흡수(`core/analyzers/insight_synthesizer.build_target_insight`, 근거 없는
  인구통계 생성 금지, 근거 부족 시 정직하게 안내). **소구포인트(appeal_tags) 완전 제거** — 기존
  구현이 `seeded_random()` 기반 mock이라 실제 광고 해석이 아니었음(§0 Guardrail). 주요 변경:
  (1) Home Hero의 Intelligence Pipeline을 4단계로 축소하고 `pipeline_wrap_marker()`로 오른쪽
  column에 anchor(최대폭 340px, Headline과 경쟁하지 않게), Analysis Story의 독립 AUDIENCE
  section 제거, (2) Primary 버튼 텍스트 대비 개선 — `accent`(#FF4D2E)는 line/dot 전용으로 남기고
  넓은 CTA 배경은 `accent_surface`(#B23A1F, 더 어두운 톤) + `text_on_accent`(#FFF8F4)로 분리해
  WCAG AA(~6:1) 확보, (3) Creative 표 정보 위계를 브랜드→소재ID→헤드라인→CTA→포맷→운영일수→노출
  지면(Placement, secondary·1줄 압축) 순으로 재배치하고 HTML export에도 동일 반영, (4) Workspace
  1차 탭을 4개(`01 시장분석/02 브랜드분석/03 소재분석/04 종합분석`)로 축소, Brand Context Header에서
  "타겟 미확정" 문구 제거, (5) Top Navigation이 본문을 가리던 문제를 `--nav-height`/
  `--content-top-gap` CSS 변수로 근본 수정(페이지별 임시 여백 추가 방식 금지), (6)
  `tests/test_smoke.py`를 새 흐름(Market→Brand→Creative→Synthesis)으로 재작성 + Target Insight/
  Appeal 제거 회귀 테스트 추가. `ui/target_tab.py`/`core/analyzers/target_recommender.py`와 DB의
  `target_status`/`recommended_target`/`confirmed_target` 컬럼은 destructive migration 없이
  유지(과거 세션 호환), 단 신규 UI 어디에서도 호출하지 않음. `pytest tests/test_smoke.py -v`
  7개 전체 통과, 실 API 키(Naver/Apify) 연동 상태에서 Home/Workspace/Creative/Synthesis 화면을
  브라우저로 직접 확인.
- **2026-09-18 (2차)**: 3차 리뉴얼 — "Brand Intelligence Platform / Editorial Technology Product".
  2차 리뉴얼(바로 아래 항목, ice blue/soft violet 3-accent)이 "전형적인 AI SaaS 데모"처럼 보인다는
  피드백을 받아 교정. Blue glow/orb/gradient/glassmorphism/backdrop-filter를 전부 제거하고 flat
  black 배경으로 전환, 브랜드 accent를 orange-red(#FF4D2E)로 교체(ice blue는 semantic data color로
  격하 — 진행중/primary chart 전용). Border radius를 4~9px로 축소. 주요 변경: (1) Hero를 12-col(7:5)
  grid로 재배치하고 blue orb를 IntelligencePipeline(HTML/CSS 기반 01~05 단계 다이어그램)으로 교체,
  (2) 브랜드 입력을 별도 rounded 카드가 아니라 Hero 안의 flat horizontal command bar로 통합, (3)
  Workspace 상단을 "한 줄 status 나열" → 7:5 grid(BrandContextHeader + 01~05 Vertical Analysis
  Status Index)로 재설계, (4) Analysis 탭 순서를 Market→Audience→Brand→Creative→Synthesis로 재배치
  (게이트 로직·실행 순서는 변경 없음 — UI 표시 순서만 조정), (5) KPI를 vertical divider 기반 full-width
  균등 grid로, (6) Insight 카드에서 "AI INTERPRETATION" 배지를 제거하고 INSIGHT 라벨 + evidence
  chip + 하단 "AI generated" meta로 축소, (7) `ui/illustrations.py`의 5개 SVG를 gradient/glow 없는
  muted line + 단일 orange 강조점으로 재작업, (8) `st.tabs` 커스텀 CSS를 `[data-baseweb=...]`(추정)
  대신 실제 확인된 공식 `data-testid`(`stTabs`/`stTab`)로 교체. `.streamlit/config.toml`의
  `headingFontWeights`가 문자열이라 TypeError로 조용히 실패하던 기존 버그도 함께 수정(정수로 교정).
  기능/데이터 로직 변경 없음, `tests/test_smoke.py` 전체 통과. 이 세션에서는 브라우저 확장 연결이
  끊겨 있어 실브라우저 스크린샷 검증은 하지 못했다 — 코드/토큰 리뷰로 대체.
- **2026-09-18**: 대규모 UI/UX 리뉴얼 — "Premium AI Intelligence / Cinematic Editorial / Luminous Dark".
  1차 리디자인(§5, 골드 계열 black monochrome)에서 한 단계 더 나아가 dark + ice blue/soft cyan/soft
  violet 3-accent 팔레트로 전환. Framework Audit 결과 Streamlit 유지 결정(설치된 1.63이 `st.navigation
  (position="top")`/`st.segmented_control`/`st.dialog`를 이미 공식 지원 — `requirements.txt` 최소버전
  `>=1.42`로 상향). 주요 변경: (1) 사이드바 내비게이션 → 공식 Top Navigation(`app.py`, `st.logo`),
  (2) `config/theme.py` 디자인 토큰 전면 재정의 + 반응형(1280/1024/768/390) 규칙 추가, (3) 홈 전체를
  Hero/Value Prop/5개 Story Section(시장→타겟→브랜드→소재→종합)/Product Preview/CTA 구조로 재구성
  (`pages/1_home.py`, `ui/hero.py`), (4) 오리지널 abstract SVG 일러스트 세트 신규 추가(`ui/illustrations.py`,
  레퍼런스 자산 비복제), (5) `ui/components.py`에 Metric/InsightBlock/StatusBadge/BrandContextBar/
  FeatureStory/EmptyState 등 재사용 컴포넌트 확충, (6) Workspace에 Brand Context Bar 도입 및 탭 스타일
  절제, (7) History를 row 기반 리스트 + Workspace 재진입 버튼으로, Settings를 상태 배지 기반으로 개선.
  기능/데이터 스키마/analyzer·scraper 로직은 전혀 변경하지 않음 — `tests/test_smoke.py` 전체 통과 확인.
  알려진 한계: History 재진입은 브랜드 컨텍스트만 복원하고 기능별 결과 자동 복원은 미구현
  (`save_function_run()`이 어디서도 호출되지 않는 기존 프로토타입 상태, 이번 리뉴얼 범위 밖).
- **2026-09-13**: STEP1 확인화면 UX 개선(문구/로딩 표시/경쟁사 태그 색상/체크박스 기본값/여백),
  소재분석에 브랜드별 수집 진행상황 표시 + Meta 페이지 자동 매칭 실패 시 URL/페이지명 직접 지정
  폴백 추가. `_gemini_recommend()`가 `lru_cache`로 실패(`None`)까지 영구 캐시해 한 번 실패한
  브랜드가 그 프로세스 안에서 계속 목업으로만 나오던 버그 수정(성공한 결과만 캐시하도록 변경).
  Streamlit 기본 "Deploy" 버튼이 안 가려지던 CSS 누락 수정. `SETUP_GUIDE.md`/`.env.example`에
  이미 발급받은 키를 빠르게 채워 넣는 빠른 참고표 추가.
- 이전: Meta Ads Library/네이버 검색광고 실연동, STEP1 Gemini 추천 실연동, 소재분석 HTML/Excel/ZIP
  내보내기, 홈 화면 히어로 이미지, Black Monochrome 리디자인(§5) — 커밋 `4addcfc`/`774d4cc` 참고.

---

## 8. Active Design Direction (Source of Truth)

이 절이 지금 유효한 디자인 지침의 유일한 출처다. §5(1차 리디자인)·2차("Luminous Dark")·3차
("Brand Intelligence Platform / Editorial Technology")는 모두 Design History일 뿐 지금 코드와
다르다 — 실제 값은 항상 `config/theme.py`/`.streamlit/config.toml`을 확인한다.

* **컨셉**: Cinematic Editorial Intelligence (4차 리뉴얼, 2026-09-20)
* **Home과 Workspace의 역할을 분리한다**(가장 중요한 원칙):
  - **Home**(`pages/1_home.py`): Cinematic Brand Experience — 웅장함/브랜드 존재감/atmospheric
    depth를 우선한다. `home_page_marker()`가 심어진 동안만 wide container(1600px)가 적용된다.
  - **Workspace**(Analyze/History/Settings): Functional Intelligence Product — 데이터 가독성이
    최우선이다. 1200px container, 장식 없음, 3차 리뉴얼 원칙을 그대로 유지한다.
  - 같은 토큰(색/타이포)을 공유하지만, decoration(gradient/glow/큰 typography)은 Home에만
    허용한다. Home의 dramatic visual language를 Workspace 데이터 화면까지 확장하지 않는다.
* **배경**: Flat Black(`#050506`~`#0B0B0D` 3단계) 기반. 이미지/gradient depth는 Home의
  large-scale atmospheric visual(Hero/Manifesto/Final CTA)에만 허용 — "Flat Black foundation +
  Controlled Luminous Depth"
* **Hero Master Asset**: `ui/assets/home/background.png`(+ `background.webp`, 인라인 delivery용
  25KB 압축본) — 사용자가 확정한 공식 Hero visual. Home Hero에서만 쓰고, 카드/보더/그림자로
  감싸지 않으며, 다른 section에서 재사용하거나 비슷한 CSS 장식으로 재현하지 않는다. `ui/hero.py`의
  `render_hero_visual()`이 유일한 렌더 지점이다.
* **Accent**: Clean vermilion/red-orange(`#F0462C`) — active nav/key action/section index/
  important highlight/selected state 등 **좁은 면적에만**. 넓은 CTA 배경처럼 면적이 넓은 곳은
  더 어두운 `accent_surface`(`#CD351D`) + 밝은 텍스트(`text_on_accent`, `#FFF8F4`)를 쓴다
  (WCAG AA 4.5:1 이상 확인, 4차 리뉴얼). `accent_hot`(`#FF3B1F`)/`accent_soft`(`#FF6542`)는 Home
  atmosphere 전용 — UI 컴포넌트에는 쓰지 않는다.
  - **Guardrail**: burnt orange/rust/brown/gold 계열(예: `#B23A1F`, `#A84A20`, `#C05A25`)은 쓰지
    않는다 — G/B 채널이 높아 "탁한 갈색"으로 보인다는 피드백으로 4차 리뉴얼에서 전면 교정했다.
    새 accent 값을 고를 때는 R 채널이 확실히 우세하고 브라우저에서 실제 검정 배경 위에 렌더링해
    확인한다.
* **Gradient/Glow**: 전면 금지가 아니라 **범위를 제한**한다.
  - 허용: Home Hero(background.png)/Manifesto/Story의 `.is-dramatic` banner/Final CTA처럼
    large-scale atmospheric visual. `filter: blur(60px)` 이상 + opacity 0.1~0.35 수준의 diffuse
    glow만 — "light in space"여야지 "neon gaming UI"처럼 보이면 실패다.
  - 금지: 버튼/입력/테이블/카드/metric 등 UI 컴포넌트의 gradient·glow. Workspace 전체.
* **Radius**: 작게 유지(4/6/9px 토큰) — 큰 radius는 SaaS 대시보드 인상을 준다
* **우선순위**: Grid → Typography → Spacing → Information hierarchy → Data → Color → Decoration
  (Decoration은 항상 마지막)
* **Navigation**: `st.navigation(position="top")` 공식 API. 본문 시작 위치는 `--nav-height`/
  `--content-top-gap` CSS 변수로 계산(`calc(var(--nav-height) + var(--content-top-gap))`) —
  페이지별로 임시 여백(`st.write("")` 등)을 추가하는 방식은 금지한다
* **Iconography**: 이모지 금지. PRD §16-2 상태 기호(○●✓△✕🔒)는 기능 표기이므로 예외
* **Contrast**: 넓은 accent 면적 위 텍스트는 항상 WCAG AA(4.5:1 이상, 가능하면) 확인 후 확정 —
  "느낌상 괜찮아 보임"으로 판단하지 않는다(16차 개정 CTA 대비 수정, 4차 리뉴얼 accent_surface/
  text_faint 재검증이 실제 사례)
* **Sample/Demo 구분**: Home의 Sample Output(§7-11 실제 기능과 무관한 예시 섹션)은 반드시
  "SAMPLE OUTPUT" 라벨 + `pointer-events:none`으로 실제 기능과 시각적으로 구분한다 — 브라우저
  프레임/대시보드 mockup처럼 실제 앱 화면을 흉내 내지 않는다(Editorial Product Showcase 형태,
  `ui/components.sample_showcase()`)
* **Layout hook**: Home cinematic scene(Hero/Manifesto/Story/Showcase/Final CTA)은
  `config.theme.scene_marker()`로 실제 `stVerticalBlock`에 CSS `:has()` 훅을 건다. 새 훅을 추가할
  때는 Streamlit의 실제 `data-testid`(`stColumn`/`stVerticalBlock`/`stElementContainer` 등,
  버전마다 바뀔 수 있음)를 브라우저 DOM에서 먼저 확인한다 — 과거 `pipeline_wrap_marker()`가
  존재하지 않는 `column`을 셀렉터로 써서 조용히 무효화돼 있던 사례가 있다(4차 리뉴얼에서 발견/수정)

새 화면/컴포넌트를 만들 때 이 목록과 충돌하면 이 목록이 우선한다. 이 목록 자체를 바꾸는 변경은
§7 최근 변경 이력에도 함께 기록한다.
