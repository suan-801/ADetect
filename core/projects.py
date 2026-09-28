"""Project repository, immutable source snapshots and explicit export selection."""
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from database.db import get_conn, create_session, save_session_inputs, save_function_run, list_function_runs

SOURCES = {
    "trend": ("검색 관심도 추이", "3년 전 1월부터 직전 완료 월까지 자사·경쟁사 묶음을 한 요청으로 비교", "market"),
    "volume": ("월간 검색량", "브랜드별 검색어 묶음의 조회 시점 PC·모바일 검색량과 연관 검색어", "market"),
    "news": ("관련 뉴스", "뉴스 검색어별 최신 기사 제목·발췌·발행일·원문 링크", "market"),
    "website": ("공식 페이지 자료", "입력한 공식 URL의 텍스트·링크·화면 캡처", "brand"),
    "search_capture": ("네이버 검색 화면·광고 관측", "검색 결과 첫 화면과 광고 영역 캡처, 광고 문구·링크", "brand"),
    "meta": ("Meta 광고 소재", "입력한 광고 라이브러리 페이지의 최대 20건 표본 (유료)", "creative"),
    "instagram": ("Instagram 공식 계정", "입력한 계정의 팔로워와 최근 게시물 (유료)", "brand"),
    "youtube": ("YouTube 공식 채널", "입력한 채널의 구독자와 최근 영상 정보", "brand"),
}
# 프로젝트 입력 v4: 브랜드별 검색어 묶음·계정(brands), 시장 관심 검색어, 뉴스 전용 필터.
# 이전 필드는 과거 프로젝트·수집 당시 입력 사본을 읽기 위해 계속 허용한다.
INPUT_VERSION = 4
RESULT_VERSION = 6
MAX_COMPETITORS = 4      # 데이터랩 한 요청의 최대 5개 주제 = 자사 1 + 경쟁사 4
MAX_TERMS = 20           # 데이터랩 주제 하나의 최대 검색어 수
MAX_MARKET = 10
MAX_NEWS = 10
BRAND_SOURCE_FIELDS = ("official_urls", "homepage", "detail_url", "instagram", "youtube", "meta_page", "utm_urls")
INPUTS = ("brand_name", "campaign", "category", "competitors", "brands", "market_keywords", "news_keywords", "news_filter",
          "setup_provenance", "input_version", "brand_keywords", "general_keywords", "keyword_mode",
          "include_terms", "exclude_terms", "sources", "paid_enabled", "save_images", "save_ad_assets")
PREFIX = {"trend":"trend", "volume":"volume", "news":"news", "site":"website", "search":"search_capture", "meta":"meta", "instagram":"instagram", "youtube":"youtube"}


def now():
    return datetime.now(timezone.utc).isoformat()


def schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS project_resource (project_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, data TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS project_digest (run_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, data TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS project (id TEXT PRIMARY KEY, name TEXT NOT NULL, archived INTEGER DEFAULT 0, updated TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS project_review (run_id TEXT NOT NULL, record_id TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(run_id,record_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS project_export (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, manifest TEXT NOT NULL, created TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS project_task (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL, inputs TEXT NOT NULL, created TEXT NOT NULL, owner TEXT, run_id TEXT)")


def migrate():
    """Idempotent, additive only. Legacy snapshots remain untouched."""
    with get_conn() as conn:
        schema(conn)
        for row in conn.execute("SELECT * FROM analysis_session ORDER BY created_at"):
            conn.execute("INSERT INTO project(id,name,updated) VALUES(?,?,?) ON CONFLICT(id) DO NOTHING",
                         (row["id"], row["brand_name"], row["created_at"]))


def term_key(term):
    """검색어 비교용 표기 (공백·대소문자 무시). 원래 표기는 그대로 저장한다."""
    return "".join(str(term).split()).casefold()


def clean_terms(terms, limit=None):
    output, seen = [], set()
    for term in terms or []:
        term = str(term).strip()
        if term and term_key(term) not in seen:
            seen.add(term_key(term)); output.append(term)
    return output[:limit] if limit else output


def project_inputs(project):
    """저장된 입력을 v4 구조로 읽는다. 저장 데이터와 수집 당시 사본은 바꾸지 않는다."""
    p = copy.deepcopy(project)
    brand = p.get("brand_name", "")
    sources = p.get("sources") or {}
    if not p.get("brands"):
        own_src = dict(sources.get(brand, {}))
        brands = [{"id": "own", "name": brand, "role": "own",
                   "terms": clean_terms(p.get("brand_keywords") or [brand], MAX_TERMS), "sources": own_src}]
        for i, name in enumerate(n for n in p.get("competitors") or [] if n and n != brand):
            brands.append({"id": f"legacy-{i}", "name": name, "role": "competitor", "terms": [name], "sources": dict(sources.get(name, {}))})
        p["brands"] = brands[:1 + MAX_COMPETITORS]
    for b in p["brands"]:
        b["terms"] = clean_terms(b.get("terms") or [b["name"]], MAX_TERMS)
        b.setdefault("sources", {})
    if "market_keywords" not in p:
        p["market_keywords"] = clean_terms(p.get("general_keywords") or ([p["category"]] if p.get("category") else []), MAX_MARKET)
    if "news_keywords" not in p:
        # 과거 프로젝트는 브랜드·일반 검색어로 뉴스를 찾았다. 같은 범위를 뉴스 검색어 초기값으로 보여준다.
        p["news_keywords"] = clean_terms((p.get("brand_keywords") or [brand]) + (p.get("general_keywords") or []), MAX_NEWS)
    if "news_filter" not in p:
        # 과거 전역 포함·제외 문구는 이제 뉴스 전용 필터다. 다른 자료에는 적용하지 않는다.
        p["news_filter"] = {"include": list(p.get("include_terms") or []), "exclude": list(p.get("exclude_terms") or [])}
        p["legacy_filter_converted"] = bool(p.get("include_terms") or p.get("exclude_terms"))
    p["brand_name"] = next((b["name"] for b in p["brands"] if b["role"] == "own"), brand)
    return p


def own_brand(p):
    return next(b for b in p["brands"] if b["role"] == "own")


def to_storage(p):
    """v4 입력을 저장 형식으로. 이전 필드는 과거 코드 경로(백업·레거시 화면)를 위해 함께 채운다."""
    own = own_brand(p)
    stored = {k: copy.deepcopy(p[k]) for k in ("brands", "market_keywords", "news_keywords", "news_filter", "campaign", "category",
                                              "paid_enabled", "save_images", "save_ad_assets", "setup_provenance") if k in p}
    stored.update(input_version=INPUT_VERSION, brand_name=own["name"], keyword_mode="brand_group",
                  competitors=[b["name"] for b in p["brands"] if b["role"] == "competitor"],
                  brand_keywords=list(own["terms"]), general_keywords=list(p.get("market_keywords", [])),
                  sources={b["name"]: copy.deepcopy(b.get("sources", {})) for b in p["brands"]})
    return stored


def term_conflicts(brands):
    """서로 다른 브랜드에 같은 검색어가 있으면 비교가 왜곡된다."""
    owners = {}
    for b in brands:
        for t in b.get("terms", []):
            owners.setdefault(term_key(t), []).append((t, b["name"]))
    return [(items[0][0], sorted({n for _, n in items})) for items in owners.values() if len({n for _, n in items}) > 1]


def validate_inputs(p):
    errors = []
    own = [b for b in p["brands"] if b["role"] == "own"]
    competitors = [b for b in p["brands"] if b["role"] == "competitor"]
    if len(own) != 1 or not own[0]["name"].strip():
        errors.append("자사 브랜드명이 필요합니다.")
    if len(competitors) > MAX_COMPETITORS:
        errors.append(f"경쟁사는 최대 {MAX_COMPETITORS}개입니다.")
    names = [term_key(b["name"]) for b in p["brands"]]
    if len(names) != len(set(names)):
        errors.append("같은 브랜드명이 두 번 입력되었습니다.")
    for b in p["brands"]:
        if not b["name"].strip():
            errors.append("경쟁사 브랜드명을 입력하거나 해당 경쟁사를 삭제해주세요.")
        if len(b.get("terms", [])) > MAX_TERMS:
            errors.append(f"{b['name']} 검색어 묶음은 최대 {MAX_TERMS}개입니다.")
    if len(p.get("market_keywords", [])) > MAX_MARKET:
        errors.append(f"시장 관심 검색어는 최대 {MAX_MARKET}개입니다.")
    if len(p.get("news_keywords", [])) > MAX_NEWS:
        errors.append(f"뉴스 검색어는 최대 {MAX_NEWS}개입니다.")
    return errors


def comparison_signature(brands):
    """검색 추이 공동 비교 구성. 브랜드·검색어 묶음이 바뀌면 값이 달라진다."""
    groups = [[b["id"], b["name"], sorted(term_key(t) for t in b.get("terms", []))] for b in brands]
    return hashlib.sha256(json.dumps(groups, ensure_ascii=False).encode()).hexdigest()[:16]


def news_passes(row, news_filter):
    """뉴스 전용 표시 필터. 제목·발췌문에만 적용하며 제외가 우선한다. 뉴스가 아닌 자료는 항상 통과한다."""
    if row.get("kind") != "뉴스":
        return True
    text = (row.get("text", "") + " " + row.get("title", "")).casefold()
    flt = news_filter or {}
    if any(w.casefold() in text for w in flt.get("exclude", []) if w):
        return False
    include = [w for w in flt.get("include", []) if w]
    return not include or any(w.casefold() in text for w in include)


def create(name, inputs):
    pid = create_session(inputs["brand_name"], inputs.get("category", ""), inputs.get("competitors", []))
    with get_conn() as conn:
        schema(conn)
        conn.execute("INSERT INTO project(id,name,updated) VALUES(?,?,?)", (pid, name.strip(), now()))
    save_session_inputs(pid, {k:copy.deepcopy(inputs[k]) for k in INPUTS if k in inputs})
    return pid


def listing(archived=False):
    migrate()
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT p.*,s.brand_name,s.inputs_json FROM project p JOIN analysis_session s ON s.id=p.id WHERE p.archived=? ORDER BY p.updated DESC", (int(archived),))]


def load(pid):
    with get_conn() as conn:
        schema(conn)
        row = conn.execute("SELECT s.*,p.name,p.archived FROM analysis_session s JOIN project p ON p.id=s.id WHERE s.id=?", (pid,)).fetchone()
    if not row:
        raise ValueError("프로젝트를 찾을 수 없습니다.")
    return {"id":pid, "name":row["name"], "brand_name":row["brand_name"], "category":row["category"],
            "competitors":json.loads(row["competitors_json"] or "[]"), **json.loads(row["inputs_json"] or "{}")}


def update(pid, name, inputs):
    save_session_inputs(pid, {k:copy.deepcopy(inputs[k]) for k in INPUTS if k in inputs})
    with get_conn() as conn:
        schema(conn)
        conn.execute("UPDATE project SET name=?,updated=? WHERE id=?", (name,now(),pid))


def archive(pid, value=True):
    with get_conn() as conn:
        schema(conn)
        conn.execute("UPDATE project SET archived=? WHERE id=?",(int(value),pid))


def canonical_url(url):
    u=urlsplit(url)
    query=urlencode([(k,v) for k,v in parse_qsl(u.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')])
    return urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path,query,""))


def normalize(result, source, inputs):
    from core.collection import apply_reviews
    result=copy.deepcopy(result)
    rows={}
    for row in result.get("records",[]):
        key=canonical_url(row["source_url"]) if row["kind"]=="뉴스" else row["id"]
        if key in rows:
            rows[key]["matched_queries"]=list(dict.fromkeys(rows[key].get("matched_queries",[])+[row.get("keyword","")]))
            # 여러 검색어·브랜드에서 발견된 같은 기사는 한 행으로 두고 발견 관계를 보존한다.
            rows[key]["found_brands"]=list(dict.fromkeys(rows[key].get("found_brands",[])+row.get("found_brands",[])))
        else:
            if row["kind"]=="뉴스":
                row["id"]=hashlib.sha256((row["brand"]+key).encode()).hexdigest()[:20]
                row["matched_queries"]=[row.get("keyword","")]
            rows[key]=row
    result["records"]=list(rows.values()) if inputs.get("input_version")==INPUT_VERSION else apply_reviews(list(rows.values()), inputs)
    # Records have one canonical copy; parts retain series and source diagnostics only.
    for p in result.get("parts",{}).values():
        p.pop("records",None)
        if p.get("state")=="미수집": p["state"]="설정 필요"
    states=[p.get("state") for p in result.get("parts",{}).values()]
    if not states: status="설정 필요"
    elif all(s=="설정 필요" for s in states): status="설정 필요"
    elif all(s=="완료" for s in states):
        has_series=any(p.get("series",{}).get("rows") or any(x.get("rows") for x in p.get("comparison",{}).get("series",[])) for p in result["parts"].values())
        status="완료" if rows or has_series else "결과 없음"
    elif any(s in ("완료","부분 완료") for s in states): status="부분 완료"
    else: status="실패"
    version=RESULT_VERSION if inputs.get("input_version")==INPUT_VERSION else 3
    result.update(schema_version=version, source=source, status=status, inputs={k:copy.deepcopy(inputs[k]) for k in INPUTS if k in inputs})
    return result


def histories(pid):
    """Expose legacy parts as virtual source snapshots without destructive migration."""
    output=[]
    for r in list_function_runs(pid):
        value=json.loads(r["result_json"] or "{}")
        if value.get("source") in SOURCES:
            output.append({"run_id":r["id"], "source":value["source"], "result":value, "created":r["created_at"]})
        elif value.get("schema_version")==2 and r["function_type"] in ("market","brand","creative"):
            for source in SOURCES:
                parts={k:v for k,v in value.get("parts",{}).items() if PREFIX.get(k.split(':')[0])==source}
                if not parts: continue
                subset={**value,"parts":parts,"records":[x for p in parts.values() for x in p.get("records",[])]}
                # No invented full inputs for old sessions.
                converted=normalize(subset,source,value.get("inputs",{})) if value.get("inputs",{}).get("brand_name") else {**subset,"source":source,"schema_version":3,"inputs":value.get("inputs",{}),"input_note":"기존 기록에 없는 입력은 복원할 수 없습니다."}
                output.append({"run_id":r["id"]+":"+source,"source":source,"result":converted,"created":r["created_at"]})
    return output


def available(item):
    r=item["result"]
    return not r.get("expired") and r.get("status") in ("완료","부분 완료","부분 실패","결과 없음")


def review_rows(item):
    with get_conn() as conn:
        schema(conn)
        saved={r["record_id"]:r["state"] for r in conn.execute("SELECT * FROM project_review WHERE run_id=?",(item["run_id"],))}
    rows=copy.deepcopy(item["result"].get("records",[]))
    for row in rows:
        if row["id"] in saved: row.update(review=saved[row["id"]],review_reason="사용자 확인")
        row["selection_id"]=item["run_id"]+"/"+row["id"]
    return rows


def set_reviews(run_id, values):
    with get_conn() as conn:
        schema(conn)
        for rid,state in values.items():
            if state not in ("포함","확인 필요","제외"): raise ValueError("잘못된 확인 상태")
            conn.execute("INSERT INTO project_review VALUES(?,?,?) ON CONFLICT(run_id,record_id) DO UPDATE SET state=excluded.state",(run_id,rid,state))


def legacy_excluded(item):
    """이전 화면에서 사용자가 직접 '제외'로 저장한 자료. 새 화면에는 분류를 보여주지 않지만
    기본 다운로드 선택에서 빠진 상태를 유지해 과거 선택이 갑자기 되살아나지 않게 한다."""
    with get_conn() as conn:
        schema(conn)
        return {r["record_id"] for r in conn.execute("SELECT record_id FROM project_review WHERE run_id=? AND state='제외'", (item["run_id"],))}


def display_rows(item):
    """화면·다운로드용 자료. 분류 필드는 싣지 않는다."""
    rows = copy.deepcopy(item["result"].get("records", []))
    for row in rows:
        row.pop("review", None); row.pop("review_reason", None)
        row["selection_id"] = item["run_id"] + "/" + row["id"]
        row["collected_version"] = item["created"]
    return rows


def default_selection(snapshots):
    """기본 다운로드 선택. 과거 사용자 '제외'는 DB 기록과 백업에 담긴 기록(review_reason='사용자 확인') 모두 존중한다."""
    output = []
    for item in snapshots:
        excluded = legacy_excluded(item) | {r["id"] for r in item["result"].get("records", [])
                                            if r.get("review") == "제외" and r.get("review_reason") == "사용자 확인"}
        output += [r["selection_id"] for r in display_rows(item) if r["id"] not in excluded]
    return output


def selection_result(project, snapshots, selected_ids, news_filter=None, extra=None):
    """화면과 같은 규칙으로 만든 다운로드 대상: 선택 ∩ 뉴스 필터 통과."""
    news_filter = news_filter if news_filter is not None else project_inputs(project).get("news_filter", {})
    rows=[]; parts={}; changes=[]; hidden=0
    selected=set(selected_ids)
    for item in snapshots:
        for r in display_rows(item):
            if not news_passes(r, news_filter):
                hidden += 1
                continue
            if r["selection_id"] in selected:
                rows.append(r)
        chosen_ids={r["id"] for r in rows}
        for key,part in item["result"].get("parts",{}).items():
            parts[item["run_id"]+":"+key]={**part,"records":[],"collected_at":item["created"],"source":item["source"]}
        changes += [c for c in item["result"].get("changes",[]) if c.get("자료ID") in chosen_ids]
    dates=collection_dates(snapshots)
    p=project_inputs(project)
    return {"schema_version":RESULT_VERSION,"status":"선택 자료","collected_at":now(),"records":rows,"parts":parts,"changes":changes,
            "news_filter":copy.deepcopy(news_filter),"hidden_by_news_filter":hidden,**(extra or {}),
            "inputs":{"project":project["name"],"brand_name":p["brand_name"],"brands":copy.deepcopy(p["brands"]),
                      "market_keywords":p.get("market_keywords",[]),"news_keywords":p.get("news_keywords",[]),
                      "campaign":p.get("campaign"),"paid_enabled":p.get("paid_enabled",True),
                      "date_mixed":len(dates)>1,"collection_dates":dates,
                      "versions":[{"run_id":i["run_id"],"source":i["source"],"collected_at":i["created"],"inputs":i["result"].get("inputs",{}),
                                   "cache_policy":i["result"].get("cache_policy"),"sample":bool(i["result"].get("sample_sources"))} for i in snapshots]},
            "sample_sources":["SAMPLE"] if any(i["result"].get("sample_sources") for i in snapshots) else []}


def collection_dates(snapshots):
    """선택한 수집 버전의 수집일(YYYY-MM-DD). 2개 이상이면 날짜 혼합이다."""
    return sorted({i["created"][:10] for i in snapshots})


def save_export(pid, result):
    from core.exporters.artifact_store import check_secrets
    raw=json.dumps(result,ensure_ascii=False)
    check_secrets(raw.encode())
    eid=uuid.uuid4().hex
    with get_conn() as conn:
        schema(conn)
        conn.execute("INSERT INTO project_export VALUES(?,?,?,?)",(eid,pid,raw,now()))
    return eid


def exports(pid):
    with get_conn() as conn:
        schema(conn)
        return [dict(r) for r in conn.execute("SELECT * FROM project_export WHERE project_id=? ORDER BY created DESC",(pid,))]


def overview():
    """프로젝트 정리 화면용 요약. 테스트성 여부는 추정하지 않고 저장된 사실(SAMPLE 여부·실행 수)만 보여준다."""
    migrate()
    with get_conn() as conn:
        schema(conn)
        rows=[dict(r) for r in conn.execute("SELECT p.id,p.name,p.archived,p.updated,s.brand_name,s.created_at FROM project p JOIN analysis_session s ON s.id=p.id ORDER BY s.created_at DESC")]
        runs={}
        for r in conn.execute("SELECT session_id,result_json FROM function_run"):
            value=json.loads(r["result_json"] or "{}")
            item=runs.setdefault(r["session_id"],{"runs":0,"sample":0,"known":0})
            item["runs"]+=1
            # 예전 정리로 만료된 기록은 SAMPLE 여부를 모를 수 있어 구분 근거에서 뺀다.
            if value.get("expired") and "sample_sources" not in value: continue
            item["known"]+=1
            item["sample"]+=bool(value.get("sample_sources"))
    for row in rows:
        info=runs.get(row["id"],{"runs":0,"sample":0,"known":0})
        row["runs"]=info["runs"]
        row["kind"]=("수집 이력 없음" if not info["runs"] else "구분 불가 (만료 기록만 있음)" if not info["known"]
                     else "SAMPLE 자료만 있음" if info["sample"]==info["known"] else "실수집 자료 포함")
    return rows


def _run_ids(conn, pid):
    return [r["id"] for r in conn.execute("SELECT id FROM function_run WHERE session_id=?",(pid,))]


def _review_count(conn, run_ids):
    # 레거시 v2 실행은 "run_id:source" 가상 ID로 확인 상태를 저장한다.
    return sum(conn.execute("SELECT COUNT(*) FROM project_review WHERE run_id=? OR run_id LIKE ?",(rid,rid+":%")).fetchone()[0] for rid in run_ids)


def delete_impact(pid):
    with get_conn() as conn:
        schema(conn)
        run_ids=_run_ids(conn,pid)
        return {"수집 실행":len(run_ids),"확인 상태":_review_count(conn,run_ids),
                "다운로드 선택 기록":conn.execute("SELECT COUNT(*) FROM project_export WHERE project_id=?",(pid,)).fetchone()[0],
                "수집 작업 기록":conn.execute("SELECT COUNT(*) FROM project_task WHERE project_id=?",(pid,)).fetchone()[0]}


def delete(pid, confirm_name):
    """프로젝트 단위 삭제만 허용한다. 원본·다운로드 파일은 다른 프로젝트와 공유될 수 있어 여기서 지우지 않고,
    참조가 사라진 뒤 저장 공간 정리 후보로만 나타난다."""
    project=load(pid)
    if confirm_name.strip()!=project["name"]:
        raise ValueError("확인용 프로젝트 이름이 일치하지 않습니다.")
    with get_conn() as conn:
        schema(conn)
        if conn.execute("SELECT 1 FROM project_task WHERE project_id=? AND state IN ('대기','수집 중')",(pid,)).fetchone():
            raise ValueError("수집 중인 프로젝트는 삭제할 수 없습니다.")
        for rid in _run_ids(conn,pid):
            conn.execute("DELETE FROM project_review WHERE run_id=? OR run_id LIKE ?",(rid,rid+":%"))
            conn.execute("DELETE FROM project_digest WHERE run_id=? OR run_id LIKE ?", (rid,rid+":%"))
        conn.execute("DELETE FROM project_export WHERE project_id=?",(pid,))
        conn.execute("DELETE FROM project_resource WHERE project_id=?",(pid,))
        conn.execute("DELETE FROM project_task WHERE project_id=?",(pid,))
        conn.execute("DELETE FROM function_run WHERE session_id=?",(pid,))
        conn.execute("DELETE FROM project WHERE id=?",(pid,))
        conn.execute("DELETE FROM analysis_session WHERE id=?",(pid,))
