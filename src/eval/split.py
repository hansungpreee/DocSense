"""labels.csv 생성: 문서 번호 끝자리로 고정 분할한다 (무작위 없음).
끝자리 1 → fewshot, 2~5 → dev, 6~0 → test. 같은 원본의 증량본은 끝자리가 같아 항상 같은 세트에 들어간다.

    python src/eval/split.py

여러 쪽 문서는 data/images/clean(또는 hard)에 있는 _p1.png로 이름을 정하므로, 이미지가 있어야 한다.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/eval/ 기준 저장소 루트

STANDARD_MAP = {
    "HR-01": ("HR", "인사/채용", "이력서"),
    "HR-02": ("HR", "인사/채용", "근로계약서"),
    "HR-03": ("HR", "인사/채용", "연봉실수령액표"),
    "FIN-01": ("FIN", "재무/회계", "합계잔액시산표"),
    "FIN-02": ("FIN", "재무/회계", "원가명세서"),
    "FIN-03": ("FIN", "재무/회계", "손익계산서"),
    "FIN-04": ("FIN", "재무/회계", "총수입금액및필요경비명세서"),
    "FIN-05": ("FIN", "재무/회계", "주요경비지출명세서"),
    "FIN-06": ("FIN", "재무/회계", "소득총액신고서"),
    "FIN-07": ("FIN", "재무/회계", "사업소득원천징수영수증"),
    "FIN-08": ("FIN", "재무/회계", "소득·세액공제신고서"),
    "FIN-09": ("FIN", "재무/회계", "감사보고서"),
    "MGT-01": ("MGT", "경영/전략", "거래처매입매출현황분석표"),
    "SAL-01": ("SAL", "영업/제안", "견적서"),
    "SAL-02": ("SAL", "영업/제안", "거래처방문일지"),
    "CUS-01": ("CUS", "고객/거래처", "비밀유지계약서"),
    "CUS-02": ("CUS", "고객/거래처", "가맹계약서"),
    "LEG-01": ("LEG", "법무/총무", "상가건물임대차계약서"),
    "LEG-02": ("LEG", "법무/총무", "표준임대차계약서"),
}

CODE_COUNTS = [
    ("HR-01", 60), ("HR-02", 30), ("HR-03", 60),
    ("FIN-01", 30), ("FIN-02", 30), ("FIN-03", 30),
    ("FIN-04", 30), ("FIN-05", 30), ("FIN-06", 30),
    ("FIN-07", 30), ("FIN-08", 30), ("FIN-09", 30),
    ("MGT-01", 30), ("SAL-01", 60), ("SAL-02", 30),
    ("CUS-01", 30), ("CUS-02", 30), ("LEG-01", 30), ("LEG-02", 30),
]

img_dirs = [
    os.path.join(ROOT, "data", "images", "clean"),
    os.path.join(ROOT, "data", "images", "hard"),
]
if not any(os.path.isdir(d) for d in img_dirs):
    # 이미지 없이 만들면 여러 쪽 문서의 _p1 이름을 못 찾아 맞는 labels.csv를 틀린 값으로 덮어쓴다
    raise SystemExit("⚠️ data/images/clean 또는 hard 폴더가 없습니다. 이미지를 받은 뒤 실행하세요 (labels.csv는 바꾸지 않음).")

def get_actual_filename(base_name: str) -> str:
    p1_name = f"{base_name}_p1.png"
    for d in img_dirs:
        if os.path.exists(os.path.join(d, p1_name)):
            return p1_name
    return f"{base_name}.png"

rows = []
p1_count = 0

for minor_code, total_count in CODE_COUNTS:
    major_code, major_name, minor_name = STANDARD_MAP[minor_code]
    for i in range(total_count):
        seq = i + 1
        base_name = f"{minor_code}_{minor_name}_{seq:03d}"
        filename = get_actual_filename(base_name)
        if filename.endswith("_p1.png"):
            p1_count += 1
            
        mod = i % 10
        split_type = "fewshot" if mod == 0 else ("dev" if mod < 5 else "test")
        rows.append({
            "file": filename,
            "major_code": major_code,
            "major": major_name,
            "minor_code": minor_code,
            "minor": minor_name,
            "split": split_type
        })

fieldnames = ["file", "major_code", "major", "minor_code", "minor", "split"]

meta_dir = os.path.join(ROOT, "data", "meta")
os.makedirs(meta_dir, exist_ok=True)
csv_path = os.path.join(meta_dir, "labels.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ labels.csv {len(rows)}건 생성 완료 (다중 페이지 _p1.png 반영: {p1_count}건) → {csv_path}")
