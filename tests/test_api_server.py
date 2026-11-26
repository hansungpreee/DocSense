"""업로드 검사 서버: 등급별 동작, 「기타」·미확정, 검사 실패, 출처 제한, HTTP 왕복 (실제 API 호출 없음)."""
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from urllib.parse import quote

import pytest

from src.api import server
from src.api.server import Handler, MockEngine, ResultCache, check, origin_allowed
from src.engine.security import load_grades
from src.engine.taxonomy import load_taxonomy


@pytest.fixture
def grades(tmp_path):
    p = tmp_path / "security_grades.yaml"
    p.write_text("FIN-03: 기밀\nHR-01: 대외비\nFIN-10: {grade: 사내한정, basis: 교부 문서}\nSAL-05: 공개\n", encoding="utf-8")
    return load_grades(p)


class FakeEngine:
    def __init__(self, grades, result=None, exc=None):
        self.grades, self.result, self.exc, self.seen = grades, result, exc, []
        self.tax, self.model, self.prompt_version = load_taxonomy(), "m1", "v1"

    def classify(self, path):
        self.seen.append(path.read_bytes())
        if self.exc:
            raise self.exc
        return self.result


@pytest.mark.parametrize("name,action,grade", [
    ("FIN-03_손익계산서.png", "block", "기밀"),
    ("HR-01_x.pdf", "confirm", "대외비"),
    ("FIN-10_x.jpg", "pass", "사내한정"),
    ("SAL-05_x.PNG", "pass", "공개"),
    ("HR-02_등급표에없음.png", "confirm", "대외비"),  # 미산정 → 최소 대외비
])
def test_actions_by_grade(grades, name, action, grade):
    r = check(b"img", name, MockEngine(grades))
    assert (r["status"], r["action"], r["handling_grade"]) == ("ok", action, grade)


def test_etc_and_unconfirmed_are_confirm(grades):
    etc = check(b"img", "회식사진.png", MockEngine(grades))
    assert etc["action"] == "confirm" and etc["minor_name"] == "기타" and etc["minor_code"] is None
    assert etc["grade_basis"] == "분류 체계 밖 문서, 담당자 확인 필요" and etc["security_grade"] is None
    assert etc["provisional"] is True
    low = check(b"img", "SAL-05_lowconf.png", MockEngine(grades))  # 공개라도 합산 미확정이면 대외비로 올린다
    assert (low["security_grade"], low["handling_grade"], low["action"], low["provisional"]) == ("공개", "대외비", "confirm", True)
    assert check(b"img", "FIN-03_x.png", MockEngine(grades))["provisional"] is False


def test_no_grade_table_means_confirm():
    assert check(b"img", "SAL-05_x.png", MockEngine({}))["action"] == "confirm"


@pytest.mark.parametrize("name,data", [("a.hwp", b"x"), ("noext", b"x"), ("a.png", b""),
                                       ("a.png", b"x" * (server.MAX_BYTES + 1))])
def test_rejects_without_calling_engine(grades, name, data):
    eng = FakeEngine(grades)
    r = check(data, name, eng)
    assert (r["status"], r["action"]) == ("error", "error") and eng.seen == []


def test_engine_failure_becomes_error_result(grades):
    class RateLimit(Exception):
        status_code = 429

    r = check(b"img", "a.png", FakeEngine(grades, exc=RateLimit("본문 sk-secret")))
    assert r["status"] == "error" and "429" in r["message"] and "sk-secret" not in r["message"]
    r = check(b"img", "a.png", FakeEngine(grades, result={"status": "error", "errors": ["x"]}))
    assert r["status"] == "error"


def test_real_engine_shape_passes_bytes(grades):
    eng = FakeEngine(grades, result={"status": "confirmed", "minor_code": "FIN-03", "minor_name": "손익계산서",
                                     "security_grade": "기밀", "grade_basis": "소분류 FIN-03 손익계산서의 기본 등급"})
    r = check(b"\x89PNG", "s.png", eng)
    assert eng.seen == [b"\x89PNG"] and r["action"] == "block" and r["grade_basis"].startswith("소분류 FIN-03")


FIN03 = {"status": "confirmed", "minor_code": "FIN-03", "minor_name": "손익계산서"}


def test_cache_reuses_code_and_reapplies_current_grades(grades, tmp_path):
    cache = ResultCache(tmp_path / "cache.json")
    eng = FakeEngine(grades, result=FIN03)
    first = check(b"same", "a.png", eng, cache)
    again = check(b"same", "다른이름.pdf", eng, cache)  # 파일명이 달라도 내용이 같으면 재사용
    assert len(eng.seen) == 1 and (first["cached"], again["cached"]) == (False, True)
    assert again["action"] == "block" and again["minor_name"] == "손익계산서"
    eng.grades = {"FIN-03": {"grade": "공개", "basis": None}}  # 등급표가 바뀌면 캐시 적중이어도 새 등급
    assert check(b"same", "a.png", eng, cache)["action"] == "pass" and len(eng.seen) == 1
    saved = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert [set(v) for v in saved.values()] == [{"minor_code", "model", "prompt_version", "checked_at"}]
    assert "same" not in json.dumps(saved) and "a.png" not in json.dumps(saved)
    assert ResultCache(tmp_path / "cache.json").items == saved  # 서버를 다시 켜도 남는다


def test_cache_misses_on_changed_file_or_setting(grades, tmp_path):
    cache = ResultCache(tmp_path / "cache.json")
    eng = FakeEngine(grades, result=FIN03)
    check(b"v1", "a.png", eng, cache)
    check(b"v1-edited", "a.png", eng, cache)
    eng.prompt_version = "v2"
    check(b"v1", "a.png", eng, cache)
    eng.prompt_version, eng.model = "v1", "m2"
    check(b"v1", "a.png", eng, cache)
    assert len(eng.seen) == 4


@pytest.mark.parametrize("result,exc", [
    ({"status": "pending_review", "minor_code": "NEW-01", "minor_name": "기타"}, None),  # 「기타」
    (FIN03 | {"cross_check": {"confirmed": False}}, None),  # 합산 미확정
    ({"status": "error", "errors": ["x"]}, None),  # 형식 오류 반복
    (None, TimeoutError()),  # 네트워크·시간 초과
])
def test_cache_skips_etc_unconfirmed_and_failures(grades, tmp_path, result, exc):
    cache = ResultCache(tmp_path / "cache.json")
    eng = FakeEngine(grades, result=result, exc=exc)
    first = check(b"x", "a.png", eng, cache)
    second = check(b"x", "a.png", eng, cache)
    assert cache.items == {} and len(eng.seen) == 2 and first["action"] != "pass"
    assert second.get("cached") in (None, False)


def test_broken_cache_file_starts_empty(tmp_path):
    (tmp_path / "cache.json").write_text("{깨짐", encoding="utf-8")
    assert ResultCache(tmp_path / "cache.json").items == {}


def test_origin_allowed():
    assert origin_allowed(None) and origin_allowed("chrome-extension://abcdef")
    assert not origin_allowed("https://chatgpt.com") and not origin_allowed("null")


@pytest.fixture
def live(grades, tmp_path, monkeypatch):
    monkeypatch.setattr(Handler, "engine", MockEngine(grades))
    log = tmp_path / "gate.log"
    server.GATE_LOG.handlers.clear()
    server.open_gate_log(log)
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", log
    httpd.shutdown()
    server.GATE_LOG.handlers.clear()


def post(url, body, headers):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_http_check_decision_and_log(live):
    base, log = live
    ext = {"Origin": "chrome-extension://abc"}
    code, r = post(base + "/check", b"img", ext | {"X-Filename": quote("FIN-03_손익계산서.png")})
    assert code == 200 and r["action"] == "block" and r["file"] == "FIN-03_손익계산서.png"
    code, _ = post(base + "/decision", json.dumps({"file": r["file"], "grade": "기밀", "choice": "cancel"}).encode(), ext)
    assert code == 200
    assert post(base + "/decision", b'{"choice": "maybe"}', ext)[0] == 400
    assert post(base + "/check", b"img", {"Origin": "https://chatgpt.com", "X-Filename": "a.png"})[0] == 403
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and "check\tFIN-03_손익계산서.png\tFIN-03\t기밀\tblock" in lines[0]
    assert lines[1].endswith("decision\tFIN-03_손익계산서.png\t-\t기밀\tcancel")
    with urllib.request.urlopen(base + "/health", timeout=5) as resp:
        assert json.loads(resp.read())["mock"] is True
