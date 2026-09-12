#!/usr/bin/env python3
# ad-monitor 독립 스킬 — 랜딩 URL UTM 구조 관찰 (규칙 "확정" ❌, 관찰 데이터 제공)
#
# 이 스크립트는 UTM 파라미터를 추출·집계만 합니다. "캠페인/그룹/소재명 규칙을 이렇다"라고
# 단정하지 않습니다 — 관찰된 샘플이 근거로 삼기에 충분한지, 어떤 규칙이 보이는지는
# ad-monitor SKILL.md 의 지시에 따라 Claude 가 표를 보고 직접 판단·서술합니다.
#
# 이유: 경쟁사 랜딩 URL 은 리다이렉트 체인·단축 URL·클릭ID(fbclid 등)만 있고
# utm_campaign/utm_content 값이 아예 없는 경우가 흔함 — 코드로 "규칙 확정"을 주장하면
# 거짓 정밀도(false precision)가 생김. 자사 URL 은 직접 UTM을 설계하므로 신뢰도가 높지만,
# 경쟁사는 낮을 수 있다는 걸 리포트에 항상 명시해야 함.

import json
import sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit, parse_qsl

# Windows 콘솔(cp949) 은 em-dash(—)·이모지 print 시 UnicodeEncodeError 로 죽는다 — UTF-8 강제
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# UTM 스탠다드 5종 + 실무에서 흔한 변형/클릭ID 키
TRACKING_KEYS = [
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "utm_id", "fbclid", "gclid", "ttclid", "campaign_id", "adset_id", "ad_id",
]


def _domain(url):
    try:
        return urlsplit(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def extract_utm_samples(items):
    """metadata.json 의 items 리스트 → [{ad_id, url, domain, params}, ...]

    link_url + card_links(carousel) 모두 스캔. UTM/트래킹 파라미터가 하나도 없는
    URL 도 샘플로 남긴다 (params={}) — "UTM 자체가 없는 브랜드"라는 사실도 관찰 결과.
    """
    samples = []
    for i, item in enumerate(items):
        ad_id = str(item.get("ad_archive_id") or item.get("adArchiveID") or item.get("id") or f"item{i:03d}")
        snap = item.get("snapshot") or {}
        urls = []
        link_url = (snap.get("link_url") or "").strip()
        if link_url:
            urls.append(link_url)
        for c in (snap.get("cards") or []):
            cu = (c.get("link_url") or "").strip()
            if cu and cu not in urls:
                urls.append(cu)
        for u in urls:
            if not u.startswith("http"):
                continue
            q = dict(parse_qsl(urlsplit(u).query, keep_blank_values=True))
            params = {k: v for k, v in q.items() if k.lower() in TRACKING_KEYS or k.lower().startswith("utm_")}
            samples.append({"ad_id": ad_id, "url": u, "domain": _domain(u), "params": params})
    return samples


def key_frequency(samples):
    """트래킹 키 등장 빈도 + 관찰된 고유 값 예시(최대 8개)."""
    freq = Counter()
    examples = defaultdict(list)
    for s in samples:
        for k, v in s["params"].items():
            freq[k] += 1
            if v and v not in examples[k] and len(examples[k]) < 8:
                examples[k].append(v)
    return freq, examples


def has_no_utm(samples):
    """샘플이 있는데도 트래킹 파라미터가 하나도 없는 비율."""
    if not samples:
        return None
    bare = sum(1 for s in samples if not s["params"])
    return bare, len(samples)


def format_utm_section_md(brand_name_kr, slug, samples):
    """브랜드 1개 분량 — utm 관찰 표 (마크다운). ad-creatives.md 에 삽입용."""
    lines = []
    lines.append(f"### UTM/트래킹 파라미터 관찰 — {brand_name_kr}")
    lines.append("")
    if not samples:
        lines.append("- (link_url 없음 — 관찰 불가)")
        lines.append("")
        return "\n".join(lines)

    bare, total = has_no_utm(samples)
    domains = Counter(s["domain"] for s in samples if s["domain"])
    lines.append(f"- 랜딩 URL 샘플 {total}건 중 **{bare}건은 트래킹 파라미터 전무** ({bare*100//total if total else 0}%)")
    lines.append(f"- 도메인: " + ", ".join(f"`{d}`({n})" for d, n in domains.most_common(5)))
    lines.append("")

    freq, examples = key_frequency(samples)
    if freq:
        lines.append("| 파라미터 키 | 등장 빈도 | 관찰된 값 예시 |")
        lines.append("|---|---|---|")
        for k, n in freq.most_common(12):
            ex = ", ".join(f"`{v}`" for v in examples[k][:5])
            lines.append(f"| `{k}` | {n} | {ex} |")
    else:
        lines.append("- 관찰된 UTM/트래킹 파라미터 없음 (랜딩 URL 이 있어도 값이 비어있거나 리다이렉트/단축 URL 일 가능성)")
    lines.append("")
    lines.append(
        "> ⚠️ **베스트에포트 관찰 데이터입니다.** 위 표는 수집된 광고의 `link_url` 을 그대로 파싱한 결과이며, "
        "\"캠페인/그룹/소재명 규칙을 이렇게 쓴다\"고 단정하지 않습니다. 리다이렉트 체인·단축 URL·클릭ID(fbclid 등)만 있고 "
        "utm_campaign/utm_content 값이 아예 없으면 규칙을 유추할 근거 자체가 부족합니다. 자사 URL 은 직접 설계하므로 "
        "신뢰도가 높지만, 경쟁사는 낮을 수 있습니다. 실제 명명 규칙 추정은 이 표를 보고 Claude 가 패턴이 보일 때만 "
        "제시합니다 (SKILL.md Step 7 참고)."
    )
    lines.append("")
    return "\n".join(lines)


def save_samples_json(out_path, samples):
    out_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("사용: python3 utm_pattern.py <metadata.json 경로>")
    items = json.loads(open(sys.argv[1], encoding="utf-8").read())
    samples = extract_utm_samples(items)
    freq, examples = key_frequency(samples)
    print(f"샘플 {len(samples)}건")
    for k, n in freq.most_common():
        print(f"  {k}: {n}건 · 예시: {examples[k][:3]}")
