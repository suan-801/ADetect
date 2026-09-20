"""종합분석 탭 — PRD §7-4·§7-11-(5)·§15. 시장/브랜드/소재 3개 기능 중 최소 1개 완료 시 잠금 해제(§6-1).

★ SYNTHESIS IMPLEMENTATION CONTRACT (담당: 종합분석 파트)

현재 상태 — Target Insight subsection만 구현 완료(근거 기반, `insight_synthesizer.
build_target_insight()`). Executive Summary/Market Signal/Brand Position/Creative Signal/
White Space/Recommended Action(§7-4)은 화면 골격(placeholder)만 있고 실제 계산 로직은 없음.

Required input: session["market_result"]/["brand_result"]/["creative_result"] (있는 것만 사용,
없으면 그 신호는 건너뛴다 — 새로운 수집을 추가하지 않는다, §15).
Required output(§7-4): 최종 결과는 insight/source/evidence/confidence를 갖춘 AI/REC 필드와,
그 근거가 되는 FACT 필드로 나뉜다 — `build_insight()` 스키마를 그대로 쓸 것.
Required states: Synthesis 게이트(잠금/해제)는 이미 구현됨(위 unlocked 판정). 각 subsection은
근거가 부족하면 `insufficient_data`로 개별 처리하고, 다른 subsection까지 막지 않는다 —
build_target_insight()가 그 기준 구현이다.

Do not:
- Workspace 1차 탭 순서를 바꾸지 않는다.
- 연령/성별 등 지금 데이터 모델에 없는 세그먼트 인구통계를 지어내지 않는다(§0·§14).
- source/evidence/confidence 없는 판단을 확정 결과처럼 보여주지 않는다(§8).

Target Insight는 독립 function_run이 아니라 이 탭의 subsection이다(§15) — 시장분석과
브랜드분석이 모두 완료(또는 부분 실패)여야 생성되며, 근거가 부족하면 임의 인구통계를
만들지 않고 insufficient_data 또는 정직한 안내 문구로 처리한다.
"""
from __future__ import annotations

import streamlit as st

from core.analyzers.insight_synthesizer import build_target_insight
from ui.components import feature_intro, prototype_notice, render_insight_card, tab_header

# §7-4 결과 구조 — Synthesis 담당자의 UI contract. 각 항목은 실제 계산 로직이 생기기 전까지
# placeholder로만 보여준다(가짜 수치를 만들지 않는다, CLAUDE.md 규칙 5).
_RESULT_STRUCTURE = [
    ("Executive Summary", "종합 총평 한 줄 — 시장·브랜드·소재 신호를 하나의 결론으로 압축"),
    ("Market Signal", "Share of Search, 검색량 추이 요약"),
    ("Brand Position", "경쟁사 대비 자사 포지션, Share of Voice(뉴스)"),
    ("Creative Signal", "Share of Ads, 소재 운영 패턴 요약"),
    ("Target Insight", "시장+브랜드 근거 기반 — 아래 subsection에서 이미 구현 완료"),
    ("White Space", "경쟁 밀도가 낮은 시장 기회 영역"),
    ("Recommended Action", "위 신호를 종합한 실행 추천 (AI Recommendation)"),
]


def render(session: dict):
    unlocked = any(
        session.get(k) in ("완료", "부분 실패")
        for k in ("market_status", "brand_status", "creative_status")
    )

    tab_header("SYNTHESIS", "종합분석", "○" if unlocked else "🔒")
    prototype_notice("프로토타입 화면 · Target Insight만 근거 기반 실제 로직, 나머지 항목은 결과 구조 골격")

    if not unlocked:
        feature_intro(["시장/브랜드/소재 중 최소 1개 이상이 완료되면 잠금 해제됩니다."])
        return

    feature_intro([
        "Share of Search / Share of Ads / Share of Voice(뉴스)",
        "포지셔닝맵, White Space",
        "한 줄 총평 (AI Recommendation)",
    ])
    st.button("종합분석 시작하기 (준비 중)", disabled=True, key="btn_start_synthesis")
    st.caption("시장·브랜드·소재 결과가 쌓이면 별도 수집 없이 조합만으로 산출합니다.")

    with st.expander("종합분석 결과 구조 (담당자용 미리보기 — 실제 결과 아님)"):
        for title, desc in _RESULT_STRUCTURE:
            st.markdown(f"**{title}** — {desc}")

    st.divider()
    st.markdown('<div class="adetect-section-label">TARGET INSIGHT</div>', unsafe_allow_html=True)
    market_ok = session.get("market_status") in ("완료", "부분 실패")
    brand_ok = session.get("brand_status") in ("완료", "부분 실패")
    if not (market_ok and brand_ok):
        st.caption("시장분석과 브랜드분석이 모두 완료되면 생성됩니다.")
    else:
        target_insight = build_target_insight(
            session.get("market_result"), session.get("brand_result"), session.get("creative_result")
        )
        if target_insight.get("status") == "insufficient_data":
            st.caption(target_insight["message"])
        else:
            render_insight_card("핵심 타겟", target_insight, kind="AI")
