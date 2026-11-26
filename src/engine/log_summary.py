"""엔진 로그(logs/engine.log) 요약: 호출 수, 상태별 건수, 재요청 건수, 오류 건수, 주요 사유.

명령줄 실행 (저장소 루트에서)
    python -m src.engine.log_summary                  # logs/engine.log
    python -m src.engine.log_summary 다른/engine.log --top 10
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(lines) -> dict:
    """로그 줄("시각 {JSON}")들을 모아 요약한다. 형식이 다른 줄은 건너뛰고 개수만 센다."""
    status, reasons = Counter(), Counter()
    calls = retried = retries = skipped = 0
    for line in lines:
        try:
            rec = json.loads(line[line.index("{"):])
        except ValueError:
            skipped += 1
            continue
        calls += 1
        status[rec["status"]] += 1
        retries += rec["retries"]
        retried += rec["retries"] > 0
        for err in rec["errors"]:
            # 재요청 사유는 시도별 목록, 예외는 문자열 하나
            for reason in err if isinstance(err, list) else [err]:
                reasons[reason] += 1
    return {
        "calls": calls,
        "status": dict(status),
        "retried_calls": retried,
        "total_retries": retries,
        "errors": status["error"] + status["exception"],
        "reasons": reasons,
        "skipped_lines": skipped,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.engine.log_summary", description="엔진 로그를 요약한다.")
    parser.add_argument("log", nargs="?", type=Path, default=Path("logs/engine.log"), help="로그 파일")
    parser.add_argument("--top", type=int, default=5, help="주요 사유를 몇 개까지 보일지 (기본값 5)")
    args = parser.parse_args(argv)
    if not args.log.is_file():
        parser.error(f"로그 파일이 없습니다: {args.log}")

    s = summarize(args.log.read_text(encoding="utf-8").splitlines())
    print(f"호출 {s['calls']}건, 상태별 {s['status']}")
    print(f"재요청이 있었던 호출 {s['retried_calls']}건 (재요청 합계 {s['total_retries']}회)")
    print(f"오류로 끝난 호출 {s['errors']}건 (재요청 한도 초과 error + API 예외 exception)")
    if s["skipped_lines"]:
        print(f"형식이 달라 건너뛴 줄 {s['skipped_lines']}개")
    print(f"주요 사유 상위 {args.top}개:")
    for reason, n in s["reasons"].most_common(args.top):
        print(f"  {n}회  {reason}")


if __name__ == "__main__":
    main()
