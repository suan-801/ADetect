# LEGACY — 현재 런타임(app.py 네비게이션·신규 화면)에서 import/실행하지 않는다. (2026-09-27 검색 확인, PRD §0 18차 개정)
# 신규 UI: app_pages/2_analyze.py → ui/project_workspace.py
# 신규 데이터 흐름: core/projects.py, core/project_jobs.py
# 사용 금지 이유: 레거시 탭·facts_workspace 전용 세션 작업 제어(core/jobs.py). 신규 수집은 core/project_jobs.py의 프로젝트 워커를 쓴다.
# 새 화면에 다시 연결하지 말 것. 기존 데이터 호환 검토 전까지 삭제하지 않고 보존한다.

"""분석을 브라우저 요청과 분리해 대기·취소 버튼을 유지한다."""
import streamlit as st
from core.jobs import submit, get_job, cancel, forget


def start(session, function, runner, inputs):
    session[function+"_job"] = submit(session,function,runner,inputs,force=session.pop(function+"_force",False))
    session[function+"_status"] = "진행중"
    st.rerun()


def pending(session, function):
    jid = session.get(function+"_job")
    if not jid:
        return False
    job = get_job(jid)
    if not job:
        session.pop(function+"_job",None)
        session[function+"_status"] = "미실행"
        return False
    if job["state"] == "done":
        # SQLite에 저장된 결과가 작업 중 다른 세션 입력으로 덮이지 않도록 소비 시에만 반영한다.
        result = job["result"]
        session[function+"_result"] = result
        session[function+"_status"] = result["status"]
        session[function+"_run_id"] = job.get("run_id")
        for key in list(session):
            if key.startswith(function+"_export_") or key.startswith("collection_export_"):
                del session[key]
        if function == "collection":
            from core.runtime import restore_results
            restore_results(session)
        elif function != "synthesis":
            session.pop("synthesis_result",None)
            session["synthesis_status"] = "미실행"
        session.pop(function+"_job",None)
        forget(jid)
        st.rerun()
    _watch(jid)
    return True


@st.fragment(run_every=1)
def _watch(jid):
    job = get_job(jid)
    if not job or job["state"] == "done":
        st.rerun()
    label = "다른 분석이 끝나기를 기다립니다." if job["state"] == "queued" else job["message"]
    st.info(label)
    st.caption("한 번에 한 분석을 실행합니다. 취소하면 진행 중인 요청 종료 후 후속 수집을 중단합니다.")
    if st.button("분석 취소",key="cancel_"+jid):
        cancel(jid)
        st.caption("취소 요청을 전달했습니다.")
