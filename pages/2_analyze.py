"""팩트 중심 수집: 조사 설정 → 수집 범위 확인 → 4개 자료 탭."""
import streamlit as st
from config import settings
from database.db import create_session
from core.collection import words,keyword_help,DEFAULT_OPTIONS,TOKEN_MESSAGE,paid_problem
from ui.facts_workspace import render,collection_bar,unified_downloads,save_inputs
from ui.components import analysis_status_index,brand_context_header

st.session_state.setdefault("step","input")
st.session_state.setdefault("session",None)
if st.session_state.step=="input":
    st.title("조사 대상 설정")
    brand=st.text_input("브랜드명 *",key="input_brand_name")
    campaign=st.text_input("조사 대상 (선택)",key="input_campaign",placeholder="예: TM사관학교 채용 / 러닝화 / 특정 모집 과정")
    st.caption("브랜드 전체를 조사하면 비워두세요. 특정 캠페인은 공식 랜딩·계정과 포함 문구로 범위를 좁힙니다.")
    category=st.text_input("관심 주제 (선택)",key="input_category",placeholder="예: TM 채용")
    competitors=st.text_input("함께 조사할 브랜드 (선택 — 쉼표로 구분)",key="input_competitors")
    if st.button("다음",type="primary",disabled=not brand.strip(),key="btn_step1_next"):
        st.session_state.draft={"brand_name":brand.strip(),"campaign":campaign.strip(),"category":category.strip(),"competitors_raw":competitors.strip()}
        st.session_state.step="confirm"
        st.rerun()
elif st.session_state.step=="confirm":
    draft=st.session_state.draft
    st.title("수집 범위 확인")
    st.caption("이 화면에서는 외부 API를 자동 호출하지 않습니다. 실제 수집은 Workspace의 수집 버튼으로 시작합니다.")
    brand=draft["brand_name"]
    campaign=st.text_input("조사 대상 (선택)",value=draft.get("campaign",""),key="confirm_campaign")
    category=st.text_input("관심 주제",value=draft.get("category", ""),key="confirm_category")
    competitors=words(st.text_input("함께 조사할 브랜드 (선택)",value=draft.get("competitors_raw",""),key="confirm_competitors"))
    competitors=[c for c in competitors if c!=brand]
    own=words(st.text_input("브랜드/캠페인 검색어 (쉼표로 구분)",value=(brand+" "+campaign).strip(),key="brand_keywords"))
    general=words(st.text_input("일반 검색어 (쉼표로 구분)",value=category,key="general_keywords",placeholder="예: TM 채용, 보험 상담원 채용"))
    preview={"brand_name":brand,"brand_keywords":own,"general_keywords":general,"category":category}
    for explanation in keyword_help(preview): st.info(explanation)
    st.caption("브랜드/캠페인 검색어와 일반 검색어를 합쳐 최대 10개까지 수집합니다. 각 검색어의 3년 추이를 별도로 조회합니다.")
    includes=words(st.text_input("포함할 문구 (선택)",value=campaign,key="include_terms",placeholder="예: TM사관학교, TM 채용"))
    excludes=words(st.text_input("제외할 문구 (선택)",key="exclude_terms",placeholder="예: 자동차보험 가입"))
    st.caption("광고는 대상 랜딩 일치 또는 포함 문구로 분류합니다. 제외 문구가 우선이며, 모호한 자료는 확인 필요로 남깁니다.")
    sources={}
    for name in [brand,*competitors]:
        with st.expander(name+" · 공식 페이지·계정",expanded=name==brand):
            sources[name]={
                "homepage":st.text_input("공식 홈페이지 또는 조사 랜딩 URL",key="homepage_"+name),
                "detail_url":st.text_input("특정 상세/캠페인 페이지 URL (선택)",key="detail_"+name),
                "instagram":st.text_input("공식 Instagram 계정 또는 URL",key="instagram_"+name),
                "youtube":st.text_input("YouTube 채널 ID 또는 @handle (선택)",key="youtube_"+name),
                "meta_page":st.text_input("Meta 광고 라이브러리 페이지 URL",key="setup_meta_"+name)}
            st.caption("알 수 없는 계정은 비워두세요. 추측하지 않고 미수집으로 표시합니다.")
    paid=st.toggle("유료 기능 ON",value=True,key="confirm_paid")
    if paid:
        for service in ("Apify","Gemini"):
            if paid_problem({"paid_enabled":True},service)==TOKEN_MESSAGE: st.warning(service+" · "+TOKEN_MESSAGE)
    labels={"website":"홈페이지·화면 캡처·이미지 원본","news":"검색어 관련 뉴스","search_capture":"네이버 검색 화면","instagram":"Instagram 최근 게시물 (유료)","youtube":"YouTube 최근 게시물","meta":"Meta 광고 소재·원본 (유료)","summary":"선택 자료 근거 요약 (유료)"}
    options={k:st.checkbox(label,value=True,key="option_"+k) for k,label in labels.items()}
    st.caption("기본 포함: 36개월 검색 추이·월별 피크/저점·최근 검색량. Meta 최대 20건/페이지, 뉴스 최대 100건/검색어, SNS 최근 최대 5건 표본. 원본은 개별 25MB·랜딩 이미지 6MB 제한입니다.")
    if settings.SAMPLE_MODE: st.warning("현재 SAMPLE 모드입니다. 외부 API를 호출하지 않습니다.")
    back,go=st.columns(2)
    with back:
        if st.button("이전",key="btn_confirm_back"):
            st.session_state.step="input"
            st.rerun()
    with go:
        if st.button("자료 수집 화면 열기",type="primary",key="btn_confirm_go",disabled=not own or len(set(own+general))>10):
            session={"id":create_session(brand,category,competitors),"brand_name":brand,"category":category,"competitors":competitors,
                     "campaign":campaign,"brand_keywords":own,"general_keywords":general,"include_terms":includes,"exclude_terms":excludes,
                     "sources":sources,"paid_enabled":paid,"collection_options":options,"reviews":{},"selected_records":[],"research_version":2,
                     **{stage+"_status":"미실행" for stage in ("market","brand","creative","synthesis")}}
            save_inputs(session)
            st.session_state.session=session
            st.session_state.step="workspace"
            st.rerun()
else:
    session=st.session_state.session
    a,b=st.columns([7,5])
    with a:
        brand_context_header(session)
        st.caption("조사 대상: "+(session.get("campaign") or "브랜드 전체"))
        if st.button("새 조사 시작",key="btn_reset_session"):
            # Clear input widget state so a different brand cannot inherit prior sources/filters.
            for k in list(st.session_state):
                if k not in ("step",): del st.session_state[k]
            st.session_state.step="input"
            st.rerun()
    with b:
        analysis_status_index([(label,session.get(stage+"_status","미실행")) for stage,label in (("market","검색·뉴스"),("brand","공식 페이지·SNS"),("creative","광고 소재"),("synthesis","확인·정리"))])
    collecting=collection_bar(session)
    tabs=st.tabs(["01 검색·뉴스","02 공식 페이지·SNS","03 광고 소재","04 확인·정리"])
    for tab,stage in zip(tabs,("market","brand","creative","synthesis")):
        with tab:
            if collecting: st.info("선택한 자료를 순서대로 수집하고 있습니다.")
            else: render(session,stage)
    if not collecting: unified_downloads(session)
