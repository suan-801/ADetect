"""결과 화면과 내보내기가 함께 쓰는 비교·집계. 저장된 값만 계산하고 API를 호출하지 않는다."""
from core import projects


def _parse(value):
    """정수, '<10' 표시값, 미제공을 구분한다. '<10'을 0으로 바꾸지 않는다."""
    if value is None or value == "":
        return "missing", None
    text = str(value).replace(",", "").replace(" ", "")
    if text.startswith("<"):
        return "lt10", None
    try:
        return "value", int(float(text))
    except ValueError:
        return "missing", None


def format_total(known, lt10, missing):
    if missing:
        return f"확인된 값 합계 {known:,} · 일부 값 미제공 {missing}개"
    if lt10:
        return f"{known:,}~{known + 9 * lt10:,} (<10 {lt10}개 포함 범위)"
    return f"{known:,}"


def volume_totals(item, brands):
    """브랜드별 검색어 묶음 합계. 정확히 일치한 검색어만, 연관 검색어·중복 표기는 제외."""
    rows = []
    names = {b["id"]: b for b in brands}
    for key, part in (item or {}).get("result", {}).get("parts", {}).items():
        terms = part.get("terms")
        if terms is None or part.get("brand_id") not in names:
            continue
        seen, pc, mobile = set(), [0, 0, 0], [0, 0, 0]
        for t in terms:
            k = projects.term_key(t["term"])
            if k in seen:
                continue
            seen.add(k)
            for bucket, raw in ((pc, t.get("pc")), (mobile, t.get("mobile"))):
                if t["state"] != "완료":
                    bucket[2] += 1
                    continue
                kind, value = _parse(raw)
                if kind == "value":
                    bucket[0] += value
                elif kind == "lt10":
                    bucket[1] += 1
                else:
                    bucket[2] += 1
        total = [pc[0] + mobile[0], pc[1] + mobile[1], pc[2] + mobile[2]]
        rows.append({"brand_id": part["brand_id"], "브랜드": names[part["brand_id"]]["name"], "검색어 수": len(seen),
                     "PC": format_total(*pc), "모바일": format_total(*mobile), "합계": format_total(*total),
                     "정확한 합계": not total[1] and not total[2], "known_total": total[0]})
    return rows


def _latest_social(history, source, brand):
    """브랜드의 최신 SNS 수집 결과. 여러 실행을 합칠 때 브랜드별 수집 시각을 함께 돌려준다."""
    key_new, key_old = f"{source}:{brand['id']}", f"{source}:{brand['name']}"
    kind = "Instagram" if source == "instagram" else "YouTube"
    for h in history:  # history는 최신순
        if h["source"] != source or h["result"].get("expired"):
            continue
        parts = h["result"].get("parts", {})
        part = parts.get(key_new) or parts.get(key_old)
        if not part:
            continue
        if part.get("state") == "설정 필요":
            continue
        if part.get("state") == "실패":
            return {"state": "수집 실패", "at": h["created"]}
        row = next((r for r in h["result"].get("records", []) if r["kind"] == kind and (r.get("brand_id") == brand["id"] or r.get("brand") == brand["name"])), None)
        if row:
            return {"state": "완료", "row": row, "at": row.get("observed_at") or h["created"]}
    return {"state": "미수집"}


def social_value(info, field, has_account):
    if info["state"] != "완료":
        return info["state"] if has_account else "미입력"
    value = info["row"].get(field)
    return "미제공 / 비공개" if value in (None, "") else f"{int(float(value)):,}" if str(value).replace(".", "").isdigit() else str(value)


def comparison_rows(p, history, volume_item):
    """브랜드 비교 요약: 검색어 묶음 월간 검색량 합계, Instagram 팔로워, YouTube 구독자, 수집 시각."""
    totals = {r["brand_id"]: r for r in volume_totals(volume_item, p["brands"])}
    rows, times = [], set()
    for b in p["brands"]:
        src = b.get("sources", {})
        ig, yt = _latest_social(history, "instagram", b), _latest_social(history, "youtube", b)
        stamps = [x["at"][:10] for x in (ig, yt) if x.get("at") and x["state"] == "완료"]
        times.update(stamps)
        vol = totals.get(b["id"])
        legacy = volume_item and not any(pt.get("terms") is not None for pt in volume_item["result"].get("parts", {}).values())
        rows.append({"브랜드": b["name"] + (" (자사)" if b["role"] == "own" else ""),
                     "검색어 묶음": ", ".join(b["terms"]),
                     "월간 검색량 합계": vol["합계"] if vol else "이전 방식 결과 — 재수집 필요" if legacy else "미수집",
                     "Instagram 팔로워": social_value(ig, "followers", bool(src.get("instagram"))),
                     "YouTube 구독자": social_value(yt, "subscribers", bool(src.get("youtube"))),
                     "SNS 수집일": ", ".join(sorted(set(stamps))) or "-"})
    vol_date = volume_item["created"][:10] if volume_item else None
    notes = []
    if vol_date:
        notes.append(f"월간 검색량 조회일 {vol_date}")
    if len(times) > 1:
        notes.append("브랜드별 SNS 수집일이 달라 같은 시점의 비교가 아닙니다")
    return rows, notes


def trend_view(item, p):
    """검색 추이 표시 정보. 새 비교(한 요청)와 이전 개별 요청 결과를 섞지 않는다."""
    if not item:
        return {"kind": "none"}
    parts = item["result"].get("parts", {})
    compare = next((pt["comparison"] for pt in parts.values() if pt.get("comparison")), None)
    market = [pt["series"] for k, pt in parts.items() if k.startswith("trend:market:") and pt.get("series")]
    if compare:
        stale = compare.get("signature") != projects.comparison_signature(p["brands"])
        return {"kind": "compare", "compare": compare, "market": market, "stale": stale}
    legacy = [pt["series"] for pt in parts.values() if pt.get("series")]
    return {"kind": "legacy", "series": legacy}


def news_view(rows, news_filter):
    shown = [r for r in rows if r["kind"] == "뉴스" and projects.news_passes(r, news_filter)]
    hidden = sum(1 for r in rows if r["kind"] == "뉴스" and not projects.news_passes(r, news_filter))
    from core.materials import timestamp
    return sorted(shown, key=timestamp, reverse=True), hidden


def search_status_rows(rows, p, observed_only=True):
    """검색 화면 관측: 검색어 × 브랜드 광고 노출 상태."""
    output = []
    for r in rows:
        if r["kind"] != "검색 화면":
            continue
        for bid, st in (r.get("brand_status") or {}).items():
            if observed_only and st["state"] != "관측 시 노출 확인":
                continue
            output.append({"검색어": r.get("keyword"), "브랜드": st.get("name", bid), "노출 상태": st["state"], "근거": st.get("evidence"),
                           "수집 환경": r.get("environment"), "수집 시각": (r.get("observed_at") or "")[:16].replace("T", " ")})
    return output
