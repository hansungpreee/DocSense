import argparse
import csv
import json
import zipfile
from collections import Counter

from src.engine import tune_set
from src.engine.tune_set import SAMPLE_N, SETS, ci95, hit, read_sets, sample_rows
from src.engine.taxonomy import ROOT


def test_sets_use_dev_only():
    # 반복 측정 묶음에 test 문서가 섞이면 프롬프트를 test에 맞추게 된다
    with (ROOT / "data" / "meta" / "labels_100.csv").open(encoding="utf-8-sig") as f:
        split = {r["file"]: r["split"] for r in csv.DictReader(f)}
    rows = read_sets()
    assert SETS.exists() and rows
    assert all(split[r["file"]] == "dev" for r in rows if r["set"] == "dev")
    weak = [r for r in rows if r["weak"]]
    assert {r["weak"].split(":")[0] for r in weak} == {"tune", "check"}

    picked = sample_rows(rows, SAMPLE_N, 20261117)
    assert picked == sample_rows(rows, SAMPLE_N, 20261117)  # 같은 시드면 같은 표본
    assert all(r in picked for r in weak)  # 약점 사례는 매 반복 들어간다
    per = Counter((r["set"], r["gold_code"]) for r in picked if not r["weak"])
    assert all(v <= 1 for (s, _), v in per.items() if s == "dev")
    assert len({r["gold_code"] for r in picked if r["set"] == "dev"}) == 100
    assert sum(r["set"] == "prose" for r in picked) == sum(r["set"] == "prose" for r in rows)  # 줄글은 전부
    assert not any(r["set"] == "hard" for r in picked)


def test_hit_rules():
    ood = {"set": "ood", "gold_code": "DEVOOD-05", "weak": ""}
    assert hit(ood, {"status": "pending_review", "minor_code": "NEW-01"})
    assert not hit(ood, {"status": "confirmed", "minor_code": "SAL-02"})
    cut = {"set": "hard2", "gold_code": "LEG-02", "weak": "check:5"}
    handed = {"status": "pending_review", "minor_code": "NEW-01"}
    assert not hit(cut, handed)  # 세트 정확도에서는 오답
    assert hit(cut, handed, weak=True)  # 약점 표에서는 사람 확인으로 넘겨 성공
    assert hit(cut, {"status": "confirmed", "minor_code": "LEG-02"})


def test_ci95_matches_known_values():
    lo, hi = ci95(10, 10)  # 10/10: 하한 69.2% (Clopper-Pearson)
    assert hi == 1.0 and abs(lo - 0.6915) < 0.001
    lo, hi = ci95(0, 10)
    assert lo == 0.0 and abs(hi - 0.3085) < 0.001


def test_ci95_large_n():
    # 전체 측정 크기(1,000장 이상)에서도 넘치지 않아야 한다
    lo, hi = ci95(1477, 1479)
    assert 0.99 < lo < hi < 1.0


def test_retry_packs_only_failed_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(tune_set, "ROOT", tmp_path)
    monkeypatch.setattr(tune_set, "TUNE_DIR", tmp_path / "tune")
    (tmp_path / "tune").mkdir()
    (tmp_path / "img").mkdir()
    for name in ("a.png", "b.png", "c.png"):
        (tmp_path / "img" / name).write_bytes(b"png")
    labels = tmp_path / "labels.csv"
    labels.write_text("file,major_code,major,minor_code,minor,split\n"
                      + "".join(f"img/{n}.png,HR,인사,HR-01,이력서,test\n" for n in "abc"), encoding="utf-8-sig")
    run = tmp_path / "test_g_1"
    run.mkdir()
    lines = [{"file": "img/a.png", "status": "confirmed"}, {"file": "img/b.png", "status": "error"},
             {"file": "img/c.png", "status": "error"}, {"file": "img/c.png", "status": "confirmed"}]  # c는 재시도로 성공
    (run / "predictions.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    tune_set.retry(argparse.Namespace(run=run, labels=labels))

    names = zipfile.ZipFile(tmp_path / "retry_test_g_1.zip").namelist()
    assert names == ["tune/labels_retry_test_g_1.csv", "img/b.png"]
