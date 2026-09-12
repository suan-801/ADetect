#!/usr/bin/env python3
# ad-monitor 독립 스킬 — 광고 모니터링 대시보드 — 정적 HTML + 로컬 미디어
#
# 입력
#   ad_monitor/{slug}/ad-creatives/{metadata.json, analysis.json, images/, videos/}
#
# 출력
#   ad_monitor/dashboard/
#     ├── index.html           # 단일 페이지 대시보드
#     ├── dashboard.json       # 통합 데이터
#     └── media/{slug}/{images,videos}/
#
# 사용
#   python3 build_dashboard.py              # 전체 빌드
#   python3 build_dashboard.py --no-copy    # 미디어 재복사 스킵 (HTML/JSON만 갱신)

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import sys
from collections import Counter

# Windows 콘솔(cp949) 은 em-dash(—)·이모지 print 시 UnicodeEncodeError 로 죽는다 — UTF-8 강제
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ad_inputs import load_brands

ROOT = pathlib.Path(__file__).resolve().parents[1]   # ad_monitor/
BRANDS_ROOT = ROOT
DASHBOARD = BRANDS_ROOT / "dashboard"
INPUTS_DIR = BRANDS_ROOT / "_inputs"


def normalize_domain(d):
    if not d:
        return ""
    d = d.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0].split("?")[0].split("#")[0]
    return d


def domain_of(url):
    if not url:
        return ""
    m = re.match(r"https?://([^/?#]+)", url)
    return normalize_domain(m.group(1) if m else "")


def extract_ad_meta(snap):
    title = (snap.get("title") or "").strip()
    link_desc = (snap.get("link_description") or "").strip()
    cta_text = (snap.get("cta_text") or "").strip()
    domain = (snap.get("caption") or "").strip()
    link_url = (snap.get("link_url") or "").strip()
    cards = snap.get("cards") or []
    extra_links = snap.get("extra_links") or []
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

    # ★ fb.com 다이나믹 광고는 link_url 이 canvas_doc 경로. 실제 랜딩은 snapshot.extra_links[0].
    is_dynamic = ("fb.com" in link_url) or ("facebook.com/canvas_doc" in link_url)
    if is_dynamic and extra_links:
        first_extra = extra_links[0]
        if isinstance(first_extra, str) and first_extra.startswith("http"):
            link_url = first_extra

    if not domain or "fb.com" in domain:
        domain = link_url
    return {
        "title": title,
        "link_description": link_desc,
        "cta_text": cta_text,
        "domain": normalize_domain(domain),
        "link_url": link_url,
        "card_links": card_links,
        "extra_links": [u for u in extra_links if isinstance(u, str) and u.startswith("http")],
    }


def load_brand_data(slug, brand_name_kr):
    base = BRANDS_ROOT / slug / "ad-creatives"
    meta_path = base / "metadata.json"
    if not meta_path.exists():
        return None

    items = json.loads(meta_path.read_text(encoding="utf-8"))
    analysis_path = base / "analysis.json"
    analysis = {}
    if analysis_path.exists():
        try:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        except Exception:
            analysis = {}

    ads = []
    for i, item in enumerate(items):
        ad_id = str(
            item.get("ad_archive_id") or item.get("adArchiveID") or item.get("id") or f"item{i:03d}"
        )
        snap = item.get("snapshot") or {}
        page_name = snap.get("page_name") or item.get("page_name") or ""
        ts = snap.get("creation_time") or item.get("start_date") or 0
        date_str = ""
        if ts:
            try:
                date_str = dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
            except Exception:
                pass
        body = snap.get("body") or {}
        caption = (body.get("text") if isinstance(body, dict) else body) or ""

        cta = snap.get("cta_type") or item.get("cta_type") or ""
        meta = extract_ad_meta(snap)
        link_url = meta["link_url"] or item.get("link_url") or ""

        videos = snap.get("videos") or []
        images = snap.get("images") or []
        cards = snap.get("cards") or []
        if videos:
            fmt = "video"
        elif cards:
            fmt = "carousel"
        elif images:
            fmt = "image"
        else:
            fmt = "unknown"

        media = []
        if fmt == "video":
            for j in range(3):
                p = base / "videos" / f"{ad_id}_{j}.mp4"
                if p.exists():
                    media.append({"type": "video", "src": f"media/{slug}/videos/{ad_id}_{j}.mp4"})
                    break
        elif fmt in ("image", "carousel"):
            for j in range(5):
                for ext in (".jpg", ".png"):
                    p = base / "images" / f"{ad_id}_{j}{ext}"
                    if p.exists():
                        media.append({"type": "image", "src": f"media/{slug}/images/{ad_id}_{j}{ext}"})
                        break

        ad_analysis = None
        analysis_status = "pending"  # 분석 시도 자체가 없는 상태 (디폴트)
        analysis_error = None
        if ad_id in analysis:
            entry = analysis[ad_id]
            # status 필드 우선 사용 (신규), 없으면 analysis 존재 여부로 추론 (구 캐시 호환)
            analysis_status = entry.get("status") or ("success" if "analysis" in entry else "pending")
            analysis_error = entry.get("error")
            if "analysis" in entry:
                ad_analysis = entry["analysis"]

        ads.append({
            "ad_id": ad_id,
            "page_name": page_name,
            "date": date_str,
            "format": fmt,
            "caption": caption,
            "cta": cta,
            "title": meta["title"],
            "link_description": meta["link_description"],
            "cta_text": meta["cta_text"],
            "domain": meta["domain"],
            "link_url": link_url,
            "card_links": meta["card_links"],
            "media": media,
            "analysis": ad_analysis,
            "analysis_status": analysis_status,
            "analysis_error": analysis_error,
        })

    domain_counter = Counter()
    for a in ads:
        d = a["domain"] or domain_of(a["link_url"])
        if d:
            domain_counter[d] += 1
        for cu in a.get("card_links") or []:
            cd = domain_of(cu)
            if cd and cd != d:
                domain_counter[cd] += 1

    return {
        "slug": slug,
        "name": brand_name_kr,
        "ads": ads,
        "domains": dict(domain_counter.most_common()),
    }


def copy_media(slug):
    src_root = BRANDS_ROOT / slug / "ad-creatives"
    if not src_root.exists():
        return 0
    dst_root = DASHBOARD / "media" / slug
    n = 0
    for sub in ("images", "videos"):
        s = src_root / sub
        if not s.exists():
            continue
        d = dst_root / sub
        d.mkdir(parents=True, exist_ok=True)
        for f in s.iterdir():
            if f.is_file():
                target = d / f.name
                if not target.exists() or target.stat().st_size != f.stat().st_size:
                    shutil.copy2(f, target)
                    n += 1
    return n


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>광고 모니터링 (ad-monitor)</title>
<style>
  /* 브랜드 컬러 팔레트 — 01_brand/brand_brief.md 의 6슬롯 값으로 교체해서 사용. 아래는 중립 톤 기본값. */
  :root {
    --brand: #4F46E5;          /* 시그니처 컬러 — CTA·강조 1포인트 */
    --brand-deep: #1E1B4B;     /* 진한 브랜드 톤 — 헤더·다크 띠 */
    --brand-soft: #EEF2FF;     /* 옅은 톤 — 호버·뱃지 BG */
    --brand-sub: #10B981;      /* 보조 액센트 — 효과·강조 */
    --bg-light: #FAFAFA;       /* 페이지 베이스 */
    --ink: #1F2937;            /* 메인 텍스트 */
    --muted: #6B7280;          /* 보조 텍스트 */
    --border: #E5E7EB;         /* 라인·구분선 */
    --bg: #FAFAFA;             /* (alias) 페이지 베이스 */
    --card: #FFFFFF;
    /* (legacy alias — 모달·badge 등 기존 변수 참조 호환) */
    --purple: var(--brand);
    --purple-deep: var(--brand-deep);
    --lavender: var(--brand-soft);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--ink); line-height: 1.55;
  }
  h1, h2, h3 { font-family: 'Noto Serif KR', 'Pretendard', serif; }

  header {
    background: linear-gradient(135deg, var(--brand-deep) 0%, #4A3A28 50%, var(--brand) 100%);
    color: #FFF7EE; padding: 1.5rem 2rem; position: sticky; top: 0; z-index: 100;
    box-shadow: 0 2px 8px rgba(45,36,24,0.18);
  }
  header h1 { font-size: 1.4rem; font-weight: 700; }
  header .meta { font-size: 0.85rem; opacity: 0.85; margin-top: 0.25rem; }

  .filters {
    display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;
    background: white; padding: 1rem 2rem; border-bottom: 1px solid var(--border);
    position: sticky; top: 88px; z-index: 99;
  }
  .filters select, .filters input {
    padding: 0.5rem 0.75rem; border: 1px solid var(--border); border-radius: 6px;
    font-size: 0.9rem; background: white;
  }
  .filters input[type=search] { min-width: 240px; flex: 1; max-width: 360px; }
  .filters .count { color: var(--muted); font-size: 0.85rem; margin-left: auto; }

  main { max-width: 1400px; margin: 1.5rem auto; padding: 0 2rem; }

  .gallery {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1rem;
  }

  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    overflow: hidden; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s;
    display: flex; flex-direction: column;
  }
  .card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(74,58,125,0.12); }

  .media-wrap {
    position: relative; aspect-ratio: 1 / 1; background: var(--lavender);
    overflow: hidden;
  }
  .media-wrap img, .media-wrap video {
    width: 100%; height: 100%; object-fit: cover;
  }
  .media-wrap .placeholder {
    display: flex; align-items: center; justify-content: center; height: 100%;
    color: var(--purple-deep); font-size: 0.9rem;
  }
  .badge {
    position: absolute; top: 8px; left: 8px;
    background: rgba(74,58,125,0.92); color: white; padding: 0.2rem 0.55rem;
    border-radius: 4px; font-size: 0.7rem; font-weight: 600;
  }
  .badge.format {
    left: auto; right: 8px; background: rgba(0,0,0,0.7);
  }
  .badge.status {
    left: auto; right: 8px; top: 38px;
    font-size: 0.66rem; padding: 0.15rem 0.45rem;
  }
  .badge.status.success { background: rgba(40,160,90,0.92); }
  .badge.status.pending { background: rgba(120,120,120,0.85); }
  .badge.status.quota_exceeded { background: rgba(220,140,40,0.92); }
  .badge.status.failed { background: rgba(200,60,60,0.92); }

  .card-body { padding: 0.75rem; flex: 1; display: flex; flex-direction: column; gap: 0.4rem; }
  .card-page { font-size: 0.78rem; color: var(--muted); }
  .card-title {
    font-size: 0.92rem; font-weight: 700; color: var(--purple-deep);
    line-height: 1.3;
    display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .card-caption {
    font-size: 0.82rem; line-height: 1.4; color: #444;
    display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; flex: 1;
  }
  .card-cta-row {
    display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;
    font-size: 0.72rem;
  }
  .cta-pill {
    background: var(--purple); color: white; padding: 0.15rem 0.5rem;
    border-radius: 4px; font-weight: 600;
  }
  .domain-pill {
    background: var(--lavender); color: var(--purple-deep);
    padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 500;
    max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .card-meta {
    font-size: 0.72rem; color: var(--muted); display: flex; gap: 0.5rem;
    border-top: 1px solid var(--border); padding-top: 0.4rem;
  }

  .domain-panel {
    background: white; border-bottom: 1px solid var(--border);
    padding: 0.85rem 2rem;
  }
  .domain-panel h2 {
    font-size: 0.82rem; color: var(--purple-deep); margin-bottom: 0.55rem;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .domain-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.5rem;
  }
  .domain-row {
    display: flex; align-items: center; gap: 0.5rem;
    font-size: 0.82rem;
  }
  .domain-row .name { color: var(--ink); font-weight: 600; flex-shrink: 0; }
  .domain-row .bar {
    flex: 1; height: 6px; background: var(--lavender); border-radius: 3px; overflow: hidden;
  }
  .domain-row .bar > span {
    display: block; height: 100%; background: var(--purple);
  }
  .domain-row .n { color: var(--muted); font-size: 0.78rem; min-width: 2ch; text-align: right; }
  .score {
    display: inline-block; background: var(--purple); color: white;
    padding: 0 0.4rem; border-radius: 4px; font-weight: 600;
  }

  dialog {
    border: none; padding: 0; max-width: 900px; width: 92vw; max-height: 92vh;
    border-radius: 12px; overflow: hidden;
    /* 중앙 정렬 (브라우저 디폴트 보강 — Safari·일부 환경에서 왼쪽 정렬되는 문제 방지) */
    margin: auto; inset: 0;
  }
  dialog::backdrop { background: rgba(0,0,0,0.5); }
  .modal-head {
    background: linear-gradient(135deg, var(--purple-deep), var(--purple));
    color: white; padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center;
  }
  .modal-head button {
    background: transparent; border: 1px solid rgba(255,255,255,0.4); color: white;
    width: 32px; height: 32px; border-radius: 50%; cursor: pointer; font-size: 1.1rem;
  }
  .modal-body { padding: 1.5rem; max-height: 75vh; overflow-y: auto; }
  .modal-media { margin-bottom: 1rem; background: var(--lavender); border-radius: 8px; overflow: hidden; }
  .modal-media img, .modal-media video { width: 100%; max-height: 460px; object-fit: contain; }
  .modal-section { margin-bottom: 1.25rem; }
  .modal-section h3 {
    font-size: 0.95rem; color: var(--purple-deep); margin-bottom: 0.5rem;
    border-left: 3px solid var(--purple); padding-left: 0.6rem;
  }
  .modal-section p, .modal-section pre {
    font-size: 0.88rem; line-height: 1.6; white-space: pre-wrap; word-break: break-word;
    background: var(--bg); padding: 0.75rem; border-radius: 6px; font-family: inherit;
  }
  .kv { display: grid; grid-template-columns: max-content 1fr; gap: 0.4rem 1rem; font-size: 0.88rem; }
  .kv .k { color: var(--muted); font-weight: 600; }
  .pill {
    display: inline-block; padding: 0.15rem 0.5rem; background: var(--lavender);
    color: var(--purple-deep); border-radius: 4px; font-size: 0.78rem; margin-right: 0.3rem;
  }
  details { margin-top: 0.75rem; }
  details summary { cursor: pointer; color: var(--purple-deep); font-size: 0.88rem; font-weight: 600; }
  details pre { margin-top: 0.5rem; }
  .stages-grid {
    display: grid; grid-template-columns: 1fr; gap: 0.5rem; margin-top: 0.5rem;
  }
  .stage {
    background: var(--bg); border-left: 3px solid var(--purple);
    padding: 0.55rem 0.75rem; border-radius: 4px; font-size: 0.85rem;
  }
  .stage .label { font-weight: 700; color: var(--purple-deep); margin-right: 0.4rem; }

  @media (max-width: 640px) {
    header, .filters, main { padding-left: 1rem; padding-right: 1rem; }
    .filters { top: 80px; }
  }
</style>
</head>
<body>

<header>
  <h1>광고 모니터링 (ad-monitor 독립 스킬)</h1>
  <div class="meta" id="header-meta"></div>
</header>

<!-- 랜딩 도메인 분포 패널 제거 (2026-05-19) — 도메인 필터는 .filters 의 select 로 유지 -->

<div class="filters">
  <select id="f-brand"><option value="all">전체 브랜드</option></select>
  <select id="f-format">
    <option value="all">전체 포맷</option>
    <option value="video">영상</option>
    <option value="image">이미지</option>
    <option value="carousel">캐러셀</option>
  </select>
  <select id="f-domain"><option value="all">전체 도메인</option></select>
  <select id="f-sort">
    <option value="date-desc">최신순</option>
    <option value="date-asc">오래된순</option>
    <option value="score-desc">점수 높은순</option>
  </select>
  <input type="search" id="f-search" placeholder="캡션·후크·제목 검색...">
  <span class="count" id="count"></span>
</div>

<main><div class="gallery" id="gallery"></div></main>

<dialog id="modal"></dialog>

<script>
const FORMAT_LABEL = { video: '🎬 영상', image: '🖼️ 이미지', carousel: '🎠 캐러셀', unknown: '?' };
const USP_LABEL = {
  users_problem: "1. User's Problem",
  solution: '2. Solution',
  promotion: '3. Promotion',
  creative_key_visual: '★ Creative Key Visual',
};
const AD_PATTERN_LABEL = {
  default: '🎯 default (페인 후킹)',
  trust_anchor: '🏆 trust_anchor (신뢰 자산 강조)',
  promotion_anchor: '💰 promotion_anchor (할인 BOFU)',
  hybrid: '🔀 hybrid (결합)',
};

// build_dashboard.py 가 빌드 시점에 window.DATA 를 주입 (file:// 더블클릭 지원)
window.DATA = /*__DATA_PLACEHOLDER__*/ window.DATA || null;
let DATA = null;
let FILTERED = [];

async function init() {
  // 인라인 데이터가 있으면 즉시 사용, 없으면 dashboard.json 로 폴백 (개발용)
  if (window.DATA) {
    DATA = window.DATA;
  } else {
    const res = await fetch('dashboard.json');
    DATA = await res.json();
  }

  const totalAds = Object.values(DATA.brands).reduce((s, b) => s + b.ads.length, 0);
  document.getElementById('header-meta').textContent =
    `${Object.keys(DATA.brands).length}개 브랜드 · 광고 ${totalAds}건 · 갱신 ${DATA.generated_at}`;

  const sel = document.getElementById('f-brand');
  for (const [slug, b] of Object.entries(DATA.brands)) {
    const opt = document.createElement('option');
    opt.value = slug; opt.textContent = `${b.name} (${b.ads.length})`;
    sel.appendChild(opt);
  }

  const allDomains = {};
  for (const b of Object.values(DATA.brands)) {
    for (const [d, n] of Object.entries(b.domains || {})) {
      allDomains[d] = (allDomains[d] || 0) + n;
    }
  }
  const dsel = document.getElementById('f-domain');
  Object.entries(allDomains)
    .sort((a, b) => b[1] - a[1])
    .forEach(([d, n]) => {
      const opt = document.createElement('option');
      opt.value = d; opt.textContent = `${d} (${n})`;
      dsel.appendChild(opt);
    });

  renderDomainPanel('all');

  ['f-brand', 'f-format', 'f-domain', 'f-sort', 'f-search'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => {
      if (id === 'f-brand') renderDomainPanel(document.getElementById('f-brand').value);
      render();
    });
  });

  render();
}

function renderDomainPanel(brandFilter) {
  const counts = {};
  for (const [slug, b] of Object.entries(DATA.brands)) {
    if (brandFilter !== 'all' && brandFilter !== slug) continue;
    for (const [d, n] of Object.entries(b.domains || {})) {
      counts[d] = (counts[d] || 0) + n;
    }
  }
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;
  const max = entries.length ? entries[0][1] : 1;
  // 메인 페이지 도메인 분포 패널은 제거됨 (사용자 요청 — 2026-05-19).
  // 도메인 필터는 .filters 의 select 로 유지.
  const panel = document.getElementById('domain-panel');
  if (panel) panel.innerHTML = '';
}

function render() {
  const brand = document.getElementById('f-brand').value;
  const fmt = document.getElementById('f-format').value;
  const dom = document.getElementById('f-domain').value;
  const sort = document.getElementById('f-sort').value;
  const q = document.getElementById('f-search').value.trim().toLowerCase();

  let ads = [];
  for (const [slug, b] of Object.entries(DATA.brands)) {
    if (brand !== 'all' && brand !== slug) continue;
    for (const ad of b.ads) {
      ads.push({...ad, brand_slug: slug, brand_name: b.name});
    }
  }
  if (fmt !== 'all') ads = ads.filter(a => a.format === fmt);
  if (dom !== 'all') {
    ads = ads.filter(a => {
      if ((a.domain || '') === dom) return true;
      return (a.card_links || []).some(u => domainOf(u) === dom);
    });
  }
  if (q) {
    ads = ads.filter(a => {
      const hay = [
        a.caption, a.page_name, a.title || '', a.cta_text || '', a.link_description || '',
        (a.analysis && a.analysis.full_storyline) || '',
        (a.analysis && a.analysis.analysis_summary && a.analysis.analysis_summary.hook_type) || '',
        (a.analysis && a.analysis.main_copy) || '',
        (a.analysis && a.analysis.layout_style) || '',
        (a.analysis && a.analysis.stages && Object.values(a.analysis.stages).join(' ')) || '',
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }
  if (sort === 'date-desc') ads.sort((x, y) => (y.date || '').localeCompare(x.date || ''));
  if (sort === 'date-asc')  ads.sort((x, y) => (x.date || '').localeCompare(y.date || ''));
  if (sort === 'score-desc') {
    ads.sort((x, y) => {
      const sx = (x.analysis && x.analysis.analysis_summary && x.analysis.analysis_summary.overall_score) ||
                 (x.analysis && x.analysis.overall_score) || 0;
      const sy = (y.analysis && y.analysis.analysis_summary && y.analysis.analysis_summary.overall_score) ||
                 (y.analysis && y.analysis.overall_score) || 0;
      return sy - sx;
    });
  }

  FILTERED = ads;
  document.getElementById('count').textContent = `${ads.length}건`;
  const gal = document.getElementById('gallery');
  gal.innerHTML = '';
  ads.forEach((a, i) => gal.appendChild(card(a, i)));
}

function card(a, idx) {
  const div = document.createElement('div');
  div.className = 'card';
  div.dataset.idx = idx;
  div.addEventListener('click', () => openModal(idx));

  const m = (a.media && a.media[0]) || null;
  let mediaEl = '<div class="placeholder">미디어 없음</div>';
  if (m && m.type === 'image') {
    mediaEl = `<img src="${m.src}" alt="" loading="lazy">`;
  } else if (m && m.type === 'video') {
    mediaEl = `<video src="${m.src}" muted preload="metadata" playsinline></video>`;
  }

  const score = (a.analysis && a.analysis.analysis_summary && a.analysis.analysis_summary.overall_score) ||
                (a.analysis && a.analysis.overall_score);

  const dom = a.domain || domainOf(a.link_url);
  const ctaLabel = a.cta_text || a.cta || '';
  const STATUS_BADGE = {
    success: { icon: '🟢', label: '분석완료' },
    pending: { icon: '⏸️', label: '분석대기' },
    quota_exceeded: { icon: '🚫', label: '무료한도' },
    failed: { icon: '❌', label: '분석실패' },
  };
  const sb = STATUS_BADGE[a.analysis_status] || STATUS_BADGE.pending;
  div.innerHTML = `
    <div class="media-wrap">
      ${mediaEl}
      <span class="badge">${a.brand_name}</span>
      <span class="badge format">${FORMAT_LABEL[a.format] || a.format}</span>
      <span class="badge status ${a.analysis_status || 'pending'}" title="${sb.label}">${sb.icon} ${sb.label}</span>
    </div>
    <div class="card-body">
      <div class="card-page">${escapeHtml(a.page_name || '')}</div>
      ${a.title ? `<div class="card-title">${escapeHtml(a.title)}</div>` : ''}
      <div class="card-caption">${escapeHtml((a.caption || '').slice(0, 160))}</div>
      <div class="card-cta-row">
        ${ctaLabel ? `<span class="cta-pill">${escapeHtml(ctaLabel)}</span>` : ''}
        ${dom ? `<span class="domain-pill" title="${escapeHtml(dom)}">${escapeHtml(dom)}</span>` : ''}
      </div>
      <div class="card-meta">
        <span>${a.date || ''}</span>
        ${score ? `<span class="score">${score}/10</span>` : ''}
      </div>
    </div>
  `;

  const v = div.querySelector('video');
  if (v) {
    div.addEventListener('mouseenter', () => v.play().catch(()=>{}));
    div.addEventListener('mouseleave', () => { v.pause(); v.currentTime = 0; });
  }

  return div;
}

function openModal(idx) {
  const a = FILTERED[idx];
  const dlg = document.getElementById('modal');
  const m = (a.media && a.media[0]) || null;
  let mediaEl = '';
  if (m && m.type === 'image') mediaEl = `<img src="${m.src}">`;
  else if (m && m.type === 'video') mediaEl = `<video src="${m.src}" controls autoplay muted></video>`;

  const an = a.analysis || {};
  const summ = an.analysis_summary || {};
  // 신규: analysis 객체 (USP 3 항목 + Creative Key Visual). 구 stages 도 폴백 지원.
  const analysis = an.analysis || an.stages || {};
  const adPattern = an.ad_pattern || '';
  let analysisHtml = '';

  // USP 3 항목 + Creative Key Visual + ad_pattern (있으면 항상 먼저 표시)
  let stagesHtml = '';
  const uspOrder = ['users_problem', 'solution', 'promotion', 'creative_key_visual'];
  // 구 키(problem/evidence/hook_image/cta) → 신 키 자동 매핑 (기존 분석 데이터 호환)
  const legacyMap = { problem: 'users_problem', evidence: 'solution', hook_image: 'creative_key_visual', cta: 'promotion' };
  const merged = { ...analysis };
  for (const [oldK, newK] of Object.entries(legacyMap)) {
    if (analysis[oldK] && !merged[newK]) merged[newK] = analysis[oldK];
  }
  if (uspOrder.some(k => merged[k]) || adPattern) {
    const patternBadge = adPattern
      ? `<div class="ad-pattern-badge">${AD_PATTERN_LABEL[adPattern] || adPattern}</div>`
      : '';
    stagesHtml = `
      <div class="modal-section">
        <h3>🧱 USP 3 항목 + Creative Key Visual</h3>
        ${patternBadge}
        <div class="stages-grid">
          ${uspOrder.map(k => merged[k] ? `<div class="stage"><span class="label">${USP_LABEL[k]}</span>${escapeHtml(merged[k])}</div>` : '').join('')}
        </div>
      </div>
    `;
  }

  if (a.format === 'video' && an.full_storyline) {
    analysisHtml = `
      <div class="modal-section">
        <h3>📊 영상 분석 요약</h3>
        <div class="kv">
          <span class="k">Hook 유형</span><span>${escapeHtml(summ.hook_type || '-')}</span>
          <span class="k">Hook 점수</span><span>${summ.hook_effectiveness || '-'}/10</span>
          <span class="k">전체 구조</span><span>${escapeHtml(summ.structure_type || '-')}</span>
          <span class="k">영상 스타일</span><span>${escapeHtml(summ.video_style || '-')}</span>
          <span class="k">길이</span><span>${summ.duration_seconds || '-'}초</span>
          <span class="k">종합 점수</span><span>${summ.overall_score || '-'}/10</span>
        </div>
        ${arrField('강점', summ.key_strengths)}
        ${arrField('개선점', summ.improvement_points)}
        ${arrField('설득 요소', summ.persuasion_elements)}
      </div>
      <div class="modal-section">
        <h3>📝 전체 스토리라인 (역할 태깅)</h3>
        <pre>${escapeHtml(an.full_storyline)}</pre>
      </div>
    `;
  } else if (an.main_copy !== undefined || an.layout_style) {
    analysisHtml = `
      <div class="modal-section">
        <h3>📊 이미지 분석</h3>
        <div class="kv">
          ${an.main_copy ? `<span class="k">메인 카피</span><span>${escapeHtml(an.main_copy)}</span>` : ''}
          ${an.sub_copy ? `<span class="k">서브 카피</span><span>${escapeHtml(an.sub_copy)}</span>` : ''}
          ${an.feature_desc ? `<span class="k">제품 설명</span><span>${escapeHtml(an.feature_desc)}</span>` : ''}
          ${an.empathy_copy ? `<span class="k">공감 카피</span><span>${escapeHtml(an.empathy_copy)}</span>` : ''}
          ${an.cta ? `<span class="k">CTA</span><span>${escapeHtml(an.cta)}</span>` : ''}
          ${an.layout_style ? `<span class="k">레이아웃</span><span>${escapeHtml(an.layout_style)}</span>` : ''}
          ${an.visual_style ? `<span class="k">비주얼 스타일</span><span>${escapeHtml(an.visual_style)}</span>` : ''}
          ${an.color_mood ? `<span class="k">컬러 무드</span><span>${escapeHtml(an.color_mood)}</span>` : ''}
          ${an.overall_score ? `<span class="k">종합 점수</span><span>${an.overall_score}/10</span>` : ''}
        </div>
      </div>
      ${an.all_text_extracted ? `<div class="modal-section"><h3>📋 추출된 전체 텍스트</h3><pre>${escapeHtml(an.all_text_extracted)}</pre></div>` : ''}
      ${an.nanobanana_prompt ? `<div class="modal-section"><h3>🎨 NanoBanana 재현 프롬프트</h3><details open><summary>펼쳐서 복사</summary><pre>${escapeHtml(an.nanobanana_prompt)}</pre></details></div>` : ''}
    `;
  } else if (an.error) {
    analysisHtml = `<div class="modal-section"><h3>⚠️ 분석 실패</h3><p>${escapeHtml(an.error)}</p></div>`;
  } else if (!stagesHtml) {
    // 상태별 안내 메시지 — 무료 한도 / 분석 대기 / 일반 미분석
    const status = a.analysis_status || 'pending';
    if (status === 'quota_exceeded') {
      analysisHtml = `
        <div class="modal-section">
          <h3>🚫 Gemini 무료 한도 도달</h3>
          <p>이 광고는 일일 무료 쿼터 초과 시점에 분석 시도되어 결과가 비어있습니다.<br/>
          <strong>다음 단계 (택1):</strong><br/>
          ① 24시간 후 같은 명령 재실행 → 무료 한도 리셋 후 자동으로 이 광고만 재시도<br/>
          ② 즉시 완료가 필요하면 <code>--paid</code> 플래그로 재실행 (유료 키 필요)</p>
          ${a.analysis_error ? `<p style="color:var(--muted);font-size:0.78rem;">에러: ${escapeHtml(a.analysis_error)}</p>` : ''}
        </div>`;
    } else if (status === 'failed') {
      analysisHtml = `
        <div class="modal-section">
          <h3>❌ 분석 실패</h3>
          <p>${escapeHtml(a.analysis_error || 'Gemini 응답 파싱 실패')}</p>
          <p style="color:var(--muted);font-size:0.82rem;">같은 명령 재실행 시 자동 재시도됩니다.</p>
        </div>`;
    } else {
      analysisHtml = `<div class="modal-section"><p style="color:var(--muted)">⏸️ 분석 대기 — Gemini 분석이 아직 실행되지 않았습니다. <code>--no-gemini</code> 없이 재실행하세요.</p></div>`;
    }
  }

  const dom = a.domain || domainOf(a.link_url);
  const cardLinksRows = (a.card_links || []).filter(u => u).map((u, idx) => {
    const cd = domainOf(u);
    return `<li><span class="pill">${idx + 1}</span> <a href="${escapeHtml(u)}" target="_blank" rel="noopener">${escapeHtml(cd || u)}</a></li>`;
  }).join('');
  const adInfoHtml = `
    <div class="modal-section">
      <h3>🎯 광고 정보 (Apify 메타)</h3>
      <div class="kv">
        ${a.title ? `<span class="k">광고 제목</span><span>${escapeHtml(a.title)}</span>` : ''}
        ${a.link_description ? `<span class="k">링크 설명</span><span>${escapeHtml(a.link_description)}</span>` : ''}
        ${a.cta_text ? `<span class="k">CTA 버튼</span><span><span class="pill">${escapeHtml(a.cta_text)}</span></span>` : ''}
        ${a.cta ? `<span class="k">CTA 타입</span><span>${escapeHtml(a.cta)}</span>` : ''}
        ${dom ? `<span class="k">랜딩 도메인</span><span>${escapeHtml(dom)}</span>` : ''}
        ${a.link_url ? `<span class="k">랜딩 URL</span><span><a href="${escapeHtml(a.link_url)}" target="_blank" rel="noopener" style="color:var(--purple-deep);word-break:break-all">${escapeHtml(a.link_url)}</a></span>` : ''}
      </div>
      ${cardLinksRows ? `<details style="margin-top:0.6rem"><summary>캐러셀 카드별 랜딩 (${(a.card_links || []).length}개)</summary><ul style="margin-top:0.4rem;padding-left:1.2rem;font-size:0.85rem;line-height:1.7">${cardLinksRows}</ul></details>` : ''}
    </div>
  `;

  dlg.innerHTML = `
    <div class="modal-head">
      <div>
        <strong>${escapeHtml(a.brand_name)}</strong> · ${FORMAT_LABEL[a.format] || a.format} · ${a.date || ''}
        <div style="font-size:0.8rem;opacity:0.85">${escapeHtml(a.page_name)} · ad_id ${a.ad_id}</div>
      </div>
      <button onclick="document.getElementById('modal').close()">×</button>
    </div>
    <div class="modal-body">
      <div class="modal-media">${mediaEl}</div>
      ${(a.title || a.cta_text || a.link_url) ? adInfoHtml : ''}
      ${stagesHtml}
      <div class="modal-section">
        <h3>💬 광고 본문 캡션</h3>
        <pre>${escapeHtml(a.caption || '(없음)')}</pre>
      </div>
      ${analysisHtml}
    </div>
  `;
  dlg.showModal();
}

function domainOf(url) {
  if (!url) return '';
  let s = String(url).trim().toLowerCase();
  s = s.replace(/^https?:\\/\\//, '');
  s = s.replace(/^www\\./, '');
  return s.split('/')[0].split('?')[0].split('#')[0];
}

function arrField(label, arr) {
  if (!arr) return '';
  const list = Array.isArray(arr) ? arr : [arr];
  return `<div style="margin-top:0.5rem"><strong style="color:var(--muted);font-size:0.82rem">${label}</strong><br>${list.map(x => `<span class="pill">${escapeHtml(String(x))}</span>`).join('')}</div>`;
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

init();
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="ad-monitor 독립 스킬 — 광고 모니터링 대시보드 빌드")
    parser.add_argument("--no-copy", action="store_true", help="미디어 재복사 스킵")
    args = parser.parse_args()

    rows = load_brands(inputs_dir=INPUTS_DIR)
    if not rows:
        sys.exit(f"시드 없음: {INPUTS_DIR}/{{slug}}.md 를 1개 이상 만들거나, fetch_ads.py 로 URL 을 직접 처리하세요")
    print(f"브랜드 후보: {len(rows)}개")

    DASHBOARD.mkdir(parents=True, exist_ok=True)

    brands = {}
    for r in rows:
        slug = r["brand_slug"]
        kr = r["brand_name_kr"]
        if not slug:
            continue
        data = load_brand_data(slug, kr)
        if data and data["ads"]:
            brands[slug] = {
                "name": kr,
                "ads": data["ads"],
                "domains": data.get("domains", {}),
            }
            top_d = ", ".join(f"{d}({n})" for d, n in list(data.get("domains", {}).items())[:3])
            print(f"  · {slug} ({kr}): {len(data['ads'])}건 · 랜딩: {top_d}")
        else:
            print(f"  · {slug} ({kr}): 데이터 없음 — 스킵")

    if not brands:
        sys.exit("로드 가능한 브랜드 데이터가 없습니다. fetch_ads.py 부터 실행하세요.")

    if not args.no_copy:
        print("\n미디어 복사 중...")
        total = 0
        for slug in brands.keys():
            n = copy_media(slug)
            if n:
                print(f"  · {slug}: {n}개 신규 복사")
            total += n
        print(f"미디어 복사 완료 ({total}개 신규)")

    dashboard_data = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M KST"),
        "brands": brands,
    }
    # dashboard.json 은 디버깅·서버 모드 폴백용으로 계속 저장
    (DASHBOARD / "dashboard.json").write_text(
        json.dumps(dashboard_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    json_kb = (DASHBOARD / "dashboard.json").stat().st_size // 1024
    print(f"\ndashboard.json 작성 ({json_kb} KB)")

    # HTML 에 데이터 인라인 주입 → file:// 더블클릭으로 바로 열림
    # </script> 등이 JSON 안에 들어있으면 HTML 파서가 깨지므로 안전하게 이스케이프
    data_json = json.dumps(dashboard_data, ensure_ascii=False)
    # </script> 가 JSON 안에 들어있으면 HTML 파서가 깨지므로 escape.
    # U+2028(LINE SEPARATOR) · U+2029(PARAGRAPH SEPARATOR) 는 JSON 에선 valid 지만
    # JS 문자열 리터럴/Script 컨텍스트에선 줄바꿈으로 해석돼 SyntaxError 발생 → escape.
    data_json = (
        data_json
        .replace("</", "<\\/")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )
    # /*__DATA_PLACEHOLDER__*/ 자리에 실제 JSON 객체를 끼워넣음
    # → 결과: window.DATA = {...} || null;  (JSON 이 truthy 라 || null 은 무시됨)
    placeholder = "/*__DATA_PLACEHOLDER__*/ window.DATA || null"
    if placeholder not in HTML_TEMPLATE:
        sys.exit(f"빌드 실패: HTML_TEMPLATE 에 placeholder '{placeholder}' 를 찾지 못함")
    html_out = HTML_TEMPLATE.replace(placeholder, data_json, 1)

    (DASHBOARD / "index.html").write_text(html_out, encoding="utf-8")
    html_kb = (DASHBOARD / "index.html").stat().st_size // 1024
    print(f"index.html 작성 ({html_kb} KB, 데이터 인라인 포함)")

    print(f"\n빌드 완료: {DASHBOARD.relative_to(ROOT)}/")
    print(f"  더블클릭: open {DASHBOARD.relative_to(ROOT)}/index.html")
    print(f"  서버 모드: cd {DASHBOARD.relative_to(ROOT)} && python3 -m http.server 8000")


if __name__ == "__main__":
    main()
