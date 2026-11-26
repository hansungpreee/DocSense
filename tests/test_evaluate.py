from src.eval.evaluate import dev_report, latest_per_file


def _row(file, status, code="HR-01", tokens=100):
    return {
        "file": file, "status": status, "split": "dev",
        "gold_code": "HR-01", "gold_major": "인사/채용",
        "minor_code": code, "predicted_code": code, "major": "인사/채용",
        "usage": {"input_tokens": tokens, "output_tokens": 0},
    }


def test_latest_per_file_keeps_last_line():
    rows = [_row("a.png", "error"), _row("b.png", "confirmed"), _row("a.png", "confirmed")]
    latest = latest_per_file(rows)
    assert [r["file"] for r in latest] == ["a.png", "b.png"]
    assert latest[0]["status"] == "confirmed"  # 오류 줄이 재실행 결과로 대체됨


def test_dev_report_scores_latest_but_sums_all_tokens():
    rows = [_row("a.png", "error", tokens=50), _row("b.png", "confirmed"), _row("a.png", "confirmed")]
    text = "\n".join(dev_report(rows))
    assert "총 2건 (성공 2건, 오류 0건, 재실행으로 대체된 줄 1개 제외)" in text
    assert "(2/2, 95% CI" in text  # 정확도 분모는 문서 수
    assert "입력 250" in text  # 토큰은 오류 줄까지 모두 더함


def test_misclassified_csv_lists_only_wrong_docs_with_empty_tag(tmp_path):
    import csv
    from src.eval.evaluate import write_misclassified

    rows = [_row("a.png", "confirmed"), _row("b.png", "pending_review", code="NEW-01"), _row("c.png", "error")]
    path, n = write_misclassified(rows, str(tmp_path))
    with open(path, encoding="utf-8-sig") as f:
        lines = list(csv.reader(f))
    assert n == 1
    assert lines[0][-1] == "원인 태그"
    assert lines[1][:3] == ["b.png", "HR-01", "NEW-01"] and lines[1][-1] == ""  # 오류 줄은 오분류가 아님


def test_confusion_png_is_saved(tmp_path):
    import pytest
    pytest.importorskip("matplotlib")
    from src.eval.evaluate import save_confusion_png

    path = save_confusion_png([_row("a.png", "confirmed"), _row("b.png", "pending_review", code="NEW-01")], str(tmp_path))
    assert path and (tmp_path / "confusion_matrix.png").stat().st_size > 0


def test_wilson_matches_reference_table():
    from src.eval.evaluate import wilson

    # 근거자료 9장: 정확도 90%, 110건 → 83.0~94.3%, 220건 → 85.3~93.3%
    assert [round(x * 100, 1) for x in wilson(99, 110)] == [83.0, 94.3]
    assert [round(x * 100, 1) for x in wilson(198, 220)] == [85.3, 93.3]
    lo, hi = wilson(88, 88)  # 100%여도 상한이 1을 넘지 않고 하한은 1보다 작다
    assert hi == 1.0 and lo < 1.0
    assert wilson(0, 0) == (0.0, 0.0)


def test_threshold_table_uses_model_pick_and_confidence():
    from src.eval.evaluate import THRESHOLDS, threshold_lines

    def r(code, conf, gold="HR-01"):
        return {"gold_code": gold, "predicted_code": code, "confidence": conf}

    assert THRESHOLDS[0] == 0.5 and THRESHOLDS[-1] == 0.95 and len(THRESHOLDS) == 10  # 0.05 간격
    ok = [r("HR-01", 0.98), r("HR-01", 0.75), r("HR-02", 0.75), r("ETC-00", 0.99)]  # 맞음 2, 틀림 1, 모델이 직접 「기타」 1
    text = "\n".join(threshold_lines(ok))
    assert "| 0.70 | 3/4 (75.0%) | 66.7%" in text  # 「기타」는 기준과 상관없이 검토로 감
    assert "| 0.80 | 1/4 (25.0%) | 100.0% (95% CI" in text and "| 0건 | 1/2 (50.0%) | - |" in text  # 맞힌 1건도 빠짐
    assert "확신도 값 종류: 3개" in text and "OOD 열은" in text


def test_threshold_table_ood_column_counts_etc_and_low_confidence():
    from src.eval.evaluate import threshold_lines

    ok = [{"gold_code": "HR-01", "predicted_code": "HR-01", "confidence": 0.98}]
    ood = [{"predicted_code": "ETC-00", "confidence": 0.9},   # 모델이 직접 「기타」 → 항상 잡힘
           {"predicted_code": "FIN-05", "confidence": 0.8},   # 기준 0.85부터 잡힘
           {"predicted_code": "FIN-05", "confidence": 0.95}]  # 0.95에서도 자동 확정(놓침)
    lines = threshold_lines(ok, ood)
    row = {line.split("|")[1].strip(): line.split("|")[-2].strip() for line in lines if line.startswith("| 0.")}
    assert row["0.50"] == "1/3 (33.3%)" and row["0.80"] == "1/3 (33.3%)"
    assert row["0.85"] == "2/3 (66.7%)" and row["0.95"] == "2/3 (66.7%)"


def test_variant_table_groups_by_first_page_variant():
    from src.eval.evaluate import variant_lines

    ok = [{"file": "a_p1.png", "gold_code": "HR-01", "minor_code": "HR-01"},
          {"file": "b_p1.png", "gold_code": "HR-01", "minor_code": "NEW-01"},
          {"file": "c.png", "gold_code": "HR-01", "minor_code": "HR-01"}]
    text = "\n".join(variant_lines(ok, {"a_p1.png": "초점 흐림", "b_p1.png": "초점 흐림"}))
    assert "| 초점 흐림 | 2 | 50.0% (1/2," in text
    assert "| 변형 정보 없음 | 1 | 100.0% (1/1," in text
