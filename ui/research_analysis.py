"""Research brief and explicit, cached AI analysis controls."""
import streamlit as st
from core import research_analysis as analysis


def brief_form(project, p):
    state = analysis.load(project["id"])
    brief = state.get("brief", {})
    with st.expander("조사 목적·시장 범위 설정"):
        st.caption("시장 전체 흐름과 광고 실행 방향을 연결하는 분석 조건입니다. 수집 당시 입력은 바뀌지 않습니다.")
        with st.form("research_brief_" + project["id"]):
            values = {key: st.text_input(label, value=brief.get(key, p.get("category", "") if key == "market" else ""), max_chars=1000)
                      for key, label in analysis.BRIEF_FIELDS.items()}
            submitted = st.form_submit_button("분석 조건 저장")
        if submitted:
            analysis.save(project["id"], {**state, "brief": values})
            st.success("분석 조건을 저장했습니다. 조건이 바뀐 기존 분석은 갱신이 필요합니다.")
        st.caption("시장 뉴스 검색어는 프로젝트 설정에서 별도로 추가하세요. 내부 성과 입력은 선택이며, 무료 API의 데이터 이용 조건을 확인하세요.")


def render(project, p, result, summary_slot):
    from core.exporters.analysis_report import analysis_html, summary_html
    pid = project["id"]
    state = analysis.load(pid)
    brief = state.get("brief", {})
    st.subheader("AI 종합 분석", anchor="ai-analysis")
    st.caption("시장 → 고객 → 경쟁 → 광고 실행 → 검증. 공개 자료 기반 AI 해석·가설이며 소비자 인식이나 성과를 확정하지 않습니다.")
    ready = all(brief.get(k, "").strip() for k in ("market", "region", "period", "goal"))
    if not ready: st.info("자료 수집 탭의 ‘조사 목적·시장 범위 설정’에서 시장·지역·기간·광고 목표를 입력해주세요.")
    else: st.caption(" · ".join(brief[k] for k in ("market", "region", "period", "goal")))
    reason = analysis.unavailable(p, result)
    if reason: st.info(reason)
    research = state.get("research")
    current_research = research if research and research.get("fingerprint") == analysis.research_key(brief) else None
    with st.expander("시장 웹 추가 조사 (선택)"):
        st.caption("Google Search를 이용한 별도 생성 요청 1회입니다. 무료 지원 여부·검색 비용은 모델과 계정에 따라 다릅니다. 실제 검색 쿼리는 여러 번 발생할 수 있습니다.")
        consent = st.checkbox("검색 비용 발생 가능성과 계정 한도를 확인했습니다", key="research_consent_" + pid)
        if st.button("시장 추가 조사 실행", disabled=bool(reason) or not ready or not consent or bool(current_research), key="research_search_" + pid):
            with st.spinner("시장 출처를 조사하고 있습니다…"):
                searched = analysis.research(p, brief)
            state["last_attempt"] = searched
            if searched.get("status") == "완료": state["research"] = searched
            analysis.save(pid, state)
            st.rerun()
        if current_research:
            st.caption("저장된 검색 결과 · " + current_research["created"][:10] + " · 원문 수치 독립 검증 아님")
            for row in current_research["evidence"]:
                st.write(row["text"])
                st.link_button("검색 근거", row["source"])
            if st.button("검색 결과 갱신 준비", key="reset_research_" + pid):
                state.pop("research", None)
                analysis.save(pid, state)
                st.rerun()
    payload = analysis.packet(result, brief, current_research)
    st.caption(f"선택 자료 {len(result['records'])}건 · 분석 근거 {len(payload['evidence'])}개(대표 자료·계산값·추가 검색). 입력 최대 20,000토큰, 생성 최대 5,000토큰. 계정 잔여 무료 한도는 미확인입니다.")
    st.link_button("Gemini 계정 사용 한도 확인", "https://aistudio.google.com/usage")
    key = analysis.fingerprint(result, brief, current_research)
    saved = state.get("analysis")
    current = saved if saved and saved.get("fingerprint") == key else None
    if saved and not current: st.warning("선택 자료·필터·수집 버전·조사 조건이 변경되었습니다. 분석 갱신이 필요하며 이전 분석은 다운로드에 포함하지 않습니다.")
    if st.button("AI 종합 분석 생성", type="primary", disabled=bool(reason) or not ready or bool(current) or not payload["evidence"], key="research_generate_" + pid):
        with st.spinner("근거를 바탕으로 광고 실행 방향을 분석하고 있습니다…"):
            generated = analysis.generate(p, result, brief, current_research)
        state["last_attempt"] = generated
        if generated.get("status") == "완료": state["analysis"] = generated
        analysis.save(pid, state)
        st.rerun()
    attempt = state.get("last_attempt", {})
    if attempt.get("status") not in (None, "완료"): st.warning(attempt.get("message", "분석 실패"))
    if attempt.get("usage"):
        tokens = attempt["usage"]
        st.caption("최근 호출 토큰 · " + " / ".join(f"{label}: {tokens.get(k) if tokens.get(k) is not None else '미제공'}" for k, label in (("input", "입력"), ("output", "출력"), ("thinking", "추론"), ("total", "합계"))))
    if current:
        summary_slot.markdown(summary_html(current), unsafe_allow_html=True)
        st.markdown(analysis_html(current), unsafe_allow_html=True)
    return current
