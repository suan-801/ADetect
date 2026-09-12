"""
올리브영 리뷰 크롤러

- 올리브영 PDP 의 리뷰 cursor API (POST /review/api/v2/reviews/cursor) 를
  Playwright 브라우저 세션 안에서 직접 호출해 모든 리뷰를 수집한다.
- 외부 IP 에서 직접 호출 시 403 으로 차단되므로 반드시 브라우저 컨텍스트가 필요하다.

사용 예:
    python3 oliveyoung_crawler.py --goods A000000226498
    python3 oliveyoung_crawler.py --goods A000000226498 --max 500 --sort USEFUL_SCORE_DESC
    python3 oliveyoung_crawler.py --url "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000226498"

출력:
    outputs/raw/{goodsNo}_{timestamp}.json   (raw API response 누적)
    outputs/raw/{goodsNo}_{timestamp}.csv    (분석용 핵심 필드만)
    outputs/raw/{goodsNo}_{timestamp}_stats.json (별점 분포·만족도 통계)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CURSOR_API = "https://m.oliveyoung.co.kr/review/api/v2/reviews/cursor"
STATS_API_TPL = "https://m.oliveyoung.co.kr/review/api/v2/reviews/{goods}/stats"

# 피부타입/톤/고민 코드 매핑 (응답에 코드값만 들어오므로 사람이 읽도록 변환)
# 정확한 코드표는 올리브영 내부값이라 추정·관측 기반. 누락 시 코드 그대로 보존.
SKIN_TYPE_MAP = {
    "A01": "건성",
    "A02": "중성",
    "A03": "복합성",
    "A04": "지성",
    "A05": "민감성",
}
SKIN_TONE_MAP = {
    "B01": "쿨톤",
    "B02": "웜톤",
    "B03": "뉴트럴",
    "B04": "봄웜",
    "B05": "여름쿨",
    "B06": "가을웜",
    "B07": "겨울쿨",
}
SKIN_TROUBLE_MAP = {
    "C01": "트러블",
    "C02": "민감성",
    "C03": "모공",
    "C04": "각질",
    "C05": "피지",
    "C06": "홍조",
    "C07": "잡티",
    "C08": "주름",
    "C09": "탄력",
    "C10": "미백",
}


def parse_goods_no(value: str) -> str:
    """URL 또는 goodsNo 양쪽을 받아 goodsNo 만 추출."""
    m = re.search(r"goodsNo=([A-Z0-9]+)", value)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Z0-9]+", value):
        return value
    raise ValueError(f"goodsNo 를 추출할 수 없습니다: {value}")


def _fetch_track(
    page,
    goods_no: str,
    sort_type: str,
    review_type: str,
    page_size: int,
    max_reviews: int | None,
    sleep_between: float,
    label: str,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """단일 (sortType, reviewType) 트랙에서 cursor 페이징 끝까지 수집.

    네트워크 일시 오류는 max_retries 회까지만 재시도하고 그 이상이면 트랙 중단.
    """
    collected: list[dict[str, Any]] = []
    cursor_id: int | None = None
    cursor_score: int | None = None
    cursor_count: int | None = None
    page_idx = 0
    retry_count = 0
    while True:
        page_idx += 1
        body = {
            "goodsNumber": goods_no,
            "size": page_size,
            "sortType": sort_type,
            "reviewType": review_type,
            "cursorId": cursor_id,
            "cursorScore": cursor_score,
            "cursorCount": cursor_count,
        }
        try:
            resp = page.evaluate(
                """async ([url, body]) => {
                    const r = await fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body),
                    });
                    return { status: r.status, json: await r.json() };
                }""",
                [CURSOR_API, body],
            )
        except Exception as exc:
            retry_count += 1
            if retry_count > max_retries:
                print(
                    f"  ! [{label}] 페이지 {page_idx} 재시도 한도({max_retries}) 초과, 트랙 종료",
                    flush=True,
                )
                break
            print(
                f"  ! [{label}] 페이지 {page_idx} 오류 ({type(exc).__name__}) "
                f"재시도 {retry_count}/{max_retries}",
                flush=True,
            )
            page.wait_for_timeout(2000)
            continue
        retry_count = 0  # 정상 응답 시 카운터 리셋
        if resp.get("status") != 200:
            print(f"  ! [{label}] HTTP {resp.get('status')} 종료", flush=True)
            break
        data = (resp.get("json") or {}).get("data") or {}
        batch = data.get("goodsReviewList") or []
        collected.extend(batch)
        print(
            f"  · [{label}] page {page_idx:>3}  +{len(batch)}  (누적 {len(collected)})",
            flush=True,
        )
        # 빈 응답 = 종료 (cap 직후 hasNext=true 와 함께 빈 배열이 오는 케이스 방어)
        if not batch or not data.get("hasNext"):
            break
        if max_reviews and len(collected) >= max_reviews:
            collected = collected[:max_reviews]
            break
        cursor_id = data.get("nextCursorId")
        cursor_score = data.get("nextCursorScore")
        cursor_count = data.get("nextCursorCount")
        time.sleep(sleep_between)
    return collected


# 비로그인 cursor API 검증된 트랙 — (sortType, reviewType) 페어
# 각 페어가 별도 100건 cap 을 가지므로 합쳐서 dedupe 하면 신호량 ↑
DEFAULT_TRACKS: tuple[tuple[str, str], ...] = (
    ("USEFUL_SCORE_DESC", "ALL"),    # 도움돼요 상위 — 메인 신호
    ("USEFUL_SCORE_DESC", "PHOTO"),  # 포토리뷰 가중
    ("RATING_ASC", "ALL"),           # 평점 낮은순 — 페인포인트 직격
    ("RATING_DESC", "ALL"),          # 평점 높은순 — 체험단/만족 신호 비교용
)


def crawl(
    goods_no: str,
    tracks: tuple[tuple[str, str], ...] = DEFAULT_TRACKS,
    page_size: int = 10,
    max_reviews: int | None = None,
    sleep_between: float = 0.4,
    headless: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """리뷰 + 통계 수집.

    비로그인 cursor API 는 (sortType, reviewType) 페어별 100건 cap 이 있어
    여러 트랙을 순회하며 reviewId 로 dedupe 한다.
    """
    pdp_url = (
        f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={goods_no}&tab=review"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        page = ctx.new_page()

        print(f"[1/3] PDP 진입: {pdp_url}", flush=True)
        page.goto(pdp_url, wait_until="domcontentloaded", timeout=30_000)
        # 리뷰 컴포넌트가 mount 되어 세션/쿠키가 잡힐 시간 확보
        page.wait_for_timeout(3000)

        # stats 먼저 가져오기
        stats = page.evaluate(
            """async (goods) => {
                const r = await fetch(`https://m.oliveyoung.co.kr/review/api/v2/reviews/${goods}/stats`);
                return await r.json();
            }""",
            goods_no,
        )
        total = stats.get("data", {}).get("reviewCount") if stats else None
        print(f"[2/3] 통계 수집 완료. 총 리뷰 {total:,}개" if total else "[2/3] 통계 수집", flush=True)

        merged: dict[int, dict[str, Any]] = {}
        for sort_type, review_type in tracks:
            label = f"{sort_type}/{review_type}"
            track = _fetch_track(
                page,
                goods_no=goods_no,
                sort_type=sort_type,
                review_type=review_type,
                page_size=page_size,
                max_reviews=max_reviews,
                sleep_between=sleep_between,
                label=label,
            )
            new_count = 0
            for r in track:
                rid = r.get("reviewId")
                if rid is not None and rid not in merged:
                    merged[rid] = r
                    new_count += 1
            print(
                f"  → [{label}] 누적 {len(track)}건, +{new_count} 신규, "
                f"dedupe 후 전체 {len(merged)}건",
                flush=True,
            )

        all_reviews = list(merged.values())
        # 도움돼요 점수 내림차순으로 안정적 정렬
        all_reviews.sort(key=lambda r: -(r.get("usefulPoint") or 0))
        browser.close()

    return all_reviews, stats


def _trouble_label(codes: list[str] | None) -> str:
    if not codes:
        return ""
    return ",".join(SKIN_TROUBLE_MAP.get(c, c) for c in codes)


def flatten_for_csv(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for r in reviews:
        profile = r.get("profileDto") or {}
        goods = r.get("goodsDto") or {}
        rows.append(
            {
                "review_id": r.get("reviewId"),
                "created_at": r.get("createdDateTime"),
                "rating": r.get("reviewScore"),
                "useful_point": r.get("usefulPoint"),
                "recommend_count": r.get("recommendCount"),
                "review_type": r.get("reviewType"),  # NORMAL / GIFT / OFFLINE
                "is_repurchase": r.get("isRepurchase"),
                "is_month_use": r.get("isMonthUseReview"),
                "is_month_over": r.get("isMonthOverReview"),
                "has_photo": r.get("hasPhoto"),
                "photo_count": len(r.get("photoReviewList") or []),
                "option_name": goods.get("optionName"),
                "nickname": profile.get("memberNickname"),
                "is_top_reviewer": profile.get("isTopReviewer"),
                "reviewer_rank": profile.get("reviewerRank"),
                "skin_type": SKIN_TYPE_MAP.get(profile.get("skinType") or "", profile.get("skinType")),
                "skin_tone": SKIN_TONE_MAP.get(profile.get("skinTone") or "", profile.get("skinTone")),
                "skin_trouble": _trouble_label(profile.get("skinTrouble")),
                "content": (r.get("content") or "").replace("\r", " ").replace("\n", " ").strip(),
            }
        )
    return rows


def save(
    goods_no: str,
    reviews: list[dict[str, Any]],
    stats: dict[str, Any] | None,
) -> dict[str, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = OUTPUT_DIR / f"{goods_no}_{ts}"

    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    stats_path = base.parent / f"{goods_no}_{ts}_stats.json"

    json_path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = flatten_for_csv(reviews)
    if rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    if stats is not None:
        stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"json": json_path, "csv": csv_path, "stats": stats_path}


def _parse_tracks(spec: str) -> tuple[tuple[str, str], ...]:
    """`SORT:REVIEWTYPE,SORT:REVIEWTYPE,...` 포맷 파싱."""
    tracks: list[tuple[str, str]] = []
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"트랙 토큰은 'SORT:REVIEWTYPE' 형태여야 합니다: {token}")
        sort_type, review_type = token.split(":", 1)
        tracks.append((sort_type.strip(), review_type.strip()))
    if not tracks:
        raise ValueError("트랙이 하나도 지정되지 않았습니다.")
    return tuple(tracks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="올리브영 리뷰 크롤러")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--goods", help="goodsNo (예: A000000226498)")
    src.add_argument("--url", help="제품 PDP URL")
    default_tracks_str = ",".join(f"{s}:{r}" for s, r in DEFAULT_TRACKS)
    parser.add_argument(
        "--tracks",
        default=default_tracks_str,
        help=(
            "콤마구분 'SORT:REVIEWTYPE' 트랙 리스트. "
            f"기본 = {default_tracks_str} "
            "(검증된 sortType: USEFUL_SCORE_DESC / RATING_ASC / RATING_DESC, "
            "reviewType: ALL / PHOTO)"
        ),
    )
    parser.add_argument("--size", type=int, default=10, help="페이지 사이즈 (기본 10)")
    parser.add_argument("--max", type=int, default=None, help="트랙당 수집 상한 (테스트용)")
    parser.add_argument("--sleep", type=float, default=0.4, help="페이지간 지연(초)")
    parser.add_argument("--headed", action="store_true", help="브라우저 창을 띄워 확인")
    args = parser.parse_args(argv)

    goods_no = parse_goods_no(args.url or args.goods)
    tracks = _parse_tracks(args.tracks)
    print(f"== goodsNo = {goods_no} | tracks = {tracks} ==", flush=True)

    reviews, stats = crawl(
        goods_no=goods_no,
        tracks=tracks,
        page_size=args.size,
        max_reviews=args.max,
        sleep_between=args.sleep,
        headless=not args.headed,
    )

    paths = save(goods_no, reviews, stats)
    print(f"[3/3] 저장 완료 ({len(reviews):,}건)", flush=True)
    for k, v in paths.items():
        try:
            rel = v.relative_to(REPO_ROOT)
        except ValueError:
            rel = v
        print(f"  - {k}: {rel}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
