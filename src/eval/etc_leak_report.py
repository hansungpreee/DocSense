"""「기타」 이탈 현황표: predictions.jsonl만 읽는다 (API 호출 없음).
 ① 체계 밖 문서(OOD)가 기존 소분류로 샌 경우, ② 정상 문서가 「기타」로 샌 경우를 센다 (8주차 회의 2안건).

    python -m src.eval.etc_leak_report \\
        --ood "③ v2 r1=results/q37e_v2_ood_dev_r1/predictions.jsonl" \\
        --dev "현재 기준선=results/q37e_v2_r1/predictions.jsonl,results/q37e_v3_r1/predictions.jsonl"

--ood·--dev는 "라벨=경로[,경로...]" 형식이고 여러 번 쓸 수 있다. 한 라벨의 경로들은 합쳐서 센다.
정상 문서의 이탈은 모델이 「기타」를 골랐거나 확신도가 --threshold(기본 0.7) 미만인 경우다.
"""
import argparse
import re
from collections import Counter, defaultdict

from src.engine.taxonomy import ETC_CODE, load_taxonomy
from src.eval.evaluate import _goes_to_review, latest_per_file, load_records

# 양식이 둘인 소분류: 양식당 30건이 번호 순서대로 이어진다 (make_labels_csv.py FILE_MAPPING 순서)
# ponytail: 양식 목록을 여기에 따로 둔다; 새 양식이 늘면 labels.csv에 template 열을 넣고 이 표를 없앤다
TEMPLATES = {
    "HR-01": ["표준 이력서(기본)", "표준 이력서(상세)"],
    "HR-03": ["2025년 연봉 실수령액표", "2026년 연봉 실수령액표"],
    "SAL-01": ["견적서·거래명세표 통합", "표준 견적서"],
}
PER_TEMPLATE = 30
NUM = re.compile(r"_(\d{3})(?:_p\d+)?\.png$")


def parse_groups(items: list[str]) -> list[tuple[str, list[str]]]:
    groups = []
    for item in items:
        label, _, paths = item.partition("=")
        if not paths:
            raise SystemExit(f"⚠️ '라벨=경로[,경로]' 형식이 아닙니다: {item}")
        groups.append((label, paths.split(",")))
    return groups


def load_ok(paths: list[str]) -> list[dict]:
    """경로마다 같은 파일의 마지막 줄만 남기고 오류 줄을 뺀다 (실행 하나를 한 번만 센다)."""
    rows = []
    for p in paths:
        rows += [r for r in latest_per_file(load_records([p])) if r.get("status") != "error"]
    return rows


def template_of(r: dict) -> str:
    names = TEMPLATES.get(r["gold_code"])
    if not names:
        return ""
    seq = int(NUM.search(r["file"]).group(1))
    return names[min((seq - 1) // PER_TEMPLATE, len(names) - 1)]


def rate(k: int, n: int) -> str:
    return f"{k}/{n} ({k / n * 100:.1f}%)" if n else "-"


def ood_section(groups) -> list[str]:
    lines = ["## ① 체계 밖 문서가 기존 소분류로 샌 경우 (개발용 OOD)", "",
             "정답은 「기타」(pending_review)입니다. 칸은 「기타」로 간 건수이고, 괄호 안은 확신도 기준 0.95를 적용했을 때입니다.", ""]
    for label, paths in groups:
        rows = load_ok(paths)
        kinds = sorted({(r["gold_code"], r["file"].split("_")[1]) for r in rows})
        lines += [f"### {label}", "", "| OOD 종류 | 「기타」 | 기준 0.95 적용 | 샌 문서 (→ 기존 소분류, 확신도) |", "| :--- | :---: | :---: | :--- |"]
        total = [0, 0, 0]
        for code, name in kinds:
            rs = [r for r in rows if r["gold_code"] == code]
            etc = sum(r["status"] == "pending_review" for r in rs)
            etc95 = sum(_goes_to_review(r, 0.95) for r in rs)
            leaked = [r for r in rs if r["status"] != "pending_review"]
            to = ", ".join(f"{r['file'].split('_')[2][:3]}→{r['minor_code']}({r['confidence']})" for r in leaked) or "-"
            lines.append(f"| {code} {name} | {rate(etc, len(rs))} | {rate(etc95, len(rs))} | {to} |")
            total = [total[0] + etc, total[1] + etc95, total[2] + len(rs)]
        lines += [f"| **합계** | **{rate(total[0], total[2])}** | **{rate(total[1], total[2])}** | |", ""]
    return lines


def dev_section(groups, threshold: float) -> list[str]:
    tax = load_taxonomy()
    lines = [f"## ② 정상 문서가 「기타」로 샌 경우 (소분류·양식별)", "",
             f"이탈 = 모델이 「기타」({ETC_CODE})를 골랐거나 확신도가 {threshold} 미만인 문서. 칸은 이탈/문서 수(실행 수 × 문서 수)입니다.", ""]
    loaded = [(label, load_ok(paths)) for label, paths in groups]
    head = "| 소분류 | 양식 | " + " | ".join(label for label, _ in loaded) + " |"
    lines += [head, "| :--- | :--- |" + " :---: |" * len(loaded)]
    leaked_files = defaultdict(list)
    sums = [[0, 0] for _ in loaded]
    for item in tax.classifiable_items:
        templates = TEMPLATES.get(item.code, [""])
        for tpl in templates:
            cells = []
            for g, (label, rows) in enumerate(loaded):
                rs = [r for r in rows if r["gold_code"] == item.code and template_of(r) == tpl]
                bad = [r for r in rs if _goes_to_review(r, threshold)]
                sums[g] = [sums[g][0] + len(bad), sums[g][1] + len(rs)]
                cells.append(rate(len(bad), len(rs)))
                leaked_files[label] += [r["file"] for r in bad]
            lines.append(f"| {item.code} {item.name} | {tpl or '-'} | " + " | ".join(cells) + " |")
    lines.append("| **합계** | | " + " | ".join(f"**{rate(k, n)}**" for k, n in sums) + " |")
    lines += ["", "이탈한 문서 (같은 문서가 여러 번이면 건수 표시):"]
    for label, files in leaked_files.items():
        counts = Counter(files)
        lines.append(f"- {label}: " + (", ".join(f"{f} ×{c}" if c > 1 else f for f, c in sorted(counts.items())) or "없음"))
    lost = [f"{label} {sum(r['predicted_code'] == r['gold_code'] and _goes_to_review(r, 0.95) for r in rows)}/{sum(r['predicted_code'] == r['gold_code'] for r in rows)}"
            for label, rows in loaded]
    lines += ["", "참고: 확신도 기준을 0.95로 올리면 정답이 「기타」로 빠지는 문서 수 — " + ", ".join(lost)]
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ood", action="append", default=[], help="라벨=경로[,경로] (개발용 OOD 결과)")
    parser.add_argument("--dev", action="append", default=[], help="라벨=경로[,경로] (dev·hard 등 체계 안 문서 결과)")
    parser.add_argument("--threshold", type=float, default=0.7, help="이탈로 볼 확신도 기준 (기본값 0.7)")
    args = parser.parse_args()
    out = ["# 「기타」 이탈 현황", ""]
    if args.ood:
        out += ood_section(parse_groups(args.ood))
    if args.dev:
        out += dev_section(parse_groups(args.dev), args.threshold)
    print("\n".join(out))
