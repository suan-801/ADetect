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
from core.analyzers.creative_analyzer import run_creative_analysis
from core.exporters.excel_builder import build_creative_excel
from core.exporters.html_builder import build_creative_html
from core.exporters.packager import build_creative_zip
from core.scrapers.ad_library import ApifyFetchError
from core.scrapers.naver_api import NaverApiError
from ui.components import feature_intro, render_insight_card, sample_data_notice, status_icon, tab_header


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


def _render_html_table(rows: list[dict], columns: list[tuple[str, str]]):
    """columns: [(표시 헤더, row dict 키)]. 각 셀 값은 이미 HTML-safe 문자열이어야 합니다."""
    if not rows:
        st.caption("활성 광고가 0건입니다.")
        return
    thead = "".join(f"<th>{html.escape(label)}</th>" for label, _ in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{row[key]}</td>" for _, key in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    st.markdown(
        f'<div class="adetect-ad-table-wrap"><table class="adetect-ad-table">'
        f"<thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render(session: dict):
    status = session.get("creative_status", "미실행")
    tab_header("CREATIVE", "소재분석", status_icon(status))

    if status in ("미실행", "전체 실패"):
        feature_intro([
            "Meta Ads Library 활성 광고 소재 (FB+IG 노출 포함)",
            "소구포인트 다중 라벨 태깅 및 비중",
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
                    "자동 매칭은 브랜드명으로 검색한 결과 중 가장 많이 등장한 페이지를 추정해 사용합니다 "
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
            try:
                with st.status("자사 및 경쟁사 광고 소재를 수집·분석하는 중...", expanded=True) as status_box:
                    def _on_progress(msg: str, _box=status_box):
                        _box.update(label=msg)

                    result = run_creative_analysis(
                        session["brand_name"], session.get("competitors", []),
                        meta_overrides=active_overrides, on_progress=_on_progress,
                    )
                    status_box.update(label="수집 완료", state="complete")
                session["creative_result"] = result
                session["creative_status"] = result["status"]
            except (ApifyFetchError, NaverApiError) as exc:
                session["creative_status"] = "전체 실패"
                st.error(f"소재 수집 실패: {exc}")
            st.rerun()
        return

    result = session["creative_result"]
    own = result["own"]
    competitors = result["competitors"]
    all_brands = [own, *competitors]

    tabs = st.tabs(["개요", "소재 목록", "Creative Analysis", "Appeal Distribution", "Long Running"])

    with tabs[0]:
        if settings.APIFY_MOCK:
            sample_data_notice()
        st.write(
            f"**{own['brand']}** vs 경쟁사 {len(competitors)}개 브랜드의 활성 광고 소재를 "
            f"동일한 기준으로 비교했습니다. (총 {sum(b['ad_count'] for b in all_brands)}건)"
        )
        st.caption("소재 ID에 마우스를 올리면 이미지(영상은 썸네일)를 미리 볼 수 있습니다 — '소재 목록'/'Creative Analysis' 탭 참고.")
        render_insight_card("소재 총평", result["creative_key_visual"], kind="AI")

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
        rows = [
            {
                "브랜드": html.escape(_brand_label(b)),
                "소재 ID": _ad_id_cell(ad),
                "포맷": html.escape(ad["format"]),
                "노출 지면": html.escape(ad["publisher_platforms"] or "-"),
                "헤드라인": html.escape(ad["headline"] or "-"),
                "CTA": html.escape(ad["cta"] or "-"),
                "운영일수": ad["ad_running_days"] if ad.get("ad_running_days") is not None else "확인 불가",
            }
            for b in all_brands
            for ad in b["ads"]
        ]
        _render_html_table(rows, [
            ("브랜드", "브랜드"), ("소재 ID", "소재 ID"), ("포맷", "포맷"),
            ("노출 지면", "노출 지면"), ("헤드라인", "헤드라인"), ("CTA", "CTA"), ("운영일수", "운영일수"),
        ])

    with tabs[2]:
        rows = [
            {
                "브랜드": html.escape(_brand_label(b)),
                "소재 ID": _ad_id_cell(ad),
                "헤드라인": html.escape(ad["headline"] or "-"),
                "본문": html.escape((ad["body"] or "-")[:120]),
                "소구포인트": html.escape(", ".join(ad["appeal_tags"])),
            }
            for b in all_brands
            for ad in b["ads"]
        ]
        _render_html_table(rows, [
            ("브랜드", "브랜드"), ("소재 ID", "소재 ID"), ("헤드라인", "헤드라인"),
            ("본문", "본문"), ("소구포인트", "소구포인트"),
        ])

    with tabs[3]:
        import pandas as pd
        for b in all_brands:
            st.markdown(f"**{_brand_label(b)}**")
            if b["appeal_distribution"]:
                st.dataframe(
                    pd.DataFrame(b["appeal_distribution"]).rename(columns={
                        "appeal_tag": "소구포인트", "count": "건수", "pct_of_brand_total": "비중(%)",
                    }),
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("활성 광고가 0건이라 소구 비중을 산출할 수 없습니다.")

    with tabs[4]:
        import pandas as pd
        rows = [
            {
                "브랜드": _brand_label(b),
                "운영기간": lr["running_days_bucket"],
                "주요 소구포인트": ", ".join(lr["dominant_appeal_tags"]),
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
        if session.get("creative_export_html"):
            st.download_button(
                "HTML 다운로드", data=session["creative_export_html"],
                file_name=f"{brand}_소재분석.html", mime="text/html", key="dl_html_creative",
            )

    with c2:
        if st.button("Excel 생성", key="gen_excel_creative"):
            with st.spinner("Excel 파일 생성 중..."):
                session["creative_export_excel"] = build_creative_excel(result)
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
        if session.get("creative_export_zip"):
            st.download_button(
                "ZIP 다운로드", data=session["creative_export_zip"],
                file_name=f"{brand}_소재원본.zip", mime="application/zip", key="dl_zip_creative",
            )
