"""ADetect 고유의 abstract SVG illustration 세트 (3차 리뉴얼, 2026-09).

이전 리비전은 ice blue/violet gradient glow를 사용했으나, "전형적인 AI SaaS 데모"처럼 보인다는
피드백에 따라 전면 재작업했다. 원칙:

- 구조는 muted line(중립 회색, text_dim)으로만 그린다 — gradient/glow/blur 금지.
- Orange accent(브랜드 컬러)는 각 illustration에서 "핵심 데이터 포인트/자사"를 가리키는
  단 하나의 지점에만 쓴다 — 장식이 아니라 의미가 있는 강조.
- Hero의 blue orb는 완전히 제거했다 — 대신 ui/components.intelligence_pipeline()이 HTML/CSS
  기반 pipeline diagram을 그린다(텍스트 접근성·반응형을 위해 SVG가 아닌 HTML로 구현).

새 일러스트가 필요하면 `_story_panel()` 헬퍼로 감싸는 패턴을 그대로 따르세요.
"""
from __future__ import annotations

LINE = "#8D949E"
LINE_SOFT = "#3A3F46"
ACCENT = "#FF4D2E"


def _story_panel(inner: str, viewbox: str = "0 0 400 200") -> str:
    return (
        f'<svg viewBox="{viewbox}" fill="none" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:100%;display:block;" aria-hidden="true">{inner}</svg>'
    )


def market_visual() -> str:
    """시장분석 — muted line chart. 마지막(최신) 포인트만 accent로 강조."""
    return _story_panel(f"""
    <path d="M20 150 L80 132 L140 140 L200 96 L260 108 L320 58 L370 40"
          stroke="{LINE}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <circle cx="370" cy="40" r="4.5" fill="{ACCENT}"/>
    <line x1="20" y1="180" x2="380" y2="180" stroke="{LINE_SOFT}" stroke-width="1"/>
    """)


def audience_visual() -> str:
    """타겟분석 — 세그먼트 동심원. 확정된 핵심 세그먼트(중심)만 accent."""
    return _story_panel(f"""
    <circle cx="180" cy="100" r="66" stroke="{LINE_SOFT}" stroke-width="1.2"/>
    <circle cx="180" cy="100" r="42" stroke="{LINE}" stroke-width="1.2"/>
    <circle cx="180" cy="100" r="7" fill="{ACCENT}"/>
    <circle cx="250" cy="62" r="3" fill="{LINE}"/>
    <circle cx="118" cy="140" r="3" fill="{LINE}"/>
    <circle cx="235" cy="145" r="2.5" fill="{LINE}"/>
    """)


def brand_visual() -> str:
    """브랜드분석 — 자사(accent) vs 경쟁사(muted line)를 같은 크기로 나란히."""
    return _story_panel(f"""
    <circle cx="150" cy="100" r="58" stroke="{ACCENT}" stroke-width="1.6"/>
    <circle cx="150" cy="100" r="3.5" fill="{ACCENT}"/>
    <circle cx="250" cy="100" r="58" stroke="{LINE_SOFT}" stroke-width="1.4"/>
    <line x1="212" y1="100" x2="188" y2="100" stroke="{LINE_SOFT}" stroke-width="1" stroke-dasharray="2 4"/>
    """)


def creative_visual() -> str:
    """소재분석 — 겹쳐진 소재 프레임(레이어드), 활성 소재 1개만 accent 테두리."""
    return _story_panel(f"""
    <rect x="140" y="40" width="140" height="96" rx="4" stroke="{LINE_SOFT}" stroke-width="1.2" transform="rotate(-5 210 88)"/>
    <rect x="120" y="52" width="140" height="96" rx="4" stroke="{LINE}" stroke-width="1.2" transform="rotate(3 190 100)"/>
    <rect x="100" y="64" width="140" height="96" rx="4" stroke="{ACCENT}" stroke-width="1.6"/>
    <line x1="122" y1="92" x2="210" y2="92" stroke="{LINE}" stroke-width="1.6" stroke-linecap="round"/>
    <line x1="122" y1="110" x2="188" y2="110" stroke="{LINE_SOFT}" stroke-width="1.6" stroke-linecap="round"/>
    """)


def synthesis_visual() -> str:
    """종합분석 — 여러 신호(muted)가 하나의 핵심 인사이트(accent)로 수렴."""
    return _story_panel(f"""
    <line x1="60" y1="45" x2="200" y2="100" stroke="{LINE_SOFT}" stroke-width="1.2"/>
    <line x1="60" y1="160" x2="200" y2="100" stroke="{LINE_SOFT}" stroke-width="1.2"/>
    <line x1="340" y1="45" x2="200" y2="100" stroke="{LINE_SOFT}" stroke-width="1.2"/>
    <line x1="340" y1="160" x2="200" y2="100" stroke="{LINE_SOFT}" stroke-width="1.2"/>
    <circle cx="60" cy="45" r="3.5" fill="{LINE}"/>
    <circle cx="60" cy="160" r="3.5" fill="{LINE}"/>
    <circle cx="340" cy="45" r="3.5" fill="{LINE}"/>
    <circle cx="340" cy="160" r="3.5" fill="{LINE}"/>
    <circle cx="200" cy="100" r="8" fill="{ACCENT}"/>
    """)
