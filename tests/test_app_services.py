"""데모 services.py 테스트 (Streamlit·API 없이). 실행: python -m pytest tests -q"""
import io
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import services  # noqa: E402
from src.db.store import SqliteStore  # noqa: E402
from src.engine.classify import Classifier  # noqa: E402


def png_bytes(tag: str = "") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (124, 175), "white").save(buf, "PNG")
    return buf.getvalue() + tag.encode()  # 꼬리 바이트로 내용(해시)을 다르게 만든다


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(services, "DB_DIR", tmp_path / "db")  # open_store()가 실제 data/db/에 파일을 만들지 않게
    monkeypatch.setattr(services, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(services.time, "sleep", lambda s: None)
    monkeypatch.setenv("DEMO_MOCK", "1")
    return SqliteStore(":memory:", services.taxonomy())


def classify_name(store, name, tag="", on_wait=None):
    path, digest = services.save_upload(name, png_bytes(tag or name))
    return store.get(store.save_result(services.classify(path, digest, store, on_wait)))


# NEW-xx 번호는 저장소의 발급기 하나에서만 나온다 ---------------------------------------
def test_numbering_shared_by_store(env):
    a = classify_name(env, "출장정산서.png")
    b = classify_name(env, "활동보고서.png")
    c = classify_name(env, "출장정산서.png", tag="다른 파일")
    assert (a["minor_code"], b["minor_code"], c["minor_code"]) == ("NEW-01", "NEW-02", "NEW-01")


def test_new_store_restarts_numbering(env):
    classify_name(env, "출장정산서.png")
    fresh = SqliteStore(":memory:", services.taxonomy())
    assert classify_name(fresh, "활동보고서.png", tag="x")["minor_code"] == "NEW-01"


# 데모 저장소는 services.open_store() 한 곳에서만 만든다 (SQLite, MOCK은 파일을 따로) ------------------
def test_open_store_uses_one_file_for_mock_and_real(env, monkeypatch):
    services.open_store("HS1001")
    monkeypatch.setenv("DEMO_MOCK", "0")
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    services.open_store("HS1001")  # 모드를 바꿔 다시 켜도 같은 파일 (이력이 사라져 보이지 않게)
    assert "docsense_HS1001.sqlite3" in [f.name for f in services.DB_DIR.iterdir()]
    assert not [f for f in services.DB_DIR.iterdir() if "mock" in f.name and f.suffix == ".sqlite3"]


def test_open_store_adopts_legacy_mock_file(env):
    legacy = services.DB_DIR / "docsense_mock_HS1001.sqlite3"
    services.DB_DIR.mkdir(parents=True, exist_ok=True)
    old = services.SqliteStore(legacy, services.taxonomy())
    rid = old.save_result({"status": "error", "errors": ["x"], "file": "a.png", "file_hash": "0" * 64,
                           "prompt_version": "v1", "model": "m"})
    assert [r["id"] for r in services.open_store("HS1001").list_history()] == [rid]  # 예전 MOCK 이력을 이어 받는다


def test_star_toggle_persists_per_employee(env):
    assert services.starred("HS1001") == set()
    services.toggle_star("HS1001", 3)
    services.toggle_star("HS1001", 5)
    services.toggle_star("HS1001", 3)  # 한 번 더 누르면 취소
    assert services.starred("HS1001") == {5} and services.starred("HS1002") == set()


def test_open_store_keeps_history_after_restart(env):
    first = services.open_store()
    a = classify_name(first, "출장정산서.png")
    again = services.open_store()  # 서버를 다시 켠 상황
    assert [r["id"] for r in again.list_history()] == [a["id"]]
    assert classify_name(again, "출장 정산서.png", tag="다른 파일")["minor_code"] == a["minor_code"]  # 번호 이어 씀


# 같은 파일은 다시 호출하지 않는다 ---------------------------------------------------------
def test_cache_by_hash(env):
    a = classify_name(env, "FIN-03_손익계산서_001.png", tag="same")
    b = classify_name(env, "FIN-03_손익계산서_001.png", tag="same")
    assert not a.get("cached") and b["cached"] and b["minor_code"] == "FIN-03" and b["id"] != a["id"]


# 오류가 나도 화면이 깨지지 않는다 -----------------------------------------------------------
class ApiError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.status_code = code


class FakeEngine:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = 0

    def classify(self, path, allocator=None):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return {"status": "confirmed", "minor_code": "FIN-03", "major": "재무/회계", "minor_name": "손익계산서",
                "confidence": 0.9, "reasons": ["x"], "evidence": [], "prompt_version": "v1", "model": "fake"}


@pytest.fixture
def real_mode(env, monkeypatch):
    monkeypatch.setenv("DEMO_MOCK", "0")
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    return env


def test_auth_error_becomes_result(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([ApiError(401)]))
    r = classify_name(real_mode, "a.png")
    assert r["status"] == "error" and "401" in r["errors"][0]


def test_rate_limit_retried(real_mode, monkeypatch):
    eng = FakeEngine([ApiError(429), ApiError(429)])
    monkeypatch.setattr(services, "_classifier", eng)
    r = classify_name(real_mode, "b.png")
    assert r["minor_code"] == "FIN-03" and eng.calls == 3


def test_rate_limit_gives_up(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([ApiError(429)] * 10))
    r = classify_name(real_mode, "c.png")
    assert r["status"] == "error" and "429" in r["errors"][0]


def test_rate_limit_notifies_each_wait(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([ApiError(429), ApiError(429)]))
    notes = []
    r = classify_name(real_mode, "g.png", on_wait=notes.append)
    assert r["minor_code"] == "FIN-03"
    assert notes == ["서버가 바쁩니다. 잠시만 기다려 주세요 (재시도 1/3)", "서버가 바쁩니다. 잠시만 기다려 주세요 (재시도 2/3)"]


def test_rate_limit_gives_up_after_three_notices(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([ApiError(429)] * 10))
    notes = []
    r = classify_name(real_mode, "h.png", on_wait=notes.append)
    assert r["status"] == "error" and "429" in r["errors"][0]  # 재시도를 다 쓰면 기존 오류 문구로 이어진다
    assert len(notes) == 3 and notes[-1].endswith("(재시도 3/3)")


def test_no_wait_notice_for_other_errors(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([ApiError(401)]))
    notes = []
    r = classify_name(real_mode, "i.png", on_wait=notes.append)
    assert r["status"] == "error" and notes == []


def test_batch_continues_after_failure(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([RuntimeError("boom")]))
    first = classify_name(real_mode, "d.png")
    second = classify_name(real_mode, "e.png")
    assert first["status"] == "error" and second["minor_code"] == "FIN-03"


def test_error_not_cached(real_mode, monkeypatch):
    monkeypatch.setattr(services, "_classifier", FakeEngine([ApiError(500)]))
    classify_name(real_mode, "f.png", tag="same")
    again = classify_name(real_mode, "f.png", tag="same")
    assert again["minor_code"] == "FIN-03" and not again.get("cached")


# 승인은 NEW 코드 단위로 ---------------------------------------------------------------------
def test_group_decision(env):
    for i in range(3):
        classify_name(env, "출장정산서.png", tag=str(i))
    classify_name(env, "활동보고서.png")
    groups = env.list_pending_groups()
    assert [(g["code"], len(g["docs"])) for g in groups] == [("NEW-01", 3), ("NEW-02", 1)]

    n = env.decide_group("NEW-01", "edited", "NEW-01", "출장비 정산서", "재무/회계")
    assert n == 3
    assert all(r["minor_name"] == "출장비 정산서" for r in env.list_history() if r["minor_code"] == "NEW-01")
    assert [g["code"] for g in env.list_pending_groups()] == ["NEW-02"]

    env.decide_group("NEW-02", "rejected", "SAL-02", "거래처 방문일지", "영업/제안")
    assert env.list_pending_groups() == []


def test_approve_requires_name(env):
    classify_name(env, "출장정산서.png")
    with pytest.raises(ValueError):
        env.decide_group("NEW-01", "approved", "NEW-01", "", "재무/회계")


# 미리보기 캐시 -----------------------------------------------------------------------------
def test_preview_cached(env):
    path, _ = services.save_upload("x.png", png_bytes("p"))
    assert services.load_preview_pages(path) is services.load_preview_pages(path)


# 분류 체계 파일이 바뀌면 엔진이 다시 읽는다 ---------------------------------------------------
def test_engine_reloads_taxonomy(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    src = (ROOT / "config" / "taxonomy.yaml").read_text(encoding="utf-8")
    yml = tmp_path / "taxonomy.yaml"
    yml.write_text(src, encoding="utf-8")
    clf = Classifier(taxonomy_path=yml, client=SimpleNamespace())
    assert not clf.tax.is_valid_code("NEW-01")

    added = src + (
        '\n  - major: "재무/회계 추가"\n    items:\n      - minor_code: "NEW-01"\n'
        '        minor_name: "출장정산서"\n        definition: "출장 경비 정산 문서"\n'
    )
    yml.write_text(added, encoding="utf-8")
    import os
    os.utime(yml, (clf._tax_mtime + 5, clf._tax_mtime + 5))
    assert clf.refresh_taxonomy() and clf.tax.is_valid_code("NEW-01")
    assert "NEW-01" in clf.allocator.taken


# 모델이 쓴 근거 문장은 마크다운으로 해석하지 않는다 -------------------------------------------
def test_plain_escapes_markdown_symbols():
    p = services.plain
    assert p("**굵게** # 제목") == r"\*\*굵게\*\* \# 제목"
    assert p("[링크](http://x) `코드` $x$ :red[빨강]") == r"\[링크\]\(http\://x\) \`코드\` \$x\$ \:red\[빨강\]"
    assert p("첫 줄\n- 둘째 줄\n\n| 표 |") == r"첫 줄 \- 둘째 줄 \| 표 \|"  # 줄바꿈은 공백으로 (목록·표가 새로 생기지 않음)
    assert p("손익계산서 제목") == "손익계산서 제목"  # 기호가 없으면 그대로
    assert p(None) == ""


# MOCK 모드는 샘플 4종으로 경우를 고른다 ------------------------------------------------
def test_mock_routes_to_samples(env):
    normal = classify_name(env, "FIN-03_손익계산서_001.png")
    low = classify_name(env, "LEG-02_표준임대차계약서_006_hard.png")
    etc = classify_name(env, "출장정산서.png")

    assert (normal["minor_code"], normal["status"], normal["new_class"]) == ("FIN-03", "confirmed", None)
    assert all(e["page"] == 1 for e in normal["evidence"])  # 1페이지 이미지에는 1페이지 근거만

    assert low["status"] == "pending_review" and low["predicted_code"] == "LEG-02"
    assert low["new_class"]["trigger"] == "low_confidence" and low["new_class"]["proposed_name"] is None
    assert low["major"] == "법무/총무" and "LEG-02" in low["new_class"]["reason"]

    assert etc["minor_code"].startswith("NEW-") and etc["new_class"]["proposed_name"] == "출장정산서"


def test_mock_low_confidence_gets_own_code(env):
    a = classify_name(env, "LEG-02_a_hard.png")
    b = classify_name(env, "LEG-02_b_hard.png")
    assert a["minor_code"] != b["minor_code"]  # 제안명이 없으면 서로 다른 문서를 한 묶음으로 묶지 않는다


def test_mock_broken_file_is_error(env):
    path, digest = services.save_upload("깨진문서.png", b"not an image")
    r = services.classify(path, digest, env)
    assert r["status"] == "error" and r["errors"][0].startswith("이미지나 PDF로 읽을 수 없는")  # 예외 이름 없이 안내 문구만
    assert services.result_row(r | {"id": 1})["대분류"] == ""  # 표에 None 대신 빈칸


# 한 문서의 여러 페이지 이미지 묶어 올리기 ---------------------------------------------------
def classify_pages(store, names, datas):
    path, digest = services.save_pages(names, datas)
    return store.get(store.save_result(services.classify(path, digest, store)))


def test_pages_saved_in_upload_order_as_one_document(env):
    datas = [png_bytes("1쪽"), png_bytes("2쪽"), png_bytes("3쪽")]
    path, _ = services.save_pages(["스캔_a.png", "스캔_b.png", "스캔_c.png"], datas)
    files = sorted(services.UPLOAD_DIR.iterdir())
    assert [f.name.split("_", 1)[1] for f in files] == ["스캔_a_p1.png", "스캔_a_p2.png", "스캔_a_p3.png"]
    assert [f.read_bytes() for f in files] == datas  # 올린 순서 = 페이지 순서
    assert len(services.load_preview_pages(path)) == 3  # 엔진의 _p1 규칙으로 3쪽이 한 문서로 읽힌다

    r = classify_pages(env, ["FIN-09_감사보고서_007_p1.png", "x.png", "y.png"], datas)
    assert (r["minor_code"], r["file"]) == ("FIN-09", "FIN-09_감사보고서_007_p1.png")  # 데이터셋 이름의 _p1은 한 번만
    assert {e["page"] for e in r["evidence"]} == {1, 2, 3}  # 다중 페이지 샘플


def test_pages_cache_key_covers_every_page_and_order(env):
    p1, p2 = png_bytes("1쪽"), png_bytes("2쪽")
    first = classify_pages(env, ["FIN-09_a.png", "b.png"], [p1, p2])
    same = classify_pages(env, ["FIN-09_a.png", "b.png"], [p1, p2])
    swapped = classify_pages(env, ["FIN-09_a.png", "b.png"], [p2, p1])
    changed = classify_pages(env, ["FIN-09_a.png", "b.png"], [p1, png_bytes("2쪽 수정")])
    assert not first.get("cached") and same["cached"]
    assert not swapped.get("cached") and not changed.get("cached")  # 순서나 한 쪽만 바뀌어도 다시 분류


def test_single_page_bundle_is_same_as_single_upload(env):
    assert services.save_pages(["a.png"], [png_bytes("1")]) == services.save_upload("a.png", png_bytes("1"))
    with pytest.raises(ValueError):
        services.save_pages([], [])


def test_pages_etc_proposal_name_has_no_page_suffix(env):
    r = classify_pages(env, ["출장정산서_p1.png", "출장정산서_p2.png"], [png_bytes("1"), png_bytes("2")])
    assert r["new_class"]["proposed_name"] == "출장정산서"  # MOCK 제안명에 _p1이 붙지 않는다


# 사원별 이력 분리 · 「기타」 표시 · 양식 내려받기 ---------------------------------------------------
def test_open_store_is_separate_per_employee(env):
    a, b = services.open_store("HS1001"), services.open_store("HS2001")
    classify_name(a, "견적서.png")
    assert len(a.list_history()) == 1 and b.list_history() == []        # 다른 사원에게는 보이지 않는다
    assert len(services.open_store("HS1001").list_history()) == 1       # 같은 사원은 다시 열어도 남는다
    assert services.open_store("../x").list_history() == []             # 사번에 경로 문자가 있어도 DB 폴더 밖으로 나가지 않는다


def test_pending_review_is_shown_as_etc(env):
    r = classify_name(env, "출장정산서.png")
    assert r["status"] == "pending_review"
    assert services.shown(r) == ("기타", "ETC-00", "기타")
    row = services.result_row(r)
    assert (row["대분류"], row["소분류 코드"], row["상태"]) == ("기타", "ETC-00", "기타")
    ok = classify_name(env, "FIN-03_손익계산서_001.png")
    assert services.shown(ok)[0] == "재무/회계" and services.result_row(ok)["상태"] == "확정"


@pytest.mark.skipif(not services.FORMS_DIR.is_dir(), reason="양식 원본(HWP·PDF)은 재배포 허락을 확인하지 못해 공개 저장소에 넣지 않았다")
def test_form_files_are_named_after_document_type_and_one_per_type():
    import yaml

    data = yaml.safe_load((ROOT / "config" / "forms.yaml").read_text(encoding="utf-8"))
    for code, name in data.items():
        f = services.form_file(code)
        assert f is not None and f.name == name and f.name.isascii(), code  # 파일 이름은 영문 (zip·윈도우에서 깨짐 방지)
        assert services.form_bytes(f) == f.read_bytes()
    assert services.form_bytes(services.form_file("HR-01"))[:4] == b"\xd0\xcf\x11\xe0"  # 한글 파일(OLE) 원본 그대로
    assert services.form_mime(services.form_file("HR-03")) == "application/pdf"
    assert services.form_file("ETC-00") is None


def test_map_majors_adds_etc_after_the_six_majors():
    majors = services.map_majors()
    assert majors[:-1] == services.all_majors() and majors[-1] == services.taxonomy().major_of(services.ETC_CODE)


# 설정 · 파일 이름 겹침 ------------------------------------------------------------------
def test_settings_default_save_and_reload(env):
    assert services.load_settings("HS1001") == services.DEFAULT_SETTINGS
    services.save_setting("HS1001", "lang", "en")
    services.save_setting("HS1001", "font", 115)
    assert services.load_settings("HS1001") | {} == {"lang": "en", "font": 115, "tour": "daily"}
    assert services.load_settings("HS1002") == services.DEFAULT_SETTINGS  # 사원마다 따로 저장


def test_settings_reject_bad_value_and_broken_file(env):
    with pytest.raises(ValueError):
        services.save_setting("HS1001", "font", 999)
    services.DB_DIR.mkdir(parents=True, exist_ok=True)
    services._settings_path("HS1001").write_text("{깨진 파일", encoding="utf-8")
    assert services.load_settings("HS1001") == services.DEFAULT_SETTINGS  # 깨져도 기본값으로 연다
    services._settings_path("HS1001").write_text('{"font": 999, "lang": "en"}', encoding="utf-8")
    assert services.load_settings("HS1001")["font"] == 100 and services.load_settings("HS1001")["lang"] == "en"


def test_name_conflicts_with_history_and_within_batch():
    assert services.name_conflicts(["a.pdf", "b.pdf"], set()) == []
    assert services.name_conflicts(["a.pdf", "B.pdf"], {"b.PDF"}) == [1]  # 이미 분류한 문서와 같음 (대소문자 무시)
    assert services.name_conflicts(["a.pdf", "a.pdf", "A.pdf"], set()) == [1, 2]  # 첫 번째만 그대로 둔다


def test_suggest_name_skips_used():
    assert services.suggest_name("보고서.pdf", {"보고서.pdf"}) == "보고서 (2).pdf"
    assert services.suggest_name("보고서.pdf", {"보고서.pdf", "보고서 (2).PDF"}) == "보고서 (3).pdf"


def test_demo_reads_taxonomy_yaml_directly(monkeypatch):
    """소분류가 늘어도 화면이 옛 목록을 보여 주지 않게, data/db 복사본 없이 원본 분류 체계를 바로 읽는다."""
    monkeypatch.delenv("TAXONOMY_PATH", raising=False)
    assert services.taxonomy_file() == services.DEFAULT_PATH
    shown = [i.code for i in services.taxonomy().classifiable_items]
    assert shown == [i.code for i in services.load_taxonomy(services.DEFAULT_PATH).classifiable_items]


# 교차 확인(Gemini+Qwen 합산) 표시: 합산 결과는 MOCK에서만 가짜로 만든다 -----------------------------
def test_mock_cross_check_confirmed_for_normal_and_unconfirmed_for_etc(env):
    ok = classify_name(env, "FIN-03_손익계산서_001.png")
    etc = classify_name(env, "출장정산서.png")
    assert ok["cross_check"]["confirmed"] is True and services.result_row(ok)["교차 확인"] == "확정"
    assert etc["cross_check"]["confirmed"] is False and services.result_row(etc)["교차 확인"] == "미확정"


def test_cross_label_blank_without_cross_check():
    assert services.cross_label({"status": "confirmed"}) == ""
    assert services.cross_label({"status": "error", "errors": ["x"]}) == ""


def test_mock_cross_check_carries_threshold(env):
    assert classify_name(env, "FIN-03_손익계산서_002.png")["cross_check"]["threshold"] == 0.95  # 화면은 기준값을 하드코딩하지 않는다


# 보안 등급 현황 리포트 -----------------------------------------------------------------
def test_grade_report_counts_by_grade_and_major_within_period(env, monkeypatch):
    from datetime import date

    monkeypatch.setattr(services, "load_grades", lambda: {"FIN-03": {"grade": "기밀", "basis": None}})
    fin = classify_name(env, "FIN-03_급여대장.png") | {"created_at": "2026-11-10T09:00:00"}
    hr = classify_name(env, "HR-01_채용공고.png") | {"created_at": "2026-11-16T23:59:59"}
    etc = classify_name(env, "출장정산서.png") | {"created_at": "2026-11-12T10:00:00"}
    err = {"status": "error", "errors": ["x"], "file": "깨진.png", "created_at": "2026-11-12T10:00:00"}
    old = fin | {"created_at": "2026-10-31T10:00:00"}  # 기간 밖

    rep = services.grade_report([fin, hr, etc, err, old], date(2026, 11, 1), date(2026, 11, 16))
    by_grade = {row["보안 등급"]: row["건수"] for row in rep["by_grade"]}
    by_major = {row["대분류"]: row["건수"] for row in rep["by_major"]}

    assert rep["total"] == 4
    assert by_grade == {"기밀": 1, "대외비": 0, "사내한정": 0, "공개": 0, "미산정": 1, "기타 (등급 없음)": 1, "오류": 1}
    assert by_major["재무/회계"] == 1 and by_major["인사/채용"] == 1 and by_major["기타"] == 1 and by_major["오류"] == 1
    assert sum(row["비율(%)"] for row in rep["by_grade"]) == 100.0
    assert [row["보안 등급"] for row in rep["rows"]] == ["기밀", "미산정", "기타 (등급 없음)", "오류"]


def test_grade_report_empty_period(env):
    from datetime import date

    rep = services.grade_report([], date(2026, 11, 1), date(2026, 11, 16))
    assert rep["total"] == 0 and rep["rows"] == []
    assert all(row["건수"] == 0 and row["비율(%)"] == 0.0 for row in rep["by_grade"] + rep["by_major"])


# 결과 화면의 보안 등급 -----------------------------------------------------------------
def test_grade_info_confirmed_uses_current_table_and_cross_check(env, monkeypatch):
    monkeypatch.setattr(services, "load_grades", lambda: {"FIN-03": {"grade": "기밀", "basis": "근거 문장"}})
    ok = classify_name(env, "FIN-03_급여대장.png")  # MOCK: 교차 확인 확정
    info = services.grade_info(ok)
    assert info["grade"] == "기밀" and info["provisional"] is False and "근거 문장" in info["basis"]
    unconfirmed = ok | {"cross_check": {"confirmed": False, "reason": "disagree"}}
    assert services.grade_info(unconfirmed)["provisional"] is True  # 합산 미확정이면 잠정
    assert services.grade_info(unconfirmed)["handling"] == "기밀"  # 미확정이어도 높은 등급은 그대로 취급(하향 방지)
    monkeypatch.setattr(services, "load_grades", lambda: {"FIN-03": {"grade": "공개", "basis": None}})
    assert services.grade_info(unconfirmed)["handling"] == "대외비"  # 낮은 등급은 확정 전까지 대외비 이상으로 올려 취급


def test_grade_info_ungraded_etc_and_error(env, monkeypatch):
    monkeypatch.setattr(services, "load_grades", lambda: {})
    ok = classify_name(env, "FIN-03_급여대장.png")
    assert services.grade_info(ok)["grade"] == "미산정" and services.grade_info(ok)["provisional"] is True
    etc = classify_name(env, "출장정산서.png")
    assert services.grade_info(etc) == {"etc": True, "handling": "대외비"}  # 「기타」는 등급 없이 담당자 확인
    assert services.grade_info({"status": "error", "errors": ["x"]}) is None
