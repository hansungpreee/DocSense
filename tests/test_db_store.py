"""SQLite 저장소(데모가 쓰는 유일한 저장소)가 화면이 기대하는 동작을 하는지 시나리오로 확인한다."""

import pytest

H1, H2, H3 = "a" * 64, "b" * 64, "c" * 64


def _result(file_hash, status, code, name=None):
    r = {"file": f"{file_hash[0]}.png", "file_hash": file_hash, "status": status, "minor_code": code,
         "minor_name": name or code, "major": "재무/회계", "prompt_version": "v2", "model": "m", "new_class": None}
    if status == "pending_review":
        r["new_class"] = {"proposed_name": name, "proposed_major": "재무/회계", "reason": "", "trigger": "etc"}
    return r


@pytest.fixture
def store(tmp_path):
    from src.db.store import SqliteStore
    from src.engine.taxonomy import load_taxonomy

    return SqliteStore(tmp_path / "docsense.sqlite3", load_taxonomy())


def test_store_scenario(store):
    ok_id = store.save_result(_result(H1, "confirmed", "FIN-03"))
    store.save_result(_result(H1, "error", None))
    assert store.find_cached(H1, "v2", "m")["id"] == ok_id  # 오류 결과는 캐시로 쓰지 않음
    assert store.find_cached(H1, "v1", "m") is None

    code = store.allocator.assign("출장정산서")
    assert store.allocator.assign("출장 정산서") == code  # 같은 제안명(공백 무시)은 같은 NEW 코드
    a = store.save_result(_result(H2, "pending_review", code, "출장정산서"))
    b = store.save_result(_result(H3, "pending_review", code, "출장정산서"))

    assert [r["id"] for r in store.list_pending()] == [a, b]
    groups = store.list_pending_groups()
    assert len(groups) == 1 and groups[0]["code"] == code and len(groups[0]["docs"]) == 2
    assert groups[0]["proposal"]["proposed_name"] == "출장정산서"

    with pytest.raises(ValueError):
        store.decide_group(code, "approved", code, "", "재무/회계")
    assert store.decide_group(code, "rejected", "FIN-05", "주요경비지출명세서", "재무/회계") == 2

    assert store.list_pending() == [] and store.list_pending_groups() == []
    decided = store.get(a)
    assert (decided["status"], decided["minor_code"], decided["minor_name"]) == ("confirmed", "FIN-05", "주요경비지출명세서")
    assert [r["id"] for r in store.list_history()] == [b, a, 2, ok_id]  # 최신순
    assert store.get(999) is None

    # 프론트 검토 0번: 결정 후 같은 파일을 다시 올리면 확정 값이 재사용되고, 확정되지 않는 행이 생기지 않는다
    cached = store.find_cached(H2, "v2", "m")
    assert (cached["status"], cached["minor_code"]) == ("confirmed", "FIN-05")
    store.save_result({k: v for k, v in cached.items() if k not in ("id", "created_at")})  # services.classify와 같은 복사
    assert store.list_pending() == []


def test_sqlite_keeps_history_and_new_codes_after_restart(tmp_path):
    from src.db.store import SqliteStore
    from src.engine.taxonomy import load_taxonomy

    tax, path = load_taxonomy(), tmp_path / "docsense.sqlite3"
    first = SqliteStore(path, tax)
    code = first.allocator.assign("출장정산서")
    first.save_result(_result(H2, "pending_review", code, "출장정산서"))

    again = SqliteStore(path, tax)  # 서버를 다시 켠 상황
    assert len(again.list_history()) == 1 and again.list_pending_groups()[0]["code"] == code
    assert again.allocator.assign("출장 정산서") == code  # 같은 이름은 이어서 같은 번호
    assert again.allocator.assign("회의록") != code  # 새 이름은 다음 번호 (이미 쓴 번호와 겹치지 않음)


def test_sqlite_gives_new_code_when_decided_name_appears_again(tmp_path):
    # 프론트와 정한 것 2번: 결정이 끝난 제안명이 다시 나오면 새 번호
    from src.db.store import SqliteStore
    from src.engine.taxonomy import load_taxonomy

    tax, path = load_taxonomy(), tmp_path / "docsense.sqlite3"
    store = SqliteStore(path, tax)
    first = store.allocator.assign("출장정산서")
    store.save_result(_result(H2, "pending_review", first, "출장정산서"))
    store.decide_group(first, "rejected", "FIN-05", "주요경비지출명세서", "재무/회계")

    second = store.allocator.assign("출장정산서")
    assert second != first  # 결정된 코드에 붙지 않음
    store.save_result(_result(H3, "pending_review", second, "출장정산서"))
    assert [g["code"] for g in store.list_pending_groups()] == [second]  # 승인 대기에 다시 보임

    again = SqliteStore(path, tax)  # 재시작해도 같은 규칙: 대기 중인 second는 이어 쓰고, 결정된 first는 안 씀
    assert again.allocator.assign("출장 정산서") == second
    assert first in again.allocator.taken
