"""프로젝트별 자료 수집·확인·다운로드 화면."""
import hashlib
import json
import streamlit as st
import pandas as pd

from config import settings
from core import projects, project_jobs
from core.collection import words, paid_problem, TOKEN_MESSAGE
from core.exporters import facts_report, artifact_store


def _reset():
    for key in list(st.session_state):
        if key not in ("step",):
            del st.session_state[key]
    st.session_state.step = "list"
    st.session_state.pop("project_id", None)
    st.rerun()


def _config(project=None):
    source = (project or {}).get("sources", {}).get((project or {}).get("brand_name", ""), {})
    # Home Hero에서 입력한 브랜드명·관심 주제를 초기값으로 이어받는다 (같은 값 재입력 방지).
    draft = {} if project else st.session_state.get("draft", {})
    brand = (project or {}).get("brand_name", draft.get("brand_name", ""))
    st.title("프로젝트 설정")
    name = st.text_input("프로젝트 이름", value=(project or {}).get("name", brand), key="project_name")
    campaign = st.text_input("조사 대상 (선택)", value=(project or {}).get("campaign", ""), key="project_campaign")
    category = st.text_input("관심 주제 (선택)", value=(project or {}).get("category", draft.get("category", "")), key="project_category")
    own = words(st.text_input("브랜드/캠페인 검색어", value=", ".join((project or {}).get("brand_keywords", [brand])), key="project_own"))
    general = words(st.text_input("일반 검색어", value=", ".join((project or {}).get("general_keywords", [])), key="project_general"))
    st.info(f"브랜드/캠페인 검색어: {', '.join(own) or '미입력'}을 기준으로 선택한 검색 추이·검색량·뉴스를 수집합니다.\n\n일반 검색어: {', '.join(general) or '미입력'}을 기준으로 같은 자료를 수집합니다.")
    include = words(st.text_input("포함 문구 (선택)", value=", ".join((project or {}).get("include_terms", [])), key="project_include"))
    exclude = words(st.text_input("제외 문구 (선택)", value=", ".join((project or {}).get("exclude_terms", [])), key="project_exclude"))
    with st.expander("공식 페이지·계정", expanded=True):
        src = {}
        for field, label in (("homepage", "공식 홈페이지 또는 조사 랜딩 URL"), ("detail_url", "캠페인 상세 URL"), ("instagram", "공식 Instagram 계정"), ("youtube", "공식 YouTube 채널"), ("meta_page", "Meta 광고 라이브러리 페이지")):
            src[field] = st.text_input(label, value=source.get(field, ""), key="project_src_" + field)
    paid = st.toggle("유료 기능 ON", value=(project or {}).get("paid_enabled", True), key="project_paid")
    if paid:
        for service in ("Apify", "Gemini"):
            if paid_problem({"paid_enabled": True}, service) == TOKEN_MESSAGE:
                st.warning(service + " · " + TOKEN_MESSAGE)
    inputs = {"brand_name": brand, "campaign": campaign, "category": category, "competitors": [],
              "brand_keywords": own, "general_keywords": general, "include_terms": include,
              "exclude_terms": exclude, "sources": {brand: src}, "paid_enabled": paid,
              "save_images": True, "save_ad_assets": True}
    disabled = not name.strip() or not brand.strip() or len(set(own + general)) > 10
    if st.button("설정 저장", type="primary", disabled=disabled, key="save_project"):
        if project:
            projects.update(project["id"], name.strip(), inputs)
            pid = project["id"]
        else:
            pid = projects.create(name.strip(), inputs)
        st.session_state.project_id = pid
        st.session_state.step = "workspace"
        st.session_state.pop("edit_project", None)
        st.rerun()
    if st.button("프로젝트 목록", key="back_projects"):
        _reset()


def _project_list():
    st.title("프로젝트")
    st.caption("브랜드와 조사 목적별로 자료와 이력을 관리합니다.")
    archived = bool(st.checkbox("보관한 프로젝트 보기"))
    rows = projects.listing(archived)
    for row in rows:
        left, middle, right = st.columns([5, 1, 1])
        left.write(f"{row['name']} · {row['brand_name']} · {row['updated'][:10]}")
        if middle.button("열기", key="open_" + row["id"]):
            st.session_state.project_id = row["id"]
            st.session_state.step = "workspace"
            st.rerun()
        # 보관은 목록에서만 바꾼다. 자료·이력은 삭제하지 않고 목록에서만 내린다.
        if right.button("보관 해제" if archived else "보관", key="archive_" + row["id"]):
            projects.archive(row["id"], not archived)
            st.rerun()
    with st.expander("새 프로젝트 만들기", expanded=not bool(rows)):
        brand = st.text_input("브랜드명 *", key="new_brand")
        if st.button("다음", type="primary", disabled=not brand.strip(), key="new_project"):
            st.session_state.draft = {"brand_name": brand.strip()}
            st.session_state.step = "config"
            st.rerun()
    _backup_import()


@st.fragment(run_every=2)
def _watch(pid):
    """수집은 별도 워커에서 돌아가므로 진행 상태를 주기적으로 다시 읽는다 (ui/job_control과 같은 방식).

    마지막 자료가 끝나면 화면 전체를 한 번 rerun해서 확인·다운로드 탭이 방금 저장된 결과를
    보여주게 한다 — 이 rerun이 없으면 사용자가 아무 버튼을 누를 때까지 옛 상태가 남는다.
    """
    active = [t for t in project_jobs.tasks(pid) if t["state"] in ("대기", "수집 중")]
    if not active:
        if st.session_state.pop("collection_running", False):
            st.rerun(scope="app")
        return
    st.session_state["collection_running"] = True
    st.dataframe([{"자료": projects.SOURCES[t["source"]][0], "상태": t["state"]} for t in active], hide_index=True)
    st.caption("수집이 끝나면 화면이 자동으로 갱신됩니다. 창을 닫으면 진행 중인 자료는 중단으로 표시됩니다.")
    if st.button("수집 중단", key="stop_collection"):
        project_jobs.cancel(pid)
        st.info("현재 요청이 끝난 뒤 후속 수집을 중단합니다.")


def _collect(project, history):
    st.subheader("조사에 필요한 자료를 선택하세요")
    pid = project["id"]
    tasks = project_jobs.tasks(pid)
    busy = any(t["state"] in ("대기", "수집 중") for t in tasks)
    _watch(pid)
    if st.button("기본 자료 선택", disabled=busy, key="default_sources"):
        for source in projects.SOURCES:
            st.session_state["select_" + pid + source] = source in ("trend", "volume", "news", "website")
        st.rerun()
    selected = []
    for source, (label, description, _) in projects.SOURCES.items():
        latest = next((h for h in history if h["source"] == source and projects.available(h)), None)
        if st.checkbox(label, key="select_" + pid + source, disabled=busy):
            selected.append(source)
        suffix = f" · 최근 {latest['created'][:16]} · {len(latest['result'].get('records', []))}건" if latest else " · 저장 자료 없음"
        st.caption(description + suffix)
    queries = list(dict.fromkeys(project.get("brand_keywords", []) + project.get("general_keywords", [])))
    st.caption("브랜드/캠페인 검색어: " + (", ".join(project.get("brand_keywords", [])) or "미입력") + "을 기준으로 선택한 검색 자료를 조회합니다.")
    st.caption("일반 검색어: " + (", ".join(project.get("general_keywords", [])) or "미입력") + "을 기준으로 선택한 검색 자료를 조회합니다.")
    project = dict(project)
    project["brand_keywords"] = [q for q in project.get("brand_keywords", []) if q in queries]
    project["general_keywords"] = [q for q in project.get("general_keywords", []) if q in queries]
    project["paid_enabled"] = st.toggle("유료 기능 ON", value=project.get("paid_enabled", True), key="collection_paid", disabled=busy)
    if project["paid_enabled"] and any(source in selected for source in ("meta", "instagram")):
        if paid_problem(project, "Apify") == TOKEN_MESSAGE:
            st.warning("Apify · " + TOKEN_MESSAGE)
    force = st.checkbox("캐시를 사용하지 않고 새로 수집", disabled=busy, key="force_collection")
    st.caption(f"검색어 {len(queries)}개 · 선택 자료 {len(selected)}종 · 선택 자료만 실행합니다. 이미 수집한 자료는 다시 호출하지 않습니다.")
    if selected and st.button("선택 자료 수집", type="primary", disabled=busy, key="start_project_collection"):
        try:
            project_jobs.submit(project, selected, force=force)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def _result(project, history):
    available = [h for h in history if projects.available(h)]
    if not available:
        st.info("자료를 수집하면 확인하고 다운로드할 수 있습니다.")
        return
    sources = st.multiselect("확인할 자료 종류", list(dict.fromkeys(h["source"] for h in available)), default=list(dict.fromkeys(h["source"] for h in available)), format_func=lambda s: projects.SOURCES[s][0], key="result_sources")
    snapshots = []
    for source in sources:
        versions = [h for h in available if h["source"] == source]
        selected_run = st.selectbox(projects.SOURCES[source][0] + " 수집 버전", [h["run_id"] for h in versions], format_func=lambda rid, rows=versions: next(h["created"][:19] + " · " + h["result"]["status"] for h in rows if h["run_id"] == rid), key="version_" + source)
        snapshots.append(next(h for h in versions if h["run_id"] == selected_run))
    rows = [row for item in snapshots for row in projects.review_rows(item)]
    st.caption(f"자료 {len(rows)}건. 확인 상태와 다운로드 대상을 분리해서 관리합니다.")
    search = st.text_input("자료 검색", key="project_record_search")
    visible = [r for r in rows if not search or search.casefold() in str(r).casefold()]
    frame = pd.DataFrame([{"선택": r["selection_id"] in st.session_state.get("download_selection", []), "자료ID": r["selection_id"], "종류": r["kind"], "내용": r["text"][:180], "확인 상태": r.get("review", "확인 필요"), "출처": r["source_url"]} for r in visible])
    if not frame.empty:
        edited = st.data_editor(frame, hide_index=True, disabled=["자료ID", "종류", "내용", "출처"], column_config={"확인 상태": st.column_config.SelectboxColumn(options=["포함", "확인 필요", "제외"])}, key="project_records_editor")
        if st.button("선택·확인 상태 적용", key="apply_record_selection"):
            selected, reviews, shown = set(), {}, set()
            for item in edited.to_dict("records"):
                run_id, record_id = item["자료ID"].rsplit("/", 1)
                # 수집 실행 단위로 모아 한 번에 저장한다 (뉴스 수백 건에서 행마다 커밋하지 않기 위해).
                reviews.setdefault(run_id, {})[record_id] = item["확인 상태"]
                shown.add(item["자료ID"])
                if item["선택"] and item["확인 상태"] != "제외":
                    selected.add(item["자료ID"])
            for run_id, values in reviews.items():
                projects.set_reviews(run_id, values)
            # 검색어로 걸러진 동안 화면에 없던 선택은 유지한다 — 필터는 표시만 바꾼다.
            hidden = {sid for sid in st.session_state.get("download_selection", []) if sid not in shown}
            st.session_state.download_selection = list(selected | hidden)
            st.rerun()
    selected_ids = st.session_state.get("download_selection", [])
    result = projects.selection_result(project, snapshots, selected_ids)
    st.caption(f"현재 다운로드 선택 {len(result['records'])}건. 제외 자료는 기본적으로 포함하지 않습니다.")
    _download(project, result)


def _download(project, result):
    # 생성 버튼 key는 rerun마다 고정해야 클릭이 유지된다. 선택이 바뀌었는지는 signature로 판정하고,
    # 선택과 다른 시점에 만든 파일은 다운로드 버튼을 노출하지 않는다 (화면과 파일의 선택 목록 일치).
    signature = hashlib.sha256(json.dumps([[r["selection_id"] for r in result["records"]], sorted(result.get("parts", {}))], ensure_ascii=False).encode()).hexdigest()[:16]
    for col, ext in zip(st.columns(3), ("html", "xlsx", "zip")):
        with col:
            if st.button(ext.upper() + " 생성", key="make_" + ext):
                try:
                    data = facts_report.report_html(project, result).encode() if ext == "html" else facts_report.excel(result) if ext == "xlsx" else facts_report.package(project, result)
                    export_id = projects.save_export(project["id"], result)
                    artifact_id = artifact_store.save_artifact(export_id, "project", ext, data)
                    st.session_state["artifact_" + artifact_id] = data
                    st.session_state["last_artifact_" + ext] = (signature, artifact_id)
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
            saved = st.session_state.get("last_artifact_" + ext)
            data = st.session_state.get("artifact_" + saved[1]) if saved and saved[0] == signature else None
            if data:
                st.download_button(ext.upper() + " 다운로드", data, file_name="ADetect." + ext, key="download_" + saved[1], on_click=artifact_store.record_download, args=(saved[1],))
            elif saved:
                st.caption("선택이 바뀌었습니다. 다시 생성해주세요.")


def _history(project, history):
    st.caption("결과 복원과 다운로드 파일 재생성은 외부 API를 호출하지 않습니다. 새로 수집하면 별도 시점의 이력이 생성됩니다.")
    if history:
        st.dataframe([{"자료": projects.SOURCES[h["source"]][0], "수집 시각": h["created"], "상태": h["result"]["status"], "보관": "이력만 있음" if h["result"].get("expired") else "결과 있음"} for h in history], hide_index=True)
    with st.expander("프로젝트 백업"):
        st.caption("입력·결과·확인 상태·보유 원본을 포함합니다. API 키는 포함하지 않습니다.")
        if st.button("백업 만들기", key="make_backup"):
            from core.project_backup import make
            try:
                st.session_state.backup_files = make(project["id"])
            except ValueError as exc:
                st.error(str(exc))
        for filename, data in st.session_state.get("backup_files", []):
            st.download_button(filename, data, file_name=filename, key="backup_" + filename)


def _backup_import():
    with st.expander("백업에서 새 프로젝트 복원"):
        files = st.file_uploader("백업 ZIP 전체 선택", type=["zip"], accept_multiple_files=True)
        if files:
            from core.project_backup import inspect, restore
            try:
                payload, _, manifest = inspect([file.getvalue() for file in files])
                st.write(payload["project"].get("name") + " · 수집 기록 " + str(len(payload["histories"])))
                if st.button("새 프로젝트로 복원", key="restore_backup"):
                    st.session_state.project_id = restore([file.getvalue() for file in files])
                    st.session_state.step = "workspace"
                    st.rerun()
            except (ValueError, KeyError, TypeError) as exc:
                st.error("백업 검증 실패: " + str(exc))


def render():
    projects.migrate()
    step = st.session_state.setdefault("step", "list")
    if step == "config":
        _config()
        return
    pid = st.session_state.get("project_id")
    if not pid:
        _project_list()
        return
    project = projects.load(pid)
    if st.session_state.get("edit_project"):
        _config(project)
        return
    st.title(project["name"])
    st.caption(project["brand_name"] + " · " + (project.get("campaign") or "브랜드 전체"))
    left, right = st.columns(2)
    if left.button("프로젝트 목록", key="to_project_list"):
        _reset()
    if right.button("프로젝트 설정", key="edit_project_button"):
        st.session_state.edit_project = True
        st.rerun()
    with st.expander("1분 사용법"):
        st.write("필요한 자료 선택 → 수집 → 자료 확인·다운로드 순서로 사용합니다. 체크 해제는 저장된 자료를 삭제하지 않습니다.")
    if settings.SAMPLE_MODE:
        st.warning("SAMPLE — 실제 수집 자료가 아닙니다.")
    history = projects.histories(pid)
    tabs = st.tabs(["자료 수집", "자료 확인·다운로드", "이력"])
    with tabs[0]:
        _collect(project, history)
    with tabs[1]:
        _result(project, history)
    with tabs[2]:
        _history(project, history)
