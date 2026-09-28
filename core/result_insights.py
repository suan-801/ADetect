"""화면과 파일이 공유하는 관측값 요약. 외부 호출·인과 해석 없이 계산한다."""
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
import html
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


def index_label(value):
    """표시용 지수: 소수 둘째 자리까지. 계산·동률 판단은 원래 값으로 한다."""
    return f"{round(value, 2):g}"


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
        add("변동 없음", f"제공된 {len(values)}개월의 지수가 모두 {index_label(high)}입니다.")
    else:
        for label, value in (("최고", high), ("최저", low)):
            months = [m for m, v in values.items() if v == value]
            add(label, f"{', '.join(months)} · 지수 {index_label(value)}" + (f" (공동 {label} {len(months)}개월)" if len(months) > 1 else ""))
    rises = []
    for month, value in values.items():
        year, m = map(int, month.split("-"))
        previous = f"{year if m > 1 else year-1:04d}-{m-1 if m > 1 else 12:02d}"
        if previous in values and value > values[previous]:
            rises.append((value-values[previous], month, previous, values[previous], value))
    if rises:
        delta = max(x[0] for x in rises)
        tied = [x for x in rises if math.isclose(x[0], delta, abs_tol=1e-9)]
        add("최대 전월 상승", "; ".join(f"{prev} → {month} · {index_label(before)} → {index_label(after)} (+{change:.2f} 지수 포인트)" for change, month, prev, before, after in tied))
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
            return ", ".join(months) + f" · 지수 {index_label(value)}"
        rows.append({"연도": str(year), "최저": label(min), "최고": label(max)})
    return rows


# 모든 프로젝트에 공통으로 쓰는 고정 목록(업종별 사전 없음). 긍정/부정 영향은 추정하지 않는다.
# 제목의 명시적인 표현만 정규식으로 찾고, 위에서부터 처음 맞는 주제를 쓴다. 이름은 업종 중립으로 두고 자동차 표현은 키워드로만 포함한다.
TOPICS = (
    ("업계 소식 모음", (r"브리프", r"단신", r"이모저모", r"Today", r"CAR News", r"Now\]", r"모빌로그", r"자동차오늘", r"Pick\]")),
    ("리콜·분쟁·제재 보도", (r"리콜", r"소송", r"과징금", r"제재", r"불매", r"결함")),
    ("리뷰·사용기", (r"시승기", r"타봤", r"타보니", r"타보고서", r"써보니", r"사용기", r"리뷰")),
    ("체험·시승", (r"시승", r"체험", r"타보고", r"타보면", r"타보세요")),
    ("프로모션·혜택", (r"프로모션", r"할인", r"혜택", r"이벤트", r"특가", r"세일", r"무이자", r"판촉", r"잔가", r"반납", r"납입금",
                    r"구매 조건", r"판매 조건", r"감사제", r"증정")),
    ("실적·수주·투자 보도", (r"실적", r"성장", r"증가", r"감소", r"적자", r"흑자", r"수주", r"투자", r"매출", r"판매량", r"성적표",
                        r"내수", r"수출",
                        r"\d+만\s?대", r"(\d{3,}|\d{1,3},\d{3})\s?대\s?(판매|돌파|계약|생산)")),
    ("신제품·서비스", (r"출시", r"신제품", r"공개", r"신차", r"서비스")),
    ("행사·캠페인", (r"캠페인", r"콘서트", r"참가", r"후원", r"개최", r"성료", r"마케팅", r"전시", r"행사", r"축제", r"기념", r"팝업", r"고객 접점")),
)
OTHER_TOPIC = "기타 관련 보도"
MULTI_BRAND = "여러 브랜드 동시 언급"
MARKET = "시장·기타"


def headline(row):
    """수집 원문에 남은 HTML 엔티티(&quot; 등)를 표시용으로만 풀어준다. 원본 필드는 바꾸지 않는다."""
    return html.unescape(row.get("title") or row.get("text", "").split("\n")[0]).strip()


def news_sections(rows):
    """대구분(제목의 주제) → 소구분(단일 브랜드 / 여러 브랜드 / 시장·기타) → 유사 제목 묶음. 모든 원문은 보존한다."""
    from core.materials import timestamp
    buckets = defaultdict(list)
    for row in sorted(rows, key=timestamp, reverse=True):
        if row.get("kind") != "뉴스":
            continue
        title = headline(row)
        topic = next((name for name, patterns in TOPICS if any(re.search(p, title) for p in patterns)), OTHER_TOPIC)
        brands = sorted(row.get("found_brands") or [])
        subject = brands[0] if len(brands) == 1 else MULTI_BRAND if brands else MARKET
        key = (topic, subject)
        normalized = re.sub(r"\W+", "", title.casefold())
        numbers = re.findall(r"\d+(?:[.,]\d+)*", title)
        group = next((g for g in buckets[key] if numbers == g["numbers"] and normalized and
                      SequenceMatcher(None, normalized, g["normalized"]).ratio() >= .78), None)
        if group is None:
            group = {"title": title, "excerpt": row.get("excerpt") or "\n".join(row.get("text", "").split("\n")[1:]),
                     "brands": brands, "normalized": normalized, "numbers": numbers, "articles": []}
            buckets[key].append(group)
        group["articles"].append(row)
    sections = []
    for topic in [name for name, _ in TOPICS] + [OTHER_TOPIC]:
        subjects = [{"title": subject, "groups": groups, "count": sum(len(g["articles"]) for g in groups)}
                    for (category, subject), groups in buckets.items() if category == topic]
        # 단일 브랜드(기사 많은 순) → 여러 브랜드 → 시장·기타
        subjects.sort(key=lambda s: (s["title"] == MULTI_BRAND, s["title"] == MARKET, -s["count"]))
        if subjects:
            groups = [g for subject in subjects for g in subject["groups"]]
            sections.append({"title": topic, "subjects": subjects, "groups": groups,
                             "count": sum(s["count"] for s in subjects)})
    return sections
