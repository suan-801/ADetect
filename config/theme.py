"""디자인 시스템 — "Premium AI Intelligence / Cinematic Editorial / Luminous Dark".

2차 리뉴얼 원칙 (대규모 UI/UX 리뉴얼, 2026-09):
- 카드로 모든 걸 감싸지 않는다 — 여백, 얇은 구분선, 타이포 위계로 구조를 만든다.
- 배경은 반드시 black 계열을 유지하되, 컬러는 ice blue / soft cyan / soft violet 3개
  accent만 극히 제한적으로 사용한다(glow, chart highlight, active indicator 정도).
- Home은 cinematic/spacious, Workspace는 dense/productive — 같은 토큰을 쓰되 스케일이 다르다.
- 이모지 아이콘·과도한 gradient·rainbow·강한 그림자를 쓰지 않는다.

색/폰트 크기/라운드/보더의 기본값은 `.streamlit/config.toml`의 [theme] 토큰이 1차로 담당합니다
(공식 테마 시스템). 이 파일은 그 토큰만으로 표현할 수 없는 것—배경 depth, 타이포 스케일,
섹션/컴포넌트 레이아웃, 모션, 반응형—을 design token 형태로 정의하고 CSS로 주입합니다.
"""
import streamlit as st

# ── Design tokens ──────────────────────────────────────────────────────────
# ui/components.py 등 다른 모듈에서도 이 토큰을 그대로 가져다 쓸 수 있도록 공개합니다.

COLORS = {
    "bg": "#06070A",
    "bg_elevated": "#0B0F14",
    "surface": "#10151C",
    "text": "#F5F7FA",
    "text_dim": "#9AA4B2",
    "text_faint": "#667080",
    "border": "rgba(255, 255, 255, 0.08)",
    "border_strong": "rgba(255, 255, 255, 0.16)",
    "ice": "#AEEBFF",      # Primary accent — AI interpretation, glow, active indicator
    "cyan": "#64D8FF",     # Secondary accent — chart highlight
    "violet": "#A59BFF",   # Tertiary accent — recommendation, comparison series
    "success": "#7FE3B4",
    "warning": "#E8B85C",  # 기존 gold(#C9A227) 계열을 semantic warning 용도로만 축소
    "error": "#FF8A80",
    # §8 FACT/AI/REC 3단 스키마 색상 매핑
    "fact": "#9AA4B2",
    "ai": "#AEEBFF",
    "rec": "#A59BFF",
}

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48, "4xl": 64, "5xl": 96, "6xl": 128}

RADIUS = {"sm": "0.5rem", "md": "0.85rem", "lg": "1.25rem"}

_CSS = f"""
<style>
:root {{
    --bg: {COLORS['bg']};
    --bg-elevated: {COLORS['bg_elevated']};
    --surface: {COLORS['surface']};
    --text: {COLORS['text']};
    --text-dim: {COLORS['text_dim']};
    --text-faint: {COLORS['text_faint']};
    --border: {COLORS['border']};
    --border-strong: {COLORS['border_strong']};
    --ice: {COLORS['ice']};
    --cyan: {COLORS['cyan']};
    --violet: {COLORS['violet']};
    --success: {COLORS['success']};
    --warning: {COLORS['warning']};
    --error: {COLORS['error']};
}}

html, body, [class*="css"] {{ letter-spacing: 0.006em; }}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }}
}}

/* ── Motion — 제한된 팔레트: fade-up / soft float / gradient drift / glow pulse ── */
@keyframes adetect-fade-up {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes adetect-float {{
    0%, 100% {{ transform: translateY(0); }}
    50%      {{ transform: translateY(-10px); }}
}}
@keyframes adetect-drift {{
    0%   {{ background-position: 0% 50%; }}
    100% {{ background-position: 100% 50%; }}
}}
@keyframes adetect-glow-pulse {{
    0%, 100% {{ opacity: 0.55; }}
    50%      {{ opacity: 1; }}
}}
@keyframes adetect-shimmer {{
    0%   {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}
.adetect-fade-up {{ animation: adetect-fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) both; }}

/* ── 배경: 순수 블랙 + 아주 은은한 luminous depth (이미지 없이 CSS만) ─────────── */
.stApp {{
    background:
        radial-gradient(1200px 680px at 14% -10%, rgba(174,235,255,0.05), transparent 60%),
        radial-gradient(980px 620px at 100% 6%, rgba(165,155,255,0.035), transparent 55%),
        radial-gradient(800px 500px at 50% 100%, rgba(100,216,255,0.025), transparent 60%),
        {COLORS['bg']};
}}

/* ── 기본 크롬 정리 ─────────────────────────────────────────────────────── */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], #MainMenu, footer {{ display: none; }}
[data-testid="stDecoration"] {{ display: none; }}

/* ── Top Navigation (st.navigation position="top") ───────────────────────
   thin / translucent / minimal / black 기반 / subtle border-bottom / active는 작은 indicator */
[data-testid="stAppHeader"] {{
    background: rgba(6,7,10,0.72) !important;
    backdrop-filter: blur(16px);
    border-bottom: 1px solid {COLORS['border']};
    height: 3.6rem;
}}
[data-testid="stHeader"] {{
    background: rgba(6,7,10,0.72) !important;
    backdrop-filter: blur(16px);
    border-bottom: 1px solid {COLORS['border']};
}}
a[data-testid="stTopNavLink"] {{
    color: {COLORS['text_dim']} !important;
    font-size: 0.86rem;
    font-weight: 450;
    border-radius: 0.5rem;
    background: transparent !important;
    box-shadow: none !important;
    position: relative;
    transition: color 0.15s ease;
}}
a[data-testid="stTopNavLink"]:hover {{
    color: {COLORS['text']} !important;
    background: rgba(255,255,255,0.045) !important;
}}
a[data-testid="stTopNavLink"][aria-current="page"] {{
    color: {COLORS['text']} !important;
    font-weight: 550;
    background: transparent !important;
}}
a[data-testid="stTopNavLink"][aria-current="page"]::after {{
    content: "";
    position: absolute;
    left: 0.9rem; right: 0.9rem; bottom: -0.4rem;
    height: 2px;
    background: linear-gradient(90deg, {COLORS['ice']}, {COLORS['violet']});
    border-radius: 2px;
}}
/* 사이드바는 더 이상 1차 내비게이션이 아님 — 남아있는 기본 크롬만 숨김 */
[data-testid="collapsedControl"] {{ display: none; }}

/* ── 본문 폭 + 여백 ────────────────────────────────────────────────────── */
[data-testid="stMainBlockContainer"] {{
    max-width: 1160px;
    margin: 0 auto;
    padding-top: 2.6rem;
    padding-bottom: 5rem;
    padding-left: 2rem;
    padding-right: 2rem;
}}
.adetect-full-bleed [data-testid="stMainBlockContainer"] {{ max-width: 100%; padding-left: 0; padding-right: 0; }}

/* ── 버튼: neutral, glow는 primary CTA에만 아주 은은하게 ─────────────────── */
.stButton button[kind="secondary"] {{
    background: transparent;
    border: 1px solid {COLORS['border']};
    color: {COLORS['text']};
    font-weight: 420;
    transition: border-color 0.15s ease, background-color 0.15s ease;
}}
.stButton button[kind="secondary"]:hover {{
    border-color: {COLORS['border_strong']};
    background: rgba(255,255,255,0.03);
}}
.stButton button[kind="primary"] {{
    background: {COLORS['text']};
    color: #06070A;
    font-weight: 560;
    box-shadow: 0 0 0 rgba(174,235,255,0);
    transition: box-shadow 0.2s ease, transform 0.15s ease;
}}
.stButton button[kind="primary"]:hover {{
    box-shadow: 0 0 28px rgba(174,235,255,0.22);
    transform: translateY(-1px);
}}

/* ── Typography utilities ─────────────────────────────────────────────── */
.adetect-eyebrow {{
    display: block;
    color: rgba(174,235,255,0.7);
    font-size: 0.76rem;
    font-weight: 550;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.adetect-eyebrow.is-neutral {{ color: {COLORS['text_faint']}; }}

.adetect-hero-title {{
    font-size: clamp(2.6rem, 4.4vw + 1rem, 4.6rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1.08;
    margin: 0;
    color: {COLORS['text']};
}}
.adetect-hero-sub {{
    color: {COLORS['text_dim']};
    font-size: 1.02rem;
    font-weight: 380;
    line-height: 1.75;
    margin-top: 1.5rem;
    max-width: 30rem;
}}
.adetect-display-title {{
    font-size: clamp(1.9rem, 2.6vw + 0.8rem, 3rem);
    font-weight: 560;
    letter-spacing: -0.025em;
    line-height: 1.16;
    color: {COLORS['text']};
    margin: 0;
}}
.adetect-page-title {{
    font-size: 1.7rem;
    font-weight: 560;
    letter-spacing: -0.015em;
    color: {COLORS['text']};
    margin: 0;
}}
.adetect-body-lg {{
    color: {COLORS['text_dim']};
    font-size: 1.02rem;
    font-weight: 380;
    line-height: 1.75;
    max-width: 34rem;
}}
@media (max-width: 900px) {{
    .adetect-hero-sub, .adetect-body-lg {{ max-width: 100%; }}
}}

/* ── Hero Visual — 오리지널 abstract SVG (ui/hero.py) ─────────────────────── */
.adetect-hero-visual {{
    position: relative;
    width: 100%;
    max-width: 460px;
    margin-left: auto;
    aspect-ratio: 1 / 1;
    animation: adetect-float 7s ease-in-out infinite;
}}
.adetect-hero-visual svg {{ width: 100%; height: 100%; display: block; }}
@media (max-width: 900px) {{
    .adetect-hero-visual {{ max-width: 260px; margin: 0 auto; }}
}}

/* ── Section shell — Home story section 공통 리듬 ─────────────────────────── */
.adetect-section {{ padding: 5.5rem 0; border-top: 1px solid {COLORS['border']}; }}
.adetect-section.is-first {{ border-top: none; padding-top: 1rem; }}
.adetect-section-eyebrow-num {{
    color: {COLORS['text_faint']};
    font-size: 0.78rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    margin-bottom: 0.9rem;
}}
@media (max-width: 900px) {{ .adetect-section {{ padding: 3.2rem 0; }} }}

/* ── Feature Story (Home §3~6) ─────────────────────────────────────────── */
.adetect-story-copy p.adetect-story-lead {{
    font-size: 1.5rem;
    font-weight: 540;
    letter-spacing: -0.015em;
    line-height: 1.35;
    color: {COLORS['text']};
    margin: 0 0 1rem 0;
}}
.adetect-story-copy p.adetect-story-desc {{
    color: {COLORS['text_dim']};
    font-size: 0.98rem;
    line-height: 1.75;
    font-weight: 380;
    margin: 0;
    max-width: 30rem;
}}
.adetect-story-panel {{
    position: relative;
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['lg']};
    background: linear-gradient(165deg, rgba(255,255,255,0.035), rgba(255,255,255,0.008));
    padding: 1.6rem 1.7rem;
    min-height: 220px;
}}
.adetect-story-panel::before {{
    content: "";
    position: absolute; inset: -1px;
    border-radius: inherit;
    padding: 1px;
    background: linear-gradient(140deg, rgba(174,235,255,0.22), transparent 40%, rgba(165,155,255,0.16));
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
    pointer-events: none;
}}

/* ── Value Prop (Home §2) ─────────────────────────────────────────────── */
.adetect-valueprop {{ text-align: left; max-width: 42rem; }}

/* ── Module list (하위 호환 — 더 이상 Home에서 기본 사용하지 않지만 유지) ─────── */
.adetect-module {{ display: flex; gap: 2.2rem; padding: 1.9rem 0; border-top: 1px solid {COLORS['border']}; }}
.adetect-module-label {{
    flex: 0 0 7rem; color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 500;
    letter-spacing: 0.14em; text-transform: uppercase; padding-top: 0.2rem;
}}
.adetect-module-title {{ font-size: 1.15rem; font-weight: 500; color: {COLORS['text']}; margin: 0 0 0.35rem 0; }}
.adetect-module-desc {{ color: {COLORS['text_dim']}; font-size: 0.9rem; font-weight: 380; line-height: 1.6; margin: 0; }}

/* ── Product Preview (Home §7) — floating layered panel ──────────────────── */
.adetect-preview-frame {{
    position: relative;
    border-radius: {RADIUS['lg']};
    border: 1px solid {COLORS['border']};
    background: {COLORS['bg_elevated']};
    padding: 1.4rem 1.6rem 1.7rem;
    box-shadow: 0 40px 90px -30px rgba(0,0,0,0.65);
}}
.adetect-preview-frame::after {{
    content: "";
    position: absolute; left: 6%; right: 6%; bottom: -14px; height: 40px;
    background: radial-gradient(ellipse at center, rgba(174,235,255,0.14), transparent 70%);
    filter: blur(6px); z-index: -1;
}}
.adetect-preview-dots {{ display: flex; gap: 0.35rem; margin-bottom: 1.1rem; }}
.adetect-preview-dots span {{ width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.14); }}

/* ── CTA section (Home §8) ────────────────────────────────────────────── */
.adetect-cta-title {{
    font-size: clamp(1.9rem, 2.6vw + 0.8rem, 2.7rem);
    font-weight: 560; letter-spacing: -0.02em; line-height: 1.2; color: {COLORS['text']};
    text-align: center; margin: 0 auto 2.2rem; max-width: 30rem;
}}

/* ── Glass Command Surface (Brand Command Bar) ────────────────────────── */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-glass-marker) {{
    background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['lg']};
    backdrop-filter: blur(22px);
    padding: 1.7rem 1.9rem 1.3rem;
    position: relative;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-glass-marker.is-glow) {{
    box-shadow: 0 0 60px -18px rgba(174,235,255,0.18);
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-glass-marker) [data-testid="stTextInput"] input {{
    font-size: 1.05rem !important;
}}

/* ── Input ─────────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid {COLORS['border']} !important;
    border-radius: {RADIUS['sm']} !important;
    color: {COLORS['text']} !important;
    padding: 0.62rem 0.9rem !important;
    font-weight: 380 !important;
    transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{ color: {COLORS['text_faint']} !important; opacity: 1 !important; }}
[data-testid="stTextInput"] input:hover,
[data-testid="stTextArea"] textarea:hover,
[data-testid="stNumberInput"] input:hover {{ border-color: {COLORS['border_strong']} !important; }}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus {{
    border-color: rgba(174,235,255,0.45) !important;
    background: rgba(174,235,255,0.045) !important;
    box-shadow: 0 0 0 3px rgba(174,235,255,0.08) !important;
}}
[data-testid="stWidgetLabel"] p {{ color: {COLORS['text_dim']} !important; font-size: 0.82rem !important; font-weight: 460 !important; }}
[data-testid="stWidgetLabel"] span[style*="rgba(250, 250, 250, 0.6)"] {{ color: {COLORS['text_faint']} !important; }}

/* ── CTA row (오른쪽 정렬 caption + button) ────────────────────────────── */
.adetect-cta-row-marker {{ position: absolute; }}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-cta-row-marker) {{
    display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 1rem;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-cta-row-marker) [data-testid="stElementContainer"] {{ width: auto; }}

/* ── Brand Context Bar (Workspace 상단, pages/2_analyze.py) ───────────────── */
.adetect-context-bar {{
    display: flex; align-items: center; flex-wrap: wrap; gap: 1.5rem;
    padding: 1rem 1.3rem;
    margin-bottom: 1.6rem;
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['md']};
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
}}
.adetect-context-brand {{ font-size: 1.02rem; font-weight: 560; color: {COLORS['text']}; }}
.adetect-context-meta {{ color: {COLORS['text_faint']}; font-size: 0.85rem; }}
.adetect-context-chips {{ display: flex; gap: 1.1rem; margin-left: auto; flex-wrap: wrap; }}
.adetect-context-chip {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; color: {COLORS['text_faint']}; }}
.adetect-context-chip b {{ color: {COLORS['text_dim']}; font-weight: 500; }}
@media (max-width: 768px) {{
    .adetect-context-bar {{ flex-direction: column; align-items: flex-start; }}
    .adetect-context-chips {{ margin-left: 0; }}
}}

/* ── Status dot / badge (StatusBadge 컴포넌트) ────────────────────────────── */
.adetect-status-dot {{ display: inline-flex; align-items: center; gap: 0.42em; font-size: 0.8rem; color: {COLORS['text_dim']}; }}
.adetect-status-dot::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; flex: none; }}
.adetect-status-dot.st-idle::before {{ background: {COLORS['text_faint']}; }}
.adetect-status-dot.st-running::before {{ background: {COLORS['ice']}; animation: adetect-glow-pulse 1.4s ease-in-out infinite; }}
.adetect-status-dot.st-done::before {{ background: {COLORS['success']}; }}
.adetect-status-dot.st-partial::before {{ background: {COLORS['warning']}; }}
.adetect-status-dot.st-fail::before {{ background: {COLORS['error']}; }}
.adetect-status-dot.st-cancel::before {{ background: {COLORS['text_faint']}; }}
.adetect-status-dot.st-locked::before {{ background: transparent; border: 1px solid {COLORS['text_faint']}; }}

/* ── Segmented Workspace Nav (WorkspaceTabs — st.segmented_control) ──────── */
[data-testid="stSegmentedControl"] {{
    border-bottom: 1px solid {COLORS['border']};
    padding-bottom: 0.9rem;
    margin-bottom: 1.8rem;
}}
[data-testid="stSegmentedControl"] label {{
    background: transparent !important;
    border: none !important;
    color: {COLORS['text_faint']} !important;
    font-size: 0.88rem !important;
    font-weight: 460 !important;
    padding: 0.3rem 0.2rem !important;
    margin-right: 1.6rem !important;
}}
[data-testid="stSegmentedControl"] label:hover {{ color: {COLORS['text_dim']} !important; }}
[data-testid="stSegmentedControl"] label[data-checked="true"],
[data-testid="stSegmentedControl"] label:has(input:checked) {{ color: {COLORS['text']} !important; }}

/* ── Section header (탭 상단, PRD §16) ────────────────────────────────────── */
.adetect-section-label {{
    color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 500;
    letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 0.3rem;
}}
.adetect-section-title {{ display: flex; align-items: baseline; gap: 0.8rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.adetect-section-title h3 {{ margin: 0 !important; font-weight: 560 !important; }}
.adetect-section-status {{ color: {COLORS['text_faint']}; font-size: 0.85rem; font-weight: 380; }}

/* ── Metric (숫자 + 라벨 + trend, 카드 아님) ───────────────────────────────── */
.adetect-metric-row {{ display: flex; flex-wrap: wrap; gap: 2.6rem; padding: 0.2rem 0 1.6rem; }}
.adetect-metric {{ min-width: 7rem; }}
.adetect-metric-label {{ color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.4rem; }}
.adetect-metric-value {{ font-size: 1.7rem; font-weight: 560; color: {COLORS['text']}; letter-spacing: -0.01em; line-height: 1; }}
.adetect-metric-value .unit {{ font-size: 0.95rem; color: {COLORS['text_dim']}; font-weight: 420; margin-left: 0.15em; }}
.adetect-metric-trend {{ font-size: 0.8rem; margin-top: 0.35rem; font-weight: 460; }}
.adetect-metric-trend.up {{ color: {COLORS['success']}; }}
.adetect-metric-trend.down {{ color: {COLORS['error']}; }}
.adetect-metric-trend.flat {{ color: {COLORS['text_faint']}; }}

/* ── Insight block — 숫자→차트→패턴→AI Insight→Evidence 흐름의 마지막 강조 지점 ── */
.adetect-insight {{
    position: relative;
    border-left: 2px solid rgba(174,235,255,0.35);
    padding: 0.2rem 0 0.2rem 1.1rem;
    margin: 0.9rem 0 1.1rem;
}}
.adetect-insight-head {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }}
.adetect-insight-head b {{ color: {COLORS['text']}; font-weight: 540; font-size: 0.95rem; }}

/* ── Badges (FACT / AI INTERPRETATION / RECOMMENDATION) ──────────────────── */
.adetect-badge {{ display: inline-flex; align-items: center; gap: 0.4em; font-size: 0.7rem; font-weight: 550; letter-spacing: 0.08em; text-transform: uppercase; margin-right: 0.6em; }}
.adetect-badge::before {{ content: ""; width: 5px; height: 5px; border-radius: 50%; display: inline-block; }}
.adetect-badge-fact {{ color: {COLORS['fact']}; }}
.adetect-badge-fact::before {{ background: {COLORS['fact']}; }}
.adetect-badge-ai {{ color: {COLORS['ai']}; }}
.adetect-badge-ai::before {{ background: {COLORS['ai']}; box-shadow: 0 0 6px rgba(174,235,255,0.7); }}
.adetect-badge-rec {{ color: {COLORS['rec']}; }}
.adetect-badge-rec::before {{ background: {COLORS['rec']}; box-shadow: 0 0 6px rgba(165,155,255,0.7); }}
.adetect-badge-sample {{ color: {COLORS['text_faint']}; }}
.adetect-badge-sample::before {{ background: {COLORS['text_faint']}; }}

/* ── Empty state (게이트 잠금/미실행) ──────────────────────────────────────── */
.adetect-empty {{ padding: 0.4rem 0 1.4rem; max-width: 32rem; }}
.adetect-empty-desc {{ color: {COLORS['text_dim']}; font-size: 0.92rem; line-height: 1.75; margin: 0 0 0.35rem 0; }}

/* ── Data table / Ad table ───────────────────────────────────────────────── */
.adetect-ad-table-wrap {{ overflow-x: auto; }}
.adetect-ad-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
.adetect-ad-table th {{
    text-align: left; color: {COLORS['text_faint']}; font-weight: 500; font-size: 0.72rem;
    letter-spacing: 0.06em; text-transform: uppercase; padding: 0.55rem 0.7rem;
    border-bottom: 1px solid {COLORS['border']}; white-space: nowrap;
}}
.adetect-ad-table td {{ color: {COLORS['text_dim']}; padding: 0.6rem 0.7rem; border-bottom: 1px solid {COLORS['border']}; vertical-align: top; }}
.adetect-ad-thumb-hover {{ position: relative; display: inline-block; color: {COLORS['text']}; border-bottom: 1px dotted rgba(255,255,255,0.3); cursor: help; }}
.adetect-ad-thumb-hover .adetect-ad-thumb-popup {{
    display: none; position: absolute; z-index: 60; left: 0; top: 1.5em;
    background: {COLORS['surface']}; border: 1px solid {COLORS['border_strong']};
    border-radius: {RADIUS['sm']}; padding: 0.4rem; box-shadow: 0 12px 32px rgba(0,0,0,0.55);
}}
.adetect-ad-thumb-hover .adetect-ad-thumb-popup img {{ display: block; width: 148px; height: 148px; object-fit: cover; border-radius: 0.4rem; background: rgba(255,255,255,0.05); }}
.adetect-ad-thumb-hover:hover .adetect-ad-thumb-popup {{ display: block; }}

/* ── Row list (History) ──────────────────────────────────────────────────── */
.adetect-row {{
    display: flex; align-items: center; gap: 1.6rem; flex-wrap: wrap;
    padding: 1.1rem 0.2rem; border-top: 1px solid {COLORS['border']};
    transition: background-color 0.15s ease;
}}
.adetect-row:hover {{ background: rgba(255,255,255,0.018); }}
.adetect-row-main {{ flex: 1 1 14rem; min-width: 0; }}
.adetect-row-brand {{ font-size: 0.98rem; font-weight: 540; color: {COLORS['text']}; margin: 0; }}
.adetect-row-meta {{ color: {COLORS['text_faint']}; font-size: 0.82rem; margin-top: 0.2rem; }}
.adetect-row-progress {{ display: flex; gap: 1rem; flex-wrap: wrap; }}

/* ── Settings status row ─────────────────────────────────────────────────── */
.adetect-kv-row {{ display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0.1rem; border-top: 1px solid {COLORS['border']}; }}
.adetect-kv-row span.label {{ color: {COLORS['text_dim']}; font-size: 0.92rem; }}

/* ── Checkbox 대비 보정 ───────────────────────────────────────────────────── */
[data-testid="stCheckbox"] svg, [data-testid="stCheckbox"] svg * {{ stroke: #06070A !important; }}

/* ── Chart 컨테이너: Streamlit 기본 vega 느낌을 낮추는 최소한의 톤 보정 ────────── */
[data-testid="stVegaLiteChart"] {{ border-radius: {RADIUS['sm']}; }}

/* ── Responsive breakpoints ──────────────────────────────────────────────── */
@media (max-width: 1280px) {{
    [data-testid="stMainBlockContainer"] {{ max-width: 96%; }}
}}
@media (max-width: 1024px) {{
    .adetect-story-panel {{ min-height: 180px; }}
}}
@media (max-width: 768px) {{
    [data-testid="stMainBlockContainer"] {{ padding-left: 1.2rem; padding-right: 1.2rem; padding-top: 1.6rem; }}
    .adetect-metric-row {{ gap: 1.6rem; }}
    [data-testid="stAppHeader"] a[data-testid="stNavigationLink"] {{ font-size: 0.8rem; padding: 0.25rem 0.1rem !important; margin-right: 0.9rem !important; }}
}}
@media (max-width: 390px) {{
    .adetect-hero-title {{ font-size: 2.2rem; }}
    .adetect-display-title {{ font-size: 1.7rem; }}
}}
</style>
"""


def inject_global_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def glass_marker(glow: bool = False):
    """이 함수를 st.container() 블록의 첫 줄에서 호출하면 그 컨테이너가 glass command surface가 됩니다."""
    cls = "adetect-glass-marker is-glow" if glow else "adetect-glass-marker"
    st.markdown(f'<div class="{cls}"></div>', unsafe_allow_html=True)


def cta_row_marker():
    """이 함수를 호출한 뒤 이어지는 위젯들(caption/button 등)을 한 줄에 배치하고
    마지막 위젯을 컨테이너 오른쪽 끝에 정렬합니다."""
    st.markdown('<div class="adetect-cta-row-marker"></div>', unsafe_allow_html=True)


def badge(kind: str, label: str | None = None) -> str:
    """FACT/AI/REC/SAMPLE 배지 HTML 조각을 반환합니다. (§8 3단계 분류)"""
    mapping = {
        "FACT": ("adetect-badge-fact", "FACT"),
        "AI": ("adetect-badge-ai", "AI INTERPRETATION"),
        "REC": ("adetect-badge-rec", "RECOMMENDATION"),
        "SAMPLE": ("adetect-badge-sample", "SAMPLE DATA"),
    }
    css_class, default_label = mapping.get(kind, ("adetect-badge-fact", kind))
    return f'<span class="adetect-badge {css_class}">{label or default_label}</span>'


def eyebrow(text: str, neutral: bool = False) -> str:
    cls = "adetect-eyebrow is-neutral" if neutral else "adetect-eyebrow"
    return f'<span class="{cls}">{text}</span>'


def section_title(label: str, title: str, status_text: str = ""):
    """탭 상단 헤더 — eyebrow 라벨 + 제목 + (선택) 상태 텍스트."""
    status_html = f'<span class="adetect-section-status">{status_text}</span>' if status_text else ""
    st.markdown(
        f'<div class="adetect-section-label">{label}</div>'
        f'<div class="adetect-section-title"><h3>{title}</h3>{status_html}</div>',
        unsafe_allow_html=True,
    )
