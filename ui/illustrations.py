"""ADetect 고유의 abstract SVG illustration 세트 (4차 리뉴얼, 2026-09).

원칙 — Home Story section(Market/Brand/Creative/Synthesis)에서만 쓰며, Workspace 데이터
화면에는 쓰지 않는다:

- 구조는 muted line(중립 회색, text_dim)으로만 그린다 — SVG 자체에는 gradient/glow/blur를
  넣지 않는다. Home의 "Controlled Luminous Depth"는 이 SVG를 감싸는 컨테이너 쪽 CSS
  (`.adetect-story-visual-banner.is-dramatic`)에서 절제해서 더하고, 일러스트 자체는 항상 선/점
  기반으로 유지한다 — 성능과 유지보수를 위해서다(§29).
- Orange accent(브랜드 컬러)는 각 illustration에서 "핵심 데이터 포인트/자사"를 가리키는
  단 하나의 지점에만 쓴다 — 장식이 아니라 의미가 있는 강조.
- Hero visual은 SVG가 아니라 공식 에셋(`ui/assets/home/background.png`, `ui/hero.py`)이다 —
  이 파일의 일러스트를 Hero 메인 비주얼로 재사용하지 않는다.

새 일러스트가 필요하면 `_story_panel()` 헬퍼로 감싸는 패턴을 그대로 따르세요.
"""
from __future__ import annotations

LINE = "#A0A3AA"
LINE_SOFT = "#3A3F46"
ACCENT = "#F0462C"


def _story_panel(inner: str, viewbox: str = "0 0 400 200") -> str:
    return (
        f'<svg viewBox="{viewbox}" fill="none" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:100%;display:block;" aria-hidden="true">{inner}</svg>'
    )


def market_visual() -> str:
    """시장분석 — banner 전체 폭을 쓰는 signal wave + horizon line. 마지막(최신) 포인트만
    accent로 강조(§29 "signal wave + luminous horizon")."""
    return _story_panel(f"""
    <line x1="0" y1="230" x2="1200" y2="230" stroke="{LINE_SOFT}" stroke-width="1"/>
    <path d="M0 190 L110 175 L220 182 L330 150 L440 158 L550 118 L660 128 L770 92 L880 100 L990 66 L1120 50"
          stroke="{LINE_SOFT}" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.55"/>
    <path d="M0 205 L110 192 L220 198 L330 172 L440 178 L550 142 L660 150 L770 116 L880 122 L990 86 L1120 62"
          stroke="{LINE}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <circle cx="1120" cy="62" r="5.5" fill="{ACCENT}"/>
    <circle cx="1120" cy="62" r="11" stroke="{ACCENT}" stroke-width="1" opacity="0.35"/>
    """, viewbox="0 0 1200 260")


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
    """종합분석 — banner 전체 폭에서 여러 신호(muted)가 하나의 핵심 인사이트(accent)로 수렴.
    4개 Story 중 가장 dramatic한 section(§60 hierarchy) — 수렴점만 accent, 나머지는 muted."""
    cx, cy = 600, 130
    nodes = [(80, 40), (80, 220), (1120, 40), (1120, 220), (600, 20), (600, 240)]
    lines = "".join(
        f'<line x1="{x}" y1="{y}" x2="{cx}" y2="{cy}" stroke="{LINE_SOFT}" stroke-width="1.1"/>'
        for x, y in nodes
    )
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{LINE}"/>' for x, y in nodes)
    return _story_panel(f"""
    {lines}
    {dots}
    <circle cx="{cx}" cy="{cy}" r="18" stroke="{ACCENT}" stroke-width="1" opacity="0.3"/>
    <circle cx="{cx}" cy="{cy}" r="9" fill="{ACCENT}"/>
    """, viewbox="0 0 1200 260")
