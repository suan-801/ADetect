# LEGACY — 현재 런타임(app.py 네비게이션·신규 화면)에서 import/실행하지 않는다. (2026-09-27 검색 확인, PRD §0 18차 개정)
# 신규 UI: app_pages/2_analyze.py → ui/project_workspace.py
# 신규 데이터 흐름: core/projects.py, core/project_jobs.py
# 사용 금지 이유: 16차 개정의 브랜드분석 탭. 18차에서는 공식 페이지·검색 화면·Instagram·YouTube를 독립 자료 종류로 수집한다.
# 새 화면에 다시 연결하지 말 것. 기존 데이터 호환 검토 전까지 삭제하지 않고 보존한다.

"""브랜드별 출처와 미수집 상태를 명확히 보여준다."""
import pandas as pd
import streamlit as st
from core.analyzers.brand_analyzer import run_brand_analysis
from ui.job_control import start, pending
from ui.analysis_shared import notices, insight, downloads
from ui.components import tab_header, status_icon


def render(session):
    status = session.get("brand_status", "미실행")
    tab_header("BRAND", "브랜드분석", status_icon(status))
    if pending(session, "brand"):
        return
    if status in ("미실행", "전체 실패", "취소"):
        session["brand_force"] = st.checkbox("24시간 캐시 무시하고 새로 수집", value=False, key="fresh_brand")
        with st.expander("선택 수집 옵션"):
            ig = st.checkbox("Instagram", value=True, key="brand_opt_ig")
            yt = st.checkbox("YouTube", value=False, key="brand_opt_yt")
            sa = st.checkbox("네이버 SA/브랜드검색", value=True, key="brand_opt_naver_sa")
            news = st.checkbox("뉴스", value=True, key="brand_opt_news")
        if st.button("브랜드분석 시작하기", type="primary", key="btn_start_brand"):
            options = {"collect_instagram":ig,"collect_youtube":yt,"collect_naver_sa":sa,"collect_news":news,
                       "sources":session.get("sources"),"variants":session.get("variants"),
                       "representative_keyword":session.get("representative_keyword"),"generic_keywords":session.get("generic_keywords")}
            start(session, "brand", lambda snapshot: run_brand_analysis(snapshot["brand_name"], snapshot.get("competitors", []), **options),
                  {"brand":session["brand_name"],"competitors":session.get("competitors", []),**options})
        if session.get("brand_result"):
            notices(session["brand_result"])
        return
    result = session["brand_result"]
    notices(result)
    profiles = [result["own"], *result["competitors"]]
    tabs = st.tabs(["개요", "브랜드 검색량", "홈페이지 분석", "광고 운영", "SNS 분석", "AI 인사이트"])
    with tabs[0]:
        st.write(f"{len(profiles)}개 브랜드 · 현재 활성 광고 기준")
        st.dataframe(pd.DataFrame([{"브랜드": p["brand"], "활성 광고": p["ad_count"], "홈페이지": p["brand_website_facts"]["status"]} for p in profiles]), hide_index=True)
    with tabs[1]:
        st.dataframe(pd.DataFrame([{"브랜드": p["brand"], "PC(30일)": p["brand_search_volume"].get("absolute_30d_pc"),
            "모바일(30일)": p["brand_search_volume"].get("absolute_30d_mobile"), "검색 키워드": ", ".join(p["brand_search_volume"].get("variants_used", []))} for p in profiles]), hide_index=True)
        st.caption("빈 수치는 미수집입니다. 인구통계는 검증된 근거가 없어 제공하지 않습니다.")
        for p in profiles:
            with st.expander(p["brand"]):
                df = pd.DataFrame(p["brand_search_volume"].get("relative_trend", []))
                if not df.empty:
                    st.line_chart(df.set_index("date")["search_index"])
                st.dataframe(pd.DataFrame(p["brand_related_keywords"]), hide_index=True)
    with tabs[2]:
        for p in profiles:
            with st.expander(p["brand"], expanded=p["is_own"]):
                w = p["brand_website_facts"]
                st.write(w.get("message") or w["source_url"])
                for text in w["raw_copy_snippets"][:20]:
                    st.write(text)
                insight("타겟·메시지 해석", p["brand_website_target_message"])
                insight("프로모션 해석", p["promotion_interpretation"])
        st.caption("수동 확인 팁: 대표 랜딩페이지의 가격·혜택 조건, 신청/구매 동선, 모바일 가독성을 직접 확인하세요.")
    with tabs[3]:
        mark = lambda x: "운영 확인" if x is True else "노출 없음" if x is False else "미확인"
        st.dataframe(pd.DataFrame([{"브랜드": p["brand"], **{k: mark(v) for k,v in p["media_operation_matrix_row"].items()}} for p in profiles]), hide_index=True)
        st.caption("미확인은 미운영을 뜻하지 않습니다. Meta는 현재 활성 소재 기준입니다.")
        for p in profiles:
            with st.expander(p["brand"] + " 네이버 관측 결과"):
                for row in p.get("naver_sa_ranking", []):
                    st.write({k:v for k,v in row.items() if k != "capture_data_uri"})
                    if row.get("capture_data_uri"):
                        st.image(row["capture_data_uri"])
    with tabs[4]:
        for p in profiles:
            st.write(p["brand"])
            st.json(p["instagram"])
            st.json(p["youtube"])
    with tabs[5]:
        for p in profiles:
            st.write(p["brand"])
            for field in ("key_message", "usp", "creative_type"):
                insight(field, p[field])
    downloads(session, "brand", result)
