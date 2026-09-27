"""UTM·추적 파라미터 구조 분석. 순수 URL 파싱이며 AI를 쓰지 않고 링크를 방문하지 않는다.

원본 URL은 그대로 보존하고(민감 파라미터만 마스킹), 분석용 정규화 값은 별도 필드로 둔다.
추적 파라미터만으로 실제 매체 집행·성과·전환을 확정하지 않는다.
"""
from urllib.parse import urlsplit, urlunsplit, parse_qsl, unquote_plus

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
TRACKING = ("utm_id", "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "dclid", "n_media", "n_query", "n_rank", "n_ad_group",
            "n_ad", "n_keyword_id", "n_keyword", "n_campaign_type", "n_ad_group_type", "nt_source", "nt_medium", "nt_detail",
            "nt_keyword", "ttclid", "twclid", "igshid", "mc_cid", "mc_eid", "_ga", "ref", "source")
SENSITIVE = ("token", "secret", "password", "passwd", "auth", "session", "sid", "signature", "sig", "key", "code", "access")
MASK = "••••"
# 광고 플랫폼의 클릭 추적 리디렉션. 최종 랜딩을 확인하지 않았으므로 '최종 URL 미확보'로 둔다.
REDIRECT_HOSTS = ("ad.search.naver.com", "adcr.naver.com", "ader.naver.com", "l.facebook.com", "lm.facebook.com", "googleadservices.com", "www.googleadservices.com")


def _sensitive(key):
    k = key.lower()
    return not k.startswith(("utm_", "n_", "nt_")) and any(s == k or k.endswith("_" + s) or k.startswith(s + "_") or s in k.split("-") for s in SENSITIVE)


def masked(url):
    """화면·내보내기용 원본 URL. 민감 파라미터 값만 가리고 나머지 표기는 바꾸지 않는다."""
    if not url:
        return url
    u = urlsplit(url)
    if not u.query:
        return url
    parts = []
    for piece in u.query.split("&"):
        key = piece.split("=", 1)[0]
        parts.append(key + "=" + MASK if "=" in piece and _sensitive(unquote_plus(key)) else piece)
    return urlunsplit((u.scheme, u.netloc, u.path, "&".join(parts), u.fragment))


def parse(url, brand="", origin=""):
    row = {"브랜드": brand, "자료 출처": origin, "원본 URL": masked(url)}
    try:
        u = urlsplit((url or "").strip())
    except ValueError:
        u = None
    if not u or not u.scheme or not u.netloc:
        return {**row, "상태": "URL 형식 확인 불가", "랜딩 도메인": None, "랜딩 경로": None, **{k: None for k in UTM_KEYS}, "기타 추적 파라미터": None, "특이사항": "URL 형식이 아닙니다."}
    host = (u.hostname or "").lower()
    pairs = parse_qsl(u.query, keep_blank_values=True)
    notes, seen, values, other = [], {}, {}, []
    for raw_key, value in pairs:
        key = raw_key.lower()
        if raw_key != key and key.startswith("utm_"):
            notes.append(f"대소문자 표기 차이: {raw_key}")
        if key in seen:
            notes.append(f"중복 키: {key}" + (" (값 다름)" if seen[key] != value else ""))
            continue
        seen[key] = value
        if key in UTM_KEYS:
            values[key] = value
            if value == "":
                notes.append(f"빈 값: {key}")
            elif value != value.strip():
                notes.append(f"앞뒤 공백: {key}")
            if "%" in value or "+" in value:
                notes.append(f"인코딩 포함: {key}")
        elif key in TRACKING or key.startswith(("utm_", "n_", "nt_")):
            other.append(f"{raw_key}={MASK if _sensitive(key) else value}")
    redirect = host in REDIRECT_HOSTS
    if redirect:
        status = "최종 URL 미확보 (광고 클릭 추적 링크)"
    elif any(k in values for k in UTM_KEYS):
        status = "UTM 확인"
    else:
        status = "확인한 URL에 UTM 없음"
    normalized = {k: (unquote_plus(values[k]).strip().casefold() if values.get(k) else None) for k in UTM_KEYS}
    return {**row, "상태": status, "랜딩 도메인": host, "랜딩 경로": u.path or "/",
            **{k: values.get(k) for k in UTM_KEYS}, "기타 추적 파라미터": ", ".join(other) or None,
            "특이사항": ", ".join(dict.fromkeys(notes)) or None, "_normalized": normalized}


def campaign_groups(rows):
    """같은 utm_campaign(정규화 값)에서 관측된 source/medium/content 조합. 관측 사실만 묶는다."""
    groups = {}
    for r in rows:
        n = r.get("_normalized") or {}
        if not n.get("utm_campaign"):
            continue
        key = (r["브랜드"], n["utm_campaign"])
        combo = " / ".join(x or "(없음)" for x in (n.get("utm_source"), n.get("utm_medium"), n.get("utm_content")))
        g = groups.setdefault(key, {"브랜드": r["브랜드"], "utm_campaign": n["utm_campaign"], "조합": [], "근거 URL 수": 0})
        if combo not in g["조합"]:
            g["조합"].append(combo)
        g["근거 URL 수"] += 1
    return [{**g, "조합": "; ".join(g["조합"])} for g in groups.values()]


def public(rows):
    """표·내보내기용 (내부 정규화 필드 제외)."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
