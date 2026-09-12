"""AI 판단 vs 사실 데이터 구분 스키마 (PRD §8).

AI/REC로 분류되는 모든 필드는 insight/source/evidence/confidence 구조를 반드시 포함합니다.
지금은 실제 Gemini 호출 대신 규칙 기반 목업 문구를 생성합니다 — 함수 시그니처는
실제 연동 시에도 그대로 유지되도록 설계했습니다.
"""
from __future__ import annotations


def build_insight(insight: str, source: list[str], evidence: list[str], confidence: str = "medium") -> dict:
    """§8-2 AI/REC 필드 공통 스키마."""
    assert confidence in ("high", "medium", "low")
    return {
        "insight": insight,
        "source": source,
        "evidence": evidence,
        "confidence": confidence,
    }


def mock_promotion_interpretation(promotion_fact: str, conversion_objective: str) -> dict:
    """conversion_objective(§7-3-a)에 맞춰 서술 톤을 다르게 하는 목업 해석.

    실제 연동 시 Gemini 프롬프트로 교체되지만, 인터페이스(입력/출력 shape)는 동일하게 유지합니다.
    """
    return build_insight(
        insight=f"'{promotion_fact}' 문구는 {conversion_objective} 전환을 유도하기 위한 목적으로 판단됨 (샘플 해석)",
        source=["Mock Brand Website"],
        evidence=[promotion_fact],
        confidence="medium",
    )
