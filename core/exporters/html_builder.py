"""소재분석 HTML 리포트 빌더 (PRD §16-5·§21-4).

인라인 CSS만 사용하는 단일 HTML 파일을 만든다. 소재 이미지는 가능하면 base64로 통째로
파일 안에 넣어 오프라인에서도 보이게 하고(§21-4), 원본 다운로드에 실패한 항목만 원본 URL로
직접 링크하는 형태로 조용히 폴백한다 — 이미지 하나 실패했다고 리포트 생성 전체가 죽으면 안 된다.
"""
from __future__ import annotations

import base64
import html
from datetime import datetime

import requests

from core.analyzers.creative_analyzer import compact_platforms


def _fetch_data_uri(url: str | None, timeout: float = 4.0) -> str | None:
    """이미지를 내려받아 data URI로 변환. 실패하면 None(호출부가 원본 URL로 폴백)."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        encoded = base64.b64encode(resp.content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"
    except requests.RequestException:
        return None


def _img_tag(ad: dict) -> str:
    url = ad.get("thumbnail_url") or ad.get("image_url")
    if not url:
        return ""
    # 목업 데이터는 이미 로컬에서 만든 data URI라 그대로 쓰면 된다 — 네트워크 재요청 불필요.
    src = url if url.startswith("data:") else (_fetch_data_uri(url) or html.escape(url, quote=True))
    return f'<img src="{src}" alt="" loading="lazy" />'


def _brand_label(b: dict) -> str:
    return b["brand"] + (" (자사)" if b["is_own"] else "")


def _ad_row(ad: dict) -> str:
    # 정보 위계: 헤드라인이 핵심 카피, 노출 지면(Placement)은 마지막 secondary metadata(§7).
    return f"""
    <tr>
      <td class="thumb">{_img_tag(ad)}</td>
      <td>{html.escape(ad.get("ad_id", ""))}</td>
      <td class="col-headline">{html.escape(ad.get("headline") or "-")}</td>
      <td>{html.escape((ad.get("body") or "-")[:200])}</td>
      <td>{html.escape(ad.get("cta") or "-")}</td>
      <td>{html.escape(ad.get("format", ""))}</td>
      <td>{ad.get("ad_running_days") if ad.get("ad_running_days") is not None else "확인 불가"}</td>
      <td class="col-placement">{html.escape(compact_platforms(ad.get("publisher_platforms")))}</td>
    </tr>"""


def _brand_section(b: dict) -> str:
    ad_rows = "".join(_ad_row(ad) for ad in b["ads"]) or (
        "<tr><td colspan='8' class='muted'>활성 광고가 0건입니다.</td></tr>"
    )
    return f"""
    <section>
      <h2>{html.escape(_brand_label(b))} <span class="muted">· 활성 광고 {b['ad_count']}건</span></h2>
      <h3>소재 목록</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>미리보기</th><th>소재 ID</th><th>헤드라인</th><th>본문</th><th>CTA</th>
          <th>포맷</th><th>운영일수</th><th>노출 지면</th></tr></thead>
          <tbody>{ad_rows}</tbody>
        </table>
      </div>
    </section>"""


_CSS = """
body { background:#0B0C10; color:#F2F2F0; font-family:-apple-system,Pretendard,sans-serif; margin:0; padding:2.5rem 3rem; }
h1 { font-size:1.9rem; font-weight:600; margin-bottom:0.2rem; }
h2 { font-size:1.25rem; font-weight:600; margin-top:2.4rem; border-top:1px solid rgba(255,255,255,0.12); padding-top:1.4rem; }
h3 { font-size:0.95rem; color:#C9A227; text-transform:uppercase; letter-spacing:0.08em; margin-top:1.4rem; }
.muted { color:#9A9A9E; font-weight:400; font-size:0.85rem; }
.meta { color:#9A9A9E; font-size:0.9rem; margin-bottom:1.6rem; }
.insight { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:0.8rem; padding:1.1rem 1.4rem; margin:1rem 0; }
.table-wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:0.82rem; }
th, td { text-align:left; padding:0.5rem 0.7rem; border-bottom:1px solid rgba(255,255,255,0.08); vertical-align:top; }
th { color:#9A9A9E; text-transform:uppercase; font-size:0.68rem; letter-spacing:0.06em; white-space:nowrap; }
td.thumb img { width:64px; height:64px; object-fit:cover; border-radius:0.4rem; background:rgba(255,255,255,0.05); }
td.col-headline { min-width:220px; max-width:320px; color:#F2F2F0; font-weight:560; white-space:normal; }
td.col-placement { max-width:130px; color:#7A7A80; font-size:0.76rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
footer { margin-top:3rem; color:#5C5C60; font-size:0.75rem; }
"""


def build_creative_html(session: dict, result: dict) -> str:
    """§7-11-(4) 소재분석 결과를 오프라인 열람 가능한 단일 HTML 문자열로 변환."""
    own = result["own"]
    competitors = result["competitors"]
    all_brands = [own, *competitors]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    insight = result["creative_key_visual"]

    sections = "".join(_brand_section(b) for b in all_brands)

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{html.escape(session["brand_name"])} 소재분석</title>
<style>{_CSS}</style></head>
<body>
  <h1>{html.escape(session["brand_name"])} — 소재분석 리포트</h1>
  <p class="meta">경쟁사 {len(competitors)}개 브랜드 비교 · 생성일시 {generated_at} · ADetect</p>
  <div class="insight">
    <div class="muted">FACT · Confidence: {html.escape(insight.get("confidence", "-"))}</div>
    <p>{html.escape(insight.get("insight", ""))}</p>
  </div>
  {sections}
  <footer>이 리포트는 Meta Ads Library에서 수집한 활성(active) 광고 소재 기준입니다.
  일부 소재 이미지는 원본 서버 링크가 만료되면 보이지 않을 수 있습니다.</footer>
</body></html>"""
