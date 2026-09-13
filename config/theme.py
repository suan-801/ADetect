"""디자인 시스템 — "Premium AI Intelligence / Black Monochrome / Minimal Glassmorphism".

★ 리디자인 원칙 (팀 피드백 반영, docs/PROJECT_PLAN.md §5):
- 모든 것을 카드/테두리로 감싸지 않는다 — 여백과 얇은 구분선으로 위계를 만든다.
- 컬러는 black/white/gray 중심, accent는 아주 좁은 범위에서만 사용한다.
- 이모지 아이콘을 쓰지 않는다 (Streamlit 내장 Material Symbols 선(line) 아이콘만 사용).
- Glassmorphism은 "보여주기"가 아니라 아주 은은한 깊이감 정도로만 쓴다.

색/폰트/라운드/보더의 기본값은 대부분 `.streamlit/config.toml`의 [theme] 토큰이 담당합니다
(공식 테마 시스템이라 어떤 Streamlit 내부 구조 변경에도 안정적으로 적용됩니다). 이 파일은
config.toml이 다루지 못하는 것만 최소한으로 추가합니다: 배경의 미세한 depth, 기본 크롬(툴바 등)
숨김, 사이드바 활성 상태, 히어로/모듈 타이포 유틸리티, 아주 옅은 glass 표면(:has() 트릭 1곳).
"""
import streamlit as st

COLORS = {
    "bg": "#070707",
    "text": "#F2F2F0",
    "text_dim": "#9A9A9E",
    "text_faint": "#5C5C60",
    "border": "rgba(255, 255, 255, 0.07)",
    "accent": "#C9A227",   # 아주 제한적으로만 사용 (링크, 미세한 하이라이트)
    "fact": "#9CA3AF",
    "ai": "#C9A227",
    "rec": "#C98A4A",
}

_CSS = f"""
<style>
html, body, [class*="css"] {{
    letter-spacing: 0.01em;
}}

/* ── 배경: 순수 블랙 + 거의 인지되지 않는 아주 은은한 depth ───────────────── */
.stApp {{
    background:
        radial-gradient(1100px 620px at 12% -12%, rgba(255,255,255,0.045), transparent 60%),
        radial-gradient(900px 560px at 100% 8%, rgba(255,255,255,0.028), transparent 55%),
        {COLORS['bg']};
}}

/* ── 기본 크롬 정리: 배포/메뉴 버튼 등 시각 노이즈 제거 ───────────────────── */
[data-testid="stToolbarActions"], #MainMenu, footer {{ display: none; }}
[data-testid="stAppHeader"] {{ background: transparent; }}
[data-testid="stDecoration"] {{ display: none; }}

/* ── 본문 폭 제한 + 넉넉한 여백 (편집 매체 같은 레이아웃) ─────────────────── */
[data-testid="stMainBlockContainer"] {{
    max-width: 1080px;
    margin: 0 auto;
    padding-top: 3.5rem;
    padding-bottom: 5rem;
    padding-left: 2rem;
    padding-right: 2rem;
}}

/* ── 사이드바: opacity로만 위계를 표현 (border/box 강조 없음) ──────────────── */
section[data-testid="stSidebar"] {{ width: 15rem !important; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
    border-radius: 8px;
    color: rgba(242, 242, 240, 0.48) !important;
    font-weight: 400;
    background: transparent !important;
    box-shadow: none !important;
    transition: color 0.15s ease;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{
    background: transparent !important;
    color: rgba(242, 242, 240, 0.78) !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: transparent !important;
    color: {COLORS['text']} !important;
    font-weight: 600;
    box-shadow: none !important;
}}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2 {{
    font-weight: 500;
}}

/* ── 버튼: neutral, 장식 없음 ─────────────────────────────────────────── */
.stButton button[kind="secondary"] {{
    background: transparent;
    border: 1px solid {COLORS['border']};
    color: {COLORS['text']};
    font-weight: 400;
}}
.stButton button[kind="secondary"]:hover {{
    border-color: rgba(255,255,255,0.22);
    color: {COLORS['text']};
}}
.stButton button[kind="primary"] {{
    background: {COLORS['text']};
    color: #0A0A0A;
    font-weight: 500;
    box-shadow: none;
}}
.stButton button[kind="primary"]:hover {{
    background: #D8D8D5;
}}

/* ── 타이포그래피 유틸리티 ────────────────────────────────────────────── */
.adetect-eyebrow {{
    display: block;
    color: {COLORS['text_faint']};
    font-size: 0.78rem;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 1.1rem;
}}
.adetect-hero-title {{
    font-size: 3.4rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1.08;
    margin: 0;
    color: {COLORS['text']};
}}
.adetect-hero-sub {{
    color: {COLORS['text_dim']};
    font-size: 0.98rem;
    font-weight: 350;
    line-height: 1.7;
    margin-top: 1.4rem;
    max-width: 26rem;
}}
@media (max-width: 900px) {{
    .adetect-hero-title {{ font-size: 2.4rem; }}
}}

/* ── Hero Object: hero_object.png 전용 wrapper (독립 컴포넌트, ui/hero.py) ── */
.adetect-hero-object {{
    width: 100%;
    max-width: 460px;
    margin-left: auto;
    margin-top: -0.5rem;
    transform: scale(1.1);
    transform-origin: top right;
    pointer-events: none;
}}
.adetect-hero-object img {{
    display: block;
    width: 100%;
    height: auto;
}}
@media (max-width: 900px) {{
    .adetect-hero-object {{ display: none; }}
}}

/* 모듈(=기능) 리스트 — 카드 대신 얇은 구분선 + 좌우 여백으로 위계 표현 */
.adetect-module {{
    display: flex;
    gap: 2.2rem;
    padding: 1.9rem 0;
    border-top: 1px solid {COLORS['border']};
}}
.adetect-module-label {{
    flex: 0 0 7rem;
    color: {COLORS['text_faint']};
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding-top: 0.2rem;
}}
.adetect-module-title {{
    font-size: 1.15rem;
    font-weight: 500;
    color: {COLORS['text']};
    margin: 0 0 0.35rem 0;
}}
.adetect-module-desc {{
    color: {COLORS['text_dim']};
    font-size: 0.9rem;
    font-weight: 350;
    line-height: 1.6;
    margin: 0;
}}

/* 상태 스트립 (Workspace 상단) — chip 대신 아주 조용한 한 줄 텍스트 */
.adetect-status-strip {{
    display: flex;
    gap: 1.4rem;
    align-items: baseline;
    flex-wrap: wrap;
    color: {COLORS['text_dim']};
    font-size: 0.85rem;
    font-weight: 350;
    padding-bottom: 1.1rem;
    margin-bottom: 1.6rem;
    border-bottom: 1px solid {COLORS['border']};
}}
.adetect-status-strip b {{ color: {COLORS['text']}; font-weight: 500; }}
.adetect-status-item {{ color: {COLORS['text_faint']}; }}
.adetect-status-item.is-active {{ color: {COLORS['text_dim']}; }}

/* 탭 섹션 헤더 (이모지 대신 eyebrow + 제목 + 상태 텍스트) */
.adetect-section-label {{
    color: {COLORS['text_faint']};
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}}
.adetect-section-title {{
    display: flex;
    align-items: baseline;
    gap: 0.7rem;
    margin-bottom: 1.6rem;
}}
.adetect-section-title h3 {{ margin: 0 !important; }}
.adetect-section-status {{ color: {COLORS['text_faint']}; font-size: 0.85rem; font-weight: 350; }}

/* 배지 (FACT / AI INTERPRETATION / RECOMMENDATION) — 칩이 아니라 옅은 라벨 텍스트 */
.adetect-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.4em;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-right: 0.6em;
}}
.adetect-badge::before {{
    content: "";
    width: 5px; height: 5px;
    border-radius: 50%;
    display: inline-block;
}}
.adetect-badge-fact {{ color: {COLORS['fact']}; }}
.adetect-badge-fact::before {{ background: {COLORS['fact']}; }}
.adetect-badge-ai {{ color: {COLORS['ai']}; }}
.adetect-badge-ai::before {{ background: {COLORS['ai']}; }}
.adetect-badge-rec {{ color: {COLORS['rec']}; }}
.adetect-badge-rec::before {{ background: {COLORS['rec']}; }}
.adetect-badge-sample {{ color: {COLORS['text_faint']}; }}
.adetect-badge-sample::before {{ background: {COLORS['text_faint']}; }}

/* ── Glass surface: 진짜 위젯을 감싸야 하는 유일한 지점(브랜드 입력 커맨드바)에만 사용 ── */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-glass-marker) {{
    background: rgba(255,255,255,0.035);
    border: 1px solid {COLORS['border']};
    border-radius: 1.1rem;
    backdrop-filter: blur(20px);
    padding: 1.6rem 1.8rem 1.2rem 1.8rem;
}}

/* ── Input: page 배경보다 살짝 밝은 surface + 명확한 hover/focus state ────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {{
    background: rgba(255,255,255,0.045) !important;
    border: 1px solid {COLORS['border']} !important;
    border-radius: 0.6rem !important;
    color: {COLORS['text']} !important;
    padding: 0.6rem 0.85rem !important;
    font-weight: 350 !important;
    transition: border-color 0.15s ease, background-color 0.15s ease;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{
    color: {COLORS['text_faint']} !important;
    opacity: 1 !important;
}}
[data-testid="stTextInput"] input:hover,
[data-testid="stTextArea"] textarea:hover,
[data-testid="stNumberInput"] input:hover {{
    border-color: rgba(255,255,255,0.18) !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus {{
    border-color: rgba(255,255,255,0.4) !important;
    background: rgba(255,255,255,0.065) !important;
    box-shadow: none !important;
}}
[data-testid="stWidgetLabel"] p {{
    color: {COLORS['text_dim']} !important;
    font-size: 0.82rem !important;
    font-weight: 450 !important;
}}

/* Streamlit ":gray[]" 마크다운 색상(rgba(250,250,250,0.6))이 검정 배경 위에서 생각보다
   눈에 띄어서, 경쟁사 유형 태그(예: "· 직접 경쟁")를 디자인 시스템의 text_faint 톤으로 더 옅게 */
[data-testid="stWidgetLabel"] span[style*="rgba(250, 250, 250, 0.6)"] {{
    color: {COLORS['text_faint']} !important;
}}

/* ── CTA row: 마지막 위젯을 Card 오른쪽 padding에 정확히 맞춰 정렬 ────────── */
.adetect-cta-row-marker {{ position: absolute; }}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-cta-row-marker) {{
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .adetect-cta-row-marker) [data-testid="stElementContainer"] {{
    width: auto;
}}

/* ── 소재 테이블 + 소재 ID 마우스오버 썸네일(§7-11-4, PRD "소재 미리보기") ────── */
.adetect-ad-table-wrap {{ overflow-x: auto; }}
.adetect-ad-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}}
.adetect-ad-table th {{
    text-align: left;
    color: {COLORS['text_faint']};
    font-weight: 500;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.5rem 0.7rem;
    border-bottom: 1px solid {COLORS['border']};
    white-space: nowrap;
}}
.adetect-ad-table td {{
    color: {COLORS['text_dim']};
    padding: 0.55rem 0.7rem;
    border-bottom: 1px solid {COLORS['border']};
    vertical-align: top;
}}
.adetect-ad-thumb-hover {{
    position: relative;
    display: inline-block;
    color: {COLORS['text']};
    border-bottom: 1px dotted rgba(255,255,255,0.35);
    cursor: help;
}}
.adetect-ad-thumb-hover .adetect-ad-thumb-popup {{
    display: none;
    position: absolute;
    z-index: 60;
    left: 0;
    top: 1.5em;
    background: #111113;
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 0.6rem;
    padding: 0.4rem;
    box-shadow: 0 12px 32px rgba(0,0,0,0.55);
}}
.adetect-ad-thumb-hover .adetect-ad-thumb-popup img {{
    display: block;
    width: 148px;
    height: 148px;
    object-fit: cover;
    border-radius: 0.4rem;
    background: rgba(255,255,255,0.05);
}}
.adetect-ad-thumb-hover:hover .adetect-ad-thumb-popup {{ display: block; }}

/* ── 체크박스: 체크 시 흰 배경 위에 흰색 체크마크가 그려져 선택 여부가 안 보이던 문제 ──
   (예: STEP1 확인 화면의 경쟁사 체크박스). 체크마크만 어두운 색으로 바꿔 대비를 확보한다.
   unchecked 상태에는 이 svg 자체가 렌더링되지 않으므로 checked 상태에만 영향을 준다. */
[data-testid="stCheckbox"] svg,
[data-testid="stCheckbox"] svg * {{
    stroke: #0B0C10 !important;
}}
</style>
"""


def inject_global_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def glass_marker():
    """이 함수를 st.container() 블록의 첫 줄에서 호출하면 그 컨테이너가 은은한 glass surface가 됩니다."""
    st.markdown('<div class="adetect-glass-marker"></div>', unsafe_allow_html=True)


def cta_row_marker():
    """이 함수를 호출한 뒤 이어지는 위젯들(caption/button 등)을 한 줄에 배치하고
    마지막 위젯을 컨테이너 오른쪽 끝(Card의 오른쪽 padding)에 정확히 맞춥니다.
    Home의 '분석하기 →'와 Analyze의 CTA가 동일한 위치·정렬을 갖도록 공통으로 사용합니다."""
    st.markdown('<div class="adetect-cta-row-marker"></div>', unsafe_allow_html=True)


def badge(kind: str, label: str | None = None) -> str:
    """FACT/AI/REC/SAMPLE 배지 HTML 조각을 반환합니다. (§8 3단계 분류, 미니멀 라벨 스타일)"""
    mapping = {
        "FACT": ("adetect-badge-fact", "FACT"),
        "AI": ("adetect-badge-ai", "AI INTERPRETATION"),
        "REC": ("adetect-badge-rec", "RECOMMENDATION"),
        "SAMPLE": ("adetect-badge-sample", "SAMPLE DATA"),
    }
    css_class, default_label = mapping.get(kind, ("adetect-badge-fact", kind))
    return f'<span class="adetect-badge {css_class}">{label or default_label}</span>'


def eyebrow(text: str) -> str:
    return f'<span class="adetect-eyebrow">{text}</span>'


def section_title(label: str, title: str, status_text: str = ""):
    """탭 상단 헤더 — 이모지 대신 eyebrow 라벨 + 제목 + (선택) 상태 텍스트."""
    status_html = f'<span class="adetect-section-status">{status_text}</span>' if status_text else ""
    st.markdown(
        f'<div class="adetect-section-label">{label}</div>'
        f'<div class="adetect-section-title"><h3>{title}</h3>{status_html}</div>',
        unsafe_allow_html=True,
    )
