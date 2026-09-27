"""Bounded storage, reference-aware cleanup and explicit restoration capabilities."""
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from database.db import get_conn
from core import storage


def schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS stored_blob (name TEXT NOT NULL, kind TEXT NOT NULL, size INTEGER NOT NULL, created REAL NOT NULL, pinned INTEGER DEFAULT 0, expired INTEGER DEFAULT 0, PRIMARY KEY(name,kind))")


def limits():
    cloud=storage.remote()
    return {"files":int(os.getenv("ADETECT_STORAGE_MAX_BYTES",str((750*1024**2) if cloud else 5*1024**3))),
            "db":int(os.getenv("ADETECT_DB_MAX_BYTES",str((300 if cloud else 500)*1024**2)))}


def usage():
    from core.evidence_store import root as evidence_root
    from core.exporters.artifact_store import root as export_root
    from config import settings
    with get_conn() as conn:
        schema(conn)
        if storage.remote():
            size=conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
            files=conn.execute("SELECT COALESCE(SUM(size),0) FROM stored_blob WHERE expired=0").fetchone()[0]
        else:
            path=Path(settings.DB_PATH)
            size=sum(p.stat().st_size for p in path.parent.glob(path.name+'*') if p.is_file())
            files=sum(p.stat().st_size for folder in (evidence_root(),export_root()) if folder.exists() for p in folder.iterdir() if p.is_file())
        return {"files":int(files),"db":int(size),"limits":limits()}


def ensure_capacity(extra=0):
    state=usage()
    if state["files"]+extra>state["limits"]["files"] or state["db"]>=state["limits"]["db"]:
        raise ValueError("저장 용량 상한 — 백업 후 만료 자료 정리 또는 보관 설정을 확인해주세요.")


def register(name,kind,size):
    with get_conn() as conn:
        schema(conn)
        conn.execute("INSERT INTO stored_blob(name,kind,size,created) VALUES(?,?,?,?) ON CONFLICT(name,kind) DO UPDATE SET expired=0,created=excluded.created,size=excluded.size",(name,kind,size,time.time()))


def pin(names,value):
    with get_conn() as conn:
        schema(conn)
        for name in names: conn.execute("UPDATE stored_blob SET pinned=? WHERE name=? AND kind='evidence'",(int(value),name))


def cleanup(dry_run=True):
    """Never removes protected latest results. Deletion candidates remain visible before apply."""
    from core import projects
    from core.evidence_store import root as evidence_root
    from core.exporters.artifact_store import root as export_root, _schema
    cutoff=(datetime.now(timezone.utc)-timedelta(days=365)).isoformat()
    candidates=[]; protected=set()
    with get_conn() as conn:
        schema(conn); projects.schema(conn); _schema(conn)
        if conn.execute("SELECT id FROM project_task WHERE state IN ('대기','수집 중') LIMIT 1").fetchone():
            return [{"종류":"안내","대상":"수집 중에는 정리하지 않습니다."}]
        runs=list(conn.execute("SELECT * FROM function_run ORDER BY created_at DESC"))
        counts={}
        for row in runs:
            value=json.loads(row["result_json"] or '{}')
            source=value.get('source')
            if source not in projects.SOURCES: continue
            key=(row['session_id'],source)
            if value.get('expired'): continue
            good=projects.available({'result':value})
            if good: counts[key]=counts.get(key,0)+1
            keep=good and counts[key]<=5
            if keep:
                # Fresh shared references protect an old asset from premature expiry.
                if row['created_at']>(datetime.now(timezone.utc)-timedelta(days=30)).isoformat():
                    protected.update(a['filename'] for r in value.get('records',[]) for a in r.get('assets',[]))
            else:
                if good or row['created_at']<cutoff:
                    candidates.append({'종류':'결과 상세','대상':row['id']})
                    if not dry_run:
                        tombstone={'schema_version':3,'source':source,'status':row['status'],'expired':True,'collected_at':row['created_at'],'records':[],'parts':{}}
                        conn.execute("UPDATE function_run SET result_json=? WHERE id=?",(json.dumps(tombstone),row['id']))
                        conn.execute("DELETE FROM project_review WHERE run_id=?",(row['id'],))
        # Import legacy on-disk file metadata lazily without altering the files.
        if not storage.remote() and not dry_run:
            for kind,folder in (('evidence',evidence_root()),('exports',export_root())):
                if folder.exists():
                    for p in folder.iterdir():
                        if p.is_file(): conn.execute("INSERT INTO stored_blob(name,kind,size,created) VALUES(?,?,?,?) ON CONFLICT(name,kind) DO NOTHING",(p.name,kind,p.stat().st_size,p.stat().st_mtime))
        for blob in conn.execute("SELECT * FROM stored_blob WHERE expired=0 AND pinned=0"):
            days=30 if blob['kind']=='evidence' else (1 if storage.remote() else 7)
            if blob['created']>time.time()-days*86400 or blob['name'] in protected: continue
            candidates.append({'종류':blob['kind'],'대상':blob['name']})
            if not dry_run:
                if storage.remote(): storage.delete(blob['kind'],blob['name'])
                else:
                    folder=evidence_root() if blob['kind']=='evidence' else export_root()
                    p=(folder/blob['name']).resolve()
                    if p.parent!=folder.resolve(): raise ValueError('잘못된 저장 경로')
                    p.unlink(missing_ok=True)
                conn.execute("UPDATE stored_blob SET expired=1 WHERE name=? AND kind=?",(blob['name'],blob['kind']))
                if blob['kind']=='exports': conn.execute("UPDATE artifact SET expired=1 WHERE filename=?",(blob['name'],))
        if not dry_run:
            conn.execute("DELETE FROM project_task WHERE created<? AND state NOT IN ('대기','수집 중')",(cutoff,))
            conn.execute("DELETE FROM download_event WHERE requested<?",(time.time()-365*86400,))
            conn.execute("DELETE FROM project_export WHERE created<?",(cutoff,))
    if not dry_run:
        from core.jobs import cached_result
        cached_result('__cleanup__')
        with get_conn() as conn: conn.execute("DELETE FROM result_cache WHERE expires<?",(time.time(),))
        if not storage.remote():
            import sqlite3
            from config.settings import DB_PATH
            with sqlite3.connect(DB_PATH) as conn: conn.execute('VACUUM')
    return candidates


def availability(result):
    from core.evidence_store import read_bytes
    if result.get('expired'): return '이력만 있음'
    assets=[a for r in result.get('records',[]) for a in r.get('assets',[])]
    return '결과·원본 모두 있음' if all(read_bytes(a) is not None for a in assets) else '결과만 있음 (일부 원본 없음)'
