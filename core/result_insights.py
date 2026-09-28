"""화면과 파일이 공유하는 관측값 요약. 외부 호출·인과 해석 없이 계산한다."""
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
import math
import re


def monthly_values(series):
    values = {}
    for row in series.get("rows", []):
        try:
            month = str(row["date"])[:7]
            date.fromisoformat(month + "-01")
            value = float(row["search_index"])
            if not math.isfinite(value) or not 0 <= value <= 100:
                continue
            if series.get("start") and month < series["start"][:7]:
                continue
            if series.get("end") and month > series["end"][:7]:
                continue
            values.setdefault(month, value)
        except (KeyError, TypeError, ValueError):
            continue
    return dict(sorted(values.items()))


def trend_facts(series):
    values = monthly_values(series)
    if not values:
        return []
    name = series.get("name") or series.get("keyword") or "검색어"
    high, low = max(values.values()), min(values.values())
    facts = []
    def add(kind, text):
        facts.append({"대상": name, "항목": kind, "관측 사실": text, "제공 월수": len(values)})
    if high == low:
        add("변동 없음", f"제공된 {len(values)}개월의 지수가 모두 {high:g}입니다.")
    else:
        for label, value in (("최고", high), ("최저", low)):
            months = [m for m, v in values.items() if v == value]
            add(label, f"{', '.join(months)} · 지수 {value:g}" + (f" (공동 {label} {len(months)}개월)" if len(months) > 1 else ""))
    rises = []
    for month, value in values.items():
        year, m = map(int, month.split("-"))
        previous = f"{year if m > 1 else year-1:04d}-{m-1 if m > 1 else 12:02d}"
        if previous in values and value > values[previous]:
            rises.append((value-values[previous], month, previous, values[previous], value))
    if rises:
        delta = max(x[0] for x in rises)
        tied = [x for x in rises if math.isclose(x[0], delta, abs_tol=1e-9)]
        add("최대 전월 상승", "; ".join(f"{prev} → {month} · {before:g} → {after:g} (+{change:.2f} 지수 포인트)" for change, month, prev, before, after in tied))
    if series.get("start") and series.get("end"):
        y1, m1 = map(int, series["start"][:7].split("-"))
        y2, m2 = map(int, series["end"][:7].split("-"))
        missing = (y2-y1)*12 + m2-m1 + 1-len(values)
        if missing > 0:
            add("범위", f"요청 기간 중 {missing}개월 미제공 · 제공된 달에서만 계산했습니다.")
    return facts


def all_trend_facts(parts):
    rows = []
    for part in parts.values():
        compare = part.get("comparison")
        if compare:
            for series in compare.get("series", []):
                rows += [{"구분": "브랜드 공동 기준", **r} for r in trend_facts({**series, "start": compare["start"], "end": compare["end"]})]
        elif part.get("series"):
            rows += [{"구분": "검색어별 별도 기준", **r} for r in trend_facts(part["series"])]
    return rows


def annual_extremes(series):
    """연도별 제공 월에서만 최고·최저 계산. 공동값과 미제공 연도를 보존한다."""
    values = monthly_values(series)
    start = (series.get("start") or next(iter(values), ""))[:4]
    end = (series.get("end") or next(reversed(values), ""))[:4]
    if not start.isdigit() or not end.isdigit():
        return []
    rows = []
    for year in range(int(start), int(end) + 1):
        observed = {m: v for m, v in values.items() if m.startswith(str(year))}
        def label(extreme):
            if not observed: return "미제공"
            value = extreme(observed.values())
            months = [f"{int(m[5:7])}월" for m, v in observed.items() if v == value]
            return ", ".join(months) + f" · 지수 {value:g}"
        rows.append({"연도": str(year), "최저": label(min), "최고": label(max)})
    return rows


# 긍정/부정 영향은 추정하지 않는다. 제목의 명시적인 주제만 표시한다.
TOPICS = (
    ("리콜·분쟁·제재 보도", ("리콜", "소송", "과징금", "제재", "불매", "결함")),
    ("프로모션·혜택", ("프로모션", "할인", "혜택", "이벤트", "특가", "무이자")),
    ("실적·수주·투자 보도", ("실적", "성장", "증가", "감소", "적자", "흑자", "수주", "투자", "매출", "판매량")),
    ("신제품·서비스", ("출시", "신제품", "공개", "신차", "서비스")),
)


def news_sections(rows):
    """유사 제목은 대표 발췌와 출처 묶음으로. 서로 다른 기사는 주제 안에서 별도 유지."""
    from core.materials import timestamp
    buckets = defaultdict(list)
    for row in sorted(rows, key=timestamp, reverse=True):
        if row.get("kind") != "뉴스":
            continue
        title = row.get("title") or row.get("text", "").split("\n")[0]
        topic = next((name for name, words in TOPICS if any(w in title for w in words)), "기타 관련 보도")
        brands = ", ".join(sorted(row.get("found_brands") or [])) or "시장·기타"
        key = (topic, brands)
        normalized = re.sub(r"\W+", "", title.casefold())
        numbers = re.findall(r"\d+(?:[.,]\d+)*", title)
        group = next((g for g in buckets[key] if numbers == g["numbers"] and normalized and
                      SequenceMatcher(None, normalized, g["normalized"]).ratio() >= .78), None)
        if group is None:
            group = {"title": title, "excerpt": row.get("excerpt") or "\n".join(row.get("text", "").split("\n")[1:]),
                     "normalized": normalized, "numbers": numbers, "articles": []}
            buckets[key].append(group)
        group["articles"].append(row)
    sections = []
    for topic in [name for name, _ in TOPICS] + ["기타 관련 보도"]:
        subjects = [{"title": subject, "groups": groups, "count": sum(len(g["articles"]) for g in groups)}
                    for (category, subject), groups in buckets.items() if category == topic]
        if subjects:
            groups = [g for subject in subjects for g in subject["groups"]]
            sections.append({"title": topic, "subjects": subjects, "groups": groups,
                             "count": sum(s["count"] for s in subjects)})
    return sections
