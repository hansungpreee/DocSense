import os
import csv
import json

os.makedirs("data/meta", exist_ok=True)
html_dir = "data/html"  # JSON 파일들이 들어있는 폴더 경로 (현재 폴더에 있다면 "." 으로 변경)

# 보내주신 22개 영어 JSON 파일명과 PRD 분류 체계 100% 매칭 테이블
# 형식: "파일명": ("대분류", "소분류코드", "표준소분류명", "양식구분명(template열)", 기본페이지수)
FILE_MAPPING = {
    # 1. 인사/채용 (HR) - 총 40건
    "01_resume_basic.json": ("인사/채용", "HR-01", "이력서", "표준 이력서(기본)", 1),
    "02_resume_detail.json": ("인사/채용", "HR-01", "이력서", "표준 이력서(상세)", 2),
    "03_labor_contract.json": ("인사/채용", "HR-02", "근로계약서", "표준근로계약서", 1),
    "04_salary_table_2025.json": ("인사/채용", "HR-03", "연봉 실수령액표", "2025년 연봉 실수령액표", 1),
    "05_salary_table_2026.json": ("인사/채용", "HR-03", "연봉 실수령액표", "2026년 연봉 실수령액표", 1),

    # 2. 재무/회계 (FIN) - 총 90건
    "01_trial_balance.json": ("재무/회계", "FIN-01", "합계잔액시산표", "표준 합계잔액시산표", 1),
    "02_cost_statement.json": ("재무/회계", "FIN-02", "원가명세서", "표준 원가명세서", 1),
    "03_income_statement.json": ("재무/회계", "FIN-03", "손익계산서", "표준 손익계산서", 1),
    "04_revenue_expense_statement.json": ("재무/회계", "FIN-04", "총수입금액 및 필요경비명세서", "총수입금액 및 필요경비명세서", 1),
    "05_major_expense_detail.json": ("재무/회계", "FIN-05", "주요경비지출명세서", "주요경비지출명세서", 1),
    "06_nps_income_report_2025.json": ("재무/회계", "FIN-06", "소득총액신고서", "소득총액신고서(2025)", 1),
    "07_business_income_withholding.json": ("재무/회계", "FIN-07", "사업소득 원천징수영수증", "사업소득 원천징수영수증", 1),
    "08_yearend_tax_settlement.json": ("재무/회계", "FIN-08", "소득·세액 공제신고서", "연말정산 소득·세액 공제신고서", 2),
    "09_audit_report.json": ("재무/회계", "FIN-09", "감사보고서", "감사보고서", 2),

    # 3. 경영/전략 (MGT) - 총 10건
    "01_partner_sales_analysis.json": ("경영/전략", "MGT-01", "거래처 매입매출현황 분석표", "거래처 매입매출현황 분석표", 1),

    # 4. 영업/제안 (SAL) - 총 30건
    "01_quote_and_invoice.json": ("영업/제안", "SAL-01", "견적서", "견적서·거래명세표 통합양식", 1),
    "02_design_quote.json": ("영업/제안", "SAL-01", "견적서", "표준 견적서", 1),
    "03_visit_log.json": ("영업/제안", "SAL-02", "거래처 방문일지", "거래처 방문일지", 1),

    # 5. 고객/거래처 (CUS) - 총 20건
    "01_nda.json": ("고객/거래처", "CUS-01", "비밀유지계약서", "표준 비밀유지계약서(NDA)", 2),
    "02_franchise_contract.json": ("고객/거래처", "CUS-02", "가맹계약서", "커피전문점 표준가맹계약서", 3),

    # 6. 법무/총무 (LEG) - 총 20건
    "01_commercial_lease.json": ("법무/총무", "LEG-01", "상가건물 임대차계약서", "상가건물 임대차 표준계약서(2024.5.8 개정)", 2),
    "02_standard_lease.json": ("법무/총무", "LEG-02", "표준임대차계약서", "표준임대차계약서", 2),
}

rows = []
code_counters = {}  # 소분류 코드별 일련번호(001~020) 카운터

for json_name, (major, minor_code, minor_name, template_label, default_pages) in FILE_MAPPING.items():
    # data/html 폴더 또는 현재 폴더에서 JSON 파일 찾기
    json_path = os.path.join(html_dir, json_name)
    if not os.path.exists(json_path):
        json_path = json_name
        
    if not os.path.exists(json_path):
        print(f"⚠️ 파일을 찾을 수 없습니다: {json_name}")
        continue

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = data.get("문서목록", [])
    for doc in docs:
        # 소분류별 순번 증가 (예: HR-01은 001~020까지 번호가 매겨짐)
        code_counters[minor_code] = code_counters.get(minor_code, 0) + 1
        seq_num = code_counters[minor_code]
        
        # 계획서 3절 약속 파일명 형식: FIN-03_손익계산서_007.png (공백은 언더바나 제거 처리)
        clean_minor_name = minor_name.replace(" ", "")
        img_filename = f"{minor_code}_{clean_minor_name}_{seq_num:03d}.png"
        
        rows.append({
            "file": img_filename,
            "template": template_label,
            "major": major,
            "minor_code": minor_code,
            "split": "dev",      # 2일 차 split.py 실행 전 기본값
            "variant": "clean",
            "pages": default_pages
        })

# labels.csv 저장
csv_path = "data/meta/labels.csv"
fieldnames = ["file", "template", "major", "minor_code", "split", "variant", "pages"]

with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ 총 {len(rows)}건의 라벨 데이터가 {csv_path}에 완벽하게 생성되었습니다!")