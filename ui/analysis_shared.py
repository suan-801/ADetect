"""분석 결과의 상태·출처·다운로드 공통 UI."""
import streamlit as st
from core.exporters.report_builder import build_report_html, build_report_excel
from core.exporters.artifact_store import save_artifact
from ui.components import sample_data_notice, render_insight_card


def notices(result):
    if result.get("sample_sources"):
        sample_data_notice()
        st.caption("SAMPLE 소스: " + ", ".join(result["sample_sources"]))
    for error in result.get("errors", []):
        st.warning(error)


def insight(label, value, kind="AI"):
    if value.get("status"):
        st.caption(f"{label} · {value['status']}: {value.get('message', '')}")
    else:
        render_insight_card(label, value, kind=kind)


def downloads(session, function, result):
    st.divider()
    if st.button("재분석 설정", key="rerun_"+function):
        session[function+"_status"] = "미실행"
        st.rerun()
    cols = st.columns(2)
    for col, ext in zip(cols, ("html", "xlsx")):
        with col:
            if st.button("HTML 리포트 생성" if ext == "html" else "Excel 생성", key=f"gen_{ext}_{function}"):
                try:
                    data = build_report_html(session, function, result) if ext == "html" else build_report_excel(function, result)
                    save_artifact(session.get(function+"_run_id"), function, ext, data)
                    session[f"{function}_export_{ext}"] = data
                except (ValueError, OSError):
                    st.error("파일 생성·저장에 실패했습니다. 저장 공간과 실행 이력을 확인하세요.")
            data = session.get(f"{function}_export_{ext}")
            if data:
                st.download_button("HTML 다운로드" if ext == "html" else "Excel 다운로드", data=data,
                    file_name=f"{function}.{ext}", mime="text/html" if ext == "html" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{ext}_{function}")
