# 작업 지침

1. **답변/보고는 한국어.** 코드/식별자/커밋 메시지 등은 필요한 경우 영어를 그대로 사용해도 되지만, 사용자에게 설명하는 텍스트는 한국어를 사용한다.

2. **PRD.md를 Product Behavior의 source of truth로 취급한다. 현재 최신 기준은 PRD.md §0 18차 개정(프로젝트형 자료 수집 MVP, 2026-09-27)이다.** 화면·데이터 스키마·게이트 조건에 대해 기억(과거 세션)과 PRD.md가 다르면 PRD.md를 따르고, PRD.md 상단의 최신 개정 절부터 확인한다 — 개정 절은 그 아래 본문과 이전 개정(17차·16차)보다 항상 우선한다.

3. **아래 항목이 바뀌면 같은 커밋에서 반드시 PRD.md / README.md / docs/PROJECT_PLAN.md를 함께 확인·갱신한다**:
   - 자료 종류(현재 8개 — `core/projects.SOURCES`)와 프로젝트 흐름
   - User Flow (게이트 조건, 탭 순서/개수)
   - Output schema (18차 `schema_version=3` 결과, §8 FACT/AI/REC 분류)
   - Gate dependency (어떤 기능이 완료돼야 다음이 열리는지)
   - Export 구조 (17차 §0-10의 01_수집정보~11_이전수집대비 시트, HTML 리포트 구조)
   - UI navigation (상단 네비게이션, 프로젝트 내부 탭 목록)
   - 저장·보관 정책 (`core/retention.py` 한도·정리 규칙, 로컬/원격 저장 방식)
   코드만 고치고 문서를 과거 구조로 남겨두지 않는다 — 문서가 실제와 어긋나면 다음 세션이 옛 구조를 다시 만들 위험이 있다.

4. **현재 사용자-facing 흐름은 `프로젝트 → 자료 수집 → 자료 확인·다운로드 → 이력`이다** (`pages/2_analyze.py` → `ui/project_workspace.py`, 데이터 흐름 `core/projects.py`·`core/project_jobs.py`). 사용자는 **8개 독립 자료 종류**(검색 관심도 추이, 월간 검색량·연관 검색어, 관련 뉴스, 공식 페이지, 네이버 검색 화면, Meta 광고, Instagram, YouTube)를 선택해 수집하며, 선택하지 않은 종류는 호출하지 않는다.
   - **Market/Brand/Creative/Synthesis는 신규 화면의 독립 단계가 아니다.** 레거시 호환(과거 세션·v2 결과 읽기) 또는 자료 종류별 내부 분류(`SOURCES`의 세 번째 값, `run_stage`)로만 남아 있다. 4단계 탭 구조를 다시 만들지 않는다.
   - **Target은 신규 UI에서 사용하지 않는다.** `ui/target_tab.py`/`core/analyzers/target_recommender.py`와 DB의 `target_status`/`recommended_target`/`confirmed_target` 컬럼은 과거 세션 호환용으로만 남아 있으며 import/render/생성하지 않는다 — `recommend_target()`은 `seeded_random()` 기반 mock이므로 재사용 금지.
   - 레거시 UI 파일(`pages/3_history.py`, `ui/facts_workspace.py`, `ui/{market,brand,creative,synthesis,target}_tab.py`, `ui/analysis_shared.py`, `ui/job_control.py`)은 상단에 `LEGACY` 주석이 있다. 새 화면에 다시 연결하지 않는다.

5. **Mock/random 데이터를 실제 분석 결과처럼 사용자에게 노출하지 않는다.** 과거 소구포인트(appeal_tags) 기능이 이 원칙을 어긴 사례였다 — `seeded_random()`으로 태그를 뽑아놓고 화면에는 확정 분석 결과처럼 보여줬다. 완전히 제거했고 재도입 조건은 PRD.md의 해당 절(Appeal Point 재도입 조건) 참고. 새 기능을 붙일 때도 "이 숫자/라벨이 실제로 무엇에서 나왔는가"를 먼저 확인한다.

6. **AI classification은 `source`/`evidence`/`confidence`가 없으면 확정 결과처럼 표시하지 않는다** (§8 FACT/AI/REC 스키마). `insight_synthesizer.build_insight()`가 만드는 shape을 그대로 따른다.

7. **불확실하면 강제로 label을 선택하지 않는다.** `insufficient_data`/`unknown`/`not_available`/`channel_not_found` 등 명시적인 fallback을 쓴다. 특히 연령/성별 등 세그먼트 인구통계처럼 지금 데이터 모델에 없는 근거를 요구하는 값은 임의로 지어내지 않는다 — `build_target_insight()`가 그 기준 구현이다.

8. **Visual guideline** (docs/PROJECT_PLAN.md §8 Active Design Direction에 상세, 4차 리뉴얼 "Cinematic Editorial Intelligence"): Flat Black · Clean Vermilion Accent(좁은 면적) · No decorative gradient abuse · No UI glow abuse · No glassmorphism · No large rounded card · Grid > Typography > Spacing > Data > Decoration.
   - **Home과 Workspace의 역할을 구분한다.** Home(`pages/1_home.py`)은 cinematic/editorial(웅장한 typography, large-scale atmospheric gradient/glow 허용)이고, Workspace(프로젝트/설정)는 functional/data-dense(장식 없음, 3차 리뉴얼 원칙 유지)다. Home의 dramatic visual language를 Workspace 데이터 화면까지 확장하지 않는다.
   - **Home은 2026-09-20부로 Hero 단일 화면이다.** 과거의 Manifesto/Product Story(Market·Brand·Creative·Synthesis 4개 section)/Sample Output/Final CTA scene은 전부 제거했다 — 다시 추가하지 않는다. Home의 유일한 실제 interactive 영역은 Hero 안의 Brand Input + CTA뿐이다.
   - Gradient/Glow는 전면 금지가 아니라 Home Hero의 large-scale atmospheric visual에만 제한적으로 허용한다 — 버튼/입력/테이블/카드 등 UI 컴포넌트에는 여전히 금지.
   - **Home Hero는 지정된 `ui/assets/home/background.png`를 visual source of truth로 사용**하며, 임의의 대체 AI visual을 새로 만들거나 다른 section에서 재사용하지 않는다(`ui/hero.py`가 유일한 렌더 지점).
   - Orange accent가 burnt orange/rust/brown(예: `#B23A1F` 계열, G/B 채널이 높아 탁하게 보임)으로 보이지 않는지 브라우저에서 실제 검정 배경 위에 렌더링해 확인한다.

9. **넓은 accent 배경 위 텍스트는 항상 대비(contrast)를 확인한다.** "느낌상 괜찮아 보인다"로 판단하지 않는다 — 작은 텍스트 기준 WCAG AA(4.5:1 이상)를 목표로 하고, 필요하면 배경(`accent_surface`)과 강조 인디케이터(`accent`)를 분리한다.

10. **코드 수정 후 검증 필수**: `pytest tests/test_smoke.py -v`와 `pytest tests -q` 통과, `python -m compileall core database ui pages app.py`, `streamlit run app.py` 정상 기동, 주요 화면(Home/프로젝트/변경한 탭/설정)의 Smoke flow 확인. API 키가 없는 상태와 명시적 SAMPLE 모드(`ADETECT_SAMPLE_MODE=true`)에서도 UI가 깨지지 않아야 하며, SAMPLE 데이터는 화면과 산출물에 SAMPLE임을 명시한다. 실사용 중 키 누락을 SAMPLE로 대체하지 않는다.
   - 테스트는 `tests/conftest.py`가 임시 DB·exports·evidence 경로를 쓰므로 실제 `storage/adetect.db`를 건드리지 않는다. 브라우저 수동 스모크는 `ADETECT_DB_PATH`·`ADETECT_EXPORT_DIR`·`ADETECT_EVIDENCE_DIR`를 별도 경로로 지정해 운영 DB와 분리한다 (README '테스트 DB 분리').
   - 실제 DB의 프로젝트·세션은 사용자 요청 없이 삭제하지 않는다. 삭제·정리 전에는 DB 백업(설정 > DB 백업)을 먼저 안내한다.

11. **유료 기능은 기본 ON이다.** Apify/Gemini는 수집·요약 버튼을 눌렀을 때만 호출하고, 키 누락 또는 확인된 인증/잔액 부족에만 정확히 `토큰 부족. 개발자에게 문의해주세요`를 표시한다. 네트워크 실패·일반 속도 제한을 토큰 부족으로 단정하지 않는다.

12. **저장은 로컬 SQLite(`storage/adetect.db`)와 로컬 파일(`storage/exports`, `storage/evidence`)이 기본이다.** 원격 DB/Storage 어댑터(`database/remote.py`, `core/storage.py`)와 클라우드 배포는 아직 검증 전이므로 완료로 표시하지 않는다. 저장 공간 표시·정리·보유 상태·원본 보호는 `core/retention.py`의 `usage`/`summary`/`cleanup`/`availability`/`pin`을 그대로 쓴다.

13. **요청받지 않은 분석 알고리즘·새 외부 API 연동을 Codex가 임의로 구현하지 않는다.** 18차 범위는 팩트 수집·확인·내보내기이며 타깃 추정·포지셔닝·전략 추천·점유율 해석은 제외다. **Mock data(예: `seeded_random()`, `rng_bool()`, `infer_brand_context()`)는 layout verification/테스트 fixture용이지 production business logic reference가 아니다** — 실제 구현 시 그대로 옮기지 않는다.

14. **Git은 `main` 단일 브랜치로 운영한다** (2026-09-27 사용자 결정). feature 브랜치를 새로 만들지 않고 `main`에 직접 커밋·push한다. 과거 `feature/*` 브랜치는 main에 모두 병합된 뒤 삭제했다.
