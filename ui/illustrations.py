"""ADetect 고유의 abstract SVG illustration 세트.

레퍼런스 이미지의 오브젝트를 복제하지 않고, ADetect 팔레트(ice blue / soft cyan / soft violet)
로만 구성한 오리지널 visual language입니다. 전부 인라인 SVG라 별도 asset 파일 없이 크기가
작고(성능), 텍스트처럼 CSS로 애니메이션(soft float)을 걸 수 있습니다.

새 일러스트가 필요하면 이 파일에 `_grad()` 헬퍼로 그라디언트를 정의하고 함수를 추가하세요.
PNG/WebP 에셋으로 교체하려면 ui/hero.py의 render_hero_object()만 바꾸면 됩니다.
"""
from __future__ import annotations

ICE = "#AEEBFF"
CYAN = "#64D8FF"
VIOLET = "#A59BFF"


def hero_visual() -> str:
    """Home Hero의 visual anchor — orbital intelligence object.
    서로 다른 각도의 궤도 3개 + 노드 + 은은한 glow core. 브랜드/시장/타겟/소재 데이터가
    하나의 코어로 수렴한다는 컨셉을 형상화합니다(실제 브랜드/로고 요소 없음)."""
    return f"""
<svg viewBox="0 0 480 480" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ADetect abstract intelligence visual">
  <defs>
    <radialGradient id="heroCore" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{ICE}" stop-opacity="0.95"/>
      <stop offset="55%" stop-color="{CYAN}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="orbitA" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{ICE}" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="{VIOLET}" stop-opacity="0.15"/>
    </linearGradient>
    <linearGradient id="orbitB" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{VIOLET}" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0.12"/>
    </linearGradient>
    <linearGradient id="orbitC" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{CYAN}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{ICE}" stop-opacity="0.08"/>
    </linearGradient>
  </defs>

  <circle cx="240" cy="240" r="120" fill="url(#heroCore)"/>

  <ellipse cx="240" cy="240" rx="190" ry="90" stroke="url(#orbitA)" stroke-width="1.4"
           transform="rotate(-18 240 240)"/>
  <ellipse cx="240" cy="240" rx="160" ry="150" stroke="url(#orbitB)" stroke-width="1.2"
           transform="rotate(38 240 240)"/>
  <ellipse cx="240" cy="240" rx="205" ry="70" stroke="url(#orbitC)" stroke-width="1"
           transform="rotate(96 240 240)"/>

  <circle cx="240" cy="240" r="34" fill="none" stroke="{ICE}" stroke-width="1.5" opacity="0.9"/>
  <circle cx="240" cy="240" r="10" fill="{ICE}"/>

  <g opacity="0.92">
    <circle cx="420" cy="205" r="5.5" fill="{ICE}"/>
    <circle cx="90" cy="300" r="4.5" fill="{VIOLET}"/>
    <circle cx="340" cy="365" r="4" fill="{CYAN}"/>
    <circle cx="115" cy="140" r="3.5" fill="{CYAN}"/>
    <circle cx="330" cy="95" r="3" fill="{VIOLET}"/>
  </g>
</svg>
"""


def _story_panel(inner: str, viewbox: str = "0 0 400 220") -> str:
    return (
        f'<svg viewBox="{viewbox}" fill="none" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:100%;display:block;" aria-hidden="true">{inner}</svg>'
    )


def market_visual() -> str:
    """시장분석 — 상승하는 신호 라인 + 은은한 area glow."""
    return _story_panel(f"""
    <defs>
      <linearGradient id="mkArea" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{ICE}" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="{ICE}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="M20 170 L80 150 L140 158 L200 108 L260 122 L320 66 L380 44 L380 220 L20 220 Z" fill="url(#mkArea)"/>
    <path d="M20 170 L80 150 L140 158 L200 108 L260 122 L320 66 L380 44" stroke="{ICE}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="380" cy="44" r="5" fill="{ICE}"/>
    <circle cx="200" cy="108" r="3.5" fill="{CYAN}" opacity="0.85"/>
    """)


def audience_visual() -> str:
    """타겟분석 — 세그먼트를 나타내는 동심원 + 노드."""
    return _story_panel(f"""
    <circle cx="200" cy="110" r="70" stroke="{VIOLET}" stroke-opacity="0.45" stroke-width="1.3"/>
    <circle cx="200" cy="110" r="46" stroke="{ICE}" stroke-opacity="0.55" stroke-width="1.3"/>
    <circle cx="200" cy="110" r="22" fill="{VIOLET}" fill-opacity="0.18" stroke="{VIOLET}" stroke-width="1.4"/>
    <circle cx="200" cy="110" r="5" fill="{ICE}"/>
    <circle cx="270" cy="70" r="4" fill="{CYAN}"/>
    <circle cx="128" cy="150" r="3.5" fill="{VIOLET}"/>
    <circle cx="255" cy="150" r="3" fill="{ICE}" opacity="0.8"/>
    """)


def brand_visual() -> str:
    """브랜드분석 — 자사/경쟁사를 같은 눈높이로 비교하는 두 개의 겹친 링."""
    return _story_panel(f"""
    <circle cx="165" cy="110" r="64" stroke="{ICE}" stroke-width="1.6" fill="{ICE}" fill-opacity="0.05"/>
    <circle cx="245" cy="110" r="64" stroke="{VIOLET}" stroke-width="1.6" fill="{VIOLET}" fill-opacity="0.05"/>
    <line x1="120" y1="110" x2="290" y2="110" stroke="{CYAN}" stroke-opacity="0.35" stroke-dasharray="3 5"/>
    <circle cx="165" cy="110" r="4" fill="{ICE}"/>
    <circle cx="245" cy="110" r="4" fill="{VIOLET}"/>
    """)


def creative_visual() -> str:
    """소재분석 — 겹쳐진 소재 프레임(레이어드 카드)."""
    return _story_panel(f"""
    <rect x="150" y="46" width="150" height="104" rx="12" stroke="{VIOLET}" stroke-opacity="0.4" stroke-width="1.3" transform="rotate(-6 225 98)"/>
    <rect x="130" y="58" width="150" height="104" rx="12" stroke="{CYAN}" stroke-opacity="0.5" stroke-width="1.3" transform="rotate(3 205 110)"/>
    <rect x="110" y="70" width="150" height="104" rx="12" fill="rgba(174,235,255,0.045)" stroke="{ICE}" stroke-width="1.6"/>
    <line x1="132" y1="98" x2="230" y2="98" stroke="{ICE}" stroke-opacity="0.55" stroke-width="2" stroke-linecap="round"/>
    <line x1="132" y1="118" x2="205" y2="118" stroke="{ICE}" stroke-opacity="0.3" stroke-width="2" stroke-linecap="round"/>
    """)


def synthesis_visual() -> str:
    """종합분석 — 여러 신호가 하나의 인사이트 노드로 수렴."""
    return _story_panel(f"""
    <defs>
      <radialGradient id="synCore" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="{ICE}" stop-opacity="0.9"/>
        <stop offset="100%" stop-color="{ICE}" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <circle cx="200" cy="110" r="46" fill="url(#synCore)"/>
    <line x1="60" y1="50" x2="200" y2="110" stroke="{CYAN}" stroke-opacity="0.5" stroke-width="1.3"/>
    <line x1="60" y1="170" x2="200" y2="110" stroke="{VIOLET}" stroke-opacity="0.5" stroke-width="1.3"/>
    <line x1="340" y1="50" x2="200" y2="110" stroke="{VIOLET}" stroke-opacity="0.4" stroke-width="1.3"/>
    <line x1="340" y1="170" x2="200" y2="110" stroke="{CYAN}" stroke-opacity="0.4" stroke-width="1.3"/>
    <circle cx="60" cy="50" r="4" fill="{CYAN}"/>
    <circle cx="60" cy="170" r="4" fill="{VIOLET}"/>
    <circle cx="340" cy="50" r="4" fill="{VIOLET}"/>
    <circle cx="340" cy="170" r="4" fill="{CYAN}"/>
    <circle cx="200" cy="110" r="9" fill="{ICE}"/>
    """)
