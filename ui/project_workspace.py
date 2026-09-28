"""프로젝트별 자료 수집·확인·다운로드 화면."""
import copy
import hashlib
import html
import json
import uuid
import streamlit as st
import pandas as pd

from config import settings
from core import projects, project_jobs, retention, project_sources, project_view, project_discovery
from core.collection import official_urls
from core.collection import words, paid_problem, TOKEN_MESSAGE
from core.exporters import facts_report, artifact_store
from ui.storage_panel import usage_bar, capacity_error
from core.materials import prioritized, summary, table_row, news_suggestions


def _reset():
    for key in list(st.session_state):
        if key not in ("step",):
            del st.session_state[key]
    st.session_state.step = "list"
    st.session_state.pop("project_id", None)
    st.rerun()


EXAMPLE = {  # 입력칸의 연한 예시는 한 프로젝트(한샘 리하우스)로 통일한다.
    "name": "예) 한샘 리하우스 캠페인 조사", "campaign": "예) 리하우스 캠페인", "category": "예) 인테리어 리모델링",
    "own_terms": "예) 한샘, 한셈, 한샘리하우스", "comp_terms": "예) 현대리바트, 리바트",
    "market": "예) 인테리어, 리모델링", "news": "예) 한샘, 한샘 리하우스",
    "include": "예) 리하우스, 리모델링", "exclude": "예) 채용, 주가",
    "official": "예)\nhttps://www.hanssem.com\nhttps://smartstore.naver.com/hanssem",
    "detail_url": "예) https://remodeling.hanssem.com/event?utm_source=meta&utm_campaign=rehaus",
    "instagram": "예) @hanssem 또는 https://www.instagram.com/hanssem",
    "youtube": "예) @hanssem 또는 UC로 시작하는 채널 ID",
    "meta_page": "예) https://www.facebook.com/ads/library/?view_all_page_id=123456789",
    "utm_urls": "예) 광고에서 확인한 랜딩 URL을 한 줄에 하나",
}
MARKET_HELP = "시장 조사를 원하는 검색어를 입력해주세요. 입력한 검색어의 검색 추이·검색량을 확인하고, 뉴스 검색어 후보로 활용합니다."


def _lines(value):
    return [x.strip() for x in (value or "").splitlines() if x.strip()]


def _brand_fields(cfg, b):
    """브랜드 한 개의 입력칸. 모든 값은 이 브랜드 id에 묶여 저장된다."""
    k = f"{cfg}_b_{b['id']}_"
    src = b.get("sources", {})
    own = b["role"] == "own"
    name = st.text_input("브랜드명", value=b.get("name", ""), placeholder="예) 한샘" if own else "예) 현대리바트", key=k + "name")
    terms = words(st.text_input(f"검색어 묶음 (쉼표로 구분, 최대 {projects.MAX_TERMS}개)", value=", ".join(b.get("terms", [])),
                                placeholder=EXAMPLE["own_terms"] if own else EXAMPLE["comp_terms"], key=k + "terms",
                                help="같은 브랜드의 공식 표기와 오타·변형을 넣습니다. 검색 추이는 묶음 전체를 한 주제로, 월간 검색량은 표기별 값을 합산해 보여줍니다."))
    official = _lines(st.text_area("공식 홈페이지 및 관련 URL (한 줄에 하나)", value="\n".join(src.get("official_urls") or ([src["homepage"]] if src.get("homepage") else [])),
                                   placeholder=EXAMPLE["official"], key=k + "official", height=88))
    left, right = st.columns(2)
    instagram = left.text_input("공식 Instagram 계정", value=src.get("instagram", ""), placeholder=EXAMPLE["instagram"], key=k + "instagram")
    youtube = right.text_input("공식 YouTube 채널", value=src.get("youtube", ""), placeholder=EXAMPLE["youtube"], key=k + "youtube")
    with st.expander("광고·캠페인 상세 설정 (선택)"):
        meta = st.text_input("Meta 광고 라이브러리 페이지 (선택)", value=src.get("meta_page", ""), placeholder=EXAMPLE["meta_page"], key=k + "meta",
                             help="facebook.com/ads/library에서 브랜드 페이지의 '모든 광고 보기' 주소. view_all_page_id=숫자가 있어야 합니다.")
        detail = st.text_input("캠페인 상세 URL (선택)", value=src.get("detail_url", ""), placeholder=EXAMPLE["detail_url"], key=k + "detail",
                               help="광고 랜딩 URL을 넣으면 UTM 구조를 분석합니다.")
        utm_urls = _lines(st.text_area("UTM 분석 대상 URL (선택)", value="\n".join(src.get("utm_urls", [])), placeholder=EXAMPLE["utm_urls"], key=k + "utm", height=68))
    return {**b, "id": b["id"], "name": name.strip(), "role": b["role"], "terms": projects.clean_terms(terms or ([name.strip()] if name.strip() else [])),
            "sources": {"official_urls": official, "homepage": official[0] if official else "", "detail_url": detail.strip(),
                        "instagram": instagram.strip(), "youtube": youtube.strip(), "meta_page": meta.strip(), "utm_urls": utm_urls}}


def _add_competitor():
    st.session_state.cfg_brands.append({"id": "c-" + uuid.uuid4().hex[:8], "name": "", "role": "competitor", "terms": [], "sources": {}})


def _remove_brand(bid):
    st.session_state.cfg_brands = [b for b in st.session_state.cfg_brands if b["id"] != bid]


def _append_news(values):
    current = words(st.session_state.get("project_news", ""))
    st.session_state.project_news = ", ".join(projects.clean_terms(current + list(values)))


def _config(project=None):
    if project is None:
        from ui.project_setup import render
        return render(_brand_fields, _reset)
    draft = {} if project else st.session_state.get("draft", {})
    base = projects.project_inputs(project or {"brand_name": draft.get("brand_name", ""), "category": draft.get("category", ""), "paid_enabled": True})
    cfg = "cfg_" + (project["id"] if project else "new")
    if st.session_state.get("cfg_key") != cfg:
        for key in list(st.session_state):
            if key.startswith(("project_", "news_", "cfg_")) and key != "project_id":
                del st.session_state[key]
        st.session_state.cfg_key = cfg
        st.session_state.cfg_brands = copy.deepcopy(base["brands"])
        st.session_state.pop("project_news", None)
    if "project_news" not in st.session_state:
        st.session_state.project_news = ", ".join(base.get("news_keywords", []))
    st.title("프로젝트 설정")

    st.subheader("프로젝트 기본 정보")
    name = st.text_input("프로젝트 이름", value=(project or {}).get("name", ""), placeholder=EXAMPLE["name"], key="project_name")
    left, right = st.columns(2)
    campaign = left.text_input("조사 대상 (선택)", value=base.get("campaign", ""), placeholder=EXAMPLE["campaign"], key="project_campaign")
    category = right.text_input("관심 주제 (선택)", value=base.get("category", ""), placeholder=EXAMPLE["category"], key="project_category")

    st.subheader("조사 브랜드 및 경쟁사")
    st.caption(f"자사 1개와 경쟁사 최대 {projects.MAX_COMPETITORS}개. 검색 추이는 모든 브랜드를 한 요청으로 조회해 같은 기준으로 비교합니다. "
               "계정은 자동으로 추측하지 않으며, 비어 있으면 그 브랜드의 해당 자료만 건너뜁니다.")
    brands = []
    for b in st.session_state.cfg_brands:
        label = ("자사 · " if b["role"] == "own" else "경쟁사 · ") + (b.get("name") or "새 경쟁사")
        with st.expander(label, expanded=b["role"] == "own" or not b.get("name")):
            brands.append(_brand_fields(cfg, b))
            if b["role"] != "own":
                st.button("이 경쟁사 삭제", key=f"{cfg}_rm_{b['id']}", on_click=_remove_brand, args=(b["id"],))
    st.session_state.cfg_brands = copy.deepcopy(brands)
    competitors = sum(1 for b in brands if b["role"] == "competitor")
    st.button("경쟁사 추가", key="add_competitor", on_click=_add_competitor, disabled=competitors >= projects.MAX_COMPETITORS,
              help=f"최대 {projects.MAX_COMPETITORS}개 (데이터랩 한 요청 최대 5개 주제)")
    for term, owners in projects.term_conflicts(brands):
        st.warning(f"'{term}'이(가) {', '.join(owners)}에 함께 들어 있습니다. 같은 검색어가 여러 브랜드에 있으면 비교가 왜곡될 수 있으니 한 브랜드에만 두세요.")

    st.subheader("시장 관심 검색어")
    market = words(st.text_input("시장 관심 검색어", value=", ".join(base.get("market_keywords", [])), placeholder=EXAMPLE["market"], key="project_market"))
    st.caption(MARKET_HELP + " 브랜드 검색량 합계에는 포함하지 않습니다.")

    st.subheader("뉴스 검색 설정")
    news = words(st.text_input(f"뉴스 검색어 (최대 {projects.MAX_NEWS}개)", placeholder=EXAMPLE["news"], key="project_news",
                               help="이 칸의 검색어로만 뉴스를 요청합니다. 비어 있으면 뉴스를 수집하지 않습니다."))
    left, right = st.columns([1, 3])
    left.button("시장 관심 검색어 가져오기", key="import_market_news", on_click=_append_news, args=(market,), disabled=not market)
    own_name = brands[0]["name"] if brands else base["brand_name"]
    candidates = [c for c in news_suggestions(own_name, campaign, category, market) if projects.term_key(c) not in {projects.term_key(n) for n in news}]
    if candidates:
        chosen = right.multiselect("뉴스 검색어 후보 (선택해야 반영)", candidates, key="news_candidates", label_visibility="collapsed", placeholder="뉴스 검색어 후보 선택")
        right.button("선택한 후보 추가", key="add_news_candidates", on_click=_append_news, args=(chosen,), disabled=not chosen)
    with st.expander("뉴스 결과 좁히기", expanded=bool(base["news_filter"].get("include") or base["news_filter"].get("exclude"))):
        st.caption("뉴스 검색어는 무엇을 검색할지, 이 조건은 받은 기사 중 무엇을 보여줄지 정합니다. 기사 전문이 아니라 제목·발췌문에만 적용하며, "
                   "빼고 싶은 문구가 우선합니다. 검색량·SNS·광고 등 다른 자료에는 적용하지 않고, 숨긴 기사도 원본은 보관합니다.")
        include = words(st.text_input("꼭 들어갈 문구 (하나 이상 포함)", value=", ".join(base["news_filter"].get("include", [])), placeholder=EXAMPLE["include"], key="news_include"))
        exclude = words(st.text_input("빼고 싶은 문구 (하나라도 있으면 숨김)", value=", ".join(base["news_filter"].get("exclude", [])), placeholder=EXAMPLE["exclude"], key="news_exclude"))
    if base.get("legacy_filter_converted"):
        st.info("이전 버전의 포함·제외 문구를 뉴스 전용 필터로 옮겼습니다. 저장하면 적용되며, 과거 수집 당시 입력 사본은 바뀌지 않습니다.")

    p = {**base, "brands": brands, "market_keywords": projects.clean_terms(market), "news_keywords": projects.clean_terms(news),
         "news_filter": {"include": include, "exclude": exclude}, "campaign": campaign, "category": category,
         "paid_enabled": base.get("paid_enabled", True), "save_images": True, "save_ad_assets": True}
    errors = projects.validate_inputs(p)
    for message in errors:
        st.warning(message)
    left, right = st.columns([1, 5])
    if left.button("설정 저장", type="primary", disabled=bool(errors), key="save_project"):
        # 이름을 비워두면 브랜드명·조사 대상으로 만든다.
        own = projects.own_brand(p)
        title = name.strip() or " ".join(x for x in (own["name"], campaign.strip()) if x)
        stored = projects.to_storage(p)
        if project:
            projects.update(project["id"], title, stored)
            pid = project["id"]
        else:
            pid = projects.create(title, stored)
        st.session_state.project_id = pid
        st.session_state.step = "workspace"
        st.session_state.pop("edit_project", None)
        st.session_state.pop("cfg_key", None)
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
DEFAULT_SOURCES = ("trend", "volume", "news", "website")
SCOPED = ("website", "meta", "search_capture", "instagram", "youtube")


def _set_sources(pid, p, paid, mode):
    """선택 버튼은 체크 상태만 바꾼다. 수집은 '선택 자료 수집'을 눌러야 시작된다."""
    for source in projects.SOURCES:
        ready, _ = project_sources.readiness(source, p, paid)
        value = {"all": ready, "none": False, "default": ready and source in DEFAULT_SOURCES}[mode]
        st.session_state["select_" + pid + source] = value


def _collect(project, history):
    pid = project["id"]
    p = projects.project_inputs(project)
    tasks = project_jobs.tasks(pid)
    busy = any(t["state"] in ("대기", "수집 중") for t in tasks)
    _watch(pid)
    paid = st.toggle("유료 기능 ON", value=p.get("paid_enabled", True), key="collection_paid", disabled=busy,
                     help="ON일 때만 유료 수집(Meta 광고·Instagram, 검색 화면 AI 보완 판독)을 선택할 수 있습니다.")
    p["paid_enabled"] = paid
    if paid and paid_problem(p, "Apify") == TOKEN_MESSAGE:
        st.warning("Apify · " + TOKEN_MESSAGE)

    st.markdown("**브랜드별 수집 대상**")
    mark = lambda v: "입력" if v else "—"
    st.dataframe([{"브랜드": b["name"], "구분": "자사" if b["role"] == "own" else "경쟁사", "검색어 묶음": ", ".join(b["terms"]),
                   "공식 URL": len(official_urls(b.get("sources", {}))) or "—", "Instagram": mark(b["sources"].get("instagram")),
                   "YouTube": mark(b["sources"].get("youtube")), "Meta 광고": mark(b["sources"].get("meta_page"))} for b in p["brands"]], hide_index=True)
    st.caption("시장 관심 검색어: " + (", ".join(p.get("market_keywords", [])) or "미입력") + " · 뉴스 검색어: " + (", ".join(p.get("news_keywords", [])) or "미입력 — 뉴스 요청 안 함"))

    b1, b2, b3, _ = st.columns([1.2, 1, 1, 3])
    b1.button("기본 자료 선택", disabled=busy, key="default_sources", on_click=_set_sources, args=(pid, p, paid, "default"))
    b2.button("전체 선택", disabled=busy, key="select_all_sources", on_click=_set_sources, args=(pid, p, paid, "all"))
    b3.button("전체 해제", disabled=busy, key="clear_sources", on_click=_set_sources, args=(pid, p, paid, "none"))
    selected, options = [], {}
    names = {b["id"]: b["name"] for b in p["brands"]}
    with st.container(key="adetect_sources"):
        for source, (label, description, _) in projects.SOURCES.items():
            ready, reason = project_sources.readiness(source, p, paid)
            if not ready:
                st.session_state["select_" + pid + source] = False
            latest = next((h for h in history if h["source"] == source and projects.available(h)), None)
            if st.checkbox(label, key="select_" + pid + source, disabled=busy or not ready):
                selected.append(source)
            meta = (f"최근 {latest['created'][:16].replace('T', ' ')} · {_size(latest)}" if latest else "저장 자료 없음") + (f" · 선택 불가: {reason}" if not ready else "")
            st.markdown(f"<div class='adetect-src-desc'>{html.escape(description)}</div><div class='adetect-src-meta{' done' if latest else ''}'>{html.escape(meta)}</div>", unsafe_allow_html=True)
            if source in selected and source in SCOPED:
                default = project_sources.default_brands(source, p, history)
                field = {"instagram": "instagram", "youtube": "youtube", "meta": "meta_page"}.get(source)
                allowed = [b["id"] for b in p["brands"] if not field or b["sources"].get(field)]
                chosen = st.multiselect("수집할 브랜드", allowed, default=[d for d in default if d in allowed], format_func=names.get,
                                        key=f"scope_{pid}_{source}", disabled=busy,
                                        help="경쟁사를 추가해도 추가 자료는 자동으로 모두 수집하지 않습니다. 유료 SNS는 저장 자료가 없는 브랜드가 기본입니다.")
                options[source] = {"brands": chosen}
                if source == "search_capture":
                    ai_ready = paid and not paid_problem(p, "Gemini")
                    ai = st.checkbox("광고 영역 AI 보완 판독 (Gemini, 유료 · 직접 추출이 부족한 캡처만)", value=ai_ready, disabled=busy or not ai_ready, key=f"ai_read_{pid}")
                    options[source]["ai_read"] = ai and ai_ready
                    st.caption("관측 검색어: " + (", ".join(project_sources.capture_keywords(p, chosen)) or "없음") + " · 같은 검색어는 한 번만 캡처하고 모든 브랜드를 함께 판독합니다.")
    force = st.checkbox("캐시를 사용하지 않고 새로 수집", disabled=busy, key="force_collection")
    if selected:
        paid_targets = []
        for source in selected:
            if source in PAID_SOURCES:
                paid_targets.append(projects.SOURCES[source][0] + " (" + ", ".join(names[b] for b in options.get(source, {}).get("brands", [])) + ")")
        if options.get("search_capture", {}).get("ai_read"):
            paid_targets.append("검색 화면 AI 보완 판독 (필요한 캡처만)")
        count = len({b for s in selected for b in (options.get(s, {}).get("brands") or ([x["id"] for x in p["brands"]] if s in ("trend", "volume") else [projects.own_brand(p)["id"]]))})
        st.info(f"대상 브랜드 {count}개 · 선택 자료: {', '.join(projects.SOURCES[s][0] for s in selected)}\n\n"
                f"유료 수집: {', '.join(paid_targets) or '없음'}\n\n"
                + ("캐시: 사용하지 않고 새로 요청" if force else "캐시: 24시간 안에 같은 조건으로 받은 결과는 다시 요청하지 않음")
                + ("\n\n검색 추이는 비교 구성 전체(" + ", ".join(b["name"] for b in p["brands"]) + ")를 한 요청으로 새로 조회합니다." if "trend" in selected else ""))
    if st.button("선택 자료 수집", type="primary", disabled=busy or not selected, key="start_project_collection"):
        try:
            project_jobs.submit({**project, "paid_enabled": paid}, selected, force=force, options=options)
            st.rerun()
        except ValueError as exc:
            capacity_error(exc, "collect_capacity_go")
    latest = {}
    for h in history:
        latest.setdefault(h["source"], h)
    problems = [(projects.SOURCES[s][0], pt.get("label", ""), pt["state"], pt.get("message", ""))
                for s, h in latest.items() for pt in h["result"].get("parts", {}).values() if pt.get("state") not in ("완료", None)]
    problems += [(projects.SOURCES[s][0], "", h["result"]["status"], "; ".join(h["result"].get("errors", []))) for s, h in latest.items() if not h["result"].get("parts") and h["result"].get("status") == "실패"]
    if problems and not busy:
        with st.expander(f"최근 수집에서 실패·건너뜀 {len(problems)}건"):
            st.dataframe([{"자료": a, "대상": b, "상태": c, "안내": d} for a, b, c, d in problems], hide_index=True)
    full = [projects.SOURCES[s][0] for s, h in latest.items()
            if retention.is_capacity_error(json.dumps([h["result"].get("errors", []), [pt.get("message", "") for pt in h["result"].get("parts", {}).values()]], ensure_ascii=False))]
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
        parts = item["result"].get("parts", {}).values()
        compare = next((pt["comparison"] for pt in parts if pt.get("comparison")), None)
        if compare:
            return f"{len(compare['series'])}개 브랜드 비교"
        months = max((len(pt["series"]["rows"]) for pt in parts if pt.get("series")), default=0)
        return f"{months}개월 (이전 방식)"
    return f"{len(item['result'].get('records', []))}건"


def _when(item):
    return item["created"][:16].replace("T", " ")


def _open_version(pid, item):
    """이력 탭의 '이 시점 결과 열기' — 위젯 생성 전에 상태를 바꿀 수 있도록 on_click 콜백으로만 호출한다."""
    st.session_state["version_" + pid + item["source"]] = item["run_id"]
    st.session_state.opened_version = projects.SOURCES[item["source"]][0] + " · " + _when(item)


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
STATE_TEXT = {"none": "미수집"}


@st.cache_data(max_entries=64, show_spinner=False)
def _image(filename, sha256):
    from core.evidence_store import read_bytes
    return read_bytes({"filename": filename, "sha256": sha256})


def _section(title):
    st.markdown(f"<div class='adetect-section'>{html.escape(title)}</div>", unsafe_allow_html=True)


def _status_line(item, source):
    """자료가 없는 영역은 빈 표 대신 상태를 한 줄로 알린다."""
    if item is None:
        st.caption(projects.SOURCES[source][0] + " · 미수집")
        return
    parts = item["result"].get("parts", {}).values()
    bad = [f"{pt.get('label')} — {pt['state']}" + (f" ({pt['message']})" if pt.get("message") else "") for pt in parts if pt.get("state") not in ("완료",)]
    if bad:
        st.caption(" · ".join(bad))


def _trend_chart(series, start=None, end=None, height=240):
    from core.result_insights import monthly_values
    frame = pd.DataFrame({s.get("name") or s.get("keyword", "검색어"): pd.Series(monthly_values(s), dtype=float) for s in series})
    if frame.empty:
        st.caption("제공된 월별 검색지수가 없습니다.")
        return
    if start and end:
        frame = frame.reindex(pd.period_range(start[:7], end[:7], freq="M").astype(str))
    else:
        frame = frame.reindex(pd.period_range(frame.index.min(), frame.index.max(), freq="M").astype(str))
    frame.index.name = "월"
    st.line_chart(frame, height=height)


def _trend(item, p):
    from core.result_insights import trend_facts
    def facts(series):
        for f in trend_facts(series):
            st.markdown(f"**{f['항목']}** · {f['관측 사실']}")
    view = project_view.trend_view(item, p)
    if view["kind"] == "none":
        st.caption("검색 추이 · 미수집")
        return
    if view["kind"] == "legacy":
        st.info("이전 방식(검색어별 별도 요청)으로 수집한 추이입니다. 요청마다 최고치가 100이라 브랜드끼리 비교할 수 없습니다. 비교 차트는 검색 추이를 새로 수집하면 표시됩니다.")
        if view["series"]:
            chosen = st.selectbox("검색어", [x["keyword"] for x in view["series"]], key="legacy_trend_topic")
            s = next(x for x in view["series"] if x["keyword"] == chosen)
            _trend_chart([s], s.get("start"), s.get("end"), height=220)
            facts(s)
        return
    compare = view["compare"]
    if view["stale"]:
        st.warning("프로젝트의 비교 브랜드 또는 검색어 묶음이 바뀌었습니다. 아래 차트는 수집 당시 구성이며, 새 구성으로 비교하려면 검색 추이를 다시 수집하세요.")
    _trend_chart(compare["series"], compare["start"], compare["end"], height=280)
    missing = [s["name"] for s in compare["series"] if not s.get("provided")]
    st.caption(f"{compare['start']} ~ {compare['end']} 월간 · 한 요청 안의 전체 최고 월=100인 상대지수(검색 횟수 아님) · 빠진 달은 0이 아님"
               + (" · 응답 없음: " + ", ".join(missing) if missing else "") + (" · SAMPLE" if compare.get("sample") else ""))
    for series in compare["series"]:
        st.markdown("**" + series["name"] + " · 주요 관측값**")
        facts({**series, "start": compare["start"], "end": compare["end"]})
    with st.expander("비교 구성과 월별 평균"):
        st.dataframe([{"브랜드": s["name"], "검색어 묶음": ", ".join(s["terms"]), "제공 월수": len(s["rows"])} for s in compare["series"]], hide_index=True)
        season = compare.get("seasonality", {})
        monthly = pd.DataFrame([{"월": f"{m['월']:02d}월", "브랜드": s["name"], "평균": m["평균 검색지수"]} for s in compare["series"] for m in season.get(s["brand_id"], {}).get("monthly", [])])
        if not monthly.empty:
            st.bar_chart(monthly.pivot_table(index="월", columns="브랜드", values="평균"), height=220, stack=False)
    if view["market"]:
        with st.expander("시장 관심 검색어 추이 (검색어별 별도 기준)"):
            chosen = st.selectbox("검색어", [x["keyword"] for x in view["market"]], key="market_trend_topic")
            s = next(x for x in view["market"] if x["keyword"] == chosen)
            _trend_chart([s], s.get("start"), s.get("end"), height=200)
            st.caption("이 검색어만의 최고 월=100. 브랜드 비교 차트와 크기를 비교할 수 없습니다.")
            facts(s)


def _editor(rows, token, selection):
    """다운로드 선택 체크박스만 편집한다. 변경은 바로 선택에 반영된다(별도 적용 버튼 없음)."""
    frame = pd.DataFrame([table_row(r, r["selection_id"] in selection) for r in rows])
    config = {"출처": st.column_config.LinkColumn(), "다운로드": st.column_config.CheckboxColumn(width="small")}
    if "랜딩" in frame:
        config["랜딩"] = st.column_config.LinkColumn()
    edited = st.data_editor(frame, hide_index=True, disabled=[c for c in frame if c != "다운로드"], column_config=config,
                            key="records_" + token, height=min(38 * len(rows) + 40, 420))
    for original, item in zip(rows, edited.to_dict("records")):
        (selection.add if item["다운로드"] else selection.discard)(original["selection_id"])


def _details(rows, p, token, selection):
    search = st.text_input("자료 검색", key="project_record_search", placeholder=f"자료 {len(rows)}건에서 검색 (검색은 표시만 바꾸며 다운로드 선택은 유지)")
    visible = [r for r in rows if not search or search.casefold() in str(r).casefold()]
    news, hidden = project_view.news_view(visible, p["news_filter"])
    others = [r for r in visible if r["kind"] not in ("뉴스", "검색 화면")]
    kinds = list(dict.fromkeys(r["kind"] for r in prioritized(others)))
    volume = [r for r in others if r["kind"] in ("검색량", "연관 검색어")]
    if news:
        st.markdown("**뉴스**")
        st.caption(summary("뉴스", news) + (f" · 뉴스 결과 좁히기로 숨긴 기사 {hidden}건" if hidden else "") + " · 중복 기사는 한 행으로 표시")
        _editor(news, token + "news", selection)
    elif hidden:
        st.caption(f"뉴스 · 설정한 뉴스 결과 좁히기 조건으로 {hidden}건 모두 숨김 (원본 보관)")
    if volume:
        with st.expander("검색어별 월간 검색량 내역 · 연관 검색어"):
            exact = [r for r in volume if r["kind"] == "검색량"]
            if exact:
                st.caption(summary("검색량", exact))
                _editor(exact, token + "vol", selection)
            related = [r for r in volume if r["kind"] == "연관 검색어"]
            if related:
                st.caption("연관 검색어 (브랜드 합계에 포함하지 않음)")
                _editor(related, token + "rel", selection)
    for kind in [k for k in kinds if k not in ("검색량", "연관 검색어")]:
        group = [r for r in others if r["kind"] == kind]
        with st.expander(f"{kind} · {len(group)}건"):
            st.caption(summary(kind, group))
            _editor(group, token + kind, selection)


def _search_area(rows, item):
    captures = [r for r in rows if r["kind"] == "검색 화면"]
    if not captures:
        _status_line(item, "search_capture") if item else st.caption("검색 화면 · 미수집")
        return
    st.caption("네이버 PC 검색 결과를 한 번 관측한 기록입니다. 첫 화면 캡처와 광고 영역 확대 캡처, 페이지에서 직접 읽은 광고 문구·링크를 보여줍니다. "
               "'이번 화면에서 미관측'은 미운영을 뜻하지 않으며, 캡처 실패·차단·영역 식별 실패는 '판독 불가'입니다. 광고를 클릭해 랜딩을 확인하지 않습니다.")
    observed = project_view.search_status_rows(captures, None)
    if observed:
        st.dataframe(observed, hide_index=True)
    else:
        st.caption("선택한 검색 화면에서 브랜드가 확정된 광고 관측 없음 · 전체 판독 상태는 원본 데이터에 보관합니다.")
    for r in captures:
        if not r.get("ads") and not (r.get("ai_read") or {}).get("ads"):
            continue
        with st.expander(f"{r.get('keyword')} · {r.get('environment', '')} · {(r.get('observed_at') or '')[:16].replace('T', ' ')}"):
            images = [a for a in r.get("assets", []) if a.get("filename", "").lower().endswith(IMAGE_EXT)]
            cols = st.columns(max(len(images), 1))
            for col, asset in zip(cols, images):
                data = _image(asset["filename"], asset.get("sha256", ""))
                with col:
                    if data is None:
                        st.caption(f"{asset.get('role', '캡처')} — 저장 이미지가 만료되었거나 없습니다. 검색 화면을 다시 수집하세요.")
                    else:
                        st.image(data, caption=asset.get("role", "캡처"), width="stretch")
            if not images:
                st.caption("저장된 캡처 이미지 없음" + (" (SAMPLE)" if r.get("sample") else ""))
            ads = [{"영역": {"powerlink": "파워링크", "brand_search": "브랜드검색"}.get(a["area"], a["area"]), "광고 문구": a.get("text"), "표시 URL": a.get("display_url"),
                    "링크": (a.get("links") or [None])[0], "판독 방식": a.get("method")} for a in r.get("ads", [])]
            ai = r.get("ai_read") or {}
            ads += [{"영역": a["area"], "광고 문구": " ".join(x for x in (a.get("advertiser_visible"), a.get("copy_visible")) if x),
                     "표시 URL": a.get("display_url_visible"), "링크": None, "판독 방식": f"AI 판독 · 신뢰도 {a['confidence']}"} for a in ai.get("ads", [])]
            if ads:
                st.dataframe(ads, hide_index=True, column_config={"링크": st.column_config.LinkColumn()})
            if ai.get("state") in ("실패",):
                st.caption("AI 보완 판독 실패 — 캡처와 직접 추출 결과는 그대로 사용할 수 있습니다.")
            st.markdown(f"[원문 검색 결과 열기]({r['source_url']})")


def _utm(p, rows):
    from core import utm
    data = project_sources.utm_rows(p, rows)
    if not data:
        st.caption("값이 있는 UTM 미관측 · UTM 값이 하나 이상 있는 URL만 표시합니다.")
        return [], []
    groups = utm.structure_rows(data)
    st.caption("URL을 방문하지 않고 주소만 분석합니다. 추적 파라미터만으로 실제 집행 매체·성과·전환을 확정하지 않습니다. 민감한 값은 가립니다.")
    if groups:
        st.caption("브랜드·UTM 항목별 관측값과 문자 구조 추정입니다. source·medium·content를 합치지 않으며 토큰의 의미를 추정하지 않습니다.")
        st.dataframe([{k: v for k, v in r.items() if k in ("브랜드", "UTM 항목", "관측값", "추정 구조", "근거 URL 수")} for r in groups], hide_index=True)
    with st.expander("UTM 원본 URL과 파라미터"):
        st.dataframe(utm.public(data), hide_index=True)
        st.dataframe(groups, hide_index=True)
    return utm.public(data), groups


def _news_sections(rows):
    from core.result_insights import news_sections
    from core.exporters.visual_report import link
    sections = news_sections(rows)
    if not sections: return
    _section("뉴스 주제별 요약")
    st.caption("선택한 기사를 제목의 주제로 묶고 유사 기사에는 대표 발췌를 표시합니다. 호재·악재를 자동 판정하지 않습니다.")
    for section in sections:
        with st.expander(f"{section['title']} · {section['count']}건", expanded=len(sections) <= 4):
            for group in section["groups"]:
                st.markdown("**" + group["title"] + "**")
                st.write(group["excerpt"] or "발췌 미제공")
                with st.expander(f"출처 {len(group['articles'])}건 · 제목 유사 기사"):
                    for row in group["articles"]:
                        st.caption(row.get("published_at") or "발행일 미제공")
                        st.markdown(link(row.get("source_url"), row.get("title") or group["title"]), unsafe_allow_html=True)


def _ad_cards(rows, token):
    from core.exporters.visual_report import link
    ads = [r for r in rows if r["kind"] == "광고"]
    if not ads: return
    _section("광고 소재")
    st.caption(summary("광고", ads))
    brands = list(dict.fromkeys(r.get("brand", "") for r in ads))
    chosen = st.selectbox("광고 브랜드", ["전체", *brands], key="ad_brand_" + token)
    if chosen != "전체": ads = [r for r in ads if r.get("brand") == chosen]
    pages = max(1, (len(ads)+11)//12)
    page = st.selectbox("광고 페이지", range(1, pages+1), key="ad_page_" + token + chosen) if pages > 1 else 1
    for start in range((page-1)*12, min(page*12, len(ads)), 3):
        for col, row in zip(st.columns(3), ads[start:min(start+3, page*12)]):
            with col:
                with st.container(border=True):
                    image = next((a for a in row.get("assets", []) if a.get("filename", "").lower().endswith(IMAGE_EXT)), None)
                    data = _image(image["filename"], image.get("sha256", "")) if image else None
                    if data: st.image(data, width="stretch")
                    else: st.caption("저장 이미지 없음 · 광고 원문 확인")
                    st.markdown("**" + row.get("brand", "") + "**")
                    st.caption(" · ".join(str(v) for v in (row.get("format"), row.get("start_date"), row.get("cta")) if v))
                    st.write(row.get("text", "")[:500])
                    if len(row.get("text", "")) > 500:
                        with st.expander("전체 문구"): st.write(row["text"])
                    st.markdown(link(row.get("source_url"), "광고 원문") + " &nbsp; " + link(row.get("landing_url"), "랜딩 페이지 ↗"), unsafe_allow_html=True)


def _stat_resources(project, p):
    from core import stat_discovery
    _section("추가 정보를 찾아보세요")
    st.caption("브랜드·관심 시장에 맞는 통계와 산업 자료를 검색합니다. 버튼을 누르면 Gemini 검색 1회 + 정리 1회가 발생하며 성공 결과는 24시간 재사용합니다.")
    saved = stat_discovery.load(project["id"], p)
    if st.button("맞춤 통계 자료 찾기", key="stat_search_" + project["id"], disabled=not p.get("paid_enabled", True)):
        with st.spinner("관련 통계 자료의 출처를 찾고 있습니다…"):
            found = stat_discovery.generate(p)
        if found.get("status") == "완료":
            try:
                stat_discovery.save(project["id"], p, found)
                saved = found
            except ValueError as exc:
                capacity_error(exc, "stat_capacity")
        else: st.warning(found.get("message", "검색 실패"))
    if saved:
        st.caption("AI 검색 기반 추천 후보 · 원문에서 조사 기간·지역·단위를 확인하세요. 검색일 " + saved.get("created", "")[:10])
        for resource in saved.get("resources", []):
            from core.exporters.visual_report import link
            st.markdown(link(resource["출처"], resource["자료명"]), unsafe_allow_html=True)
            st.write(resource["추천 이유 (AI)"])
            with st.expander("검색 근거·신뢰도"):
                st.write(resource["검색 근거"])
                st.caption(resource["방식"] + " · " + resource["신뢰도"])
    else:
        st.caption("현재 브랜드·시장 조건으로 검색한 통계 자료 후보가 없습니다.")
    return (saved or {}).get("resources", [])


def _result(project, history):
    pid = project["id"]
    p = projects.project_inputs(project)
    by_source = _versions([h for h in history if projects.available(h)])
    if not by_source:
        st.info("자료를 수집하면 확인하고 다운로드할 수 있습니다.")
        return
    snapshots = []
    for source, versions in by_source.items():
        key = "version_" + pid + source
        if key in st.session_state and st.session_state[key] not in [h["run_id"] for h in versions]:
            del st.session_state[key]
        # 이전 자료를 고르지 않았으면 최근 성공 결과를 쓴다.
        snapshots.append(next((h for h in versions if h["run_id"] == st.session_state.get(key)), versions[0]))
    if st.session_state.get("opened_version"):
        st.success("이력에서 연 자료: " + st.session_state.pop("opened_version"))
    older = [i for i in snapshots if i is not by_source[i["source"]][0]]
    with st.expander("이전에 수집한 자료 보기" + (f" · {len(older)}종 이전 자료 표시 중" if older else ""), expanded=bool(older)):
        for source, versions in by_source.items():
            st.selectbox(projects.SOURCES[source][0], [h["run_id"] for h in versions], key="version_" + pid + source,
                         format_func=lambda rid, rows=versions: next(_when(h) + " 수집 · " + _size(h) + (" · 최근" if h is rows[0] else "") for h in rows if h["run_id"] == rid))
    dates = projects.collection_dates(snapshots)
    if len(dates) > 1:
        st.caption("수집일이 다른 자료가 함께 표시됩니다 (" + ", ".join(dates) + "). 다운로드 파일에도 기록됩니다.")
    by = {i["source"]: i for i in snapshots}
    rows = [row for item in snapshots for row in projects.display_rows(item)]
    scope = pid + ":" + ",".join(i["run_id"] for i in snapshots)
    if st.session_state.get("selection_scope") != scope:
        st.session_state.selection_scope = scope
        st.session_state.download_selection = set(projects.default_selection(snapshots))
    selection = set(st.session_state.download_selection)

    _section("브랜드 비교 요약")
    comparison, notes = project_view.comparison_rows(p, snapshots, by.get("volume"))
    st.dataframe(comparison, hide_index=True)
    st.caption(" · ".join(notes + ["월간 검색량은 검색어 묶음의 정확히 일치한 표기만 더한 검색 횟수(고유 검색자 수 아님)이며 연관 검색어는 제외",
                                   "검색 추이(3년 전 1월~직전 월 상대지수)와 기간·단위가 다름"]))

    _section("검색 추이")
    _trend(by.get("trend"), p)

    from core.analyzers import news_digest
    shown_news, _ = project_view.news_view(rows, p["news_filter"])
    digest = None
    if shown_news and by.get("news"):
        _section("뉴스 핵심 내용·수치 요약")
        st.caption("제목·발췌 기준 · 최신순 최대 30건 · 기사 원문 전체를 읽지 않습니다. 요약 버튼을 누를 때만 Gemini 호출이 발생합니다.")
        digest = news_digest.load(by["news"]["run_id"], shown_news)
        if st.button("수집한 뉴스 요약하기", disabled=not p.get("paid_enabled", True) or bool(digest), key="news_digest_" + pid):
            with st.spinner("뉴스 발췌에서 근거를 정리하고 있습니다…"):
                digest = news_digest.generate(shown_news)
                try:
                    news_digest.save(by["news"]["run_id"], shown_news, digest)
                except ValueError as exc:
                    capacity_error(exc, "digest_capacity")
        if not p.get("paid_enabled", True):
            st.caption("프로젝트 설정에서 유료 기능을 켜면 사용할 수 있습니다.")
        if digest:
            if digest.get("status") == "완료":
                st.caption(f"대상 {len(shown_news)}건 중 {digest['processed']}건 검토 · " + digest["message"])
                highlights = news_digest.export_rows(digest, shown_news)
                if highlights: st.dataframe(highlights, hide_index=True, column_config={"출처": st.column_config.LinkColumn()})
                else: st.info("발췌 안에서 요약할 만한 핵심 근거를 찾지 못했습니다. 원문 링크를 확인해주세요.")
            else: st.warning(digest.get("message", "요약 실패"))
        else:
            st.caption("현재 수집 버전·뉴스 필터에 맞는 저장 요약이 없습니다. 기존 뉴스 수집 없이 요약만 요청할 수 있습니다.")

    token = hashlib.sha256(scope.encode()).hexdigest()[:12]
    with st.expander("원본 데이터·다운로드 선택"):
        _details(rows, p, token, selection)
    st.session_state.download_selection = selection
    selected_rows = [r for r in rows if r["selection_id"] in selection and projects.news_passes(r, p["news_filter"])]
    _news_sections(selected_rows)
    _ad_cards(selected_rows, token)

    _section("검색 화면과 광고 관측")
    _search_area(selected_rows, by.get("search_capture"))

    _section("UTM 구조")
    utm_data, utm_groups = _utm(p, [r for r in rows if r["selection_id"] in selection])

    stat_resources = _stat_resources(project, p)
    _section("다운로드")
    extra = {"comparison": comparison, "comparison_notes": notes, "utm": utm_data, "utm_structures": utm_groups, "stat_resources": stat_resources}
    result = projects.selection_result(project, snapshots, selection, p["news_filter"], extra)
    st.caption(f"다운로드 대상 {len(result['records'])}건 (선택한 자료 중 뉴스 결과 좁히기를 통과한 자료)"
               + (f" · 수집일 혼합 {', '.join(dates)}" if len(dates) > 1 else "") + (" · SAMPLE 포함" if result.get("sample_sources") else ""))
    result["news_digest"] = news_digest.export_rows(digest, result["records"])
    _download(project, result)



def _download(project, result):
    # 생성 버튼 key는 rerun마다 고정해야 클릭이 유지된다. 선택·필터·버전이 바뀌면 signature가 달라지고,
    # 그 전에 만든 파일은 다운로드 버튼을 내리지 않고 '다시 생성' 안내만 한다.
    stable = {k: v for k, v in result.items() if k != "collected_at"}
    signature = hashlib.sha256(json.dumps([project["id"], stable], ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]
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
                st.caption("선택·필터·수집 버전이 바뀌었습니다. 다시 생성해주세요.")


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
        st.session_state.pop("cfg_key", None)
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
