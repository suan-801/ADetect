"""분석하기 — STEP 1 브랜드 설정 → STEP 2 분석 Workspace (PRD §16-1·§16-2·§16-4).

타겟 입력 필드는 없습니다 (★ 15차 개정) — 타겟은 타겟분석 탭에서 게이트 통과 후 추천됩니다.

3차 리뉴얼: Analysis Header를 "브랜드/카테고리/타겟 + 5개 상태가 한 줄에 섞여 가독성이 낮던"
구조에서 7:5 grid(왼쪽 Brand Context, 오른쪽 01~05 Vertical Analysis Status Index)로 재설계했다.
탭 표시 순서도 PRD 내부 실행 순서(시장→브랜드→소재→타겟→종합, 게이트 의존성 때문)는 그대로 두되
화면에는 Market/Audience/Brand/Creative/Synthesis 순서로 보이도록 재배치했다 — gate 판정 로직
자체(target_gate_open 등)는 전혀 건드리지 않았다.
"""
from __future__ import annotations

import streamlit as st

from config.theme import command_marker, cta_row_marker
from core.analyzers.recommender import recommend_category, recommend_competitors
from database.db import create_session
from ui import brand_tab, creative_tab, market_tab, synthesis_tab, target_tab
from ui.components import analysis_status_index, brand_context_header

st.session_state.setdefault("step", "input")
st.session_state.setdefault("session", None)

# ── STEP 1: 브랜드 설정 (입력) ──────────────────────────────────────────
if st.session_state.step == "input":
    st.markdown(
        "<span class='adetect-eyebrow'>Step 1</span>"
        "<p class='adetect-page-title'>브랜드 설정</p>",
        unsafe_allow_html=True,
    )
    st.write("")
    with st.container():
        command_marker()
        brand_name = st.text_input(
            "브랜드명 *", value=st.session_state.pop("prefill_brand", ""), key="input_brand_name"
        )
        category = st.text_input(
            "카테고리 (선택 — 비워두면 AI가 추천)",
            value=st.session_state.pop("prefill_category", ""),
            key="input_category",
        )
        competitors_raw = st.text_input(
            "경쟁사 (선택 — 쉼표로 구분, 비워두면 AI가 추천)",
            value=st.session_state.pop("prefill_competitors", ""),
            key="input_competitors",
        )
        st.write("")
        if st.button("다음", type="primary", disabled=not brand_name.strip(), key="btn_step1_next"):
            st.session_state.draft = {
                "brand_name": brand_name.strip(),
                "category": category.strip(),
                "competitors_raw": competitors_raw.strip(),
            }
            st.session_state.step = "confirm"
            st.rerun()

# ── STEP 1: 확인 화면 (AI 추천 → 사용자 확인, §9) ──────────────────────
elif st.session_state.step == "confirm":
    draft = st.session_state.draft
    st.markdown(
        "<span class='adetect-eyebrow'>Step 1 · Information</span>"
        "<p class='adetect-page-title'>브랜드명을 기반으로 추천합니다</p>",
        unsafe_allow_html=True,
    )
    st.write("")

    with st.spinner("브랜드명을 기반으로 카테고리·경쟁사를 추천하는 중..."):
        category = draft["category"] or recommend_category(draft["brand_name"])
        user_competitors = [c.strip() for c in draft["competitors_raw"].split(",") if c.strip()]
        ai_competitors = recommend_competitors(draft["brand_name"], category)
    # 사용자 입력 경쟁사 우선 (§7-10) — 입력이 있으면 그 값 우선, 부족한 슬롯만 AI가 보완
    user_names = {c["name"] if isinstance(c, dict) else c for c in user_competitors}
    candidates = (
        [{"name": c, "type": None} for c in user_competitors]
        + [c for c in ai_competitors if c["name"] not in user_names]
    )

    with st.container():
        command_marker()
        category = st.text_input("카테고리", value=category, key="confirm_category")
        st.caption("경쟁사 — 직접 입력한 값이 있다면 그 값을 우선 반영합니다.")
        selected = []
        for c in candidates:
            name, ctype = c["name"], c.get("type")
            # 브랜드명은 굵게(primary), 유형 태그는 muted gray로 시각적으로 구분
            label = f"**{name}**  :gray[· {ctype}]" if ctype else f"**{name}**"
            checked = st.checkbox(label, value=False, key=f"competitor_{name}")
            if checked:
                selected.append(name)
        extra = st.text_input("경쟁사 추가 (쉼표로 구분)", key="confirm_extra_competitors")
        selected += [c.strip() for c in extra.split(",") if c.strip()]

        st.write("")
        with st.container():
            cta_row_marker()
            back = st.button("이전", key="btn_confirm_back")
            go = st.button("분석하기 →", type="primary", key="btn_confirm_go")

    if back:
        st.session_state.step = "input"
        st.rerun()
    if go:
        session_id = create_session(draft["brand_name"], category, selected)
        st.session_state.session = {
            "id": session_id,
            "brand_name": draft["brand_name"],
            "category": category,
            "competitors": selected,
            "market_status": "미실행",
            "brand_status": "미실행",
            "creative_status": "미실행",
            "target_status": "not_set",
        }
        st.session_state.step = "workspace"
        st.rerun()

# ── STEP 2: 분석 Workspace (5개 기능) ───────────────────────────────────
elif st.session_state.step == "workspace":
    session = st.session_state.session

    # 게이트 판정 로직은 리뉴얼 이전과 동일 — 화면 표시 순서만 Market/Audience/Brand/Creative/
    # Synthesis로 바꿨을 뿐, target_gate_open 등 실행 조건은 그대로다.
    target_gate_open = session["market_status"] in ("완료", "부분 실패") and session["brand_status"] in ("완료", "부분 실패")
    if not target_gate_open:
        target_status_for_index = "🔒"
    elif session["target_status"] == "confirmed":
        target_status_for_index = "완료"
    else:
        target_status_for_index = "미실행"

    synthesis_gate_open = any(
        session[k] in ("완료", "부분 실패") for k in ("market_status", "brand_status", "creative_status")
    ) or session["target_status"] == "confirmed"
    synthesis_status_for_index = "미실행" if synthesis_gate_open else "🔒"

    header_col, status_col = st.columns([7, 5], gap="large")
    with header_col:
        brand_context_header(session)
        if st.button("새 브랜드로 다시 시작", key="btn_reset_session"):
            st.session_state.session = None
            st.session_state.step = "input"
            st.rerun()
    with status_col:
        analysis_status_index([
            ("시장 분석", session["market_status"]),
            ("타겟 분석", target_status_for_index),
            ("브랜드 분석", session["brand_status"]),
            ("소재 분석", session["creative_status"]),
            ("종합 분석", synthesis_status_for_index),
        ])

    st.write("")

    # 탭 표시 순서: Market → Audience(타겟) → Brand → Creative → Synthesis
    tab_market, tab_target, tab_brand, tab_creative, tab_synth = st.tabs(
        ["01 시장분석", "02 타겟분석", "03 브랜드분석", "04 소재분석", "05 종합분석"]
    )
    with tab_market:
        market_tab.render(session)
    with tab_target:
        target_tab.render(session)
    with tab_brand:
        brand_tab.render(session)
    with tab_creative:
        creative_tab.render(session)
    with tab_synth:
        synthesis_tab.render(session)
