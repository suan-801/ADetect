"""Single worker with durable per-source attempts; interrupted paid calls never auto-retry."""
import copy
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from database.db import get_conn, save_function_run
from core import projects

OWNER=uuid.uuid4().hex
POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix="project-collection")
LOCK=threading.Lock()
CANCEL={}


def tasks(pid):
    with get_conn() as conn:
        projects.schema(conn)
        # Single application instance; a previous process cannot still own a task.
        conn.execute("UPDATE project_task SET state='중단' WHERE owner<>? AND state IN ('대기','수집 중')",(OWNER,))
        return [dict(r) for r in conn.execute("SELECT * FROM project_task WHERE project_id=? ORDER BY created DESC",(pid,))]


def cancel(pid):
    event=CANCEL.get(pid)
    if event: event.set()


def submit(project, sources, force=False, retry=False):
    from core.retention import ensure_capacity
    ensure_capacity()
    sources=[s for s in dict.fromkeys(sources) if s in projects.SOURCES]
    if not sources: raise ValueError("수집할 자료를 선택해주세요.")
    snapshot=copy.deepcopy(project)
    with LOCK:
        if any(t["state"] in ("대기","수집 중") for t in tasks(project["id"])):
            raise ValueError("이 프로젝트는 이미 수집 중입니다.")
        event=threading.Event(); CANCEL[project["id"]]=event
        attempts=[]
        with get_conn() as conn:
            for source in sources:
                tid=uuid.uuid4().hex
                conn.execute("INSERT INTO project_task VALUES(?,?,?,?,?,?,?,?)",(tid,project["id"],source,"대기",json.dumps({k:snapshot.get(k) for k in projects.INPUTS},ensure_ascii=False),projects.now(),OWNER,None))
                attempts.append((tid,source))
        POOL.submit(execute,snapshot,attempts,event,force,retry)


def execute(project,attempts,event,force,retry):
    from core.collection import run_stage, error_message
    from core import jobs
    jobs._local.job={"cancel":event,"force":force,"partial":{}}
    try:
        for tid,source in attempts:
            if event.is_set():
                finish(tid,"중단"); continue
            finish(tid,"수집 중")
            inputs=copy.deepcopy(project)
            inputs["source_selection"]=[source]
            inputs["collection_options"]={k:k==source for k in ("website","news","instagram","youtube","search_capture","meta")}
            stage=projects.SOURCES[source][2]
            # Source caches already preserve successful requests during retries.
            try:
                from core.retention import ensure_capacity
                ensure_capacity()
                value=projects.normalize(run_stage(stage,inputs),source,inputs)
                previous=next((i for i in projects.histories(project["id"]) if i["source"]==source and projects.available(i)),None)
                value["changes"]=changes(previous["result"] if previous else {},value)
                rid=save_function_run(project["id"],source,value["status"],value)
                finish(tid,value["status"],rid)
            except jobs.AnalysisCancelled:
                finish(tid,"중단")
            except Exception as exc:
                value={"schema_version":3,"source":source,"status":"실패","records":[],"parts":{},"inputs":{k:inputs.get(k) for k in projects.INPUTS},"errors":[error_message(exc)],"collected_at":projects.now()}
                rid=save_function_run(project["id"],source,"실패",value)
                finish(tid,"실패",rid)
    finally:
        jobs._local.job=None
        CANCEL.pop(project["id"],None)


def finish(tid,state,run_id=None):
    with get_conn() as conn:
        conn.execute("UPDATE project_task SET state=?,run_id=COALESCE(?,run_id) WHERE id=?",(state,run_id,tid))


def changes(old,new):
    before={r["id"]:r for r in old.get("records",[])}
    after={r["id"]:r for r in new.get("records",[])}
    if not old:return []
    output=[]
    for rid,row in after.items():
        fields=("text","pc","mobile","followers","subscribers","cta","landing_url")
        label="이번 수집에서 추가 관측" if rid not in before else "원문 또는 관측값 변경" if any(row.get(k)!=before[rid].get(k) for k in fields) else None
        if label: output.append({"자료ID":rid,"변화":label,"출처":row["source_url"]})
    if new["status"] in ("완료","결과 없음"):
        output.extend({"자료ID":rid,"변화":"이번 수집에서 미관측 (삭제 확정 아님)","출처":r["source_url"]} for rid,r in before.items() if rid not in after)
    return output
