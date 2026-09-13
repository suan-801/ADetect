"""Gemini 클라이언트 공용 헬퍼 — 여러 analyzer가 공유하는 client 인스턴스 1개만 생성합니다.

모델명은 GEMINI_MODEL(.env, 기본값 gemini-flash-latest)로 관리하며, 실제 사용 가능한
모델 목록은 GEMINI_API_KEY 발급 계정 기준 `client.models.list()`로 언제든 재확인할 수 있습니다.
"""
from __future__ import annotations

from google import genai

from config import settings

_client: genai.Client | None = None


class GeminiCallError(RuntimeError):
    """Gemini 호출 실패 — 호출부에서 §11 '부분 실패' 또는 목업 폴백으로 처리해야 합니다."""


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client
