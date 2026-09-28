"""New-project wizard. Form submissions commit to a draft before changing steps."""
import copy
import uuid
import streamlit as st
from core import projects, project_discovery
from core.collection import words


def candidate_brand(candidate, bid, role):
    urls = candidate.get("homepage_candidates", [])
    return {"id": bid, "role": role, "name": candidate.get("name", ""),
            "terms": candidate.get("terms") or [candidate.get("name", "")],
            "sources": {"official_urls": urls, "homepage": next(iter(urls), ""),
                        "instagram": candidate.get("instagram_candidate", ""),
                        "youtube": candidate.get("youtube_candidate", ""),
                        "meta_page": candidate.get("meta_page_candidate", "")},
            "proposal_evidence": candidate.get("evidence_urls", [])}


def _move(step):
    st.session_state.setup_step = step
    st.rerun()


def render(brand_fields, reset):
    if "setup_draft" not in st.session_state:
        seed = st.session_state.get("draft", {})
        st.session_state.setup_draft = projects.project_inputs({**seed, "paid_enabled": True})
        st.session_state.setup_step = 1
        st.session_state.setup_id = uuid.uuid4().hex
    p = st.session_state.setup_draft
    step = st.session_state.setup_step
    cfg = "setup_" + st.session_state.setup_id
    st.title("새 프로젝트")
    st.caption(f"{step}/4 · " + ["조사 대상", "자사 정보 확인", "경쟁사 선택", "수집 설정 확인"][step - 1])
    st.caption("조사 대상 → 자사 정보 → 경쟁사 → 최종 확인 · 이전으로 이동해도 제출한 입력은 유지됩니다.")
    if step == 1:
        with st.form(cfg + "start"):
            brand = st.text_input("브랜드명 *", value=p["brands"][0]["name"])
            topic = st.text_input("조사 범위 (선택)", value=p.get("campaign", p.get("category", "")), placeholder="비워두면 브랜드 전체 · 예: 리하우스 사업, TM 채용")
            ai = st.checkbox("AI로 설정 초안 제안받기 (Gemini · 유료 호출 가능)", value=True)
            st.caption("1차 검색 범위: 공식 홈페이지 · Instagram 공식 프로필 · YouTube 공식 채널 · 검색어 · 경쟁사 후보")
            replace = st.checkbox("이미 작성한 초안을 새 제안으로 교체", value=False) if p.get("setup_requested") else False
            submitted = st.form_submit_button("초안 준비하고 다음", type="primary")
        if submitted:
            if not brand.strip():
                st.warning("브랜드명을 입력해주세요.")
                return
            changed = (brand.strip(), topic.strip()) != (p["brands"][0]["name"], p.get("campaign", ""))
            if changed and p.get("setup_requested") and not replace:
                st.warning("조사 대상이 바뀌었습니다. 기존 초안을 교체하려면 위 확인란을 선택해주세요.")
                return
            if replace or not p.get("setup_requested"):
                p = projects.project_inputs({"brand_name": brand.strip(), "campaign": topic.strip(), "paid_enabled": True})
                if ai:
                    with st.spinner("검색 근거가 있는 후보를 찾고 있습니다…"):
                        result = project_discovery.suggest(brand, topic)
                    p["proposal"] = result
                    proposed = result.get("suggestions") or {}
                    if proposed.get("own"):
                        p["brands"][0] = candidate_brand(proposed["own"], "own", "own")
                        p["brands"][0]["name"] = brand.strip()
                    for key in ("category", "market_keywords", "news_keywords"):
                        if proposed.get(key):
                            p[key] = proposed[key]
                p["setup_requested"] = True
                st.session_state.setup_draft = p
            _move(2)
    elif step == 2:
        result = p.get("proposal", {})
        if result:
            (st.info if result.get("suggestions") else st.warning)(result.get("message", "후보 없음"))
            if not result.get("suggestions") and st.button("AI 초안 다시 준비하기 (다음 화면에서 요청)"):
                p["setup_requested"] = False
                _move(1)
        st.caption("검색에서 찾은 후보도 공식 여부를 직접 확인해주세요. 빈 계정은 해당 자료 수집만 건너뜁니다.")
        with st.expander("AI 제안 출처"):
            for url in result.get("evidence_urls", []):
                st.write(url)
        with st.form(cfg + "own"):
            own = brand_fields(cfg, p["brands"][0])
            prev = st.form_submit_button("이전")
            nxt = st.form_submit_button("자사 정보 확인하고 다음", type="primary")
        if prev or nxt:
            p["brands"][0] = own
            errors = projects.validate_inputs({**p, "brands": [own]})
            if nxt and errors:
                for error in errors: st.warning(error)
            else:
                _move(1 if prev else 3)
    elif step == 3:
        candidates = (p.get("proposal", {}).get("suggestions") or {}).get("competitors", [])
        # Pick candidates once; subsequently edit the draft directly without overwriting it.
        if not p.get("competitors_reviewed"):
            with st.form(cfg + "candidates"):
                chosen = []
                for index, candidate in enumerate(candidates):
                    if st.checkbox(candidate["name"] + (" · " + candidate["reason"] if candidate.get("reason") else ""), key=cfg + f"candidate_{index}"):
                        chosen.append(candidate_brand(candidate, "c-" + str(index), "competitor"))
                manual = st.text_input("직접 추가할 경쟁사 (쉼표로 구분)", placeholder="경쟁사 없이 진행할 수도 있습니다")
                apply = st.form_submit_button("선택한 경쟁사 확인 / 건너뛰기", type="primary")
                back = st.form_submit_button("이전")
            if back: _move(2)
            if apply:
                chosen += [candidate_brand({"name": n}, "m-" + uuid.uuid4().hex[:8], "competitor") for n in words(manual)]
                errors = projects.validate_inputs({**p, "brands": [p["brands"][0], *chosen]})
                if errors:
                    for error in errors: st.warning(error)
                else:
                    p["brands"] = [p["brands"][0], *chosen]
                    p["competitors_reviewed"] = True
                    if not chosen: _move(4)
                    st.rerun()
        else:
            with st.form(cfg + "competitors"):
                brands = [p["brands"][0]]
                for b in p["brands"][1:]:
                    with st.expander(b["name"], expanded=False):
                        if st.checkbox("이 경쟁사 포함", value=True, key=cfg + b["id"] + "keep"):
                            brands.append(brand_fields(cfg, b))
                if len(brands) == 1: st.caption("경쟁사 없이 자사 자료만 수집합니다.")
                back = st.form_submit_button("이전")
                nxt = st.form_submit_button("경쟁사 확인하고 다음", type="primary")
                reselect = st.form_submit_button("경쟁사 다시 선택")
            if back or nxt or reselect:
                p["brands"] = brands
                if reselect:
                    p["competitors_reviewed"] = False
                    st.rerun()
                errors = projects.validate_inputs(p)
                if nxt and errors:
                    for error in errors: st.warning(error)
                else: _move(2 if back else 4)
    else:
        st.write("**조사 브랜드** · " + ", ".join(b["name"] for b in p["brands"]))
        for term, owners in projects.term_conflicts(p["brands"]):
            st.warning(f"'{term}'이(가) {', '.join(owners)}에 함께 들어 있습니다. 비교 범위를 확인해주세요.")
        st.caption("프로젝트 생성 후 자료 수집 화면에서 필요한 자료와 비용 조건을 확인하고 실행합니다. 지금은 수집하지 않습니다.")
        with st.form(cfg + "finish"):
            name = st.text_input("프로젝트 이름", value=p.get("title") or " ".join(filter(None, [p["brands"][0]["name"], p.get("campaign")])) )
            market = words(st.text_input("시장 관심 검색어", value=", ".join(p.get("market_keywords", [])), help="시장 조사를 원하는 검색어입니다. 검색 추이·검색량을 조회하고 뉴스 검색어 후보로 활용합니다."))
            news = words(st.text_input("뉴스 수집 검색어", value=", ".join(p.get("news_keywords", [])), help="이 검색어로 뉴스를 요청합니다. 비워두면 뉴스를 수집하지 않습니다."))
            with st.expander("뉴스 결과 좁히기 (선택)"):
                include = words(st.text_input("꼭 들어갈 문구", value=", ".join(p["news_filter"].get("include", []))))
                exclude = words(st.text_input("빼고 싶은 문구", value=", ".join(p["news_filter"].get("exclude", []))))
            paid = st.checkbox("유료 기능 사용", value=p.get("paid_enabled", True))
            confirmed = st.checkbox("브랜드·검색어·주소 후보를 확인했습니다")
            back = st.form_submit_button("이전")
            save = st.form_submit_button("확인하고 프로젝트 만들기", type="primary")
        if back or save:
            p.update(title=name, market_keywords=market, news_keywords=news, news_filter={"include": include, "exclude": exclude}, paid_enabled=paid)
            if back: _move(3)
            errors = projects.validate_inputs(p)
            if not confirmed: errors.append("후보 확인란을 선택해주세요.")
            if errors:
                for error in errors: st.warning(error)
            else:
                stored = projects.to_storage(p)
                stored["setup_provenance"] = {"confirmed_at": projects.now(), "proposal": p.get("proposal", {}), "method": "four_step_review"}
                pid = projects.create(name.strip() or p["brands"][0]["name"], stored)
                st.session_state.project_id = pid
                st.session_state.step = "workspace"
                for key in list(st.session_state):
                    if key.startswith(("setup_", cfg)): del st.session_state[key]
                st.rerun()
    st.button("프로젝트 목록으로", on_click=reset, key=cfg + "cancel")
