# ADetect 레퍼런스 번들

`Claudecode_MarketingOS_student` 워크스페이스에서 **실제로 동작이 검증된** 코드 중, ADetect 개발 시 그대로 이식하거나 참고할 파일들만 뽑아온 사본입니다.
`new_prd.md`(§4 참고 소스 코드)와 함께 다른 환경/다른 개발자에게 전달하세요 — 이 폴더 하나면 원본 워크스페이스 없이도 레퍼런스 코드를 확인할 수 있습니다.

> ⚠️ 이 폴더는 **스냅샷 사본**입니다. 원본(`02_competitor/`, `ad_monitor/`, `_shared/` 등)이 이후 수정돼도 자동으로 반영되지 않습니다. 원본이 크게 바뀌면 이 번들도 다시 복사해서 갱신하세요.

## 폴더 구성

| 폴더 | 파일 | ADetect 대응 모듈 | 이식 포인트 |
|---|---|---|---|
| `scrapers/` | `fetch_competitor_ads.py` | `core/scrapers/ad_library.py` + `core/analyzers/gemini_vision.py` | Apify actor 호출·polling, 이미지/영상 다운로드·분류, Gemini 이미지/영상 분석 프롬프트(USP 4항목 JSON), ffmpeg 키프레임 추출, quota 예외 처리 — **가장 먼저 볼 파일** |
| `scrapers/` | `fetch_ads.py` | 〃 (독립 버전) | `fetch_competitor_ads.py`와 거의 동일한 쌍. UTM 관찰 통합 예시로 참고 |
| `scrapers/` | `competitor_inputs.py`, `ad_inputs.py` | 입력/시드 관리 유틸 | slugify, `_inputs/*.md` 파싱, URL 최초 입력 시 자동 시드 생성 |
| `scrapers/` | `utm_pattern.py` | 자사 분석 — UTM 구조 분석 요구사항 | 랜딩 URL UTM 관찰 + 캠페인/그룹/소재명 규칙 베스트에포트 추정 |
| `exporters/` | `build_dashboard_competitor.py`, `build_dashboard_ad_monitor.py` | `core/exporters/html_builder.py`의 "오프라인 독립 HTML" 부분 | `window.DATA` 인라인 데이터 주입으로 file:// 더블클릭에도 동작하는 정적 HTML 대시보드 패턴 |
| `exporters/` | `period_report.py` | `core/exporters/html_builder.py`의 Jinja2 부분 | `Jinja2 Environment` 세팅, Playwright headless Chromium으로 HTML→PDF 변환 |
| `crawlers/` | `oliveyoung_crawler.py` | `core/scrapers/naver_serp.py` 설계 참고 | Playwright 브라우저 컨텍스트 안에서 내부 API/페이지 직접 조작, cursor 페이징, 트랙별 재시도·백오프 구조. **★ 이름에 속지 말 것**: 이 스크립트는 올리브영 **쇼핑몰에서 팔리는 특정 상품(`goodsNo`)의 리뷰**를 긁는 도구입니다. ADetect에서 "올리브영"을 브랜드로 분석할 때 쓰는 도구가 아닙니다 — 그건 §7-3(브랜드 프로필)·§7-10(광고 페이지 식별) 로직이 담당합니다. 여기서는 **패턴(브라우저 세션 내 내부 API 직접 호출)만** 참고하세요 |
| `lib/` | `env_loader.py` | `config/settings.py` | 외부 의존성(python-dotenv) 없이 stdlib만으로 `.env` 파싱 |
| `lib/` | `requirements_baseline.txt` | `requirements.txt` | Jinja2·playwright·requests 등 이미 검증된 버전 핀 |
| `reference_docs/` | `reference_analysis_method.md`, `analysis_method.md` | `config/prompts.py` 설계 근거 | USP 3항목(User's Problem·Solution·Promotion) + Creative Key Visual + ad_pattern 분석 방법론 원문 |
| `templates_sample/period_v1/` | `index.html.j2`, `deck.html.j2`, `assets/style.css` | `templates/report_template.html` | Jinja2 리포트 템플릿 레이아웃 예시 (compact/deck 2종) |
| `templates_sample/ui_ref.png` | (사용자 제공 최종 UI 레퍼런스 이미지) | `templates/`, §16·§17 | ★ **최종 UI 디자인 레퍼런스** — 입력/진행/결과·이력 4개 화면 목업. 다크 톤(#08080A대) + 골드 포인트 + FACT/AI INTERPRETATION/RECOMMENDATION 3단 구분 표시가 실제로 어떻게 보여야 하는지의 기준 이미지. `app.py`·`html_builder.py`·`templates/report_template.html` 구현 시 이 이미지를 1차 기준으로 삼을 것 (PRD §16의 ASCII 목업보다 이 이미지가 우선) |

## 주의사항 (이식 시 반드시 할 일)

1. **경로 하드코딩 제거**: 원본 파일들은 `ROOT = pathlib.Path(__file__).resolve().parents[2]`처럼 원래 워크스페이스 구조(`02_competitor/`, `ad_monitor/` 등)를 가정한 상대경로가 박혀 있습니다. ADetect의 `core/`, `storage/` 구조에 맞게 전부 다시 계산해야 합니다.
2. **`fetch_competitor_ads.py` vs `fetch_ads.py` 통합**: 두 파일은 거의 동일한 코드의 복붙 쌍입니다. ADetect에서는 하나(`core/scrapers/ad_library.py`)로 합치고 차이점(UTM 통합 등)만 옵션으로 흡수하세요.
3. **시크릿 없음, 하지만 재확인 권장**: 복사 시점에 `apify_api_...` 같은 실제 키 패턴을 스캔해 플레이스홀더뿐임을 확인했습니다. 이후 로컬에서 `.env`로 테스트하며 실수로 실제 키를 커밋하지 않도록 주의하세요.
4. **Meta 전용 로직**: `fetch_competitor_ads.py`/`fetch_ads.py`는 Apify의 `facebook-ads-library-scraper` 액터 기준입니다. Google Ads Transparency Center는 별도 조사가 필요합니다(PRD §11 Phase 0 참고).
