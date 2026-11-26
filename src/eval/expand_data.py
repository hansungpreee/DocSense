import os
import json
import copy
import re
import glob
import random

def find_project_root():
    candidates = [
        os.getcwd(),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ]
    for path in candidates:
        if os.path.exists(os.path.join(path, "data", "html")):
            return path
    return os.getcwd()

BASE_DIR = find_project_root()
html_dir = os.path.join(BASE_DIR, "data", "html")

FILE_MAPPING = [
    ("01_resume_basic.json", "HR-01", "이력서"),
    ("02_resume_detail.json", "HR-01", "이력서"),
    ("03_labor_contract.json", "HR-02", "근로계약서"),
    ("04_salary_table_2025.json", "HR-03", "연봉실수령액표"),
    ("05_salary_table_2026.json", "HR-03", "연봉실수령액표"),
    ("01_trial_balance.json", "FIN-01", "합계잔액시산표"),
    ("02_cost_statement.json", "FIN-02", "원가명세서"),
    ("03_income_statement.json", "FIN-03", "손익계산서"),
    ("04_revenue_expense_statement.json", "FIN-04", "총수입금액및필요경비명세서"),
    ("05_major_expense_detail.json", "FIN-05", "주요경비지출명세서"),
    ("06_nps_income_report_2025.json", "FIN-06", "소득총액신고서"),
    ("07_business_income_withholding.json", "FIN-07", "사업소득원천징수영수증"),
    ("08_yearend_tax_settlement.json", "FIN-08", "소득·세액공제신고서"),
    ("09_audit_report.json", "FIN-09", "감사보고서"),
    ("01_partner_sales_analysis.json", "MGT-01", "거래처매입매출현황분석표"),
    ("01_quote_and_invoice.json", "SAL-01", "견적서"),
    ("02_design_quote.json", "SAL-01", "견적서"),
    ("03_visit_log.json", "SAL-02", "거래처방문일지"),
    ("01_nda.json", "CUS-01", "비밀유지계약서"),
    ("02_franchise_contract.json", "CUS-02", "가맹계약서"),
    ("01_commercial_lease.json", "LEG-01", "상가건물임대차계약서"),
    ("02_standard_lease.json", "LEG-02", "표준임대차계약서"),
]

def find_doc_id_key_and_val(doc_dict):
    for key, val in doc_dict.items():
        if isinstance(val, str) and ("-" in val or "_" in val) and any(c.isdigit() for c in val):
            return key, val
    for key, val in doc_dict.items():
        if isinstance(val, str):
            return key, val
    return None, None

def mutate_html_content(html_text: str, rng: random.Random) -> str:
    # 1) 콤마가 포함된 금액 변형 (예: 1,500,000 -> 1,620,000)
    def replace_money(match):
        num_str = match.group(0).replace(",", "")
        if len(num_str) >= 4 and num_str.isdigit():
            num = int(num_str)
            new_num = int(round((num * rng.uniform(0.85, 1.25)) / 100.0) * 100)
            return f"{new_num:,}"
        return match.group(0)
    s = re.sub(r"\b\d{1,3}(?:,\d{3})+\b", replace_money, html_text)

    # 2) 전화번호 뒷자리 변형
    s = re.sub(r"(010-\d{4}-)\d{4}", lambda m: f"{m.group(1)}{rng.randint(1000, 9999)}", s)

    # 3) 날짜(월/일) 변형 (2024. 5. 8 개정 같은 법령 표기는 건드리지 않도록 하이픈/슬래시 날짜만 변경)
    def replace_date(match):
        year = match.group(1)
        sep1 = match.group(2)
        month = rng.randint(1, 12)
        sep2 = match.group(4)
        day = rng.randint(1, 28)
        return f"{year}{sep1}{month:02d}{sep2}{day:02d}"
    s = re.sub(r"(202[3-6])([-/])(\d{2})([-/])(\d{2})", replace_date, s)
    return s

def expand_all(target_count=30):
    rng = random.Random(42)
    expanded_files = 0
    created_htmls = 0

    for json_name, minor_code, clean_name in FILE_MAPPING:
        json_path = os.path.join(html_dir, json_name)
        if not os.path.exists(json_path):
            print(f"⚠️ 파일 없음: {json_path}")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        docs = data.get("문서목록", [])
        if not docs:
            continue

        orig_docs = docs[:10]  # 원본 10개 기준
        new_docs = list(orig_docs)

        while len(new_docs) < target_count:
            idx = len(new_docs) + 1  # 11 ~ 30
            base_doc = copy.deepcopy(orig_docs[(idx - 1) % len(orig_docs)])
            id_key, orig_id = find_doc_id_key_and_val(base_doc)

            if not orig_id:
                break

            # 원본 HTML 파일 찾기
            orig_html_path = os.path.join(html_dir, f"{orig_id}.html")
            if not os.path.exists(orig_html_path):
                matches = glob.glob(os.path.join(html_dir, f"*{orig_id}*.html"))
                if matches:
                    orig_html_path = matches[0]
                else:
                    break

            # 새 doc_id 및 새 HTML 파일 생성
            new_id = f"{orig_id}_aug{idx:02d}"
            base_doc[id_key] = new_id
            new_html_path = os.path.join(html_dir, f"{new_id}.html")

            if not os.path.exists(new_html_path):
                with open(orig_html_path, "r", encoding="utf-8") as hf:
                    html_str = hf.read()
                mutated_html = mutate_html_content(html_str, rng)
                with open(new_html_path, "w", encoding="utf-8") as hf:
                    hf.write(mutated_html)
                created_htmls += 1

            new_docs.append(base_doc)

        data["문서목록"] = new_docs
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        expanded_files += 1
        print(f"  ✔ {json_name}: 문서목록 {len(orig_docs)}건 -> {len(new_docs)}건 확장 완료!")

    print(f"\n✅ 총 {expanded_files}개 JSON 확장 완료! (새 HTML {created_htmls}개 생성됨)")

if __name__ == "__main__":
    expand_all(30)