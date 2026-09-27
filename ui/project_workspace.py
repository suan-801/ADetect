"""프로젝트별 자료 수집·확인·다운로드 화면."""
import hashlib
import html
import json
import streamlit as st
import pandas as pd

from config import settings
from core import projects, project_jobs, retention
from core.collection import words, paid_problem, TOKEN_MESSAGE
from core.exporters import facts_report, artifact_store
from ui.storage_panel import usage_bar, capacity_error


def _reset():
    for key in list(st.session_state):
        if key not in ("step",):
            del st.session_state[key]
    st.session_state.step = "list"
    st.session_state.pop("project_id", None)
    st.rerun()


EXAMPLE = {  # 입력칸의 연한 예시는 한 프로젝트로 통일한다.
    "name": "예) 한샘 리하우스 캠페인 조사", "campaign": "예) 리하우스 캠페인", "category": "예) 인테리어 리모델링",
    "own": "예) 한샘, 한샘리하우스", "general": "예) 인테리어, 리모델링",
    "include": "예) 리하우스, 패키지 할인", "exclude": "예) 채용, 주가",
    "official": "예)\nhttps://www.hanssem.com\nhttps://smartstore.naver.com/hanssem\nhttps://brand.naver.com/hanssem",
    "detail_url": "예) https://remodeling.hanssem.com/event?utm_source=meta&utm_campaign=rehaus",
    "instagram": "예) @hanssem 또는 https://www.instagram.com/hanssem",
    "youtube": "예) @hanssem 또는 UC로 시작하는 채널 ID",
    "meta_page": "예) https://www.facebook.com/ads/library/?view_all_page_id=123456789",
}


def _config(project=None):
    source = (project or {}).get("sources", {}).get((project or {}).get("brand_name", ""), {})
    # Home Hero에서 입력한 브랜드명·관심 주제를 초기값으로 이어받는다 (같은 값 재입력 방지).
    draft = {} if project else st.session_state.get("draft", {})
    brand = (project or {}).get("brand_name", draft.get("brand_name", ""))
    st.title("프로젝트 설정")
    st.caption("브랜드: " + brand)
    name = st.text_input("프로젝트 이름", value=(project or {}).get("name", ""), placeholder=EXAMPLE["name"], key="project_name")
    campaign = st.text_input("조사 대상 (선택)", value=(project or {}).get("campaign", ""), placeholder=EXAMPLE["campaign"], key="project_campaign")
    category = st.text_input("관심 주제 (선택)", value=(project or {}).get("category", draft.get("category", "")), placeholder=EXAMPLE["category"], key="project_category")
    own = words(st.text_input("브랜드/캠페인 검색어", value=", ".join((project or {}).get("brand_keywords", [])), placeholder=EXAMPLE["own"], key="project_own"))
    general = words(st.text_input("일반 검색어", value=", ".join((project or {}).get("general_keywords", [])), placeholder=EXAMPLE["general"], key="project_general",
                                  help="검색어마다 검색 추이·검색량·뉴스를 따로 수집합니다. 두 칸 합쳐 최대 10개."))
    include = words(st.text_input("포함 문구 (선택)", value=", ".join((project or {}).get("include_terms", [])), placeholder=EXAMPLE["include"], key="project_include"))
    exclude = words(st.text_input("제외 문구 (선택)", value=", ".join((project or {}).get("exclude_terms", [])), placeholder=EXAMPLE["exclude"], key="project_exclude"))
    with st.expander("공식 페이지·계정", expanded=True):
        official = [u.strip() for u in st.text_area("공식 URL (한 줄에 하나)", value="\n".join(source.get("official_urls") or ([source["homepage"]] if source.get("homepage") else [])),
                                                    placeholder=EXAMPLE["official"], key="project_src_official", height=110).splitlines() if u.strip()]
        st.caption("자사몰·스마트스토어·브랜드스토어 등 여러 개를 넣을 수 있습니다. '공식 페이지 자료'를 수집하면 각각 저장합니다.")
        detail = st.text_input("캠페인 상세 URL (선택)", value=source.get("detail_url", ""), placeholder=EXAMPLE["detail_url"], key="project_src_detail_url")
        st.caption("Meta 광고 라이브러리 등에서 광고의 랜딩 URL을 열어 utm 구조를 확인해 보세요. 이 URL과 일치하는 자료는 '포함'으로 분류됩니다.")
        instagram = st.text_input("공식 Instagram 계정", value=source.get("instagram", ""), placeholder=EXAMPLE["instagram"], key="project_src_instagram")
        youtube = st.text_input("공식 YouTube 채널", value=source.get("youtube", ""), placeholder=EXAMPLE["youtube"], key="project_src_youtube")
        meta = st.text_input("Meta 광고 라이브러리 페이지", value=source.get("meta_page", ""), placeholder=EXAMPLE["meta_page"], key="project_src_meta_page")
        st.caption("facebook.com/ads/library에서 브랜드 페이지를 찾아 '페이지의 모든 광고 보기'를 연 뒤 주소를 붙여넣으세요. 주소에 view_all_page_id=숫자가 있어야 합니다.")
    src = {"official_urls": official, "homepage": official[0] if official else "", "detail_url": detail,
           "instagram": instagram, "youtube": youtube, "meta_page": meta}
    inputs = {"brand_name": brand, "campaign": campaign, "category": category, "competitors": [],
              "brand_keywords": own or [brand], "general_keywords": general, "include_terms": include,
              "exclude_terms": exclude, "sources": {brand: src}, "paid_enabled": (project or {}).get("paid_enabled", True),
              "save_images": True, "save_ad_assets": True}
    too_many = len(set(inputs["brand_keywords"] + general)) > 10
    if too_many:
        st.warning("검색어는 두 칸 합쳐 최대 10개입니다.")
    left, right = st.columns([1, 5])
    if left.button("설정 저장", type="primary", disabled=not brand.strip() or too_many, key="save_project"):
        # 이름을 비워두면 브랜드명·조사 대상으로 만든다.
        title = name.strip() or " ".join(x for x in (brand, campaign.strip()) if x)
        if project:
            projects.update(project["id"], title, inputs)
            pid = project["id"]
        else:
            pid = projects.create(title, inputs)
        st.session_state.project_id = pid
        st.session_state.step = "workspace"
        st.session_state.pop("edit_project", None)
        st.rerun()
    if right.button("프로젝트 목록", key="back_projects"):
        _reset()


def _close_delete():
    st.session_state.pop("delete_ids", None)


@st.dialog("프로젝트 삭제", on_dismiss=_close_delete)
def _delete_dialog(ids):
    rows = [r for r in projects.overview() if r["id"] in ids]
    st.write(f"{len(rows)}개 프로젝트를 삭제합니다. 되돌릴 수 없습니다.")
    for r in rows:
        impact = projects.delete_impact(r["id"])
        st.caption(f"{r['name']} · 수집 실행 {impact['수집 실행']}건 · 확인 상태 {impact['확인 상태']}건 · 다운로드 기록 {impact['다운로드 선택 기록']}건")
    backed = st.checkbox("DB 백업을 먼저 만들었습니다 (설정 > DB 백업)", key="delete_backup_ok")
    left, right = st.columns(2)
    if left.button("취소", key="delete_cancel"):
        _close_delete()
        st.rerun()
    if right.button("삭제", type="primary", disabled=not backed, key="delete_confirm"):
        failed = []
        for r in rows:
            try:
                projects.delete(r["id"], r["name"])
            except ValueError as exc:
                failed.append(r["name"] + " — " + str(exc))
        for r in rows:
            st.session_state.pop("pick_" + r["id"], None)
        _close_delete()
        st.session_state.deleted_message = (f"{len(rows) - len(failed)}개 삭제 완료" + (" · 실패: " + "; ".join(failed) if failed else ""))
        st.rerun()


def _project_list():
    st.title("프로젝트")
    if st.session_state.get("deleted_message"):
        st.success(st.session_state.pop("deleted_message"))
    archived = bool(st.checkbox("보관한 프로젝트 보기", key="show_archived"))
    rows = projects.listing(archived)
    kinds = {r["id"]: r["kind"] for r in projects.overview()} if rows else {}
    for row in rows:
        pick, left, middle, right = st.columns([0.4, 5, 1, 1], vertical_alignment="center")
        pick.checkbox("선택", key="pick_" + row["id"], label_visibility="collapsed")
        tag = kinds.get(row["id"], "")
        left.markdown(f"**{row['name']}** · {row['brand_name']} · {row['updated'][:10]}"
                      + (f" <span style='color:#797C84;font-size:0.8rem'>· {tag}</span>" if tag and tag != "실수집 자료 포함" else ""), unsafe_allow_html=True)
        if middle.button("열기", key="open_" + row["id"]):
            st.session_state.project_id = row["id"]
            st.session_state.step = "workspace"
            st.rerun()
        # 보관은 목록에서만 바꾼다. 자료·이력은 삭제하지 않고 목록에서만 내린다.
        if right.button("보관 해제" if archived else "보관", key="archive_" + row["id"]):
            projects.archive(row["id"], not archived)
            st.rerun()
    picked = [r["id"] for r in rows if st.session_state.get("pick_" + r["id"])]
    if picked and st.button(f"선택 {len(picked)}개 삭제", key="delete_picked"):
        st.session_state.delete_ids = picked
    # 팝업 안의 체크박스를 눌러도 팝업이 유지되도록 선택 목록을 상태로 들고 있는다.
    if st.session_state.get("delete_ids"):
        _delete_dialog(st.session_state.delete_ids)
    with st.expander("새 프로젝트 만들기", expanded=not bool(rows)):
        brand = st.text_input("브랜드명 *", placeholder="예) 한샘", key="new_brand")
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


PAID_SOURCES = ("meta", "instagram")


def _collect(project, history):
    pid = project["id"]
    tasks = project_jobs.tasks(pid)
    busy = any(t["state"] in ("대기", "수집 중") for t in tasks)
    _watch(pid)
    project = dict(project)
    project["paid_enabled"] = st.toggle("유료 기능 ON", value=project.get("paid_enabled", True), key="collection_paid", disabled=busy,
                                        help="ON일 때만 Meta 광고·Instagram(Apify 유료)을 선택할 수 있습니다.")
    if project["paid_enabled"] and paid_problem(project, "Apify") == TOKEN_MESSAGE:
        st.warning("Apify · " + TOKEN_MESSAGE)
    if st.button("기본 자료 선택", disabled=busy, key="default_sources"):
        for source in projects.SOURCES:
            st.session_state["select_" + pid + source] = source in ("trend", "volume", "news", "website")
        st.rerun()
    selected = []
    with st.container(key="adetect_sources"):
        for source, (label, description, _) in projects.SOURCES.items():
            locked = source in PAID_SOURCES and not project["paid_enabled"]
            if locked:
                st.session_state["select_" + pid + source] = False
            latest = next((h for h in history if h["source"] == source and projects.available(h)), None)
            if st.checkbox(label, key="select_" + pid + source, disabled=busy or locked):
                selected.append(source)
            meta = (f"최근 {latest['created'][:16].replace('T', ' ')} · {_size(latest)}" if latest else "저장 자료 없음") + (" · 유료 기능 ON 시 선택 가능" if locked else "")
            st.markdown(f"<div class='adetect-src-desc'>{html.escape(description)}</div><div class='adetect-src-meta{' done' if latest else ''}'>{html.escape(meta)}</div>", unsafe_allow_html=True)
    queries = list(dict.fromkeys(project.get("brand_keywords", []) + project.get("general_keywords", [])))
    force = st.checkbox("캐시를 사용하지 않고 새로 수집", disabled=busy, key="force_collection")
    st.caption(f"검색어 {len(queries)}개 ({', '.join(queries) or '미입력'}) · 선택 자료 {len(selected)}종")
    if selected and st.button("선택 자료 수집", type="primary", disabled=busy, key="start_project_collection"):
        try:
            project_jobs.submit(project, selected, force=force)
            st.rerun()
        except ValueError as exc:
            capacity_error(exc, "collect_capacity_go")
    latest = {}
    for h in history:
        latest.setdefault(h["source"], h)
    full = [projects.SOURCES[s][0] for s, h in latest.items()
            if retention.is_capacity_error(json.dumps([h["result"].get("errors", []), [p.get("message", "") for p in h["result"].get("parts", {}).values()]], ensure_ascii=False))]
    if full and not busy:
        st.warning("최근 수집 중 저장 공간 부족으로 원본 저장 또는 수집이 중단된 자료가 있습니다: " + ", ".join(full))
        capacity_error(retention.CapacityError(retention.CAPACITY_MESSAGE), "collect_capacity_recent_go")


def _versions(available):
    """자료 종류별 성공 버전 (최신순). history는 이미 최신순이다."""
    by_source = {}
    for h in available:
        by_source.setdefault(h["source"], []).append(h)
    return {s: by_source[s] for s in projects.SOURCES if s in by_source}


def _size(item):
    """검색 추이는 자료 행이 아니라 월별 시리즈이므로 개월 수로 센다."""
    if item["source"] == "trend":
        months = max((len(p["series"]["rows"]) for p in item["result"].get("parts", {}).values() if p.get("series")), default=0)
        return f"{months}개월"
    return f"{len(item['result'].get('records', []))}건"


def _open_version(pid, item):
    """이력 탭의 '이 시점 결과 열기' — 위젯 생성 전에 상태를 바꿀 수 있도록 on_click 콜백으로만 호출한다."""
    st.session_state["version_" + pid + item["source"]] = item["run_id"]
    chosen = st.session_state.get("result_sources_" + pid)
    if chosen is not None and item["source"] not in chosen:
        st.session_state["result_sources_" + pid] = chosen + [item["source"]]
    st.session_state.opened_version = projects.SOURCES[item["source"]][0] + " · " + item["created"][:16].replace("T", " ")


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _num(value):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None  # '<10' 같은 표시값은 숫자로 바꾸지 않는다.


@st.cache_data(max_entries=64, show_spinner=False)
def _image(filename, sha256):
    from core.evidence_store import read_bytes
    return read_bytes({"filename": filename, "sha256": sha256})


def _visuals(snapshots, rows):
    """선택한 수집 버전의 요약 지표·차트·이미지. 값은 저장된 자료 그대로이며 새 해석을 만들지 않는다."""
    by = {i["source"]: i for i in snapshots}
    counts = {state: sum(1 for r in rows if r.get("review", "확인 필요") == state) for state in ("포함", "확인 필요", "제외")}
    cols = st.columns(4)
    cols[0].metric("자료", f"{len(rows)}건")
    for col, state in zip(cols[1:], counts):
        col.metric(state, f"{counts[state]}건")
    series = [p["series"] for p in by.get("trend", {}).get("result", {}).get("parts", {}).values() if p.get("series", {}).get("rows")]
    seasonality = [(p["series"]["keyword"], p["seasonality"]) for p in by.get("trend", {}).get("result", {}).get("parts", {}).values() if p.get("seasonality") and p.get("series")]
    volume = [r for r in rows if r["kind"] in ("검색량", "연관 검색어")]
    news = [r for r in rows if r["kind"] == "뉴스"]
    images = [(r, a) for r in rows for a in r.get("assets", []) if a.get("filename", "").lower().endswith(IMAGE_EXT)]
    names = [n for n, ok in (("검색 추이", series), ("검색량·뉴스", volume or news), ("이미지", images)) if ok]
    if not names:
        return
    tabs = dict(zip(names, st.tabs(names)))
    if "검색 추이" in tabs:
        with tabs["검색 추이"]:
            frame = pd.DataFrame([{"월": r["date"][:7], "검색어": s["keyword"], "상대지수": r["search_index"]} for s in series for r in s["rows"]])
            st.line_chart(frame.pivot_table(index="월", columns="검색어", values="상대지수"), height=260)
            st.caption("검색어별 조회 기간 최고치=100인 상대지수입니다. 서로 다른 검색어의 100은 같은 규모가 아니며, 빠진 달은 0이 아닙니다.")
            if seasonality:
                left, right = st.columns([3, 2])
                with left:
                    monthly = pd.DataFrame([{"월": f"{m['월']:02d}월", "검색어": k, "평균": m["평균 검색지수"]} for k, v in seasonality for m in v["monthly"]])
                    if not monthly.empty:
                        st.caption("월별 평균 (36개월)")
                        st.bar_chart(monthly.pivot_table(index="월", columns="검색어", values="평균"), height=220, stack=False)
                with right:
                    st.caption("연도별 피크·저점 월")
                    st.dataframe([{"검색어": k, **y} for k, v in seasonality for y in v["yearly"]], hide_index=True)
    if "검색량·뉴스" in tabs:
        with tabs["검색량·뉴스"]:
            exact = [r for r in volume if r["kind"] == "검색량"]
            if exact:
                frame = pd.DataFrame([{"검색어": r["text"], "PC": _num(r.get("pc")), "모바일": _num(r.get("mobile"))} for r in exact]).set_index("검색어")
                if frame.notna().any().any():
                    st.caption("월간 검색량 (조회 시점)")
                    st.bar_chart(frame, height=220, stack=False)
            related = [r for r in volume if r["kind"] == "연관 검색어"]
            if related or exact:
                st.dataframe([{"구분": r["kind"], "검색어": r["text"], "조회어": r.get("keyword"), "PC": r.get("pc"), "모바일": r.get("mobile")} for r in exact + related[:20]],
                             hide_index=True, height=min(38 * (len(exact) + min(len(related), 20)) + 40, 320))
            if news:
                dates = pd.to_datetime(pd.Series([r.get("published_at") for r in news]), errors="coerce", utc=True).dropna()
                left, right = st.columns([3, 2])
                with left:
                    if not dates.empty:
                        st.caption(f"뉴스 발행일별 건수 (수집 {len(news)}건)")
                        st.bar_chart(dates.dt.strftime("%Y-%m-%d").value_counts().sort_index().rename("건수"), height=220)
                with right:
                    st.caption("검색어별 뉴스 수")
                    per = {}
                    for r in news:
                        for q in r.get("matched_queries") or [r.get("keyword")]:
                            per[q] = per.get(q, 0) + 1
                    st.dataframe([{"검색어": k, "건수": v} for k, v in sorted(per.items(), key=lambda x: -x[1])], hide_index=True)
    if "이미지" in tabs:
        with tabs["이미지"]:
            shown = 0
            grid = st.columns(4)
            for r, asset in images:
                data = _image(asset["filename"], asset.get("sha256", ""))
                if data is None:
                    continue
                with grid[shown % 4]:
                    st.image(data, caption=f"{r['brand']} · {r['kind']}", width="stretch")
                    st.markdown(f"[원문]({r['source_url']})")
                shown += 1
                if shown >= 12:
                    break
            if not shown:
                st.caption("보유한 이미지 원본이 없습니다.")
            elif len(images) > shown:
                st.caption(f"{shown}개 표시 · 전체 {len(images)}개는 ZIP 다운로드에 포함됩니다.")


def _result(project, history):
    pid = project["id"]
    by_source = _versions([h for h in history if projects.available(h)])
    if not by_source:
        st.info("자료를 수집하면 확인하고 다운로드할 수 있습니다.")
        return
    order = list(by_source)
    source_key = "result_sources_" + pid
    if source_key not in st.session_state or any(s not in order for s in st.session_state[source_key]):
        st.session_state[source_key] = [s for s in st.session_state.get(source_key, order) if s in order] or order
    snapshots = []
    for source in [s for s in order if s in st.session_state[source_key]]:
        versions = by_source[source]
        key = "version_" + pid + source
        if key in st.session_state and st.session_state[key] not in [h["run_id"] for h in versions]:
            del st.session_state[key]
        # 다른 시점을 고르지 않았으면 최근 성공 결과를 그대로 쓴다.
        snapshots.append(next((h for h in versions if h["run_id"] == st.session_state.get(key)), versions[0]))
    if st.session_state.get("opened_version"):
        st.success("이력에서 연 결과: " + st.session_state.pop("opened_version"))
    st.caption("  ·  ".join(f"{projects.SOURCES[i['source']][0]} {i['created'][:10]} {_size(i)}"
                            + ("" if i is by_source[i["source"]][0] else " (다른 시점)") for i in snapshots) or "선택한 자료 종류가 없습니다.")
    with st.expander("다른 시점 선택", expanded=False):
        st.multiselect("확인할 자료 종류", order, format_func=lambda s: projects.SOURCES[s][0], key=source_key)
        for source in [s for s in order if s in st.session_state[source_key]]:
            versions = by_source[source]
            st.selectbox(projects.SOURCES[source][0] + " 수집 버전", [h["run_id"] for h in versions], key="version_" + pid + source,
                         format_func=lambda rid, rows=versions: next(h["created"][:19].replace("T", " ") + " · " + h["result"]["status"] + " · " + _size(h) + (" · 최근" if h is rows[0] else "") for h in rows if h["run_id"] == rid))
    dates = projects.collection_dates(snapshots)
    if len(dates) > 1:
        st.warning("날짜 혼합 — 선택한 자료의 수집일이 서로 다릅니다 (" + ", ".join(dates) + "). 다운로드 파일에도 이 안내가 기록됩니다.")
    rows = [row for item in snapshots for row in projects.review_rows(item)]
    _visuals(snapshots, rows)
    search = st.text_input("자료 검색", key="project_record_search", placeholder=f"자료 {len(rows)}건 · 확인 상태와 다운로드 대상은 따로 관리합니다")
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
    st.caption(f"현재 다운로드 선택 {len(result['records'])}건. 제외 자료는 기본적으로 포함하지 않습니다."
               + (" 수집일이 다른 자료가 섞여 있습니다 (" + ", ".join(dates) + ")." if len(dates) > 1 else ""))
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
                    capacity_error(exc, "download_capacity_go_" + ext)
            saved = st.session_state.get("last_artifact_" + ext)
            data = st.session_state.get("artifact_" + saved[1]) if saved and saved[0] == signature else None
            if data:
                st.download_button(ext.upper() + " 다운로드", data, file_name="ADetect." + ext, key="download_" + saved[1], on_click=artifact_store.record_download, args=(saved[1],))
            elif saved:
                st.caption("선택이 바뀌었습니다. 다시 생성해주세요.")


AVAILABILITY_GUIDE = {
    "결과·원본 모두 있음": "저장된 결과를 열 수 있고, 원본을 포함한 HTML/Excel/ZIP을 다시 만들 수 있습니다.",
    "결과만 있음 (일부 원본 없음)": "결과를 열고 다운로드 파일을 다시 만들 수 있습니다. 만료되었거나 없는 원본은 ZIP에 포함되지 않으며 원본_보관안내.txt에 사유가 남습니다.",
    "이력만 있음": "당시 결과를 복원할 수 없습니다 (정리로 결과 상세가 만료되었거나 수집에 실패한 기록). 프로젝트 백업 ZIP이 있으면 프로젝트 목록의 '백업에서 새 프로젝트 복원'으로 가져오거나, 자료 수집 탭에서 새로 수집하세요. 새 수집은 복원이 아니라 새 시점의 자료입니다.",
}


def _availability(history):
    """보유 상태는 core.retention.availability_detail 결과를 그대로 쓴다. 원본 해시 확인 비용 때문에 실행별로 캐시한다."""
    cache = st.session_state.setdefault("availability_cache", {})
    output = {}
    for h in history:
        key = h["run_id"] + ("#expired" if h["result"].get("expired") else "")
        if key not in cache:
            cache[key] = retention.availability_detail(h["result"])
        output[h["run_id"]] = cache[key]
    return output


def _history(project, history):
    st.caption("결과 복원과 다운로드 파일 재생성은 외부 API를 호출하지 않습니다. 새로 수집하면 별도 시점의 이력이 생성됩니다.")
    if history:
        details = _availability(history)
        st.dataframe([{"자료": projects.SOURCES[h["source"]][0], "수집 시각": h["created"][:19].replace("T", " "), "상태": h["result"]["status"],
                       "보유 상태": details[h["run_id"]][0], "없는 원본": len(details[h["run_id"]][1]) or ""} for h in history], hide_index=True)
        counts = {}
        for state, _ in details.values():
            counts[state] = counts.get(state, 0) + 1
        st.caption(" · ".join(f"{k} {v}건" for k, v in counts.items()))
        choice = st.selectbox("이력 선택", [h["run_id"] for h in history], key="history_choice_" + project["id"],
                              format_func=lambda rid: next(projects.SOURCES[h["source"]][0] + " · " + h["created"][:16].replace("T", " ") + " · " + details[rid][0] for h in history if h["run_id"] == rid))
        item = next(h for h in history if h["run_id"] == choice)
        state, missing = details[choice]
        (st.info if state == "결과·원본 모두 있음" else st.warning)(state + " — " + AVAILABILITY_GUIDE[state])
        if state != "이력만 있음" and projects.available(item):
            st.button("이 시점 결과 열기", key="open_version_" + choice, on_click=_open_version, args=(project["id"], item),
                      help="자료 확인·다운로드 탭에서 이 수집 버전을 사용합니다.")
        if missing:
            st.caption(f"없는 원본 {len(missing)}개 — 원문 링크에서 다시 확인할 수 있습니다.")
            st.dataframe(missing, hide_index=True, column_config={"원문 링크": st.column_config.LinkColumn()})
        names = sorted({a["filename"] for r in item["result"].get("records", []) for a in r.get("assets", [])} - {m["파일명"] for m in missing})
        if names:
            protected = retention.pinned(names)
            st.caption(f"이 시점의 보유 원본 {len(names)}개 중 보호 {len(protected)}개. 보호한 원본은 저장 공간 정리 후보에서 제외됩니다.")
            if st.button("원본 보호 해제" if len(protected) == len(names) else "원본 보호", key="pin_" + choice):
                retention.pin(names, len(protected) != len(names))
                st.rerun()
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
    left, right, _ = st.columns([1, 1, 4])
    if left.button("프로젝트 목록", key="to_project_list"):
        _reset()
    if right.button("프로젝트 설정", key="edit_project_button"):
        st.session_state.edit_project = True
        st.rerun()
    if settings.SAMPLE_MODE:
        st.warning("SAMPLE 모드 — 실제 수집 자료가 아닙니다. 실행한 PowerShell 창에 ADETECT_SAMPLE_MODE=true가 남아 있으면 새 창에서 다시 실행하세요.")
    usage_bar("project_usage")
    history = projects.histories(pid)
    tabs = st.tabs(["자료 수집", "자료 확인·다운로드", "이력"])
    with tabs[0]:
        _collect(project, history)
    with tabs[1]:
        _result(project, history)
    with tabs[2]:
        _history(project, history)
