"""외부 라이브러리·네트워크 없이 열리는 그래프·이미지 중심 HTML."""
import base64
import html
import os
import math
from datetime import date
from urllib.parse import urlsplit
from config.theme import COLORS
from core.evidence_store import read_bytes
from core.result_insights import monthly_values, trend_facts, news_sections, annual_extremes, headline, MULTI_BRAND


def esc(value):
    return html.escape(str(value if value is not None else "미제공"), quote=True)


def link(url, label="원문 보기"):
    from core.utm import masked
    try:
        u = urlsplit(str(url or ""))
        if u.scheme not in ("http", "https") or not u.netloc: return ""
    except ValueError:
        return ""
    return f'<a href="{esc(masked(url))}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def table(rows):
    if not rows: return ""
    columns = list(dict.fromkeys(k for row in rows for k in row))
    def cell(value):
        if isinstance(value, str) and value.startswith(("https://", "http://")) and "\n" not in value:
            return link(value, value if len(value) < 64 else value[:61] + "…")
        if isinstance(value, (list, dict)):
            from core.exporters.facts_report import scalar
            return esc(scalar(value))
        return esc(value)
    return '<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{esc(c)}</th>' for c in columns) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{cell(row.get(c))}</td>' for c in columns) + '</tr>' for row in rows) + '</tbody></table></div>'


def chart(series, start, end):
    """같은 기준 시리즈만 그린다. 누락 월은 선을 끊고 공백으로 둔다."""
    values = [(s.get("name") or s.get("keyword", "검색어"), monthly_values({**s, "start": start, "end": end})) for s in series]
    if not any(v for _, v in values): return '<p class="muted">제공된 검색 추이 없음</p>'
    first, last = date.fromisoformat(start[:7] + "-01"), date.fromisoformat(end[:7] + "-01")
    count = (last.year-first.year)*12 + last.month-first.month + 1
    if count < 1: return ""
    months = [f'{(first.year*12+first.month-1+i)//12:04d}-{(first.year*12+first.month-1+i)%12+1:02d}' for i in range(count)]
    palette = [COLORS[k] for k in ("accent_hover", "data_blue", "success", "warning", "text")]
    svg = ['<svg class="trend-chart" viewBox="0 0 960 300" role="img" aria-label="월간 상대 검색지수. 누락 월은 선을 끊어 표시합니다.">']
    for level in (0, 25, 50, 75, 100):
        y = 246-level*2
        svg.append(f'<line x1="48" x2="934" y1="{y}" y2="{y}" stroke="{COLORS["input_border"]}"/><text x="35" y="{y+5}" text-anchor="end">{level}</text>')
    def x(i): return 48 + i*886/max(count-1, 1)
    for i, month in enumerate(months):
        if i in (0, count-1) or (i % max(1, count//6) == 0 and i < count-3):
            anchor = "start" if i == 0 else "end" if i == count-1 else "middle"
            svg.append(f'<text x="{x(i):.2f}" y="277" text-anchor="{anchor}">{month}</text>')
    legend = []
    for index, (name, data) in enumerate(values):
        color = palette[index % len(palette)]
        legend.append(f'<span><i style="background:{color}"></i>{esc(name)}</span>')
        segment = []
        def flush():
            if len(segment) > 1:
                svg.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            segment.clear()
        for i, month in enumerate(months):
            if month not in data:
                flush()
                continue
            value = data[month]
            segment.append(f'{x(i):.2f},{246-value*2:.2f}')
            svg.append(f'<circle cx="{x(i):.2f}" cy="{246-value*2:.2f}" r="3" fill="{color}"><title>{esc(name)} · {month}: {value:g}</title></circle>')
        flush()
    return '<div class="chart"><div class="legend">' + ''.join(legend) + '</div>' + ''.join(svg) + '</svg></div>'


def fact_list(series, annual=False):
    facts = [f for f in trend_facts(series) if not annual or f["항목"] not in ("최고", "최저", "변동 없음")]
    return (table(annual_extremes(series)) if annual else '') + '<ul class="facts">' + ''.join(f'<li><strong>{esc(f["항목"])}</strong> {esc(f["관측 사실"])}</li>' for f in facts) + '</ul>'


class Images:
    def __init__(self):
        self.used = 0
        self.cache = {}
        try:
            mb = float(os.getenv("ADETECT_HTML_IMAGE_MAX_MB", "20"))
            if not math.isfinite(mb) or mb <= 0: raise ValueError
        except ValueError:
            mb = 20
        self.maximum = int(mb*1024**2)

    def render(self, row):
        from core.exporters.image_preview import compress
        unavailable_preview = False
        images = sorted([a for a in row.get("assets", []) if a.get("filename", "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))], key=lambda a: a.get("role") != "썸네일")
        for asset in images:
            name = asset["filename"]
            key = (name, asset.get("sha256"))
            if key not in self.cache:
                original = read_bytes(asset)
                data = compress(original) if original else None
                self.cache[key] = base64.b64encode(data).decode() if data else None
            encoded = self.cache[key]
            if not encoded:
                unavailable_preview = True
                continue
            if self.used + len(encoded) > self.maximum:
                return '<div class="no-image">미리보기 용량 한도 · ZIP 원본 확인</div>'
            self.used += len(encoded)
            role = '영상 썸네일' if row.get("format") == "video" or asset.get("role") == "썸네일" else '저장 이미지 미리보기'
            return f'<img loading="lazy" src="data:image/jpeg;base64,{encoded}" alt="{esc(row.get("brand", ""))} · {role}">'
        if unavailable_preview:
            return '<div class="no-image">미리보기 생성 불가 · ZIP 보관 상태 또는 원문 확인</div>'
        message = '영상 썸네일 없음 · 재수집 또는 원문 확인' if row.get("format") == "video" else '저장 이미지 없음 · 원문 링크 확인'
        return '<div class="no-image">' + message + '</div>'


def cards(rows, images):
    output = []
    for row in rows:
        fields = [row.get("format"), row.get("start_date") or row.get("published_at"), row.get("cta")]
        meta = " · ".join(str(v) for v in fields if v)
        text = row.get("text", "")
        body = f'<p class="copy">{esc(text[:500])}</p>'
        if len(text) > 500:
            body += '<details><summary>전체 문구 보기</summary><p class="copy">' + esc(text) + '</p></details>'
        output.append('<article class="media-card">' + images.render(row) + '<div class="card-body"><p class="eyebrow">' + esc(row.get("brand", "")) + ' · ' + esc(row.get("kind")) + '</p><p class="muted">' + esc(meta) + '</p>' + body +
                      '<div class="links">' + link(row.get("source_url")) + link(row.get("landing_url"), "랜딩 페이지 ↗") + '</div></div></article>')
    return '<div class="media-grid">' + ''.join(output) + '</div>'


def news_html(rows):
    output = []
    for section in news_sections(rows):
        subjects = []
        for subject in section["subjects"]:
            groups = []
            for group in subject["groups"]:
                representative, *others = group["articles"]
                # 여러 브랜드 소구분에서는 어떤 브랜드가 함께 언급됐는지 제목 옆에 표시한다.
                brands = ' <span class="muted">· ' + esc(', '.join(group["brands"])) + '</span>' if subject["title"] == MULTI_BRAND else ''
                groups.append('<li><div class="news-headline"><span>' + link(representative.get("source_url"), group["title"]) + brands + '</span><time>' + esc((representative.get("published_at") or "날짜 미제공")[:10]) + '</time></div>' +
                              ('<details><summary>유사 기사 ' + str(len(others)) + '건 더 보기</summary><ul>' + ''.join('<li>' + link(r.get("source_url"), headline(r) or group["title"]) + ' <span class="muted">' + esc((r.get("published_at") or '')[:10]) + '</span></li>' for r in others) + '</ul></details>' if others else '') + '</li>')
            # 첫 다섯 개만 먼저 읽고 필요하면 나머지를 펼친다. 모든 원문은 보존한다.
            content = '<ul class="news-list">' + ''.join(groups[:5]) + '</ul>'
            if len(groups) > 5:
                content += '<details><summary>나머지 제목 ' + str(len(groups)-5) + '개 더 보기</summary><ul class="news-list">' + ''.join(groups[5:]) + '</ul></details>'
            subjects.append('<details class="news-subject"><summary>' + esc(subject["title"]) + f' · {len(groups)}개 주제 / 기사 {subject["count"]}건</summary>' + content + '</details>')
        output.append('<details class="news-section"><summary>' + esc(section["title"]) + f' <span class="muted">· {len(section["groups"])}개 주제 / 기사 {section["count"]}건</span></summary>' + ''.join(subjects) + '</details>')
    return ''.join(output)


def gallery(rows, images):
    brands = list(dict.fromkeys(r.get("brand", "") for r in rows))
    return ''.join('<details><summary>' + esc(brand) + f' · {sum(r.get("brand", "") == brand for r in rows)}건</summary>' +
                   cards([r for r in rows if r.get("brand", "") == brand], images) + '</details>' for brand in brands)


def utm_summary(rows):
    if not rows: return ""
    from core.utm import display_structures
    return '<p class="muted">브랜드별 UTM 항목과 실제 관측값입니다. 전체 URL·문자 구조·표본 근거는 Excel에서 확인할 수 있습니다.</p>' + table(display_structures(rows))


def resource_cards(rows):
    return ''.join('<article class="news-item"><h3>' + link(r.get("출처"), r.get("자료명", "자료")) + '</h3><p>' + esc(r.get("추천 이유 (AI)")) + '</p><details><summary>AI 검색 근거·신뢰도</summary><p>' + esc(r.get("검색 근거")) + '</p><p class="muted">' + esc(r.get("방식")) + ' · ' + esc(r.get("신뢰도")) + '</p></details></article>' for r in rows)


def report(session, result, tables):
    records, parts = result.get("records", []), result.get("parts", {})
    images = Images()
    sections, nav = [], []
    def section(identity, title, content):
        if not content: return
        nav.append(f'<a href="#{identity}">{esc(title)}</a>')
        sections.append(f'<section id="{identity}"><h2>{esc(title)}</h2>{content}</section>')
    comparisons = result.get("comparison", [])
    summary = []
    for row in comparisons:
        summary.append('<article class="brand"><h3>' + esc(row.get("브랜드")) + '</h3><dl>' + ''.join('<dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd>' for k, v in row.items() if k not in ("브랜드", "검색어 묶음")) + '</dl><p class="muted">' + esc(row.get("검색어 묶음", "")) + '</p></article>')
    section("brands", "브랜드 비교", '<div class="brand-grid">' + ''.join(summary) + '</div>' if summary else '')
    trend, market = [], []
    for part in parts.values():
        compare = part.get("comparison")
        if compare:
            from core.projects import comparison_signature
            current = result.get("inputs", {}).get("brands", [])
            if current and compare.get("signature") != comparison_signature(current):
                trend.append('<div class="notice">현재 프로젝트와 수집 당시 브랜드·검색어 구성이 다릅니다. 아래 차트는 수집 당시 기준이며 새 비교에는 재수집이 필요합니다.</div>')
            trend.append('<p class="muted">' + esc(compare["start"] + " ~ " + compare["end"]) + ' · 한 요청 안의 전체 최고 월=100</p>' + chart(compare["series"], compare["start"], compare["end"]))
            for s in compare["series"]:
                trend.append('<h3>' + esc(s["name"]) + ' · 연도별 최저·최고</h3>' + fact_list({**s, "start": compare["start"], "end": compare["end"]}, annual=True))
        elif part.get("series"):
            s = part["series"]
            market.append('<h3>' + esc(s["keyword"]) + '</h3><p class="muted">' + esc(s["start"] + " ~ " + s["end"]) + ' · 검색어별 별도 최고 월=100</p>' + chart([s], s["start"], s["end"]) + fact_list(s))
    section("trend", "브랜드 검색 추이", ''.join(trend))
    section("market", "시장 검색어 추이", ''.join(market))
    news = [r for r in records if r["kind"] == "뉴스"]
    if news:
        section("news", "뉴스 주제별 요약", '<p class="muted">주제 → 브랜드(여러 브랜드 동시 언급·시장·기타) → 최신 기사 제목 순으로 펼쳐보세요. 주제는 제목에 쓰인 표현으로만 나눕니다. 비슷한 제목은 묶고 발췌문은 Excel에 담았습니다. 시장·기타는 브랜드 직접 언급이 없는 기사이며, 시장 전체를 대표하지 않습니다.</p>' + news_html(news) + ('<details><summary>AI 선정 핵심 근거</summary>' + table(result.get("news_digest", [])) + '</details>' if result.get("news_digest") else ''))
    section("ads", "광고 소재", '<p class="muted">수집된 광고 표본 · 브랜드별로 펼쳐 이미지·문구·랜딩 확인</p>' + gallery([r for r in records if r["kind"] == "광고"], images) if any(r["kind"] == "광고" for r in records) else '')
    captures = [r for r in records if r["kind"] == "검색 화면"]
    if captures:
        from core.project_view import search_ad_rows
        # 네이버 광고 이동 주소는 길고 읽을 수 없어 HTML에서는 뺀다. Excel에는 링크를 유지한다.
        filtered = [{k: v for k, v in r.items() if k != "링크"} for r in tables.get("09_검색광고문구", [])]
        section("search", "검색 화면 관측", '<p class="muted">공식 도메인이 일치한 자사·경쟁사 광고만 표시합니다. 일반 검색어도 같은 기준을 적용합니다. 전체 광고 원문·판독 상태는 Excel에 보관합니다.</p>' + table(tables.get("08_검색화면광고관측", [])) + (table(filtered) if filtered else '<p class="muted">조건에 맞는 광고 문구 미관측</p>') + ''.join('<details><summary>' + esc(r.get("keyword")) + ' · 저장 캡처 (전체 화면)</summary>' + images.render(r) + '</details>' for r in captures if search_ad_rows([r], result.get("inputs", {}))))
    section("utm", "브랜드별 UTM 구조", utm_summary(tables.get("12_브랜드별UTM구조", [])))
    media = [r for r in records if r["kind"] in ("홈페이지", "YouTube 게시물")]
    instagram = [r for r in records if r["kind"] == "Instagram 게시물"]
    insta_links = ''.join('<li><strong>' + esc(r.get("brand")) + '</strong> · ' + link(r.get("source_url"), (r.get("published_at") or '')[:10] + ' 게시물 ↗') + '</li>' for r in instagram)
    section("media", "공식 페이지·SNS", (gallery(media, images) if media else '') + ('<details><summary>Instagram 최신 게시물 · ' + str(len(instagram)) + '건</summary><ul class="news-list">' + insta_links + '</ul></details>' if instagram else ''))
    resources = result.get("stat_resources", [])
    section("resources", "맞춤 통계 자료 후보", resource_cards(resources))
    problems = [r for r in tables.get("18_수집상태", []) if r.get("상태") != "완료"]
    section("conditions", "수집 범위·상태", ('<details><summary>일부 자료 수집 상태 · ' + str(len(problems)) + '개 항목 확인</summary>' + table(problems) + '</details>' if problems else '') + '<details><summary>수집 조건과 시각</summary>' + table(tables.get("17_수집조건", [])) + '</details>')
    css = """*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.65 system-ui,'Malgun Gothic',sans-serif}main{max-width:1280px;margin:auto;padding:40px 28px}h1{font-size:32px;line-height:1.3;margin:12px 0}h2{font-size:24px;margin:0 0 20px}h3{font-size:18px}h4{font-size:16px;margin:0 0 8px}p{margin:8px 0 16px}section{padding:36px 0;border-top:1px solid var(--border)}a{color:var(--accent);text-decoration:underline;text-underline-offset:3px;overflow-wrap:anywhere}nav{display:flex;gap:12px 20px;flex-wrap:wrap;padding:18px 0}nav a{font-size:14px}.muted,dt{color:var(--dim)}.eyebrow{font-size:13px;color:var(--accent);letter-spacing:.06em}.notice{border-left:3px solid var(--accent);padding:8px 16px;background:var(--surface);margin:18px 0}.brand-grid,.media-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:20px}.brand,.media-card{border:1px solid var(--border);background:var(--surface);min-width:0}.brand,.card-body{padding:20px}.brand h3{margin-top:0}dl{margin:0}dt{font-size:13px}dd{font-size:20px;margin:0 0 12px;overflow-wrap:anywhere}.media-card img{width:100%;height:250px;object-fit:contain;background:var(--bg)}.copy{white-space:pre-wrap;overflow-wrap:anywhere}.links{display:flex;gap:16px;flex-wrap:wrap}.no-image{height:180px;display:grid;place-items:center;color:var(--dim);border-bottom:1px solid var(--border);padding:24px}.chart{margin:20px 0}.trend-chart{width:100%;height:auto;min-height:200px}svg text{fill:var(--dim);font:13px system-ui}.legend{display:flex;gap:20px;flex-wrap:wrap}.legend i{display:inline-block;width:18px;height:3px;margin:0 7px 4px 0}.facts{padding-left:22px}.facts li{margin:7px 0}.facts strong{display:inline-block;min-width:105px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;min-width:90px;max-width:580px;overflow-wrap:anywhere;white-space:pre-wrap}th{color:var(--dim);font-weight:500}details{margin:12px 0;padding:12px 0;border-bottom:1px solid var(--border)}summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}.news-section>summary{font-size:18px}.news-item{padding:20px 0;margin-left:18px;max-width:960px}.news-item+article{border-top:1px solid var(--border)}.news-item p{max-width:85ch}img{max-width:100%}footer{margin:36px 0;color:var(--dim);font-size:13px}@media(max-width:600px){main{padding:24px 16px}h1{font-size:26px}.media-grid,.brand-grid{grid-template-columns:1fr}section{padding:24px 0}.facts strong{display:block}}@media print{body{background:white;color:black}nav{display:none}.media-card,figure{break-inside:avoid}a{color:inherit}.muted,dt{color:#444}svg text{fill:#444}}
"""
    css += """main{padding-bottom:100px}.news-subject{margin-left:20px}.news-list{list-style:none;padding:0;margin:12px 0}.news-list>li{padding:12px 0;border-bottom:1px solid var(--border)}.news-headline{display:flex;align-items:baseline;justify-content:space-between;gap:20px}.news-headline time{flex-shrink:0;color:var(--dim);font-size:13px}.fixed-footer{position:fixed;bottom:0;left:0;right:0;display:flex;justify-content:flex-end;background:var(--surface);border-top:1px solid var(--border);padding:10px max(20px,calc((100vw - 1224px)/2));z-index:10}.fixed-footer a{display:inline-block;padding:6px 16px;border:1px solid var(--border);text-decoration:none}section{scroll-margin-top:20px}a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px}summary:hover{color:var(--accent)}@media(max-width:600px){.news-headline{display:block}.news-headline time{display:block;margin-top:4px}.news-subject{margin-left:12px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{.fixed-footer{display:none}.brand,.media-card,.notice{background:white;color:black}}"""
    tokens = f':root{{--bg:{COLORS["bg"]};--surface:{COLORS["bg_elevated"]};--text:{COLORS["text"]};--dim:{COLORS["text_dim"]};--accent:{COLORS["accent_hover"]};--border:{COLORS["input_border"]}}}'
    title = result.get("inputs", {}).get("project") or session.get("name") or session.get("brand_name", "ADetect")
    notices = ('<div class="notice">SAMPLE — 실제 수집 자료가 아닙니다.</div>' if result.get("sample_sources") else '')
    if result.get("inputs", {}).get("date_mixed"):
        notices += '<div class="notice">수집일 혼합 · ' + esc(', '.join(result["inputs"].get("collection_dates", []))) + ' · 같은 시점의 비교가 아닙니다.</div>'
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'
            + esc(title) + ' · ADetect</title><style>' + tokens + css + '</style></head><body><main id="top"><header><p class="eyebrow">ADETECT / RESEARCH COLLECTION</p><h1>'
            + esc(title) + '</h1><p class="muted">' + esc(session.get("campaign") or "브랜드 자료 모음") + f' · 선택 자료 {len(records)}건</p>' + notices
            + '</header><nav aria-label="보고서 목차">' + ''.join(nav) + '</nav><p class="muted">검색 추이는 상대지수이며 검색 횟수가 아닙니다. 누락 월은 0이 아닙니다. 서로 다른 요청의 지수 크기는 비교하지 않습니다.</p>'
            + ''.join(sections) + '<footer>원본 데이터·전체 발췌·UTM 근거는 Excel, 원본 이미지는 ZIP에서 확인하세요. HTML 이미지는 용량을 줄인 미리보기입니다.<br>수집된 표본과 원문 기록입니다. 기사·브랜드의 주장을 검증된 사실이나 성과로 해석하지 않습니다.</footer></main><div class="fixed-footer"><a href="#top" aria-label="보고서 최상단으로 이동">↑ 최상단으로</a></div></body></html>')
