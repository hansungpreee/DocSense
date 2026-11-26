"""Gemini+Qwen 합산 확정(교차 확인). 두 모델의 분류 결과 JSON을 받아 확정 여부를 붙인다.

확정 규칙: Qwen이 정식 분류(status=confirmed)를 냈고, Gemini도 정식 분류로 같은 코드를 냈으며,
Gemini 확신도가 기준(기본 0.95) 이상이면 확정. 그 밖에는 모두 미확정(담당자 확인 필요)이다.
- 한쪽 오류(503 과부하 등): 남은 쪽 결과를 그대로 쓰되 미확정. 둘 다 오류면 Qwen 오류 결과를 그대로 돌려준다.
- Qwen 429 재시도는 호출하는 쪽(app/services.py의 2·4·8초 재시도)이 맡는다. Gemini 실패는 gemini_unavailable로 받는다.

데모·검사 서버는 CrossClassifier(make_classifier)로 두 모델을 동시에 부른다. 평가는 모델별로 run.py를 돌린 뒤 아래 명령으로 합친다.
같은 cross_check()를 쓰므로 데모와 평가의 확정 규칙이 같다.

결과에 붙는 필드 (화면 app/evidence.py가 읽는 모양)
    cross_check = {"confirmed": bool, "reason": str, "threshold": float,
                   "gemini": {"minor_code": str | None, "confidence": float | None}}
    reason: agree | disagree | low_confidence | etc | gemini_unavailable | qwen_unavailable

명령줄 실행 (저장소 루트에서, 같은 세트를 두 모델로 돌린 predictions.jsonl 두 개)
    python -m src.engine.cross_check results/a_vfinal_qwen_fix/predictions.jsonl results/a_vfinal_gemini_fix/predictions.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

THRESHOLD = 0.95  # 이상이면 확정. 11/17 「1.0만」(> 0.95)에서 변경: results/prompt_tune/threshold_1117.md
ETC_CODE = "ETC-00"
GEMINI_MODEL = "gemini-3.1-flash-lite"  # 평가(results/README.md)에 쓴 모델과 같게
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_TIMEOUT = 60  # 초. Gemini는 느린 꼬리가 40~50초라 그보다 길게 기다리지 않는다


def _code(r: dict) -> str | None:
    """비교에 쓰는 코드. 「기타」는 NEW-xx 번호가 호출마다 다르므로 모델이 고른 원래 코드(ETC-00 등)를 쓴다."""
    return r.get("predicted_code") or r.get("minor_code")


def _summary(r: dict) -> dict:
    code = r.get("minor_code") if r.get("status") == "confirmed" else ETC_CODE  # 「기타」·낮은 확신도는 화면에서 「기타」로 보인다
    return {"minor_code": code, "confidence": r.get("confidence")}


def cross_check(qwen: dict, gemini: dict, threshold: float = THRESHOLD) -> dict:
    """두 결과를 합친 결과 1건. 화면에 보일 분류는 Qwen(Qwen 오류면 Gemini)이고, cross_check 필드를 붙인다."""
    q_err, g_err = qwen.get("status") == "error", gemini.get("status") == "error"
    if q_err and g_err:
        return qwen  # 오류 결과는 그대로 (캐시에 넣지 않는 규칙도 그대로 적용된다)
    if g_err:
        return qwen | {"cross_check": {"confirmed": False, "reason": "gemini_unavailable", "threshold": threshold,
                                       "gemini": {"minor_code": None, "confidence": None}}}
    if q_err:
        return gemini | {"cross_check": {"confirmed": False, "reason": "qwen_unavailable", "threshold": threshold,
                                         "gemini": _summary(gemini)}}

    if qwen.get("status") != "confirmed" or gemini.get("status") != "confirmed":
        reason = "etc" if _code(qwen) == _code(gemini) else "disagree"  # 둘 다 「기타」면 etc, 한쪽만이면 서로 다른 판단
    elif _code(qwen) != _code(gemini):
        reason = "disagree"
    elif float(gemini.get("confidence") or 0) < threshold:
        reason = "low_confidence"
    else:
        reason = "agree"
    return qwen | {"cross_check": {"confirmed": reason == "agree", "reason": reason, "threshold": threshold,
                                   "gemini": _summary(gemini)}}


def cross_model_name(qwen_model: str) -> str:
    """합산 결과의 model 값. 데모 캐시가 Qwen 단독 결과나 Gemini 없이 낸 결과를 다시 쓰지 않게 두 모델을 함께 적는다."""
    gemini = os.getenv("GEMINI_MODEL", GEMINI_MODEL) if os.getenv("GEMINI_API_KEY") else "gemini 없음"
    return f"{qwen_model}+{gemini}"


class CrossClassifier:
    """Qwen·Gemini를 동시에 불러 cross_check()로 합친다. Classifier와 같은 모양(classify, tax, grades, model, prompt_version).
    gemini가 None(키 없음)이면 Gemini 실패와 같게 모든 결과가 미확정(gemini_unavailable)이다.
    Qwen 예외는 그대로 올린다 (데모의 429 재시도·오류 안내가 그대로 동작하게)."""

    def __init__(self, qwen, gemini=None):
        self.qwen, self.gemini = qwen, gemini
        self.model = cross_model_name(qwen.model)
        self.prompt_version = qwen.prompt_version

    @property
    def tax(self):
        return self.qwen.tax

    @property
    def grades(self):
        return self.qwen.grades

    def _gemini(self, path) -> dict:
        try:
            return self.gemini.classify(path)  # Gemini 「기타」 번호는 Gemini 쪽 발급기에서만 나온다 (저장소 번호를 쓰지 않음)
        except Exception:  # 429·503·시간 초과 등. 엔진 로그에는 Gemini Classifier가 종류만 남긴다
            return {"status": "error"}

    def classify(self, path, allocator=None) -> dict:
        if self.gemini is None:
            qwen, gemini = self.qwen.classify(path, allocator=allocator), {"status": "error"}
        else:
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(self._gemini, path)
            try:
                qwen = self.qwen.classify(path, allocator=allocator)
            finally:
                pool.shutdown(wait=False)  # Qwen 예외면 Gemini를 기다리지 않고 바로 올린다
            gemini = future.result()
        r = cross_check(qwen, gemini)
        if (r.get("cross_check") or {}).get("reason") == "qwen_unavailable" and r.get("status") == "pending_review":
            # Qwen 오류로 Gemini 결과를 쓰는 「기타」: NEW-xx 번호는 저장소 발급기에서 다시 받는다
            r["minor_code"] = (allocator or self.qwen.allocator).assign((r.get("new_class") or {}).get("proposed_name"))
        return r | {"model": self.model}


def make_classifier(**kwargs) -> CrossClassifier:
    """데모·검사 서버용. Qwen은 VLM_*, Gemini는 GEMINI_API_KEY·GEMINI_MODEL·GEMINI_BASE_URL (.env)."""
    from .classify import Classifier

    qwen = Classifier(**kwargs)
    gemini = None
    key = os.getenv("GEMINI_API_KEY")
    if key:
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=os.getenv("GEMINI_BASE_URL", GEMINI_BASE_URL), timeout=GEMINI_TIMEOUT)
        gemini = Classifier(**{k: v for k, v in kwargs.items() if k != "allocator"},
                            model=os.getenv("GEMINI_MODEL", GEMINI_MODEL), client=client)
    return CrossClassifier(qwen, gemini)


def _load(path: Path) -> dict[str, dict]:
    """파일명 → 마지막 줄. 오류 후 재실행한 문서는 뒤의 줄이 남는다."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return {r["file"]: r for r in rows}


def summarize(qwen: dict[str, dict], gemini: dict[str, dict], threshold: float = THRESHOLD) -> str:
    """확정률과 확정된 건 중 오답 수 (합격 기준: 확정률 90% 이상, 확정 오답 0건·최대 1%)."""
    files = sorted(set(qwen) | set(gemini))
    reasons, wrong, n_conf = Counter(), [], 0
    for f in files:
        q = qwen.get(f) or {"status": "error"}
        g = gemini.get(f) or {"status": "error"}
        r = cross_check(q, g, threshold)
        cc = r.get("cross_check")
        reasons[cc["reason"] if cc else "both_error"] += 1
        if cc and cc["confirmed"]:
            n_conf += 1
            gold = q.get("gold_code") or g.get("gold_code")  # 정답 열이 없는 결과(데모 등)는 오답을 세지 않는다
            if gold and r.get("minor_code") != gold:
                wrong.append(f"  {f} · 정답 {gold} → 확정 {r.get('minor_code')}")
    n = len(files) or 1
    lines = [
        f"문서 {n}건 · 기준: Gemini 확신도 >= {threshold} 이고 두 모델 코드 일치",
        f"확정 {n_conf}건 ({n_conf / n:.1%}) · 확정 중 오답 {len(wrong)}건"
        + (f" ({len(wrong) / n_conf:.1%})" if n_conf else ""),
        "미확정 사유: " + (", ".join(f"{k} {v}" for k, v in sorted(reasons.items()) if k != "agree") or "없음"),
    ]
    return "\n".join(lines + (["확정 오답"] + wrong if wrong else []))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="같은 세트의 Qwen·Gemini predictions.jsonl로 합산 확정률을 잰다 (API 호출 없음)")
    ap.add_argument("qwen", type=Path)
    ap.add_argument("gemini", type=Path)
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    args = ap.parse_args(argv)
    print(summarize(_load(args.qwen), _load(args.gemini), args.threshold))


if __name__ == "__main__":
    main()
