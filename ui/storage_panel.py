"""저장 공간 표시·정리, DB 백업, 프로젝트 단위 삭제 화면 (core/retention, core/db_backup)."""
import streamlit as st

from core import retention, projects
from core.retention import human

SETTINGS_PAGE = "pages/4_settings.py"


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
    st.caption("정리 대상: 자료 종류별 최근 5개를 넘는 오래된 결과 상세, 30일 이상 참조되지 않은 원본, 7일이 지난 다운로드 파일. "
               "모든 자료 종류의 최근 성공 결과와 그 원본, 현재 연 프로젝트의 결과 원본, 수집 중인 작업, 보호(pin)한 원본은 제외합니다. "
               "결과 상세를 정리해도 수집 이력(시각·상태)은 남습니다.")
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
            st.warning(f"정리 후보 {len(real)}개 · 약 {human(total)}. 원본·다운로드 파일은 삭제 후 복구할 수 없습니다. "
                       "필요하면 먼저 아래 'DB 백업'과 storage 폴더 복사를 해주세요.")
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


def backup_panel():
    from core import db_backup
    st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>DB 백업</span>", unsafe_allow_html=True)
    st.caption("입력·결과·확인 상태·다운로드 요청 이력을 담은 SQLite 사본을 만듭니다. 원본(storage/evidence)과 다운로드 파일(storage/exports)은 포함되지 않으므로 "
               "원본까지 보존하려면 앱 종료 후 두 폴더를 함께 복사하세요.")
    if st.button("DB 백업 만들기", key="make_db_backup"):
        try:
            path = db_backup.backup_db()
            st.session_state.db_backup_done = str(path)
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get("db_backup_done"):
        st.success("백업 완료: " + st.session_state.db_backup_done)
    recent = db_backup.backups()[:3]
    if recent:
        st.caption("최근 백업: " + " · ".join(p.name for p in recent))


def project_cleanup_panel():
    st.markdown("<span class='adetect-eyebrow' style='margin-bottom:0.2rem;'>프로젝트 정리</span>", unsafe_allow_html=True)
    if st.session_state.get("project_deleted"):
        st.success("삭제 완료: " + st.session_state.pop("project_deleted"))
    rows = projects.overview()
    if not rows:
        st.caption("저장된 프로젝트가 없습니다.")
        return
    counts = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    st.caption(f"프로젝트 {len(rows)}개 · " + " · ".join(f"{k} {v}개" for k, v in counts.items())
               + ". 구분은 저장된 사실(SAMPLE 여부·수집 실행 수) 기준이며 테스트 여부를 추정하지 않습니다.")
    with st.expander("프로젝트 목록과 단위 삭제", expanded=False):
        st.dataframe([{"프로젝트": r["name"], "브랜드": r["brand_name"], "생성": r["created_at"][:16], "수집 실행": r["runs"],
                       "구분": r["kind"], "보관": "보관됨" if r["archived"] else ""} for r in rows], hide_index=True)
        st.caption("삭제는 프로젝트 단위로만 가능하며 되돌릴 수 없습니다. 원본 파일은 다른 프로젝트와 공유될 수 있어 즉시 지우지 않고, 참조가 사라지면 저장 공간 정리 후보로 나타납니다.")
        choice = st.selectbox("삭제할 프로젝트", [None] + [r["id"] for r in rows], key="delete_project_choice",
                              format_func=lambda pid: "선택 안 함" if pid is None else next(f"{r['name']} · {r['brand_name']} · {r['created_at'][:10]} · {r['kind']}" for r in rows if r["id"] == pid))
        if not choice:
            return
        target = next(r for r in rows if r["id"] == choice)
        impact = projects.delete_impact(choice)
        st.warning("삭제 대상: " + target["name"] + " — " + ", ".join(f"{k} {v}건" for k, v in impact.items()) + "이 DB에서 삭제됩니다.")
        backed = st.checkbox("DB 백업을 먼저 만들었습니다 (위 'DB 백업 만들기').", key="delete_backup_confirmed")
        typed = st.text_input("확인을 위해 프로젝트 이름을 그대로 입력하세요", key="delete_project_confirm")
        if st.button("프로젝트 삭제", disabled=not backed or typed.strip() != target["name"], key="delete_project_apply"):
            try:
                projects.delete(choice, typed)
                if st.session_state.get("project_id") == choice:
                    st.session_state.pop("project_id", None)
                    st.session_state.step = "list"
                for key in ("delete_project_choice", "delete_project_confirm", "delete_backup_confirmed"):
                    st.session_state.pop(key, None)
                st.session_state.project_deleted = target["name"]
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
