"""기능별 실행 결과 영속화와 동일 세션 복원."""
import hashlib
import json
from datetime import datetime, timezone
from database.db import save_function_run, list_function_runs

FUNCTIONS = ("market", "brand", "creative", "synthesis", "collection", "trend", "volume", "news", "website", "search_capture", "meta", "instagram", "youtube")


def persist_result(session, function, result):
    if function not in FUNCTIONS:
        raise ValueError("Unknown function")
    result.setdefault("collected_at", datetime.now(timezone.utc).isoformat())
    run_id = save_function_run(session["id"], function, result["status"], result)
    session[function + "_result"] = result
    session[function + "_status"] = result["status"]
    session[function + "_run_id"] = run_id
    for key in list(session):
        if key.startswith(function + "_export_") or (function != "collection" and key.startswith("collection_export_")):
            del session[key]
    if function not in ("synthesis", "collection"):
        session.pop("synthesis_result", None)
        session["synthesis_status"] = "미실행"
    return run_id


def restore_results(session):
    seen = set()
    for row in list_function_runs(session["id"]):
        f = row["function_type"]
        if f not in FUNCTIONS or f in seen:
            continue
        seen.add(f)
        try:
            result = json.loads(row["result_json"] or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(result, dict):
            continue
        session[f + "_result"] = result
        session[f + "_status"] = row["status"]
        session[f + "_run_id"] = row["id"]
    for f in FUNCTIONS:
        session.setdefault(f + "_status", "미실행")
    synthesis = session.get("synthesis_result", {})
    if synthesis and synthesis.get("input_signature") != input_signature(session):
        session.pop("synthesis_result", None)
        session["synthesis_status"] = "미실행"
    return session


def input_signature(session):
    payload = {f: session.get(f + "_result") for f in FUNCTIONS[:3]}
    payload["reviews"] = session.get("reviews", {})
    payload["selected_records"] = session.get("selected_records", [])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
