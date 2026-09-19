"""분석하기 — STEP 1 브랜드 설정 → STEP 2 분석 Workspace (PRD §16-1·§16-2·§16-4).

타겟 입력 필드는 없습니다 — Target은 독립 Primary Analysis Function이 아니라 종합분석
탭 안의 Target Insight subsection이다(§4·§12·§15). Workspace의 4개 1차 탭은 항상
시장/브랜드/소재/종합 순서로 고정한다.

Target 관련 레거시 코드(ui/target_tab.py, core/analyzers/target_recommender.py,
DB의 target_status/recommended_target/confirmed_target)는 과거 세션·DB 호환을 위해
그대로 남겨두되, 이 화면에서는 더 이상 import/render하지 않는다 — 독립 tab·독립
function_run으로 다시 노출하지 않는다(destructive migration 아님).
"""
from __future__ import annotations

import streamlit as st

from config.theme import command_marker, cta_row_marker
from core.analyzers.recommender import recommend_category, recommend_competitors
from database.db import create_session
from ui import brand_tab, creative_tab, market_tab, synthesis_tab
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

# ── STEP 2: 분석 Workspace (4개 Primary Analysis Function) ──────────────
elif st.session_state.step == "workspace":
    session = st.session_state.session

    # 종합분석 활성화 조건: 시장/브랜드/소재 중 최소 1개 이상 완료(또는 부분 실패) — Target은
    # 더 이상 이 게이트에 관여하지 않는다(§6-1·§12). Target Insight는 종합분석 탭 내부에서
    # 시장+브랜드 결과 유무로 자체 판단한다(ui/synthesis_tab.py 참고).
    synthesis_gate_open = any(
        session[k] in ("완료", "부분 실패") for k in ("market_status", "brand_status", "creative_status")
    )
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
            ("브랜드 분석", session["brand_status"]),
            ("소재 분석", session["creative_status"]),
            ("종합 분석", synthesis_status_for_index),
        ])

    st.write("")

    # Workspace 1차 탭은 항상 4개(Market/Brand/Creative/Synthesis) — Target은 독립 탭이 아니다.
    tab_market, tab_brand, tab_creative, tab_synth = st.tabs(
        ["01 시장분석", "02 브랜드분석", "03 소재분석", "04 종합분석"]
    )
    with tab_market:
        market_tab.render(session)
    with tab_brand:
        brand_tab.render(session)
    with tab_creative:
        creative_tab.render(session)
    with tab_synth:
        synthesis_tab.render(session)
