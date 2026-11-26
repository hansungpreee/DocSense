"""Gemini+Qwen 합산 확정: 일치, 불일치, 낮은 확신도, 「기타」, 한쪽·양쪽 오류 (API 호출 없음)."""
import json

from src.engine.cross_check import _load, cross_check, summarize


def res(code, conf=0.99, status="confirmed", model="qwen"):
    r = {"file": "a.png", "minor_code": code, "predicted_code": code, "confidence": conf, "status": status, "model": model}
    if status == "pending_review":  # 엔진은 「기타」에 NEW-xx를 붙이고 predicted_code에 원래 코드를 남긴다
        r["minor_code"] = "NEW-01"
    if status == "error":
        r = {"file": "a.png", "status": "error", "errors": ["503"], "model": model}
    return r


def test_agree_confirms():
    r = cross_check(res("FIN-03"), res("FIN-03", 0.97, model="gemini"))
    assert r["minor_code"] == "FIN-03" and r["model"] == "qwen"
    assert r["cross_check"] == {"confirmed": True, "reason": "agree", "threshold": 0.95,
                                "gemini": {"minor_code": "FIN-03", "confidence": 0.97}}


def test_disagree_and_low_confidence():
    assert cross_check(res("FIN-03"), res("FIN-02", model="gemini"))["cross_check"]["reason"] == "disagree"
    low = cross_check(res("FIN-03"), res("FIN-03", 0.9, model="gemini"))["cross_check"]
    assert low["confirmed"] is False and low["reason"] == "low_confidence"
    edge = cross_check(res("FIN-03"), res("FIN-03", 0.95, model="gemini"))["cross_check"]  # 기준 「이상」이라 0.95는 확정
    assert edge["confirmed"] is True and edge["reason"] == "agree"


def test_etc_is_never_confirmed():
    both = cross_check(res("ETC-00", status="pending_review"), res("ETC-00", status="pending_review"))["cross_check"]
    assert both["reason"] == "etc" and both["gemini"]["minor_code"] == "ETC-00"
    one = cross_check(res("FIN-03"), res("ETC-00", status="pending_review"))["cross_check"]
    assert one == {"confirmed": False, "reason": "disagree", "threshold": 0.95,
                   "gemini": {"minor_code": "ETC-00", "confidence": 0.99}}


def test_one_side_error_uses_other_but_unconfirmed():
    r = cross_check(res("FIN-03"), res(None, status="error", model="gemini"))
    assert r["minor_code"] == "FIN-03" and r["cross_check"]["reason"] == "gemini_unavailable"
    r = cross_check(res(None, status="error"), res("FIN-03", model="gemini"))
    assert r["model"] == "gemini" and r["cross_check"]["confirmed"] is False
    assert r["cross_check"]["reason"] == "qwen_unavailable"


def test_both_error_returns_error_without_field():
    r = cross_check(res(None, status="error"), res(None, status="error", model="gemini"))
    assert r["status"] == "error" and "cross_check" not in r


def test_summarize_counts_confirmed_wrong(tmp_path):
    def write(name, rows):
        p = tmp_path / name
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        return _load(p)

    q = write("q.jsonl", [res("FIN-03") | {"file": "1.png", "gold_code": "FIN-02"},
                          res("HR-01") | {"file": "2.png", "gold_code": "HR-01"},
                          {"file": "3.png", "status": "error"}, res("LEG-01") | {"file": "3.png", "gold_code": "LEG-01"}])
    g = write("g.jsonl", [res("FIN-03") | {"file": "1.png"}, res("HR-01", 0.9) | {"file": "2.png"},
                          res("LEG-01") | {"file": "3.png"}])
    text = summarize(q, g)
    assert "확정 2건 (66.7%) · 확정 중 오답 1건 (50.0%)" in text  # 3.png는 재실행 성공 줄이 남는다
    assert "low_confidence 1" in text and "1.png · 정답 FIN-02 → 확정 FIN-03" in text


class FakeClf:
    """Classifier 대신. result가 예외면 올린다."""
    def __init__(self, result, model="q"):
        from src.engine.guardrail import NewCodeAllocator
        self.result, self.model, self.prompt_version = result, model, "v1"
        self.tax, self.grades, self.allocator, self.calls = None, {}, NewCodeAllocator(), []

    def classify(self, path, allocator=None):
        self.calls.append(allocator)
        if isinstance(self.result, Exception):
            raise self.result
        return dict(self.result)


def test_cross_classifier_calls_both_and_merges(monkeypatch):
    from src.engine.cross_check import CrossClassifier
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("GEMINI_MODEL", "g")
    q, g = FakeClf(res("FIN-03")), FakeClf(res("FIN-03", 0.97, model="g"), model="g")
    shared = object()
    r = CrossClassifier(q, g).classify("a.png", allocator=shared)
    assert r["cross_check"]["confirmed"] is True and r["model"] == "q+g"
    assert q.calls == [shared] and g.calls == [None]  # Gemini는 저장소 번호를 쓰지 않는다


def test_cross_classifier_gemini_failure_or_missing_is_unconfirmed(monkeypatch):
    from src.engine.cross_check import CrossClassifier
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = CrossClassifier(FakeClf(res("FIN-03")), FakeClf(RuntimeError("503"))).classify("a.png")
    assert r["minor_code"] == "FIN-03" and r["cross_check"]["reason"] == "gemini_unavailable"
    r = CrossClassifier(FakeClf(res("FIN-03")), None).classify("a.png")
    assert r["cross_check"]["reason"] == "gemini_unavailable" and r["model"] == "q+gemini 없음"


def test_cross_classifier_qwen_exception_propagates():
    import pytest
    from src.engine.cross_check import CrossClassifier
    with pytest.raises(RuntimeError):
        CrossClassifier(FakeClf(RuntimeError("429")), FakeClf(res("FIN-03", 0.97))).classify("a.png")


def test_cross_classifier_gemini_etc_fallback_takes_store_number():
    from src.engine.cross_check import CrossClassifier
    from src.engine.guardrail import NewCodeAllocator
    g_etc = res("ETC-00", status="pending_review") | {"minor_code": "NEW-01", "new_class": {"proposed_name": "회식사진"}}
    store = NewCodeAllocator(taken={"NEW-01"})
    r = CrossClassifier(FakeClf(res(None, status="error")), FakeClf(g_etc)).classify("a.png", allocator=store)
    assert r["cross_check"]["reason"] == "qwen_unavailable" and r["minor_code"] == "NEW-02"
