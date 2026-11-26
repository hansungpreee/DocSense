import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "eval"))  # evaluate.py와 같은 import 방식

from compare_runs import compare  # noqa: E402


def _r(file, code, conf=0.9, gold="LEG-02", reason="근거"):
    return {"file": file, "gold_code": gold, "minor_code": code, "confidence": conf, "status": "confirmed",
            "reasons": [reason]}


def test_compare_keeps_only_wrong_or_flipping_docs():
    runs = {
        "r1": {"a.png": _r("a.png", "LEG-02"), "b.png": _r("b.png", "NEW-01", reason="제목 없음"),
               "c.png": _r("c.png", "NEW-02"), "d.png": _r("d.png", "LEG-02")},
        "r2": {"a.png": _r("a.png", "LEG-02"), "b.png": _r("b.png", "LEG-02"),
               "c.png": _r("c.png", "NEW-03"), "d.png": {"file": "d.png", "gold_code": "LEG-02", "status": "error"}},
    }
    rows = {r["file"]: r for r in compare(runs)}
    assert "a.png" not in rows  # 두 번 다 맞음
    assert rows["b.png"]["구분"] == "흔들림" and rows["b.png"]["r1 예측"] == "기타(NEW-01) (0.9)"
    assert rows["b.png"]["근거 문장 요약 (틀린 실행)"] == "r1: 제목 없음"  # 틀린 실행의 근거만
    assert rows["c.png"]["구분"] == "매번 오답"  # NEW 번호가 달라도 둘 다 오답
    assert rows["d.png"]["r2 예측"] == "오류" and rows["d.png"]["구분"] == "흔들림"
    assert [r["file"] for r in compare(runs)][0] == "c.png"  # 매번 오답이 맨 위
    assert all(r["원인 태그"] == "" for r in rows.values())
