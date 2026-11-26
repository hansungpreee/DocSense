"""개발셋 일괄 분류: labels.csv의 문서를 차례로 분류해 결과를 저장하고 정확도를 요약한다 (v1 기준선 측정용).

    python -m src.engine.run --images ../data_branch --prompt v1 --per-class 2   # 소분류마다 2건씩 맛보기
    python -m src.engine.run --images ../data_branch --prompt v1                 # 개발셋 전체
    python -m src.engine.run --images <PNG 폴더> --prompt v2 --out v2_clean_r1   # 결과를 results/v2_clean_r1/에 저장
    python -m src.engine.run --images <OOD 폴더> --prompt v2 --split ood         # 분류 체계 밖 문서 (ood_labels.csv)

결과
    results/<실행 이름>/predictions.jsonl  문서 1건당 한 줄 (결과 JSON + gold_code, gold_major, split, usage)
    results/<실행 이름>/summary.txt        정확도와 오분류 목록 (OOD는 「기타」 판정률)
    실행 이름은 --out으로 정하고, 생략하면 프롬프트 버전.

중간에 끊겨도 같은 실행 이름으로 다시 실행하면 이미 성공한 문서는 건너뛴다 (API 비용 절약). 실행 이름이 다르면 이어받지 않는다.
상세 평가(F1, 혼동행렬)는 평가 담당의 src/eval 스크립트가 predictions.jsonl을 읽어 만든다.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .classify import Classifier
from .prompt import PROMPT_VERSIONS
from .taxonomy import DEFAULT_PATH, ROOT

LABELS = ROOT / "data" / "meta" / "labels.csv"
OOD_LABELS = ROOT / "data" / "meta" / "ood_labels.csv"


def read_labels(path: Path, split: str, per_class: int) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if split == "ood":  # ood_labels.csv는 열이 다르다: 정답은 OOD 종류(OOD-01~03)이고 대분류는 없다
        # ood_code 열이 없는 라벨(예: ood_dev_all_labels.csv)은 minor_code를 정답으로 쓴다
        rows = [{"file": r["file"], "minor_code": r.get("ood_code") or r["minor_code"], "major": None, "split": "ood"}
                for r in rows]
    else:
        rows = [r for r in rows if r["split"] == split]
    if not per_class:
        return rows
    picked, seen = [], Counter()
    for r in rows:
        seen[r["minor_code"]] += 1
        if seen[r["minor_code"]] <= per_class:
            picked.append(r)
    return picked


def read_done(path: Path) -> dict[str, dict]:
    """이미 성공한 문서 (파일명 → 결과). 오류 결과는 다시 시도한다."""
    if not path.exists():
        return {}
    done = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("status") != "error":
            done[r["file"]] = r
    return done


def error_lines(results: list[dict]) -> list[str]:
    failed = [r for r in results if r.get("status") == "error"]
    if not failed:
        return []
    return ["", "오류 (다시 실행하면 재시도)"] + [f"  {r['file']} · {' / '.join(r['errors'])}" for r in failed]


def summarize(results: list[dict], version: str) -> str:
    ok = [r for r in results if r.get("status") != "error"]
    errors = len(results) - len(ok)
    n = len(ok) or 1
    minor = sum(r["minor_code"] == r["gold_code"] for r in ok)
    first = sum(r["predicted_code"] == r["gold_code"] for r in ok)
    major = sum(r["major"] == r["gold_major"] for r in ok)

    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in ok:
        per_class[r["gold_code"]][1] += 1
        per_class[r["gold_code"]][0] += r["minor_code"] == r["gold_code"]

    lines = [
        f"프롬프트 {version} · 문서 {len(results)}건 (성공 {len(ok)}, 오류 {errors})",
        f"대분류 정확도      {major / n:.1%} ({major}/{len(ok)})",
        f"소분류 정확도      {minor / n:.1%} ({minor}/{len(ok)})  ← 「기타」로 빠진 건 오답 처리",
        f"소분류 (모델 1순위) {first / n:.1%} ({first}/{len(ok)})  ← 확신도 기준 적용 전",
        "",
        "소분류별 정답 수",
    ]
    lines += [f"  {code:7s} {c}/{t}" for code, (c, t) in sorted(per_class.items())]
    wrong = [r for r in ok if r["minor_code"] != r["gold_code"]]
    lines += ["", f"오분류 {len(wrong)}건 (파일 · 정답 → 예측 · 확신도)"]
    for r in wrong:
        first_pick = f" (1순위 {r['predicted_code']})" if r["predicted_code"] != r["minor_code"] else ""
        lines.append(f"  {r['file']} · {r['gold_code']} → {r['minor_code']}{first_pick} · {r['confidence']}")
    return "\n".join(lines + error_lines(results))


def summarize_ood(results: list[dict], version: str) -> str:
    """분류 체계 밖 문서: 「기타」(status pending_review)로 빠져야 정답. 정식 코드로 확정된 건이 오분류."""
    ok = [r for r in results if r.get("status") != "error"]
    n = len(ok) or 1
    etc = [r for r in ok if r["status"] == "pending_review"]

    per_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in ok:
        per_kind[r["gold_code"]][1] += 1
        per_kind[r["gold_code"]][0] += r["status"] == "pending_review"

    # 「기타」가 된 길은 둘: 모델이 ETC-00을 고름(trigger etc) / 정식 코드를 골랐지만 확신도가 기준 미만(low_confidence)
    low = [r for r in etc if (r.get("new_class") or {}).get("trigger") == "low_confidence"]

    lines = [
        f"프롬프트 {version} · OOD 문서 {len(results)}건 (성공 {len(ok)}, 오류 {len(results) - len(ok)})",
        f"「기타」 판정률     {len(etc) / n:.1%} ({len(etc)}/{len(ok)})  ← NEW-xx(pending_review)로 빠진 비율, 높을수록 좋음",
        f"  모델이 직접 「기타」 {len(etc) - len(low)}건 · 확신도 기준 미만 {len(low)}건  ← 뒤쪽이 기준값이 거른 건",
        "",
        "종류별 「기타」 판정 수",
    ]
    lines += [f"  {code:7s} {c}/{t}" for code, (c, t) in sorted(per_kind.items())]
    wrong = [r for r in ok if r["status"] != "pending_review"]
    lines += ["", f"정식 분류로 확정된 건 {len(wrong)}건 (파일 · 정답 종류 → 예측 · 확신도)"]
    lines += [f"  {r['file']} · {r['gold_code']} → {r['minor_code']} · {r['confidence']}" for r in wrong]
    if low:
        lines += ["", f"확신도 기준 미만으로 「기타」가 된 건 {len(low)}건 (파일 · 정답 종류 → 모델 1순위 · 확신도)"]
        lines += [f"  {r['file']} · {r['gold_code']} → {r['predicted_code']} · {r['confidence']}" for r in low]
    return "\n".join(lines + error_lines(results))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.engine.run", description="개발셋을 일괄 분류하고 정확도를 요약한다."
    )
    parser.add_argument("--images", type=Path, required=True, help="labels.csv의 file 이름으로 된 이미지가 있는 폴더")
    parser.add_argument("--prompt", default="v1", choices=list(PROMPT_VERSIONS), help="프롬프트 버전 (기본값 v1)")
    parser.add_argument("--split", default="dev", choices=["dev", "test", "ood"], help="dev·test: labels.csv의 split, ood: ood_labels.csv (기본값 dev)")
    parser.add_argument("--per-class", type=int, default=0, help="소분류마다 앞에서 N건만 (0 = 전부)")
    parser.add_argument("--labels", type=Path, help="정답 라벨 CSV (기본값: ood면 ood_labels.csv, 아니면 labels.csv)")
    parser.add_argument("--out", help="실행 이름: 결과를 results/<실행 이름>/에 저장 (기본값 프롬프트 버전)")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_PATH,
                        help="분류 체계 YAML (기본값 config/taxonomy.yaml, 100종 측정은 config/taxonomy_100.yaml)")
    parser.add_argument("--confirm-test", action="store_true", help="테스트셋 실행 확인 (프롬프트 동결 후에만)")
    args = parser.parse_args(argv)
    if args.split == "test" and not args.confirm_test:
        parser.error("테스트셋은 프롬프트 동결 후 한 번만 평가합니다. 정말 실행하려면 --confirm-test를 붙이세요.")
    if not args.images.is_dir():
        parser.error(f"이미지 폴더가 없습니다: {args.images}")
    if not args.taxonomy.is_file():
        parser.error(f"분류 체계 파일이 없습니다: {args.taxonomy}")

    run_name = args.out or args.prompt
    if run_name in (".", "..") or "/" in run_name or "\\" in run_name:
        parser.error(f"--out은 폴더 경로가 아니라 실행 이름입니다 (results/<실행 이름>/에 저장): {run_name}")

    labels = args.labels or (OOD_LABELS if args.split == "ood" else LABELS)
    rows = read_labels(labels, args.split, args.per_class)
    missing = [r["file"] for r in rows if not (args.images / r["file"]).is_file()]
    if missing:
        parser.error(f"이미지 {len(missing)}개가 폴더에 없습니다 (예: {missing[0]})")

    out_dir = ROOT / "results" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"
    done = read_done(pred_path)

    try:
        # 평가는 --taxonomy로 정한 파일로 잰다. .env의 TAXONOMY_PATH(데모 승인으로 바뀌는 복사본)는 따르지 않는다
        clf = Classifier(prompt_version=args.prompt, taxonomy_path=args.taxonomy)
    except RuntimeError as e:
        parser.exit(1, f"{e}\n")

    results = []
    with pred_path.open("a", encoding="utf-8") as out:
        for i, row in enumerate(rows, start=1):
            if row["file"] in done:
                results.append(done[row["file"]])
                continue
            try:
                r = clf.classify(args.images / row["file"])
            except Exception as e:  # 네트워크·한도 초과 등: 기록하고 다음 문서로 (다시 실행하면 재시도)
                r = {"file": row["file"], "status": "error", "errors": [f"{type(e).__name__}: {e}"[:300]]}
            # usage: 재요청까지 합친 토큰. 오류로 끝난 문서도 쓴 만큼 남는다
            # file은 라벨 CSV에 적힌 그대로 둔다 (하위 폴더 경로가 든 라벨도 이어 하기가 맞게)
            r |= {"file": row["file"], "gold_code": row["minor_code"], "gold_major": row["major"], "split": row["split"],
                  "usage": clf.last_usage}
            if clf.last_retry_errors:  # 재요청 사유 (시도별 목록). 결과 JSON 형식은 그대로, 이 실행 기록에만 덧붙인다
                r["retry_errors"] = clf.last_retry_errors
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()  # 중간에 끊겨도 지금까지 결과는 남긴다
            results.append(r)
            hit = r.get("status") == "pending_review" if args.split == "ood" else r.get("minor_code") == row["minor_code"]
            mark = "O" if hit else "X"
            print(f"[{i}/{len(rows)}] {mark} {row['file']} → {r.get('minor_code', '오류')}", flush=True)

    summary = (summarize_ood if args.split == "ood" else summarize)(results, args.prompt)
    summary += f"\n분류 체계 파일: {args.taxonomy}"
    (out_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print("\n" + summary)
    print(f"\n저장: {pred_path}, {out_dir / 'summary.txt'}")


if __name__ == "__main__":
    main()
