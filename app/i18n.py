"""화면 문구 번역 (한국어 ↔ 영어). 한국어 문구를 그대로 키로 쓰고, 영어 사전에 없으면 한국어를 그대로 보여 준다.
번역하지 않는 것: 파일 이름, 모델이 쓴 판단 근거, 사원 이름. 대분류·소분류·부서 이름은 아래 사전으로 바꾼다."""
import streamlit as st

EN = {
    # 메뉴 · 공통
    "대시보드": "Dashboard", "업로드": "Upload", "이력": "History", "문서 양식": "Forms", "설정": "Settings",
    "로그아웃": "Log out", "프로그램 설명": "Help", "한성부기들의 서류 정리방": "Hansung Turtles' Document Room",
    # 로그인
    "사번과 비밀번호를 입력해 시작하세요. 소속 부서에 맞는 문서를 먼저 보여드립니다.":
        "Enter your employee ID and password. Documents for your department are shown first.",
    "사번": "Employee ID", "비밀번호": "Password", "로그인": "Log in",
    "사번 또는 비밀번호가 올바르지 않습니다.": "Employee ID or password is incorrect.",
    # 대시보드
    "맵": "Map", "목록": "List", "보기": "View",
    "{n} {t}님, 주황색으로 빛나는 가운데 원이 <b>{d}</b> 담당 대분류입니다. 원을 누르면 그 대분류의 문서가 나옵니다.":
        "{n} {t}: the glowing orange circle in the center is the major category for <b>{d}</b>. Click a circle to see its documents.",
    "문서 {n}건": "{n} docs", "← 대분류 맵으로": "← Back to map", "우리 부서": "Our team",
    "분류 체계 밖 문서": "Outside the taxonomy",
    "이 대분류로 분류한 문서가 아직 없습니다.": "No documents classified under this category yet.",
    # 업로드
    "문서 업로드": "Upload documents", "분류": "Classify", "분류 결과": "Results", "업로드 메뉴": "Upload menu",
    "PNG, JPG, PDF, TXT, CSV, DOC, DOCX 문서를 올리면 대분류와 소분류를 판별합니다. 한 개든 여러 개든 한 번에 올릴 수 있습니다.":
        "Upload PNG, JPG, PDF, TXT, CSV, DOC or DOCX files to find their major and minor categories. One or many at a time.",
    "문서": "Documents",
    "호출 한도 보호를 위해 문서 사이에 {s:g}초씩 간격을 둡니다 (최소 약 {m:.1f}분).":
        "To protect the call limit, there is a {s:g}s gap between documents (about {m:.1f} min at least).",
    "분류하기": "Classify", "이어서 분류하기": "Resume classifying", "분류 중...": "Classifying...",
    "✕ 중단": "✕ Stop", "{i}/{n} 완료": "{i}/{n} done",
    "분류를 중단했습니다. {n}건은 이미 저장됐습니다. 「{b}」를 누르면 남은 문서부터 다시 시작합니다.":
        "Classification was stopped. {n} already saved. Press “{b}” to restart from the remaining documents.",
    "오래 걸리면 「✕ 중단」을 눌러 멈추고 다시 시작할 수 있습니다. 이미 끝난 문서는 저장됩니다. (지금 처리 중인 1건은 끝난 뒤 멈춥니다)":
        "If it takes too long, press “✕ Stop” and restart later. Finished documents are kept. (The document in progress finishes first.)",
    "아직 분류한 문서가 없습니다. 「분류」에서 문서를 올려 주세요.": "Nothing classified yet. Upload documents in “Classify”.",
    "{n}건 중 {e}건이 실패했습니다. 해당 문서의 「분류 근거」에서 원인을 확인하세요.":
        "{e} of {n} failed. Open “View evidence” on the document to see why.",
    "CSV 내려받기": "Download CSV",
    # 이름 겹침
    "파일 이름이 겹칩니다": "Duplicate file names",
    "이미 분류한 문서나 이번에 올린 다른 파일과 이름이 같습니다. 새 이름을 정해 주세요.":
        "These names match a classified document or another file in this batch. Please choose new names.",
    "「{n}」의 새 이름": "New name for “{n}”", "이 이름으로 분류": "Classify with these names",
    "이름 그대로 분류": "Keep names as they are", "이름이 비었거나 아직 겹칩니다: {n}": "Name is empty or still duplicated: {n}",
    # 근거 팝업
    "분류 근거": "Classification evidence", "분류 근거 보기": "View evidence", "분류 결과 ({i}/{n})": "Result ({i}/{n})",
    "◀ 이전": "◀ Prev", "다음 ▶": "Next ▶", "문서를 분류하지 못했습니다": "Could not classify this document",
    "다시 시도": "Retry", "페이지": "Page", "근거 영역 표시": "Show evidence boxes", "대분류": "Major", "소분류": "Minor",
    "확신도 {c:.0%}": "Confidence {c:.0%}", "판단 근거": "Reasons",
    "확신도가 기준보다 낮아 「기타」로 분류했습니다.": "Confidence was below the threshold, so it was placed in “Other”.",
    "기존 분류 체계에 없는 문서로 판단되어 「기타」로 분류했습니다.": "Not in the current taxonomy, so it was placed in “Other”.",
    "분류에 실패했습니다": "Classification failed", "파일: {f}": "File: {f}",
    # 목록
    "정렬": "Sort", "최신순": "Newest", "중요도순": "Starred first", "파일명": "File name", "확신도": "Confidence", "중요": "Star",
    "분류 실패": "Failed", "중요 표시": "Star", "중요 표시 취소": "Remove star",
    # 이력
    "분류 이력": "History", "내가 분류한 문서만 보입니다. 다른 사원의 이력과는 공유되지 않습니다.":
        "Only documents you classified are shown. History is not shared between employees.",
    "아직 분류 이력이 없습니다.": "No history yet.", "전체": "All", "상태": "Status", "파일명 검색": "Search file name",
    "조건에 맞는 이력이 없습니다.": "No history matches.",
    # 보안 현황 리포트
    "보안 현황": "Security status", "보안 현황 리포트": "Security status report",
    "내가 분류한 문서의 보안 등급과 대분류 현황입니다. 등급은 지금 등급표 기준이며, 「기타」 문서는 분류 체계 밖이라 등급이 없습니다.":
        "Security grades and major categories of documents you classified. Grades follow the current grade table; “Other” documents are outside the taxonomy and have no grade.",
    "기간": "Period", "종료일도 골라 주세요.": "Please pick an end date too.", "검사 문서": "Documents checked",
    "{n}건": "{n}", "이 기간에 분류한 문서가 없습니다.": "No documents were classified in this period.",
    "보안 등급별": "By security grade", "대분류별": "By major category",
    "요약 CSV 내려받기": "Download summary CSV", "문서별 CSV 내려받기": "Download per-document CSV",
    "검토 필요만 보기": "Needs review only",
    "「기타」로 빠졌거나, 분류에 실패했거나, 교차 확인에서 미확정인 문서만 보여줍니다. 담당자가 확인해야 하는 문서입니다.":
        "Shows only documents placed in “Other”, that failed to classify, or are unconfirmed by the cross-check. These need a person's check.",
    "확정 — Gemini와 Qwen이 같은 분류로 판단했습니다.": "Confirmed — Gemini and Qwen chose the same category.",
    "미확정 — 담당자 확인이 필요합니다. {why}": "Unconfirmed — a person needs to check. {why}",
    "Gemini와 Qwen의 분류가 서로 다릅니다.": "Gemini and Qwen chose different categories.",
    "Gemini의 확신도가 기준({th}) 미만입니다.": "Gemini's confidence is below the threshold ({th}).",
    "Gemini를 쓸 수 없어 Qwen 결과만 있습니다.": "Gemini was unavailable, so only the Qwen result exists.",
    "Qwen을 쓸 수 없어 Gemini 결과만 있습니다.": "Qwen was unavailable, so only the Gemini result exists.",
    "두 모델 모두 기존 분류 체계에 없는 문서(「기타」)로 판단했습니다.": "Both models judged it a document outside the taxonomy (“Other”).",
    "분류 체계 밖 문서, 담당자 확인 필요": "Document outside the taxonomy — needs a person's check",
    "확인 전까지 {g} 이상으로 취급합니다.": "Treated as {g} or higher until checked.",
    "분류가 확정되기 전까지 {g} 이상으로 취급합니다.": "Treated as {g} or higher until the category is confirmed.",
    "판단 근거는 모델이 쓴 원문(한국어)을 그대로 보여 줍니다.": "The reasons are shown as the model wrote them (in Korean).",
    "보안 등급": "Security grade", " (잠정)": " (provisional)", "등급 근거: {b}": "Grade basis: {b}",
    "기밀": "Secret", "대외비": "Confidential", "사내한정": "Internal only", "공개": "Public", "미산정": "Ungraded",
    "두 모델의 결과가 일치하지 않습니다.": "The two models' results do not match.",
    "Gemini 판단: {n} ({c}) · 확신도 {p:.0%}": "Gemini's pick: {n} ({c}) · confidence {p:.0%}",
    "교차 확인": "Cross-check", "미확정": "Unconfirmed",
    "우리 부서는 담당 대분류만, 전체는 모든 대분류의 이력을 보여줍니다.": "“Our team” shows our majors only; “All” shows every major.",
    "비워 두면 위의 '보기' 범위를 따릅니다. 고르면 그 대분류만 봅니다.": "Leave empty to follow “View”. Pick to show only those majors.",
    "확정": "Confirmed", "기타": "Other", "오류": "Error",
    # 문서 양식
    "회사에서 쓰는 모든 문서 양식을 대분류별로 찾아 내려받을 수 있습니다. 내려받은 파일은 한글(HWP)·PDF 원본 그대로이니 열어서 작성하세요.":
        "Find and download every company form by major category. Files are the original HWP/PDF, so open them to fill in.",
    "문서 이름, 코드, 설명으로 검색": "Search by name, code or description", "양식 검색": "Search forms",
    "조건에 맞는 양식이 없습니다.": "No forms match.", "양식 파일 준비 중": "Form file coming soon",
    "전체 ({n})": "All ({n})",
    # 설정
    "글자 크기": "Text size", "작게": "Small", "보통": "Normal", "크게": "Large", "매우 크게": "Extra large",
    "언어": "Language", "사용 방법 안내": "How-to tour",
    "매일 처음 열 때 보여주기": "Show on the first launch each day", "끄기": "Off",
    "사용 방법 안내 다시 보기": "Replay the tour",
    "설정은 내 계정에만 저장됩니다. 파일 이름과 AI가 쓴 판단 근거는 번역되지 않습니다.":
        "Settings are saved to your account only. File names and the AI's written reasons are not translated.",
    "다음 화면에서 안내가 시작됩니다.": "The tour starts on the next screen.",
    # 투어
    "건너뛰기": "Skip", "다음: 아무 곳이나 클릭": "Click anywhere to continue", "끝내기: 아무 곳이나 클릭": "Click anywhere to finish",
    "대시보드: 대분류 맵입니다. 우리 부서 대분류가 가운데에서 주황색으로 빛나고, 원을 누르면 그 문서들이 나옵니다.":
        "Dashboard: the major-category map. Your team's category glows orange in the center; click a circle to see its documents.",
    "업로드: 문서를 올려 분류합니다. 끝나면 분류 근거가 바로 팝업으로 나옵니다.":
        "Upload: classify documents. The evidence pops up as soon as it finishes.",
    "이력: 내가 분류한 문서 기록을 찾아봅니다.": "History: look up the documents you classified.",
    "문서 양식: 회사 문서 양식을 내려받습니다.": "Forms: download company document forms.",
    "설정: 글자 크기, 언어, 이 안내의 표시 여부를 바꿉니다.": "Settings: text size, language and this tour.",
    "도움말: 언제든 여기서 프로그램 설명을 볼 수 있습니다.": "Help: open the program guide here any time.",
    # 도움말 팝업
    "문서를 올리면, 어떤 문서인지 알려 줍니다": "Upload a document and we tell you what it is",
    "스캔본·사진·PDF를 AI가 직접 보고 대분류와 소분류를 고릅니다. 판단한 근거도 함께 보여 줍니다.":
        "AI looks at scans, photos and PDFs and picks the major and minor category, with its reasons.",
    "**① 올리기**  \n문서를 한 개든 여러 개든 올립니다.": "**① Upload**  \nOne document or many.",
    "**② 분류하기**  \n버튼을 누르면 대분류·소분류가 정해집니다.": "**② Classify**  \nPress the button to get categories.",
    "**③ 근거 보기**  \n문서 위에 판단 근거가 표시됩니다.": "**③ See evidence**  \nReasons are marked on the document.",
    "메뉴": "Menu", "알아 두세요": "Good to know",
    "- 분류 체계에 없거나 확신이 낮은 문서는 **「기타」** 로 분류됩니다.\n- **확신도**가 낮을수록 사람이 한 번 더 확인하는 것이 좋습니다.\n- 분류 이력은 **내 계정에만** 저장되고 다른 사원에게 보이지 않습니다.":
        "- Documents outside the taxonomy or with low confidence go to **“Other”**.\n- The lower the **confidence**, the more a human should double-check.\n- History is saved to **your account only**.",
    "| 메뉴 | 할 수 있는 일 |\n| --- | --- |\n| 대시보드 | 대분류 맵을 보고, 원을 눌러 그 대분류의 내 문서를 봅니다 |\n| 업로드 | 문서를 올려 분류하고, 결과에서 「분류 근거」를 봅니다 |\n| 이력 | 내가 분류한 문서 기록을 찾아봅니다 |\n| 보안 현황 | 기간을 골라 보안 등급별·대분류별 건수를 보고 CSV로 내려받습니다 |\n| 문서 양식 | 회사 문서 양식을 대분류별로 내려받습니다 |\n| 설정 | 글자 크기·언어·사용 방법 안내를 바꿉니다 |":
        "| Menu | What you can do |\n| --- | --- |\n| Dashboard | See the category map and open your documents |\n| Upload | Classify documents and view evidence |\n| History | Look up documents you classified |\n| Security status | Pick a period to see counts by grade and category, and download CSV |\n| Forms | Download company forms by category |\n| Settings | Text size, language, tour |",
    "분류 체계 보기": "Taxonomy", "HS리테일은 어떤 회사인가요?": "What is HS Retail?",
    "HS리테일은 이 프로젝트를 위해 설정한 가상의 회사입니다. 사번·문서·거래처는 모두 가상입니다.":
        "HS Retail is a fictional company for this project. IDs, documents and clients are all fictional.",
    # 소분류 100종 중 신규 75종 (HR-06~, FIN-11~, MGT-03~, SAL-07~, CUS-04~, LEG-04~)
    "복지제도 안내서": "Benefits guide", "인사발령통지서": "Personnel appointment notice",
    "위생교육 이수확인서": "Hygiene training certificate", "건강진단결과서": "Health checkup result",
    "교대근무표": "Shift schedule", "교육훈련 계획표": "Training plan", "포상 추천서": "Award recommendation",
    "자격증 취득 현황표": "Certification status table", "면접평가표": "Interview evaluation sheet", "직무기술서": "Job description",
    "외상매출금 연령분석표": "Receivables aging report", "환율 변동 손익표": "FX gain/loss statement",
    "판매장려금(리베이트) 정산서": "Sales rebate settlement", "입금확인증": "Deposit confirmation",
    "대출금 상환계획표": "Loan repayment plan", "이행보증보험증권": "Performance bond", "주주명부": "Shareholder register",
    "고정자산 감가상각 명세서": "Fixed asset depreciation schedule", "현금출납부": "Cash book", "어음관리대장": "Notes register",
    "퇴직연금 가입 내역서": "Retirement pension enrollment", "정부 보조금 교부 결정 통지서": "Government grant award notice",
    "SWOT 분석서": "SWOT analysis", "신제품 출시 계획서": "New product launch plan", "시장조사보고서": "Market research report",
    "프로젝트 일정표(간트차트)": "Project schedule (Gantt chart)", "업무 처리 매뉴얼": "Operating manual",
    "신규 물류센터 사업타당성 검토서": "Logistics center feasibility study", "사업장 현황표": "Site overview",
    "ESG 경영 보고서": "ESG report", "리스크 관리 대장": "Risk register", "조직도": "Organization chart",
    "회사 소개서": "Company profile", "신년 경영 방침서": "New year management policy",
    "제안서": "Proposal", "프로모션 기획서": "Promotion plan", "판촉 행사 결과표": "Promotion results",
    "상품 카탈로그": "Product catalog", "거래처 등급 기준표": "Client grade criteria", "진열 계획도": "Display plan",
    "행사 부스 운영 계획서": "Event booth plan", "시식 행사 안내 포스터": "Tasting event poster",
    "거래처 담당자 연락처 명부": "Client contact list", "파렛트 적재 기준표": "Pallet loading guide",
    "제품 라벨 시안": "Product label draft", "경쟁사 제품 비교표": "Competitor product comparison",
    "상품 규격서": "Product specification", "지역별 영업 담당 구역도": "Sales territory map",
    "거래처 등록신청서": "Client registration form", "거래처 신용평가표": "Client credit evaluation",
    "클레임 처리 보고서": "Claim handling report", "거래처 계약 갱신 통지서": "Contract renewal notice",
    "거래처 월간 소식지": "Client monthly newsletter", "거래처 출입 허가증": "Client access permit",
    "거래처 대표자 인감증명서": "Client representative seal certificate", "사업자등록증": "Business registration certificate",
    "거래처 위치 약도": "Client location map", "거래처 위촉장": "Client appointment letter",
    "거래처 감사장": "Client appreciation letter", "거래처 월간 행사 캘린더": "Client monthly event calendar",
    "산업재해 발생 보고서": "Industrial accident report", "HACCP 인증서": "HACCP certificate",
    "품질검사 성적서": "Quality inspection report", "원산지 증명서": "Certificate of origin",
    "수입식품 신고필증": "Imported food declaration", "차량운행일지": "Vehicle log", "비상 대피 안내도": "Evacuation plan",
    "위임장": "Power of attorney", "내용증명": "Certified mail notice", "사내 공고문": "Internal notice",
    "개인정보 수집·이용 동의서": "Personal data consent form", "문서수발대장": "Document register",
    "주차 허가증": "Parking permit", "법인 등기사항증명서": "Corporate registry certificate",
    "법률 자문 의견서": "Legal advice opinion",
    # 대분류 · 소분류 · 부서 · 직급
    "인사/채용": "HR / Recruiting", "재무/회계": "Finance / Accounting", "경영/전략": "Management / Strategy",
    "영업/제안": "Sales / Proposals", "고객/거래처": "Customers / Clients", "법무/총무": "Legal / General Affairs",
    "이력서": "Resume", "근로계약서": "Labor contract", "연봉 실수령액표": "Net salary table",
    "합계잔액시산표": "Trial balance", "원가명세서": "Cost statement", "손익계산서": "Income statement",
    "총수입금액 및 필요경비명세서": "Gross income & expense statement", "주요경비지출명세서": "Major expense statement",
    "소득총액신고서": "Total income report", "사업소득 원천징수영수증": "Business income withholding receipt",
    "소득·세액 공제신고서": "Income & tax deduction report", "감사보고서": "Audit report",
    "거래처 매입매출현황 분석표": "Client purchase/sales analysis", "견적서": "Quotation", "거래처 방문일지": "Client visit log",
    "비밀유지계약서": "NDA", "가맹계약서": "Franchise agreement", "상가건물 임대차계약서": "Commercial lease",
    "표준임대차계약서": "Standard lease",
    "재직증명서": "Employment certificate", "세금계산서": "Tax invoice", "연간사업계획서": "Annual business plan",
    "재고조사표": "Inventory count sheet", "발주서": "Purchase order", "납품확인서": "Delivery confirmation",
    "인사팀": "HR Team", "재무회계팀": "Finance Team", "경영기획팀": "Planning Team", "영업팀": "Sales Team",
    "고객지원팀": "Customer Support", "법무총무팀": "Legal Team", "팀장": "Team Lead", "과장": "Manager",
    "대리": "Assistant Manager", "사원": "Staff",
}


def lang() -> str:
    return (st.session_state.get("settings") or {}).get("lang", "ko")


def t(ko: str, **kw) -> str:
    """현재 언어의 문구. 영어 사전에 없으면 한국어 그대로. {자리표시자}는 kw로 채운다."""
    text = EN.get(ko, ko) if lang() == "en" else ko
    return text.format(**kw) if kw else text
