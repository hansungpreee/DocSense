"""업로드 검사 속도 측정: 사고 모드(enable_thinking) 설정별로 같은 파일을 실제 API로 분류해 시간과 정답 대비 결과를 비교한다.

확장 검사 서버와 같은 엔진(Classifier)·같은 등급 규칙(handling_grade)을 쓴다. 엔진 설정은 바꾸지 않고,
이 스크립트 안에서만 요청에 enable_thinking을 붙인다. dev 파일만 쓴다(labels.csv의 split=test 파일은 거부).

실행 (저장소 루트에서, 키를 불러온 cmd에서)
    python -m src.api.bench <파일들...> --modes default off --out results/bench_1116.csv

    default : 지금 서버와 같은 요청 (enable_thinking을 보내지 않음)
    on/off  : enable_thinking true/false를 붙여 보냄
첫 모드가 기준이다. 정답 소분류는 labels.csv의 같은 파일명 → 파일명 앞 코드(FIN-03_...) → 둘 다 없으면 「기타」 순으로 정한다.
10~12건은 속도·회귀 확인용이다. 이 결과로 전체 정확도를 말하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import time
from pathlib import Path

from src.engine.pages import load_pages
from src.engine.security import GRADES, GRADES_PATH, handling_grade, load_grades
from src.engine.taxonomy import load_taxonomy

MODES = {"default": None, "on": True, "off": False}
LABELS = Path("data/meta/labels.csv")


class TimedClient:
    """OpenAI client를 감싸 모델 호출 시간·사고 토큰을 모으고 enable_thinking을 붙인다 (Classifier의 client 자리에 넣는다)."""

    def __init__(self, client, thinking: bool | None):
        self.client, self.thinking = client, thinking
        self.chat = self.completions = self
        self.model_ms = self.reasoning_tokens = 0

    def create(self, **kw):
        if self.thinking is not None:
            kw["extra_body"] = {"enable_thinking": self.thinking}
        start = time.time()
        resp = self.client.chat.completions.create(**kw)
        self.model_ms += int((time.time() - start) * 1000)
        details = getattr(getattr(resp, "usage", None), "completion_tokens_details", None)
        self.reasoning_tokens += getattr(details, "reasoning_tokens", 0) or 0
        if getattr(resp.choices[0].message, "reasoning_content", None):  # 토큰 수를 안 주는 경우 대비
            self.reasoning_tokens = max(self.reasoning_tokens, 1)
        return resp


def expected_code(path: Path, labels: dict[str, dict], tax) -> str | None:
    """정답 소분류. None = 「기타」(체계 밖)."""
    if path.name in labels:
        code = labels[path.name]["minor_code"]
    else:
        code = "-".join(path.name.split("-")[:2]).split("_")[0]
    return code if tax.get(code) else None


def grade_of(code: str | None, grades: dict) -> str:
    r = {"status": "confirmed", "minor_code": code} if code else {"status": "pending_review"}
    return handling_grade(r, grades)


def summarize(rows: list[dict]) -> str:
    """모드별 시간 중앙값·정답 수, 그리고 첫 모드 대비 변화(결과 다름, 정답→오답, 등급 하향, 「기타」 증가)."""
    modes = list(dict.fromkeys(r["mode"] for r in rows))
    base = {r["file"]: r for r in rows if r["mode"] == modes[0]}
    out = []
    for m in modes:
        rs = [r for r in rows if r["mode"] == m]
        ok = [r for r in rs if r["pred"] != "error"]
        line = (f"[{m}] {len(rs)}건 · 전체 시간 중앙값 {statistics.median([r['total_ms'] for r in rs]) / 1000:.1f}초"
                f" · 모델 호출 {statistics.median([r['model_ms'] for r in rs]) / 1000:.1f}초"
                f" · 사고 토큰 있음 {sum(1 for r in rs if r['reasoning_tokens'])}건"
                f" · 소분류 정답 {sum(r['code_ok'] for r in rs)}/{len(rs)} · 등급 정답 {sum(r['grade_ok'] for r in rs)}/{len(rs)}"
                f" · 오류 {len(rs) - len(ok)}건")
        if m != modes[0]:
            pairs = [(base[r["file"]], r) for r in rs if r["file"] in base]
            line += (f"\n    {modes[0]} 대비: 결과 다름 {sum(b['pred'] != r['pred'] for b, r in pairs)}"
                     f" · 정답→오답 {sum(b['code_ok'] and not r['code_ok'] for b, r in pairs)}"
                     f" · 등급 하향 {sum(r['grade_rank'] > b['grade_rank'] for b, r in pairs)}"
                     f" · 「기타」 증가 {sum(r['pred'] == '기타' and b['pred'] != '기타' for b, r in pairs)}")
        out.append(line)
    return "\n".join(out)


def run_one(path: Path, mode: str, client, tax, grades, labels, prompt_version: str) -> dict:
    from src.engine.classify import Classifier

    timed = TimedClient(client, MODES[mode])
    clf = Classifier(prompt_version=prompt_version, client=timed)
    start = time.time()
    pages = load_pages(path)  # PDF 변환 시간만 따로 잰다. 엔진이 안에서 한 번 더 변환하므로 전체 시간에는 이미 들어 있다
    pages_ms = int((time.time() - start) * 1000)
    start = time.time()
    try:
        r = clf.classify(path)
        pred = r["minor_code"] if r["status"] == "confirmed" else ("error" if r["status"] == "error" else "기타")
    except Exception as e:  # 예외 메시지는 응답 본문을 담을 수 있어 종류·상태 코드만
        r, pred = {}, "error"
        print(f"  {path.name} [{mode}] 오류: {type(e).__name__} {getattr(e, 'status_code', '') or ''}")
    total_ms = int((time.time() - start) * 1000)
    want = expected_code(path, labels, tax)
    got_grade = "-" if pred == "error" else grade_of(None if pred == "기타" else pred, grades)
    want_grade = grade_of(want, grades)
    return {
        "file": path.name, "mode": mode, "pages": len(pages), "total_ms": total_ms, "model_ms": timed.model_ms,
        "pages_ms": pages_ms, "reasoning_tokens": timed.reasoning_tokens, "retries": r.get("retries", "-"),
        "pred": pred, "want": want or "기타", "code_ok": pred == (want or "기타"),
        "grade": got_grade, "want_grade": want_grade, "grade_ok": got_grade == want_grade,
        # 하향 비교용: 숫자가 클수록 낮은 등급, 오류는 업로드를 막으므로 가장 높은 등급처럼 0
        "grade_rank": GRADES.index(got_grade) if got_grade in GRADES else 0,
    }


def main(argv: list[str] | None = None) -> None:
    import os

    from dotenv import load_dotenv
    from openai import OpenAI

    ap = argparse.ArgumentParser(prog="python -m src.api.bench", description="사고 모드 설정별 검사 시간·결과 비교")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--modes", nargs="+", default=["default", "off"], choices=list(MODES))
    ap.add_argument("--out", type=Path, default=Path("results/bench.csv"))
    args = ap.parse_args(argv)

    load_dotenv()
    if not os.getenv("VLM_API_KEY"):
        ap.exit(1, "VLM_API_KEY가 없습니다. env_qwen.bat을 먼저 call 하세요.\n")
    tax, grades = load_taxonomy(), load_grades(GRADES_PATH)
    labels = {}
    if LABELS.exists():
        with LABELS.open(encoding="utf-8-sig") as f:
            labels = {r["file"]: r for r in csv.DictReader(f)}
    blocked = [p.name for p in args.files if labels.get(p.name, {}).get("split") == "test"]
    if blocked:
        ap.exit(1, f"테스트셋 파일은 쓰지 않습니다: {', '.join(blocked)}\n")
    missing = [str(p) for p in args.files if not p.is_file()]
    if missing:
        ap.exit(1, f"파일이 없습니다: {', '.join(missing)}\n")

    client = OpenAI(api_key=os.getenv("VLM_API_KEY"),
                    base_url=os.getenv("VLM_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"))
    prompt_version = os.getenv("PROMPT_VERSION", "v1")
    print(f"모델 {os.getenv('VLM_MODEL', 'qwen3.7-plus-2026-05-26')} · 프롬프트 {prompt_version} · 모드 {args.modes}")
    rows = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for path in args.files:
        for mode in args.modes:  # 파일마다 모드를 번갈아 돌려 시간대 차이가 한쪽에 몰리지 않게 한다
            rows.append(run_one(path, mode, client, tax, grades, labels, prompt_version))
            row = rows[-1]
            print(f"  {path.name} [{mode}] {row['total_ms'] / 1000:.1f}초 → {row['pred']} (정답 {row['want']})")
            with args.out.open("w", encoding="utf-8-sig", newline="") as f:  # 매 건 저장: 중간에 멈춰도 잃지 않게
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    print(summarize(rows))
    print(f"저장: {args.out}")


if __name__ == "__main__":
    main()
