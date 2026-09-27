"""Portable, validated project backups. Multipart packages never contain credentials."""
import hashlib
import json
import uuid
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED
from core import projects
from database.db import get_conn
from core.evidence_store import read_bytes, save_bytes
from core.exporters.artifact_store import check_secrets

MAX_TOTAL=250*1024**2
CHUNK=30*1024**2


def make(pid):
    project=projects.load(pid)
    project={k:v for k,v in project.items() if k in (*projects.INPUTS,'name')}
    histories=projects.histories(pid)
    for h in histories: h['result']['records']=projects.review_rows(h)
    with get_conn() as conn:
        projects.schema(conn)
        for h in histories:
            digest = conn.execute('SELECT fingerprint,data FROM project_digest WHERE run_id=?', (h['run_id'],)).fetchone()
            if digest: h['news_digest'] = dict(digest)
    entries={'project.json':json.dumps({'schema_version':3,'project':project,'histories':histories,'exports':projects.exports(pid)},ensure_ascii=False).encode()}
    missing=[]
    for h in histories:
        for row in h['result'].get('records',[]):
            for asset in row.get('assets',[]):
                name='originals/'+asset['filename']
                if name in entries: continue
                data=read_bytes(asset)
                if data is None: missing.append(asset['filename'])
                else: entries[name]=data
    if sum(map(len,entries.values()))>MAX_TOTAL: raise ValueError('백업 250MB 상한 — 자료별 보관량을 줄여주세요.')
    for data in entries.values(): check_secrets(data)
    # Logical files are chunked so even JSON larger than a cloud object limit fits.
    chunks={}
    filemap={}
    for name,data in entries.items():
        names=[]
        for offset in range(0,max(len(data),1),CHUNK):
            key='chunks/'+uuid.uuid4().hex
            chunks[key]=data[offset:offset+CHUNK]; names.append(key)
        filemap[name]={'chunks':names,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    manifest={'schema_version':3,'backup_id':uuid.uuid4().hex,'files':filemap,'missing_assets':missing,'parts':len(chunks)}
    packages=[]
    for idx,(key,data) in enumerate(chunks.items(),1):
        out=BytesIO()
        with ZipFile(out,'w',ZIP_DEFLATED) as z:
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
            z.writestr(key,data)
        packages.append((f'ADetect_backup_{manifest["backup_id"]}_{idx:03d}.zip',out.getvalue()))
    return packages


def inspect(packages):
    chunks={}; manifest=None; total=0
    if not packages or len(packages)>100: raise ValueError('백업 파일 수를 확인해주세요.')
    for data in packages:
        if len(data)>40*1024**2: raise ValueError('개별 백업 40MB 상한')
        with ZipFile(BytesIO(data)) as z:
            if len(z.infolist())>1000: raise ValueError('과도한 압축 항목')
            for info in z.infolist():
                path=PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename:
                    raise ValueError('잘못된 압축 경로')
                total+=info.file_size
                if total>MAX_TOTAL+10*1024**2: raise ValueError('압축 해제 용량 상한')
                if info.filename=='manifest.json':
                    current=json.loads(z.read(info))
                    if manifest is not None and manifest!=current: raise ValueError('서로 다른 백업 파일입니다.')
                    manifest=current
                else:
                    if info.filename in chunks: raise ValueError('중복 패키지')
                    chunks[info.filename]=z.read(info)
    if not manifest or manifest.get('schema_version')!=3 or len(chunks)!=manifest.get('parts'):
        raise ValueError('지원하지 않는 백업 버전 또는 패키지 누락')
    files={}
    for name,meta in manifest['files'].items():
        if any(c not in chunks for c in meta['chunks']): raise ValueError('백업 패키지 누락')
        content=b''.join(chunks[c] for c in meta['chunks'])
        if len(content)!=meta['bytes'] or hashlib.sha256(content).hexdigest()!=meta['sha256']: raise ValueError('백업 파일 손상')
        check_secrets(content)
        files[name]=content
    payload=json.loads(files['project.json'])
    if payload.get('schema_version')!=3 or not payload.get('project',{}).get('brand_name'): raise ValueError('프로젝트 정보 없음')
    if any(h.get('source') not in projects.SOURCES for h in payload.get('histories',[])): raise ValueError('알 수 없는 자료 종류')
    return payload,files,manifest


def restore(packages):
    from core.retention import ensure_capacity
    payload,files,manifest=inspect(packages)
    ensure_capacity(sum(map(len,files.values())))
    # Validate all references before writing anything; a recorded omitted original is allowed.
    for h in payload['histories']:
        for row in h['result'].get('records',[]):
            for asset in row.get('assets',[]):
                data=files.get('originals/'+asset['filename'])
                if data is not None and hashlib.sha256(data).hexdigest()!=asset['sha256']: raise ValueError('원본 해시 불일치')
    for name,data in files.items():
        if name.startswith('originals/'):
            ext=name.rsplit('.',1)[-1]
            saved=save_bytes(data,ext)
            if name!='originals/'+saved['filename']: raise ValueError('원본 파일명 불일치')
    pid=uuid.uuid4().hex; p=payload['project']; timestamp=projects.now()
    # DB import is one transaction; retries make an independent project, never overwrite.
    with get_conn() as conn:
        projects.schema(conn)
        conn.execute("INSERT INTO analysis_session(id,brand_name,category,competitors_json,created_at,inputs_json) VALUES(?,?,?,?,?,?)",(pid,p['brand_name'],p.get('category',''),json.dumps(p.get('competitors',[])),timestamp,json.dumps({k:p[k] for k in projects.INPUTS if k in p},ensure_ascii=False)))
        conn.execute("INSERT INTO project(id,name,updated) VALUES(?,?,?)",(pid,p.get('name',p['brand_name'])+' (복원)',timestamp))
        for h in payload['histories']:
            rid=uuid.uuid4().hex
            conn.execute("INSERT INTO function_run(id,session_id,function_type,status,result_json,created_at) VALUES(?,?,?,?,?,?)",(rid,pid,h['source'],h['result']['status'],json.dumps(h['result'],ensure_ascii=False),h['created']))
            if h.get('news_digest'):
                d = h['news_digest']
                conn.execute('INSERT INTO project_digest VALUES(?,?,?)', (rid,d['fingerprint'],d['data']))
        for e in payload.get('exports',[]):
            conn.execute("INSERT INTO project_export VALUES(?,?,?,?)",(uuid.uuid4().hex,pid,e['manifest'],e['created']))
    return pid
