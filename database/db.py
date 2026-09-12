"""SQLite 연결 및 CRUD — analysis_session / function_run 2단 구조 (PRD §6-1·§13·§18).

Phase 0~1 스켈레톤 단계에서는 데모/이력 화면이 동작하는 정도로만 구현합니다.
멀티유저 동시성 락(§18)은 이후 Phase 4에서 추가합니다.
"""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from config.settings import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_session (
    id TEXT PRIMARY KEY,
    brand_name TEXT NOT NULL,
    category TEXT,
    competitors_json TEXT,
    target_status TEXT DEFAULT 'not_set',
    recommended_target TEXT,
    confirmed_target TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS function_run (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    function_type TEXT NOT NULL,        -- market / target / brand / creative / synthesis
    status TEXT NOT NULL,               -- 완료 / 부분 실패 / 취소 / 전체 실패
    result_json TEXT,
    estimated_cost REAL DEFAULT 0,
    actual_cost REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES analysis_session (id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)  # 매 연결마다 idempotent하게 스키마 보장 (page 단위 실행 대비)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn():
        pass  # get_conn()이 이미 스키마를 보장하므로 명시적 초기화 호출용으로만 남겨둠


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(brand_name: str, category: str | None, competitors: list[str]) -> str:
    session_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO analysis_session (id, brand_name, category, competitors_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, brand_name, category, json.dumps(competitors, ensure_ascii=False), _now()),
        )
    return session_id


def update_target(session_id: str, *, status: str, recommended: str | None = None, confirmed: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE analysis_session SET target_status=?, "
            "recommended_target=COALESCE(?, recommended_target), "
            "confirmed_target=COALESCE(?, confirmed_target) WHERE id=?",
            (status, recommended, confirmed, session_id),
        )


def save_function_run(session_id: str, function_type: str, status: str, result: dict,
                       estimated_cost: float = 0.0, actual_cost: float = 0.0) -> str:
    run_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO function_run (id, session_id, function_type, status, result_json, "
            "estimated_cost, actual_cost, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, session_id, function_type, status, json.dumps(result, ensure_ascii=False),
             estimated_cost, actual_cost, _now()),
        )
    return run_id


def list_sessions(limit: int = 20) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM analysis_session ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()


def list_function_runs(session_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM function_run WHERE session_id=? ORDER BY created_at DESC", (session_id,)
        )
        return cur.fetchall()
