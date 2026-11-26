import csv
from pathlib import Path

from src.eval.plan75 import cus, hr, leg
from src.eval.plan75.render_hcl import FORBIDDEN, PER_FORM, split_of

ROOT = Path(__file__).resolve().parents[1]


def test_specs_37종_코드_중복없음():
    specs = hr.SPECS + cus.SPECS + leg.SPECS
    codes = [s[0] for s in specs]
    assert len(codes) == 37 and len(set(codes)) == 37


def test_분할_3_12_10():
    s = [split_of(i) for i in range(1, PER_FORM + 1)]
    assert (s.count("fewshot"), s.count("dev"), s.count("test")) == (3, 12, 10)


def test_라벨_test_제외_555행():
    p = ROOT / "data/meta/labels_plan75_hcl.csv"
    if not p.exists():
        return
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    assert len(rows) == 555  # 공개 저장소는 test 370행을 뺐다 (fewshot 111 + dev 444)
    assert not any(r["split"] == "test" for r in rows)
    assert not any(w in r["file"] for r in rows for w in FORBIDDEN)
