"""사용자가 지정한 공개 홈페이지에서 원문을 수집한다. 도메인을 추측하지 않는다."""
import ipaddress
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import requests
from config import settings


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text, self.links, self.hidden = [], [], 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        text = " ".join(data.split())
        if not self.hidden and len(text) > 3:
            self.text.append(text)


def validate_public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        raise ValueError("공개 http/https URL을 입력하세요.")
    if parts.port not in (None, 80, 443):
        raise ValueError("표준 웹 포트만 지원합니다.")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("공개 웹사이트만 수집할 수 있습니다.")
    return url


def fetch_public_html(url):
    for _ in range(5):
        validate_public_url(url)
        with requests.get(url, timeout=15, allow_redirects=False, stream=True,
                          headers={"User-Agent": "ADetect/1.0 (brand research)"}) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            response.raise_for_status()
            if "html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("HTML 페이지가 아닙니다.")
            data = bytearray()
            for chunk in response.iter_content(8192):
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ValueError("페이지 크기 제한 초과")
            encoding = response.encoding
            if not encoding or encoding.lower() == "iso-8859-1":
                encoding = "utf-8"
            return data.decode(encoding, errors="replace"), url
    raise ValueError("리디렉션 한도 초과")


def render_public_page(url):
    """JS 전용 공개 페이지 폴백. 모든 하위 요청도 공개 주소로 제한한다."""
    from playwright.sync_api import sync_playwright
    validate_public_url(url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width":1280,"height":900})
            def route_request(route):
                try:
                    if route.request.resource_type in ("image","font","media"):
                        route.abort()
                        return
                    validate_public_url(route.request.url)
                    route.continue_()
                except (ValueError,OSError):
                    route.abort()
            context.route("**/*",route_request)
            page=context.new_page()
            page.goto(url,wait_until="domcontentloaded",timeout=20000)
            try:
                page.wait_for_load_state("networkidle",timeout=5000)
            except Exception:
                pass
            text=page.locator("body").inner_text(timeout=5000)
            if any(x in text.lower() for x in ("captcha","자동입력 방지","접근이 제한")):
                raise ValueError("접근 제한")
            validate_public_url(page.url)
            return page.content(),page.url
        finally:
            browser.close()


def crawl_brand_website(brand_name, url=None, homepage_url=None):
    result = {"brand": brand_name, "source_url": url or homepage_url, "fallback_used": False,
              "raw_copy_snippets": [], "usp_summary": "not_available", "promotion_fact": "not_available",
              "social_links": [], "collected_at": datetime.now(timezone.utc).isoformat(), "status": "not_available"}
    if settings.SAMPLE_MODE:
        return {**result,"message":"SAMPLE 모드에서는 홈페이지를 수집하지 않습니다."}
    for candidate in dict.fromkeys(u for u in (url, homepage_url) if u):
        try:
            content, final_url = fetch_public_html(candidate)
            parser = TextParser()
            parser.feed(content)
            snippets = list(dict.fromkeys(parser.text))[:120]
            if len(" ".join(snippets)) < 100:
                content, final_url = render_public_page(final_url)
                parser = TextParser()
                parser.feed(content)
                snippets = list(dict.fromkeys(parser.text))[:120]
            result.update(source_url=final_url, raw_copy_snippets=snippets, status="available" if snippets else "not_available",
                          fallback_used=candidate != url, social_links=[urljoin(final_url, h) for h in parser.links
                          if urlsplit(urljoin(final_url,h)).hostname in ("www.instagram.com", "instagram.com", "www.youtube.com", "youtube.com")])
            return result
        except Exception:
            continue
    result["message"] = "공식 홈페이지 URL이 없거나 페이지에 접근하지 못했습니다."
    return result
