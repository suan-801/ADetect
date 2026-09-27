"""종류별 자료 표·한 줄 요약. 근거가 설명 가능한 값만 쓰며 추정 점수·분류는 만들지 않는다."""
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ORDER = ['검색량', '뉴스', '광고', '검색 화면', '홈페이지', 'Instagram', 'YouTube', 'Instagram 게시물', 'YouTube 게시물', '연관 검색어']


def timestamp(row):
    value = row.get('published_at') or row.get('observed_at') or row.get('collected_at') or ''
    for parse in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            parsed = parse(str(value))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()
        except (TypeError, ValueError, OverflowError):
            pass
    return 0


def prioritized(rows):
    """자료 종류 순서, 같은 종류 안에서는 최신순."""
    recent = sorted(rows, key=timestamp, reverse=True)
    return sorted(recent, key=lambda r: ORDER.index(r['kind']) if r['kind'] in ORDER else 99)


def summary(kind, rows):
    """표 위 한 줄 요약. 자료가 적으면 건수만 말한다."""
    n = len(rows)
    brands = sorted({r.get('brand') for r in rows if r.get('brand')})
    if kind in ('검색량', '연관 검색어'):
        return f'{n}개 검색어의 조회 시점 PC·모바일 월간 검색량입니다. <10·미제공은 0이 아닙니다.'
    if kind in ('Instagram', 'YouTube'):
        return f'{", ".join(brands)} 계정의 수집 당시 지표입니다. 미제공·비공개 값은 0으로 표시하지 않습니다.'
    if kind == '광고':
        counts = Counter(str(r.get('format') or '형식 미제공') for r in rows)
        return f'{n}건 표본 · ' + ', '.join(f'{k} {v}건' for k, v in counts.most_common()) + ' · 전체 광고량·성과가 아닙니다.'
    if kind == '뉴스':
        dates = sorted(str(r.get('published_at'))[:10] for r in rows if r.get('published_at'))
        return f'표시 중인 기사 {n}건' + (f' · {dates[0]} ~ {dates[-1]} 발행' if dates else '') + ' · 최신순'
    if kind in ('Instagram 게시물', 'YouTube 게시물'):
        return f'{", ".join(brands)}의 최근 게시물 {n}건입니다.'
    if kind == '홈페이지':
        return f'{", ".join(brands)} 공식 페이지 {n}곳에 기재된 내용입니다. 기재 내용의 사실 여부는 검증하지 않았습니다.'
    return f'{n}건'


def _value(value):
    return '미제공' if value is None or value == '' else ', '.join(map(str, value)) if isinstance(value, list) else str(value)


def table_row(row, selected):
    """화면·다운로드 표의 한 행. 내부 ID·반복 안내 문장은 싣지 않는다."""
    kind = row['kind']
    # 뉴스는 수집한 프로젝트가 아니라 기사에 언급된 브랜드를 보여준다.
    item = {'다운로드': selected} if kind == '뉴스' else {'다운로드': selected, '브랜드': row.get('brand', '')}
    if kind in ('검색량', '연관 검색어'):
        item.update({'검색어': row['text'], '조회 표기': row.get('keyword', ''), 'PC 월간 검색량': _value(row.get('pc')), '모바일 월간 검색량': _value(row.get('mobile'))})
    elif kind == '뉴스':
        item.update({'발행일': _value(row.get('published_at')), '제목': row.get('title') or row['text'].split('\n')[0],
                     '발췌': (row.get('excerpt') or '\n'.join(row['text'].split('\n')[1:]))[:240],
                     '발견 검색어': _value(row.get('matched_queries') or row.get('keyword')), '언급 브랜드': _value(row.get('found_brands')) if row.get('found_brands') else '없음'})
    else:
        item['내용'] = row['text'][:240]
    fields = {'광고': ('format', 'cta', 'start_date', 'landing_url'), 'Instagram': ('followers', 'post_count', 'observed_at'),
              'YouTube': ('subscribers', 'videos', 'observed_at'), 'Instagram 게시물': ('published_at',), 'YouTube 게시물': ('published_at',),
              '홈페이지': ('coverage',)}
    labels = {'published_at': '게시일', 'format': '형식', 'cta': 'CTA', 'start_date': '시작일', 'landing_url': '랜딩',
              'followers': '팔로워 수', 'post_count': '게시물 수', 'subscribers': '구독자 수', 'videos': '영상 수',
              'observed_at': '수집 시각', 'coverage': '수집 범위'}
    for key in fields.get(kind, ()):
        value = row.get(key)
        item[labels[key]] = str(value)[:16].replace('T', ' ') if key == 'observed_at' and value else (
            '미제공 / 비공개' if value is None and key in ('followers', 'post_count', 'subscribers', 'videos') else _value(value))
    item['출처'] = row['source_url']
    if row.get('sample'):
        item['SAMPLE'] = 'SAMPLE'
    return item


def news_suggestions(brand, campaign, category, market=()):
    """입력 기반 뉴스 검색어 후보. 사용자가 적용해야 입력에 반영된다."""
    candidates = [brand, f'{brand} {campaign}'.strip() if campaign else '', f'{brand} 신제품', f'{brand} 캠페인',
                  f'{category} 동향'.strip() if category else '', *[f'{m} 시장' for m in market]]
    return list(dict.fromkeys(s for s in candidates if s))
