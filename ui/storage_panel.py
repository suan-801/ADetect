"""저장 공간 표시·정리와 DB 백업 화면 (core/retention, core/db_backup). 프로젝트 삭제는 프로젝트 목록에 있다."""
import streamlit as st

from core import retention
from core.retention import human

SETTINGS_PAGE = "app_pages/4_settings.py"


def _go_settings(key):
    if st.button("저장 공간 정리로 이동", key=key):
        st.switch_page(SETTINGS_PAGE)


def usage_bar(key="usage"):
    """프로젝트 화면 상단의 한 줄 사용량. 80% 이상 경고, 90% 이상 강한 경고와 정리 안내."""
    try:
        state = retention.summary()
    except Exception:  # 사용량 조회 실패가 수집 화면 전체를 막지 않게 한다.
        st.caption("저장 용량을 확인하지 못했습니다.")
        return None
    lim = state["limits"]
    st.caption(f"저장 공간 · 파일 {human(state['files'])} / {human(lim['files'])} · DB {human(state['db'])} / {human(lim['db'])}"
               f" · 전체 한도 {human(state['total_limit'])} · 사용률 {state['ratio']:.0%}")
    if state["level"] == "critical":
        st.error(f"저장 공간 사용률 {state['ratio']:.0%} — 곧 새 수집과 파일 생성이 중단됩니다. 설정에서 정리 후보를 확인하고 정리해주세요.")
        _go_settings(key + "_go")
    elif state["level"] == "warn":
        st.warning(f"저장 공간 사용률 {state['ratio']:.0%} — 80%를 넘었습니다. 필요 없는 원본·파일 정리를 권장합니다.")
    return state


def capacity_error(exc, key):
    """저장 상한 오류는 단순 오류가 아니라 정리 화면으로 안내한다."""
    if retention.is_capacity_error(exc):
        st.error("저장 공간이 부족해 진행하지 못했습니다. 설정 > 저장 공간 관리에서 정리 후보를 확인한 뒤 다시 시도해주세요.")
        _go_settings(key)
    else:
        st.error(str(exc))


def cleanup_panel():
    st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>저장 공간 관리</span>", unsafe_allow_html=True)
    usage_bar("settings_usage")
    st.caption("오래된 원본·다운로드 파일을 정리합니다. 최근 결과와 보호한 원본은 제외됩니다.")
    protect = st.session_state.get("project_id")
    if st.button("정리 후보 보기", key="cleanup_preview"):
        st.session_state.cleanup_candidates = retention.cleanup(dry_run=True, protect_project=protect)
        st.session_state.pop("cleanup_done", None)
    candidates = st.session_state.get("cleanup_candidates")
    if candidates is not None:
        real = [c for c in candidates if c["종류"] != "안내"]
        for note in (c for c in candidates if c["종류"] == "안내"):
            st.info(note["대상"])
        if not real and not any(c["종류"] == "안내" for c in candidates):
            st.success("지금 정리할 항목이 없습니다.")
        if real:
            total = sum(c["예상 용량"] for c in real)
            st.dataframe([{"종류": c["종류"], "파일명": c["파일명"], "예상 용량": human(c["예상 용량"])} for c in real], hide_index=True)
            st.warning(f"정리 후보 {len(real)}개 · 약 {human(total)} · 삭제 후 복구할 수 없습니다.")
            agree = st.checkbox(f"위 {len(real)}개 항목을 정리하는 것에 동의합니다.", key="cleanup_agree")
            if st.button("정리 실행", type="primary", disabled=not agree, key="cleanup_apply"):
                before = retention.summary()
                done = retention.cleanup(dry_run=False, protect_project=protect, only={retention.candidate_key(c) for c in real})
                st.session_state.cleanup_done = {"items": [c for c in done if c["종류"] != "안내"], "before": before, "after": retention.summary()}
                st.session_state.pop("cleanup_candidates", None)
                st.session_state.pop("cleanup_agree", None)
                st.session_state.pop("availability_cache", None)
                st.rerun()
    done = st.session_state.get("cleanup_done")
    if done:
        st.success(f"정리 완료 — {len(done['items'])}개 항목. 파일 {human(done['before']['files'])} → {human(done['after']['files'])}, "
                   f"DB {human(done['before']['db'])} → {human(done['after']['db'])}, 사용률 {done['before']['ratio']:.0%} → {done['after']['ratio']:.0%}")
        if done["items"]:
            with st.expander("삭제·정리된 항목", expanded=False):
                st.dataframe([{"종류": c["종류"], "파일명": c["파일명"], "용량": human(c["예상 용량"])} for c in done["items"]], hide_index=True)


def _open_folder(path):
    """이 PC의 파일 탐색기로 폴더를 연다 (로컬 실행 전용)."""
    import os
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606 — 사용자가 누른 버튼으로 로컬 폴더만 연다.
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except OSError:
        return False


@st.dialog("보관 완료!")
def _backup_done(path):
    st.write("DB 백업을 만들었습니다.")
    st.code(str(path), language=None)
    if st.button("바로 확인하기", type="primary", key="open_backup_folder"):
        if not _open_folder(path.parent):
            st.caption("폴더를 열지 못했습니다. 위 경로를 직접 열어주세요.")


def backup_panel():
    from core import db_backup
    st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>DB 백업</span>", unsafe_allow_html=True)
    st.caption("원본·다운로드 파일은 포함되지 않습니다. 함께 보관하려면 앱 종료 후 storage 폴더를 복사하세요.")
    if st.button("DB 백업 만들기", key="make_db_backup"):
        try:
            _backup_done(db_backup.backup_db())
        except ValueError as exc:
            st.error(str(exc))
