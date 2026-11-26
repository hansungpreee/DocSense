"""data/meta/labels_100.csv 생성: 소분류 100종의 정답 라벨 네 파일을 한 파일로 합친다 (원본 CSV는 고치지 않는다).

    python -m src.eval.make_labels_100

- 합치는 파일: labels.csv(19종), labels_new_minors.csv(6종), labels_plan75_hcl.csv(37종), expansion_labels.csv(38종)
- labels_new.csv는 넣지 않는다 (HR-04 급여명세서 폐기분이라 labels_new_minors.csv의 HR-04와 겹친다).
- 코드는 config/taxonomy_100.yaml에 있어야 하고, 이름(minor 열)은 그 파일의 이름으로 통일한다 (띄어쓰기 차이 7건).
- split.py는 labels.csv를 덮어쓰므로 부르지 않는다.
"""
import csv
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "data" / "meta"
SOURCES = ["labels.csv", "labels_new_minors.csv", "labels_plan75_hcl.csv", "expansion_labels.csv"]
COLUMNS = ["file", "major_code", "major", "minor_code", "minor", "split"]  # expansion의 template 열은 뺀다


def main() -> None:
    with (ROOT / "config" / "taxonomy_100.yaml").open(encoding="utf-8") as f:
        tax = yaml.safe_load(f)["taxonomy"]
    names = {i["minor_code"]: i["minor_name"] for m in tax for i in m["items"] if i["minor_code"] != "ETC-00"}

    rows, seen = [], {}
    for source in SOURCES:
        with (META / source).open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r["minor_code"] not in names:
                    raise SystemExit(f"{source}: taxonomy_100.yaml에 없는 코드 {r['minor_code']} ({r['file']})")
                code, kind = r["file"].split("_")[:2]  # 파일 이름은 <코드>_<소분류 이름>_<번호>.png
                if code != r["minor_code"] or kind.replace(" ", "") != names[code].replace(" ", ""):
                    raise SystemExit(f"{source}: 파일 이름과 소분류가 맞지 않음 {r['file']} (코드 {r['minor_code']} = {names[code]})")
                if r["file"] in seen:
                    raise SystemExit(f"파일 이름 중복: {r['file']} ({seen[r['file']]}, {source})")
                seen[r["file"]] = source
                rows.append({**{c: r[c] for c in COLUMNS}, "minor": names[r["minor_code"]]})

    missing = sorted(set(names) - {r["minor_code"] for r in rows})
    if missing:
        raise SystemExit(f"라벨이 없는 소분류: {', '.join(missing)}")

    out = META / "labels_100.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:  # 엑셀 호환
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    splits = Counter(r["split"] for r in rows)
    print(f"{out}: {len(rows)}장, 소분류 {len(names)}종, fewshot {splits['fewshot']} / dev {splits['dev']} / test {splits['test']}")


if __name__ == "__main__":
    main()
