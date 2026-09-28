"""외부 라이브러리·네트워크 없이 열리는 그래프·이미지 중심 HTML."""
import base64
import html
from datetime import date
from urllib.parse import urlsplit
from config.theme import COLORS
from core.evidence_store import read_bytes
from core.result_insights import monthly_values, trend_facts, news_sections


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


def fact_list(series):
    return '<ul class="facts">' + ''.join(f'<li><strong>{esc(f["항목"])}</strong> {esc(f["관측 사실"])}</li>' for f in trend_facts(series)) + '</ul>'


class Images:
    def __init__(self):
        self.used = 0
        self.cache = {}

    def render(self, row):
        images = [a for a in row.get("assets", []) if a.get("filename", "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))]
        for asset in images:
            name = asset["filename"]
            key = (name, asset.get("sha256"))
            data = self.cache.get(key)
            if data is None:
                data = read_bytes(asset)
            if data is None: continue
            if self.used + len(data) > 20*1024**2:
                return '<div class="no-image">HTML 이미지 20MB 한도 · ZIP 원본 확인</div>'
            self.cache[key] = data
            self.used += len(data)
            ext = name.rsplit(".", 1)[-1].lower()
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            return f'<img loading="lazy" src="data:image/{mime};base64,{base64.b64encode(data).decode()}" alt="{esc(row.get("brand", ""))} · {esc(row.get("kind", ""))} 저장 이미지">'
        return '<div class="no-image">저장 이미지 없음 · 원문 링크 확인</div>'


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
        groups = []
        for group in section["groups"]:
            references = ''.join('<li>' + esc(r.get("published_at", "")) + ' · ' + link(r.get("source_url"), r.get("title") or group["title"]) + '</li>' for r in group["articles"])
            groups.append('<article class="news-item"><h4>' + esc(group["title"]) + '</h4><p>' + esc(group["excerpt"] or "발췌 미제공") + '</p><details><summary>출처 ' + str(len(group["articles"])) + '건 · 제목 유사 기사</summary><ul>' + references + '</ul></details></article>')
        output.append('<details class="news-section" open><summary>' + esc(section["title"]) + f' <span class="muted">{section["count"]}건</span></summary>' + ''.join(groups) + '</details>')
    return ''.join(output)


def gallery(rows, images):
    brands = list(dict.fromkeys(r.get("brand", "") for r in rows))
    return ''.join('<details' + (' open' if index == 0 else '') + '><summary>' + esc(brand) + f' · {sum(r.get("brand", "") == brand for r in rows)}건</summary>' +
                   cards([r for r in rows if r.get("brand", "") == brand], images) + '</details>' for index, brand in enumerate(brands))


def utm_summary(rows):
    if not rows: return ""
    compact = [{k: (str(v)[:160] + "…" if k == "관측값" and len(str(v)) > 160 else v) for k, v in row.items()
                if k in ("브랜드", "UTM 항목", "관측값", "추정 구조", "근거 URL 수")} for row in rows]
    return '<p class="muted">관측된 URL 표본의 문자 구조 추정입니다. 전체 운영 규칙이나 토큰의 의미를 확정하지 않습니다.</p>' + table(compact) + '<details><summary>전체 관측값·근거 URL·표본 한계</summary>' + table(rows) + '</details>'


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
                trend.append('<h3>' + esc(s["name"]) + '</h3>' + fact_list({**s, "start": compare["start"], "end": compare["end"]}))
        elif part.get("series"):
            s = part["series"]
            market.append('<h3>' + esc(s["keyword"]) + '</h3><p class="muted">' + esc(s["start"] + " ~ " + s["end"]) + ' · 검색어별 별도 최고 월=100</p>' + chart([s], s["start"], s["end"]) + fact_list(s))
    section("trend", "브랜드 검색 추이", ''.join(trend))
    section("market", "시장 검색어 추이", ''.join(market))
    news = [r for r in records if r["kind"] == "뉴스"]
    if news:
        section("news", "뉴스 주제별 요약", '<p class="muted">제목의 주제·유사도로 묶은 대표 발췌입니다. 호재·악재·인과관계를 판정하지 않습니다. 출처를 펼쳐 전체 기사를 확인하세요.</p>' + news_html(news) + ('<details><summary>AI 선정 핵심 근거</summary>' + table(result.get("news_digest", [])) + '</details>' if result.get("news_digest") else ''))
    section("ads", "광고 소재", '<p class="muted">수집된 광고 표본 · 브랜드별로 펼쳐 이미지·문구·랜딩 확인</p>' + gallery([r for r in records if r["kind"] == "광고"], images) if any(r["kind"] == "광고" for r in records) else '')
    captures = [r for r in records if r["kind"] == "검색 화면"]
    if captures:
        section("search", "검색 화면 관측", '<p class="muted">관측된 광고만 표시합니다. 미관측·판독 불가 상태와 캡처는 원본 데이터에 보존합니다.</p>' + table(tables.get("08_검색화면광고관측", [])) + table(tables.get("09_검색광고문구", [])) + ''.join('<details><summary>' + esc(r.get("keyword")) + ' · 저장 캡처</summary>' + images.render(r) + '</details>' for r in captures if r.get("ads") or (r.get("ai_read") or {}).get("ads")))
    section("utm", "브랜드별 UTM 구조", utm_summary(tables.get("12_브랜드별UTM구조", [])))
    media = [r for r in records if r["kind"] in ("홈페이지", "Instagram 게시물", "YouTube 게시물")]
    section("media", "공식 페이지·SNS", cards(media, images) if media else '')
    resources = result.get("stat_resources", [])
    section("resources", "맞춤 통계 자료 후보", resource_cards(resources))
    problems = [r for r in tables.get("18_수집상태", []) if r.get("상태") != "완료"]
    section("conditions", "수집 범위·상태", ('<details open><summary>일부 자료 수집 상태</summary>' + table(problems) + '</details>' if problems else '') + '<details><summary>수집 조건과 시각</summary>' + table(tables.get("17_수집조건", [])) + '</details>')
    raw = ''.join('<details><summary>' + esc(name) + f' · {len(rows)}행</summary>' + table(rows) + '</details>' for name, rows in tables.items())
    css = """*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.65 system-ui,'Malgun Gothic',sans-serif}main{max-width:1280px;margin:auto;padding:40px 28px}h1{font-size:32px;line-height:1.3;margin:12px 0}h2{font-size:24px;margin:0 0 20px}h3{font-size:18px}h4{font-size:16px;margin:0 0 8px}p{margin:8px 0 16px}section{padding:36px 0;border-top:1px solid var(--border)}a{color:var(--accent);text-decoration:underline;text-underline-offset:3px;overflow-wrap:anywhere}nav{display:flex;gap:12px 20px;flex-wrap:wrap;padding:18px 0}nav a{font-size:14px}.muted,dt{color:var(--dim)}.eyebrow{font-size:13px;color:var(--accent);letter-spacing:.06em}.notice{border-left:3px solid var(--accent);padding:8px 16px;background:var(--surface);margin:18px 0}.brand-grid,.media-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:20px}.brand,.media-card{border:1px solid var(--border);background:var(--surface);min-width:0}.brand,.card-body{padding:20px}.brand h3{margin-top:0}dl{margin:0}dt{font-size:13px}dd{font-size:20px;margin:0 0 12px;overflow-wrap:anywhere}.media-card img{width:100%;height:250px;object-fit:contain;background:var(--bg)}.copy{white-space:pre-wrap;overflow-wrap:anywhere}.links{display:flex;gap:16px;flex-wrap:wrap}.no-image{height:180px;display:grid;place-items:center;color:var(--dim);border-bottom:1px solid var(--border);padding:24px}.chart{margin:20px 0}.trend-chart{width:100%;height:auto;min-height:200px}svg text{fill:var(--dim);font:13px system-ui}.legend{display:flex;gap:20px;flex-wrap:wrap}.legend i{display:inline-block;width:18px;height:3px;margin:0 7px 4px 0}.facts{padding-left:22px}.facts li{margin:7px 0}.facts strong{display:inline-block;min-width:105px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;min-width:90px;max-width:580px;overflow-wrap:anywhere;white-space:pre-wrap}th{color:var(--dim);font-weight:500}details{margin:12px 0;padding:12px 0;border-bottom:1px solid var(--border)}summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}.news-section>summary{font-size:18px}.news-item{padding:20px 0;margin-left:18px;max-width:960px}.news-item+article{border-top:1px solid var(--border)}.news-item p{max-width:85ch}img{max-width:100%}.view-radio{position:absolute;width:1px;height:1px;opacity:0}.view-label{display:inline-block;padding:12px 20px;border-bottom:2px solid transparent;cursor:pointer;margin:12px 0 0}.view-radio:focus-visible+label{outline:2px solid var(--accent)}#overview:checked+label,#raw:checked+label{border-color:var(--accent);color:var(--accent)}#raw-panel{display:none}#raw:checked~#raw-panel{display:block}#raw:checked~#overview-panel{display:none}footer{margin:36px 0;color:var(--dim);font-size:13px}@media(max-width:600px){main{padding:24px 16px}h1{font-size:26px}.media-grid,.brand-grid{grid-template-columns:1fr}section{padding:24px 0}.facts strong{display:block}}@media print{body{background:white;color:black}nav,.view-label,.view-radio{display:none}#overview-panel{display:block!important}#raw-panel{display:none!important}.media-card,figure{break-inside:avoid}a{color:inherit}.muted,dt{color:#444}svg text{fill:#444}}
""".replace("\\+", "")
    tokens = f':root{{--bg:{COLORS["bg"]};--surface:{COLORS["bg_elevated"]};--text:{COLORS["text"]};--dim:{COLORS["text_dim"]};--accent:{COLORS["accent_hover"]};--border:{COLORS["input_border"]}}}'
    title = result.get("inputs", {}).get("project") or session.get("name") or session.get("brand_name", "ADetect")
    notices = ('<div class="notice">SAMPLE — 실제 수집 자료가 아닙니다.</div>' if result.get("sample_sources") else '')
    if result.get("inputs", {}).get("date_mixed"):
        notices += '<div class="notice">수집일 혼합 · ' + esc(', '.join(result["inputs"].get("collection_dates", []))) + ' · 같은 시점의 비교가 아닙니다.</div>'
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + ' · ADetect</title><style>' + tokens + css + '</style></head><body><main><header><p class="eyebrow">ADETECT / RESEARCH COLLECTION</p><h1>' + esc(title) + '</h1><p class="muted">' + esc(session.get("campaign") or "브랜드 자료 모음") + f' · 선택 자료 {len(records)}건</p>' + notices + '</header><input class="view-radio" type="radio" name="view" id="overview" checked><label class="view-label" for="overview">시각 요약</label><input class="view-radio" type="radio" name="view" id="raw"><label class="view-label" for="raw">원본 데이터</label><div id="overview-panel"><nav aria-label="보고서 목차">' + ''.join(nav) + '</nav><p class="muted">검색 추이는 상대지수이며 검색 횟수가 아닙니다. 누락 월은 0이 아닙니다. 서로 다른 요청의 지수 크기는 비교하지 않습니다.</p>' + ''.join(sections) + '</div><div id="raw-panel"><h2>선택 자료의 원본 데이터</h2><p class="muted">현재 선택·뉴스 필터·수집 버전과 동일한 상세 자료입니다. Excel에서도 확인할 수 있습니다.</p>' + raw + '</div><footer>수집된 표본과 원문 기록입니다. 기사·브랜드의 주장을 검증된 사실이나 성과로 해석하지 않습니다.</footer></main></body></html>'
