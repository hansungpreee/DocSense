import os
import json
import glob
import fitz  # PyMuPDF
from playwright.sync_api import sync_playwright

html_dir = "data/html"
out_dir = "data/images/clean"
os.makedirs(out_dir, exist_ok=True)

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

def find_doc_id(doc_dict):
    for key, val in doc_dict.items():
        if isinstance(val, str) and ("-" in val or "_" in val) and any(c.isdigit() for c in val):
            return val
    for val in doc_dict.values():
        if isinstance(val, str):
            return val
    return None

def render_all():
    code_counters = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for json_name, minor_code, clean_name in FILE_MAPPING:
            json_path = os.path.join(html_dir, json_name)
            if not os.path.exists(json_path):
                continue

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            docs = data.get("문서목록", [])
            for doc in docs:
                code_counters[minor_code] = code_counters.get(minor_code, 0) + 1
                seq_num = code_counters[minor_code]
                base_name = f"{minor_code}_{clean_name}_{seq_num:03d}"

                # 이미 PNG가 있어도 매번 다시 렌더링한다 (HTML을 고치면 이미지에 바로 반영되도록).
                # 쪽수가 줄어든 문서는 옛 _pN.png가 남으므로, 다시 렌더링할 때는 data/images/clean을 먼저 비운다.
                single_path = os.path.join(out_dir, f"{base_name}.png")

                doc_id = find_doc_id(doc)
                html_path = os.path.join(html_dir, f"{doc_id}.html")
                if not os.path.exists(html_path):
                    matches = glob.glob(os.path.join(html_dir, f"*{doc_id}*.html"))
                    if matches:
                        html_path = matches[0]
                    else:
                        continue

                abs_html_path = os.path.abspath(html_path)
                page.goto(f"file:///{abs_html_path}")
                page.wait_for_load_state("networkidle")

                pdf_bytes = page.pdf(format="A4", print_background=True)
                pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                page_count = len(pdf_doc)

                if page_count == 1:
                    pix = pdf_doc[0].get_pixmap(dpi=200)
                    pix.save(single_path)
                    print(f"[단일 페이지] {base_name}.png 생성")
                else:
                    for p_idx in range(page_count):
                        out_path = os.path.join(out_dir, f"{base_name}_p{p_idx+1}.png")
                        pix = pdf_doc[p_idx].get_pixmap(dpi=200)
                        pix.save(out_path)
                    print(f"[다중 페이지 분할] {base_name} -> _p1 ~ _p{page_count}.png ({page_count}장) 완료")

                pdf_doc.close()

        browser.close()
    print("\n✅ 30건 증량분 PNG 렌더링이 모두 완료되었습니다!")

if __name__ == "__main__":
    render_all()