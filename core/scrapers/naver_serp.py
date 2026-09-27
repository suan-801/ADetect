"""공개 검색결과 1회 캡처. 차단·알 수 없는 마크업은 미확인으로 처리."""
import base64
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from config import settings


def capture_search(keyword, brand_name, keyword_type="brand_rep", homepage=None, observe_rotations=1):
    result = {"keyword": keyword, "keyword_type": keyword_type, "rank": None, "has_ad": None,
              "status": "not_available", "captured_at": datetime.now(timezone.utc).isoformat(),
              "source_url": "https://search.naver.com/search.naver?"+urlencode({"query": keyword})}
    if settings.SAMPLE_MODE:
        return {**result, "message": "SAMPLE 모드에서는 공개 사이트를 요청하지 않습니다."}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.goto(result["source_url"], wait_until="domcontentloaded", timeout=20000)
                text = page.locator("body").inner_text(timeout=5000)
                if any(t in text.lower() for t in ("captcha", "자동입력", "비정상적인 접근", "접근이 제한")):
                    return {**result, "message": "차단 감지 — 수동 확인 필요"}
                result["capture_data_uri"] = "data:image/png;base64,"+base64.b64encode(page.screenshot(full_page=False)).decode()
                brand_area = page.locator("#brandsearch, #brandsearch_area, .sp_brand, .brandsearch").first
                result["brand_search"] = {"status":"not_available", "has_ad":None, "rotation_count":None}
                if brand_area.count():
                    copy = brand_area.inner_text().strip()
                    if brand_name.replace(" ", "").lower() in copy.replace(" ", "").lower():
                        links = brand_area.locator("a[href]").evaluate_all("els => els.map(e => e.href)")
                        result["brand_search"] = {"status":"available", "has_ad":True, "ad_copy_snippet":copy,
                            "landing_links":list(dict.fromkeys(links)),"observed_variants":1,"rotation_count":None,
                            "note":"관측 횟수 내 서로 다른 소재 수입니다. 전체 계약 소재 수가 아닙니다.","captured_at":result["captured_at"]}
                        variants = {copy}
                        observations = 1
                        for _ in range(max(0,min(observe_rotations,3)-1)):
                            from core.jobs import checkpoint
                            checkpoint("브랜드검색 소재 순차 관측 중")
                            page.wait_for_timeout(1500)
                            page.reload(wait_until="domcontentloaded",timeout=20000)
                            current_text = page.locator("body").inner_text(timeout=5000)
                            if any(t in current_text.lower() for t in ("captcha","자동입력","비정상적인 접근","접근이 제한")):
                                result["brand_search"]["note"] += " 추가 관측 중 차단되어 중단했습니다."
                                break
                            current = page.locator("#brandsearch, #brandsearch_area, .sp_brand, .brandsearch").first
                            if current.count():
                                observed = current.inner_text().strip()
                                if brand_name.replace(" ","").lower() in observed.replace(" ","").lower():
                                    variants.add(observed)
                                    observations += 1
                        result["brand_search"].update(observed_variants=len(variants),rotation_count=len(variants),
                            observations=observations,variant_copy_snippets=sorted(variants))
                # 광고 전용 영역에 식별자가 없으면 페이지 전체를 광고로 추정하지 않는다.
                section = page.locator("#power_link_body, .sc_new.sp_power, #sp_power").first
                if section.count():
                    blocks = section.locator("li").all()
                    ads = []
                    for block in blocks:
                        copy = block.inner_text().strip()
                        links = block.locator("a[href]").evaluate_all("els => els.map(e => e.href)")
                        if copy and links:
                            ads.append({"copy": copy, "links": links})
                    matches = [(i+1, a) for i,a in enumerate(ads) if brand_name.replace(" ", "").lower() in a["copy"].replace(" ", "").lower()]
                    if matches:
                        rank, ad = matches[0]
                        result.update(status="available", has_ad=True, rank=rank, ad_copy_snippet=ad["copy"], landing_links=ad["links"])
                    elif ads:
                        result.update(status="available", has_ad=False, ad_copy_snippet="")
                result.setdefault("message", "관측한 한 화면 기준. 미확인은 미운영을 뜻하지 않습니다.")
                return result
            finally:
                browser.close()
    except Exception:
        return {**result, "message": "캡처 실패 — 브라우저 설치·접근 상태 확인 필요"}


BLOCK_WORDS = ("captcha", "자동입력", "비정상적인 접근", "접근이 제한")
AREAS = {
    # 선택자가 맞지 않으면 '식별 실패'로 남기고 광고가 없다고 판단하지 않는다.
    "powerlink": "#power_link_body, .sc_new.sp_power, #sp_power, section.sp_power",
    "brand_search": "div.brand_search, #brandsearch, #brandsearch_area, .sp_brand, .brandsearch, section.sp_brand",
}
DOMAIN = r"(?:[a-z0-9-]+\.)+(?:com|co\.kr|kr|net|shop|store|io|me|org)(?:/[\w\-./]*)?"
VIEWPORT = {"width": 1440, "height": 1000}


def observe_search(keyword):
    """네이버 PC 검색 결과 1회 관측. 첫 화면 캡처 + 광고 영역 확대 캡처 + 페이지에서 직접 추출한 광고 정보.

    반환 state: captured / blocked / failed. 광고를 클릭하거나 랜딩을 방문하지 않는다.
    """
    import re
    result = {"keyword": keyword, "source_url": "https://search.naver.com/search.naver?"+urlencode({"query": keyword}),
              "captured_at": datetime.now(timezone.utc).isoformat(),
              "environment": f"PC 브라우저 {VIEWPORT['width']}×{VIEWPORT['height']} · 첫 화면 캡처",
              "state": "failed", "screenshot": None, "areas": {}}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport=VIEWPORT)
                page.goto(result["source_url"], wait_until="domcontentloaded", timeout=20000)
                text = page.locator("body").inner_text(timeout=5000)
                if any(t in text.lower() for t in BLOCK_WORDS):
                    return {**result, "state": "blocked", "message": "차단 화면 감지 — 판독 불가"}
                result["screenshot"] = page.screenshot(full_page=False)
                for name, selector in AREAS.items():
                    area = page.locator(selector).first
                    if not area.count():
                        result["areas"][name] = {"identified": False, "ads": []}
                        continue
                    ads = []
                    # 파워링크는 광고 하나가 최상위 li 하나다(하위 li는 같은 광고의 추가 링크). 브랜드검색은 영역 전체가 광고 하나다.
                    blocks = area.locator("li:not(li li)").all() if name == "powerlink" else []
                    for block in (blocks or [area]):
                        copy = block.inner_text().strip()
                        links = list(dict.fromkeys(block.locator("a[href]").evaluate_all("els => els.map(e => e.href)")))
                        if not copy:
                            continue
                        lines = [l.strip() for l in copy.splitlines() if l.strip()]
                        shown = re.findall(DOMAIN, copy.lower())
                        ads.append({"title": lines[0][:120], "text": " ".join(lines)[:600], "display_url": shown[0] if shown else None, "links": links[:10]})
                    try:
                        shot = area.screenshot(timeout=5000)
                    except Exception:
                        shot = None
                    result["areas"][name] = {"identified": True, "ads": ads, "screenshot": shot}
                result["state"] = "captured"
                return result
            finally:
                browser.close()
    except Exception:
        return {**result, "state": "failed", "message": "캡처 실패 — 브라우저 설치·접속 상태 확인 필요"}
