"""개발용 OOD 라벨 두 파일(ood_dev, ood_dev2)을 labels.csv와 같은 열 형식의 한 파일로 합친다.

실행 (저장소 루트): python src/eval/merge_ood_dev.py   → data/meta/ood_dev_all_labels.csv (11종 × 10건 = 110행)
- 열: labels.csv의 file,major_code,major,minor_code,minor,split + nearest_minor_code
  - major_code·major는 「기타」(ETC), minor_code는 OOD 종류(DEVOOD-xx), minor는 문서 이름, split은 항상 ood
  - nearest_minor_code: 「이 분류인 것 같다」 tip 평가용 가장 가까운 소분류. 닮은 소분류가 없으면 빈칸
- DEVOOD-03 발주서는 SAL-04가 되어 체계 밖이 아니므로 뺀다. 이미지·시드는 그대로 둔다
  (render_ood.py --dev는 난수를 이어 쓰므로, 종류를 빼고 다시 만들면 뒤 종류 이미지가 달라진다).
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "data" / "meta"
SOURCES = [META / "ood_dev_labels.csv", META / "ood_dev2_labels.csv"]
OUT = META / "ood_dev_all_labels.csv"
DROP = {"DEVOOD-03"}  # 발주서 → SAL-04
# 가장 가까운 소분류와 판단 근거는 docs/ood_dev_all_notes.md (닮은 종류 확인)
NEAREST = {
    "DEVOOD-02": "SAL-04",  # 비품구매요청서: 품목·수량·단가·희망납기 표가 발주서와 닮음 (공급처·발주번호 없음)
    "DEVOOD-04": "HR-03",  # 급여명세서: 연봉 실수령액표와 닮음
    "DEVOOD-05": "SAL-02",  # 출장결과보고서: 거래처 방문일지와 닮음
    "DEVOOD-06": "MGT-01",  # 부서별예산집행실적표: 전년대비 비교표라 거래처 매입매출현황 분석표와 닮음
    "DEVOOD-09": "SAL-05",  # 반품폐기확인서: 품목·수량 표와 확인자 서명이 납품확인서와 닮음 (납품·발주번호, 인수 없음)
}


def main():
    rows = []
    for path in SOURCES:
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r["ood_code"] in DROP:
                    continue
                rows.append({"file": r["file"], "major_code": "ETC", "major": "기타", "minor_code": r["ood_code"],
                             "minor": r["title"], "split": "ood", "nearest_minor_code": NEAREST.get(r["ood_code"], "")})
    assert len(rows) == 110, len(rows)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}행 → {OUT}")


if __name__ == "__main__":
    main()
