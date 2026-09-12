#!/usr/bin/env python3
"""
/12-period-report — 기간 리포트 HTML + PDF (주간/월간/캠페인).

데이터:
- Meta API 직접 풀 (필수, ROAS 진실값)
- GA4 service account 있으면 자동 흡수, 없으면 placeholder
- Clarity CRO 마크다운 있으면 흡수 (outputs/cro/ 최신)

산출:
- outputs/period/{brand}/{since}_{until}-v{N}.html
- outputs/period/{brand}/{since}_{until}-v{N}.pdf (Playwright chromium)

사용:
  python3 period_report.py --period weekly --from 2026-05-05 --to 2026-05-11
  python3 period_report.py --period monthly --from 2026-05-01 --to 2026-05-31
  python3 period_report.py --period campaign --from 2026-05-01 --to 2026-05-11 --campaign-id 12345
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja2 import Environment, FileSystemLoader, select_autoescape

from lib.env_loader import load_env, require
from lib.meta_client import MetaClient, aggregate, freshness_tier, AdRow
from lib.kpi_config import load as load_kpi, targets as load_targets

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
TEMPLATES = ROOT / "templates" / "period_v1"
OUTPUTS = ROOT.parent / "12_period"
CRO_DIR = ROOT.parent / "11_dashboard" / "cro"
DAILY_DIR = ROOT.parent / "10_daily"
CREATIVES_DIR = ROOT.parent / "11_dashboard" / "creatives"

# 스타일 정의 — compact (navy 8-slide 실무자용) · deck (보라 16-slide 발표용)
STYLE_TEMPLATES = {
    "compact": "index.html.j2",
    "deck": "deck.html.j2",
}


def _daily_cache(brand: str, ds: str) -> dict | None:
    """daily-slack 가 dump 한 JSON 의 account 합계 1행 반환 — 있으면 Meta 호출 절약."""
    p = DAILY_DIR / brand / f"{ds}-slack.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        acc = (data.get("account") or [None])[0]
        return acc
    except Exception:
        return None


def fmt_won(v) -> str:
    v = float(v or 0)
    if abs(v) >= 100_000_000:
        return f"{v/100_000_000:.2f}억"
    if abs(v) >= 10_000:
        return f"{v/10_000:.1f}만"
    return f"{int(v):,}원"


def fmt_num(v) -> str:
    try:
        return f"{int(float(v)):,}"
    except (TypeError, ValueError):
        return "-"


def roas_badge(r: float) -> str:
    if r >= 2.0:
        return "green"
    if r < 1.0:
        return "red"
    return "yellow"


def collect_meta(env: dict, since: date, until: date, brand: str) -> dict:
    client = MetaClient(env)
    s, u = since.isoformat(), until.isoformat()
    days = (until - since).days + 1
    rows_total = client.insights(s, u, level="account")
    campaigns = client.insights(s, u, level="campaign")
    ads = client.insights(s, u, level="ad")

    total = rows_total[0] if rows_total else aggregate(ads)
    tier = freshness_tier(until)

    daily_rows = []
    cursor = since
    cache_hits = 0
    while cursor <= until:
        ds = cursor.isoformat()
        cached = _daily_cache(brand, ds)
        if cached:
            cache_hits += 1
            daily_rows.append({
                "date": ds,
                "spend": cached.get("spend", 0),
                "purchase_value": cached.get("purchase_value", 0),
                "roas": cached.get("roas", 0),
            })
        else:
            try:
                r = client.insights(ds, ds, level="account")
                row = r[0] if r else None
            except Exception:
                row = None
            daily_rows.append({
                "date": ds,
                "spend": row.spend if row else 0,
                "purchase_value": row.purchase_value if row else 0,
                "roas": row.roas if row else 0,
            })
        cursor += timedelta(days=1)
    if cache_hits:
        print(f"  ✓ daily-slack 캐시 hit: {cache_hits}/{days}일 (Meta 호출 절약)")

    return {
        "total": total,
        "campaigns": sorted(campaigns, key=lambda r: -r.spend),
        "ads": ads,
        "daily": daily_rows,
        "tier": tier,
        "days": days,
    }


def select_ads(rows: list[AdRow], thresholds, n_top: int = 5, n_bot: int = 3):
    cand = [r for r in rows if r.spend >= thresholds.spend_min]
    top = sorted([r for r in cand if r.purchases >= 1], key=lambda r: (-r.roas, -r.purchase_value))[:n_top]
    bot = sorted([r for r in cand if r.purchases == 0 or r.roas < thresholds.roas_red],
                 key=lambda r: (r.roas, -r.spend))[:n_bot]
    return top, bot


def ga4_block(env: dict, since: date, until: date) -> dict | None:
    """GA4 키 있으면 합계 1행, 없으면 None."""
    if not env.get("GA4_PROPERTY_ID") or not (env.get("GA4_SERVICE_ACCOUNT_PATH") or env.get("GA4_SERVICE_ACCOUNT_JSON")):
        return None
    try:
        from lib.ga4_client import daily_summary
        # 기간 평균은 미지원 — 일별 합산 (대표일 = until)
        summary = daily_summary(env, until)
        return {
            "sessions": summary["sessions"],
            "users": summary["users"],
            "new_users": summary["new_users"],
            "conv_rate": summary["conversion_rate"],
            "conversions": summary["conversions"],
        }
    except Exception as e:
        print(f"  ⚠️ GA4 흡수 실패: {e}")
        return None


def latest_cro_markdown(brand: str) -> str | None:
    folder = CRO_DIR / brand
    if not folder.exists():
        return None
    files = sorted(folder.glob("*-cro-v*.md"))
    if not files:
        return None
    text = files[-1].read_text(encoding="utf-8")
    return text.replace("\n", "<br>")


def build_actions(total: AdRow, top_ads: list[AdRow], bottom_ads: list[AdRow], thresholds) -> list[dict]:
    actions: list[dict] = []
    if total.roas < thresholds.roas_red:
        actions.append({
            "priority": True,
            "title": f"전체 ROAS {total.roas:.2f} — 가드레일 미달",
            "detail": "예산 분배 점검 + 저성과 소재 OFF + 고성과 신규 소재 투입.",
        })
    if bottom_ads:
        worst = bottom_ads[0]
        actions.append({
            "priority": True,
            "title": f"저성과 소재 OFF: {worst.ad_name}",
            "detail": f"ROAS {worst.roas:.2f}, 누적 지출 {fmt_won(worst.spend)}. 즉시 중지 권장.",
        })
    if top_ads:
        best = top_ads[0]
        actions.append({
            "priority": False,
            "title": f"고성과 확장: {best.ad_name}",
            "detail": f"ROAS {best.roas:.2f}, 예산 비중 +20% 검토. 유사 앵글 변주 신규 5개 제작.",
        })
    actions.append({
        "priority": False,
        "title": "다음 주 실행 — A/B 1세트 + 카드뉴스 1세트",
        "detail": "고성과 패턴 베이스로 NanoBanana 신규 + 카드뉴스 신규 1세트 (05·07 스킬).",
    })
    return actions


def _thumb_path(ad_name: str, out_dir: Path) -> str | None:
    """Ad name → assets/creatives/{base}.{ext} 경로. `_FP` 등 suffix 제거 후 jpg|png 탐색."""
    if not ad_name:
        return None
    # `meta036_260420_sh_FP` → `meta036_260420_sh`
    base = ad_name
    for suffix in ("_FP_1대1", "_FP", "_1대1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    assets_dir = out_dir / "assets" / "creatives"
    src_root = CREATIVES_DIR
    assets_dir.mkdir(parents=True, exist_ok=True)
    for ext in (".jpg", ".png", ".jpeg", ".webp"):
        # 1) 이미 추출된 썸네일이 있으면 그대로
        existing = assets_dir / f"{base}{ext}"
        if existing.exists():
            return f"assets/creatives/{base}{ext}"
        # 2) 원본 이미지가 있으면 복사
        src = src_root / f"{base}{ext}"
        if src.exists():
            try:
                import shutil
                shutil.copyfile(src, existing)
                return f"assets/creatives/{base}{ext}"
            except Exception:
                pass
    # 3) mp4 가 있으면 ffmpeg 로 추출 시도 (조용히 실패)
    for vsuffix in ("", "_FP", "_FP_1대1"):
        mp4 = src_root / f"{base}{vsuffix}.mp4"
        if mp4.exists():
            try:
                import subprocess
                dst = assets_dir / f"{base}.jpg"
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", "00:00:01", "-i", str(mp4),
                     "-frames:v", "1", "-q:v", "3", "-vf", "scale=480:-1", str(dst)],
                    check=True, capture_output=True, timeout=15,
                )
                if dst.exists():
                    return f"assets/creatives/{base}.jpg"
            except Exception:
                continue
    return None


def _kpi_signal(value: float, *, green_at: float, red_at: float, higher_is_better: bool = True) -> str:
    """🟢 양호 / 🟡 관찰 / 🔴 액션 → kpi-tile 의 .good/.warn/.bad CSS 클래스 반환."""
    if higher_is_better:
        if value >= green_at:
            return "good"
        if value < red_at:
            return "bad"
        return "warn"
    if value <= green_at:
        return "good"
    if value > red_at:
        return "bad"
    return "warn"


def build_deck_context(args, meta: dict, ga4: dict | None, thresholds, tgt, out_dir: Path) -> dict:
    """deck.html.j2 용 컨텍스트 빌드. compact 와 동일한 데이터를 deck 슬롯에 매핑."""
    total: AdRow = meta["total"]
    ads = meta["ads"]
    days = meta["days"]

    # 1) 8대 KPI 타일
    sessions = ga4["sessions"] if ga4 else 0
    new_users = ga4["new_users"] if ga4 else 0
    impressions = int(total.impressions or 0)
    ctr = float(total.ctr or 0)
    spend = float(total.spend or 0)
    revenue = float(total.purchase_value or 0)
    roas = float(total.roas or 0)
    purchases = int(total.purchases or 0)
    cpa = (spend / purchases) if purchases else 0

    def n_short(v: int) -> str:
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1000:
            return f"{v/1000:.0f}K"
        return f"{v:,}"

    kpis = [
        {"label": "SESSIONS", "value": n_short(sessions) if sessions else "-",
         "delta": "GA4 연결 시 표시", "delta_cls": "flat",
         "cls": _kpi_signal(sessions, green_at=1000, red_at=300) if sessions else ""},
        {"label": "NEW USERS", "value": n_short(new_users) if new_users else "-",
         "delta": "GA4 연결 시 표시", "delta_cls": "flat",
         "cls": _kpi_signal(new_users, green_at=700, red_at=200) if new_users else ""},
        {"label": "IMPRESSIONS", "value": n_short(impressions),
         "delta": f"{days}일 누적", "delta_cls": "flat", "cls": ""},
        {"label": "CTR", "value": f"{ctr:.2f}%",
         "delta": f"빨강선 {thresholds.ctr_red_pct:.1f}% 기준",
         "delta_cls": "up" if ctr >= thresholds.ctr_red_pct else "down",
         "cls": _kpi_signal(ctr, green_at=tgt.target_ctr_pct, red_at=thresholds.ctr_red_pct)},
        {"label": "SPEND", "value": fmt_won(spend),
         "delta": f"일평균 {fmt_won(spend/days if days else 0)}", "delta_cls": "flat",
         "cls": "warn" if thresholds.daily_budget and spend > thresholds.daily_budget * days * 1.1 else ""},
        {"label": "REVENUE", "value": fmt_won(revenue),
         "delta": f"구매 {purchases}건", "delta_cls": "up" if revenue >= spend else "down",
         "cls": "good" if revenue >= spend else "bad"},
        {"label": "ROAS", "value": f"{roas:.2f}",
         "delta": f"목표 {tgt.target_roas:.2f} · 달성 {(roas/tgt.target_roas*100 if tgt.target_roas else 0):.0f}%",
         "delta_cls": "flat",
         "cls": _kpi_signal(roas, green_at=thresholds.roas_green, red_at=thresholds.roas_red)},
        {"label": "CPA", "value": f"{int(cpa):,}" if cpa else "-",
         "delta": f"목표 {int(tgt.target_cpa):,} · 빨강선 {int(thresholds.cpa_red):,}",
         "delta_cls": "down" if cpa > thresholds.cpa_red else "up",
         "cls": _kpi_signal(cpa, green_at=tgt.target_cpa, red_at=thresholds.cpa_red, higher_is_better=False)},
    ]

    # 2) Summary block
    if tgt.kpi_period == "monthly" and tgt.monthly_purchase_goal:
        pace_pct = purchases / tgt.monthly_purchase_goal * 100
        purchase_pace_text = f"월 목표 {int(tgt.monthly_purchase_goal)} 대비 {pace_pct:.0f}%"
    else:
        purchase_pace_text = f"기간 누적 {purchases}건"

    summary = {
        "spend_disp": fmt_won(spend), "revenue_disp": fmt_won(revenue),
        "roas": roas, "purchases": purchases,
        "purchase_pace_text": purchase_pace_text,
        "sessions_disp": n_short(sessions) if sessions else "-",
        "spend_delta_text": f"일평균 {fmt_won(spend/days if days else 0)}",
        "revenue_delta_text": f"손익 {('+' if revenue >= spend else '−')}{fmt_won(abs(revenue-spend))}",
    }

    # 3) Headline / Lead — 데이터에서 자동 도출
    pace_pct_val = (purchases / tgt.monthly_purchase_goal * 100) if tgt.monthly_purchase_goal else 0
    if roas >= thresholds.roas_green:
        headline = f"{days}일 동안 <strong>{fmt_won(spend)}</strong> 광고비로 <strong>{fmt_won(revenue)}</strong> 매출, <span class=\"badge\">ROAS {roas:.2f}</span> — 목표 위 안착, 스케일업 검토 시점이에요."
    elif roas >= thresholds.roas_red:
        headline = f"{days}일 동안 <strong>{fmt_won(spend)}</strong> 광고비로 <strong>{fmt_won(revenue)}</strong> 매출, <span class=\"badge\">ROAS {roas:.2f}</span> — 손익분기선 위는 지켰지만 <strong>매출 페이싱 {pace_pct_val:.0f}%</strong>는 보강이 필요해요."
    else:
        headline = f"{days}일 동안 <strong>{fmt_won(spend)}</strong> 광고비로 <strong>{fmt_won(revenue)}</strong> 매출, <span class=\"badge\">ROAS {roas:.2f}</span> — 가드레일 미달, 저성과 OFF 와 예산 재분배가 시급해요."

    lead = f"기간 평균 CTR {ctr:.2f}%, 구매 {purchases}건 · CPA {int(cpa):,}원. 상세 소재별 효율은 슬라이드 04, 패턴 분석은 09·10에서 확인하세요."

    # 4) Campaign mix
    campaign_mix = []
    for c in meta["campaigns"][:4]:
        campaign_mix.append({
            "label": (c.campaign_name or "—")[:24].upper(),
            "value": f"{c.roas:.2f}",
            "sub": f"매출 {fmt_won(c.purchase_value)} · 지출 {fmt_won(c.spend)} · 구매 {int(c.purchases)}건",
            "highlight": c.roas >= thresholds.roas_green,
        })

    # 5) Creative table — top + bottom 합쳐서 ROAS desc
    candidates = [a for a in ads if a.spend >= thresholds.spend_min]
    candidates = sorted(candidates, key=lambda a: -a.roas)
    creative_table = []
    for i, a in enumerate(candidates[:12], 1):
        row_cls = "win" if a.roas >= thresholds.roas_green else ("lose" if a.roas < thresholds.roas_red else "")
        if a.roas >= thresholds.roas_green:
            badge = "green"
        elif a.roas >= 1.0:
            badge = "yellow"
        else:
            badge = "red"
        if i == 1:
            status = "🥇 BEST"
        elif i <= 3 and a.roas >= 1.5:
            status = "🥈 GOOD"
        elif a.roas >= thresholds.roas_red:
            status = "유지"
        elif a.roas >= 0.5:
            status = "v2 교체"
        else:
            status = "OFF"
        creative_table.append({
            "rank": i, "name": a.ad_name, "roas": a.roas,
            "revenue_disp": fmt_won(a.purchase_value), "spend_disp": fmt_won(a.spend),
            "purchases": int(a.purchases), "ctr": a.ctr,
            "row_cls": row_cls, "roas_badge": badge, "status": status,
        })

    # 6) Hero best / worst
    winners = [a for a in candidates if a.roas >= thresholds.roas_red and a.purchases >= 1]
    losers = [a for a in candidates if a.roas < thresholds.roas_red or a.purchases == 0]
    losers = sorted(losers, key=lambda a: (a.roas, -a.spend))

    def _ad_to_card(a: AdRow) -> dict:
        return {
            "name": a.ad_name, "roas": a.roas, "ctr": a.ctr,
            "revenue_disp": fmt_won(a.purchase_value),
            "spend_disp": fmt_won(a.spend), "purchases": int(a.purchases),
            "thumb": _thumb_path(a.ad_name, out_dir),
        }

    best = _ad_to_card(winners[0]) if winners else None
    worst = _ad_to_card(losers[0]) if losers else None

    runners_up = []
    for i, a in enumerate(winners[1:5], 2):
        card = _ad_to_card(a); card["rank"] = i
        card["note"] = f"CTR {a.ctr:.2f}% · 구매 {int(a.purchases)}건 — 유지 또는 변주 후보."
        runners_up.append(card)

    losers_more = []
    losers_more_spend = 0
    for a in losers[1:5]:
        card = _ad_to_card(a)
        card["note"] = f"CTR {a.ctr:.2f}% · 지출 {fmt_won(a.spend)} — 즉시 OFF 또는 v2 교체."
        losers_more.append(card)
        losers_more_spend += a.spend

    # 7) CX (Clarity) — cro_markdown 흡수 미지원 시 placeholder, 향후 cro_report 파서 연동
    cx_tiles = None  # 데이터 없으면 슬라이드 자동 생략

    # 8) Pattern analysis — 자동 도출 어려움. 빈 리스트면 슬라이드 자동 생략.
    winning_patterns: list[dict] = []
    losing_patterns: list[dict] = []

    # 9) Next actions
    next_actions = []
    actions_raw = build_actions(total, winners[:5], losers[:3], thresholds)
    for a in actions_raw[:5]:
        pill = "critical" if a["priority"] else "med"
        pill_label = "CRITICAL" if a["priority"] else "MED"
        next_actions.append({"title": a["title"], "detail": a["detail"], "pill": pill, "pill_label": pill_label})

    week_num = datetime.strptime(args.since, "%Y-%m-%d").date().isocalendar()[1]

    return {
        "brand": args.brand, "brand_display": args.brand.upper(),
        "brand_display_kr": "[브랜드명]" if args.brand == "sample_brand" else args.brand,
        "period_start": args.since, "period_end": args.until, "days": days,
        "year": args.since[:4], "week_num": week_num,
        "tier": meta["tier"], "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M KST"),
        "target_roas": tgt.target_roas, "spend_min_disp": fmt_won(thresholds.spend_min),
        "summary": summary, "summary_headline": headline, "summary_lead": lead,
        "kpis": kpis, "campaign_mix": campaign_mix,
        "creative_table": creative_table,
        "best": best, "worst": worst,
        "runners_up": runners_up, "losers_more": losers_more,
        "losers_more_spend_disp": fmt_won(losers_more_spend),
        "winning_patterns": winning_patterns, "losing_patterns": losing_patterns,
        "cx_tiles": cx_tiles,
        "next_actions": next_actions,
    }


def render_deck(args, ctx: dict) -> str:
    env_j = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    tmpl = env_j.get_template(STYLE_TEMPLATES["deck"])
    return tmpl.render(**ctx)


def render(env: dict, args, meta: dict, ga4: dict | None, cro_md: str | None) -> tuple[str, dict]:
    thresholds = load_kpi(args.brand)
    top_ads, bottom_ads = select_ads(meta["ads"], thresholds, n_top=8, n_bot=5)
    top_campaigns = meta["campaigns"][:5]

    css = (TEMPLATES / "assets" / "style.css").read_text(encoding="utf-8")
    env_j = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    tmpl = env_j.get_template("index.html.j2")

    period_map = {"weekly": "주간", "monthly": "월간", "campaign": "캠페인"}
    period_label = period_map.get(args.period, args.period)

    if ga4 and ga4.get("conversions"):
        diff_pct = (meta["total"].purchases - ga4["conversions"]) / ga4["conversions"] * 100 if ga4["conversions"] else 0
        attribution_diff = f"+{diff_pct:.0f}%" if diff_pct > 0 else f"{diff_pct:.0f}%"
    else:
        attribution_diff = "GA4 데이터 미연결"

    daily_chart_json = json.dumps({
        "labels": [d["date"][5:] for d in meta["daily"]],
        "spend": [round(d["spend"]) for d in meta["daily"]],
        "purchase_value": [round(d["purchase_value"]) for d in meta["daily"]],
        "roas": [round(d["roas"], 2) for d in meta["daily"]],
    }, ensure_ascii=False)

    footer_note = (
        "ROAS·매출은 Meta Ads Manager 어트리뷰션(7d-click + 1d-view) 기준. "
        "GA4 는 utm 유입·트래픽 분석용. "
        f"freshness: {meta['tier']}."
    )

    html = tmpl.render(
        brand=args.brand,
        brand_display=args.brand.upper(),
        period_label=period_label,
        since=args.since,
        until=args.until,
        days=meta["days"],
        tier=meta["tier"],
        total=meta["total"],
        top_campaigns=top_campaigns,
        top_ads=top_ads,
        bottom_ads=bottom_ads,
        ga4_data=ga4,
        cro_markdown=cro_md,
        thresholds=thresholds,
        attribution_diff=attribution_diff,
        daily_chart_json=daily_chart_json,
        next_actions=build_actions(meta["total"], top_ads, bottom_ads, thresholds),
        inline_css=css,
        footer_note=footer_note,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M KST"),
        fmt_won=fmt_won, fmt_num=fmt_num,
        roas_badge=roas_badge,
    )
    return html, {
        "top_campaigns_n": len(top_campaigns),
        "top_ads_n": len(top_ads),
        "bottom_ads_n": len(bottom_ads),
    }


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    from playwright.sync_api import sync_playwright
    url = f"file://{html_path.resolve()}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(800)  # Chart.js 렌더 여유
        page.pdf(
            path=str(pdf_path),
            format="A4",
            landscape=True,
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()


def next_version(folder: Path, base: str) -> int:
    n = 1
    while (folder / f"{base}-v{n}.html").exists():
        n += 1
    return n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--period", choices=["weekly", "monthly", "campaign"], default="weekly")
    p.add_argument("--from", dest="since", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="until", required=True, help="YYYY-MM-DD")
    p.add_argument("--brand", default="sample_brand")
    p.add_argument("--style", choices=["compact", "deck", "both"], default="both",
                   help="compact = navy 8-slide 실무자용 / deck = 보라 16-slide 발표용 / both = 둘 다")
    p.add_argument("--no-pdf", action="store_true", help="PDF 생성 skip (HTML 만)")
    p.add_argument("--campaign-id", help="--period campaign 일 때 필터링 (현재는 표시만)")
    args = p.parse_args()

    since = datetime.strptime(args.since, "%Y-%m-%d").date()
    until = datetime.strptime(args.until, "%Y-%m-%d").date()

    env = load_env()
    require(env, ["META_APP_ID", "META_APP_SECRET", "META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID"])

    print(f"▶ period_report — {args.period} {since}~{until} brand={args.brand} style={args.style}")
    meta = collect_meta(env, since, until, args.brand)
    print(f"  ✓ Meta: campaigns={len(meta['campaigns'])} ads={len(meta['ads'])} tier={meta['tier']}")

    ga4 = ga4_block(env, since, until)
    if ga4:
        print(f"  ✓ GA4: sessions={ga4['sessions']}")
    else:
        print("  ⚠️ GA4 미연결 — placeholder")

    cro_md = latest_cro_markdown(args.brand)
    if cro_md:
        print("  ✓ CRO 마크다운 흡수")
    else:
        print("  ⚠️ CRO 마크다운 없음 — placeholder")

    folder = OUTPUTS / args.brand
    folder.mkdir(parents=True, exist_ok=True)
    base = f"{args.since}_{args.until}"

    styles_to_render = ["compact", "deck"] if args.style == "both" else [args.style]
    outputs_written: list[Path] = []

    for style in styles_to_render:
        v = next_version(folder, f"{base}-{style}")
        html_path = folder / f"{base}-{style}-v{v}.html"

        if style == "compact":
            html, stats = render(env, args, meta, ga4, cro_md)
            html_path.write_text(html, encoding="utf-8")
            print(f"  📄 [compact] HTML: {html_path.relative_to(PROJECT_ROOT)} ({stats})")
        elif style == "deck":
            thresholds = load_kpi(args.brand)
            tgt = load_targets(args.brand)
            ctx = build_deck_context(args, meta, ga4, thresholds, tgt, folder)
            html = render_deck(args, ctx)
            html_path.write_text(html, encoding="utf-8")
            print(f"  📄 [deck]    HTML: {html_path.relative_to(PROJECT_ROOT)} (best={ctx['best']['name'] if ctx['best'] else '-'}, worst={ctx['worst']['name'] if ctx['worst'] else '-'})")

        outputs_written.append(html_path)

        if not args.no_pdf:
            pdf_path = folder / f"{base}-{style}-v{v}.pdf"
            try:
                render_pdf(html_path, pdf_path)
                print(f"  📄 [{style}] PDF: {pdf_path.relative_to(PROJECT_ROOT)}")
            except Exception as e:
                print(f"  ⚠️ [{style}] PDF 실패 (HTML 은 있음): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
