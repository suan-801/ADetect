# LEGACY — 현재 런타임(app.py 네비게이션·신규 화면)에서 import/실행하지 않는다. (2026-09-27 검색 확인, PRD §0 18차 개정)
# 신규 UI: pages/2_analyze.py → ui/project_workspace.py
# 신규 데이터 흐름: core/projects.py, core/project_jobs.py
# 사용 금지 이유: 17차 개정의 4단계(Market/Brand/Creative/Synthesis) 자료 화면. 단계 단위 run_stage/run_all 실행과 세션 입력 구조를 쓴다. 18차 개정에서 프로젝트·8개 자료 종류 단위 수집으로 대체되었다.
# 새 화면에 다시 연결하지 말 것. 기존 데이터 호환 검토 전까지 삭제하지 않고 보존한다.

"""수집 자료 탐색·확인·요약·통합 다운로드 화면."""
import math
import hashlib
import json
import streamlit as st
import pandas as pd
from core.collection import run_stage,run_all,all_records,apply_reviews,keyword_help,paid_problem,TOKEN_MESSAGE
from core.runtime import persist_result
from core.exporters.artifact_store import save_artifact,record_download
from core.exporters.facts_report import combined,package
from core.exporters.report_builder import build_report_excel,build_report_html
from core.evidence_store import read_bytes
from database.db import save_session_inputs
from ui.job_control import start,pending

INPUT_FIELDS=("campaign","brand_keywords","general_keywords","include_terms","exclude_terms","sources","paid_enabled","collection_options","reviews","selected_records","research_version")
LABELS={"market":"검색·뉴스 자료","brand":"공식 페이지·SNS","creative":"광고 소재","synthesis":"확인·정리"}


def save_inputs(session):
    save_session_inputs(session["id"],{k:session[k] for k in INPUT_FIELDS if k in session and session[k] is not None})


def export_buttons(session,function,result):
    cols=st.columns(3)
    for col,ext,label in zip(cols,("html","xlsx","zip"),("HTML 리포트","Excel","ZIP 원본 패키지")):
        key=f"{function}_export_{ext}"
        with col:
            if st.button(label+" 생성",key=f"gen_{ext}_{function}"):
                try:
                    data=build_report_html(session,function,result) if ext=="html" else build_report_excel(function,result) if ext=="xlsx" else package(session,result)
                    run=session.get(function+"_run_id")
                    signature=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    if not run or (function=="collection" and session.get("collection_export_signature")!=signature):
                        run=persist_result(session,function,result)
                        if function=="collection": session["collection_export_signature"]=signature
                    aid=save_artifact(run,function,ext,data)
                    session[key]=data
                    session[key+"_id"]=aid
                except (ValueError,OSError):
                    st.error("파일 저장 실패 — 저장 공간과 원본 파일을 확인해주세요.")
            if session.get(key):
                st.download_button(label+" 다운로드",session[key],file_name=f"ADetect_{function}.{ext}",key=f"dl_{ext}_{function}",
                    on_click=record_download,args=(session[key+"_id"],))
    st.caption("파일 생성 이력과 다운로드 요청 시각을 PC에 저장합니다. 브라우저 저장 완료 여부는 확인하지 않습니다.")


def collection_bar(session):
    for text in keyword_help(session): st.caption(text)
    session["paid_enabled"]=st.toggle("유료 기능 ON",value=session.get("paid_enabled",True),key="workspace_paid_"+session["id"])
    if session["paid_enabled"]:
        for service in ("Apify","Gemini"):
            if paid_problem(session,service)==TOKEN_MESSAGE: st.warning(f"{service} · {TOKEN_MESSAGE}")
    st.caption("유료 기능 ON은 Meta·Instagram 수집과 선택 자료 요약에 적용됩니다. 키 설정 여부와 잔액·권한 검증은 다릅니다.")
    save_inputs(session)
    if pending(session,"collection"): return True
    session["collection_force"]=st.checkbox("캐시를 사용하지 않고 새로 수집",value=False,key="fresh_collection")
    busy=any(session.get(s+"_job") for s in LABELS)
    a,b=st.columns(2)
    with a:
        if st.button("선택한 자료 한 번에 수집",type="primary",key="collect_all",disabled=busy):
            start(session,"collection",lambda snap:run_all(snap),{"inputs":{k:session.get(k) for k in INPUT_FIELDS},"action":"all"})
    with b:
        if st.button("미수집·실패 항목만 재시도",key="retry_all",disabled=busy):
            start(session,"collection",lambda snap:run_all(snap,True),{"action":"retry"})
    return False


def trends(result):
    parts=[p for p in result.get("parts",{}).values() if p.get("series")]
    if not parts: return
    st.write("3년 검색 추이 · 완료된 최근 36개월")
    chosen=st.selectbox("추이를 볼 검색어",range(len(parts)),format_func=lambda i:parts[i]["series"]["keyword"],key="trend_keyword")
    part=parts[chosen]
    series,summary=part["series"],part["seasonality"]
    if series["rows"]:
        st.line_chart(pd.DataFrame(series["rows"]).set_index("date")["search_index"])
    st.caption(series["note"])
    st.caption(f"조회 기간 {series['start']} ~ {series['end']} · 제공 {summary['observed_months']}/36개월")
    if summary["peak_months"]:
        st.write("평균 피크: "+", ".join(f"{m}월" for m in summary["peak_months"])+" · 평균 저점: "+", ".join(f"{m}월" for m in summary["low_months"]))
    else:
        st.info("월별 차이가 없거나 36개월 자료가 부족해 전체 기간 피크·저점을 확정하지 않습니다.")
    st.dataframe(pd.DataFrame(summary["monthly"]),hide_index=True)
    st.dataframe(pd.DataFrame(summary["yearly"]),hide_index=True)
    st.caption(summary["note"])


def records_view(session,rows,key):
    rows=apply_reviews(rows,session)
    search=st.text_input("자료 검색",key="filter_"+key,placeholder="브랜드·문구·검색어로 검색")
    kind=st.multiselect("자료 종류",list(dict.fromkeys(r["kind"] for r in rows)),key="kinds_"+key)
    states=st.multiselect("확인 상태",["포함","확인 필요","제외"],default=["포함","확인 필요"],key="states_"+key)
    filtered=[r for r in rows if (not search or search.casefold() in str(r).casefold()) and (not kind or r["kind"] in kind) and r["review"] in states]
    st.caption(f"필터 결과 {len(filtered)}건 / 중복 제거 후 {len(rows)}건 · 제외 자료도 이력에 남습니다.")
    table=[{"종류":r["kind"],"브랜드":r["brand"],"문구":r["text"][:160],"확인 상태":r["review"],"출처":r["source_url"]} for r in filtered]
    st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
    if not filtered: return
    page=st.number_input("자료 페이지 (20개씩)",min_value=1,max_value=max(1,math.ceil(len(filtered)/20)),value=1,key="page_"+key)
    for r in filtered[(page-1)*20:page*20]:
        with st.expander(r["kind"]+" · "+r["brand"]+" · "+r["text"][:55]):
            st.write(r["text"])
            if r["source_url"].startswith(("https://","http://")): st.link_button("원문 열기",r["source_url"])
            st.caption("수집 시각: "+r["collected_at"]+" · "+r.get("review_reason",""))
            for field in ("note","coverage"):
                if r.get(field): st.caption(r[field])
            labels={"pc":"PC 검색량","mobile":"모바일 검색량","keyword":"조회어","followers":"팔로워","post_count":"게시물 수","subscribers":"구독자","videos":"영상 수","published_at":"게시일","landing_url":"연결 페이지","format":"형식","cta":"CTA","start_date":"시작일","running_days":"관측 운영일수","placements":"노출 지면"}
            metadata=[{"항목":label,"내용":str(r[field]) if r[field] is not None else "미제공"} for field,label in labels.items() if field in r]
            if metadata: st.dataframe(pd.DataFrame(metadata),hide_index=True)
            for warning in r.get("warnings",[]): st.warning(warning)
            if r.get("links"):
                st.dataframe(pd.DataFrame(r["links"]).rename(columns={"text":"링크 문구","url":"연결 URL"}),hide_index=True)
            state=st.selectbox("관련 자료 확인",["포함","확인 필요","제외"],index=["포함","확인 필요","제외"].index(r["review"]),key="review_"+key+r["id"])
            if state!=r["review"]:
                session.setdefault("reviews",{})[r["id"]]=state
                session.pop("synthesis_result",None)
                session["synthesis_status"]="미실행"
                for export_key in list(session):
                    if "_export_" in export_key: session.pop(export_key)
                save_inputs(session)
                st.rerun()
            if r.get("assets") and st.checkbox("저장된 원본 미리보기",key="preview_"+key+r["id"]):
                for asset in r["assets"]:
                    data=read_bytes(asset)
                    if data is None: st.caption("원본 파일 없음 — 수집을 다시 실행하세요.")
                    elif asset["filename"].endswith(".mp4"): st.video(data)
                    else: st.image(data)


def render(session,stage):
    st.subheader(LABELS[stage])
    if pending(session,stage): return
    if stage!="synthesis":
        session[stage+"_force"]=st.checkbox("이 탭 새로 수집 (24시간 캐시 무시)",value=False,key="fresh_"+stage)
    if stage=="synthesis":
        rows=all_records(session)
        if not rows:
            st.info("자료를 수집한 뒤 필요한 자료를 선택하세요.")
            return
        records_view(session,rows,"all")
        eligible={r["id"]:r for r in rows if r["review"]!="제외"}
        selected=st.multiselect("근거 요약에 사용할 자료 (최대 20개)",list(eligible),
            default=[rid for rid in session.get("selected_records",[]) if rid in eligible],max_selections=20,
            format_func=lambda rid:eligible[rid]["kind"]+" · "+eligible[rid]["text"][:70],key="summary_selection")
        if selected!=session.get("selected_records",[]):
            session.pop("synthesis_result",None)
            session["synthesis_status"]="미실행"
            for k in list(session):
                if k.startswith(("synthesis_export_","collection_export_")): session.pop(k)
        session["selected_records"]=selected
        save_inputs(session)
        st.caption("선택한 원문만 요약합니다. 효과·타깃·포지셔닝·전략 추천은 생성하지 않습니다.")
    if st.button("선택 자료 근거 요약" if stage=="synthesis" else LABELS[stage]+" 수집",type="primary",key="btn_start_"+stage,
                 disabled=stage=="synthesis" and not session.get("selected_records")):
        start(session,stage,lambda snap:run_stage(stage,snap),{k:session.get(k) for k in INPUT_FIELDS})
    result=session.get(stage+"_result")
    if not result: return
    if result.get("schema_version")!=2:
        st.info("이전 버전 자료입니다. 새 수집을 실행하면 팩트 중심 형식으로 표시됩니다. 기존 파일은 이력에 남아 있습니다.")
        return
    if result.get("sample_sources"): st.warning("SAMPLE — 실제 수집 자료가 아닙니다.")
    parts=result.get("parts",{})
    if parts:
        st.dataframe(pd.DataFrame([{"수집 대상":p["label"],"상태":p["state"],"안내":p.get("message","")} for p in parts.values()]),hide_index=True)
    if result.get("changes"):
        with st.expander("이전 수집과 달라진 자료"):
            st.dataframe(pd.DataFrame(result["changes"]),hide_index=True)
    if stage!="synthesis":
        if st.button("이 탭 미수집·실패 항목 재시도",key="retry_"+stage):
            start(session,stage,lambda snap:run_stage(stage,snap,True),{"retry":True,"old":result.get("collected_at"),"inputs":{k:session.get(k) for k in INPUT_FIELDS}})
        if stage=="market": trends(result)
        records_view(session,result.get("records",[]),stage)
    else:
        summary=result.get("summary",{})
        if summary.get("status"): st.info(summary.get("message","요약 근거 부족"))
        else:
            st.write(summary.get("insight",""))
            for quote in summary.get("evidence",[]): st.write("원문 근거: "+quote)
            for source in summary.get("source",[]):
                if source.startswith(("https://","http://")): st.link_button("요약 출처",source)
            st.caption("근거 검증 수준: "+summary.get("confidence","미제공"))
    export_buttons(session,stage,result)


def unified_downloads(session):
    if not any(session.get(s+"_result",{}).get("schema_version")==2 for s in LABELS): return
    with st.expander("전체 자료 통합 다운로드"):
        st.caption("모든 탭의 수집 자료·확인 상태·검색 추이·원본을 묶습니다. 미확인·제외 여부를 함께 기록합니다.")
        export_buttons(session,"collection",combined(session))
