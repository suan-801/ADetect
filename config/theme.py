"""디자인 시스템 — "Brand Intelligence Platform / Editorial Technology Product".

3차 리뉴얼 원칙 (2026-09 교정, 이전 "Luminous Dark" 방향에서 전환):
- Blue glow / orb / gradient / glassmorphism을 전부 제거한다 — 전형적인 "AI SaaS 데모" 인상을
  주는 가장 큰 원인이었다. 배경은 순수 flat black이고, 장식은 존재하지 않는다.
- Orange-red(#FF4D2E)는 브랜드 accent다. 넓은 면적을 채우지 않고 active nav/key action/
  section index/important highlight/selected state 등 "의미가 있는 지점"에만 쓴다.
  Ice blue는 브랜드 컬러가 아니라 semantic data color(진행중/primary chart/AI 해석)로 격하한다.
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
    "bg": "#060708",
    "bg_elevated": "#0A0C0F",
    "surface": "#0D1014",
    "border": "#202328",
    "border_soft": "#15181C",
    "text": "#F4F5F7",
    "text_dim": "#8D949E",
    "text_faint": "#5F6670",
    # Primary brand accent — orange-red. 좁은 면적에만: active nav, key action, section index,
    # important highlight, key data point, selected state.
    "accent": "#FF4D2E",
    "accent_hover": "#FF6A4E",
    # Filled CTA surface — accent(#FF4D2E)를 넓은 면적(버튼 배경)에 그대로 쓰면 밝은 텍스트도
    # 어두운 텍스트도 대비가 애매해진다. 넓은 면적 전용으로 한 단계 더 어둡게 분리하고,
    # 그 위에는 항상 밝은 텍스트(text_on_accent)를 쓴다 — WCAG AA(4.5:1 이상) 확인됨.
    "accent_surface": "#B23A1F",
    "accent_surface_hover": "#C2431F",
    "text_on_accent": "#FFF8F4",
    # Data semantic colors — 브랜드 컬러가 아니라 상태/차트 전용.
    "data_blue": "#5AA9E6",
    "success": "#5FBF77",
    "warning": "#D9A441",
    "error": "#E5484D",
    # §8 FACT/AI/REC 3단 스키마
    "fact": "#8D949E",
    "ai": "#5AA9E6",
    "rec": "#FF4D2E",
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
@keyframes adetect-pipeline-move {{
    0%   {{ top: 2%; opacity: 0; }}
    8%   {{ opacity: 1; }}
    92%  {{ opacity: 1; }}
    100% {{ top: 96%; opacity: 0; }}
}}
.adetect-fade-up {{ animation: adetect-fade-up 0.4s ease both; }}

/* ── 배경: flat black, gradient/glow 없음 ─────────────────────────────────── */
.stApp {{ background: {COLORS['bg']}; }}

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

/* ── Hero grid (12-col: 왼쪽 7 / 오른쪽 5), 높이는 콘텐츠에 맞춰 자연스럽게 ─────── */
.adetect-hero-shell {{ padding: 2.2rem 0 3rem; }}
@media (max-width: 900px) {{ .adetect-hero-shell {{ padding: 1rem 0 2rem; }} }}

/* ── Intelligence Pipeline wrap (Hero 오른쪽 컬럼 anchor) ──────────────────
   Pipeline이 5-col 폭 전체로 퍼지면 Headline과 시각적으로 경쟁하므로, 폭을 제한하고
   오른쪽으로 anchor한다. Visual priority: Headline > Brand Input/CTA > Pipeline. */
div[data-testid="column"]:has(div[data-testid="stElementContainer"] .adetect-pipeline-wrap-marker) {{
    max-width: 340px;
    margin-left: auto;
    margin-top: 2.6rem;
}}
@media (max-width: 900px) {{
    div[data-testid="column"]:has(div[data-testid="stElementContainer"] .adetect-pipeline-wrap-marker) {{
        max-width: 100%;
        margin-left: 0;
        margin-top: 2.4rem;
    }}
}}

/* ── Intelligence Pipeline (Hero right visual) ────────────────────────────
   thin line + number + label. glow/orb 없음. active indicator만 accent color. */
.adetect-pipeline {{ position: relative; padding: 0.4rem 0 0.4rem 2.1rem; }}
.adetect-pipeline::before {{
    content: "";
    position: absolute; left: 7px; top: 6px; bottom: 6px; width: 1px;
    background: {COLORS['border']};
}}
.adetect-pipeline-dot {{
    position: absolute; left: 3px; width: 9px; height: 9px; border-radius: 50%;
    background: {COLORS['accent']};
    animation: adetect-pipeline-move 6s ease-in-out infinite;
}}
.adetect-pipeline-step {{ position: relative; padding: 1.05rem 0; border-bottom: 1px solid {COLORS['border_soft']}; }}
.adetect-pipeline-step:last-child {{ border-bottom: none; }}
.adetect-pipeline-num {{ color: {COLORS['text_faint']}; font-size: 0.72rem; font-weight: 550; letter-spacing: 0.08em; }}
.adetect-pipeline-label {{ color: {COLORS['text']}; font-size: 0.98rem; font-weight: 540; margin-top: 0.15rem; }}

/* ── Section shell — Home story section 공통 리듬 ─────────────────────────── */
.adetect-section {{ padding: 4.5rem 0; border-top: 1px solid {COLORS['border']}; }}
.adetect-section.is-first {{ border-top: none; padding-top: 0.5rem; }}
.adetect-section-eyebrow-num {{ color: {COLORS['text_faint']}; font-size: 0.78rem; font-weight: 500; letter-spacing: 0.1em; margin-bottom: 0.8rem; }}
@media (max-width: 900px) {{ .adetect-section {{ padding: 2.6rem 0; }} }}

/* ── Feature Story (Home §3~6) ─────────────────────────────────────────── */
.adetect-story-copy p.adetect-story-lead {{
    font-size: 1.4rem; font-weight: 560; letter-spacing: -0.01em; line-height: 1.32;
    color: {COLORS['text']}; margin: 0 0 0.9rem 0;
}}
.adetect-story-copy p.adetect-story-desc {{
    color: {COLORS['text_dim']}; font-size: 0.95rem; line-height: 1.72; font-weight: 400;
    margin: 0; max-width: 28rem;
}}
.adetect-story-panel {{
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['md']};
    background: {COLORS['bg_elevated']};
    padding: 1.5rem 1.6rem;
    min-height: 200px;
}}

/* ── Value Prop (Home §2) ─────────────────────────────────────────────── */
.adetect-valueprop {{ text-align: left; max-width: 40rem; }}

/* ── Product Preview (Home §7) — flat frame, shadow 없음 ──────────────────── */
.adetect-preview-frame {{
    border-radius: {RADIUS['md']};
    border: 1px solid {COLORS['border']};
    background: {COLORS['bg_elevated']};
    padding: 1.4rem 1.6rem 1.7rem;
}}
.adetect-preview-dots {{ display: flex; gap: 0.35rem; margin-bottom: 1.1rem; }}
.adetect-preview-dots span {{ width: 6px; height: 6px; border-radius: 50%; background: {COLORS['border']}; }}

/* ── CTA section (Home §8) ────────────────────────────────────────────── */
.adetect-cta-title {{
    font-size: clamp(1.6rem, 1.1rem + 1.4vw, 2.3rem);
    font-weight: 560; letter-spacing: -0.015em; line-height: 1.25; color: {COLORS['text']};
    text-align: left; margin: 0 0 1.8rem;
}}

/* ── Brand Command Bar (Hero, flat — glass/blur/glow 없음) ────────────────── */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-command-marker) {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS['md']};
    padding: 1.1rem 1.2rem;
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


def pipeline_wrap_marker():
    """이 함수를 Hero 오른쪽 column의 첫 줄에서 호출하면 그 column이 Intelligence Pipeline
    anchor(최대폭 제한 + 오른쪽 정렬)로 스타일링됩니다."""
    st.markdown('<div class="adetect-pipeline-wrap-marker"></div>', unsafe_allow_html=True)


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
