"""분석하기 — STEP 1 브랜드 설정 → STEP 2 분석 Workspace (PRD §16-1·§16-2·§16-4).

타겟 입력 필드는 없습니다 (★ 15차 개정) — 타겟은 타겟분석 탭에서 게이트 통과 후 추천됩니다.
"""
from __future__ import annotations

import streamlit as st

from config.theme import glass_marker
from core.analyzers.recommender import recommend_category, recommend_competitors
from database.db import create_session
from ui import brand_tab, creative_tab, market_tab, synthesis_tab, target_tab
from ui.components import status_icon

st.session_state.setdefault("step", "input")
st.session_state.setdefault("session", None)

# ── STEP 1: 브랜드 설정 (입력) ──────────────────────────────────────────
if st.session_state.step == "input":
    st.markdown(
        "<span class='adetect-eyebrow'>Step 1</span>"
        "<p class='adetect-hero-title' style='font-size:1.7rem;'>브랜드 설정</p>",
        unsafe_allow_html=True,
    )
    st.write("")
    with st.container():
        glass_marker()
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
        st.caption("타겟은 여기서 입력하지 않습니다 — 시장분석·브랜드분석 결과를 근거로 이후 타겟분석 탭에서 추천됩니다.")
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
        "<span class='adetect-eyebrow'>Step 1 · Confirm</span>"
        "<p class='adetect-hero-title' style='font-size:1.7rem;'>브랜드명을 기반으로 추천했습니다</p>",
        unsafe_allow_html=True,
    )
    st.write("")

    category = draft["category"] or recommend_category(draft["brand_name"])
    user_competitors = [c.strip() for c in draft["competitors_raw"].split(",") if c.strip()]
    ai_competitors = recommend_competitors(draft["brand_name"], category)
    # 사용자 입력 경쟁사 우선 (§7-10) — 입력이 있으면 그 값 우선, 부족한 슬롯만 AI가 보완
    candidates = user_competitors + [c for c in ai_competitors if c not in user_competitors]

    with st.container():
        glass_marker()
        category = st.text_input("카테고리", value=category, key="confirm_category")
        st.caption("경쟁사 — 사용자가 직접 입력했다면 그 값이 우선 반영됩니다 (§7-10)")
        selected = []
        for c in candidates:
            checked = st.checkbox(c, value=True, key=f"competitor_{c}")
            if checked:
                selected.append(c)
        extra = st.text_input("경쟁사 추가 (쉼표로 구분)", key="confirm_extra_competitors")
        selected += [c.strip() for c in extra.split(",") if c.strip()]

        col1, col2 = st.columns([1, 3])
        back = col1.button("이전", key="btn_confirm_back")
        go = col2.button("확정하고 Workspace로 이동", type="primary", key="btn_confirm_go")

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

# ── STEP 2: 분석 Workspace (5개 탭) ─────────────────────────────────────
elif st.session_state.step == "workspace":
    session = st.session_state.session

    target_display = session.get("confirmed_target") or "타겟 미확정"
    target_gate_open = session["market_status"] in ("완료", "부분 실패") and session["brand_status"] in ("완료", "부분 실패")
    if not target_gate_open:
        target_icon = "🔒"
    elif session["target_status"] == "confirmed":
        target_icon = status_icon("완료")
    else:
        target_icon = status_icon("미실행")

    synthesis_gate_open = any(
        session[k] in ("완료", "부분 실패") for k in ("market_status", "brand_status", "creative_status")
    ) or session["target_status"] == "confirmed"
    synthesis_icon = status_icon("미실행") if synthesis_gate_open else "🔒"

    strip = (
        f"<div class='adetect-status-strip'>"
        f"<b>{session['brand_name']}</b>"
        f"<span>{session['category']}</span>"
        f"<span>{target_display}</span>"
        f"<span class='adetect-status-item'>시장 {status_icon(session['market_status'])}</span>"
        f"<span class='adetect-status-item'>타겟 {target_icon}</span>"
        f"<span class='adetect-status-item'>브랜드 {status_icon(session['brand_status'])}</span>"
        f"<span class='adetect-status-item'>소재 {status_icon(session['creative_status'])}</span>"
        f"<span class='adetect-status-item'>종합 {synthesis_icon}</span>"
        f"</div>"
    )
    st.markdown(strip, unsafe_allow_html=True)

    if st.button("새 브랜드로 다시 시작", key="btn_reset_session"):
        st.session_state.session = None
        st.session_state.step = "input"
        st.rerun()

    tab_market, tab_target, tab_brand, tab_creative, tab_synth = st.tabs(
        ["시장분석", "타겟분석", "브랜드분석", "소재분석", "종합분석"]
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
