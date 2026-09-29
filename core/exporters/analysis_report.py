"""Shared escaped presentation for app and portable HTML."""
from html import escape


def esc(value):
    return escape(str(value or ""))


def summary_html(analysis):
    sections = analysis.get("sections", [])
    conclusions = [s["items"][0] for s in sections[:3] if s["items"]]
    actions = sections[3]["items"] if len(sections) > 3 else []
    return '<div><h2>AI 핵심 결론·우선 실행</h2><p>선택 자료 기반 AI 해석·가설</p><h3>핵심 결론</h3><ul>' + ''.join('<li>' + esc(i["title"]) + ' · ' + esc(i["interpretation"]) + '</li>' for i in conclusions) + '</ul><h3>우선 실행</h3><ol>' + ''.join('<li>' + esc(i["action"]) + '</li>' for i in actions[:3]) + '</ol><p>근거와 제약은 마지막 AI 종합 분석에서 확인하세요.</p></div>'


def analysis_html(analysis):
    from core.exporters.visual_report import link
    output = ['<p>AI 해석·제안 · ' + esc(analysis.get("created", "")[:10]) + ' · ' + esc(analysis.get("model")) + '</p>']
    brief = analysis.get("brief", {})
    output.append('<p>' + esc(' · '.join(brief.get(k, '') for k in ("market", "region", "period", "goal"))) + '</p>')
    for section in analysis.get("sections", []):
        output.append('<details><summary>' + esc(section["title"]) + '</summary>')
        if section.get("missing"): output.append('<p>' + esc(section["missing"]) + '</p>')
        for item in section["items"]:
            output.append('<article><h3>' + esc(item["title"]) + '</h3>')
            for field, label in (("observation", "관측·기사 주장"), ("interpretation", "AI 해석·가설"), ("action", "실행"), ("audience", "고객 상황"), ("message", "메시지·소재"), ("channel", "채널 역할"), ("landing", "랜딩"), ("validation", "검증 방법"), ("limitation", "제약·추가 확인")):
                if item.get(field): output.append('<p><strong>' + ("관측·기사 주장" if field == "observation" else label) + '</strong> · ' + esc(item[field]) + '</p>')
            output.append('<details><summary>근거 확인 · 인용 일치 검증 / 해석 타당성은 검토 필요</summary>')
            for ref in item["evidence"]:
                output.append('<blockquote>' + esc(ref["quote"]) + '</blockquote><p>' + esc(ref["kind"]) + ' · ' + esc(ref.get("date")) + ' ' + link(ref["source"], "출처") + '</p>')
            output.append('</details></article>')
        output.append('</details>')
    return ''.join(output)
