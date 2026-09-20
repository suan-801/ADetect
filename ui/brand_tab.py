"""브랜드분석 탭 — PRD §7-3·§7-11-(3)·§16-3. 자사+경쟁사 통합 스키마.

★ BRAND IMPLEMENTATION CONTRACT (담당: 브랜드분석 파트, 백엔드 포함)

현재 상태 — 부분 실연동: `core/analyzers/brand_analyzer.run_brand_analysis()`가 오케스트레이션을
담당한다. 브랜드 검색량(`naver_api.get_brand_search_volume`)·Meta 광고 요약(`ad_library.
fetch_meta_ads`)은 키가 있으면 이미 실제 데이터다. `brand_site.crawl_brand_website()`(항상
목업, `BRAND_SITE_MOCK=True` 고정)·`ad_library.fetch_instagram_profile()`(브랜드명→handle
해석 문제 미해결)·`brand_analyzer.infer_brand_context()`/AI 해석 문구(아직 Gemini 미연동, 전부
규칙 기반 템플릿)는 실제 로직으로 교체 필요.

Required input: session["brand_name"], session["competitors"], 선택 수집 옵션 4개
(collect_instagram/youtube/naver_sa/news).
Required output(PRD §7-3): run_brand_analysis()의 반환 shape(own/competitors/brand_context/
comparison_insight)을 바꾸지 말 것 — ui/brand_tab.py가 이 shape을 그대로 렌더링한다.
Required states: 완료/부분 실패/전체 실패(§11) — 지금은 자사 수집 실패만 전체 실패로 처리한다.
brand_analyzer._analyze_single_brand()의 `media_operation_matrix_row["naver_sa"/
"naver_brand_search"/"youtube_channel"]`은 `rng_bool()`(seeded_random 기반)로 항상 채워지며
API 키 유무와 무관한 UI 스켈레톤 검증용 placeholder다 — 실제 네이버 SA/브랜드검색 운영 여부
조회로 교체 필요(§16 Guardrail 참고).

Reference pattern: `ui/creative_tab.py`/`core/analyzers/creative_analyzer.py` — Gemini
실연동 예시는 `core/analyzers/recommender.py`(구조화된 JSON 응답 스키마 + 실패 시 목업 폴백).

Do not:
- Workspace 1차 탭 순서를 바꾸지 않는다.
- source/evidence/confidence 없는 AI 판단을 확정 결과처럼 보여주지 않는다(§8).
- rng_bool()/infer_brand_context() 같은 seeded_random mock 로직을 실제 판단 근거로 재사용하지
  않는다 — UI 골격 검증용일 뿐이다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import settings
from core.analyzers.brand_analyzer import run_brand_analysis
from core.scrapers.ad_library import ApifyFetchError
from core.scrapers.naver_api import NaverApiError
from ui.components import feature_intro, metric_row, prototype_notice, render_insight_card, sample_data_notice, status_icon, tab_header


def render(session: dict):
    status = session.get("brand_status", "미실행")
    tab_header("BRAND", "브랜드분석", status_icon(status))
    prototype_notice("프로토타입 화면 · 브랜드 검색량·Meta 광고는 실제 데이터 연동, 홈페이지 분석·Instagram·AI 해석 문구는 연동 예정")

    if status in ("미실행", "전체 실패"):
        feature_intro([
            "브랜드 검색량 (자사+경쟁사) · 홈페이지 분석",
            "브랜드 뉴스 · SNS 프로필",
            "네이버 SA/브랜드검색 · 매체 운영 현황",
        ])
        if status == "전체 실패":
            st.error("브랜드 데이터 수집에 실패했습니다. 네이버 API 키/권한을 확인한 뒤 다시 시도해주세요.")
        with st.expander("선택 수집 옵션"):
            st.checkbox("Instagram", value=True, key="brand_opt_ig")
            st.checkbox("YouTube", value=False, key="brand_opt_yt")
            st.checkbox("네이버 SA/브랜드검색", value=True, key="brand_opt_naver_sa")
            st.checkbox("뉴스", value=True, key="brand_opt_news")

        if st.button("브랜드분석 시작하기", type="primary", key="btn_start_brand"):
            try:
                with st.spinner("자사 및 경쟁사 브랜드 데이터를 수집·분석하는 중..."):
                    # 체크박스 상태를 실제 수집 로직에 전달 — 이전에는 이 값들이 화면에만 있고
                    # run_brand_analysis()에 전달되지 않아, 체크 여부와 무관하게 항상 전체 수집됐다.
                    result = run_brand_analysis(
                        session["brand_name"],
                        session.get("competitors", []),
                        collect_instagram=st.session_state.get("brand_opt_ig", True),
                        collect_youtube=st.session_state.get("brand_opt_yt", False),
                        collect_naver_sa=st.session_state.get("brand_opt_naver_sa", True),
                        collect_news=st.session_state.get("brand_opt_news", True),
                    )
                session["brand_result"] = result
                session["brand_status"] = result["status"]
            except (NaverApiError, ApifyFetchError) as exc:
                # 자사 brand_search_volume/meta_ads 자체가 실패 — §6 브랜드분석 전체 실패 조건
                session["brand_status"] = "전체 실패"
                st.error(f"브랜드 데이터 수집 실패: {exc}")
            st.rerun()
        return

    result = session["brand_result"]
    own = result["own"]
    competitors = result["competitors"]
    ctx = result["brand_context"]

    tabs = st.tabs(["개요", "브랜드 검색량", "홈페이지 분석", "광고 운영", "SNS 분석", "AI 인사이트"])

    with tabs[0]:
        if settings.NAVER_DATALAB_MOCK and settings.APIFY_MOCK:
            sample_data_notice()
        elif settings.BRAND_SITE_MOCK:
            st.caption("브랜드 검색량·광고 소재는 실데이터, 홈페이지 분석·Instagram은 아직 목업입니다.")
        own_sv = own["brand_search_volume"]
        metric_row([
            ("자사 검색량(30일)", f"{own_sv['absolute_30d_pc'] + own_sv['absolute_30d_mobile']:,}", None),
            ("자사 활성 광고", str(own["ad_count"]), None),
            ("비교 경쟁사", str(len(competitors)), None),
        ])
        st.write(
            f"**{own['brand']}** vs 경쟁사 {len(competitors)}개 브랜드를 동일한 기준으로 비교했습니다."
        )
        st.caption(
            f"내부 판단(비노출): brand_type={ctx['brand_type']} · "
            f"conversion_objective={ctx['conversion_objective']}"
        )
        render_insight_card("브랜드 비교 총평", result["comparison_insight"])

    with tabs[1]:
        rows = []
        for b in [own, *competitors]:
            sv = b["brand_search_volume"]
            rows.append({
                "브랜드": b["brand"] + (" (자사)" if b["is_own"] else ""),
                "최근 30일 PC": sv["absolute_30d_pc"],
                "최근 30일 모바일": sv["absolute_30d_mobile"],
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        own_trend = pd.DataFrame(own["brand_search_volume"]["relative_trend"])
        if not own_trend.empty:
            own_trend["date"] = pd.to_datetime(own_trend["date"])
            st.line_chart(own_trend.set_index("date")["search_index"], color="#5AA9E6")

    with tabs[2]:
        sample_data_notice()
        for b in [own, *competitors]:
            label = f"{b['brand']}" + (" (자사)" if b["is_own"] else "")
            with st.expander(label, expanded=b["is_own"]):
                st.write(f"USP 요약: {b['brand_website_facts']['usp_summary']}")
                st.write(f"프로모션: {b['promotion_fact']}")
                render_insight_card("타겟·메시지 해석", b["brand_website_target_message"])
                render_insight_card("프로모션 해석", b["promotion_interpretation"])

    with tabs[3]:
        st.caption(
            "Meta Ads 열만 실제 수집 데이터(활성 광고 수 > 0)입니다 — 네이버 SA/브랜드검색/"
            "YouTube 운영 여부는 아직 실제 조회 로직이 없어 화면 골격 검증용 placeholder입니다."
        )
        rows = []
        for b in [own, *competitors]:
            m = b["media_operation_matrix_row"]
            rows.append({
                "브랜드": b["brand"] + (" (자사)" if b["is_own"] else ""),
                "네이버 SA": "●" if m["naver_sa"] else "X",
                "네이버 브랜드검색": "●" if m["naver_brand_search"] else "X",
                "Meta Ads": "●" if m["meta_ads"] else "X",
                "Instagram 프로필": "●" if m["instagram_profile"] else "X",
                "YouTube": "●" if m["youtube_channel"] else "X",
                "활성 광고 수": b["ad_count"],
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    with tabs[4]:
        sample_data_notice()
        for b in [own, *competitors]:
            ig = b["instagram"]
            label = f"{b['brand']}" + (" (자사)" if b["is_own"] else "")
            if ig.get("not_collected"):
                st.write(f"**{label}**: Instagram 수집이 선택 해제되어 있습니다 (not_collected)")
                continue
            if not ig.get("profile_found"):
                st.write(f"**{label}**: 공식 Instagram 프로필을 찾지 못함")
                continue
            st.write(f"**{label}**: 팔로워 {ig['followers']:,} · 게시물 {ig['posts']:,}")
            st.caption(ig["recent_caption_sample"])

    with tabs[5]:
        for b in [own, *competitors]:
            label = f"{b['brand']}" + (" (자사)" if b["is_own"] else "")
            st.markdown(f"**{label}** 핵심 메시지: {', '.join(b['key_message'])}")

    st.divider()
    c1, c2 = st.columns(2)
    c1.button("HTML 다운로드 — 기능 개발 후 제공 예정", disabled=True, key="dl_html_brand")
    c2.button("Excel 다운로드 — 기능 개발 후 제공 예정", disabled=True, key="dl_excel_brand")
