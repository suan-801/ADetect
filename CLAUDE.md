# 작업 지침

1. **답변/보고는 한국어.** 코드/식별자/커밋 메시지 등은 필요한 경우 영어를 그대로 사용해도 되지만, 사용자에게 설명하는 텍스트는 한국어를 사용한다.

2. **PRD.md를 Product Behavior의 source of truth로 취급한다.** 화면·데이터 스키마·게이트 조건에 대해 기억(과거 세션)과 PRD.md가 다르면 PRD.md를 따르고, PRD.md 상단의 최신 개정 절(예: "§0 16차 개정")을 먼저 확인한다 — 개정 절은 그 아래 본문보다 항상 우선한다.

3. **아래 항목이 바뀌면 같은 커밋에서 반드시 PRD.md / README.md / docs/PROJECT_PLAN.md를 함께 확인·갱신한다**:
   - Primary Analysis stage(현재 4개: Market/Brand/Creative/Synthesis)
   - User Flow (게이트 조건, 탭 순서/개수)
   - Output schema (§7 필드, §8 FACT/AI/REC 분류)
   - Gate dependency (어떤 기능이 완료돼야 다음이 열리는지)
   - Export 구조 (§14 Excel 시트 번호/컬럼, HTML 리포트 구조)
   - UI navigation (Workspace 탭 목록, Status Index 항목 수)
   코드만 고치고 문서를 과거 구조로 남겨두지 않는다 — 문서가 실제와 어긋나면 다음 세션이 옛 구조를 다시 만들 위험이 있다.

4. **현재 사용자-facing Top-level flow는 4단계다: Market → Brand → Creative → Synthesis.** Target은 독립 탭·독립 `function_run`이 아니라 **Synthesis 결과 안의 Target Insight subsection**이다(`core/analyzers/insight_synthesizer.build_target_insight`). `ui/target_tab.py`/`core/analyzers/target_recommender.py`와 DB의 `target_status`/`recommended_target`/`confirmed_target` 컬럼은 과거 세션 호환을 위해 코드베이스에 남아있을 수 있지만, 신규 UI 어디에서도 import/render/생성하지 않는다 — `recommend_target()`은 `seeded_random()` 기반 mock이므로 재사용 금지.

5. **Mock/random 데이터를 실제 분석 결과처럼 사용자에게 노출하지 않는다.** 과거 소구포인트(appeal_tags) 기능이 이 원칙을 어긴 사례였다 — `seeded_random()`으로 태그를 뽑아놓고 화면에는 확정 분석 결과처럼 보여줬다. 완전히 제거했고 재도입 조건은 PRD.md의 해당 절(Appeal Point 재도입 조건) 참고. 새 기능을 붙일 때도 "이 숫자/라벨이 실제로 무엇에서 나왔는가"를 먼저 확인한다.

6. **AI classification은 `source`/`evidence`/`confidence`가 없으면 확정 결과처럼 표시하지 않는다** (§8 FACT/AI/REC 스키마). `insight_synthesizer.build_insight()`가 만드는 shape을 그대로 따른다.

7. **불확실하면 강제로 label을 선택하지 않는다.** `insufficient_data`/`unknown`/`not_available`/`channel_not_found` 등 명시적인 fallback을 쓴다. 특히 연령/성별 등 세그먼트 인구통계처럼 지금 데이터 모델에 없는 근거를 요구하는 값은 임의로 지어내지 않는다 — `build_target_insight()`가 그 기준 구현이다.

8. **Visual guideline** (docs/PROJECT_PLAN.md §8 Active Design Direction에 상세, 4차 리뉴얼 "Cinematic Editorial Intelligence"): Flat Black · Clean Vermilion Accent(좁은 면적) · No decorative gradient abuse · No UI glow abuse · No glassmorphism · No large rounded card · Grid > Typography > Spacing > Data > Decoration.
   - **Home과 Workspace의 역할을 구분한다.** Home(`pages/1_home.py`)은 cinematic/editorial(웅장한 typography, large-scale atmospheric gradient/glow 허용)이고, Workspace(Analyze/History/Settings)는 functional/data-dense(장식 없음, 3차 리뉴얼 원칙 유지)다. Home의 dramatic visual language를 Workspace 데이터 화면까지 확장하지 않는다.
   - **Home은 2026-09-20부로 Hero 단일 화면이다.** 과거의 Manifesto/Product Story(Market·Brand·Creative·Synthesis 4개 section)/Sample Output/Final CTA scene은 전부 제거했다 — 다시 추가하지 않는다. Home의 유일한 실제 interactive 영역은 Hero 안의 Brand Input + CTA뿐이다.
   - Gradient/Glow는 전면 금지가 아니라 Home Hero의 large-scale atmospheric visual에만 제한적으로 허용한다 — 버튼/입력/테이블/카드 등 UI 컴포넌트에는 여전히 금지.
   - **Home Hero는 지정된 `ui/assets/home/background.png`를 visual source of truth로 사용**하며, 임의의 대체 AI visual을 새로 만들거나 다른 section에서 재사용하지 않는다(`ui/hero.py`가 유일한 렌더 지점).
   - Orange accent가 burnt orange/rust/brown(예: `#B23A1F` 계열, G/B 채널이 높아 탁하게 보임)으로 보이지 않는지 브라우저에서 실제 검정 배경 위에 렌더링해 확인한다.

9. **넓은 accent 배경 위 텍스트는 항상 대비(contrast)를 확인한다.** "느낌상 괜찮아 보인다"로 판단하지 않는다 — 작은 텍스트 기준 WCAG AA(4.5:1 이상)를 목표로 하고, 필요하면 배경(`accent_surface`)과 강조 인디케이터(`accent`)를 분리한다.

10. **코드 수정 후 검증 필수**: `pytest tests/test_smoke.py -v` 통과, `streamlit run app.py` 정상 기동, 주요 화면(Home/Workspace/변경한 탭)의 Smoke flow 확인. API 키가 없는 Mock Mode에서도 UI가 깨지지 않아야 하며, Mock 데이터는 화면에 SAMPLE임을 명시한다.

11. **Creative Analysis는 현재 Reference Implementation이다** (`ui/creative_tab.py`/`core/analyzers/creative_analyzer.py` — Meta 실연동+HTML/Excel/ZIP 다운로드까지 end-to-end 완료). Market/Brand/Synthesis는 UI/UX skeleton 단계이며(각 파일 상단의 "IMPLEMENTATION CONTRACT" 참고), Claude가 요청받지 않은 실제 분석 알고리즘·새 외부 API 연동을 임의로 구현하지 않는다 — 각 기능은 별도 담당자가 개발할 영역이다. 해당 기능 담당자가 개발을 시작할 때는 Creative의 상태/오류/진행(st.status)/결과/다운로드 패턴(§18 공통 컴포넌트 포함)을 참고하되, 기능 고유 데이터 구조는 항상 PRD.md를 따른다. **Mock data(예: `seeded_random()`, `rng_bool()`, `infer_brand_context()`)는 layout verification/테스트 fixture용이지 production business logic reference가 아니다** — 실제 구현 시 그대로 옮기지 않는다.
