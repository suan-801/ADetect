"""분석하기 — STEP 1 브랜드 설정 → STEP 2 분석 Workspace (PRD §16-1·§16-2·§16-4).

타겟 입력 필드는 없습니다 (★ 15차 개정) — 타겟은 타겟분석 탭에서 게이트 통과 후 추천됩니다.
Workspace의 5개 기능은 `st.tabs`를 유지합니다 — PRD §6-1이 "지속되는 5개 탭"으로 명시하고
있고(탭 전환과 무관하게 각 탭의 session 상태가 항상 최신으로 유지되어야 함), 이를
`st.segmented_control` 기반 단일 렌더링으로 바꾸면 비활성 탭의 상태 갱신 타이밍이 달라집니다.
대신 기본 tab underline/pill을 CSS로 전면 제거하고 절제된 segmented 느낌으로 재도색했습니다
(config/theme.py `[data-baseweb="tab-*"]` 규칙 참고).
"""
from __future__ import annotations

import streamlit as st

from config.theme import cta_row_marker, glass_marker
from core.analyzers.recommender import recommend_category, recommend_competitors
from database.db import create_session
from ui import brand_tab, creative_tab, market_tab, synthesis_tab, target_tab
from ui.components import brand_context_bar, status_icon

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
        glass_marker()
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

# ── STEP 2: 분석 Workspace (5개 기능, segmented navigation) ────────────
elif st.session_state.step == "workspace":
    session = st.session_state.session

    target_gate_open = session["market_status"] in ("완료", "부분 실패") and session["brand_status"] in ("완료", "부분 실패")
    if not target_gate_open:
        target_status_for_chip = "🔒"
    elif session["target_status"] == "confirmed":
        target_status_for_chip = "완료"
    else:
        target_status_for_chip = "미실행"

    synthesis_gate_open = any(
        session[k] in ("완료", "부분 실패") for k in ("market_status", "brand_status", "creative_status")
    ) or session["target_status"] == "confirmed"
    synthesis_status_for_chip = "미실행" if synthesis_gate_open else "🔒"

    status_items = [
        ("시장", session["market_status"]),
        ("브랜드", session["brand_status"]),
        ("소재", session["creative_status"]),
        ("타겟", target_status_for_chip),
        ("종합", synthesis_status_for_chip),
    ]
    brand_context_bar(session, status_items)

    if st.button("새 브랜드로 다시 시작", key="btn_reset_session"):
        st.session_state.session = None
        st.session_state.step = "input"
        st.rerun()

    # 분석 순서: 시장 → 브랜드 → 소재 → 타겟 → 종합 (타겟·종합은 게이트형, §6-1)
    section_status = {
        "시장분석": session["market_status"],
        "브랜드분석": session["brand_status"],
        "소재분석": session["creative_status"],
        "타겟분석": target_status_for_chip,
        "종합분석": synthesis_status_for_chip,
    }
    tab_labels = [
        f"{label}  {'🔒' if st_val == '🔒' else status_icon(st_val)}" for label, st_val in section_status.items()
    ]
    tab_market, tab_brand, tab_creative, tab_target, tab_synth = st.tabs(tab_labels)
    with tab_market:
        market_tab.render(session)
    with tab_brand:
        brand_tab.render(session)
    with tab_creative:
        creative_tab.render(session)
    with tab_target:
        target_tab.render(session)
    with tab_synth:
        synthesis_tab.render(session)
