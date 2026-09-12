"""종합분석 탭 — PRD §7-4·§7-11-(5). 시장/타겟/브랜드/소재 4개 기능 중 최소 1개 완료 시 잠금 해제(§6-1)."""
from __future__ import annotations

import streamlit as st

from ui.components import feature_card, status_icon


def render(session: dict):
    unlocked = any(
        session.get(k) in ("완료", "부분 실패")
        for k in ("market_status", "brand_status", "creative_status")
    ) or session.get("target_status") == "confirmed"

    st.subheader(f"{'○' if unlocked else '🔒'} 종합분석")

    if not unlocked:
        feature_card(
            "🏁", "이 기능은 다른 4개 기능의 결과를 조합합니다",
            "시장/타겟/브랜드/소재 중 최소 1개 이상이 완료되면 잠금 해제됩니다 (§6-1).",
        )
        return

    feature_card(
        "🏁", "이 기능은 다음을 산출합니다",
        "· Share of Search / Share of Ads / Share of Voice(뉴스)\n"
        "· 포지셔닝맵, White Space\n"
        "· 한 줄 총평 (AI Recommendation)",
    )
    st.button("종합분석 시작하기 (준비 중)", disabled=True, key="btn_start_synthesis")
    st.caption("시장·타겟·브랜드·소재 결과가 쌓이면 별도 수집 없이 조합만으로 산출합니다 (§7-4).")
