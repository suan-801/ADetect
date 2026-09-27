# LEGACY — 현재 런타임(app.py 네비게이션·신규 화면)에서 import/실행하지 않는다. (2026-09-27 검색 확인, PRD §0 18차 개정)
# 신규 UI: pages/2_analyze.py → ui/project_workspace.py
# 신규 데이터 흐름: core/projects.py, core/project_jobs.py
# 사용 금지 이유: 16차 개정의 소재분석 탭(과거 Reference Implementation). 18차에서는 Meta 광고를 자료 종류 'meta'로 core/project_jobs.py를 통해 수집한다. 상태/다운로드 패턴 참고용으로만 남긴다.
# 새 화면에 다시 연결하지 말 것. 기존 데이터 호환 검토 전까지 삭제하지 않고 보존한다.

"""소재분석 탭 — PRD §7-11-(4). 자사+경쟁사 통합, DA(Meta Ads) 전용.

core/analyzers/creative_analyzer.py의 run_creative_analysis()를 호출해 렌더링합니다.
APIFY_API_TOKEN이 있으면 실제 Meta Ads Library 소재를 가져오고(config.settings.APIFY_MOCK),
없으면 목업 데이터로 동작합니다 — 두 경우 모두 이 탭의 렌더링 로직은 동일합니다.

"소재 ID"에 마우스를 올리면 소재 이미지(영상은 미리보기 썸네일)가 뜨는 미리보기는
st.dataframe이 셀 안에 임의 HTML을 넣을 수 없어서 직접 HTML 테이블로 렌더링합니다(§16-2).
"""
from __future__ import annotations

import html

import streamlit as st

from config import settings
from core.exporters.artifact_store import save_artifact
from ui.job_control import start, pending
from core.analyzers.creative_analyzer import compact_platforms, run_creative_analysis
from core.exporters.excel_builder import build_creative_excel
from core.exporters.html_builder import build_creative_html
from core.exporters.packager import build_creative_zip
from core.scrapers.ad_library import ApifyFetchError
from core.scrapers.naver_api import NaverApiError
from ui.components import feature_intro, metric_row, render_insight_card, sample_data_notice, status_icon, tab_header


def _brand_label(b: dict) -> str:
    return b["brand"] + (" (자사)" if b["is_own"] else "")


def _ad_id_cell(ad: dict) -> str:
    """소재 ID 셀 — thumbnail_url이 있으면 마우스오버 시 이미지 미리보기를 띄웁니다."""
    ad_id = html.escape(ad["ad_id"])
    thumb = ad.get("thumbnail_url")
    if not thumb:
        return ad_id
    alt = "영상 미리보기" if ad.get("format") == "video" else "소재 이미지"
    return (
        f'<span class="adetect-ad-thumb-hover">{ad_id}'
        f'<span class="adetect-ad-thumb-popup">'
        f'<img src="{html.escape(thumb, quote=True)}" alt="{alt}" loading="lazy" />'
        f"</span></span>"
    )


def _render_html_table(rows: list[dict], columns: list[tuple[str, str, str | None]]):
    """columns: [(표시 헤더, row dict 키, 선택적 CSS class)]. 셀 값은 이미 HTML-safe 문자열이어야 합니다.

    Headline이 다른 metadata보다 먼저·크게 보이고, Placement는 1줄을 넘지 않는 secondary
    metadata로 압축되도록 col-headline/col-placement 클래스를 지원한다(§6 정보 위계 변경).
    """
    if not rows:
        st.caption("활성 광고가 0건입니다.")
        return
    thead = "".join(f"<th>{html.escape(label)}</th>" for label, _, _ in columns)
    body_rows = []
    for row in rows:
        cells = []
        for _, key, css_class in columns:
            cls_attr = f' class="{css_class}"' if css_class else ""
            cells.append(f"<td{cls_attr}>{row[key]}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    st.markdown(
        f'<div class="adetect-ad-table-wrap"><table class="adetect-ad-table">'
        f"<thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render(session: dict):
    status = session.get("creative_status", "미실행")
    tab_header("CREATIVE", "소재분석", status_icon(status))

    if pending(session, "creative"):
        return
    if status in ("미실행", "전체 실패", "취소"):
        session["creative_force"] = st.checkbox("24시간 캐시 무시하고 새로 수집", value=False, key="fresh_creative")
        feature_intro([
            "Meta Ads Library 활성 광고 소재 (FB+IG 노출 포함)",
            "헤드라인·CTA·포맷 등 실제 소재 정보",
            "운영기간 분석 (단기/중기/장기)",
        ])
        st.write("")
        if status == "전체 실패":
            st.error("소재 데이터 수집에 실패했습니다. Apify 토큰/액터 상태를 확인한 뒤 다시 시도해주세요.")

        targets = [session["brand_name"], *session.get("competitors", [])]
        overrides = session.setdefault("creative_meta_overrides", {})
        if not settings.APIFY_MOCK:
            with st.expander("메타 라이브러리 페이지 직접 지정 (선택 — 자동 추천이 부정확할 때)"):
                st.caption(
                    "자사는 공식 페이지 확인이 필요합니다. 경쟁사는 인증·팔로워 신호를 우선하고, 없으면 정확히 일치하는 이름만 사용합니다 "
                    "— 동명이인·무관 광고주가 섞이면 엉뚱한 결과가 나올 수 있습니다. Meta Ads Library에서 "
                    "해당 브랜드의 정확한 광고 페이지를 찾아 URL을 붙여넣거나, 정확한 페이지명을 입력하세요."
                )
                for name in targets:
                    overrides[name] = st.text_input(
                        f"{name} — Meta Ads Library URL 또는 정확한 페이지명",
                        value=overrides.get(name, ""),
                        key=f"meta_override_{name}",
                    )

        if st.button("소재분석 시작하기", type="primary", key="btn_start_creative"):
            active_overrides = {k: v.strip() for k, v in overrides.items() if v.strip()}
            def execute(snapshot):
                result = run_creative_analysis(snapshot["brand_name"], snapshot.get("competitors", []), meta_overrides=active_overrides)
                result["sample_sources"] = ["meta_ads"] if settings.APIFY_MOCK else []
                return result
            start(session, "creative", execute, {"brand":session["brand_name"],"competitors":session.get("competitors", []),"overrides":active_overrides})
        return

    result = session["creative_result"]
    for note in result.get("limitations", []):
        st.caption(note)
    for error in result.get("errors", []):
        st.warning(error)
    own = result["own"]
    competitors = result["competitors"]
    all_brands = [own, *competitors]

    tabs = st.tabs(["개요", "소재 목록", "Creative Analysis", "Long Running"])

    with tabs[0]:
        if result.get("sample_sources"):
            sample_data_notice()
        metric_row([
            ("수집 활성 소재", str(sum(b["ad_count"] for b in all_brands)), None),
            ("자사 소재", "미확인" if own.get("collection_failed") else str(own["ad_count"]), None),
            ("비교 경쟁사", str(len(competitors)), None),
        ])
        st.write(
            f"**{own['brand']}** vs 경쟁사 {len(competitors)}개 브랜드의 활성 광고 소재를 "
            f"동일한 기준으로 비교했습니다. (총 {sum(b['ad_count'] for b in all_brands)}건)"
        )
        st.caption("소재 ID에 마우스를 올리면 이미지(영상은 썸네일)를 미리 볼 수 있습니다 — '소재 목록'/'Creative Analysis' 탭 참고.")
        render_insight_card("소재 총평", result["creative_key_visual"], kind="FACT")

        if not settings.APIFY_MOCK:
            with st.expander("브랜드별로 실제 매칭된 Meta 페이지 확인"):
                st.caption("의도한 브랜드와 다른 페이지가 매칭됐다면, 위 '소재분석 시작하기' 화면의 "
                           "'메타 라이브러리 페이지 직접 지정'에 정확한 URL/페이지명을 입력하고 다시 수집하세요.")
                for b in all_brands:
                    resolved = b["ads"][0]["resolved_page_name"] if b["ads"] else None
                    st.caption(f"{_brand_label(b)} → {resolved or '매칭된 활성 광고 없음'}")
            if st.button("설정 변경 후 다시 수집", key="btn_edit_creative_overrides"):
                session["creative_status"] = "미실행"
                st.rerun()

    with tabs[1]:
        # 정보 우선순위: 브랜드 → 소재ID → 헤드라인(핵심 카피) → CTA → 포맷 → 운영일수 →
        # 노출 지면(secondary, 1줄 압축) — Placement가 Headline보다 먼저/길게 나오던 문제 수정(§6).
        rows = [
            {
                "브랜드": html.escape(_brand_label(b)),
                "소재 ID": _ad_id_cell(ad),
                "헤드라인": html.escape(ad["headline"] or "-"),
                "CTA": html.escape(ad["cta"] or "-"),
                "포맷": html.escape(ad["format"]),
                "운영일수": ad["ad_running_days"] if ad.get("ad_running_days") is not None else "확인 불가",
                "노출 지면": html.escape(compact_platforms(ad.get("publisher_platforms"))),
            }
            for b in all_brands
            for ad in b["ads"]
        ]
        _render_html_table(rows, [
            ("브랜드", "브랜드", None), ("소재 ID", "소재 ID", None),
            ("헤드라인", "헤드라인", "col-headline"), ("CTA", "CTA", None),
            ("포맷", "포맷", None), ("운영일수", "운영일수", None),
            ("노출 지면", "노출 지면", "col-placement"),
        ])

    with tabs[2]:
        rows = [
            {
                "브랜드": html.escape(_brand_label(b)),
                "소재 ID": _ad_id_cell(ad),
                "헤드라인": html.escape(ad["headline"] or "-"),
                "본문": html.escape((ad["body"] or "-")[:160]),
            }
            for b in all_brands
            for ad in b["ads"]
        ]
        _render_html_table(rows, [
            ("브랜드", "브랜드", None), ("소재 ID", "소재 ID", None),
            ("헤드라인", "헤드라인", "col-headline"), ("본문", "본문", None),
        ])

    with tabs[3]:
        import pandas as pd
        rows = [
            {
                "브랜드": _brand_label(b),
                "운영기간": lr["running_days_bucket"],
                "평균 운영일수": lr["avg_running_days"] if lr["avg_running_days"] is not None else "확인 불가",
                "소재 수": lr["ad_count"],
            }
            for b in all_brands
            for lr in b["long_running_analysis"]
        ]
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.caption("활성 광고가 0건입니다.")

    st.divider()
    _render_downloads(session, result)


def _render_downloads(session: dict, result: dict):
    """HTML/Excel은 즉시 생성되는 만큼 가볍고, ZIP은 원본 이미지/영상을 실제로 내려받아
    묶으므로 소재 수에 따라 시간이 걸릴 수 있다 — 그래서 셋 다 '생성 → 다운로드' 2단계로
    통일해서, 무거운 ZIP도 같은 패턴 안에서 자연스럽게 스피너를 보여줄 수 있게 했다."""
    brand = session["brand_name"]
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("HTML 리포트 생성", key="gen_html_creative"):
            with st.spinner("HTML 리포트 생성 중... (이미지 포함)"):
                session["creative_export_html"] = build_creative_html(session, result)
                save_artifact(session.get("creative_run_id"), "creative", "html", session["creative_export_html"])
        if session.get("creative_export_html"):
            st.download_button(
                "HTML 다운로드", data=session["creative_export_html"],
                file_name=f"{brand}_소재분석.html", mime="text/html", key="dl_html_creative",
            )

    with c2:
        if st.button("Excel 생성", key="gen_excel_creative"):
            with st.spinner("Excel 파일 생성 중..."):
                session["creative_export_excel"] = build_creative_excel(result)
                save_artifact(session.get("creative_run_id"), "creative", "xlsx", session["creative_export_excel"])
        if session.get("creative_export_excel"):
            st.download_button(
                "Excel 다운로드", data=session["creative_export_excel"],
                file_name=f"{brand}_소재분석.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_excel_creative",
            )

    with c3:
        if st.button("이미지/영상 ZIP 생성", key="gen_zip_creative"):
            with st.spinner("이미지/영상 원본을 내려받아 압축하는 중... (소재 수에 따라 시간이 걸릴 수 있습니다)"):
                session["creative_export_zip"] = build_creative_zip(result)
                save_artifact(session.get("creative_run_id"), "creative", "zip", session["creative_export_zip"])
        if session.get("creative_export_zip"):
            st.download_button(
                "ZIP 다운로드", data=session["creative_export_zip"],
                file_name=f"{brand}_소재원본.zip", mime="application/zip", key="dl_zip_creative",
            )
