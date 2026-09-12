#!/usr/bin/env python3
# ad-monitor 독립 스킬 — 메타 광고 소재 수집 + Gemini 4축 분석 (자사·경쟁사 구분 없음)
# Apify + Gemini REST API 직접 호출 (n8n 불필요)
#
# ★ 독립 스킬 — Claudecode_MarketingOS_student 프로젝트의 01_brand/02_competitor/03_customer/04_brief
# 등 다른 스킬 산출물을 전혀 참조하지 않습니다. 자격증명도 `ad_monitor/.env` 전용 파일 사용.
#
# 사전 준비
#   1) Apify 가입 → API 토큰: https://console.apify.com/settings/integrations
#   2) Apify 액터 1회 활성화: https://apify.com/curious_coder/facebook-ads-library-scraper
#   3) Gemini API 키: https://aistudio.google.com/apikey
#   4) 자격증명 등록 — `ad_monitor/.env` 파일에 작성 (스크립트가 자동 로드):
#        APIFY_TOKEN=apify_api_...
#        GEMINI_API_KEY=AQ...   # 2026년 새 키는 AQ 로 시작
#      템플릿: `ad_monitor/.env.example` 참고
#
# 사용 (Less is More — URL 1개만 입력, 자사/경쟁사 구분 없음)
#   python3 fetch_ads.py "https://www.facebook.com/ads/library/?...&view_all_page_id=123"
#       └ 첫 크롤 후 page_name 으로 자동 slug 도출 → _inputs/{slug}.md 자동 생성
#   python3 fetch_ads.py brand-a           # 기존 시드 슬러그
#   python3 fetch_ads.py                   # _inputs/urls.md 전체 일괄
#   python3 fetch_ads.py --max 50          # 브랜드당 최대 광고 수
#   python3 fetch_ads.py --no-gemini       # 분석 스킵 (수집만)
#
# 출력
#   ad_monitor/{slug}/
#     ├── ad-creatives.md          # 분석 요약 (단일 브랜드, USP 3항목 + UTM 관찰 포함)
#     └── ad-creatives/
#         ├── metadata.json        # 광고 카드 원본
#         ├── analysis.json        # USP 3 항목 + Creative Key Visual + ad_pattern 분석
#         ├── utm_samples.json     # 랜딩 URL UTM/트래킹 파라미터 관찰 원본
#         ├── images/{ad_id}_{n}.jpg
#         ├── videos/{ad_id}_{n}.mp4
#         └── keyframes/{ad_id}_*_kf{1..6}.jpg   # 영상에서 추출한 키프레임 (시각 분석용)
#   ad_monitor/ads_report.md        # 통합 트렌드 리포트 (전체 브랜드)
#
# 영상 분석 방식
#   ffmpeg 로 키프레임 6장 (8/22/40/58/75/92%) 추출 후 Gemini 멀티모달 이미지 분석.
#   ★ 대본·오디오 추출 ❌ — 자막·텍스트 오버레이만 키프레임에서 읽음.

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from collections import Counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Windows 콘솔(cp949) 은 이모지(⚠️·🚫·❌) print 시 UnicodeEncodeError 로 죽는다 — UTF-8 강제
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ad_inputs import (
    COMBINED_INPUT,
    INPUTS_DIR,
    load_combined_brands,
    load_brand,
    load_brands,
    slugify,
    write_seed_md,
)
import utm_pattern


API_BASE = "https://api.apify.com/v2"
GEMINI_BASE = "https://generativelanguage.googleapis.com"
ROOT = pathlib.Path(__file__).resolve().parents[1]   # ad_monitor/
BRANDS_ROOT = ROOT


def _load_env_file(env_path):
    """`KEY=VALUE` 한 줄씩 파싱해 os.environ 에 주입 (기존 값은 덮어쓰지 않음).
    외부 의존성(python-dotenv) 없이 stdlib 만으로 처리.
    """
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


# 독립 스킬 전용 자격증명 파일 (다른 스킬의 09_tracking/.env 와 별개)
_load_env_file(ROOT / ".env")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

EXCLUDED_KEYS = {
    "video_preview_image_url",
    "page_profile_picture_url",
    "profile_photo",
    "page_cover_photo",
    "watermarked_resized_image_url",
}


def first_url(value):
    if not value:
        return ""
    return value.split("|", 1)[0].strip()


# ──────────────────────── HTTP / Apify ────────────────────────

class GeminiQuotaExceeded(Exception):
    """무료 티어 일일 한도(250 RPD) 또는 RPM 한도 초과.
    호출자가 잡아서 부분 결과 저장 후 graceful 종료해야 함.
    """
    pass


def _is_quota_error(http_code, body_str):
    if http_code == 429:
        return True
    if http_code == 403:
        upper = body_str.upper()
        return ("QUOTA" in upper) or ("EXCEEDED" in upper) or ("RESOURCE_EXHAUSTED" in upper)
    return False


def http(method, url, payload=None, raw=False, timeout=120, _retries=3):
    headers = {"Content-Type": "application/json"}
    body = json.dumps(payload).encode() if payload else None
    is_gemini = "generativelanguage.googleapis.com" in url
    for attempt in range(_retries):
        req = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=timeout) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except HTTPError as e:
            body_str = ""
            try:
                body_str = e.read().decode(errors='ignore')
            except Exception:
                pass
            # Gemini 무료 한도 / RPM 한도 → 호출자에게 위임 (sys.exit 금지)
            if is_gemini and _is_quota_error(e.code, body_str):
                raise GeminiQuotaExceeded(f"HTTP {e.code}: {body_str[:200]}")
            # Gemini 서버 일시 장애(5xx, "high demand" 등) → 지수 백오프 재시도
            if is_gemini and e.code >= 500 and attempt < _retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            # Gemini 의 그 외 실패는 sys.exit 금지 — 호출자(광고별 try/except)가 이 1건만
            # 실패 처리하고 다음 광고로 계속 진행하도록 일반 예외로 전달
            if is_gemini:
                raise RuntimeError(f"HTTP {e.code}: {body_str[:300]}")
            sys.exit(f"HTTP {e.code} on {method} {url}\n{body_str[:500]}")
    raise RuntimeError(f"HTTP retry exhausted on {method} {url}")


def run_actor(token, actor_id, run_input):
    actor_path = actor_id.replace("/", "~")
    url = f"{API_BASE}/acts/{actor_path}/runs?token={token}"
    return http("POST", url, payload=run_input)["data"]


def wait_run(token, run_id, poll=8, max_wait=900):
    url = f"{API_BASE}/actor-runs/{run_id}?token={token}"
    waited = 0
    while waited < max_wait:
        data = http("GET", url)["data"]
        status = data["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return data
        time.sleep(poll)
        waited += poll
    raise TimeoutError(f"Run {run_id} did not finish within {max_wait}s")


def get_items(token, dataset_id):
    url = f"{API_BASE}/datasets/{dataset_id}/items?token={token}&clean=true&format=json"
    return http("GET", url)


def download(url, dest):
    if not url or dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(url, timeout=60) as r:
            dest.write_bytes(r.read())
        return True
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"  · 다운로드 실패: {url[:80]}... → {e}")
        return False


# ──────────────────────── Gemini 분석 프롬프트 ────────────────────────
# 레퍼런스 분석법 (ad_monitor/_reference/analysis_method.md) 적용
# ★ 업종 무관 — 뷰티뿐 아니라 금융/리크루팅/교육/이커머스 등 어떤 업종의 광고에도 동일 프레임 적용

VIDEO_PROMPT = """당신은 15년차 퍼포먼스마케터이자 다양한 산업(뷰티·금융·교육·리크루팅·이커머스 등)의 디지털 광고 분석 전문가입니다.

아래 6장의 이미지는 **하나의 광고 영상에서 시간 순서대로 추출된 키프레임**입니다 (8%·22%·40%·58%·75%·92% 지점). 영상 전체를 본 것처럼 시퀀스를 해석하고 자막·텍스트 오버레이를 빠짐없이 읽어 카피의 흐름을 추정하세요. 오디오 대사는 없으므로 화면에 표시된 자막만 인용하세요.

## 출력 JSON 스키마

{
  "full_storyline": "(HOOK) 0-3초 자막/장면 묘사 ... (페인포인트) ... (브랜드 USP) ... (CTA)",
  "analysis_summary": {
    "hook_type": "...",
    "structure_type": "...",
    "persuasion_elements": ["..."],
    "video_style": "...",
    "key_strengths": ["...", "...", "..."]
  },
  "ad_pattern": "default | trust_anchor | promotion_anchor | hybrid",
  "analysis": {
    "users_problem": "고객의 문제 (공감언어·상황). 페인/욕구/호기심/트렌드 중 어떤 톤",
    "solution": "USP 차별성 + RTB(권위·통념·숫자) + 결과 시각화",
    "promotion": "가격 혜택 + 리스크 제거 + 시급성. 실제 카피 인용",
    "creative_key_visual": "메인 비주얼 1~2줄. 제품/서비스 단독·시연·라이프스타일·인포그래픽·신뢰 자산 중 어떤 형태"
  },
  "_method": "keyframes"
}

## full_storyline 역할 태그
(HOOK) (일상 공감) (페인포인트) (브랜드 USP) (기능/혜택) (효과/결과) (사회적 증거) (추천/후기) (CTA) (기타)

## ad_pattern 라벨 정의
- "default": 페인 후킹 + Solution 자연 연결 + Promotion 약 (가장 흔함)
- "trust_anchor": User's Problem 약, Solution(권위·랭킹·인증) 강 — 페인 없이 신뢰 한 방
- "promotion_anchor": Promotion 거의 전부 — 할인·1+1·한정 강조 (BOFU)
- "hybrid": 위 2개 이상 동시 강조

자막을 요약하지 말고 화면에 보이는 텍스트 그대로 인용하세요."""

KEYFRAME_PCTS = [0.08, 0.22, 0.40, 0.58, 0.75, 0.92]

IMAGE_PROMPT = """당신은 15년차 퍼포먼스마케터이자 다양한 산업(뷰티·금융·교육·리크루팅·이커머스 등)의 디지털 광고 분석 전문가이며, AI 이미지 생성 프롬프트 전문가입니다.

이 광고 이미지를 **픽셀 단위로 정밀 분석**하고, USP 분석법 (3 항목 + Creative Key Visual + ad_pattern) 에 따라 구조화하세요. 또한 AI 이미지 생성 도구로 **거의 동일하게 재현**할 수 있는 상세 프롬프트를 작성하세요.

## ad_pattern (광고 유형 1개 라벨)
- "default": 페인 후킹 → Solution → Promotion 약 (가장 흔함)
- "trust_anchor": User's Problem 약, Solution(권위·랭킹·인증) 강 — 페인 없이 신뢰 한 방 (예: 1위 배지 + 별점)
- "promotion_anchor": Promotion 거의 전부 — 할인·1+1·한정 강조 (BOFU)
- "hybrid": 2개 이상 동시 강조

## 출력 JSON 스키마

{
  "main_copy": "가장 크고 눈에 띄는 핵심 헤드라인 (원문 그대로)",
  "sub_copy": "메인을 보조하는 부가 설명 문구 (원문 그대로)",
  "feature_desc": "제품/서비스의 특징·효능·기능 관련 텍스트 (성분/커리큘럼/혜택 조건 등 업종에 맞게, 원문 그대로)",
  "empathy_copy": "타겟의 고민, 공감을 자극하는 문구 (원문 그대로)",
  "cta": "할인율, 가격, 구매·지원 유도 문구 (원문 그대로)",
  "all_text_extracted": "이미지에서 추출한 모든 텍스트 (전수)",
  "layout_style": "구조 (좌우분할 60:40 / 상하분할 / 중앙집중 / Z형 / F형 등)",
  "visual_style": "사진/일러스트/3D/혼합, 무드 (미니멀/럭셔리/친근 등)",
  "color_mood": "주조 컬러 + HEX 추정 (예: 딥퍼플 #2D1B4E 베이스)",
  "overall_score": 1-10,
  "ad_pattern": "default | trust_anchor | promotion_anchor | hybrid",
  "analysis": {
    "users_problem": "고객의 문제 — 공감언어·상황. 페인/욕구/호기심/트렌드 중 어떤 톤. trust_anchor·promotion_anchor 일 경우 '약함' 또는 '없음' 명시 OK",
    "solution": "해결책·USP·근거 — USP 차별성 + RTB(권위·통념·숫자) + 결과 시각화. 한 광고에 여러 요소면 모두 기록",
    "promotion": "지금 구매/지원해야 하는 이유 — 가격 혜택 + 리스크 제거 + 시급성. 실제 카피 인용",
    "creative_key_visual": "메인 비주얼 1~2줄 묘사. 변주 — 제품/서비스 단독 / 시연 / 라이프스타일 / 인포그래픽 / 신뢰 자산 중 어떤 형태"
  },
  "nanobanana_prompt": "이 광고를 거의 동일하게 재현할 영문 상세 프롬프트 (레이아웃, 텍스트 폰트/크기/색상, 배경 그라데이션 HEX, 제품 위치/각도/조명, 소품 등 모두 포함)"
}

**중요**: 텍스트는 요약하지 말고 원문 그대로 추출하세요."""


def gemini_analyze_image(api_key, image_path):
    if not image_path.exists():
        return None
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    suffix = image_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    url = f"{GEMINI_BASE}/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    body = {
        "contents": [{
            "parts": [
                {"text": IMAGE_PROMPT},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        }],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    res = http("POST", url, payload=body, timeout=120)
    try:
        text = res["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {"error": f"parse_failed: {e}", "raw": str(res)[:500]}


def extract_keyframes(video_path, out_dir):
    """ffmpeg 로 키프레임 6장 (8/22/40/58/75/92%) 추출.
    Gemini Files API 영상 업로드는 코덱/내부 처리 문제로 실패율 높아 키프레임 폴백을 디폴트로 사용."""
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob(f"{video_path.stem}_kf*.jpg"))
    if len(existing) >= len(KEYFRAME_PCTS):
        return existing[:len(KEYFRAME_PCTS)]
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    duration = float(res.stdout.strip())
    frames = []
    for i, pct in enumerate(KEYFRAME_PCTS, start=1):
        t = duration * pct
        out = out_dir / f"{video_path.stem}_kf{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video_path),
             "-frames:v", "1", "-q:v", "3", "-y", str(out)],
            check=True,
        )
        frames.append(out)
    return frames


def gemini_analyze_video(api_key, video_path):
    """영상 → 키프레임 6장 추출 → Gemini 멀티모달 이미지 분석.
    ★ 대본·오디오 추출 ❌ — 자막·텍스트 오버레이만 키프레임에서 읽음."""
    if not video_path.exists():
        return None
    keyframes_dir = video_path.parent.parent / "keyframes"
    frames = extract_keyframes(video_path, keyframes_dir)

    parts = [{"text": VIDEO_PROMPT}]
    for f in frames:
        b64 = base64.b64encode(f.read_bytes()).decode()
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})

    url = f"{GEMINI_BASE}/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    res = http("POST", url, payload=body, timeout=180)
    try:
        text = res["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {"error": f"parse_failed: {e}", "raw": str(res)[:500]}


# ──────────────────────── 미디어 추출 ────────────────────────

def classify_and_extract(item):
    snap = item.get("snapshot") or {}
    videos = snap.get("videos") or []
    images = snap.get("images") or []
    cards = snap.get("cards") or []

    img_urls = []
    vid_urls = []

    if videos:
        fmt = "video"
        for v in videos:
            u = v.get("video_hd_url") or v.get("video_sd_url")
            if u:
                vid_urls.append(u)
    elif cards:
        fmt = "carousel"
        for c in cards:
            cv = c.get("video_hd_url") or c.get("video_sd_url")
            if cv:
                vid_urls.append(cv)
            else:
                ci = c.get("original_image_url") or c.get("resized_image_url")
                if ci:
                    img_urls.append(ci)
    elif images:
        fmt = "image"
        for img in images:
            u = img.get("original_image_url") or img.get("resized_image_url")
            if u:
                img_urls.append(u)
    else:
        fmt = "unknown"

    img_urls = list(dict.fromkeys(img_urls))
    vid_urls = list(dict.fromkeys(vid_urls))
    return fmt, img_urls, vid_urls


# ──────────────────────── 분석 보고서 생성 ────────────────────────

KO_WORD_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
HASHTAG_RE = re.compile(r"#[\w가-힣]+")
STOPWORDS = {
    "있어요", "있는", "있고", "있습니다", "있을", "있다",
    "그리고", "그런데", "하지만", "정말", "진짜", "너무",
    "지금", "오늘", "이번", "저는", "제가", "여러분",
    "광고", "AD", "ad",
}

def extract_caption(item):
    snap = item.get("snapshot") or {}
    body = snap.get("body") or {}
    if isinstance(body, dict):
        return (body.get("text") or "").strip()
    if isinstance(body, str):
        return body.strip()
    return ""

def extract_cta(item):
    snap = item.get("snapshot") or {}
    return (snap.get("cta_type") or item.get("cta_type") or "").strip() or "(없음)"

def normalize_domain(d):
    if not d:
        return ""
    d = d.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0].split("?")[0].split("#")[0]
    return d

def extract_ad_meta(item):
    snap = item.get("snapshot") or {}
    title = (snap.get("title") or "").strip()
    link_desc = (snap.get("link_description") or "").strip()
    cta_text = (snap.get("cta_text") or "").strip()
    domain = (snap.get("caption") or "").strip()
    link_url = (snap.get("link_url") or "").strip()

    cards = snap.get("cards") or []
    card_links = []
    if cards:
        first = cards[0]
        if not title or title == snap.get("page_name"):
            title = (first.get("title") or title).strip()
        if not link_desc:
            link_desc = (first.get("link_description") or "").strip()
        if not cta_text:
            cta_text = (first.get("cta_text") or "").strip()
        if not link_url:
            link_url = (first.get("link_url") or "").strip()
        for c in cards:
            u = (c.get("link_url") or "").strip()
            if u:
                card_links.append(u)

    return {
        "title": title,
        "link_description": link_desc,
        "cta_text": cta_text,
        "domain": normalize_domain(domain),
        "link_url": link_url,
        "card_links": card_links,
    }

def domain_of(url):
    if not url:
        return ""
    m = re.match(r"https?://([^/?#]+)", url)
    return normalize_domain(m.group(1) if m else "")

def fmt_date(ts):
    if not ts:
        return ""
    try:
        return dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return str(ts)


def build_analysis_md(brand_name_kr, slug, items, query_url, run_id, fmt_counts, processed, analysis_cache=None, utm_samples=None):
    today = dt.datetime.now().strftime("%Y-%m-%d %H:%M KST")

    pages = Counter()
    for it in items:
        snap = it.get("snapshot") or {}
        pn = snap.get("page_name") or it.get("page_name") or "(미상)"
        pages[pn] += 1

    months = Counter()
    starts = []
    for it in items:
        snap = it.get("snapshot") or {}
        ts = snap.get("creation_time") or it.get("start_date")
        d = fmt_date(ts)
        if d:
            months[d[:7]] += 1
            starts.append(d)
    starts.sort()

    cta = Counter(extract_cta(it) for it in items)
    metas = [extract_ad_meta(it) for it in items]
    cta_texts = Counter(m["cta_text"] for m in metas if m["cta_text"])
    domains = Counter()
    for m in metas:
        d = (m["domain"] or domain_of(m["link_url"])).lower()
        if d:
            domains[d] += 1
        for cu in m.get("card_links") or []:
            cd = domain_of(cu).lower()
            if cd and cd != d:
                domains[cd] += 1

    captions = [extract_caption(it) for it in items]
    all_text = "\n".join(captions)
    hashtags = Counter(HASHTAG_RE.findall(all_text))
    words = Counter(
        w for w in KO_WORD_RE.findall(HASHTAG_RE.sub("", all_text))
        if w not in STOPWORDS and len(w) >= 2
    )

    lines = []
    lines.append("---")
    lines.append("file_type: ad-monitor-brand")
    lines.append(f"brand_slug: {slug}")
    lines.append(f"last_updated: {today.split()[0]}")
    lines.append("sources: meta_ad_library_apify_scrape")
    lines.append(f"ad_count: {len(items)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {brand_name_kr} — 광고 소재 분석")
    lines.append("")
    lines.append("> 자동 갱신: `ad_monitor/_scripts/fetch_ads.py` (독립 스킬 — 다른 스킬 산출물 미참조)")
    lines.append("> 매 실행 시 덮어쓰기됩니다.")
    lines.append("")
    lines.append("## 0. 수집 메타")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 광고 카드 수 | {len(items)} |")
    lines.append(f"| 후처리 저장 | 이미지 {processed['images']}장 · 영상 {processed['videos']}개 |")
    lines.append(f"| 수집 일시 | {today} |")
    lines.append(f"| Apify Run | {run_id} |")
    lines.append(f"| Ad Library 쿼리 | {query_url[:90]}... |")
    lines.append(f"| 원본 데이터 | `ad-creatives/metadata.json` |")
    lines.append("")
    lines.append("## 1. 포맷 믹스")
    lines.append("")
    lines.append("| 포맷 | 광고 수 | 비중 |")
    lines.append("|---|---|---|")
    total = sum(fmt_counts.values()) or 1
    for f in ("video", "image", "carousel", "unknown"):
        n = fmt_counts.get(f, 0)
        if n:
            lines.append(f"| {f} | {n} | {n*100//total}% |")
    lines.append("")
    lines.append("## 2. 광고 운영 페이지")
    lines.append("")
    lines.append("| Page Name | 광고 수 |")
    lines.append("|---|---|")
    for name, n in pages.most_common(5):
        lines.append(f"| {name} | {n} |")
    lines.append("")
    lines.append("## 3. 광고 시작일 분포")
    lines.append("")
    if starts:
        lines.append(f"- 가장 빠른 시작: **{starts[0]}**")
        lines.append(f"- 가장 늦은 시작: **{starts[-1]}**")
        lines.append("")
        lines.append("| 월 | 광고 수 |")
        lines.append("|---|---|")
        for m, n in sorted(months.items()):
            lines.append(f"| {m} | {n} |")
    else:
        lines.append("- (시작일 정보 없음)")
    lines.append("")
    lines.append("## 4. CTA 분포")
    lines.append("")
    lines.append("### 4-1. CTA 타입 (Apify cta_type)")
    lines.append("")
    lines.append("| CTA | 횟수 |")
    lines.append("|---|---|")
    for c, n in cta.most_common(10):
        lines.append(f"| {c} | {n} |")
    lines.append("")
    lines.append("### 4-2. CTA 버튼 라벨")
    lines.append("")
    if cta_texts:
        lines.append("| 버튼 라벨 | 횟수 |")
        lines.append("|---|---|")
        for c, n in cta_texts.most_common(15):
            lines.append(f"| {c} | {n} |")
    else:
        lines.append("- (Apify가 cta_text 없음)")
    lines.append("")
    lines.append("## 5. 랜딩 도메인 분포")
    lines.append("")
    if domains:
        total_d = sum(domains.values())
        lines.append("| 도메인 | 광고 수 | 비중 |")
        lines.append("|---|---|---|")
        for d, n in domains.most_common(15):
            lines.append(f"| `{d}` | {n} | {n*100//total_d}% |")
    else:
        lines.append("- (link_url 없음)")
    lines.append("")
    lines.append("## 6. 캡션 키워드 빈도")
    lines.append("")
    lines.append("### 6-1. 해시태그 (상위 15)")
    lines.append("")
    if hashtags:
        for h, n in hashtags.most_common(15):
            lines.append(f"- `{h}` × {n}")
    else:
        lines.append("- (해시태그 없음)")
    lines.append("")
    lines.append("### 6-2. 일반 키워드 (상위 20)")
    lines.append("")
    if words:
        for w, n in words.most_common(20):
            lines.append(f"- `{w}` × {n}")
    else:
        lines.append("- (캡션 없음)")
    lines.append("")
    lines.append("## 7. UTM/트래킹 파라미터 관찰")
    lines.append("")
    lines.append(utm_pattern.format_utm_section_md(brand_name_kr, slug, utm_samples or []))
    lines.append("## 8. 광고 카드 전수 (시작일 내림차순)")
    lines.append("")
    by_date = sorted(
        items,
        key=lambda it: ((it.get("snapshot") or {}).get("creation_time") or it.get("start_date") or 0),
        reverse=True,
    )
    for i, it in enumerate(by_date, 1):
        ad_id = str(it.get("ad_archive_id") or it.get("adArchiveID") or it.get("id") or f"item{i:03d}")
        snap = it.get("snapshot") or {}
        date = fmt_date(snap.get("creation_time") or it.get("start_date"))
        fmt = "video" if (snap.get("videos")) else ("carousel" if snap.get("cards") else ("image" if snap.get("images") else "unknown"))
        cta_v = extract_cta(it)
        cap = extract_caption(it).replace("\n", " ").strip()
        cap_preview = (cap[:140] + "…") if len(cap) > 140 else cap
        meta = extract_ad_meta(it)
        lines.append(f"### #{i} · `{ad_id}` · {date} · {fmt} · CTA={cta_v}")
        if meta["title"]:
            lines.append(f"- **광고 제목**: {meta['title']}")
        if meta["link_description"]:
            lines.append(f"- **링크 설명**: {meta['link_description']}")
        if meta["cta_text"]:
            lines.append(f"- **CTA 버튼**: {meta['cta_text']}")
        if meta["link_url"]:
            d = (meta["domain"] or domain_of(meta["link_url"]))
            lines.append(f"- **랜딩**: {d} → [{meta['link_url'][:90]}{'…' if len(meta['link_url']) > 90 else ''}]({meta['link_url']})")
        if cap_preview:
            lines.append(f"> {cap_preview}")

        if analysis_cache and ad_id in analysis_cache:
            entry = analysis_cache[ad_id]
            a = entry.get("analysis") or {}
            # USP 3 항목 + Creative Key Visual + ad_pattern (구 stages 호환)
            analysis = a.get("analysis") or a.get("stages") or {}
            ad_pattern = a.get("ad_pattern") or ""
            # 구 키 → 신 키 매핑 (기존 분석 결과 호환)
            legacy_map = {"problem": "users_problem", "evidence": "solution",
                          "hook_image": "creative_key_visual", "cta": "promotion"}
            merged = dict(analysis)
            for old_k, new_k in legacy_map.items():
                if analysis.get(old_k) and not merged.get(new_k):
                    merged[new_k] = analysis[old_k]

            if a.get("error"):
                lines.append(f"- ⚠️ Gemini 분석 실패: {a['error']}")
            else:
                if merged or ad_pattern:
                    lines.append("- **USP 3 항목 + Creative Key Visual:**")
                    if ad_pattern:
                        pattern_label = {
                            "default": "🎯 default (페인 후킹)",
                            "trust_anchor": "🏆 trust_anchor (신뢰 자산 강조)",
                            "promotion_anchor": "💰 promotion_anchor (할인 BOFU)",
                            "hybrid": "🔀 hybrid (결합)",
                        }.get(ad_pattern, ad_pattern)
                        lines.append(f"  - **ad_pattern**: {pattern_label}")
                    for k, label in (("users_problem", "1. User's Problem"),
                                     ("solution", "2. Solution"),
                                     ("promotion", "3. Promotion"),
                                     ("creative_key_visual", "★ Creative Key Visual")):
                        v = merged.get(k)
                        if v:
                            lines.append(f"  - **{label}**: {v}")
                if fmt == "video":
                    summ = a.get("analysis_summary") or {}
                    story = a.get("full_storyline") or ""
                    if summ:
                        lines.append(f"- **Hook**: {summ.get('hook_type', '?')}")
                        lines.append(f"- **구조**: {summ.get('structure_type', '?')} · 스타일: {summ.get('video_style', '?')}")
                        if summ.get('key_strengths'):
                            ks = summ['key_strengths'] if isinstance(summ['key_strengths'], list) else [summ['key_strengths']]
                            lines.append(f"- **강점**: {' / '.join(str(x) for x in ks[:3])}")
                    if story:
                        preview = story[:300] + ("…" if len(story) > 300 else "")
                        lines.append(f"- **스토리라인**: {preview}")
                elif fmt in ("image", "carousel"):
                    if a.get("main_copy"): lines.append(f"- **메인 카피**: {a['main_copy']}")
                    if a.get("sub_copy"): lines.append(f"- **서브 카피**: {a['sub_copy']}")
                    if a.get("cta"): lines.append(f"- **CTA 카피**: {a['cta']}")
                    if a.get("layout_style"): lines.append(f"- **레이아웃**: {a['layout_style']}")
                    if a.get("color_mood"): lines.append(f"- **컬러 무드**: {a['color_mood']}")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────── 트렌드 분석 helpers ────────────────────────

# 메시지 각도 라벨 — keyword 패턴 → angle label
MESSAGE_ANGLES = [
    ("단기간 효과 (X일·X주·X시간)", [r"\d+\s*(?:일|주|시간|분|초|개월)", r"즉각", r"즉시", r"단\s*\d+\s*(?:일|주|회)"]),
    ("임상 수치·% 강조", [r"임상", r"\d+\s*%(?!\s*OFF)", r"\d+\s*배", r"등급", r"테스트"]),
    ("권위·랭킹 (1위·인증)", [r"1\s*위", r"올리브영", r"네이버\s*1", r"베스트", r"BEST", r"NO\.?\s*1", r"랭킹", r"인증"]),
    ("저자극·민감성", [r"저자극", r"민감", r"순한", r"진정", r"수딩", r"트러블"]),
    ("가격 할인 (%·원)", [r"%\s*OFF", r"\d+\s*%\s*할인", r"특가", r"세일"]),
    ("1+1·증정", [r"1\s*\+\s*1", r"\d+\s*\+\s*\d+", r"증정", r"GIFT", r"사은품"]),
    ("한정·시급성", [r"한정", r"마감", r"D-?\s*\d", r"오늘", r"마지막", r"지금만"]),
    ("리스크 제거 (환불·체험)", [r"환불", r"체험", r"무료\s*배송", r"교환", r"반품", r"보장"]),
    ("성분·기능 (수분·보습·미백)", [r"수분", r"보습", r"광채", r"미백", r"주름", r"탄력"]),
    ("자연주의·비건·천연", [r"비건", r"천연", r"유기농", r"내추럴", r"plant", r"vegan"]),
]


def _to_str_safe(v):
    """list/str/None 안전 변환 (carousel 광고는 sub_copy 가 list)."""
    if v is None: return ""
    if isinstance(v, list): return " · ".join(str(x) for x in v if x)
    return str(v)


def _extract_usp_dict(entry):
    """nested analysis → top-level → stages 폴백 순으로 USP 3 항목 추출."""
    a = (entry or {}).get("analysis") or {}
    nested = a.get("analysis") if isinstance(a.get("analysis"), dict) else None
    if nested and ("users_problem" in nested or "solution" in nested):
        return nested
    if "users_problem" in a or "solution" in a:
        return {k: a.get(k) for k in ("users_problem", "solution", "promotion", "creative_key_visual")}
    stages = a.get("stages") or {}
    if stages:
        return {
            "users_problem": stages.get("problem"),
            "solution": stages.get("evidence"),
            "promotion": stages.get("cta"),
            "creative_key_visual": stages.get("hook_image"),
        }
    return {}


def _count_ad_patterns(cache):
    c = Counter()
    for entry in (cache or {}).values():
        a = (entry or {}).get("analysis") or {}
        ap = (a.get("ad_pattern") or "?").strip() or "?"
        c[ap] += 1
    return c


def _ad_text_blob(entry, item=None):
    """광고 1건의 모든 텍스트를 한 문자열로 합쳐 반환 (각도 매칭용)."""
    a = (entry or {}).get("analysis") or {}
    parts = []
    for k in ("main_copy", "sub_copy", "cta", "feature_desc", "empathy_copy", "all_text_extracted"):
        v = _to_str_safe(a.get(k))
        if v: parts.append(v)
    if item is not None:
        cap = extract_caption(item) or ""
        if cap: parts.append(cap)
    return " ".join(parts)


def _message_angle_matrix(brands_data):
    """브랜드 × 메시지 각도 매트릭스. angle 별 매칭 광고 수."""
    labels = [lbl for lbl, _ in MESSAGE_ANGLES]
    result = {}
    for b in brands_data:
        cache = b.get("cache") or {}
        item_by_id = {}
        for i, it in enumerate(b.get("items") or []):
            aid = str(it.get("ad_archive_id") or it.get("adArchiveID") or it.get("id") or f"item{i:03d}")
            item_by_id[aid] = it
        counts = {lbl: 0 for lbl in labels}
        for ad_id, entry in cache.items():
            blob = _ad_text_blob(entry, item_by_id.get(ad_id))
            for lbl, patterns in MESSAGE_ANGLES:
                if any(re.search(p, blob) for p in patterns):
                    counts[lbl] += 1
        result[b["slug"]] = counts
    return labels, result


def _split_traits(s):
    """color/visual/layout 문자열을 ',·/+;' 로 분할 후 정규화."""
    if not s: return []
    parts = re.split(r"[,，·/+;]", str(s))
    out = []
    for p in parts:
        t = p.strip()
        if 3 <= len(t) <= 60:
            out.append(t)
    return out


def _top_visual_traits(brands_data):
    color = Counter(); visual = Counter(); layout = Counter()
    for b in brands_data:
        for entry in (b.get("cache") or {}).values():
            a = (entry or {}).get("analysis") or {}
            for t in _split_traits(a.get("color_mood", "")): color[t] += 1
            for t in _split_traits(a.get("visual_style", "")): visual[t] += 1
            for t in _split_traits(a.get("layout_style", "")): layout[t] += 1
    return color.most_common(6), visual.most_common(6), layout.most_common(6)


def _extract_cta_library(brands_data):
    """브랜드별 CTA 문구 라이브러리 — 버튼 / 가격 혜택 / 리스크 제거."""
    PRICE_PAT = re.compile(r"(\d+\s*%\s*OFF|\d+\s*%\s*할인|\d+\s*\+\s*\d+|\d{1,3}(?:,\d{3})*\s*원|특가|증정)")
    RISK_PAT = re.compile(r"(환불|체험|보장|교환|반품|무료\s*배송)")
    rows = []
    for b in brands_data:
        items = b.get("items") or []
        cache = b.get("cache") or {}
        cta_buttons = Counter(extract_ad_meta(it)["cta_text"] for it in items if extract_ad_meta(it)["cta_text"])
        top_btn = cta_buttons.most_common(1)
        button = f"{top_btn[0][0]} ({top_btn[0][1]})" if top_btn else "-"
        prices = Counter(); risks = Counter()
        for entry in cache.values():
            a = (entry or {}).get("analysis") or {}
            for k in ("cta", "main_copy", "sub_copy", "all_text_extracted"):
                v = _to_str_safe(a.get(k))
                if not v: continue
                for m in PRICE_PAT.findall(v): prices[m.strip()] += 1
                for m in RISK_PAT.findall(v): risks[m.strip()] += 1
        rows.append({
            "brand": b["brand_name_kr"],
            "button": button,
            "price_offer": " / ".join(f"{k}({n})" for k, n in prices.most_common(3)) or "-",
            "risk_relief": " / ".join(f"{k}({n})" for k, n in risks.most_common(3)) or "-",
        })
    return rows


def _angle_coverage_summary(matrix_labels, matrix):
    """브랜드 간 메시지 각도 커버리지 — '자사' 가정 없이, 전체 0건/저점유 앵글만 나열."""
    zero_angles = [lbl for lbl in matrix_labels if all(matrix[s].get(lbl, 0) == 0 for s in matrix)]
    low_angles = [
        (lbl, sum(matrix[s].get(lbl, 0) for s in matrix))
        for lbl in matrix_labels
        if not all(matrix[s].get(lbl, 0) == 0 for s in matrix)
    ]
    low_angles.sort(key=lambda x: x[1])
    low_top3 = [lbl for lbl, _ in low_angles[:3]]

    out = ["**추적 중인 브랜드 전체가 0건인 메시지 각도:**"]
    if zero_angles:
        for a in zero_angles: out.append(f"- {a}")
    else:
        out.append("- (없음 — 모든 각도를 최소 1개 브랜드가 점유)")
    out.append("")
    out.append("**점유율 최하위 angle Top 3 (저점유):**")
    for lbl in low_top3: out.append(f"- {lbl}")
    out.append("")
    out.append(
        "> ℹ️ 이 독립 스킬은 \"자사 vs 경쟁사\" 구도를 가정하지 않습니다. 특정 브랜드가 자사라면, "
        "위 커버리지와 자사 브랜드의 실제 소구점을 직접 비교해 차별화 여지를 판단하세요."
    )
    return "\n".join(out)


# ──────────────────────── 통합 트렌드 리포트 ────────────────────────

def build_trend_report(brands_data):
    """브랜드별 분석 데이터를 통합 리포트로 합성 (자사/경쟁사 구분 없음).

    brands_data: [{slug, brand_name_kr, items, cache}]
    """
    today = dt.datetime.now().strftime("%Y-%m-%d %H:%M KST")
    out = []
    out.append("---")
    out.append("file_type: ad-monitor-trend")
    out.append(f"last_updated: {today.split()[0]}")
    out.append(f"brand_count: {len(brands_data)}")
    out.append("---")
    out.append("")
    out.append("# 광고 모니터링 트렌드 (전체 통합, 독립 스킬)")
    out.append("")
    out.append(f"> 자동 갱신 — {today}")
    out.append("> 매 실행 시 덮어쓰기됩니다. `Claudecode_MarketingOS_student` 프로젝트의 다른 스킬 산출물과 독립적입니다.")
    out.append("")

    # ── § 1. 분석 대상 ──
    out.append("## 1. 분석 대상")
    out.append("")
    out.append("| 슬러그 | 브랜드 | 활성 광고 수 | 마지막 분석 | ad_pattern 분포 |")
    out.append("|---|---|---|---|---|")
    for b in brands_data:
        cache = b.get("cache") or {}
        patterns = _count_ad_patterns(cache)
        pat_str = " / ".join(f"{k}={v}" for k, v in patterns.most_common()) or "-"
        last_ts = ""
        for entry in cache.values():
            ts = entry.get("analyzed_at", "")
            if ts and ts > last_ts: last_ts = ts
        last_str = last_ts.split("T")[0] if last_ts else "-"
        out.append(f"| {b['slug']} | **{b['brand_name_kr']}** | {len(b.get('items') or [])} | {last_str} | {pat_str} |")
    out.append("")

    # ── § 2. 강조 메시지 매트릭스 ──
    out.append("## 2. 강조 메시지 매트릭스 (브랜드 × 메시지 각도)")
    out.append("")
    out.append("> 광고 1건의 통합 텍스트에서 angle keyword 매칭 → 점유 광고 수. ✅ N건 / — 0건.")
    out.append("")
    labels, matrix = _message_angle_matrix(brands_data)
    header = "| 메시지 각도 | " + " | ".join(b["brand_name_kr"] for b in brands_data) + " |"
    sep = "|---|" + "---|" * len(brands_data)
    out.append(header); out.append(sep)
    for lbl in labels:
        cells = []
        for b in brands_data:
            n = matrix[b["slug"]].get(lbl, 0)
            cells.append(f"✅ {n}건" if n else "—")
        out.append(f"| {lbl} | " + " | ".join(cells) + " |")
    out.append("")

    # ── § 3. ad_pattern 분포 ──
    out.append("## 3. ad_pattern 분포 (광고 유형별 비율)")
    out.append("")
    total_patterns = Counter()
    for b in brands_data:
        for k, v in _count_ad_patterns(b.get("cache") or {}).items():
            total_patterns[k] += v
    total = sum(total_patterns.values()) or 1
    out.append("| ad_pattern | 건수 | 비율 |")
    out.append("|---|---|---|")
    for k in ("default", "trust_anchor", "promotion_anchor", "hybrid"):
        n = total_patterns.get(k, 0)
        out.append(f"| `{k}` | {n} | {n/total*100:.0f}% |")
    other = sum(v for k, v in total_patterns.items() if k not in ("default", "trust_anchor", "promotion_anchor", "hybrid"))
    if other:
        out.append(f"| (기타) | {other} | {other/total*100:.0f}% |")
    out.append("")

    # ── § 4. USP 3 항목 가로 비교 ──
    out.append("## 4. USP 3 항목 + Creative Key Visual — 브랜드 가로 비교")
    out.append("")
    out.append("> USP 분석법 (User's Problem · Solution · Promotion + Creative Key Visual) 으로 분해된 결과를 항목별 가로 비교. 브랜드별 상위 3개 인용.")
    out.append("")
    stage_keys = [
        ("users_problem", "4-1. User's Problem (공감언어·상황)"),
        ("solution", "4-2. Solution (USP·RTB·결과 시각화)"),
        ("promotion", "4-3. Promotion (가격·리스크·시급성)"),
        ("creative_key_visual", "4-★. Creative Key Visual (핵심 비주얼)"),
    ]
    for key, label in stage_keys:
        out.append(f"### {label}")
        out.append("")
        for b in brands_data:
            cache = b.get("cache") or {}
            samples = []
            seen = set()
            for entry in cache.values():
                usp = _extract_usp_dict(entry)
                v = _to_str_safe(usp.get(key)).strip()
                if not v or v in seen: continue
                seen.add(v)
                samples.append(v)
                if len(samples) >= 3: break
            out.append(f"**{b['brand_name_kr']}** —")
            if samples:
                for s in samples: out.append(f"- {s}")
            else:
                out.append("- (분석 결과 없음)")
            out.append("")

    # ── § 5. 카피라이팅 Top 인용 (압축) ──
    out.append("## 5. 카피라이팅 Top 인용 (브랜드별 상위 5개)")
    out.append("")
    out.append("> 광고 카피 raw 덤프 ❌. 브랜드별 메인 카피 중복 제거 후 상위 5개만 인용. 전체는 `{slug}/ad-creatives.md` 참고.")
    out.append("")
    for b in brands_data:
        out.append(f"### {b['brand_name_kr']} ({b['slug']})")
        cache = b.get("cache") or {}
        items = b.get("items") or []
        item_by_id = {}
        for i, it in enumerate(items):
            aid = str(it.get("ad_archive_id") or it.get("adArchiveID") or it.get("id") or f"item{i:03d}")
            item_by_id[aid] = it
        seen = set()
        count = 0
        for ad_id, entry in cache.items():
            if count >= 5: break
            a = (entry or {}).get("analysis") or {}
            mc = _to_str_safe(a.get("main_copy")).strip().replace("\n", " ")
            if not mc or mc in seen: continue
            seen.add(mc)
            count += 1
            cta_copy = _to_str_safe(a.get("cta")).strip().replace("\n", " ")
            meta = extract_ad_meta(item_by_id.get(ad_id, {}))
            out.append(f"- 📌 **{mc[:80]}** — CTA: {meta.get('cta_text', '-')} / 카피 보조: {cta_copy[:60]}")
        if count == 0:
            out.append("- (분석된 카피 없음)")
        out.append("")

    # ── § 6. CTA 문구 라이브러리 ──
    out.append("## 6. CTA 문구 라이브러리 (브랜드별)")
    out.append("")
    out.append("| 브랜드 | 대표 버튼 | 가격 혜택 (Top 3) | 리스크 제거 (Top 3) |")
    out.append("|---|---|---|---|")
    for row in _extract_cta_library(brands_data):
        out.append(f"| {row['brand']} | {row['button']} | {row['price_offer']} | {row['risk_relief']} |")
    out.append("")

    # ── § 7. 시각 패턴 트렌드 ──
    out.append("## 7. 시각 패턴 트렌드 (컬러·비주얼·레이아웃)")
    out.append("")
    color_top, visual_top, layout_top = _top_visual_traits(brands_data)
    out.append("**컬러 무드 — 자주 등장하는 토큰 Top 6:**")
    for t, n in color_top: out.append(f"- {t} ({n}건)")
    if not color_top: out.append("- (분석 데이터 없음)")
    out.append("")
    out.append("**비주얼 스타일 Top 6:**")
    for t, n in visual_top: out.append(f"- {t} ({n}건)")
    if not visual_top: out.append("- (분석 데이터 없음)")
    out.append("")
    out.append("**레이아웃 Top 6:**")
    for t, n in layout_top: out.append(f"- {t} ({n}건)")
    if not layout_top: out.append("- (분석 데이터 없음)")
    out.append("")

    # ── § 8. 메시지 각도 커버리지 (자사/경쟁사 가정 없음) ──
    out.append("## 8. 메시지 각도 커버리지")
    out.append("")
    out.append(_angle_coverage_summary(labels, matrix))
    out.append("")

    # ── § 9. UTM/트래킹 파라미터 관찰 (브랜드별) ──
    out.append("## 9. UTM/트래킹 파라미터 관찰 (브랜드별) — 캠페인/그룹/소재명 규칙 추정용 원본")
    out.append("")
    out.append(
        "> ★ 아래는 랜딩 URL 을 그대로 파싱한 **관찰 데이터**입니다. \"규칙이 이렇다\"고 단정하지 않습니다 — "
        "실제 명명 규칙 추정(캠페인명/그룹명/소재명 인코딩 패턴)은 이 표를 근거로 Claude 가 매 실행 시 채팅에 "
        "베스트에포트로 제시합니다 (SKILL.md Step 7). 경쟁사는 리다이렉트·클릭ID 만 있고 utm 값 자체가 없는 "
        "경우가 흔해 정확도가 낮을 수 있습니다."
    )
    out.append("")
    for b in brands_data:
        samples = utm_pattern.extract_utm_samples(b.get("items") or [])
        out.append(utm_pattern.format_utm_section_md(b["brand_name_kr"], b["slug"], samples))

    # ── § 10. 다음 모니터링 트리거 ──
    out.append("## 10. 다음 모니터링 트리거")
    out.append("")
    out.append("- [ ] 신규 활성 광고 5건 이상 → `python3 ad_monitor/_scripts/fetch_ads.py` 재실행")
    out.append("- [ ] 새 키워드 / angle 등장 → 매트릭스 업데이트")
    out.append("- [ ] 기존 광고 절반 이상 비활성 → 직전 트렌드와 diff 비교")
    out.append("")

    return "\n".join(out)


# ──────────────────────── 브랜드 처리 ────────────────────────

def fetch_brand(token, actor, slug, brand_name_kr, ad_library_url, max_ads, gemini_key=None, rpm_delay=4.0,
                inputs_dir=None, auto_seed=False, gemini_tier="free", group=""):
    """단일 브랜드 크롤 + 분석 + 보고서 생성.

    auto_seed=True: slug 가 비어있는 URL-only 흐름. 첫 크롤 후 page_name 으로 slug 도출.
    """
    print(f"\n=== {slug or '(URL-only)'} ===")
    print(f"  Ad Library: {ad_library_url[:80]}...")
    charged = max(max_ads, 10)
    actor_input = {
        "urls": [{"url": ad_library_url}],
        "count": charged,
        "maxItems": charged,
        "scrapeAdDetails": True,
    }
    run = run_actor(token, actor, actor_input)
    print(f"  Run ID: {run['id']}")
    final = wait_run(token, run["id"])
    if final["status"] != "SUCCEEDED":
        print(f"  ⚠️ 상태: {final['status']} — 스킵")
        return None

    items = get_items(token, final["defaultDatasetId"])
    if items and isinstance(items[0], dict) and "error" in items[0] and len(items) == 1:
        print(f"  ⚠️ 액터 에러: {items[0]['error']}")
        return None
    items = items[:max_ads]
    print(f"  광고 카드 수신: {len(items)}")

    # URL-only 흐름: page_name 에서 slug 자동 도출 + 시드 .md 자동 생성
    if auto_seed and items:
        snap0 = (items[0].get("snapshot") or {})
        page_name = snap0.get("page_name") or items[0].get("page_name") or ""
        derived_slug = slugify(page_name)
        if not slug or slug == "(URL-only)":
            slug = derived_slug
        if not brand_name_kr:
            brand_name_kr = page_name or derived_slug
        print(f"  자동 슬러그: {slug}  (page_name='{page_name}')")
        seed_path = write_seed_md(slug, brand_name_kr, ad_library_url, group=group, inputs_dir=inputs_dir)
        if seed_path:
            print(f"  시드 자동 생성: {seed_path.relative_to(ROOT)}")

    if not slug:
        print("  ⚠️ slug 도출 실패 — 스킵")
        return None

    out_dir = BRANDS_ROOT / slug / "ad-creatives"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    analysis_path = out_dir / "analysis.json"
    cache = {}
    if analysis_path.exists():
        try:
            cache = json.loads(analysis_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    fmt_counts = Counter()
    processed = {"images": 0, "videos": 0}
    media_index = {}

    for i, item in enumerate(items):
        ad_id = str(
            item.get("ad_archive_id")
            or item.get("adArchiveID")
            or item.get("id")
            or f"item{i:03d}"
        )
        fmt, img_urls, vid_urls = classify_and_extract(item)
        fmt_counts[fmt] += 1

        img_files, vid_files = [], []
        for j, u in enumerate(img_urls[:3]):
            ext = ".png" if ".png" in u.lower() else ".jpg"
            dest = out_dir / "images" / f"{ad_id}_{j}{ext}"
            if download(u, dest) or dest.exists():
                processed["images"] += 1
                img_files.append(dest)
        for j, u in enumerate(vid_urls[:1]):
            dest = out_dir / "videos" / f"{ad_id}_{j}.mp4"
            if download(u, dest) or dest.exists():
                processed["videos"] += 1
                vid_files.append(dest)

        media_index[ad_id] = {"format": fmt, "image_files": img_files, "video_files": vid_files}

    # Gemini 분석
    if gemini_key:
        tier_label = "유료" if gemini_tier == "paid" else "무료(250 RPD)"
        print(f"  Gemini 분석 시작 (모델: {GEMINI_MODEL}, 분당 ~{int(60/rpm_delay)}건, 키 등급: {tier_label})")
        analyzed = 0
        skipped = 0
        quota_hit = False
        for ad_id, mi in media_index.items():
            # 이미 성공적으로 분석된 광고는 스킵
            if ad_id in cache and "analysis" in cache[ad_id] and cache[ad_id].get("status") != "quota_exceeded":
                skipped += 1
                continue
            fmt = mi["format"]
            try:
                if fmt == "video" and mi["video_files"]:
                    result = gemini_analyze_video(gemini_key, mi["video_files"][0])
                elif fmt in ("image", "carousel") and mi["image_files"]:
                    result = gemini_analyze_image(gemini_key, mi["image_files"][0])
                else:
                    continue
                # parse_failed 같은 부분 실패는 status=failed 로 마킹
                status = "failed" if (isinstance(result, dict) and result.get("error")) else "success"
                cache[ad_id] = {
                    "format": fmt,
                    "analyzed_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "model": GEMINI_MODEL,
                    "status": status,
                    "analysis": result,
                }
                analyzed += 1
                if analyzed % 5 == 0:
                    print(f"    · 진행: {analyzed} 분석 완료")
                analysis_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                time.sleep(rpm_delay)
            except GeminiQuotaExceeded as e:
                # 무료 한도 도달 → 이 광고만 quota_exceeded 로 마킹하고 루프 종료
                cache[ad_id] = {
                    "format": fmt,
                    "attempted_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "model": GEMINI_MODEL,
                    "status": "quota_exceeded",
                    "error": str(e),
                }
                analysis_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                quota_hit = True
                remaining = len(media_index) - analyzed - skipped - 1
                print(f"\n  🚫 Gemini 무료 한도 도달 — {ad_id} 에서 중단")
                print(f"     · 분석 완료: {analyzed} 건 · 캐시 스킵: {skipped} 건 · 미분석: {remaining} 건")
                print(f"  💡 다음 단계 (택1):")
                print(f"     ① 24시간 후 같은 명령 재실행 → 무료 한도 리셋 후 미분석 광고만 이어서 분석")
                print(f"     ② 즉시 완료가 필요하면: ad_monitor/.env 에 GEMINI_API_KEY_PAID=AQ... 추가 후 `--paid` 플래그로 재실행")
                break
            except Exception as e:
                print(f"    ⚠️ {ad_id} 분석 실패: {e}")
                cache[ad_id] = {
                    "format": fmt,
                    "attempted_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "model": GEMINI_MODEL,
                    "status": "failed",
                    "error": str(e)[:300],
                }
                analysis_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        if not quota_hit:
            print(f"  Gemini 완료: 신규 {analyzed}건 · 캐시 스킵 {skipped}건")

    analysis_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    utm_samples = utm_pattern.extract_utm_samples(items)
    utm_pattern.save_samples_json(out_dir / "utm_samples.json", utm_samples)

    md_text = build_analysis_md(
        brand_name_kr=brand_name_kr,
        slug=slug,
        items=items,
        query_url=ad_library_url,
        run_id=run["id"],
        fmt_counts=fmt_counts,
        processed=processed,
        analysis_cache=cache,
        utm_samples=utm_samples,
    )
    md_path = BRANDS_ROOT / slug / "ad-creatives.md"
    md_path.write_text(md_text, encoding="utf-8")

    print(f"  포맷 분류: {dict(fmt_counts)}")
    print(f"  저장: 이미지 {processed['images']}장 · 영상 {processed['videos']}개")
    print(f"  분석 보고서: {md_path.relative_to(ROOT.parent)}")

    return {"slug": slug, "brand_name_kr": brand_name_kr, "items": items, "cache": cache}


# ──────────────────────── main ────────────────────────

def rebuild_md_only(slug, brand_name_kr):
    base = BRANDS_ROOT / slug / "ad-creatives"
    meta_path = base / "metadata.json"
    if not meta_path.exists():
        print(f"  · {slug}: metadata.json 없음 — 스킵")
        return None
    items = json.loads(meta_path.read_text(encoding="utf-8"))
    cache = {}
    ap = base / "analysis.json"
    if ap.exists():
        try:
            cache = json.loads(ap.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    fmt_counts = Counter()
    processed = {"images": 0, "videos": 0}
    for it in items:
        snap = it.get("snapshot") or {}
        if snap.get("videos"):
            fmt_counts["video"] += 1
        elif snap.get("cards"):
            fmt_counts["carousel"] += 1
        elif snap.get("images"):
            fmt_counts["image"] += 1
        else:
            fmt_counts["unknown"] += 1
    img_dir = base / "images"
    vid_dir = base / "videos"
    if img_dir.exists():
        processed["images"] = sum(1 for _ in img_dir.iterdir() if _.is_file())
    if vid_dir.exists():
        processed["videos"] = sum(1 for _ in vid_dir.iterdir() if _.is_file())

    utm_samples = utm_pattern.extract_utm_samples(items)
    utm_pattern.save_samples_json(base / "utm_samples.json", utm_samples)

    md_text = build_analysis_md(
        brand_name_kr=brand_name_kr, slug=slug, items=items,
        query_url="(re-build)", run_id="(rebuild)",
        fmt_counts=fmt_counts, processed=processed, analysis_cache=cache,
        utm_samples=utm_samples,
    )
    md_path = BRANDS_ROOT / slug / "ad-creatives.md"
    md_path.write_text(md_text, encoding="utf-8")
    print(f"  · {slug}: ad-creatives.md 재생성 (광고 {len(items)}건)")
    return {"slug": slug, "brand_name_kr": brand_name_kr, "items": items, "cache": cache}


def main():
    parser = argparse.ArgumentParser(
        description="ad-monitor 독립 스킬 — Apify 로 메타 광고 소재 수집 + Gemini 분석 (URL 1개로 시작, 자사/경쟁사 구분 없음)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        help=(
            "Meta Ad Library URL (https://...) 또는 기존 시드 슬러그 (예: brand-a). "
            "생략 시 _inputs/*.md 전체 일괄 처리."
        ),
    )
    parser.add_argument("--max", type=int, default=30, help="브랜드당 최대 광고 수 (기본 30)")
    parser.add_argument("--no-gemini", action="store_true", help="Gemini 분석 스킵")
    parser.add_argument("--md-only", action="store_true", help="기존 metadata/analysis로 md만 재생성")
    parser.add_argument("--rpm", type=float, default=4.0, help="Gemini 호출 간격(초) — 기본 4")
    parser.add_argument("--paid", action="store_true",
                        help="유료 Gemini 키 사용 (GEMINI_API_KEY_PAID). 기본은 무료 키(GEMINI_API_KEY 또는 GEMINI_API_KEY_FREE)")
    args = parser.parse_args()

    # 1) target 분기
    target = (args.target or "").strip()
    is_url = target.lower().startswith(("http://", "https://"))

    rows = []          # 일괄·슬러그 흐름 입력
    url_targets = []   # URL-only 흐름 입력 [(url, slug_or_None, brand_kr_or_None, group)]

    if is_url:
        url_targets.append((target, None, None, ""))
    elif target:
        # 슬러그
        row = load_brand(target, inputs_dir=INPUTS_DIR)
        if not row:
            sys.exit(f"slug 매칭 없음: _inputs/{target}.md 가 없습니다")
        rows = [row]
    else:
        # 통합 입력 파일 우선 (사용자가 편집하는 유일한 파일)
        combined = load_combined_brands()
        if combined:
            print(f"통합 입력 파일 사용: {COMBINED_INPUT.relative_to(ROOT)} ({len(combined)}개 URL)")
            for c in combined:
                # notes 의 첫 토큰을 brand_kr 힌트로 (예: "메디큐브 — PDRN..." → "메디큐브")
                kr_hint = ""
                if c["notes"]:
                    kr_hint = re.split(r"[—\-–·/(]", c["notes"], maxsplit=1)[0].strip()
                url_targets.append((c["url"], None, kr_hint or None, c.get("group", "")))
        else:
            rows = load_brands(inputs_dir=INPUTS_DIR)

        if not rows and not url_targets:
            sys.exit(
                f"입력 없음: {COMBINED_INPUT.relative_to(ROOT)} 에 URL 을 적거나, "
                f"URL 을 직접 인자로 넘기세요.\n"
                f"  예) python3 fetch_ads.py 'https://www.facebook.com/ads/library/?...&view_all_page_id=123'"
            )

    # 2) md-only 분기 — 브랜드별 ad-creatives.md + 통합 ads_report.md 동시 재생성
    if args.md_only:
        seen_slugs = set()
        rebuild_targets = []  # [(slug, brand_kr)]
        for r in rows:
            slug = r["brand_slug"]
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                rebuild_targets.append((slug, r["brand_name_kr"]))
        for meta_path in BRANDS_ROOT.glob("*/ad-creatives/metadata.json"):
            slug = meta_path.parent.parent.name
            if slug.startswith("_") or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            seed_row = load_brand(slug, inputs_dir=INPUTS_DIR)
            kr = (seed_row or {}).get("brand_name_kr") or slug
            rebuild_targets.append((slug, kr))

        brands_data = []
        for slug, kr in rebuild_targets:
            entry = rebuild_md_only(slug, kr)
            if entry:
                brands_data.append(entry)

        if brands_data:
            trend_md = build_trend_report(brands_data)
            trend_path = BRANDS_ROOT / "ads_report.md"
            trend_path.write_text(trend_md, encoding="utf-8")
            print(f"\n통합 트렌드 리포트: {trend_path.relative_to(ROOT.parent)}")
        print("\n완료 (md 재생성).")
        return

    # 3) 환경 변수
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        sys.exit(
            "APIFY_TOKEN 이 없습니다.\n"
            "  ad_monitor/.env 에 한 줄 추가 → APIFY_TOKEN=apify_api_...\n"
            "  발급: https://console.apify.com/settings/integrations"
        )
    actor = os.environ.get("APIFY_ACTOR", "curious_coder~facebook-ads-library-scraper").strip()

    gemini_key = None
    gemini_tier = "free"
    if not args.no_gemini:
        if args.paid:
            gemini_key = os.environ.get("GEMINI_API_KEY_PAID", "").strip() \
                or os.environ.get("GEMINI_API_KEY", "").strip()
            gemini_tier = "paid"
            if not gemini_key:
                sys.exit(
                    "--paid 플래그 사용 시 GEMINI_API_KEY_PAID 가 필요합니다.\n"
                    "  ad_monitor/.env 에 한 줄 추가 → GEMINI_API_KEY_PAID=AQ..."
                )
        else:
            gemini_key = os.environ.get("GEMINI_API_KEY_FREE", "").strip() \
                or os.environ.get("GEMINI_API_KEY", "").strip()
            gemini_tier = "free"
        if not gemini_key:
            print("⚠️ Gemini 키가 없어 분석은 스킵하고 수집만 진행합니다.")
            print("   ad_monitor/.env 에 GEMINI_API_KEY_FREE=AQ... (무료) 또는 GEMINI_API_KEY=AQ... 한 줄 추가")

    print(f"\nApify 액터: {actor}")
    print(f"브랜드: {len(rows)}개 (시드) + {len(url_targets)}개 (URL-only) · 브랜드당 최대 {args.max}개")

    brands_data = []  # 트렌드 리포트용

    # 4) URL-only 흐름
    for url, slug, kr, group in url_targets:
        try:
            res = fetch_brand(
                token, actor, slug or "", kr or "", url, args.max,
                gemini_key=gemini_key, rpm_delay=args.rpm,
                inputs_dir=INPUTS_DIR, auto_seed=True, gemini_tier=gemini_tier,
                group=group or "",
            )
            if res:
                brands_data.append(res)
        except Exception as e:
            print(f"  ❌ URL 처리 실패: {e}")

    # 5) 시드 슬러그 흐름
    for r in rows:
        url = first_url(r["meta_ad_library_link"])
        slug = r["brand_slug"]
        kr = r["brand_name_kr"]
        if not url:
            print(f"\n=== {slug} === (skip — Meta Ad Library URL 비어있음)")
            continue
        try:
            res = fetch_brand(
                token, actor, slug, kr, url, args.max,
                gemini_key=gemini_key, rpm_delay=args.rpm,
                gemini_tier=gemini_tier, group=r.get("group", ""),
            )
            if res:
                brands_data.append(res)
        except Exception as e:
            print(f"  ❌ {slug} 실패: {e}")

    # 6) 통합 트렌드 리포트 (모든 시드 + URL 합산)
    if brands_data:
        all_rows = load_brands(inputs_dir=INPUTS_DIR)
        seen = {b["slug"] for b in brands_data}
        for r in all_rows:
            if r["brand_slug"] in seen:
                continue
            base = BRANDS_ROOT / r["brand_slug"] / "ad-creatives"
            meta_path = base / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                items = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            cache = {}
            ap = base / "analysis.json"
            if ap.exists():
                try:
                    cache = json.loads(ap.read_text(encoding="utf-8"))
                except Exception:
                    cache = {}
            brands_data.append({
                "slug": r["brand_slug"],
                "brand_name_kr": r["brand_name_kr"],
                "items": items,
                "cache": cache,
            })

        trend_md = build_trend_report(brands_data)
        trend_path = BRANDS_ROOT / "ads_report.md"
        trend_path.write_text(trend_md, encoding="utf-8")
        print(f"\n통합 트렌드 리포트: {trend_path.relative_to(ROOT.parent)}")

    print("\n완료.")


if __name__ == "__main__":
    main()
