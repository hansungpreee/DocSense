"""계획 75종 중 인사/채용(HR-06~15)·고객/거래처(CUS-04~15)·법무/총무(LEG-04~18) 37종 × 25장을 만든다.

실행 (저장소 루트): python -m src.eval.plan75.render_hcl [--only HR-06,CUS-04]
- 결과: data/images/plan75/<코드>_<이름>_<번호>.png (A4, 1656×2342, gitignore),
        data/meta/labels_plan75_hcl.csv (labels.csv와 같은 열)
- 코드는 가안이다 (병합 직전에 동결). 분할은 기존 규칙: 번호 끝자리 1 fewshot / 2~5 dev / 그 밖 test → 종류당 3/12/10.
- 내용은 시드 고정 난수(코드·번호)라 다시 실행해도 같은 이미지다. 문서 안에 정답 단서(OOD·분류명 설명)는 넣지 않는다.
- 「기타」 평가 문서 이름(지출결의서·회의록·협조전·품의서·활동보고서·출장정산서)은 문서에 쓰지 않는다 (tests가 확인).
- 한 쪽(A4)을 넘치면 그림이 잘리므로 멈춘다.
"""
import argparse
import csv
import random
from pathlib import Path

from src.eval.plan75 import cus, hr, leg

ROOT = Path(__file__).resolve().parents[3]
IMG_DIR = ROOT / "data" / "images" / "plan75"
LABELS_OUT = ROOT / "data" / "meta" / "labels_plan75_hcl.csv"
A4_CSS = (794, 1123)
SCALE = 1656 / 794
PER_FORM = 25
MAJORS = {"HR": ("HR", "인사/채용"), "CUS": ("CUS", "고객/거래처"), "LEG": ("LEG", "법무/총무")}
FORBIDDEN = ["지출결의서", "회의록", "협조전", "품의서", "활동보고서", "출장정산서"]


def split_of(seq: int) -> str:
    return {1: "fewshot", 2: "dev", 3: "dev", 4: "dev", 5: "dev"}.get(seq % 10, "test")


def all_specs():
    return hr.SPECS + cus.SPECS + leg.SPECS


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", help="쉼표로 구분한 코드만 만든다 (예: HR-06,LEG-10)")
    args = parser.parse_args()
    specs = all_specs()
    if args.only:
        want = args.only.split(",")
        unknown = [w for w in want if w not in {s[0] for s in specs}]
        if unknown:
            raise SystemExit(f"알 수 없는 코드: {unknown}")
        specs = [s for s in specs if s[0] in want]
    from playwright.sync_api import sync_playwright  # 테스트가 playwright 없는 PC에서도 import되도록 실행 때만 불러온다
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": A4_CSS[0], "height": A4_CSS[1]}, device_scale_factor=SCALE)
        for code, name, build in specs:
            major_code, major = MAJORS[code.split("-")[0]]
            for seq in range(1, PER_FORM + 1):
                html = build(random.Random(f"{code}-{seq}"), seq)
                bad = [w for w in FORBIDDEN if w in html]
                if bad:
                    raise SystemExit(f"⚠️ {code}-{seq:03d}: 「기타」 평가 문서 이름이 들어 있습니다 {bad}")
                page.set_content(html)
                h, w = page.evaluate("[document.documentElement.scrollHeight, document.documentElement.scrollWidth]")
                doc_id = f"{code}_{name.replace(' ', '')}_{seq:03d}"
                if h > A4_CSS[1] or w > A4_CSS[0]:
                    raise SystemExit(f"⚠️ {doc_id}: 내용이 A4 한 쪽을 넘습니다 ({w}×{h})")
                page.screenshot(path=str(IMG_DIR / f"{doc_id}.png"))
                rows.append({"file": f"{doc_id}.png", "major_code": major_code, "major": major, "minor_code": code,
                             "minor": name, "split": split_of(seq)})
        browser.close()
    with LABELS_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}장 → {IMG_DIR}, 라벨 → {LABELS_OUT}")


if __name__ == "__main__":
    main()
