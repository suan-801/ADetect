"""Project repository, immutable source snapshots and explicit export selection."""
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from database.db import get_conn, create_session, save_session_inputs, save_function_run, list_function_runs

SOURCES = {
    "trend": ("검색 관심도 추이", "완료된 36개월의 상대지수·월별 평균·연도별 피크와 저점", "market"),
    "volume": ("월간 검색량·연관 검색어", "조회 시점의 PC·모바일 검색량과 연관어. 과거 절대 검색량 아님", "market"),
    "news": ("관련 뉴스", "검색어별 최대 100건의 제목·발췌·발행일·원문 링크", "market"),
    "website": ("공식 페이지 자료", "지정 페이지 텍스트·링크·화면 캡처와 선택 이미지 원본", "brand"),
    "search_capture": ("네이버 검색 화면", "선택 검색어의 관측 화면. 광고 순위·미운영 판정 없음", "brand"),
    "meta": ("Meta 광고 소재", "확인한 페이지의 최대 20건 표본·문구·CTA·원본 (유료)", "creative"),
    "instagram": ("Instagram 공식 계정", "확인한 계정과 최근 최대 5개 게시물 (유료)", "brand"),
    "youtube": ("YouTube 공식 채널", "확인한 채널과 최근 최대 5개 영상 정보. 영상 다운로드 제외", "brand"),
}
INPUTS = ("brand_name", "campaign", "category", "competitors", "brand_keywords", "general_keywords",
          "include_terms", "exclude_terms", "sources", "paid_enabled", "save_images", "save_ad_assets")
PREFIX = {"trend":"trend", "volume":"volume", "news":"news", "site":"website", "search":"search_capture", "meta":"meta", "instagram":"instagram", "youtube":"youtube"}


def now():
    return datetime.now(timezone.utc).isoformat()


def schema(conn):
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
        else:
            if row["kind"]=="뉴스":
                row["id"]=hashlib.sha256((row["brand"]+key).encode()).hexdigest()[:20]
                row["matched_queries"]=[row.get("keyword","")]
            rows[key]=row
    result["records"]=apply_reviews(list(rows.values()), inputs)
    # Records have one canonical copy; parts retain series and source diagnostics only.
    for p in result.get("parts",{}).values():
        p.pop("records",None)
        if p.get("state")=="미수집": p["state"]="설정 필요"
    states=[p.get("state") for p in result.get("parts",{}).values()]
    if not states: status="설정 필요"
    elif all(s=="설정 필요" for s in states): status="설정 필요"
    elif all(s=="완료" for s in states):
        status="완료" if rows or any(p.get("series",{}).get("rows") for p in result["parts"].values()) else "결과 없음"
    elif any(s in ("완료","부분 완료") for s in states): status="부분 완료"
    else: status="실패"
    result.update(schema_version=3, source=source, status=status, inputs={k:copy.deepcopy(inputs[k]) for k in INPUTS if k in inputs})
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


def selection_result(project, snapshots, selected_ids, include_excluded=False):
    rows=[]; parts={}; changes=[]
    selected=set(selected_ids)
    for item in snapshots:
        chosen=[r for r in review_rows(item) if r["selection_id"] in selected and (include_excluded or r.get("review")!="제외")]
        rows+=chosen
        for key,part in item["result"].get("parts",{}).items():
            if item["source"]=="trend" or chosen:
                parts[item["run_id"]+":"+key]={**part,"records":[],"collected_at":item["created"]}
        changes += [c for c in item["result"].get("changes",[]) if c.get("자료ID") in {r["id"] for r in chosen}]
    dates=collection_dates(snapshots)
    return {"schema_version":3,"status":"선택 자료","collected_at":now(),"records":rows,"parts":parts,"changes":changes,
            "inputs":{"project":project["name"],"brand_name":project.get("brand_name"),"date_mixed":len(dates)>1,"collection_dates":dates,
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
        conn.execute("DELETE FROM project_export WHERE project_id=?",(pid,))
        conn.execute("DELETE FROM project_task WHERE project_id=?",(pid,))
        conn.execute("DELETE FROM function_run WHERE session_id=?",(pid,))
        conn.execute("DELETE FROM project WHERE id=?",(pid,))
        conn.execute("DELETE FROM analysis_session WHERE id=?",(pid,))
