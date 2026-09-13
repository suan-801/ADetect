"""소재 이미지/영상 원본 ZIP 패키저 — PRD §16-5·§7-11-(4).

브랜드별 폴더 구조로 원본 파일을 담는다. 개별 파일 다운로드 실패는 그 파일만 건너뛰고
manifest.csv에 실패 사유를 남긴다 — 소재 하나가 만료된 링크라고 전체 ZIP 생성이 실패하면 안 된다.
"""
from __future__ import annotations

import base64
import csv
import io
import zipfile

import requests

_TIMEOUT = 10.0


def _slugify(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip() or "brand"


def _ext_for(ad: dict) -> str:
    if ad.get("format") == "video":
        return ".mp4"
    url = (ad.get("image_url") or "").lower()
    if url.startswith("data:image/svg"):
        return ".svg"
    return ".png" if ".png" in url else ".jpg"


def _fetch_bytes(url: str) -> bytes:
    """data: URI(목업)는 그 자리에서 디코드, 그 외(실데이터)는 실제로 내려받는다."""
    if url.startswith("data:"):
        _, _, payload = url.partition(",")
        return base64.b64decode(payload)
    resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.content


def _brand_label(b: dict) -> str:
    return b["brand"] + ("_자사" if b["is_own"] else "")


def build_creative_zip(result: dict) -> bytes:
    own = result["own"]
    competitors = result["competitors"]
    all_brands = [own, *competitors]

    buffer = io.BytesIO()
    manifest_rows = [["브랜드", "ad_id", "포맷", "파일명", "상태"]]

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for b in all_brands:
            folder = _slugify(_brand_label(b))
            for ad in b["ads"]:
                url = ad.get("image_url") or ad.get("thumbnail_url")
                filename = f"{folder}/{ad['ad_id']}{_ext_for(ad)}"
                if not url:
                    manifest_rows.append([b["brand"], ad["ad_id"], ad["format"], filename, "원본 URL 없음"])
                    continue
                try:
                    zf.writestr(filename, _fetch_bytes(url))
                    manifest_rows.append([b["brand"], ad["ad_id"], ad["format"], filename, "성공"])
                except (requests.RequestException, ValueError) as exc:
                    manifest_rows.append([b["brand"], ad["ad_id"], ad["format"], filename, f"실패: {exc}"])

        manifest_buf = io.StringIO()
        csv.writer(manifest_buf).writerows(manifest_rows)
        zf.writestr("manifest.csv", manifest_buf.getvalue())

    return buffer.getvalue()
