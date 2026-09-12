"""디자인 시스템 — ref.png(다크+골드 톤) 참고, PRD §17 디자인 가이드 반영.

주의: 화면 콘텐츠/기능은 PRD.md를 기준으로 하고, 이 파일은 오직 "시각적 스타일"만 담당합니다.
Streamlit 기본 위젯 위에 CSS를 덮어씌우는 방식이라 ref.png와 100% 동일하지는 않습니다
(예: 사이드바 네비게이션 아이콘 배치, 히어로 영역의 3D 오브젝트 그래픽 등은 구현 난이도가 높아
단순화했습니다 — 실제 픽셀 단위 재현이 필요하면 알려주세요).
"""
import streamlit as st

# Pretendard 오픈소스 웹폰트 (jsDelivr CDN, 별도 파일 불필요)
PRETENDARD_CDN = (
    "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@1.3.9/dist/web/static/pretendard.css"
)

COLORS = {
    "bg": "#0B0C10",
    "bg_alt": "#111115",
    "card": "rgba(20, 20, 25, 0.88)",
    "card_border": "rgba(255, 255, 255, 0.08)",
    "gold": "#D4AF37",
    "gold_soft": "#C5A059",
    "text": "#F5F1E8",
    "text_dim": "#9A9AA3",
    "fact": "#B8BCC4",       # FACT 배지 - 실버/그레이 (§17)
    "ai": "#D4AF37",         # AI INTERPRETATION 배지 - 골드 (§17)
    "rec": "#E08A3C",        # RECOMMENDATION 배지 - 앰버 (§17)
}

_CSS = f"""
<link rel="stylesheet" as="style" crossorigin href="{PRETENDARD_CDN}" />
<style>
html, body, [class*="css"], .stMarkdown, .stButton button {{
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}
.stApp {{
    background: {COLORS['bg']};
    color: {COLORS['text']};
}}
section[data-testid="stSidebar"] {{
    background: {COLORS['bg_alt']};
    border-right: 1px solid {COLORS['card_border']};
}}
section[data-testid="stSidebar"] * {{
    color: {COLORS['text']} !important;
}}

/* 카드 컨테이너 (st.container(border=True) 기반) */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['card_border']} !important;
    border-radius: 16px;
}}

/* 기본 버튼 */
.stButton button {{
    background: {COLORS['text']};
    color: #0B0C10;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    padding: 0.55em 1.3em;
}}
.stButton button:hover {{
    background: {COLORS['gold']};
    color: #0B0C10;
}}
.stButton button:disabled {{
    background: rgba(255,255,255,0.12);
    color: {COLORS['text_dim']};
}}

/* 배지 (FACT / AI INTERPRETATION / RECOMMENDATION, PRD §8·§17) */
.adetect-badge {{
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    padding: 2px 9px;
    border-radius: 999px;
    margin-right: 6px;
}}
.adetect-badge-fact {{ background: rgba(184,188,196,0.15); color: {COLORS['fact']}; border: 1px solid {COLORS['fact']}; }}
.adetect-badge-ai {{ background: rgba(212,175,55,0.15); color: {COLORS['ai']}; border: 1px solid {COLORS['ai']}; }}
.adetect-badge-rec {{ background: rgba(224,138,60,0.15); color: {COLORS['rec']}; border: 1px solid {COLORS['rec']}; }}
.adetect-badge-sample {{ background: rgba(255,255,255,0.08); color: {COLORS['text_dim']}; border: 1px dashed {COLORS['text_dim']}; }}

.adetect-hero-title {{
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1.15;
    margin: 0;
}}
.adetect-hero-sub {{
    color: {COLORS['text_dim']};
    font-size: 1.05rem;
    margin-top: 14px;
}}
.adetect-eyebrow {{
    color: {COLORS['gold']};
    letter-spacing: 0.12em;
    font-weight: 700;
    font-size: 0.85rem;
}}
.adetect-status-strip {{
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
    color: {COLORS['text_dim']};
    font-size: 0.95rem;
    padding: 10px 0 4px 0;
    border-bottom: 1px solid {COLORS['card_border']};
    margin-bottom: 14px;
}}
.adetect-chip {{
    background: rgba(255,255,255,0.06);
    border: 1px solid {COLORS['card_border']};
    border-radius: 999px;
    padding: 3px 12px;
    font-size: 0.85rem;
}}
</style>
"""


def inject_global_css():
    st.markdown(_CSS, unsafe_allow_html=True)


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
