"""확장 소분류 38종 × 25건(950장)을 만든다: HTML → A4 PNG(1656×2342) + 라벨 CSV.

실행 (저장소 루트): python -m src.eval.render_expansion                        # 전체 950장 → data/images/expansion/
                   python -m src.eval.render_expansion --only FIN-11 SAL-10   # 일부 소분류만
                   python -m src.eval.render_expansion --html-only <폴더>      # PNG 없이 HTML만 (브라우저 불필요)
- 재무/회계 FIN-11~22 (12종), 경영/전략 MGT-03~14 (12종), 영업/제안 SAL-07~20 (14종). 코드는 분류체계 도표의 임시 코드다.
- 소분류당 25건: 번호 001~003 fewshot, 004~013 dev, 014~025 test. 홀수 번호는 양식 A, 짝수 번호는 양식 B (양식 2종이 모든 분할에 섞인다).
- 내용은 (소분류, 번호)로 고정한 난수로 정한다. 다시 실행해도 같은 문서이고 소분류를 늘려도 앞 문서가 바뀌지 않는다.
- 라벨은 data/meta/expansion_labels.csv에 따로 쓴다 (taxonomy.yaml 반영 전 코드라 labels.csv에 넣지 않는다. new_form_labels.csv와 같은 이유).
- test 분할은 프롬프트 동결 전에는 열거나 평가에 쓰지 않는다. 수치는 합성용 근사값이다.
"""
import argparse
import csv
import random
import zlib
from pathlib import Path

from src.eval.expansion_common import A4_CSS, SCALE
from src.eval.expansion_fin import FORMS as FIN
from src.eval.expansion_mgt import FORMS as MGT
from src.eval.expansion_sal import FORMS as SAL

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "images" / "expansion"
LABELS = ROOT / "data" / "meta" / "expansion_labels.csv"
PER_FORM = 25
SEED = 2026
MAJORS = {"FIN": "재무/회계", "MGT": "경영/전략", "SAL": "영업/제안"}
ALL_FORMS = FIN + MGT + SAL


def split_of(seq: int) -> str:
    return "fewshot" if seq <= 3 else ("dev" if seq <= 13 else "test")


def build_all(only=None):
    """(파일 이름, HTML) 목록과 라벨 행. 양식 A(0)는 홀수 번호, 양식 B(1)는 짝수 번호."""
    docs, rows = [], []
    for code, minor, fn in ALL_FORMS:
        if only and code not in only:
            continue
        for seq in range(1, PER_FORM + 1):
            layout = 0 if seq % 2 else 1
            rng = random.Random(SEED * 1_000_000 + zlib.crc32(code.encode()) % 1000 * 1000 + seq)
            name = f"{code}_{minor}_{seq:03d}.png"
            docs.append((name, fn(layout, rng)))
            rows.append({"file": name, "major_code": code.split("-")[0], "major": MAJORS[code.split("-")[0]], "minor_code": code,
                         "minor": minor, "split": split_of(seq), "template": "양식A" if layout == 0 else "양식B"})
    return docs, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", help="이 소분류 코드만 만든다 (예: FIN-11 SAL-10)")
    parser.add_argument("--html-only", type=Path, help="PNG 없이 이 폴더에 HTML만 저장한다")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="이미지 저장 폴더")
    args = parser.parse_args()
    docs, rows = build_all(args.only)
    if not args.only:  # 일부만 만들 때는 전체 라벨을 덮어쓰지 않는다
        with LABELS.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    if args.html_only:
        args.html_only.mkdir(parents=True, exist_ok=True)
        for name, html in docs:
            (args.html_only / name.replace(".png", ".html")).write_text(html, encoding="utf-8")
        print(f"HTML {len(docs)}건 → {args.html_only}")
        return
    from playwright.sync_api import sync_playwright  # 브라우저가 필요한 경로에서만 불러온다
    args.out.mkdir(parents=True, exist_ok=True)
    too_long = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": A4_CSS[0], "height": A4_CSS[1]}, device_scale_factor=SCALE)
        for name, html in docs:
            page.set_content(html)
            if page.evaluate("document.documentElement.scrollHeight") > A4_CSS[1] or page.evaluate("document.documentElement.scrollWidth") > A4_CSS[0]:
                too_long.append(name)  # A4 한 장에 안 들어가면 잘린 이미지가 된다
            page.screenshot(path=str(args.out / name))
        browser.close()
    print(f"이미지 {len(docs)}장 → {args.out}" + ("" if args.only else f", 라벨 → {LABELS}"))
    if too_long:
        raise SystemExit(f"⚠️ A4를 넘는 문서 {len(too_long)}건: {too_long[:10]} … 항목 수나 여백을 줄이세요.")


if __name__ == "__main__":
    main()
