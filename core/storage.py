"""Private object storage. No credentials or public bucket URLs in report data."""
import os
import requests


def remote():
    return bool(os.getenv("ADETECT_DATABASE_URL"))


def request(method,group,name,data=None):
    if '/' in name or '\\' in name or name in ('.','..'): raise ValueError("잘못된 파일 경로")
    base=os.environ["SUPABASE_URL"].rstrip('/')
    if not base.startswith('https://'): raise ValueError("HTTPS 저장소가 필요합니다.")
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    bucket=os.getenv("ADETECT_STORAGE_BUCKET","adetect-private")
    if data is not None and len(data)>40*1024**2: raise ValueError("클라우드 단일 파일 40MB 상한")
    response=requests.request(method,f"{base}/storage/v1/object/{bucket}/{group}/{name}",headers={"apikey":key,"Authorization":"Bearer "+key,"Content-Type":"application/octet-stream","x-upsert":"true"},data=data,timeout=60)
    if method=='GET' and response.status_code in (400,404): return None
    if not response.ok: raise ValueError("비공개 저장소 요청 실패 — 설정·권한·용량을 확인해주세요.")
    return response.content


def put(group,name,data): return request('POST',group,name,data)
def get(group,name): return request('GET',group,name)
def delete(group,name): return request('DELETE',group,name)
