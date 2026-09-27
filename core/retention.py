"""Bounded storage, reference-aware cleanup and explicit restoration capabilities."""
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from database.db import get_conn
from core import storage

CAPACITY_MESSAGE = "저장 용량 상한 — 설정 > 저장 공간 관리에서 정리 후보를 확인하거나 보관 설정을 확인해주세요."
WARN_RATIO = 0.8
CRITICAL_RATIO = 0.9


class CapacityError(ValueError):
    """저장 상한 도달. 화면은 이 예외를 정리 UI 안내로 연결한다."""


def schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS stored_blob (name TEXT NOT NULL, kind TEXT NOT NULL, size INTEGER NOT NULL, created REAL NOT NULL, pinned INTEGER DEFAULT 0, expired INTEGER DEFAULT 0, PRIMARY KEY(name,kind))")


def limits():
    cloud=storage.remote()
    return {"files":int(os.getenv("ADETECT_STORAGE_MAX_BYTES",str((750*1024**2) if cloud else 5*1024**3))),
            "db":int(os.getenv("ADETECT_DB_MAX_BYTES",str((300 if cloud else 500)*1024**2)))}


def _folders():
    from core.evidence_store import root as evidence_root
    from core.exporters.artifact_store import root as export_root
    return (("evidence",evidence_root()),("exports",export_root()))


def usage():
    from config import settings
    with get_conn() as conn:
        schema(conn)
        if storage.remote():
            size=conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
            files=conn.execute("SELECT COALESCE(SUM(size),0) FROM stored_blob WHERE expired=0").fetchone()[0]
        else:
            path=Path(settings.DB_PATH)
            size=sum(p.stat().st_size for p in path.parent.glob(path.name+'*') if p.is_file())
            files=sum(p.stat().st_size for _,folder in _folders() if folder.exists() for p in folder.iterdir() if p.is_file())
        return {"files":int(files),"db":int(size),"limits":limits()}


def summary(state=None):
    """화면 표시용 사용률. 파일·DB 중 한도에 더 가까운 쪽을 사용률로 본다 (둘 중 하나만 차도 저장이 막힌다)."""
    state=state or usage()
    lim=state["limits"]
    ratio=max(state["files"]/lim["files"] if lim["files"] else 1.0, state["db"]/lim["db"] if lim["db"] else 1.0)
    level="critical" if ratio>=CRITICAL_RATIO else "warn" if ratio>=WARN_RATIO else "ok"
    return {**state,"total":state["files"]+state["db"],"total_limit":lim["files"]+lim["db"],"ratio":ratio,"level":level}


def human(size):
    size=float(size or 0)
    for unit in ("B","KB","MB","GB"):
        if size<1024 or unit=="GB":
            return f"{size:.0f}{unit}" if unit=="B" else f"{size:.1f}{unit}"
        size/=1024


def ensure_capacity(extra=0):
    state=usage()
    if state["files"]+extra>state["limits"]["files"] or state["db"]>=state["limits"]["db"]:
        raise CapacityError(CAPACITY_MESSAGE)


def is_capacity_error(exc_or_text):
    text=str(exc_or_text)
    return isinstance(exc_or_text,CapacityError) or "저장 용량 상한" in text or "보관 용량 초과" in text


def register(name,kind,size):
    with get_conn() as conn:
        schema(conn)
        conn.execute("INSERT INTO stored_blob(name,kind,size,created) VALUES(?,?,?,?) ON CONFLICT(name,kind) DO UPDATE SET expired=0,created=excluded.created,size=excluded.size",(name,kind,size,time.time()))


def pin(names,value):
    """원본 보호. 메타데이터가 아직 없는 기존 파일도 보호할 수 있도록 등록 후 표시한다."""
    from core.evidence_store import root as evidence_root
    folder=evidence_root()
    with get_conn() as conn:
        schema(conn)
        for name in names:
            path=folder/name
            if not storage.remote() and path.is_file():
                conn.execute("INSERT INTO stored_blob(name,kind,size,created) VALUES(?,?,?,?) ON CONFLICT(name,kind) DO NOTHING",(name,'evidence',path.stat().st_size,path.stat().st_mtime))
            conn.execute("UPDATE stored_blob SET pinned=? WHERE name=? AND kind='evidence'",(int(value),name))


def pinned(names):
    names=list(names)
    if not names: return set()
    with get_conn() as conn:
        schema(conn)
        marks=",".join("?"*len(names))
        return {r["name"] for r in conn.execute(f"SELECT name FROM stored_blob WHERE kind='evidence' AND pinned=1 AND name IN ({marks})",names)}


def candidate_key(item):
    return item.get("종류","")+"/"+item.get("대상","")


def cleanup(dry_run=True, protect_project=None, only=None):
    """Never removes protected results. Deletion candidates remain visible before apply.

    보호: 모든 프로젝트·자료 종류의 최근 성공 결과와 그 원본, `protect_project`의 보관 중인 성공 결과 원본,
    진행 중 수집(정리 자체를 중단), 작성 중 임시 파일(.tmp), pin 처리된 원본.
    `only`가 주어지면 사용자가 미리보기에서 본 후보(candidate_key) 중 지금도 후보인 것만 삭제한다.
    """
    from core import projects
    from core.exporters.artifact_store import _schema
    cutoff=(datetime.now(timezone.utc)-timedelta(days=365)).isoformat()
    fresh=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
    allowed=set(only) if only is not None else None
    candidates=[]; protected=set()
    take=lambda item: allowed is None or candidate_key(item) in allowed
    with get_conn() as conn:
        schema(conn); projects.schema(conn); _schema(conn)
        if conn.execute("SELECT id FROM project_task WHERE state IN ('대기','수집 중') LIMIT 1").fetchone():
            return [{"종류":"안내","대상":"수집 중에는 정리하지 않습니다.","파일명":"","예상 용량":0}]
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
                assets={a['filename'] for r in value.get('records',[]) for a in r.get('assets',[])}
                # 최근 성공 결과(자료 종류별 1건)와 현재 프로젝트 결과, 30일 이내 참조 원본은 만료하지 않는다.
                if counts[key]==1 or row['session_id']==protect_project or row['created_at']>fresh:
                    protected.update(assets)
            elif good or row['created_at']<cutoff:
                item={'종류':'결과 상세','대상':row['id'],'파일명':projects.SOURCES[source][0]+" · "+row['created_at'][:16],'예상 용량':len(row['result_json'] or '')}
                if not take(item): continue
                candidates.append(item)
                if not dry_run:
                    tombstone={'schema_version':3,'source':source,'status':row['status'],'expired':True,'collected_at':row['created_at'],'records':[],'parts':{},'sample_sources':value.get('sample_sources',[])}
                    conn.execute("UPDATE function_run SET result_json=? WHERE id=?",(json.dumps(tombstone),row['id']))
                    conn.execute("DELETE FROM project_review WHERE run_id=?",(row['id'],))
                    conn.execute("DELETE FROM project_digest WHERE run_id=? OR run_id LIKE ?",(row['id'],row['id']+":%"))
        blobs={(b['name'],b['kind']):dict(b) for b in conn.execute("SELECT * FROM stored_blob WHERE expired=0")}
        if not storage.remote():
            # 메타데이터가 없는 기존 파일도 미리보기에 동일하게 보여야 실행 결과와 목록이 일치한다.
            for kind,folder in _folders():
                if not folder.exists(): continue
                for p in folder.iterdir():
                    if not p.is_file() or p.suffix==".tmp" or p.name.startswith("."): continue
                    if (p.name,kind) not in blobs:
                        blobs[(p.name,kind)]={'name':p.name,'kind':kind,'size':p.stat().st_size,'created':p.stat().st_mtime,'pinned':0,'expired':0,'legacy':True}
        for blob in blobs.values():
            if blob['pinned'] or blob['name'].endswith('.tmp'): continue
            days=30 if blob['kind']=='evidence' else (1 if storage.remote() else 7)
            if blob['created']>time.time()-days*86400 or blob['name'] in protected: continue
            item={'종류':'원본 파일' if blob['kind']=='evidence' else '다운로드 파일','대상':blob['kind']+":"+blob['name'],'파일명':blob['name'],'예상 용량':int(blob['size'] or 0)}
            if not take(item): continue
            candidates.append(item)
            if not dry_run:
                if blob.get('legacy'):
                    conn.execute("INSERT INTO stored_blob(name,kind,size,created) VALUES(?,?,?,?) ON CONFLICT(name,kind) DO NOTHING",(blob['name'],blob['kind'],blob['size'],blob['created']))
                if storage.remote(): storage.delete(blob['kind'],blob['name'])
                else:
                    folder=dict(_folders())[blob['kind']]
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


def availability_detail(result):
    """(보유 상태, 없는 원본 목록). 상태 문자열은 availability()와 동일하다."""
    from core.evidence_store import read_bytes
    from core.projects import available
    # 만료된 결과와 복원할 결과가 없는 실패·중단 기록은 모두 '이력만 있음'이다.
    if result.get('expired') or not available({'result':result}): return '이력만 있음', []
    missing=[]; seen=set()
    for r in result.get('records',[]):
        for a in r.get('assets',[]):
            if a.get('filename') in seen: continue
            seen.add(a.get('filename'))
            if read_bytes(a) is None:
                missing.append({"자료ID":r.get("id"),"종류":r.get("kind"),"파일명":a.get("filename"),"원문 링크":a.get("source_url") or r.get("source_url")})
    return ('결과·원본 모두 있음' if not missing else '결과만 있음 (일부 원본 없음)'), missing


def availability(result):
    return availability_detail(result)[0]
