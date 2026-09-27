"""분석 세션·기능별 실행 이력과 파일 재다운로드. 만료 파일은 이력만 보존한다."""
from __future__ import annotations

import html
import json
from datetime import datetime

import streamlit as st

from database.db import list_sessions, list_function_runs
from core.runtime import restore_results
from core.exporters.artifact_store import list_artifacts, read_artifact, record_download, download_events
from ui.components import section_header_block

section_header_block("History", "이력 관리")
st.caption("이 PC의 SQLite에 입력·수집 결과·다운로드 요청 이력을 저장합니다. 파일은 별도 폴더에 보관합니다. 브라우저 저장 완료 여부는 확인할 수 없습니다.")
st.write("")

sessions = list_sessions()

if not sessions:
    st.markdown(
        '<div class="adetect-empty"><p class="adetect-empty-desc">'
        "아직 분석 세션이 없습니다. 'Analyze' 메뉴에서 새 분석을 시작해보세요.</p></div>",
        unsafe_allow_html=True,
    )
else:
    for s in sessions:
        competitors = json.loads(s["competitors_json"] or "[]")
        row_col, action_col = st.columns([5, 1], vertical_alignment="center")
        with row_col:
            st.markdown(
                '<div class="adetect-row">'
                '<div class="adetect-row-main">'
                f'<p class="adetect-row-brand">{html.escape(s["brand_name"])}'
                f'<span style="color:#667080;font-weight:380;"> · {html.escape(s["category"] or "카테고리 미지정")}</span></p>'
                f'<p class="adetect-row-meta">경쟁사 {len(competitors)}개 · 생성일 {html.escape(s["created_at"][:19])}</p>'
                "</div></div>",
                unsafe_allow_html=True,
            )
        runs = list_function_runs(s["id"])
        with row_col:
            latest = {}
            for run in runs:
                latest.setdefault(run["function_type"], run["status"])
            st.caption(" · ".join(f"{k}: {v}" for k,v in latest.items() if k != "target") or "아직 실행한 분석이 없습니다.")
        with row_col:
            if runs:
                with st.expander("실행 이력·파일 다운로드"):
                    for run in runs:
                        if run["function_type"] == "target":
                            continue
                        st.write(f"{run['created_at'][:19]} · {run['function_type']} · {run['status']}")
                        artifacts = list_artifacts(run["id"])
                        if not artifacts:
                            st.caption("생성된 파일이 없습니다. Workspace에서 결과 파일을 생성하세요.")
                        for artifact in artifacts:
                            ext = artifact["extension"]
                            events = download_events(artifact["id"])
                            st.caption(f"파일 생성: {datetime.fromtimestamp(artifact['created']).astimezone().isoformat(timespec='seconds')} · 다운로드 요청 {len(events)}회")
                            if events:
                                st.write([datetime.fromtimestamp(e["requested"]).astimezone().isoformat(timespec="seconds") for e in events])
                            if artifact["expired"]:
                                st.button(f"{ext.upper()} · 파일 만료",disabled=True,key="expired_"+artifact["id"])
                            else:
                                key="history_data_"+artifact["id"]
                                if st.button(f"{ext.upper()} 파일 불러오기",key="prepare_"+artifact["id"]):
                                    st.session_state[key]=read_artifact(artifact["id"],touch=False)
                                    if st.session_state[key] is None: st.warning("파일이 없습니다. 결과를 복원해 다시 생성하세요.")
                                if st.session_state.get(key):
                                    st.download_button(f"{ext.upper()} 재다운로드", data=st.session_state[key],
                                        file_name=f"{run['function_type']}.{ext}",key="history_dl_"+artifact["id"], on_click=record_download, args=(artifact["id"],))
        with action_col:
            if st.button("열기 →", key=f"reenter_{s['id']}"):
                st.session_state.session = {
                    "id": s["id"],
                    "brand_name": s["brand_name"],
                    "category": s["category"],
                    "competitors": competitors,
                    "market_status": "미실행",
                    "brand_status": "미실행",
                    "creative_status": "미실행",
                }
                saved_inputs = json.loads(s["inputs_json"] or "{}")
                st.session_state.session.update({k:v for k,v in saved_inputs.items() if v is not None})
                st.session_state.session["creative_meta_overrides"] = {n:v["meta_page"] for n,v in saved_inputs.get("sources", {}).items() if v.get("meta_page")}
                restore_results(st.session_state.session)
                st.session_state.step = "workspace"
                st.switch_page("pages/2_analyze.py")
