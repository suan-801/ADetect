"""실행별 산출물 보관. 파일만 LRU로 만료하고 이력 메타데이터는 유지한다."""
import os
import time
import uuid
from pathlib import Path
from config import settings
from database.db import get_conn


def root():
    return Path(os.getenv("ADETECT_EXPORT_DIR", "storage/exports")).resolve()


def _schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS artifact (id TEXT PRIMARY KEY, run_id TEXT, function_type TEXT, extension TEXT, filename TEXT, created REAL, accessed REAL, size INTEGER, expired INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS download_event (id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, requested REAL NOT NULL)")


def _path(filename):
    path = (root()/filename).resolve()
    if path.parent != root() or path.name != filename:
        raise ValueError("잘못된 산출물 경로")
    return path


def check_secrets(data):
    for name in ("NAVER_CLIENT_SECRET","NAVER_AD_SECRET_KEY","APIFY_API_TOKEN","GEMINI_API_KEY","YOUTUBE_API_KEY"):
        secret = str(getattr(settings,name,""))
        if len(secret)>7 and secret.encode() in data:
            raise ValueError("산출물에 API 인증정보가 포함되어 생성을 중단했습니다.")


def save_artifact(run_id, function, extension, data):
    from core import storage
    from core.retention import ensure_capacity, register
    if extension not in ("html","xlsx","zip"):
        raise ValueError("Unsupported extension")
    if not run_id:
        raise ValueError("저장된 실행 결과가 필요합니다.")
    data = data.encode("utf-8") if isinstance(data,str) else data
    check_secrets(data)
    maximum = int(os.getenv("ADETECT_EXPORT_MAX_BYTES",str(5*1024**3)))
    if len(data)>maximum:
        raise ValueError("산출물이 파일 보관 용량 상한보다 큽니다.")
    root().mkdir(parents=True,exist_ok=True)
    aid = uuid.uuid4().hex
    filename = aid+"."+extension
    ensure_capacity(len(data))
    if storage.remote(): storage.put('exports',filename,data)
    else: _path(filename).write_bytes(data)
    register(filename,'exports',len(data))
    now=time.time()
    with get_conn() as conn:
        _schema(conn)
        conn.execute("INSERT INTO artifact VALUES (?,?,?,?,?,?,?,?,0)",(aid,run_id,function,extension,filename,now,now,len(data)))
        rows=conn.execute("SELECT * FROM artifact WHERE expired=0 ORDER BY accessed DESC").fetchall()
        size=0
        retained_runs=set()
        for row in rows:
            retained_runs.add(row["run_id"])
            size += row["size"]
            if len(retained_runs)>int(os.getenv("ADETECT_EXPORT_MAX_RUNS","20")) or size>maximum:
                path=_path(row["filename"])
                if storage.remote(): storage.delete('exports',row['filename'])
                else: path.unlink(missing_ok=True)
                conn.execute("UPDATE stored_blob SET expired=1 WHERE name=? AND kind='exports'",(row['filename'],))
                conn.execute("UPDATE artifact SET expired=1 WHERE id=?",(row["id"],))
    return aid


def list_artifacts(run_id):
    with get_conn() as conn:
        _schema(conn)
        return [dict(r) for r in conn.execute("SELECT * FROM artifact WHERE run_id=? ORDER BY created DESC",(run_id,))]


def read_artifact(aid, touch=True):
    from core import storage
    with get_conn() as conn:
        _schema(conn)
        row=conn.execute("SELECT * FROM artifact WHERE id=?",(aid,)).fetchone()
        if not row or row["expired"]:
            return None
        path=_path(row["filename"])
        data=storage.get('exports',row['filename']) if storage.remote() else path.read_bytes() if path.is_file() else None
        if data is None:
            conn.execute("UPDATE artifact SET expired=1 WHERE id=?",(aid,))
            return None
        if touch:
            conn.execute("UPDATE artifact SET accessed=? WHERE id=?",(time.time(),aid))
        return data


def touch_artifact(aid):
    with get_conn() as conn:
        _schema(conn)
        conn.execute("UPDATE artifact SET accessed=? WHERE id=? AND expired=0",(time.time(),aid))


def record_download(aid):
    """브라우저의 파일 저장 완료가 아닌 다운로드 요청을 기록한다."""
    with get_conn() as conn:
        _schema(conn)
        row=conn.execute("SELECT filename FROM artifact WHERE id=? AND expired=0",(aid,)).fetchone()
        from core import storage
        if row and (storage.remote() or _path(row["filename"]).is_file()):
            now=time.time()
            conn.execute("INSERT INTO download_event VALUES (?,?,?)",(uuid.uuid4().hex,aid,now))
            conn.execute("UPDATE artifact SET accessed=? WHERE id=?",(now,aid))


def download_events(aid):
    with get_conn() as conn:
        _schema(conn)
        return [dict(r) for r in conn.execute("SELECT requested FROM download_event WHERE artifact_id=? ORDER BY requested DESC",(aid,))]
