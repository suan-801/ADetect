# ADetect 개발 계획서 (뼈대/프로토타입 단계)

> 기준 문서: [`PRD.md`](../PRD.md) (15차 개정 — 브랜드 범용화 + 타겟 후추천 구조).
> 이 문서는 "그 PRD를 실제로 어떻게, 누가, 어떤 순서로 만들 것인가"만 다룹니다.

---

## 1. 지금까지 만든 것 (현재 상태, 2026-09-13 갱신)

| 영역 | 상태 | 위치 |
|---|---|---|
| 저장소 뼈대 (폴더 구조, .env, requirements) | ✅ 완료 | 루트 |
| 디자인 시스템 — Black Monochrome / Minimal Glassmorphism, Pretendard | ✅ 완료 (2차 리디자인 + STEP1 UX 피드백 반영) | `config/theme.py`, `.streamlit/config.toml` |
| 홈 화면 (히어로 오브젝트 포함) | ✅ 완료 | `pages/1_home.py`, `ui/hero.py` |
| STEP 1 브랜드 설정 + AI 추천 확인 화면 | ✅ 완료 — **카테고리/경쟁사 추천 Gemini 실연동**(GEMINI_API_KEY 있으면), 실패해도 목업으로 조용히 폴백 | `pages/2_analyze.py`, `core/analyzers/recommender.py` |
| STEP 2 Workspace 5개 탭 골격 + 상태 스트립 | ✅ 완료 | `pages/2_analyze.py` |
| 시장분석 탭 | 🟡 **부분 실연동** — 검색량 추이(DataLab)·뉴스는 NAVER 키 있으면 실동작. `search_seasonality`/`reference_sources`/`market_issues`/`upcoming_changes`(§7-1) 및 다운로드는 아직 미구현 | `ui/market_tab.py`, `core/scrapers/naver_api.py` |
| 타겟분석 탭 (게이트 + 추천/확정/분석 2단계) | 🟡 **부분 실연동** — `interest_keywords`는 네이버 검색광고 키워드도구 API(RelKwdStat) 실연동, `recommended_target`/`ai_persona`는 아직 규칙 기반 목업(Gemini 미연동) | `ui/target_tab.py`, `core/analyzers/target_recommender.py`, `core/scrapers/naver_ad_api.py` |
| **브랜드분석 탭 (자사+경쟁사 통합)** | 🟡 **부분 실연동** — 브랜드 검색량(절대치 포함)·Meta 광고 요약은 Naver/Apify 키 있으면 실동작. 홈페이지 크롤링(Playwright)·Instagram 프로필·`brand_context`/해석 문구는 아직 목업(Gemini 미연동) | `ui/brand_tab.py`, `core/analyzers/brand_analyzer.py`, `core/scrapers/{naver_api,naver_ad_api,brand_site,ad_library}.py` |
| **소재분석 탭** | 🟢 **End-to-End 동작** — Meta Ads Library 실연동(APIFY_API_TOKEN), 자동 페이지 매칭이 부정확할 때 URL/페이지명 직접 지정 폴백, 브랜드별 수집 진행상황(st.status) 표시, HTML/Excel/ZIP 다운로드 완료. `appeal_tags`(소구포인트) 태깅은 아직 규칙 기반 목업(Gemini Vision 미연동) | `ui/creative_tab.py`, `core/analyzers/creative_analyzer.py`, `core/scrapers/ad_library.py`, `core/exporters/*.py` |
| 종합분석 탭 | ⚪ 화면 골격만 (담당자 미배정) | `ui/synthesis_tab.py` |
| 이력 관리 / 설정 화면 | 🟡 골격만 (실제 재진입 기능 없음, API 키 상태 표시만 동작) | `pages/3_history.py`, `pages/4_settings.py` |
| SQLite 이력 저장 (`analysis_session`/`function_run`) | ✅ 완료 | `database/db.py` |

지금 `streamlit run app.py`로 실행하면 **브랜드명 입력 → STEP1 확인(키 있으면 Gemini 실추천) → Workspace 진입 →
시장분석/브랜드분석/소재분석 시작(키 있으면 부분 실연동) → 타겟분석 자동 잠금해제 → 추천/확정/분석**까지
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
 └─ pages/2_analyze.py    — STEP1 입력 → STEP2 Workspace(5탭)
 │     └─ ui/market_tab.py     ─┐
 │     └─ ui/target_tab.py      │  각 탭은 session(dict)을 받아 그리고,
 │     └─ ui/brand_tab.py       │  core/analyzers/*.py 를 호출해 결과를 채움
 │     └─ ui/creative_tab.py    │
 │     └─ ui/synthesis_tab.py  ─┘
 └─ pages/3_history.py    — SQLite 이력 조회
 └─ pages/4_settings.py   — API 키 상태 확인

core/scrapers/*   — 실제 수집 (서비스별 config.settings.*_MOCK 플래그에 따라 개별적으로 mock↔실연동 전환)
core/analyzers/*  — AI 판단/추천 (§8 FACT/AI/REC 스키마 공통 사용, insight_synthesizer.build_insight)
core/exporters/*  — 결과 내보내기 (지금은 소재분석 전용 HTML/Excel/ZIP만 존재)
database/db.py    — analysis_session / function_run (PRD §6-1·§13)
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
| **타겟분석** (미배정) | `ui/target_tab.py`, `core/analyzers/target_recommender.py` | `interest_keywords`는 이미 실연동 — §7-2-a AI Persona 3개 필드 근거 데이터 실측 연결, Gemini 프롬프트로 `recommend_target`/`ai_persona` 교체 |
| **소재분석** (미배정, 진행 상황 좋음) | `ui/creative_tab.py`, `core/analyzers/creative_analyzer.py`, `core/scrapers/ad_library.py` | Meta Ads Library 실연동 + 페이지 직접 지정 폴백 + HTML/Excel/ZIP 다운로드까지 완료. 남은 작업: `appeal_tags`(소구포인트) 태깅을 Gemini Vision으로 교체 |
| **종합분석** (미배정) | `ui/synthesis_tab.py` (신규 작성 필요) | §7-4 SOV/포지셔닝맵/White Space |

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
├─ feature/target-analysis  — 타겟분석 담당 (미배정)
├─ feature/creative-analysis — 소재분석 전담자 배정 시 여기로 분리
└─ feature/synthesis        — 종합분석 담당 (미배정)
```
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

## 5. 디자인 리디자인 — "Premium AI Intelligence / Black Monochrome / Minimal Glassmorphism"

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
| **M0** | 뼈대 + 프로토타입 — 5개 기능이 눈에 보이고 클릭 가능 | ✅ 완료 | |
| **M1** | 브랜드분석 실제 API 연동 (네이버+Apify+Gemini) | 🟡 부분 완료 — 네이버·Apify는 실연동, Gemini(brand_context/해석 문구)는 아직 | PRD §22 Phase 0~1 |
| **M2** | 시장분석 실제 API 연동 | 🟡 부분 완료 — 검색량·뉴스는 실연동, 계절성/참고자료/이슈 필드는 아직 | PRD §22 Phase 1~2 |
| **M3** | 타겟분석 Gemini 프롬프트 연동 | 🟡 부분 완료 — 관심 키워드는 실연동(§21-10), `recommend_target`/AI Persona는 아직 목업 | PRD §22 Phase 1~2 |
| **M4** | 소재분석·종합분석 신규 구현 | 🟡 부분 완료 — 소재분석은 Meta 실연동+다운로드까지 완료(appeal_tags 태깅만 목업), 종합분석은 미착수 | PRD §22 Phase 2~3 |
| **M5** | Excel/HTML/ZIP 내보내기, 이력 재진입 | 🟡 부분 완료 — 소재분석 다운로드만 완료, 나머지 4개 탭 다운로드·이력 재진입은 아직 | PRD §22 Phase 3~4 |

---

## 7. 최근 변경 이력 (요약)

각 세션마다 이 문서를 계속 갱신하지 못하면 실제 코드와 계획서가 어긋나기 쉬워서, 굵직한 변경만
간단히 누적 기록합니다. 자세한 내용은 `git log`/커밋 메시지를 참고하세요.

- **2026-09-13**: STEP1 확인화면 UX 개선(문구/로딩 표시/경쟁사 태그 색상/체크박스 기본값/여백),
  소재분석에 브랜드별 수집 진행상황 표시 + Meta 페이지 자동 매칭 실패 시 URL/페이지명 직접 지정
  폴백 추가. `_gemini_recommend()`가 `lru_cache`로 실패(`None`)까지 영구 캐시해 한 번 실패한
  브랜드가 그 프로세스 안에서 계속 목업으로만 나오던 버그 수정(성공한 결과만 캐시하도록 변경).
  Streamlit 기본 "Deploy" 버튼이 안 가려지던 CSS 누락 수정. `SETUP_GUIDE.md`/`.env.example`에
  이미 발급받은 키를 빠르게 채워 넣는 빠른 참고표 추가.
- 이전: Meta Ads Library/네이버 검색광고 실연동, STEP1 Gemini 추천 실연동, 소재분석 HTML/Excel/ZIP
  내보내기, 홈 화면 히어로 이미지, Black Monochrome 리디자인(§5) — 커밋 `4addcfc`/`774d4cc` 참고.
