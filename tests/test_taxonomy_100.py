"""소분류 100종 분류 체계(config/taxonomy.yaml) 점검. 실행: python -m pytest tests -q"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import i18n  # noqa: E402
from src.engine.taxonomy import DEFAULT_PATH, load_taxonomy  # noqa: E402


def _order(code: str) -> tuple:
    prefix, num = re.match(r"([A-Z]+)-(\d+)", code).groups()
    return prefix, int(num)


def test_has_100_unique_minors_in_order():
    items = load_taxonomy(DEFAULT_PATH).classifiable_items
    codes = [i.code for i in items]
    assert len(codes) == 100 and len(set(codes)) == 100
    for major in {i.major for i in items}:
        seq = [_order(i.code) for i in items if i.major == major]
        assert seq == sorted(seq), major


def test_new_75_match_label_files():
    labels = {}
    for name in ("labels_plan75_hcl.csv", "expansion_labels.csv"):
        with open(ROOT / "data" / "meta" / name, encoding="utf-8-sig", newline="") as f:
            labels.update({r["minor_code"]: r["minor"] for r in csv.DictReader(f)})
    assert len(labels) == 75
    names = {i.code: i.name for i in load_taxonomy(DEFAULT_PATH).classifiable_items}
    assert {c: names[c] for c in labels} == labels  # 코드와 이름이 라벨 파일과 같다


def test_every_minor_name_is_translated():
    items = load_taxonomy(DEFAULT_PATH).classifiable_items
    assert not [i.name for i in items if i.name not in i18n.EN]
