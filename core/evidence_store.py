"""원본 자료는 내용 해시로 로컬 보관하며 DB에는 참조만 저장한다."""
import hashlib
import os
from pathlib import Path
from urllib.parse import urljoin
import requests
from core.scrapers.brand_site import validate_public_url


def root():
    return Path(os.getenv("ADETECT_EVIDENCE_DIR","storage/evidence")).resolve()


def save_bytes(data, extension, source_url=""):
    if extension not in ("png","jpg","webp","gif","mp4","html"):
        raise ValueError("지원하지 않는 원본 형식")
    from core.exporters.artifact_store import check_secrets
    check_secrets(data)
    folder=root()
    folder.mkdir(parents=True,exist_ok=True)
    filename=hashlib.sha256(data).hexdigest()+"."+extension
    from core import storage
    from core.retention import register, ensure_capacity, CapacityError
    if storage.remote():
        if storage.get('evidence',filename) is None:
            ensure_capacity(len(data))
            storage.put('evidence',filename,data)
        register(filename,'evidence',len(data))
        return {"filename":filename,"bytes":len(data),"source_url":source_url,"sha256":filename.split('.')[0]}
    path=folder/filename
    limit=int(os.getenv("ADETECT_EVIDENCE_MAX_BYTES",str(5*1024**3)))
    if not path.exists():
        ensure_capacity(len(data))
        used=sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
        if used+len(data)>limit:
            raise CapacityError("원본 보관 용량 초과 — 설정 > 저장 공간 관리에서 정리 후보를 확인해주세요.")
        temporary=path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    register(filename,'evidence',len(data))
    return {"filename":filename,"bytes":len(data),"source_url":source_url,"sha256":filename.split('.')[0]}


def read_bytes(asset):
    filename=asset.get("filename","")
    from core import storage
    if storage.remote():
        data=storage.get('evidence',filename)
        return data if data is not None and hashlib.sha256(data).hexdigest()==asset.get('sha256') else None
    path=(root()/filename).resolve()
    if path.parent != root() or not path.is_file():
        return None
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=asset.get("sha256"):
        return None
    return data


def fetch_asset(url, maximum=25*1024**2):
    for _ in range(5):
        validate_public_url(url)
        with requests.get(url,stream=True,allow_redirects=False,timeout=15) as response:
            if response.is_redirect:
                url=urljoin(url,response.headers["Location"])
                continue
            response.raise_for_status()
            mime=response.headers.get("Content-Type","").split(";")[0].lower()
            extension={"image/png":"png","image/jpeg":"jpg","image/webp":"webp","image/gif":"gif","video/mp4":"mp4"}.get(mime)
            if not extension:
                raise ValueError("원본 형식 미지원")
            data=bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>maximum:
                    raise ValueError("개별 원본 용량 한도 초과")
            return save_bytes(bytes(data),extension,url)
    raise ValueError("리디렉션 한도 초과")


def capture_website(url, save_images=True):
    from playwright.sync_api import sync_playwright
    from core.jobs import checkpoint
    validate_public_url(url)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":1280,"height":900})
            image_responses={}
            def remember(response):
                if response.request.resource_type=="image":
                    image_responses[response.url]=response
            page.on("response",remember)
            def route(request):
                try:
                    validate_public_url(request.request.url)
                    if request.request.resource_type=="media":
                        request.abort()
                    else:
                        request.continue_()
                except (ValueError,OSError):
                    request.abort()
            page.route("**/*",route)
            page.goto(url,wait_until="domcontentloaded",timeout=30000)
            try:
                page.wait_for_load_state("networkidle",timeout=5000)
            except Exception:
                pass
            body=page.locator("body").inner_text(timeout=5000)
            if any(w in body.lower() for w in ("captcha","자동입력 방지","접근이 제한")):
                raise ValueError("접근 제한")
            assets=[save_bytes(page.screenshot(full_page=True),"png",page.url)]
            images=page.locator("img").evaluate_all("els => els.map(e => ({url:e.currentSrc || e.src,alt:e.alt,width:e.naturalWidth,height:e.naturalHeight}))")
            links=page.locator("a[href]").evaluate_all("els => els.map(e=>({text:e.innerText,url:e.href})).filter(e=>e.text.trim())")
            warnings=[]
            candidates=list(dict.fromkeys(i["url"] for i in images if i["width"]>=300 and i["height"]>=150))
            for image in candidates[:12] if save_images else []:
                checkpoint("랜딩 이미지 원본 저장 중")
                try:
                    response=image_responses.get(image)
                    if response and response.ok:
                        extension={"image/png":"png","image/jpeg":"jpg","image/webp":"webp","image/gif":"gif"}.get(response.headers.get("content-type","").split(';')[0].lower())
                        if not extension:
                            raise ValueError("이미지 응답 형식 미지원")
                        if int(response.headers.get("content-length","0"))>6*1024**2:
                            raise ValueError("이미지 용량 초과")
                        data=response.body()
                        if len(data)>6*1024**2:
                            raise ValueError("이미지 용량 초과")
                        assets.append(save_bytes(data,extension,image))
                    else:
                        assets.append(fetch_asset(image,6*1024**2))
                except Exception:
                    warnings.append("이미지 원본 저장 실패: "+image)
            return {"assets":assets,"visible_text":body,"images":images,"links":links[:100],"warnings":warnings,
                    "image_count":len(candidates),"source_url":page.url,
                    "coverage":"이미지 속 문구는 자동 추출하지 않았습니다. 캡처·이미지에서 조건을 확인하세요. 이미지 최대 12개 보관."}
        finally:
            browser.close()
