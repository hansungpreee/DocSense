"""vFinal 예외 규칙 반복 측정용 문서 묶음 만들기·채점 (dev만, test는 열지 않는다).

    # 1) 내 PC의 이미지 폴더에서 문서를 찾아 라벨 CSV 두 개를 만든다 (cmd 창 두 개로 나눠 돌리려고 반으로 나눔)
    python -m src.engine.tune_set build --dev data/images/clean data/images/new data/images/expansion data/images/plan75_hcl --prose data/images/hard_prose --hprose data/images/human_prose --hard2 data/images/hard2_dev --ood data/images/ood_dev
    # 2) 각 CSV로 분류 (--images . : CSV의 file이 저장소 루트 기준 경로)
    python -m src.engine.run --images . --labels results/prompt_tune/labels_sample_1.csv --prompt vFinal --out tune_r1_1
    # 3) 채점: 세트별 정확도, 약점 튜닝용/확인용, 극비 회귀, 기준(고치기 전 vFinal) 대비 바뀐 문서
    python -m src.engine.tune_set score results/tune_r1_1 results/tune_r1_2
    python -m src.engine.tune_set score results/tune_g1_1 results/tune_g1_2 --model gemini   # Gemini 결과는 Gemini 기준과 비교
    # 4) 오류(429 등)로 남은 문서만 다른 사람 PC에서 이어 돌리기: 라벨 CSV + 그 이미지만 zip으로 묶는다
    python -m src.engine.tune_set retry results/test_g_1 results/prompt_tune/labels_test_1.csv

묶음 정의는 results/prompt_tune/sets.csv (set, file, gold_code, weak).
- set: dev(labels_100 dev 1,136) · prose(줄글 B 123) · hprose(다듬은 줄글 C 24) · hard2 · hard · ood(개발용 OOD 110)
- --scope sample(기본): 매 반복 회귀 표본 약 430장. 소분류(OOD는 종류)마다 고정 시드 SEED로 SAMPLE_N장 무작위 + 약점 사례 전부.
  규칙이 겨냥한 줄글 B·C는 전부, hard2·OOD는 5장(OOD는 규칙 1·4가 「기타」를 줄이는 부작용 감시), dev는 1장.
  dev 소분류마다 5장 이상·극비 dev 전부는 마지막 --scope full에서 본다
- --scope full: 전체 (마지막 1회)
- weak: 「tune:N」 규칙을 만들 때 근거로 본 사례, 「check:N」 같은 유형이지만 규칙을 맞추는 데 쓰지 않은 사례 (N = 예외 규칙 번호)
OOD 문서는 「기타」(pending_review)면 정답, 규칙 5 사례는 사람 확인(pending_review)으로 넘어가도 성공으로 센다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import zipfile
from collections import defaultdict
from math import exp, lgamma, log, log1p
from pathlib import Path

import yaml

from .security import GRADES as GRADE_ORDER
from .taxonomy import ROOT, load_taxonomy

TUNE_DIR = ROOT / "results" / "prompt_tune"
SETS = TUNE_DIR / "sets.csv"
GRADES = ROOT / "config" / "security_grades.yaml"
TOP_GRADE = GRADE_ORDER[0]  # 가장 높은 등급 (11/17 「극비」→「기밀」 개명, 이름은 security.py만 따른다)
# 고치기 전 vFinal(d795bb1, 정의 수정 반영 100종) 결과. dev 세트 1·2는 결과 파일이 없어(사용자 로컬, 100%) 비교에서 빠진다
BASELINE = {
    "qwen": {
        "dev": ["a_vfinal_qwen_fix", "s3_vfinal_qwen"],
        "prose": ["b_vfinal_qwen_fix"],
        "hprose": ["c_vfinal_qwen_fix"],
        "hard2": ["vfinal_hard2_fix2_r1"],
        "hard": ["vfinal_hard_fix2_r1"],
        "ood": ["vfinal_ood_dev_fix2_r1"],
    },
    "gemini": {
        "dev": ["a_vfinal_gemini_fix", "s3_vfinal_gemini"],
        "prose": ["b_vfinal_gemini_fix"],
        "hprose": ["c_vfinal_gemini_fix"],
        "hard2": ["vfinal_hard2_gemini_fix2_r1"],
        "hard": ["vfinal_hard_gemini_fix2_r1"],
        "ood": ["vfinal_ood_dev_gemini_fix2_r1"],
    },
}
SEED = 20261117  # 세트 3 Gemini 표본(s3_sample.py)과 같은 시드
# 세트별 소분류당 표본 장수 (None = 전부, 0 = 안 넣음)
SAMPLE_N = {"dev": 1, "prose": None, "hprose": None, "hard2": 5, "hard": 0, "ood": 5}
SET_NAMES = {"dev": "dev 100종", "prose": "줄글 B", "hprose": "다듬은 줄글 C", "hard2": "hard2", "hard": "hard",
             "ood": "개발용 OOD(「기타」율)"}


def read_sets() -> list[dict]:
    with SETS.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sample_rows(rows: list[dict], per_set: dict[str, int | None], seed: int) -> list[dict]:
    """세트·소분류마다 per_set[세트]장 무작위 + 약점 사례 전부. 시드와 순서를 고정해 매 반복 같은 표본이 나온다."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["set"], r["gold_code"])].append(r)
    rng = random.Random(seed)
    picked = {id(r) for r in rows if r["weak"]}
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda r: r["file"])
        n = per_set[key[0]]
        picked |= {id(r) for r in rng.sample(members, len(members) if n is None else min(n, len(members)))}
    return [r for r in rows if id(r) in picked]


def build(args: argparse.Namespace) -> None:
    folders = {"dev": args.dev, "prose": args.prose, "hprose": args.hprose, "hard2": args.hard2, "hard": args.hard,
               "ood": args.ood}
    if args.scope == "test":  # 프롬프트 동결 후 1회만: labels_100.csv의 test 문서 (dev 폴더들에서 찾는다)
        with (ROOT / "data" / "meta" / "labels_100.csv").open(encoding="utf-8-sig") as f:
            rows = [{"set": "dev", "file": r["file"], "gold_code": r["minor_code"], "weak": ""}
                    for r in csv.DictReader(f) if r["split"] == "test"]
    else:
        rows = read_sets() if args.scope == "full" else sample_rows(read_sets(), SAMPLE_N, args.seed)
    split = "test" if args.scope == "test" else "dev"
    tax = load_taxonomy()
    out, missing = [], []
    for name, dirs in folders.items():
        want = [r for r in rows if r["set"] == name]
        if not want:
            continue
        if not dirs:
            print(f"건너뜀: {SET_NAMES[name]} {len(want)}장 (--{name} 폴더를 주지 않음)")
            continue
        found: dict[str, list[Path]] = defaultdict(list)
        for d in dirs:
            for p in Path(d).rglob("*.png"):
                found[p.name].append(p)
        for r in want:
            paths = found.get(r["file"], [])
            if len(paths) != 1:  # 없거나 같은 이름이 둘 이상이면 어느 쪽인지 모르므로 멈춘다
                missing.append(f"{name}/{r['file']} ({len(paths)}개)")
                continue
            code = r["gold_code"]
            major = tax.major_of(code) or "기타"
            out.append({"file": paths[0].as_posix(), "major": major, "minor_code": code, "split": split})
    if missing and not args.skip_missing:
        raise SystemExit(f"이미지를 하나로 찾지 못한 문서 {len(missing)}건 (예: {missing[:3]})")
    if missing:  # 이 PC에 없는 이미지는 빼고 진행한다. 빠진 문서는 채점에서도 세지 않는다
        print(f"건너뜀: 이미지를 하나로 찾지 못한 문서 {len(missing)}건 (예: {missing[:3]})")
    parts = [out[0::2], out[1::2]]
    for i, part in enumerate(parts, start=1):
        path = TUNE_DIR / f"labels_{args.scope}_{i}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "major", "minor_code", "split"])
            w.writeheader()
            w.writerows(part)
        print(f"{path.relative_to(ROOT)}: {len(part)}장")


def last_results(run_dir: Path) -> dict[str, dict]:
    """파일 이름 → 마지막 성공 결과. 오류 줄은 버린다."""
    out = {}
    path = run_dir / "predictions.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("status") != "error":
                out[Path(r["file"]).name] = r
    return out


def binom_cdf(k: int, n: int, p: float) -> float:
    # 로그로 계산한다: comb(n, i)를 실수로 바꾸면 n이 1,000 넘는 전체 측정에서 넘친다
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    log_pmf = (lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1) + i * log(p) + (n - i) * log1p(-p) for i in range(k + 1))
    return sum(exp(x) for x in log_pmf)


def ci95(k: int, n: int) -> tuple[float, float]:
    """정답률 k/n의 95% 정확 신뢰구간 (Clopper-Pearson, 이분법). s3_sample.py와 같은 계산."""
    def solve(f) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) < 0.025)
    upper = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) > 0.025)
    return lower, upper


def hit(row: dict, r: dict, weak: bool = False) -> bool:
    if row["set"] == "ood":
        return r["status"] == "pending_review"
    if weak and row["weak"].endswith(":5") and r["status"] == "pending_review":
        return True  # 약점 표에서만: 구분 근거가 안 보이는 문서는 사람 확인으로 넘기면 성공
    return r["minor_code"] == row["gold_code"]


def score(args: argparse.Namespace) -> None:
    rows = read_sets()
    # 결과의 file은 저장소 루트 기준 경로다. 이름이 겹치는 세트(dev·hard·hard2)는 이미지 폴더 이름으로 가린다
    by_path: dict[str, dict] = {}
    for run in args.runs:
        for line in (Path(run) / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("status") != "error":
                by_path[r["file"]] = r
    current: dict[tuple[str, str], dict] = {}
    for path, r in by_path.items():
        name = Path(path).name
        cands = [row for row in rows if row["file"] == name]
        if len(cands) > 1:  # 같은 이름: 경로의 폴더 이름으로 세트를 고른다
            parent = Path(path).parent.name.lower()
            pick = [c for c in cands if (c["set"] == "hard2") == ("hard2" in parent)
                    and (c["set"] == "hard") == ("hard" in parent and "hard2" not in parent)]
            cands = pick
        if len(cands) == 1:
            current[(cands[0]["set"], name)] = r

    base = {s: {} for s in SET_NAMES}
    for s, dirs in BASELINE[args.model].items():
        for d in dirs:
            base[s] |= last_results(ROOT / "results" / d)

    grades = yaml.safe_load(GRADES.read_text(encoding="utf-8")) if GRADES.exists() else {}
    top = {c for c, g in grades.items() if (g.get("grade") if isinstance(g, dict) else g) == TOP_GRADE}

    lines = ["세트별 (이번 / 기준: 고치기 전 vFinal의 같은 문서)"]
    for s in SET_NAMES:
        rs = [row for row in rows if row["set"] == s and (s, row["file"]) in current]
        if not rs:
            continue
        now = sum(hit(row, current[(s, row["file"])]) for row in rs)
        with_base = [row for row in rs if row["file"] in base[s]]
        b_now = sum(hit(row, current[(s, row["file"])]) for row in with_base)
        b_old = sum(hit(row, base[s][row["file"]]) for row in with_base)
        lo, hi = ci95(now, len(rs))
        lines.append(f"  {SET_NAMES[s]:18s} {now}/{len(rs)} ({now / len(rs):.1%}, 95% CI {lo:.1%}~{hi:.1%})   "
                     f"기준 있는 {len(with_base)}장: "
                     f"{b_old} → {b_now}")

    lines += ["", "약점 사례 (기준 → 이번, 규칙 번호별. 규칙 5는 사람 확인으로 넘겨도 성공)"]
    weak = defaultdict(lambda: [0, 0, 0])  # 기준 맞음, 이번 맞음, 장수
    for row in rows:
        key = (row["set"], row["file"])
        if row["weak"] and key in current:
            old = base[row["set"]].get(row["file"])
            weak[row["weak"]][0] += bool(old) and hit(row, old, weak=True)
            weak[row["weak"]][1] += hit(row, current[key], weak=True)
            weak[row["weak"]][2] += 1
    for role, title in (("tune", "튜닝용"), ("check", "확인용")):
        part = {k: v for k, v in sorted(weak.items()) if k.startswith(role)}
        old, now, total = (sum(v[i] for v in part.values()) for i in range(3))
        detail = ", ".join(f"규칙{k[-1]} {v[0]}→{v[1]}/{v[2]}" for k, v in part.items())
        lines.append(f"  {title} {old} → {now} / {total}  ({detail})")

    flips_bad, flips_good, top_bad = [], [], []
    for (s, name), r in sorted(current.items()):
        row = next(x for x in rows if x["set"] == s and x["file"] == name)
        ok = hit(row, r)
        if not ok and row["gold_code"] in top:
            top_bad.append(f"  {s}/{name} · {row['gold_code']} → {r['minor_code']} · {r['confidence']}")
        old = base[s].get(name)
        if old is None:
            continue
        was = hit(row, old)
        mark = f"  {s}/{name} · {row['gold_code']}: {old['minor_code']} → {r['minor_code']} · {r['confidence']}"
        if was and not ok:
            flips_bad.append(mark)
        elif ok and not was:
            flips_good.append(mark)
    lines += ["", f"새로 틀림 {len(flips_bad)}건"] + flips_bad
    lines += ["", f"새로 맞음 {len(flips_good)}건"] + flips_good
    lines += ["", f"극비 문서 오답 {len(top_bad)}건 (다른 코드·「기타」로 바뀐 것)"] + top_bad
    wrong = [f"  {s}/{name} · {next(x for x in rows if x['set'] == s and x['file'] == name)['gold_code']} → "
             f"{r['minor_code']} · {r['confidence']}"
             for (s, name), r in sorted(current.items())
             if not hit(next(x for x in rows if x["set"] == s and x["file"] == name), r)]
    lines += ["", f"전체 오답 {len(wrong)}건"] + wrong
    print("\n".join(lines))


def retry(args: argparse.Namespace) -> None:
    """실행 결과에서 성공 기록이 없는 문서만 골라 라벨 CSV와 이미지를 zip 하나로 묶는다 (저장소 루트에 풀면 같은 경로)."""
    done = {r["file"] for r in map(json.loads, (args.run / "predictions.jsonl").read_text(encoding="utf-8").splitlines())
            if r.get("status") != "error"}
    with args.labels.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, [r for r in reader if r["file"] not in done]
    if not rows:
        raise SystemExit("남은 문서가 없습니다.")
    missing = [r["file"] for r in rows if not (ROOT / r["file"]).is_file()]
    if missing:
        raise SystemExit(f"이미지 {len(missing)}개가 없습니다 (예: {missing[0]}). 저장소 루트에서 실행하세요.")
    name = f"retry_{args.run.name}"
    label_path = TUNE_DIR / f"labels_{name}.csv"
    with label_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    zip_path = ROOT / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(label_path, label_path.relative_to(ROOT).as_posix())
        for r in rows:
            z.write(ROOT / r["file"], r["file"])
    print(f"남은 문서 {len(rows)}건 → {zip_path.name} (라벨 {label_path.relative_to(ROOT).as_posix()})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.engine.tune_set", description="vFinal 예외 규칙 반복 측정")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="이미지 폴더에서 문서를 찾아 라벨 CSV 두 개를 만든다")
    b.add_argument("--skip-missing", action="store_true", help="이 PC에 없는 이미지는 빼고 라벨을 만든다")
    b.add_argument("--scope", choices=["sample", "full", "test"], default="sample",
                   help="sample: 반복용 약 430장, full: dev 전체, test: 동결 후 test 1회 (labels_100.csv)")
    b.add_argument("--seed", type=int, default=SEED)
    for name in ("dev", "prose", "hprose", "hard2", "hard", "ood"):
        b.add_argument(f"--{name}", nargs="*", type=Path, help=f"{SET_NAMES[name]} 이미지 폴더 (하위 폴더까지 찾음)")
    s = sub.add_parser("score", help="실행 결과 폴더를 채점한다")
    s.add_argument("runs", nargs="+", type=Path, help="results/<실행 이름> 폴더")
    s.add_argument("--model", choices=list(BASELINE), default="qwen", help="비교할 기준 결과의 모델 (기본값 qwen)")
    t = sub.add_parser("retry", help="오류로 남은 문서만 라벨 CSV와 이미지를 zip으로 묶는다 (다른 PC에서 이어 돌리기)")
    t.add_argument("run", type=Path, help="results/<실행 이름> 폴더")
    t.add_argument("labels", type=Path, help="그 실행에 쓴 라벨 CSV")
    args = parser.parse_args(argv)
    {"build": build, "score": score, "retry": retry}[args.cmd](args)


if __name__ == "__main__":
    main()
