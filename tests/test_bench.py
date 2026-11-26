"""검사 속도 측정 스크립트: enable_thinking 주입, 정답 판정, 모드 비교 요약 (실제 API 호출 없음)."""
from pathlib import Path
from types import SimpleNamespace

from src.api.bench import TimedClient, expected_code, grade_of, summarize
from src.engine.taxonomy import load_taxonomy


class FakeClient:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kw):
        self.calls.append(kw)
        usage = SimpleNamespace(completion_tokens_details=SimpleNamespace(reasoning_tokens=7))
        return SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])


def test_timed_client_sends_thinking_only_when_set():
    raw = FakeClient()
    TimedClient(raw, None).chat.completions.create(model="m")
    off = TimedClient(raw, False)
    off.chat.completions.create(model="m")
    assert "extra_body" not in raw.calls[0] and raw.calls[1]["extra_body"] == {"enable_thinking": False}
    assert off.reasoning_tokens == 7


def test_expected_code_and_grade():
    tax = load_taxonomy()
    labels = {"x.png": {"minor_code": "FIN-03"}}
    assert expected_code(Path("x.png"), labels, tax) == "FIN-03"
    assert expected_code(Path("HR-01_이력서_002.png"), {}, tax) == "HR-01"
    assert expected_code(Path("회식사진.png"), {}, tax) is None
    assert grade_of(None, {}) == "대외비"  # 「기타」는 최소 대외비


def row(file, mode, pred, ok, rank, ms=1000):
    return {"file": file, "mode": mode, "pred": pred, "code_ok": ok, "grade_ok": ok, "grade_rank": rank,
            "total_ms": ms, "model_ms": ms, "reasoning_tokens": 0}


def test_summarize_counts_regressions():
    rows = [row("a", "default", "FIN-03", True, 0, 15000), row("a", "off", "FIN-10", False, 2, 5000),
            row("b", "default", "HR-01", True, 1), row("b", "off", "기타", False, 1)]
    text = summarize(rows)
    assert "결과 다름 2" in text and "정답→오답 2" in text and "등급 하향 1" in text and "「기타」 증가 1" in text
