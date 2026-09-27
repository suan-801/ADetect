"""단일 인스턴스 FIFO 작업 큐, 협력적 취소, 24시간 결과 캐시."""
import copy
import hashlib
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from config import settings
from database.db import get_conn
from core.runtime import persist_result

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="adetect")
_lock = threading.Lock()
_jobs = {}
_local = threading.local()


class AnalysisCancelled(Exception):
    pass


def checkpoint(message=None, partial=None):
    job = getattr(_local, "job", None)
    if job:
        if partial is not None:
            job["partial"] = copy.deepcopy(partial)
        if message:
            job["message"] = message
        if job["cancel"].is_set():
            raise AnalysisCancelled()


def cache_key(function, inputs):
    modes = {k: getattr(settings,k) for k in ("NAVER_DATALAB_MOCK", "NAVER_SEARCH_MOCK", "NAVER_AD_MOCK", "APIFY_MOCK", "GEMINI_MOCK", "GEMINI_MODEL")}
    # 계정 변경 시 이전 계정 캐시를 재사용하지 않는다. 키는 해시 입력으로만 사용한다.
    credentials = "|".join(str(getattr(settings,k,"")) for k in ("NAVER_CLIENT_ID","NAVER_CLIENT_SECRET","APIFY_API_TOKEN","GEMINI_API_KEY","NAVER_AD_API_KEY","NAVER_AD_SECRET_KEY","NAVER_AD_CUSTOMER_ID","YOUTUBE_API_KEY"))
    identity = hashlib.sha256(credentials.encode()).hexdigest()
    return hashlib.sha256(json.dumps(["facts-v2",function,inputs,modes,identity,settings.SAMPLE_MODE],sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def cached_result(key):
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS result_cache (cache_key TEXT PRIMARY KEY, result_json TEXT, expires REAL)")
        row = conn.execute("SELECT result_json FROM result_cache WHERE cache_key=? AND expires>?", (key,time.time())).fetchone()
        return json.loads(row[0]) if row else None


def store_cache(key, result):
    if result.get("status") != "완료":
        return
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS result_cache (cache_key TEXT PRIMARY KEY, result_json TEXT, expires REAL)")
        conn.execute("DELETE FROM result_cache WHERE expires<?", (time.time(),))
        conn.execute("INSERT INTO result_cache VALUES (?,?,?) ON CONFLICT(cache_key) DO UPDATE SET result_json=excluded.result_json,expires=excluded.expires",(key,json.dumps(result,ensure_ascii=False),time.time()+86400))


def submit(session, function, runner, inputs, force=False):
    snapshot = copy.deepcopy(session)
    snapshot = {k:v for k,v in snapshot.items() if "_export_" not in k}
    with _lock:
        for jid, job in _jobs.items():
            if job["session_id"] == session["id"] and job["function"] == function and not job["future"].done():
                return jid
        jid = str(uuid.uuid4())
        job = {"session_id":session["id"],"function":function,"cancel":threading.Event(),"state":"queued",
               "message":"작업 순서를 기다립니다.","partial":{},"result":None,"future":None,"created":time.time(),"force":force}
        _jobs[jid] = job
        def execute():
            _local.job = job
            job["state"] = "running"
            try:
                checkpoint("분석 중")
                key = cache_key(function,inputs)
                result = None if force or function == "collection" else cached_result(key)
                if result is None:
                    result = runner(snapshot)
                    checkpoint(partial=result)
                    if function != "collection":
                        store_cache(key,result)
                else:
                    result["cache_hit"] = True
                persist_result(snapshot,function,result)
                job["result"] = result
                job["run_id"] = snapshot[function+"_run_id"]
                job["state"] = "done"
            except AnalysisCancelled:
                result = {**job["partial"],"status":"취소","message":"취소 요청 이후 새 수집을 중단했습니다."}
                persist_result(snapshot,function,result)
                job["result"],job["state"] = result,"done"
                job["run_id"] = snapshot[function+"_run_id"]
            except Exception:
                result = {**job["partial"],"status":"전체 실패","errors":["작업 실행 실패. 설정과 수집 소스를 확인하세요."]}
                try:
                    persist_result(snapshot,function,result)
                    job["run_id"] = snapshot[function+"_run_id"]
                finally:
                    job["result"],job["state"] = result,"done"
            finally:
                _local.job = None
        job["future"] = _executor.submit(execute)
        return jid


def get_job(jid):
    return _jobs.get(jid)


def cancel(jid):
    job = _jobs.get(jid)
    if job:
        job["cancel"].set()


def forget(jid):
    with _lock:
        job = _jobs.get(jid)
        if job and job["future"].done():
            _jobs.pop(jid,None)


def source_cache(name):
    """성공한 소스별 결과를 재사용해 부분 실패 재시도의 중복 호출을 줄인다."""
    from functools import wraps
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            checkpoint()
            key=cache_key("source:"+name,{"args":args,"kwargs":kwargs})
            job=getattr(_local,"job",None)
            hit=None if job and job.get("force") else cached_result(key)
            if hit:
                return hit["data"]
            result=fn(*args,**kwargs)
            if not isinstance(result,dict) or result.get("status") not in ("not_available","insufficient_data"):
                store_cache(key,{"status":"완료","data":result})
            return result
        return wrapped
    return decorate
