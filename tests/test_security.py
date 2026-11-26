"""보안 등급 조회: 등급표 조회, 미산정 처리, 분류 결과 연결, dev 지표 집계 (API 호출 없음)."""
import json
from types import SimpleNamespace

from PIL import Image

from src.engine.classify import Classifier
from src.engine.security import grade_fields, handling_grade, load_grades, summarize

UNGRADED = {"security_grade": "미산정", "grade_basis": "등급표에 없는 분류 (확정 전까지 대외비 이상으로 취급)"}


def grades_file(tmp_path, text="FIN-03: 기밀\nFIN-10: {grade: 사내한정, basis: 교부 문서}\nHR-01: 대외비\nSAL-05: 공개\nSAL-01: 비밀\nSAL-02: 일반\n"):
    p = tmp_path / "security_grades.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def fake_client(replies):
    replies = list(replies)

    def create(**kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=replies.pop(0)))], usage=None)

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def reply(code="FIN-03", conf=0.93):
    return json.dumps({"minor_code": code, "confidence": conf, "reasons": ["x"],
                       "evidence": [{"page": 1, "bbox_2d": [10, 10, 50, 50], "label": "제목"}],
                       "new_class_proposal": None})


def test_lookup_and_ungraded(tmp_path):
    table = load_grades(grades_file(tmp_path))
    assert "SAL-01" not in table and "SAL-02" not in table  # 4단계 중 하나가 아닌 이름(옛 「일반」 포함)은 버린다
    assert table["SAL-05"]["grade"] == "공개"
    r = {"status": "confirmed", "minor_code": "FIN-03", "minor_name": "손익계산서"}
    assert grade_fields(r, table) == {"security_grade": "기밀", "grade_basis": "소분류 FIN-03 손익계산서의 기본 등급"}
    assert grade_fields({"status": "confirmed", "minor_code": "FIN-10", "minor_name": "세금계산서"}, table) == {
        "security_grade": "사내한정", "grade_basis": "소분류 FIN-10 세금계산서의 기본 등급 (교부 문서)"}
    assert grade_fields({"status": "confirmed", "minor_code": "MGT-05"}, table) == UNGRADED  # 체계 안, 등급표 밖
    for r in ({"status": "pending_review", "minor_code": "NEW-01"}, {"status": "pending_review", "minor_code": "ETC-00"}):
        assert grade_fields(r, table) == {}  # 「기타」는 등급 피드백 없음


def test_missing_file_is_ungraded(tmp_path):
    assert load_grades(tmp_path / "없음.yaml") == {}


def test_classifier_attaches_grade_but_not_on_error(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    g = grades_file(tmp_path)
    r = Classifier(client=fake_client([reply()]), grades_path=g).classify(img)
    assert r["security_grade"] == "기밀" and r["status"] == "confirmed"
    r = Classifier(client=fake_client([reply(conf=0.3)]), grades_path=g).classify(img)  # 낮은 확신도 → 「기타」
    assert r["status"] == "pending_review" and "security_grade" not in r
    r = Classifier(client=fake_client(["x", "y", "z"]), grades_path=g).classify(img)
    assert r["status"] == "error" and "security_grade" not in r
    r = Classifier(client=fake_client([reply()]), grades_path=tmp_path / "없음.yaml").classify(img)
    assert r["security_grade"] == "미산정"


def test_handling_grade_is_conservative(tmp_path):
    table = load_grades(grades_file(tmp_path))
    assert handling_grade({"status": "pending_review", "minor_code": "NEW-01"}, table) == "대외비"
    assert handling_grade({"status": "confirmed", "minor_code": "FIN-10"}, table) == "사내한정"
    unconfirmed = {"confirmed": False, "reason": "disagree"}
    assert handling_grade({"status": "confirmed", "minor_code": "FIN-10", "cross_check": unconfirmed}, table) == "대외비"
    assert handling_grade({"status": "confirmed", "minor_code": "FIN-03", "cross_check": unconfirmed}, table) == "기밀"


def test_summarize_counts_downgrade(tmp_path):
    table = load_grades(grades_file(tmp_path))
    rows = [
        {"file": "1", "status": "confirmed", "gold_code": "FIN-03", "minor_code": "FIN-03"},  # 일치
        {"file": "2", "status": "confirmed", "gold_code": "FIN-03", "minor_code": "FIN-10"},  # 기밀 → 사내한정: 하향
        {"file": "3", "status": "pending_review", "gold_code": "HR-01", "minor_code": "NEW-01"},  # 미산정 → 대외비 취급
        {"file": "4", "status": "confirmed", "gold_code": "FIN-10", "minor_code": "HR-01"},  # 사내한정 → 대외비: 상향
        {"file": "5", "status": "confirmed", "gold_code": "MGT-05", "minor_code": "MGT-05"},  # 등급표 밖: 안 셈
        {"file": "6", "status": "error", "gold_code": "FIN-03"},  # 오류: 안 셈
        {"file": "7", "status": "pending_review", "gold_code": "FIN-03", "minor_code": "NEW-02"},  # 기밀 → 대외비 취급: 하향
    ]
    text = summarize(rows, table)
    assert text.startswith("등급표에 있는 문서 5건 (기밀 3, 대외비 1, 사내한정 1, 공개 0)")
    assert "등급 일치 1건 (20.0%) · 사람에게 넘김(「기타」·미산정·합산 미확정) 2건 (40.0%)" in text
    assert "하향 오류 1건 · 미확정을 대외비 이상으로 보수 처리하면 2건" in text
    assert "소분류 오분류 4건 중 등급 하향 1건 (25.0%)" in text
    assert "2 · FIN-03 기밀 → FIN-10 사내한정" in text


def test_real_grade_table_covers_taxonomy():
    """실제 등급표: 분류 체계의 소분류(「기타」 제외) 전부에 4단계 중 하나가 있고, 체계에 없는 코드는 없다."""
    import yaml

    from src.engine.security import GRADES, GRADES_PATH
    from src.engine.taxonomy import load_taxonomy

    codes = {i.code for i in load_taxonomy().items} - {"ETC-00"}
    raw = yaml.safe_load(GRADES_PATH.read_text(encoding="utf-8"))
    assert set(raw) == codes
    assert all(v["grade"] in GRADES and v.get("basis") for v in raw.values())
    assert len(load_grades()) == len(codes)
