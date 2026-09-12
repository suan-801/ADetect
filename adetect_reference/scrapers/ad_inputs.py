#!/usr/bin/env python3
# ad-monitor 독립 스킬 — 브랜드 시드 .md 파일 파서 (자사·경쟁사 구분 없이 URL 1개 = 브랜드 1개)
#
# 입력
#   ad_monitor/_inputs/{slug}.md
#
# 사용 (다른 스크립트에서)
#   from ad_inputs import load_brands, INPUTS_DIR
#   rows = load_brands()                     # status=paused 제외
#   rows = load_brands(include_paused=True)
#   row = load_brand("medicube")             # 단일

import pathlib
import re
import sys

# Windows 콘솔(cp949) 은 em-dash(—)·이모지 print 시 UnicodeEncodeError 로 죽는다 — UTF-8 강제
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]   # ad_monitor/
INPUTS_DIR = ROOT / "_inputs"
COMBINED_INPUT = INPUTS_DIR / "urls.md"  # 통합 입력 파일 (사용자가 편집하는 유일한 곳)

# Frontmatter (YAML 형식이지만 단순 key: value 만 파싱)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_URL_RE = re.compile(r"https?://[^\s<>\"'`)\]]+")

_SECTION_ALIASES = {
    "meta ad library": "meta_ad_library_link",
    "meta": "meta_ad_library_link",
    "notes": "notes",
    "note": "notes",
}


def _parse_frontmatter(text):
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    body = text[m.end():]
    fm = {}
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def _split_sections(body):
    matches = list(_SECTION_RE.finditer(body))
    sections = {}
    for i, m in enumerate(matches):
        title = m.group(1).strip().lower()
        key = _SECTION_ALIASES.get(title)
        if not key:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[key] = body[start:end].strip()
    return sections


def _extract_urls(section_text):
    if not section_text:
        return []
    urls = _URL_RE.findall(section_text)
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_brand_md(path):
    """단일 .md 파일 → dict 반환.

    반환 키:
      brand_slug, brand_name_kr, brand_name_en, product_name_kr,
      group, status, meta_ad_library_link, notes, source_path
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    sections = _split_sections(body)

    meta = _extract_urls(sections.get("meta_ad_library_link", ""))
    notes_raw = sections.get("notes", "").strip()
    notes = " ".join(line.strip().lstrip("-").strip() for line in notes_raw.splitlines() if line.strip())

    slug = (fm.get("brand_slug") or fm.get("competitor_slug") or path.stem).strip()

    return {
        "brand_slug": slug,
        "brand_name_kr": fm.get("brand_name_kr", "").strip(),
        "brand_name_en": fm.get("brand_name_en", "").strip(),
        "product_name_kr": fm.get("product_name_kr", "").strip(),
        "group": (fm.get("group") or fm.get("classification") or "").strip(),
        "status": (fm.get("status") or "active").strip().lower(),
        "meta_ad_library_link": "|".join(meta),
        "notes": notes,
        "source_path": str(path),
    }


def load_brands(include_paused=False, inputs_dir=None):
    """`_inputs/*.md` 전체를 파싱해 리스트로 반환. README.md·템플릿은 제외."""
    base = pathlib.Path(inputs_dir) if inputs_dir else INPUTS_DIR
    if not base.exists():
        return []
    rows = []
    for path in sorted(base.glob("*.md")):
        name = path.stem.lower()
        if name in {"readme", "template", "brand-template", "urls"}:
            continue
        try:
            row = parse_brand_md(path)
        except Exception as e:
            print(f"  ⚠️ 파싱 실패: {path.name} — {e}", file=sys.stderr)
            continue
        if not row["brand_slug"]:
            print(f"  ⚠️ slug 없음: {path.name} — 무시", file=sys.stderr)
            continue
        if not include_paused and row["status"] == "paused":
            continue
        rows.append(row)
    return rows


def load_brand(slug, inputs_dir=None):
    base = pathlib.Path(inputs_dir) if inputs_dir else INPUTS_DIR
    candidate = base / f"{slug}.md"
    if not candidate.exists():
        return None
    return parse_brand_md(candidate)


# ──────────────────────── 통합 입력 파일 (urls.md) ────────────────────────

# `##` 헤딩은 자유 텍스트 그룹 라벨 (예: "## 자사", "## 관찰 대상 A", "## 인접 카테고리").
# 직접/간접경쟁 같은 고정 분류를 강제하지 않음 — 독립 스킬은 자사·경쟁사를 구분하지 않고
# 넣은 URL 을 전부 동등한 분석 대상으로 취급. 헤딩 텍스트는 참고용 그룹 라벨로만 그대로 보존.

_FB_AD_LIBRARY_RE = re.compile(r"https?://(?:www\.)?facebook\.com/ads/library/\?[^\s<>\"'`]+")


def load_combined_brands(path=None):
    """`_inputs/urls.md` 한 파일에서 URL 리스트 추출.

    포맷 규칙:
      - `##` 헤딩 → 다음 URL 들의 자유 그룹 라벨 (자사/경쟁사 구분 강제 ❌, 아무 텍스트나 OK. 헤딩 자체 생략 가능)
      - URL 라인: `https://...` (옵션: 뒤에 `# 메모` — brand_kr 힌트)
      - URL 앞에 `#` 가 붙어있으면 (주석 처리) → 스킵
      - `>` 인용·일반 주석 라인·빈 줄은 무시

    반환: list of {"url", "group", "notes"}
    """
    p = pathlib.Path(path) if path else COMBINED_INPUT
    if not p.exists():
        return []

    out = []
    seen = set()
    group = ""

    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        # 헤딩 → group 라벨 갱신 (자유 텍스트, 분류 강제 ❌)
        if stripped.startswith("##"):
            group = stripped.lstrip("#").strip()
            continue

        # `# ...` 단독 주석 (URL 미포함) → 스킵
        if stripped.startswith("#") and not _FB_AD_LIBRARY_RE.search(stripped):
            continue

        # `>` 인용 → 스킵
        if stripped.startswith(">"):
            continue

        # URL 추출
        m = _FB_AD_LIBRARY_RE.search(stripped)
        if not m:
            continue

        # 라인이 `#` 으로 시작 = 비활성화 (주석 처리)
        if stripped.startswith("#"):
            continue

        url = m.group(0).rstrip(",.;)")
        if url in seen:
            continue
        seen.add(url)

        # URL 뒤 `# 메모` 추출
        tail = stripped[m.end():].strip()
        notes = ""
        if "#" in tail:
            notes = tail.split("#", 1)[1].strip()

        out.append({
            "url": url,
            "group": group,
            "notes": notes,
        })

    return out


# ──────────────────────── URL → slug 자동 생성 ────────────────────────

_SLUG_DASH = re.compile(r"[\s_]+")
_SLUG_INVALID = re.compile(r"[^a-z0-9가-힣\-]+")
_SLUG_MULTI_DASH = re.compile(r"-{2,}")


def slugify(text):
    """page_name(또는 임의 문자열) → 영문 소문자·하이픈 슬러그.

    - 한글이 섞이면 한글은 보존 (파일명/폴더명으로 OK)
    - 공백·언더스코어 → 하이픈
    - 영문은 lowercase
    - 특수문자 제거
    - 빈 결과면 'brand' 폴백
    """
    if not text:
        return "brand"
    s = text.strip().lower()
    s = _SLUG_DASH.sub("-", s)          # 공백·언더스코어 → 하이픈 (먼저!)
    s = _SLUG_INVALID.sub("", s)        # 그 외 특수문자 제거
    s = _SLUG_MULTI_DASH.sub("-", s)
    s = s.strip("-")
    return s or "brand"


def write_seed_md(slug, brand_name_kr, ad_library_url, brand_name_en="", group="", inputs_dir=None):
    """URL-only 흐름: Apify 응답에서 추출한 page_name 으로 _inputs/{slug}.md 자동 생성.

    이미 있으면 덮어쓰지 않고 그대로 두고 None 반환.
    """
    base = pathlib.Path(inputs_dir) if inputs_dir else INPUTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{slug}.md"
    if path.exists():
        return None
    content = f"""---
brand_slug: {slug}
brand_name_kr: {brand_name_kr}
brand_name_en: {brand_name_en}
product_name_kr:
group: {group}
status: active
---

## Meta Ad Library
{ad_library_url}

## Notes
(자동 생성 — 첫 크롤 시 Apify page_name 으로 슬러그 도출)
"""
    path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    combined = load_combined_brands()
    if combined:
        print(f"통합 입력 (urls.md): {len(combined)}개 URL\n")
        for c in combined:
            print(f"  [{c['group'] or '미분류'}] {c['notes'][:60] or '(메모 없음)'}")
            print(f"     {c['url'][:120]}...")
        print()

    rows = load_brands(include_paused=True)
    if rows:
        print(f"개별 시드 (_inputs/*.md): {len(rows)}개\n")
        for r in rows:
            print(f"[{r['brand_slug']}] {r['brand_name_kr']} ({r['brand_name_en']}) — {r['group']} / {r['status']}")
            print(f"  Meta: {len(r['meta_ad_library_link'].split('|')) if r['meta_ad_library_link'] else 0}개")
            print(f"  notes: {r['notes'][:80]}")
            print()
