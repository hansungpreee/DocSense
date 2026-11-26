import json
import sqlite3
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"
H1, H2, H3 = "a" * 64, "b" * 64, "c" * 64
T = "2026-10-08T16:00:00"


def _db():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con


def _save(con, file_hash, status, new_code=None):
    con.execute(
        "INSERT INTO classifications (file_hash, result_json, prompt_version, model, status, new_code, created_at)"
        " VALUES (?, ?, 'v2', 'qwen3-vl-plus', ?, ?, ?)",
        (file_hash, json.dumps({"status": status}), status, new_code, T),
    )


def _pending_groups(con):
    rows = con.execute(
        "SELECT p.new_code, count(*) FROM class_proposals p JOIN classifications c USING (new_code)"
        " WHERE p.decision IS NULL AND c.status = 'pending_review' GROUP BY p.new_code"
    )
    return dict(rows.fetchall())


def test_one_new_code_groups_many_docs_and_decision_applies_to_all():
    con = _db()
    con.execute("INSERT INTO class_proposals (new_code, proposed_name, created_at) VALUES ('NEW-01', '출장정산서', ?)", (T,))
    _save(con, H1, "pending_review", "NEW-01")
    _save(con, H2, "pending_review", "NEW-01")
    _save(con, H3, "confirmed")
    assert _pending_groups(con) == {"NEW-01": 2}

    # 반려: 기존 코드로 재지정. 묶인 문서 전체를 한 번에 확정
    con.execute(
        "UPDATE class_proposals SET decision = 'rejected', final_code = 'FIN-05', final_name = '주요경비지출명세서',"
        " final_major = '재무/회계', decided_at = ? WHERE new_code = 'NEW-01'", (T,)
    )
    con.execute("UPDATE classifications SET status = 'confirmed' WHERE new_code = 'NEW-01' AND status = 'pending_review'")
    assert _pending_groups(con) == {}
    finals = con.execute(
        "SELECT p.final_code FROM classifications c JOIN class_proposals p USING (new_code) WHERE c.file_hash IN (?, ?)",
        (H1, H2),
    ).fetchall()
    assert finals == [("FIN-05",), ("FIN-05",)]


def test_cache_lookup_skips_error_results():
    con = _db()
    _save(con, H1, "confirmed")
    _save(con, H1, "error")
    row = con.execute(
        "SELECT status FROM classifications WHERE file_hash = ? AND prompt_version = 'v2' AND model = 'qwen3-vl-plus'"
        " AND status <> 'error' ORDER BY id DESC LIMIT 1", (H1,)
    ).fetchone()
    assert row == ("confirmed",)


@pytest.mark.parametrize("sql", [
    # 「기타」 문서인데 NEW 코드가 없음
    "INSERT INTO classifications (file_hash, result_json, prompt_version, model, status, created_at)"
    f" VALUES ('{H1}', '{{}}', 'v2', 'm', 'pending_review', '{T}')",
    # 없는 NEW 코드를 가리킴
    "INSERT INTO classifications (file_hash, result_json, prompt_version, model, status, new_code, created_at)"
    f" VALUES ('{H1}', '{{}}', 'v2', 'm', 'pending_review', 'NEW-99', '{T}')",
    # 결정했는데 결정 시각이 없음
    f"INSERT INTO class_proposals (new_code, decision, final_code, created_at) VALUES ('NEW-02', 'approved', 'NEW-02', '{T}')",
    # 허용하지 않는 상태 값
    "INSERT INTO classifications (file_hash, result_json, prompt_version, model, status, created_at)"
    f" VALUES ('{H1}', '{{}}', 'v2', 'm', 'done', '{T}')",
])
def test_schema_rejects_inconsistent_rows(sql):
    with pytest.raises(sqlite3.IntegrityError):
        _db().execute(sql)


def test_cache_lookup_after_decision_returns_confirmed_final_code():
    # 프론트 검토 0번: NEW-01 반려 후 같은 파일을 다시 올리면 확정 값이 재사용되어야 한다
    con = _db()
    con.execute("INSERT INTO class_proposals (new_code, proposed_name, created_at) VALUES ('NEW-01', '출장정산서', ?)", (T,))
    _save(con, H1, "pending_review", "NEW-01")
    con.execute(
        "UPDATE class_proposals SET decision = 'rejected', final_code = 'FIN-05', final_name = '주요경비지출명세서',"
        " final_major = '재무/회계', decided_at = ? WHERE new_code = 'NEW-01'", (T,)
    )
    con.execute("UPDATE classifications SET status = 'confirmed' WHERE new_code = 'NEW-01' AND status = 'pending_review'")
    row = con.execute(
        "SELECT c.status, p.final_code FROM classifications c"
        " LEFT JOIN class_proposals p ON p.new_code = c.new_code AND p.decision IS NOT NULL"
        " WHERE c.file_hash = ? AND c.prompt_version = 'v2' AND c.model = 'qwen3-vl-plus' AND c.status <> 'error'"
        " ORDER BY c.id DESC LIMIT 1", (H1,)
    ).fetchone()
    assert row == ("confirmed", "FIN-05")
    assert _pending_groups(con) == {}  # 확정되지 않고 남는 행이 없음
