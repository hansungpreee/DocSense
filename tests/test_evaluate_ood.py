import os

from src.eval.evaluate import ood_report, report_path, token_lines


def _row(n, code, status, name=None):
    return {
        "file": f"{code}_종류{code[-1]}_{n:03d}.png",
        "gold_code": code,
        "split": "ood",
        "status": status,
        "minor_code": "NEW-01" if status == "pending_review" else "FIN-05",
        "confidence": 0.8,
        "new_class": {"proposed_name": name} if status == "pending_review" else None,
    }


def test_ood_report_counts_pending_review_as_correct():
    rows = [
        _row(1, "OOD-01", "pending_review", "지출결의서"),
        _row(2, "OOD-01", "confirmed"),
        _row(1, "OOD-02", "pending_review"),
        {"file": "OOD-03_종류3_001.png", "gold_code": "OOD-03", "split": "ood", "status": "error"},
    ]
    text = "\n".join(ood_report(rows))
    assert "총 4건 (성공 3건, 오류 1건)" in text
    assert "(2/3, 95% CI" in text  # 오류는 분모에서 뺀다
    assert "| **OOD-01** 종류1 | 1/2 | 50.0% |" in text
    assert "지출결의서 1건" in text and "(이름 없음) 1건" in text
    assert "OOD-01_종류1_002.png → FIN-05" in text


def test_token_lines_sums_all_rows_including_errors():
    rows = [
        {"status": "confirmed", "usage": {"input_tokens": 1000, "output_tokens": 200}},
        {"status": "error", "usage": {"input_tokens": 500, "output_tokens": 0}},  # 오류도 쓴 토큰
        {"status": "confirmed"},  # usage 없는 옛 줄은 건너뜀
    ]
    assert token_lines(rows) == ["- **토큰 사용량**: 입력 1,500 + 출력 200 = **1,700** (usage 기록 2줄, 오류·재실행 포함)"]
    assert token_lines([{"status": "confirmed"}]) == []  # usage가 하나도 없으면 줄을 만들지 않음


def test_report_saved_next_to_first_pred():
    dev = os.path.join("results", "v5", "predictions.jsonl")
    ood = os.path.join("results", "v5_ood", "predictions.jsonl")
    assert report_path([dev, ood]) == os.path.join("results", "v5", "eval_report.md")
    assert report_path(["predictions.jsonl"]) == "eval_report.md"  # 폴더 없이 주면 현재 폴더
