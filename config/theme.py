"""디자인 시스템 — "Cinematic Editorial Intelligence" (4차 리뉴얼, 2026-09).

4차 리뉴얼 원칙 — Home과 Workspace의 역할을 분리한다:
- **Home**: Cinematic Brand Experience. Flat Black foundation 위에 "Controlled Luminous
  Depth"(절제된 red/vermilion atmosphere)를 허용한다. 3차 리뉴얼의 "No gradient/No glow" 전면
  금지는 과도했다는 판단 아래, large-scale atmospheric visual(Hero)에 한해서만 gradient/glow를
  허용하도록 완화했다 — 버튼/입력/테이블/카드 등 UI 컴포넌트에는 여전히 금지다(§8 Active
  Design Direction 참고). Home은 2026-09-20부로 Hero 단일 화면으로 축소됐다 — 과거
  Manifesto/Story/Sample Output/Final CTA scene은 더 이상 존재하지 않는다.
- **Workspace**(Analyze/History/Settings): Functional Intelligence Product. 3차 리뉴얼의
  flat/no-decoration 원칙을 그대로 유지한다 — 데이터 가독성이 최우선이다.
- Orange-red accent는 과거(`#B23A1F`) rust/brown 톤을 완전히 교정했다 — R 채널이 확실히
  우세하고 G/B가 낮아 "탁한 갈색"으로 보이지 않는 clean vermilion 계열로 재정의했다
  (`accent_surface` 대비 WCAG AA 4.5:1 이상 확인, §4 Color System 재검증 결과).
- Border radius는 작게(4/6/9px) 유지한다 — 큰 radius의 rounded card를 남발하면 SaaS 대시보드
  처럼 보인다는 지적을 반영했다. 카드로 감싸는 대신 여백/1px 구분선/grid/타이포로 구조를 만든다.
- Grid → Typography → Spacing → Information hierarchy → Data → Color → Decoration 순으로
  우선순위를 둔다. Decoration(glow/gradient/큰 radius)은 이 우선순위의 가장 마지막이다.

색/폰트 크기/라운드/보더의 기본값은 `.streamlit/config.toml`의 [theme] 토큰이 1차로 담당합니다.
이 파일은 그 토큰만으로 표현할 수 없는 것—타이포 스케일, 섹션/컴포넌트 레이아웃, 반응형—을
design token 형태로 정의하고 CSS로 주입합니다.
"""
import streamlit as st

# ── Design tokens ──────────────────────────────────────────────────────────

COLORS = {
    "bg": "#050506",
    "bg_elevated": "#0B0B0D",
    "surface": "#0D1014",
    "border": "#202328",
    "border_soft": "#15181C",
    "text": "#F7F7F5",
    # Secondary(본문) / Faint(eyebrow·meta) 2단계 — 과거 값은 faint가 대비 3.5:1로 AA 미달이었다.
    "text_dim": "#A0A3AA",
    "text_faint": "#797C84",
    # Primary brand accent — clean vermilion/red-orange. 좁은 면적에만: active nav, key action,
    # section index, important highlight, key data point, selected state.
    "accent": "#F0462C",
    "accent_hover": "#FF6542",
    # Home Hero 같은 large-scale atmospheric visual 전용(§8) — 버튼/카드 등 넓은 UI 면적에는
    # 쓰지 않는다. Hot core / soft diffuse 2단계로 radial light를 구성한다.
    "accent_hot": "#FF3B1F",
    "accent_soft": "#FF6542",
    # Filled CTA surface — accent를 넓은 면적(버튼 배경)에 그대로 쓰면 대비가 애매해진다. 넓은
    # 면적 전용으로 한 단계 더 어둡게 분리하고, 위에는 항상 밝은 텍스트(text_on_accent)를 쓴다.
    # 과거 #B23A1F는 G/B 채널이 높아 rust/brown으로 보인다는 피드백에 따라 R이 확실히 우세한
    # 값으로 교체(WCAG AA 4.5:1 이상 확인, 4차 리뉴얼 §4 Color System).
    "accent_surface": "#CD351D",
    "accent_surface_hover": "#C8331A",
    "text_on_accent": "#FFF8F4",
    # Data semantic colors — 브랜드 컬러가 아니라 상태/차트 전용.
    "data_blue": "#5AA9E6",
    "success": "#5FBF77",
    "warning": "#D9A441",
    "error": "#E5484D",
    # §8 FACT/AI/REC 3단 스키마
    "fact": "#8D949E",
    "ai": "#5AA9E6",
    "rec": "#F0462C",
}

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48, "4xl": 64, "5xl": 96}

RADIUS = {"sm": "4px", "md": "6px", "lg": "9px"}

_CSS = f"""
<style>
:root {{
    --bg: {COLORS['bg']};
    --bg-elevated: {COLORS['bg_elevated']};
    --surface: {COLORS['surface']};
    --border: {COLORS['border']};
    --border-soft: {COLORS['border_soft']};
    --text: {COLORS['text']};
    --text-dim: {COLORS['text_dim']};
    --text-faint: {COLORS['text_faint']};
    --accent: {COLORS['accent']};
    --accent-hot: {COLORS['accent_hot']};
    --accent-soft: {COLORS['accent_soft']};
    --accent-surface: {COLORS['accent_surface']};
    --accent-surface-hover: {COLORS['accent_surface_hover']};
    --text-on-accent: {COLORS['text_on_accent']};
    --data-blue: {COLORS['data_blue']};
    --success: {COLORS['success']};
    --warning: {COLORS['warning']};
    --error: {COLORS['error']};
    /* Top Navigation이 콘텐츠를 가리던 문제 수정 — nav 높이 + 여백을 토큰으로 분리해
       본문 시작 위치를 한 곳에서만 계산한다 (페이지별 임시 st.write("") 패치 금지). */
    --nav-height: 60px;
    --content-top-gap: 28px;
}}

html, body, [class*="css"] {{ letter-spacing: 0.003em; }}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }}
}}

/* ── Motion — 절제: fade / 2~6px translate / hover border 전환만 허용 ─────────── */
@keyframes adetect-fade-up {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes adetect-pulse-dot {{
    0%, 100% {{ opacity: 0.4; }}
    50%      {{ opacity: 1; }}
}}
.adetect-fade-up {{ animation: adetect-fade-up 0.4s ease both; }}

/* ── 배경: flat black. Gradient/glow는 Home Hero의 large-scale atmospheric
   visual에 한해서만 허용한다 — UI 컴포넌트(버튼/카드/입력/테이블)에는 여전히
   전면 금지(§8 Active Design Direction, 4차 리뉴얼). ─────────────────────── */
.stApp {{ background: {COLORS['bg']}; overflow-x: hidden; }}
/* Home의 full-bleed breakout(.adetect-bleed, 100vw 트릭)이 스크롤바 폭만큼 미세한 가로
   스크롤을 만들 수 있어 방어적으로 막는다 — 모바일에서 "본문을 방해하지 않는다" 원칙(§31)과
   동일한 목적. */
html {{ overflow-x: hidden; }}

/* ── 기본 크롬 정리 ─────────────────────────────────────────────────────── */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], #MainMenu, footer {{ display: none; }}
[data-testid="stDecoration"] {{ display: none; }}

/* ── Top Navigation ── height 60px, flat, bottom border만으로 구분 ─────────── */
[data-testid="stAppHeader"], [data-testid="stHeader"] {{
    background: {COLORS['bg']} !important;
    border-bottom: 1px solid {COLORS['border_soft']};
    height: 60px;
}}
a[data-testid="stTopNavLink"] {{
    color: {COLORS['text_dim']} !important;
    font-size: 0.86rem;
    font-weight: 450;
    border-radius: 0;
    background: transparent !important;
    box-shadow: none !important;
    position: relative;
    transition: color 0.15s ease;
}}
a[data-testid="stTopNavLink"]:hover {{ color: {COLORS['text']} !important; background: transparent !important; }}
a[data-testid="stTopNavLink"][aria-current="page"] {{ color: {COLORS['text']} !important; font-weight: 560; background: transparent !important; }}
a[data-testid="stTopNavLink"][aria-current="page"]::after {{
    content: "";
    position: absolute;
    left: 0.9rem; right: 0.9rem; bottom: -0.62rem;
    height: 2px;
    background: {COLORS['accent']};
}}
[data-testid="collapsedControl"] {{ display: none; }}

/* ── 본문 폭 + 여백 ────────────────────────────────────────────────────── */
[data-testid="stMainBlockContainer"] {{
    max-width: 1200px;
    margin: 0 auto;
    padding-top: calc(var(--nav-height) + var(--content-top-gap));
    padding-bottom: 4.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
}}

/* ── 버튼: flat, radius 작게, glow 없음 ────────────────────────────────── */
.stButton button[kind="secondary"] {{
    background: transparent;
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['sm']};
    color: {COLORS['text']};
    font-weight: 420;
    box-shadow: none;
    transition: border-color 0.15s ease, background-color 0.15s ease;
}}
.stButton button[kind="secondary"]:hover {{ border-color: {COLORS['text_faint']}; background: rgba(255,255,255,0.02); }}
/* Filled orange CTA — accent_surface(어두운 orange-red) + 밝은 텍스트. accent(#FF4D2E) 자체는
   넓은 면적에 쓰지 않는다 — line/dot/active indicator 전용으로 남겨둔다 (§5 대비 개선). */
.stButton button[kind="primary"] {{
    background: {COLORS['accent_surface']};
    border: 1px solid {COLORS['accent_surface']};
    border-radius: {RADIUS['sm']};
    color: {COLORS['text_on_accent']};
    font-weight: 560;
    box-shadow: none;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}}
.stButton button[kind="primary"]:hover {{
    background: {COLORS['accent_surface_hover']};
    border-color: {COLORS['accent_surface_hover']};
    color: {COLORS['text_on_accent']};
}}
.stButton button[kind="primary"]:focus-visible {{
    outline: 2px solid {COLORS['accent']};
    outline-offset: 2px;
}}
.stButton button[kind="primary"]:disabled {{
    background: {COLORS['border']};
    border-color: {COLORS['border']};
    color: {COLORS['text_faint']};
}}
.stButton button[kind="secondary"]:focus-visible {{
    outline: 2px solid {COLORS['accent']};
    outline-offset: 2px;
}}

/* ── Typography scale ─────────────────────────────────────────────────── */
.adetect-eyebrow {{
    display: block;
    color: {COLORS['text_faint']};
    font-size: 0.74rem;
    font-weight: 550;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    margin-bottom: 0.9rem;
}}
.adetect-eyebrow.is-accent {{ color: {COLORS['accent']}; }}

/* Hero headline: desktop 52~64 / tablet 40~48 / mobile 32~38 */
.adetect-hero-title {{
    /* 표지처럼 보이도록 큰 폭으로 확대 — 이전 clamp(2rem,...,4rem) 대비 데스크톱 기준 약 1.7배.
       !important 필요: Streamlit이 markdown <p>에 자체 `.st-emotion-cache-XXXX p{{font-size:inherit}}`
       규칙을 붙이는데, 이 규칙의 specificity(0,1,1)가 클래스 단독 선택자(0,1,0)보다 높아서
       !important 없이는 font-size가 항상 16px로 눌려버린다(실측 확인된 버그, 다른 커스텀
       타이포 클래스에도 잠재적으로 동일 문제가 있을 수 있음 — 이번엔 hero-title만 수정). */
    font-size: clamp(2.4rem, 1.3rem + 3.2vw, 4.6rem) !important;
    font-weight: 640;
    letter-spacing: -0.03em;
    line-height: 1.03;
    margin: 0;
    color: {COLORS['text']};
}}
.adetect-hero-sub {{
    color: {COLORS['text_dim']};
    font-size: 1rem;
    font-weight: 400;
    line-height: 1.7;
    margin-top: 1.3rem;
    max-width: 30rem;
}}
/* Page headline: 40~56 */
.adetect-page-title {{
    font-size: clamp(1.8rem, 1.2rem + 1.6vw, 2.6rem);
    font-weight: 600;
    letter-spacing: -0.02em;
    color: {COLORS['text']};
    margin: 0;
}}
/* Section headline: 28~36 */
.adetect-display-title {{
    font-size: clamp(1.6rem, 1.1rem + 1.4vw, 2.1rem);
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: {COLORS['text']};
    margin: 0;
}}
.adetect-body-lg {{
    color: {COLORS['text_dim']};
    font-size: 0.98rem;
    font-weight: 400;
    line-height: 1.7;
    max-width: 32rem;
}}
@media (max-width: 900px) {{
    .adetect-hero-sub, .adetect-body-lg {{ max-width: 100%; }}
}}

/* ══════════════════════════════════════════════════════════════════════════
   HOME — Cinematic Brand Experience (4차 리뉴얼). Workspace(Analyze/History/
   Settings)는 이 블록의 영향을 받지 않는다 — 모두 .adetect-home-page-marker가
   심어진 페이지(pages/1_home.py)에서만 매칭되는 :has() 셀렉터로 격리했다.
   ══════════════════════════════════════════════════════════════════════════ */

/* Home 전용 wide container — Workspace의 1200px 규칙은 그대로 두고 Home만 완화.
   본문 텍스트는 각 컴포넌트의 max-width(28~34rem)가 계속 담당하므로, 컨테이너를
   넓혀도 문단이 과도하게 길어지지 않는다. */
[data-testid="stMainBlockContainer"]:has(.adetect-home-page-marker) {{
    max-width: 1600px;
    padding-left: clamp(1.2rem, 4vw, 4rem);
    padding-right: clamp(1.2rem, 4vw, 4rem);
}}

/* Full-bleed breakout — Hero처럼 viewport 전체를 캔버스로 쓰는 scene에 적용한다.
   안쪽 콘텐츠는 별도 max-width로 다시 제한한다.
   scene_marker()로 심은 마커는 실제 크기가 없는 빈 div이므로, `.adetect-bleed` 자체가 아니라
   그 마커를 담고 있는 실제 stVerticalBlock에 breakout을 적용해야 한다(:has() 트릭). */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-bleed) {{
    width: 100vw;
    position: relative;
    left: 50%;
    right: 50%;
    margin-left: -50vw;
    margin-right: -50vw;
}}

/* ── HERO SCENE ────────────────────────────────────────────────────────────
   background.png(공식 Hero visual asset)를 절대 위치 레이어로 깔고, 텍스트는
   safe area(왼쪽)에서만 움직인다. Visual priority: Headline > background.png >
   Brand Input > Pipeline(§65). */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-hero-scene) {{
    position: relative;
    overflow: hidden;
    min-height: calc(92vh - var(--nav-height));
    display: flex;
    align-items: center;
    padding: 2.4rem clamp(1.2rem, 5vw, 5.5rem) 3rem;
}}
/* 텍스트 가독성 지원용 black fade — 새 glow/orb를 추가하는 게 아니라 이미지
   왼쪽을 페이지 배경(순검정)과 자연스럽게 이어붙이는 용도(§48). background.png 자체가
   왼쪽에 이미 negative space를 두고 있어, 과거 값(0.94/0.55/0.08)은 이미지의 red/orange
   luminosity를 필요 이상으로 죽이고 있었다 — 텍스트가 겹치는 0~48% 구간은 가독성을 위해
   유지하되, 중간~우측 구간은 얇게 줄여 이미지가 더 선명하게 비치도록 완화했다. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-hero-scene)::after {{
    content: "";
    position: absolute; inset: 0; z-index: 1; pointer-events: none;
    background: linear-gradient(90deg,
        {COLORS['bg']} 0%, rgba(5,5,6,0.82) 26%,
        rgba(5,5,6,0.38) 48%, rgba(5,5,6,0.04) 64%, transparent 76%);
}}
@media (max-width: 900px) {{
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-hero-scene) {{
        min-height: auto;
        padding: 1.6rem 1.2rem 2.2rem;
    }}
}}

/* background.png 자체 — decorative, pointer-events 없음(§57). 카드/보더/그림자로
   감싸지 않는다(§44) — 페이지 배경과 이미지의 검정이 그대로 맞닿아야 한다. */
/* Streamlit은 모든 stElementContainer에 기본 position:relative를 준다 — 우리 absolute
   레이어(inset:0)가 그 바로 위 wrapper(보통 height:0)를 containing block으로 잡아버려서
   납작하게 찌그러지는 문제가 있었다. 이 두 마커를 담은 stElementContainer만 static으로
   되돌려 진짜 positioning context(:has()로 스타일링한 상위 stVerticalBlock scene)까지
   건너뛰게 한다. */
div[data-testid="stElementContainer"]:has(.adetect-hero-visual-layer) {{
    position: static;
}}

.adetect-hero-visual-layer {{
    position: absolute; inset: 0; z-index: 0; pointer-events: none;
    background-repeat: no-repeat;
    background-size: cover;
    background-position: right -6vw center;
}}
@media (max-width: 900px) {{
    .adetect-hero-visual-layer {{ background-position: 68% center; opacity: 0.55; }}
}}
@media (max-width: 480px) {{
    .adetect-hero-visual-layer {{ opacity: 0.4; }}
}}

/* Hero content — safe area. z-index 2로 이미지/fade 위에 놓는다. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-hero-content) {{
    position: relative; z-index: 2; max-width: 42rem;
}}

.adetect-hero-wordmark {{
    display: block; color: {COLORS['text_faint']}; font-size: 0.76rem; font-weight: 600;
    letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 1.6rem;
}}
.adetect-hero-wordmark b {{ color: {COLORS['text_dim']}; font-weight: 600; }}

/* Hero headline — 표지 타이포그래피. desktop ~72~90px 수준까지 검토(§6). */
.adetect-hero-title {{
    font-size: clamp(2.6rem, 1.5rem + 3.8vw, 5.7rem) !important;
    font-weight: 660;
    letter-spacing: -0.03em;
    line-height: 1.18;
    margin: 0;
    color: {COLORS['text']};
}}
.adetect-hero-sub {{
    color: {COLORS['text_dim']};
    font-size: 1.04rem;
    font-weight: 400;
    line-height: 1.68;
    margin-top: 2.1rem;
    max-width: 34rem;
    white-space: nowrap;
}}
@media (max-width: 900px) {{
    .adetect-hero-sub {{ white-space: normal; }}
}}

/* ── Command Bar — Hero의 웅장함을 방해하지 않는 가벼운 형태(§10). 사각 카드
   대신 hairline underline 중심, 배경은 거의 투명. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-command-marker) {{
    background: rgba(11, 11, 13, 0.55);
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    border-radius: 0;
    padding: 0 0 1rem 0;
}}
.adetect-command-label {{
    display: block; color: {COLORS['accent']}; font-size: 0.7rem; font-weight: 600;
    letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 0.7rem;
}}

/* ── Intelligence Pipeline Rail — Hero의 secondary information layer(§49~51).
   Command Bar 아래에 붙는 "또 하나의 폼 설명"처럼 보이지 않도록, command bar와는 뚜렷이
   다른 technical index 톤(작은 크기·넓은 자간·tabular-nums)으로 분리하고 여백을 크게 둔다.
   더 이상 Main Illustration이 아니라 제품 구조를 알려주는 compact index다. 4단계 모두 동일한
   비중으로 보여준다 — 특정 단계(예: MARKET)만 accent로 강조하면 "이미 진행 중인 단계"처럼
   오독되므로, num/label 모두 동일한 text 컬러를 쓴다. border box 없음, moving line 없음,
   glow/pulse 애니메이션 없음(절제). */
.adetect-pipeline-rail-eyebrow {{
    display: block; color: {COLORS['text_faint']}; font-size: 0.64rem; font-weight: 550;
    letter-spacing: 0.19em; text-transform: uppercase; margin: 0;
}}
.adetect-pipeline-rail {{
    display: flex; flex-wrap: wrap; gap: 0 clamp(1.6rem, 3vw, 2.8rem);
    margin-top: 4rem; padding-top: 1rem; border-top: 1px solid {COLORS['border_soft']};
    max-width: 40rem;
}}
.adetect-pipeline-rail-item {{ display: flex; align-items: baseline; gap: 0.5rem; padding: 0.3rem 0; }}
.adetect-pipeline-rail-num {{
    color: {COLORS['text_faint']}; font-size: 0.68rem; font-weight: 550; letter-spacing: 0.06em;
    font-variant-numeric: tabular-nums;
}}
.adetect-pipeline-rail-label {{ color: {COLORS['text']}; font-size: 0.76rem; font-weight: 550; letter-spacing: 0.06em; }}
@media (max-width: 640px) {{
    .adetect-pipeline-rail {{ gap: 0.5rem 1.4rem; margin-top: 2.8rem; }}
}}

/* ── Input ─────────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {{
    background: {COLORS['bg_elevated']} !important;
    border: 1px solid {COLORS['border']} !important;
    border-radius: {RADIUS['sm']} !important;
    color: {COLORS['text']} !important;
    padding: 0.6rem 0.85rem !important;
    font-weight: 400 !important;
    transition: border-color 0.15s ease;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{ color: {COLORS['text_faint']} !important; opacity: 1 !important; }}
[data-testid="stTextInput"] input:hover,
[data-testid="stTextArea"] textarea:hover,
[data-testid="stNumberInput"] input:hover {{ border-color: {COLORS['text_faint']} !important; }}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus {{
    border-color: {COLORS['accent']} !important;
    background: {COLORS['bg_elevated']} !important;
    box-shadow: none !important;
}}
[data-testid="stWidgetLabel"] p {{ color: {COLORS['text_dim']} !important; font-size: 0.8rem !important; font-weight: 460 !important; }}
[data-testid="stWidgetLabel"] span[style*="rgba(250, 250, 250, 0.6)"] {{ color: {COLORS['text_faint']} !important; }}

/* ── CTA row (오른쪽 정렬 caption + button) ────────────────────────────── */
.adetect-cta-row-marker {{ position: absolute; }}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-cta-row-marker) {{
    display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 1rem;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-cta-row-marker) [data-testid="stElementContainer"] {{ width: auto; }}

/* ── Brand Context Header (Workspace 상단, pages/2_analyze.py) ─────────────
   좌: 브랜드/카테고리/타겟. 우: Analysis Status vertical index. */
.adetect-context-block {{ padding-right: 1rem; }}
.adetect-context-brand {{ font-size: clamp(1.4rem, 1rem + 1vw, 1.9rem); font-weight: 600; color: {COLORS['text']}; letter-spacing: -0.015em; margin: 0; }}
.adetect-context-meta {{ color: {COLORS['text_dim']}; font-size: 0.9rem; margin-top: 0.55rem; line-height: 1.6; }}
.adetect-context-meta b {{ color: {COLORS['text']}; font-weight: 500; }}

.adetect-status-header {{ display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.3rem; }}
.adetect-status-label {{ color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 550; letter-spacing: 0.1em; text-transform: uppercase; }}
.adetect-status-count {{ color: {COLORS['text_dim']}; font-size: 0.85rem; font-weight: 500; }}
.adetect-status-row {{
    display: flex; align-items: center; gap: 0.7rem;
    min-height: 40px;
    border-top: 1px solid {COLORS['border_soft']};
}}
.adetect-status-row:last-child {{}}
.adetect-status-num {{ color: {COLORS['text_faint']}; font-size: 0.76rem; font-weight: 500; width: 1.3rem; flex: none; }}
.adetect-status-name {{ color: {COLORS['text']}; font-size: 0.9rem; flex: 1; }}
.adetect-status-value {{ display: inline-flex; align-items: center; gap: 0.45em; font-size: 0.8rem; color: {COLORS['text_dim']}; flex: none; }}
.adetect-status-value::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; flex: none; }}
.adetect-status-value.st-idle::before {{ background: {COLORS['text_faint']}; }}
.adetect-status-value.st-running::before {{ background: {COLORS['data_blue']}; animation: adetect-pulse-dot 1.3s ease-in-out infinite; }}
.adetect-status-value.st-done::before {{ background: {COLORS['success']}; }}
.adetect-status-value.st-partial::before {{ background: {COLORS['warning']}; }}
.adetect-status-value.st-fail::before {{ background: {COLORS['error']}; }}
.adetect-status-value.st-cancel::before {{ background: {COLORS['text_faint']}; }}
.adetect-status-value.st-locked::before {{ background: transparent; border: 1px solid {COLORS['text_faint']}; }}
@media (max-width: 768px) {{ .adetect-context-block {{ margin-bottom: 1.6rem; padding-right: 0; }} }}

/* Status dot 하위 호환(History/Settings 등에서 재사용) */
.adetect-status-dot {{ display: inline-flex; align-items: center; gap: 0.42em; font-size: 0.8rem; color: {COLORS['text_dim']}; }}
.adetect-status-dot::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; flex: none; }}
.adetect-status-dot.st-idle::before {{ background: {COLORS['text_faint']}; }}
.adetect-status-dot.st-running::before {{ background: {COLORS['data_blue']}; animation: adetect-pulse-dot 1.3s ease-in-out infinite; }}
.adetect-status-dot.st-done::before {{ background: {COLORS['success']}; }}
.adetect-status-dot.st-partial::before {{ background: {COLORS['warning']}; }}
.adetect-status-dot.st-fail::before {{ background: {COLORS['error']}; }}
.adetect-status-dot.st-cancel::before {{ background: {COLORS['text_faint']}; }}
.adetect-status-dot.st-locked::before {{ background: transparent; border: 1px solid {COLORS['text_faint']}; }}

/* ── Analysis Tabs — thin/compact/understated, active = orange underline ─────
   공식 data-testid(stTabs/stTab)만 사용 — data-baseweb 같은 내부 구현 문자열에는
   의존하지 않는다(빌드마다 바뀔 수 있음, PRD §21 "fragile CSS selector 최소화"). */
[data-testid="stTabs"] {{ gap: 0; }}
[data-testid="stTabs"] [role="tablist"], [data-testid="stTabs"] > div:first-child {{
    gap: 1.6rem !important;
    border-bottom: 1px solid {COLORS['border']};
}}
[data-testid="stTab"] {{
    background: transparent !important;
    color: {COLORS['text_faint']} !important;
    font-size: 0.88rem !important;
    font-weight: 460 !important;
    padding: 0 0 0.7rem 0 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    box-shadow: none !important;
}}
[data-testid="stTab"]:hover {{ color: {COLORS['text_dim']} !important; }}
[data-testid="stTab"][aria-selected="true"] {{
    color: {COLORS['text']} !important;
    border-bottom: 2px solid {COLORS['accent']} !important;
}}
[data-testid="stTab"] p {{ font-size: inherit !important; font-weight: inherit !important; }}

/* ── Section header (탭 상단) — Analysis headline 22~28 ───────────────────── */
.adetect-section-label {{ color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.3rem; }}
.adetect-section-title {{ display: flex; align-items: baseline; gap: 0.8rem; margin-bottom: 1.4rem; flex-wrap: wrap; }}
.adetect-section-title h3 {{ margin: 0 !important; font-weight: 580 !important; font-size: 1.5rem !important; }}
.adetect-section-status {{ color: {COLORS['text_faint']}; font-size: 0.85rem; font-weight: 400; }}

/* ── Metric — full-width grid + vertical divider, 숫자가 먼저 보이게 ───────── */
.adetect-metric-row {{ display: flex; width: 100%; padding: 0.2rem 0 1.6rem; }}
.adetect-metric {{ flex: 1; padding: 0 1.6rem; border-left: 1px solid {COLORS['border']}; }}
.adetect-metric:first-child {{ padding-left: 0; border-left: none; }}
.adetect-metric-label {{ color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.5rem; }}
.adetect-metric-value {{ font-size: 1.9rem; font-weight: 600; color: {COLORS['text']}; letter-spacing: -0.01em; line-height: 1; }}
.adetect-metric-value .unit {{ font-size: 1rem; color: {COLORS['text_dim']}; font-weight: 420; margin-left: 0.15em; }}
.adetect-metric-trend {{ font-size: 0.8rem; margin-top: 0.5rem; font-weight: 460; }}
.adetect-metric-trend.up {{ color: {COLORS['success']}; }}
.adetect-metric-trend.down {{ color: {COLORS['error']}; }}
.adetect-metric-trend.flat {{ color: {COLORS['text_faint']}; }}
@media (max-width: 640px) {{
    .adetect-metric-row {{ flex-wrap: wrap; row-gap: 1.2rem; }}
    .adetect-metric {{ flex: 1 1 45%; }}
}}

/* ── Insight block — "INSIGHT"가 먼저, AI 배지/glow 없음 ─────────────────── */
.adetect-insight {{ border-left: 2px solid {COLORS['border']}; padding: 0.1rem 0 0.1rem 1.1rem; margin: 0.8rem 0 1rem; }}
.adetect-insight-label {{ color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 550; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.4rem; }}
.adetect-insight-label.kind-ai {{ color: {COLORS['data_blue']}; }}
.adetect-insight-label.kind-rec {{ color: {COLORS['accent']}; }}
.adetect-insight-title {{ color: {COLORS['text']}; font-weight: 540; font-size: 0.98rem; margin-bottom: 0.35rem; }}
.adetect-insight-meta {{ color: {COLORS['text_faint']}; font-size: 0.78rem; margin-top: 0.5rem; }}
.adetect-evidence-chips {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.6rem; }}
.adetect-evidence-chip {{
    font-size: 0.76rem; color: {COLORS['text_dim']}; border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['sm']}; padding: 0.2rem 0.55rem;
}}

/* ── Badges (FACT / INSIGHT / RECOMMENDATION) — 다른 컴포넌트에서 재사용 ─────── */
.adetect-badge {{ display: inline-flex; align-items: center; gap: 0.4em; font-size: 0.7rem; font-weight: 550; letter-spacing: 0.08em; text-transform: uppercase; margin-right: 0.6em; }}
.adetect-badge::before {{ content: ""; width: 5px; height: 5px; border-radius: 50%; display: inline-block; }}
.adetect-badge-fact {{ color: {COLORS['fact']}; }}
.adetect-badge-fact::before {{ background: {COLORS['fact']}; }}
.adetect-badge-ai {{ color: {COLORS['ai']}; }}
.adetect-badge-ai::before {{ background: {COLORS['ai']}; }}
.adetect-badge-rec {{ color: {COLORS['rec']}; }}
.adetect-badge-rec::before {{ background: {COLORS['rec']}; }}
.adetect-badge-sample {{ color: {COLORS['text_faint']}; }}
.adetect-badge-sample::before {{ background: {COLORS['text_faint']}; }}

/* ── Empty state (게이트 잠금/미실행) ──────────────────────────────────────── */
.adetect-empty {{ padding: 0.4rem 0 1.4rem; max-width: 32rem; }}
.adetect-empty-desc {{ color: {COLORS['text_dim']}; font-size: 0.92rem; line-height: 1.72; margin: 0 0 0.35rem 0; }}

/* ── Data table / Ad table ───────────────────────────────────────────────── */
.adetect-ad-table-wrap {{ overflow-x: auto; }}
.adetect-ad-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
.adetect-ad-table th {{
    text-align: left; color: {COLORS['text_faint']}; font-weight: 500; font-size: 0.72rem;
    letter-spacing: 0.06em; text-transform: uppercase; padding: 0.55rem 0.7rem;
    border-bottom: 1px solid {COLORS['border']}; white-space: nowrap;
}}
.adetect-ad-table td {{ color: {COLORS['text_dim']}; padding: 0.6rem 0.7rem; border-bottom: 1px solid {COLORS['border']}; vertical-align: top; }}
/* Creative 정보 위계 — 헤드라인이 가장 잘 보이는 카피 정보, Placement는 secondary metadata */
.adetect-ad-table td.col-headline {{
    min-width: 260px; max-width: 320px; color: {COLORS['text']}; font-weight: 520;
    white-space: normal; line-height: 1.5;
}}
.adetect-ad-table td.col-placement {{
    max-width: 140px; color: {COLORS['text_faint']}; font-size: 0.78rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.adetect-ad-thumb-hover {{ position: relative; display: inline-block; color: {COLORS['text']}; border-bottom: 1px dotted {COLORS['text_faint']}; cursor: help; }}
.adetect-ad-thumb-hover .adetect-ad-thumb-popup {{
    display: none; position: absolute; z-index: 60; left: 0; top: 1.5em;
    background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['sm']}; padding: 0.4rem;
}}
.adetect-ad-thumb-hover .adetect-ad-thumb-popup img {{ display: block; width: 148px; height: 148px; object-fit: cover; border-radius: 3px; background: {COLORS['bg_elevated']}; }}
.adetect-ad-thumb-hover:hover .adetect-ad-thumb-popup {{ display: block; }}

/* ── Row list (History) ──────────────────────────────────────────────────── */
.adetect-row {{ display: flex; align-items: center; gap: 1.6rem; flex-wrap: wrap; padding: 1rem 0.1rem; border-top: 1px solid {COLORS['border']}; }}
.adetect-row-main {{ flex: 1 1 14rem; min-width: 0; }}
.adetect-row-brand {{ font-size: 0.96rem; font-weight: 540; color: {COLORS['text']}; margin: 0; }}
.adetect-row-meta {{ color: {COLORS['text_faint']}; font-size: 0.82rem; margin-top: 0.2rem; }}

/* ── Settings status row ─────────────────────────────────────────────────── */
.adetect-kv-row {{ display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0.1rem; border-top: 1px solid {COLORS['border']}; }}
.adetect-kv-row span.label {{ color: {COLORS['text_dim']}; font-size: 0.92rem; }}

/* ── Checkbox 대비 보정 ───────────────────────────────────────────────────── */
[data-testid="stCheckbox"] svg, [data-testid="stCheckbox"] svg * {{ stroke: #06070A !important; }}

/* ── Responsive breakpoints ──────────────────────────────────────────────── */
@media (max-width: 1280px) {{ [data-testid="stMainBlockContainer"] {{ max-width: 96%; }} }}
@media (max-width: 768px) {{
    [data-testid="stMainBlockContainer"] {{
        padding-left: 1.2rem; padding-right: 1.2rem;
        padding-top: calc(var(--nav-height) + 20px);
    }}
    a[data-testid="stTopNavLink"] {{ font-size: 0.8rem; margin-right: 0.7rem !important; }}
}}
@media (max-width: 390px) {{
    .adetect-hero-title {{ font-size: 2.4rem !important; }}
    .adetect-display-title {{ font-size: 1.5rem; }}
}}
</style>
"""


def inject_global_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def command_marker():
    """이 함수를 st.container() 블록의 첫 줄에서 호출하면 그 컨테이너가 flat command bar가 됩니다."""
    st.markdown('<div class="adetect-command-marker"></div>', unsafe_allow_html=True)


# 하위 호환 별칭 — 이전 리비전(glassmorphism)의 이름. 신규 코드는 command_marker()를 사용하세요.
glass_marker = command_marker


def home_page_marker():
    """pages/1_home.py 최상단에서 한 번 호출합니다 — 이 마커가 존재하는 동안만
    `[data-testid="stMainBlockContainer"]`의 wide-container 규칙이 적용되어 Home만 Workspace의
    1200px 규칙에서 벗어납니다(§21 Home/Workspace 역할 분리)."""
    st.markdown('<div class="adetect-home-page-marker"></div>', unsafe_allow_html=True)


def scene_marker(class_name: str):
    """`with st.container():` 블록의 첫 줄에서 호출하면, 그 컨테이너의 실제
    `div[data-testid="stVerticalBlock"]`에 `class_name`을 키로 하는 CSS `:has()` 규칙이 적용됩니다.
    Home cinematic scene(현재는 Hero뿐)의 범용 레이아웃 훅 — `class_name`에 공백으로 여러
    클래스를 넘기면 각각을 독립된 CSS 규칙에서 참조할 수 있습니다. `command_marker()`도 동일한
    매커니즘의 특수 사례입니다.

    주의: Streamlit 1.63 기준 실제 컬럼 컨테이너의 data-testid는 `stColumn`이지 `column`이
    아닙니다 — 과거 `pipeline_wrap_marker()`가 잘못된 셀렉터(`column`)를 써서 조용히 무효화돼
    있었던 버그를 이 리뉴얼에서 발견/제거했습니다. 새 셀렉터를 작성할 때는 브라우저 DOM에서
    실제 `data-testid` 값을 먼저 확인하세요."""
    st.markdown(f'<div class="{class_name}"></div>', unsafe_allow_html=True)


def cta_row_marker():
    """이 함수를 호출한 뒤 이어지는 위젯들(caption/button 등)을 한 줄에 배치하고
    마지막 위젯을 컨테이너 오른쪽 끝에 정렬합니다."""
    st.markdown('<div class="adetect-cta-row-marker"></div>', unsafe_allow_html=True)


def badge(kind: str, label: str | None = None) -> str:
    """FACT/AI/REC/SAMPLE 배지 HTML 조각을 반환합니다. (§8 3단계 분류)"""
    mapping = {
        "FACT": ("adetect-badge-fact", "FACT"),
        "AI": ("adetect-badge-ai", "INSIGHT"),
        "REC": ("adetect-badge-rec", "RECOMMENDATION"),
        "SAMPLE": ("adetect-badge-sample", "SAMPLE DATA"),
    }
    css_class, default_label = mapping.get(kind, ("adetect-badge-fact", kind))
    return f'<span class="adetect-badge {css_class}">{label or default_label}</span>'


def eyebrow(text: str, accent: bool = False) -> str:
    cls = "adetect-eyebrow is-accent" if accent else "adetect-eyebrow"
    return f'<span class="{cls}">{text}</span>'


def section_title(label: str, title: str, status_text: str = ""):
    """탭 상단 헤더 — eyebrow 라벨 + 제목(Analysis headline) + (선택) 상태 텍스트."""
    status_html = f'<span class="adetect-section-status">{status_text}</span>' if status_text else ""
    st.markdown(
        f'<div class="adetect-section-label">{label}</div>'
        f'<div class="adetect-section-title"><h3>{title}</h3>{status_html}</div>',
        unsafe_allow_html=True,
    )
