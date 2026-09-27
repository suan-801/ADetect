# LEGACY — 현재 런타임(app.py 네비게이션·신규 화면)에서 import/실행하지 않는다. (2026-09-27 검색 확인, PRD §0 18차 개정)
# 신규 UI: pages/2_analyze.py → ui/project_workspace.py
# 신규 데이터 흐름: core/projects.py, core/project_jobs.py
# 사용 금지 이유: 16차 개정의 종합분석 탭(SoS/SoA/SOV·포지셔닝·전략 추천·Target Insight). 18차 새 화면과 내보내기에서 제외된 해석 기능이다.
# 새 화면에 다시 연결하지 말 것. 기존 데이터 호환 검토 전까지 삭제하지 않고 보존한다.

"""기존 결과만 사용하는 종합분석. Target Insight는 자동 파생한다."""
import pandas as pd
import streamlit as st
from core.analyzers.insight_synthesizer import build_target_insight, run_synthesis
from core.runtime import input_signature
from ui.job_control import start, pending
from core.analyzers.positioning import propose_axes
from ui.analysis_shared import notices, insight, downloads
from ui.components import tab_header, status_icon


def render(session):
    unlocked = any(session.get(k+"_status") in ("완료", "부분 실패") for k in ("market", "brand", "creative"))
    tab_header("SYNTHESIS", "종합분석", status_icon(session.get("synthesis_status", "미실행")) if unlocked else "🔒")
    if not unlocked:
        st.caption("시장·브랜드·소재 중 최소 1개 분석을 완료하면 사용할 수 있습니다.")
        return
    if pending(session, "synthesis"):
        return
    brand_result = session.get("brand_result", {})
    if brand_result.get("competitors"):
        with st.expander("포지셔닝맵 축 확인"):
            if st.button("근거 기반 축 제안", key="propose_axes"):
                session["axis_proposal"] = propose_axes(brand_result)
            proposal = session.get("axis_proposal", {})
            if proposal.get("status") == "awaiting_confirmation":
                x = st.text_input("X축 (0점 ↔ 100점)", proposal["x_axis_label"], key="position_x")
                y = st.text_input("Y축 (0점 ↔ 100점)", proposal["y_axis_label"], key="position_y")
                if st.button("축 확정", key="confirm_axes"):
                    session["confirmed_axes"] = {"x_axis_label":x,"y_axis_label":y,"confirmed":True}
                st.caption("확정 후 종합분석을 실행하면 좌표를 산출합니다.")
            elif proposal:
                st.caption(proposal.get("message"))
    if st.button("종합분석 시작하기", type="primary", key="btn_start_synthesis"):
        start(session, "synthesis", lambda snapshot: run_synthesis(snapshot, snapshot.get("confirmed_axes")),
              {"signature":input_signature(session), "axes":session.get("confirmed_axes")})
    result = session.get("synthesis_result")
    if result:
        notices(result)
        st.dataframe(pd.DataFrame(result.get("sov", [])), hide_index=True)
        for text in result.get("limitations", []):
            st.caption(text)
        for field, title in (("one_line_summary", "Executive Summary"), ("competitive_landscape", "경쟁 구도"),
            ("common_message", "공통 메시지"), ("differentiation_point", "차별화 포인트"), ("white_space", "White Space"), ("recommended_angle", "Recommended Action")):
            insight(title, result.get(field, {}), "REC" if field in ("one_line_summary", "recommended_angle") else "AI")
        position = result.get("positioning_map", {})
        if position.get("status") == "available":
            st.scatter_chart(pd.DataFrame(position["points"]), x="x_axis_score", y="y_axis_score", color="brand")
            st.caption(position["message"])
            for point in position["points"]:
                insight(point["brand"], point)
        else:
            insight("Positioning", position)
        downloads(session, "synthesis", result)
    st.divider()
    market = session.get("market_result") if session.get("market_status") in ("완료", "부분 실패") else None
    brand = session.get("brand_result") if session.get("brand_status") in ("완료", "부분 실패") else None
    if not result and any(session.get(k+"_result", {}).get("sample_sources") for k in ("market", "brand", "creative")):
        st.caption("SAMPLE 입력 기반 Target Insight입니다.")
    insight("Target Insight", build_target_insight(market, brand, session.get("creative_result")))
