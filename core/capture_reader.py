"""검색 화면 광고 영역의 Gemini 보완 판독 (유료).

페이지에서 직접 추출한 텍스트·링크가 우선이다. 직접 추출이 부족한 캡처만 이미지로 판독하며,
결과는 'AI 판독'으로 구분해 캡처와 근거 문구에 연결한다. 금지: 화면에 없는 URL 생성,
성과·타깃·전략 추정, 미관측을 미운영으로 확정. 실패해도 원본 캡처·직접 추출 결과는 그대로 둔다.
"""
import hashlib
import json

from config import settings
from core.jobs import cached_result, store_cache, cache_key

PROMPT_VERSION = "capture-read-v1"
AREA_TYPES = ("powerlink", "brand_search")
PROMPT = (
    "네이버 검색 결과의 광고 영역 캡처입니다. 이미지에 실제로 보이는 글자만 옮기세요. "
    "보이지 않거나 흐린 정보는 null로 두고 추측하지 마세요. URL·랜딩 주소·성과·타깃·전략을 만들지 마세요. "
    "JSON만 반환: {\"ads\":[{\"area\":\"powerlink|brand_search\",\"advertiser_visible\":str|null,"
    "\"copy_visible\":str|null,\"display_url_visible\":str|null,\"image_description\":str|null,"
    "\"confidence\":\"high|medium|low\"}]}. 광고가 보이지 않으면 {\"ads\":[]}."
)


def needs_reading(area):
    """직접 추출이 부족한 경우만: 영역은 찾았지만 문구가 비었거나, 캡처는 있는데 영역 식별 실패."""
    if not area:
        return False
    if not area.get("identified"):
        return True
    return any(not ad.get("text") for ad in area.get("ads", []))


def _validate(payload):
    ads = []
    for ad in (payload or {}).get("ads", []) if isinstance(payload, dict) else []:
        if not isinstance(ad, dict) or ad.get("area") not in AREA_TYPES or ad.get("confidence") not in ("high", "medium", "low"):
            continue
        item = {k: (ad.get(k).strip()[:300] if isinstance(ad.get(k), str) and ad.get(k).strip() else None)
                for k in ("advertiser_visible", "copy_visible", "display_url_visible", "image_description")}
        if not any(item[k] for k in ("advertiser_visible", "copy_visible")):
            continue  # 근거 문구가 없는 판독은 버린다.
        ads.append({"area": ad["area"], **item, "confidence": ad["confidence"]})
    return ads


def read_capture(image_bytes, caller=None):
    """반환: {"state": "완료"|"실패"|"사용 안 함", "ads": [...], "method": ..., "image_sha256": ...}.

    caller는 테스트에서 Gemini 호출을 대신한다. 같은 이미지·같은 판독 조건은 24시간 캐시를 쓴다.
    """
    sha = hashlib.sha256(image_bytes).hexdigest()
    base = {"method": f"Gemini 이미지 판독 ({settings.GEMINI_MODEL}, {PROMPT_VERSION})", "image_sha256": sha, "ads": []}
    if caller is None and (settings.GEMINI_MOCK or settings.SAMPLE_MODE):
        return {**base, "state": "사용 안 함", "message": "Gemini 키 없음 또는 SAMPLE 모드"}
    key = cache_key("capture_read", {"sha": sha, "prompt": PROMPT_VERSION, "model": settings.GEMINI_MODEL})
    hit = cached_result(key)
    if hit:
        return hit["data"]
    try:
        if caller is None:
            from google.genai import types
            from core.analyzers.gemini_client import get_client
            response = get_client().models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/png"), PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            text = response.text
        else:
            text = caller(image_bytes, PROMPT)
        result = {**base, "state": "완료", "ads": _validate(json.loads(text))}
    except Exception as exc:
        from core.collection import error_message
        return {**base, "state": "실패", "message": error_message(exc)}
    store_cache(key, {"status": "완료", "data": result})
    return result
