"""Shared escaped presentation for app and portable HTML."""
from html import escape
from config.theme import COLORS

FIELDS = (("observation", "관측·기사 주장"), ("interpretation", "AI 해석·가설"), ("action", "실행"),
          ("audience", "고객 상황"), ("message", "메시지·소재"), ("channel", "채널 역할"), ("landing", "랜딩"),
          ("validation", "검증 방법"), ("limitation", "제약·추가 확인"))

# 앱(st.markdown)과 HTML 보고서 모두에서 쓰도록 .ai-analysis 범위로 한정한 스타일.
CSS = (f"<style>.ai-analysis{{max-width:960px}}"
       f".ai-analysis .ai-meta{{color:{COLORS['text_dim']};font-size:13px;margin:4px 0}}"
       f".ai-analysis details{{margin:0;padding:14px 0;border-bottom:1px solid {COLORS['input_border']}}}"
       f".ai-analysis summary{{cursor:pointer;font-weight:600;font-size:17px}}"
       f".ai-analysis .ai-item{{padding:18px 0 6px}}.ai-analysis .ai-item+.ai-item{{border-top:1px solid {COLORS['border']}}}"
       f".ai-analysis .ai-item h4{{font-size:16px;margin:0 0 12px;color:{COLORS['text']}}}"
       f".ai-analysis .ai-fields{{display:grid;grid-template-columns:8.5em minmax(0,1fr);gap:8px 20px;margin:0}}"
       f".ai-analysis .ai-fields dt{{color:{COLORS['text_dim']};font-size:13px;font-weight:500;padding-top:2px}}"
       f".ai-analysis .ai-fields dt.ai-hypo{{color:{COLORS['accent_hover']}}}"
       f".ai-analysis .ai-fields dd{{margin:0;font-size:15px;line-height:1.6;color:{COLORS['text']};overflow-wrap:anywhere}}"
       f".ai-analysis .ai-cite{{font-size:13px;color:{COLORS['text_dim']};margin:12px 0 0}}"
       f".ai-analysis a{{color:{COLORS['accent_hover']}}}"
       f".ai-analysis .ai-sources{{padding-left:28px;margin:8px 0}}.ai-analysis .ai-sources li{{padding:10px 0;border-bottom:1px solid {COLORS['border']}}}"
       f".ai-analysis .ai-sources q{{display:block;color:{COLORS['text']};quotes:none}}"
       f"@media(max-width:600px){{.ai-analysis .ai-fields{{grid-template-columns:1fr;gap:2px}}.ai-analysis .ai-fields dd{{margin-bottom:10px}}}}"
       f"@media print{{.ai-analysis .ai-fields dd,.ai-analysis .ai-item h4,.ai-analysis .ai-sources q{{color:black}}}}</style>")


def esc(value):
    # 빈 줄이 있으면 st.markdown이 HTML 블록을 끊으므로 줄바꿈은 <br>로 바꾼다.
    return escape(str(value or "")).replace("\r", "").replace("\n", "<br>")


def summary_html(analysis):
    sections = analysis.get("sections", [])
    conclusions = [s["items"][0] for s in sections[:3] if s["items"]]
    actions = sections[3]["items"] if len(sections) > 3 else []
    return '<div><h2>AI 핵심 결론·우선 실행</h2><p>선택 자료 기반 AI 해석·가설</p><h3>핵심 결론</h3><ul>' + ''.join('<li>' + esc(i["title"]) + ' · ' + esc(i["interpretation"]) + '</li>' for i in conclusions) + '</ul><h3>우선 실행</h3><ol>' + ''.join('<li>' + esc(i["action"]) + '</li>' for i in actions[:3]) + '</ol><p>근거와 제약은 마지막 AI 종합 분석에서 확인하세요.</p></div>'


def analysis_html(analysis):
    from core.exporters.visual_report import link
    brief = analysis.get("brief", {})
    output = [CSS, '<div class="ai-analysis"><p class="ai-meta">AI 해석·제안 · ' + esc(analysis.get("created", "")[:10]) + ' · ' + esc(analysis.get("model"))
              + '<br>' + esc(' · '.join(brief.get(k, '') for k in ("market", "region", "period", "goal"))) + '</p>']
    refs = {}  # (evidence id, quote) → 번호. 같은 인용은 한 번만 근거 목록에 싣는다.
    for section in analysis.get("sections", []):
        output.append('<details><summary>' + esc(section["title"]) + f' <span class="ai-meta">· {len(section["items"])}개</span></summary>')
        if section.get("missing"): output.append('<p class="ai-meta">추가 확인 필요 · ' + esc(section["missing"]) + '</p>')
        for n, item in enumerate(section["items"], 1):
            output.append(f'<article class="ai-item"><h4>{n}. ' + esc(item["title"]) + '</h4><dl class="ai-fields">')
            for field, label in FIELDS:
                if item.get(field):
                    output.append(f'<dt{" class=ai-hypo" if field == "interpretation" else ""}>{label}</dt><dd>' + esc(item[field]) + '</dd>')
            numbers = [refs.setdefault((ref.get("id"), ref["quote"]), len(refs) + 1) for ref in item["evidence"]]
            output.append('</dl><p class="ai-cite">근거 ' + ' '.join(f'<a href="#ai-ref-{i}">[{i}]</a>' for i in dict.fromkeys(numbers)) + '</p></article>')
        output.append('</details>')
    evidence = {}
    for section in analysis.get("sections", []):
        for item in section["items"]:
            for ref in item["evidence"]:
                evidence.setdefault(refs[(ref.get("id"), ref["quote"])], ref)
    if evidence:
        output.append(f'<details><summary>근거 목록 <span class="ai-meta">· {len(evidence)}개 · 인용 일치만 검증했으며 해석 타당성은 검토가 필요합니다</span></summary><ol class="ai-sources">')
        for number, ref in sorted(evidence.items()):
            output.append(f'<li id="ai-ref-{number}"><q>' + esc(ref["quote"]) + '</q><span class="ai-meta">' + esc(ref.get("kind"))
                          + (' · ' + esc(str(ref["date"])[:10]) if ref.get("date") else '') + (' · ' + link(ref["source"], "출처") if link(ref.get("source"), "출처") else '') + '</span></li>')
        output.append('</ol></details>')
    output.append('</div>')
    return ''.join(output)
