"""가짜 결과 JSON(app/mock/samples)이 엔진의 실제 출력 형식과 같은지 확인한다.
엔진의 결과 형식이 바뀌면 이 테스트가 깨져서 샘플도 같이 고치게 된다."""
import json
import re
from pathlib import Path

from src.engine.guardrail import NewCodeAllocator, finalize
from src.engine.taxonomy import load_taxonomy

SAMPLES = sorted((Path(__file__).resolve().parents[1] / "app" / "mock" / "samples").glob("*.json"))


def engine_keys():
    tax = load_taxonomy()
    raw = {"minor_code": "FIN-03", "confidence": 0.9, "reasons": ["x"],
           "evidence": [{"page": 1, "bbox_2d": [0, 0, 10, 10], "label": "t"}]}
    return set(finalize(raw, tax, NewCodeAllocator.from_taxonomy(tax)))


def test_samples_exist():
    assert len(SAMPLES) == 4


def test_samples_match_engine_format():
    tax = load_taxonomy()
    keys = engine_keys()
    for path in SAMPLES:
        r = json.loads(path.read_text(encoding="utf-8"))
        assert set(r) == keys, f"{path.name}: 키가 엔진 출력과 다름 {set(r) ^ keys}"
        assert 0 <= r["confidence"] <= 1 and r["reasons"]
        for e in r["evidence"]:
            x1, y1, x2, y2 = e["bbox"]
            assert 0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 1000, path.name
        assert tax.is_valid_code(r["predicted_code"]), path.name

        if r["status"] == "confirmed":
            item = tax.get(r["minor_code"])
            assert item and r["new_class"] is None, path.name
            assert (r["major"], r["minor_name"]) == (item.major, item.name), path.name
        else:
            assert r["status"] == "pending_review" and re.fullmatch(r"NEW-\d{2}", r["minor_code"]), path.name
            assert set(r["new_class"]) == {"proposed_name", "proposed_major", "reason", "trigger"}, path.name
            assert r["new_class"]["trigger"] in ("etc", "low_confidence"), path.name
            assert r["new_class"]["proposed_major"] in tax.majors, path.name
