"""같은 프롬프트를 여러 번 돌린 결과를 비교해 오분류·흔들림 분석 CSV를 만든다.

    python src/eval/compare_runs.py results/v2_clean_r4/predictions.jsonl results/v2_clean_r5/predictions.jsonl \\
        --out results/analysis/v2_r4_r5_flips.csv

한 번이라도 틀렸거나 실행마다 답이 다른 문서만 남긴다. '원인 태그'는 주간 오분류 리뷰에서 사람이 채운다.
"""
import argparse
import csv
import json
import os

from evaluate import CAUSE_TAGS, latest_per_file

REASON_CHARS = 90  # 근거 문장 요약 길이 (실행마다 첫 문장만)


def load_run(path: str) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {r["file"]: r for r in latest_per_file(rows)}


def pick(r: dict | None) -> str:
    if r is None:
        return "(없음)"
    if r.get("status") == "error":
        return "오류"
    code = r.get("minor_code") or ""
    shown = f"기타({code})" if code.startswith("NEW-") else code
    return f"{shown} ({r.get('confidence')})"


def compare(runs: dict[str, dict[str, dict]]) -> list[dict]:
    names = list(runs)
    files = sorted(set().union(*runs.values()))
    out = []
    for f in files:
        rs = [runs[n].get(f) for n in names]
        gold = next(r["gold_code"] for r in rs if r)
        codes = [r.get("minor_code") if r and r.get("status") != "error" else None for r in rs]
        wrong = [c != gold for c in codes]
        if not any(wrong) and len(set(codes)) == 1:
            continue
        kind = "매번 오답" if all(wrong) else "흔들림"
        reasons = " / ".join(f"{n}: {(r.get('reasons') or [''])[0][:REASON_CHARS]}"
                             for n, r, w in zip(names, rs, wrong) if r and w)
        row = {"file": f, "gold_code": gold, "구분": kind}
        row |= {f"{n} 예측": pick(r) for n, r in zip(names, rs)}
        row |= {"원인 태그": "", "근거 문장 요약 (틀린 실행)": reasons}
        out.append(row)
    return sorted(out, key=lambda r: (r["구분"] != "매번 오답", r["gold_code"], r["file"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="여러 실행의 predictions.jsonl을 비교해 오분류·흔들림 CSV 생성")
    parser.add_argument("pred", nargs="+", help="predictions.jsonl 경로 (2개 이상, 실행 이름은 폴더 이름)")
    parser.add_argument("--out", required=True, help="저장할 CSV 경로")
    args = parser.parse_args()
    if len(args.pred) < 2:
        raise SystemExit("⚠️ 비교하려면 결과 파일이 2개 이상 필요합니다.")
    missing = [p for p in args.pred if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"⚠️ 파일을 찾을 수 없습니다: {', '.join(missing)}")

    runs = {os.path.basename(os.path.dirname(os.path.abspath(p))): load_run(p) for p in args.pred}
    rows = compare(runs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:  # 엑셀에서 한글이 깨지지 않게
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["file"])
        writer.writeheader()
        writer.writerows(rows)
    always = sum(r["구분"] == "매번 오답" for r in rows)
    print(f"✅ {args.out}: {len(rows)}건 (매번 오답 {always}, 흔들림 {len(rows) - always})")
    print(f"   '원인 태그' 열에 {CAUSE_TAGS} 중 하나를 적어 주세요")
