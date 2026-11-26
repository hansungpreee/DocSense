"""SQLite 저장소. app/services.py의 메모리 Store와 메서드 이름·인자·반환 형태가 같다.

    store = SqliteStore("data/db/docsense.sqlite3", services.taxonomy())

- 스키마는 같은 폴더의 schema.sql (docs/db_schema.md 참고).
- result_json에는 엔진 결과를 그대로 두고, 담당자 결정은 class_proposals에만 쓴다.
  get()·list_history()가 결정 값을 결과에 덮어서 돌려주므로 화면이 받는 값은 메모리 Store와 같다.
- NEW 코드 발급기(allocator)는 시작할 때 class_proposals에서 복원해 재시작해도 번호가 이어진다.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from src.engine.guardrail import NewCodeAllocator, _norm
from src.engine.taxonomy import Taxonomy

SCHEMA = Path(__file__).with_name("schema.sql")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SqliteStore:
    def __init__(self, path: str | Path, tax: Taxonomy):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # Streamlit 세션 여러 개가 연결 하나를 같이 쓴다
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.allocator = NewCodeAllocator.from_taxonomy(tax)
        # 번호는 전체에서 복원해 재사용하지 않고, 이름 → 번호는 결정 안 된 제안만 (결정된 이름이 다시 나오면 새 번호)
        for row in self._db.execute("SELECT new_code, proposed_name, decision FROM class_proposals"):
            self.allocator.taken.add(row["new_code"])
            if row["proposed_name"] and row["decision"] is None:
                self.allocator.by_name[_norm(row["proposed_name"])] = row["new_code"]

    # 저장·조회 -----------------------------------------------------------------
    def save_result(self, result: dict) -> int:
        status = result.get("status")
        new_code = result.get("minor_code") if status == "pending_review" else None
        proposal = result.get("new_class") or {}
        now = _now()
        with self._lock, self._db:  # 제안과 결과를 한 트랜잭션으로
            if new_code:
                self._db.execute(
                    "INSERT OR IGNORE INTO class_proposals (new_code, proposed_name, proposed_major, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (new_code, proposal.get("proposed_name"), proposal.get("proposed_major"), now),
                )
            cur = self._db.execute(
                "INSERT INTO classifications"
                " (file_hash, result_json, prompt_version, model, status, new_code, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result.get("file_hash"), json.dumps(result, ensure_ascii=False), result.get("prompt_version"),
                 result.get("model"), status, new_code, now),
            )
            return cur.lastrowid

    def get(self, result_id: int) -> dict | None:
        rows = self._select("WHERE c.id = ?", (result_id,))
        return rows[0] if rows else None

    def find_cached(self, file_hash: str, prompt_ver: str, model: str) -> dict | None:
        """같은 파일·같은 프롬프트·같은 모델로 성공한 결과가 있으면 돌려준다 (API 재호출 방지)."""
        rows = self._select(
            "WHERE c.file_hash = ? AND c.prompt_version = ? AND c.model = ? AND c.status <> 'error'"
            " ORDER BY c.id DESC LIMIT 1",
            (file_hash, prompt_ver, model),
        )
        return rows[0] if rows else None

    def list_history(self) -> list[dict]:
        return self._select("ORDER BY c.id DESC")

    def list_pending(self) -> list[dict]:
        return self._select("WHERE c.status = 'pending_review' ORDER BY c.id")

    # 승인 대기: NEW 코드 단위로 묶어서 결정한다 ---------------------------------------
    def list_pending_groups(self) -> list[dict]:
        groups: dict[str, dict] = {}
        for r in self.list_pending():
            g = groups.setdefault(
                r["minor_code"],
                {"code": r["minor_code"], "proposal": r.get("new_class") or {}, "docs": []},
            )
            g["docs"].append(r)
        return list(groups.values())

    def decide_group(self, new_code: str, decision: str, final_code: str, final_name: str, final_major: str) -> int:
        """decision: approved / edited / rejected. 같은 NEW 코드의 승인 대기 문서 전체에 적용하고 건수를 돌려준다."""
        if decision in ("approved", "edited") and not final_name:
            raise ValueError("분류명이 비어 있으면 승인할 수 없습니다.")
        with self._lock, self._db:
            self._db.execute(
                "UPDATE class_proposals SET decision = ?, final_code = ?, final_name = ?, final_major = ?,"
                " decided_at = ? WHERE new_code = ?",
                (decision, final_code, final_name, final_major, _now(), new_code),
            )
            cur = self._db.execute(
                "UPDATE classifications SET status = 'confirmed' WHERE new_code = ? AND status = 'pending_review'",
                (new_code,),
            )
            # 결정된 제안명이 다시 나오면 새 번호를 받도록 이름 → 번호 연결을 끊는다 (프론트와 정한 것 2번)
            for name in [k for k, v in self.allocator.by_name.items() if v == new_code]:
                del self.allocator.by_name[name]
            # taxonomy.yaml 추가(FR-10)는 호출하는 쪽이 먼저 add_minor()로 하고, 받은 정식 코드를 final_code로 넘긴다.
            return cur.rowcount

    # 내부 -----------------------------------------------------------------------
    def _select(self, tail: str, params: tuple = ()) -> list[dict]:
        sql = (
            "SELECT c.id, c.result_json, c.status, c.created_at, p.decision, p.final_code, p.final_name, p.final_major"
            " FROM classifications c LEFT JOIN class_proposals p ON p.new_code = c.new_code " + tail
        )
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        return [self._to_result(row) for row in rows]

    @staticmethod
    def _to_result(row: sqlite3.Row) -> dict:
        r = json.loads(row["result_json"]) | {"id": row["id"], "created_at": row["created_at"], "status": row["status"]}
        if row["decision"] and row["status"] == "confirmed":  # 담당자가 결정한 문서는 결정 값으로 보여 준다
            r.update(minor_code=row["final_code"], minor_name=row["final_name"], major=row["final_major"])
        return r
