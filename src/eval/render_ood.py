"""OOD셋(분류 체계 밖 사내 문서) 3종 × 20건을 만든다: HTML → A4 PNG(200dpi 상당), data/meta/ood_labels.csv.

실행 (저장소 루트): python src/eval/render_ood.py          # 최종 OOD셋 (프롬프트 동결 후 1회만 평가)
                   python src/eval/render_ood.py --dev    # 개발용 OOD 6종 × 10건 (확신도 기준 정하기용)
- 종류: 법인카드지출결의서, 주간업무회의록, 부서간업무협조전 — 서로 다른 양식(결재란·사용내역 / 회의 개요·결정사항 / 수발신·회신란)
- 회사명은 본 데이터와 같은 '(주)에이치에스리테일'. 문서 안에 'OOD'·'분류 체계 외' 같은 정답 단서를 넣지 않는다.
- 내용은 시드 고정 난수로 고른다 (다시 실행해도 같은 이미지).
- 개발용 OOD는 최종 OOD 3종과 겉모습이 다른 종류로, 폴더·라벨·코드·시드를 모두 따로 둔다.
  최종 OOD셋을 보고 확신도 기준을 정하면 최종 평가가 오염되기 때문이다 (근거자료 7·10장).
  - DEVOOD-01·02 (휴가신청서, 비품구매요청서): 분류 체계와 닮지 않은 문서
  - DEVOOD-03~06: 기존 소분류와 겉모습·항목이 닮은 문서. 모델이 닮은 소분류로 확정하는지 보려고 만든다 (10-12 추가).
    발주서 ↔ SAL-01 견적서, 급여명세서 ↔ HR-03 연봉 실수령액표, 출장결과보고서 ↔ SAL-02 거래처 방문일지,
    부서별예산집행실적표 ↔ MGT-01 거래처 매입매출현황 분석표.
    지출결의서는 최종 OOD-01(법인카드지출결의서)과 같은 종류이고 「기타」 정의의 예시에도 있어 넣지 않는다.
    문서 안에 「기타」 정의 예시와 같은 단어(지출결의서·활동보고서·출장정산서)를 쓰지 않는다 (10-12, PR #55 리뷰).
  - 앞의 종류 뒤에 새 종류를 붙였으므로 DEVOOD-01·02 이미지는 이전과 같다 (같은 시드, 같은 순서).
- 새 개발용 OOD (--dev2): DEVOOD-07~12 6종 × 10건. 승격 6종(발주서 등)이 소분류가 되면 DEVOOD-03(발주서)이 더는 「기타」
  정답이 아니므로 그 뒤의 개발용 OOD로 쓴다. 사내 미등록 3종(시설점검일지·고객사과문발송대장·반품폐기확인서)과
  사외 3종(제과레시피카드·악보·택배운송장). 기존 개발용·최종 OOD와 폴더·라벨·코드·시드(11)를 모두 따로 둔다.
  설계는 docs/doc_candidate_pool.md 3절. 라벨의 company 열은 사내 문서 'HS리테일', 사외 문서 '사외'.
  택배운송장은 실제로는 소형 스티커라 A4 윗부분에 한 장을 놓았다.
"""
import argparse
import csv
import random
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "images" / "ood"
LABELS = ROOT / "data" / "meta" / "ood_labels.csv"
COMPANY = "(주)에이치에스리테일"
PER_FORM = 20
SEED = 42
A4_CSS = (794, 1123)  # A4를 96dpi CSS 픽셀로
SCALE = 1656 / 794  # 본 데이터(200dpi, 1656×2342)와 같은 크기로 저장

DEV_OUT_DIR = ROOT / "data" / "images" / "ood_dev"
DEV_LABELS = ROOT / "data" / "meta" / "ood_dev_labels.csv"
DEV_PER_FORM = 10
DEV_SEED = 7

DEV2_OUT_DIR = ROOT / "data" / "images" / "ood_dev2"
DEV2_LABELS = ROOT / "data" / "meta" / "ood_dev2_labels.csv"
DEV2_PER_FORM = 10
DEV2_SEED = 11

PEOPLE = ["김민수", "이서연", "박지훈", "최유진", "정다은", "강현우", "윤채원", "장도윤", "한지민", "오승현"]
TEAMS = ["영업1팀", "영업2팀", "재무회계팀", "물류운영팀", "인사총무팀", "마케팅팀", "구매팀", "가맹사업팀"]
MERCHANTS = [("한빛식당", "거래처 미팅 중식"), ("스타문구", "사무용품 구입"), ("코레일", "출장 KTX"),
             ("하늘택시", "거래처 방문 교통비"), ("그린마트", "행사 다과 구입"), ("오피스디포", "프린터 토너"),
             ("바다횟집", "협력사 간담회 석식"), ("한강주차장", "방문 주차비"), ("카페모아", "외부 회의 음료")]
AGENDAS = [("PB 신제품 입점 일정", "11월 2주 차 대형마트 3곳 동시 입점으로 확정"),
           ("물류센터 재고 실사", "월말 순환 실사를 분기 2회로 확대"),
           ("가맹점 판촉 행사", "HS커피 가을 시즌 음료 1+1 행사 10일간 진행"),
           ("거래처 단가 협상", "OEM 공장 원가 인상분 3% 중 1.5%만 반영"),
           ("신규 매장 인력 배치", "송파점 오픈 인력 4명을 영업2팀에서 지원"),
           ("고객 클레임 대응", "유통기한 표기 오류 건 회수 완료, 재발 방지 교육 실시"),
           ("분기 매출 점검", "3분기 매출 목표 대비 102% 달성")]
LEAVE_TYPES = [("연차", "개인 사유"), ("반차(오후)", "병원 진료"), ("경조휴가", "형제 결혼"),
               ("병가", "감기 몸살 치료"), ("연차", "가족 여행"), ("공가", "예비군 훈련")]
SUPPLIES = [("A4 복사용지", "80g, 2,500매/박스", 26_000), ("레이저 토너", "흑백, 정품", 89_000),
            ("모니터 받침대", "원목, 2단", 32_000), ("무선 마우스", "저소음", 18_000),
            ("화이트보드 마커", "4색 세트", 6_500), ("문서 보관함", "A4, 10칸", 45_000),
            ("USB 메모리", "64GB", 12_000), ("사무용 의자", "메쉬, 팔걸이", 159_000)]
REQUESTS = [("전산 시스템 권한 요청", "신규 입사자 2명의 ERP 조회 권한 부여"),
            ("행사 인력 지원 요청", "주말 판촉 행사 운영 인력 3명 지원"),
            ("물류 차량 배차 요청", "다음 주 화·목 용인 물류센터 추가 배차"),
            ("자료 제출 요청", "3분기 거래처별 매출 자료 제출"),
            ("교육 참석 요청", "정보보안 정기 교육 부서원 참석"),
            ("시설 점검 협조", "본사 4층 냉난방기 점검 시간 사무실 개방")]

SUPPLIERS = [("(주)한결제과", "214-81-3****"), ("대성음료(주)", "128-86-5****"), ("(주)푸른포장", "305-81-7****"),
             ("미래식품(주)", "617-81-2****"), ("(주)동원유통", "110-81-9****")]
GOODS = [("HS 버터쿠키", "200g×24입", 38_000), ("HS 초코칩쿠키", "180g×24입", 36_500), ("HS 오렌지주스", "1L×12병", 21_600),
         ("HS 탄산수 레몬", "500ml×20병", 14_000), ("쇼핑백(중)", "크라프트, 100매", 23_000), ("선물세트 케이스", "2단, 50개", 61_000),
         ("HS 웨하스", "150g×30입", 29_700), ("HS 아이스티", "340ml×24캔", 19_200)]
TRIP_PLACES = [("부산", "해운대 대형마트 본점"), ("대전", "중부 물류 협력사"), ("광주", "호남 가맹점 3곳"),
               ("대구", "OEM 제과 공장"), ("강릉", "동해안 휴게소 입점 매장"), ("제주", "제주 공항 면세 매장")]
BUDGET_ITEMS = ["판매촉진비", "광고선전비", "운반비", "소모품비", "교육훈련비", "여비교통비"]

FACILITY_ITEMS = ["소화기 압력 게이지", "비상구 유도등", "냉난방기 필터", "승강기 안전 점검 스티커", "전기 분전반 외관",
                  "주차장 조명", "화장실 급배수", "출입문 잠금장치", "비상 샤워·세안기", "지게차 충전 구역"]
# (제목, 기준 분량 개수, [(재료, 분량, 단위)], [순서])
RECIPES = [("레몬 파운드케이크", 8, [("박력분", 120, "g"), ("버터", 100, "g"), ("설탕", 90, "g"), ("달걀", 2, "개"), ("레몬 껍질", 1, "개")],
            ["버터와 설탕을 부드럽게 섞는다.", "달걀을 나누어 넣으며 섞는다.", "체 친 가루와 레몬 껍질을 넣고 가볍게 섞는다.", "틀에 붓고 오븐에서 굽는다."]),
           ("오트밀 쿠키", 12, [("오트밀", 100, "g"), ("박력분", 80, "g"), ("버터", 70, "g"), ("흑설탕", 60, "g"), ("건포도", 40, "g")],
            ["버터와 흑설탕을 섞는다.", "가루류와 오트밀, 건포도를 넣고 반죽한다.", "한 숟가락씩 떠서 팬에 올린다.", "노릇해질 때까지 굽는다."]),
           ("딸기잼 스콘", 6, [("중력분", 200, "g"), ("차가운 버터", 60, "g"), ("우유", 80, "ml"), ("설탕", 30, "g"), ("딸기잼", 50, "g")],
            ["가루와 차가운 버터를 손으로 비벼 섞는다.", "우유를 넣고 한 덩어리로 뭉친다.", "반죽을 접어 밀어 자른다.", "구운 뒤 딸기잼을 곁들인다."]),
           ("초코 브라우니", 9, [("다크초콜릿", 120, "g"), ("버터", 80, "g"), ("설탕", 100, "g"), ("달걀", 2, "개"), ("박력분", 60, "g")],
            ["초콜릿과 버터를 중탕으로 녹인다.", "설탕과 달걀을 섞는다.", "가루를 넣고 매끈하게 섞는다.", "틀에 부어 굽고 식힌 뒤 자른다."]),
           ("마들렌", 10, [("박력분", 100, "g"), ("버터", 90, "g"), ("설탕", 80, "g"), ("달걀", 2, "개"), ("꿀", 15, "g")],
            ["달걀과 설탕, 꿀을 섞는다.", "가루를 넣고 녹인 버터를 천천히 넣는다.", "반죽을 냉장고에서 쉬게 한다.", "틀에 80% 채워 굽는다."])]

BASE_CSS = """
body { font-family: 'Noto Sans CJK KR', 'Malgun Gothic', sans-serif; margin: 0; padding: 56px 60px; color: #111; }
h1 { text-align: center; font-size: 30px; letter-spacing: 6px; margin: 0 0 24px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border: 1px solid #333; padding: 8px 10px; }
th { background: #f0f0f0; font-weight: 600; }
.meta { font-size: 14px; margin-bottom: 16px; }
.right { text-align: right; } .center { text-align: center; }
.foot { margin-top: 40px; text-align: center; font-size: 16px; font-weight: 600; }
"""


def won(n: int) -> str:
    return f"{n:,}"


def approval_box(titles) -> str:
    head = "".join(f"<th style='width:70px'>{t}</th>" for t in titles)
    cells = "".join("<td style='height:52px'></td>" for _ in titles)
    return f"<table style='width:auto;margin-left:auto;margin-bottom:20px'><tr><th rowspan=2 style='width:28px'>결<br>재</th>{head}</tr><tr>{cells}</tr></table>"


def card_expense(i: int, rng: random.Random) -> str:
    who, team = rng.choice(PEOPLE), rng.choice(TEAMS)
    month = rng.randint(1, 9)
    items = rng.sample(MERCHANTS, rng.randint(3, 6))
    rows, total = "", 0
    for day, (shop, use) in zip(sorted(rng.sample(range(1, 28), len(items))), items):
        amt = rng.randrange(8_000, 180_000, 100)
        total += amt
        rows += f"<tr><td class=center>2026.{month:02d}.{day:02d}</td><td>{shop}</td><td>{use}</td><td class=right>{won(amt)}</td></tr>"
    return f"""<h1>법인카드 지출결의서</h1>
{approval_box(["담당", "팀장", "본부장"])}
<table class=meta>
<tr><th style='width:16%'>결의번호</th><td>HS-재무-2026-{i:04d}</td><th style='width:16%'>작성일</th><td>2026.{month:02d}.28</td></tr>
<tr><th>소속</th><td>{team}</td><th>사용자</th><td>{who}</td></tr>
<tr><th>카드번호</th><td>법인 ****-****-****-{rng.randint(1000, 9999)}</td><th>결제계좌</th><td>법인 운영자금 계좌</td></tr>
</table>
<table>
<tr><th style='width:18%'>사용일</th><th style='width:24%'>가맹점</th><th>사용 목적</th><th style='width:18%'>금액(원)</th></tr>
{rows}
<tr><th colspan=3>합 계</th><th class=right>{won(total)}</th></tr>
</table>
<p style='margin-top:24px;font-size:14px'>위 금액을 법인카드 사용 내역으로 결의하오니 승인하여 주시기 바랍니다.</p>
<div class=foot>{COMPANY}</div>"""


def weekly_minutes(i: int, rng: random.Random) -> str:
    team = rng.choice(TEAMS)
    attendees = rng.sample(PEOPLE, rng.randint(4, 6))
    agendas = rng.sample(AGENDAS, 3)
    month, day = rng.randint(1, 9), rng.randint(1, 27)
    body = "".join(
        f"<tr><td class=center>{n}</td><td>{a}</td><td>{d}</td></tr>" for n, (a, d) in enumerate(agendas, start=1))
    todos = "".join(
        f"<tr><td>{a} 후속 조치</td><td class=center>{rng.choice(attendees)}</td><td class=center>2026.{month:02d}.{min(day + 7, 28):02d}</td></tr>"
        for a, _ in agendas[:2])
    return f"""<h1>주간업무회의록</h1>
<table class=meta>
<tr><th style='width:16%'>회의 일시</th><td>2026.{month:02d}.{day:02d} (월) 09:30~10:30</td><th style='width:14%'>장소</th><td>본사 {rng.randint(3, 7)}층 회의실</td></tr>
<tr><th>주관 부서</th><td>{team}</td><th>작성자</th><td>{attendees[0]}</td></tr>
<tr><th>참석자</th><td colspan=3>{', '.join(attendees)}</td></tr>
</table>
<h3 style='font-size:16px;margin:22px 0 8px'>1. 논의 안건 및 결정 사항</h3>
<table><tr><th style='width:8%'>번호</th><th style='width:32%'>안건</th><th>결정 사항</th></tr>{body}</table>
<h3 style='font-size:16px;margin:22px 0 8px'>2. 다음 주 할 일</h3>
<table><tr><th>할 일</th><th style='width:18%'>담당</th><th style='width:20%'>기한</th></tr>{todos}</table>
<p style='margin-top:20px;font-size:13px;color:#444'>※ 회의록 수정 요청은 작성자에게 회의 후 2일 이내 전달</p>
<div class=foot>{COMPANY} {team}</div>"""


def coop_request(i: int, rng: random.Random) -> str:
    sender, receiver, cc = rng.sample(TEAMS, 3)
    title, detail = rng.choice(REQUESTS)
    month, day = rng.randint(1, 9), rng.randint(1, 20)
    return f"""<h1>업 무 협 조 전</h1>
<table class=meta>
<tr><th style='width:16%'>문서번호</th><td>HS-{sender}-2026-{i:03d}</td><th style='width:16%'>시행일자</th><td>2026.{month:02d}.{day:02d}</td></tr>
<tr><th>수 신</th><td>{receiver}장</td><th>발 신</th><td>{sender}장</td></tr>
<tr><th>참 조</th><td>{cc}</td><th>회신 기한</th><td>2026.{month:02d}.{day + 5:02d}</td></tr>
<tr><th>제 목</th><td colspan=3>{title}</td></tr>
</table>
<div style='border:1px solid #333;padding:18px 20px;min-height:260px;font-size:15px;line-height:1.9'>
1. 귀 부서의 업무 협조에 감사드립니다.<br>
2. 아래와 같이 {detail}을(를) 요청하오니 협조하여 주시기 바랍니다.<br>
<div style='text-align:center;margin:10px 0'>- 아 래 -</div>
 가. 요청 내용: {detail}<br>
 나. 요청 기간: 2026.{month:02d}.{day:02d} ~ 2026.{month:02d}.{day + 5:02d}<br>
 다. 담 당 자: {sender} {rng.choice(PEOPLE)} (내선 {rng.randint(200, 499)})<br>
</div>
<h3 style='font-size:15px;margin:22px 0 8px'>회신란</h3>
<table><tr><th style='width:20%'>처리 결과</th><td style='height:70px'></td></tr><tr><th>회신자</th><td></td></tr></table>
<div class=foot>{COMPANY} {sender}</div>"""


def leave_request(i: int, rng: random.Random) -> str:
    who, team = rng.choice(PEOPLE), rng.choice(TEAMS)
    rank = rng.choice(["사원", "대리", "과장", "차장"])
    kind, reason = rng.choice(LEAVE_TYPES)
    month, day = rng.randint(1, 9), rng.randint(1, 20)
    days = 0.5 if "반차" in kind else rng.randint(1, 5)
    end = day if days < 1 else day + int(days) - 1
    proxy = rng.choice([p for p in PEOPLE if p != who])
    return f"""<h1>휴 가 신 청 서</h1>
{approval_box(["담당", "팀장"])}
<table class=meta>
<tr><th style='width:16%'>소속</th><td>{team}</td><th style='width:16%'>직급</th><td>{rank}</td></tr>
<tr><th>성명</th><td>{who}</td><th>사번</th><td>HS{rng.randint(18, 26):02d}{rng.randint(100, 999)}</td></tr>
</table>
<table>
<tr><th style='width:20%'>휴가 종류</th><td>{kind}</td></tr>
<tr><th>기간</th><td>2026.{month:02d}.{day:02d} ~ 2026.{month:02d}.{end:02d} ({days}일)</td></tr>
<tr><th>사유</th><td style='height:80px'>{reason}</td></tr>
<tr><th>업무 대행자</th><td>{proxy}</td></tr>
<tr><th>비상 연락처</th><td>010-****-{rng.randint(1000, 9999)}</td></tr>
</table>
<p style='margin-top:36px;font-size:15px;text-align:center'>위와 같이 휴가를 신청합니다.</p>
<p style='text-align:center;font-size:15px'>2026년 {month}월 {max(day - 3, 1)}일</p>
<p style='text-align:right;font-size:15px;margin-right:40px'>신청인 {who} (인)</p>
<div class=foot>{COMPANY}</div>"""


def supply_request(i: int, rng: random.Random) -> str:
    who, team = rng.choice(PEOPLE), rng.choice([t for t in TEAMS if t != "구매팀"])
    month, day = rng.randint(1, 9), rng.randint(1, 20)
    items = rng.sample(SUPPLIES, rng.randint(2, 5))
    rows, total = "", 0
    for n, (name, spec, price) in enumerate(items, start=1):
        qty = rng.randint(1, 10)
        total += qty * price
        rows += (f"<tr><td class=center>{n}</td><td>{name}</td><td>{spec}</td><td class=center>{qty}</td>"
                 f"<td class=right>{won(price)}</td><td class=right>{won(qty * price)}</td></tr>")
    return f"""<h1>비품 구매 요청서</h1>
{approval_box(["요청자", "팀장", "구매팀"])}
<table class=meta>
<tr><th style='width:16%'>요청 부서</th><td>{team}</td><th style='width:16%'>요청자</th><td>{who}</td></tr>
<tr><th>요청일</th><td>2026.{month:02d}.{day:02d}</td><th>희망 납기</th><td>2026.{month:02d}.{day + 7:02d}</td></tr>
</table>
<table>
<tr><th style='width:7%'>번호</th><th style='width:22%'>품명</th><th>규격</th><th style='width:9%'>수량</th><th style='width:14%'>단가(원)</th><th style='width:15%'>금액(원)</th></tr>
{rows}
<tr><th colspan=5>합 계</th><th class=right>{won(total)}</th></tr>
</table>
<h3 style='font-size:15px;margin:22px 0 8px'>요청 사유</h3>
<div style='border:1px solid #333;padding:14px 16px;min-height:90px;font-size:14px'>{team} 업무용 비품 소진 및 교체 필요</div>
<div class=foot>{COMPANY} {team}</div>"""


def purchase_order(i: int, rng: random.Random) -> str:
    supplier, biz_no = rng.choice(SUPPLIERS)
    month, day = rng.randint(1, 9), rng.randint(1, 20)
    rows, supply_total = "", 0
    for n, (name, spec, price) in enumerate(rng.sample(GOODS, rng.randint(3, 6)), start=1):
        qty = rng.randint(5, 80)
        supply_total += qty * price
        rows += (f"<tr><td class=center>{n}</td><td>{name}</td><td>{spec}</td><td class=center>{qty}</td>"
                 f"<td class=right>{won(price)}</td><td class=right>{won(qty * price)}</td><td class=right>{won(qty * price // 10)}</td></tr>")
    tax = supply_total // 10
    return f"""<h1>발 주 서</h1>
{approval_box(["담당", "팀장", "구매팀장"])}
<table class=meta>
<tr><th style='width:16%'>발주번호</th><td>PO-2026-{i:04d}</td><th style='width:16%'>발주일자</th><td>2026.{month:02d}.{day:02d}</td></tr>
<tr><th>수 신</th><td>{supplier} 귀중</td><th>사업자번호</th><td>{biz_no}</td></tr>
<tr><th>발 주 처</th><td>{COMPANY} 구매팀</td><th>담당자</th><td>{rng.choice(PEOPLE)}</td></tr>
<tr><th>납기일</th><td>2026.{month:02d}.{day + 7:02d}</td><th>납품 장소</th><td>용인 물류센터</td></tr>
</table>
<p style='font-size:15px;margin:14px 0'>아래와 같이 발주하오니 납기 내 납품하여 주시기 바랍니다. 발주금액: <b>{won(supply_total + tax)}원</b> (부가세 포함)</p>
<table>
<tr><th style='width:6%'>번호</th><th>품명</th><th style='width:16%'>규격</th><th style='width:8%'>수량</th><th style='width:12%'>단가</th><th style='width:14%'>공급가액</th><th style='width:12%'>세액</th></tr>
{rows}
<tr><th colspan=5>합 계</th><th class=right>{won(supply_total)}</th><th class=right>{won(tax)}</th></tr>
</table>
<p style='margin-top:20px;font-size:13px'>※ 결제 조건: 납품 검수 후 익월 말 현금 결제 / 납품 시 거래명세서 동봉</p>
<div class=foot>{COMPANY}</div>"""


def pay_stub(i: int, rng: random.Random) -> str:
    who, team = rng.choice(PEOPLE), rng.choice(TEAMS)
    rank = rng.choice(["사원", "대리", "과장", "차장"])
    month = rng.randint(1, 9)
    base = rng.randrange(2_600_000, 4_800_000, 10_000)
    pays = [("기본급", base), ("식대", 200_000), ("직책수당", 0 if rank == "사원" else 150_000),
            ("연장근로수당", rng.randrange(0, 400_000, 10_000))]
    gross = sum(v for _, v in pays)
    health = int(base * 0.03545)
    income_tax = int(base * rng.uniform(0.02, 0.05)) // 10 * 10
    deducts = [("국민연금", int(base * 0.045)), ("건강보험", health), ("장기요양보험", int(health * 0.1295)),
               ("고용보험", int(gross * 0.009)), ("소득세", income_tax), ("지방소득세", income_tax // 10)]
    deduct_total = sum(v for _, v in deducts)
    body = ""
    for n, (d_name, d_amt) in enumerate(deducts):  # 공제 항목(6줄)이 지급 항목(4줄)보다 많아 남는 지급 칸은 비운다
        p_name, p_amt = pays[n] if n < len(pays) else ("", None)
        p_cell = "" if p_amt is None else won(p_amt)
        body += f"<tr><td>{p_name}</td><td class=right>{p_cell}</td><td>{d_name}</td><td class=right>{won(d_amt)}</td></tr>"
    return f"""<h1>급 여 명 세 서</h1>
<p class=center style='font-size:15px;margin-top:-10px'>2026년 {month}월 귀속 (지급일 2026.{month:02d}.25)</p>
<table class=meta>
<tr><th style='width:16%'>성명</th><td>{who}</td><th style='width:16%'>사번</th><td>HS{rng.randint(18, 26):02d}{rng.randint(100, 999)}</td></tr>
<tr><th>부서</th><td>{team}</td><th>직급</th><td>{rank}</td></tr>
</table>
<table>
<tr><th colspan=2>지급 항목</th><th colspan=2>공제 항목</th></tr>
{body}
<tr><th>지급 합계</th><th class=right>{won(gross)}</th><th>공제 합계</th><th class=right>{won(deduct_total)}</th></tr>
<tr><th colspan=2>실 지급액</th><th colspan=2 class=right>{won(gross - deduct_total)}</th></tr>
</table>
<p style='margin-top:24px;font-size:13px'>※ 귀하의 노고에 감사드립니다. 급여 문의는 인사총무팀(내선 210)으로 해 주세요.</p>
<div class=foot>{COMPANY}</div>"""


def trip_report(i: int, rng: random.Random) -> str:
    who, team = rng.choice(PEOPLE), rng.choice(TEAMS)
    city, place = rng.choice(TRIP_PLACES)
    month, day = rng.randint(1, 9), rng.randint(1, 20)
    nights = rng.randint(1, 3)
    plan = "".join(
        f"<tr><td class=center>2026.{month:02d}.{day + n:02d}</td><td>{place}</td><td>{a}</td></tr>"
        for n, (a, _) in enumerate(rng.sample(AGENDAS, nights + 1)))
    return f"""<h1>출 장 결 과 보 고 서</h1>
{approval_box(["담당", "팀장", "본부장"])}
<table class=meta>
<tr><th style='width:16%'>출장자</th><td>{team} {who}</td><th style='width:16%'>보고일</th><td>2026.{month:02d}.{day + nights + 2:02d}</td></tr>
<tr><th>출장 기간</th><td>2026.{month:02d}.{day:02d} ~ {day + nights:02d} ({nights}박 {nights + 1}일)</td><th>출장지</th><td>{city}</td></tr>
<tr><th>출장 목적</th><td colspan=3>{place} 현장 점검 및 협의</td></tr>
</table>
<h3 style='font-size:16px;margin:22px 0 8px'>1. 일정별 활동 내용</h3>
<table><tr><th style='width:18%'>일자</th><th style='width:30%'>방문처</th><th>주요 내용</th></tr>{plan}</table>
<h3 style='font-size:16px;margin:22px 0 8px'>2. 결과 및 건의 사항</h3>
<div style='border:1px solid #333;padding:14px 16px;min-height:110px;font-size:14px;line-height:1.8'>
{rng.choice(AGENDAS)[1]}. 후속 조치는 다음 주 팀 회의에서 공유 예정.</div>
<div class=foot>{COMPANY} {team}</div>"""


def budget_report(i: int, rng: random.Random) -> str:
    quarter = rng.randint(1, 3)
    rows, tot = "", [0, 0, 0]
    for team in rng.sample(TEAMS, 5):
        item = rng.choice(BUDGET_ITEMS)
        budget = rng.randrange(30_000_000, 200_000_000, 1_000_000)
        spent = int(budget * rng.uniform(0.6, 1.1)) // 10_000 * 10_000
        last = int(spent * rng.uniform(0.8, 1.2)) // 10_000 * 10_000
        tot = [tot[0] + budget, tot[1] + spent, tot[2] + last]
        rows += (f"<tr><td>{team}</td><td>{item}</td><td class=right>{won(budget)}</td><td class=right>{won(spent)}</td>"
                 f"<td class=right>{spent / budget:.1%}</td><td class=right>{won(last)}</td><td class=right>{spent / last - 1:+.1%}</td></tr>")
    return f"""<h1>부서별 예산 집행 실적표</h1>
<p class=center style='font-size:15px;margin-top:-10px'>2026년 {quarter}분기 (단위: 원)</p>
<table class=meta><tr><th style='width:16%'>작성 부서</th><td>재무회계팀</td><th style='width:16%'>작성일</th><td>2026.{quarter * 3 + 1:02d}.05</td></tr></table>
<table>
<tr><th>부서</th><th>예산 과목</th><th>배정 예산</th><th>집행액</th><th>집행률</th><th>전년 동기 집행액</th><th>전년 대비</th></tr>
{rows}
<tr><th colspan=2>합 계</th><th class=right>{won(tot[0])}</th><th class=right>{won(tot[1])}</th><th class=right>{tot[1] / tot[0]:.1%}</th>
<th class=right>{won(tot[2])}</th><th class=right>{tot[1] / tot[2] - 1:+.1%}</th></tr>
</table>
<p style='margin-top:20px;font-size:13px'>※ 집행률 100%를 넘은 부서는 다음 분기 예산 조정 시 사유서를 제출합니다.</p>
<div class=foot>{COMPANY} 재무회계팀</div>"""


FORMS = [("OOD-01", "법인카드지출결의서", card_expense),
         ("OOD-02", "주간업무회의록", weekly_minutes),
         ("OOD-03", "부서간업무협조전", coop_request)]
DEV_FORMS = [("DEVOOD-01", "휴가신청서", leave_request),
             ("DEVOOD-02", "비품구매요청서", supply_request),
             ("DEVOOD-03", "발주서", purchase_order),  # 아래 4종은 기존 소분류와 닮은 문서 (10-12 추가)
             ("DEVOOD-04", "급여명세서", pay_stub),
             ("DEVOOD-05", "출장결과보고서", trip_report),
             ("DEVOOD-06", "부서별예산집행실적표", budget_report)]


def facility_log(i: int, rng: random.Random) -> str:
    who, team = rng.choice(PEOPLE), rng.choice(["인사총무팀", "물류운영팀"])
    place = rng.choice(["본사 3층 사무실", "본사 지하 1층 주차장", "용인 물류센터 A동", "용인 물류센터 B동", "송파점 후방 창고"])
    month, day = rng.randint(1, 9), rng.randint(1, 27)
    rows = ""
    for n, item in enumerate(rng.sample(FACILITY_ITEMS, 6), start=1):
        ok = rng.random() < 0.75
        mark = "☑ 양호 &nbsp;☐ 조치필요" if ok else "☐ 양호 &nbsp;☑ 조치필요"
        note = "" if ok else rng.choice(["다음 주 교체 예정", "업체 방문 요청", "임시 조치 완료"])
        rows += f"<tr><td class=center>{n}</td><td>{item}</td><td class=center>{mark}</td><td>{note}</td></tr>"
    return f"""<h1>시설 점검 일지</h1>
{approval_box(["점검자", "팀장"])}
<table class=meta>
<tr><th style='width:16%'>점검 일시</th><td>2026.{month:02d}.{day:02d} {rng.randint(8, 16):02d}:00</td><th style='width:16%'>점검 구역</th><td>{place}</td></tr>
<tr><th>점검자</th><td>{team} {who}</td><th>날씨</th><td>{rng.choice(['맑음', '흐림', '비'])}</td></tr>
</table>
<table>
<tr><th style='width:7%'>번호</th><th style='width:34%'>점검 항목</th><th style='width:27%'>판정</th><th>조치 내용</th></tr>
{rows}
</table>
<h3 style='font-size:15px;margin:22px 0 8px'>특이 사항</h3>
<div style='border:1px solid #333;padding:14px 16px;min-height:90px;font-size:14px'>{rng.choice(['특이 사항 없음', '야간 조명 일부 점멸, 다음 점검 시 재확인', '냉난방기 소음 발생, 업체 문의 예정'])}</div>
<div class=foot>{COMPANY} {team}</div>"""


def apology_ledger(i: int, rng: random.Random) -> str:
    team = rng.choice(["고객지원팀", "가맹사업팀"])
    month = rng.randint(1, 9)
    rows = ""
    for n, day in enumerate(sorted(rng.sample(range(1, 28), rng.randint(6, 9))), start=1):
        surname = rng.choice(["김", "이", "박", "최", "정", "강", "윤", "장"])
        reason = rng.choice(["포장 파손 상태로 수령", "배송 3일 지연", "주문과 다른 맛 발송", "매장 응대 불친절", "행사 쿠폰 적용 누락"])
        way = rng.choice(["문자", "이메일", "우편", "전화"])
        rows += (f"<tr><td class=center>{month:02d}{day:02d}-{n:02d}</td><td class=center>2026.{month:02d}.{day:02d}</td>"
                 f"<td class=center>{surname}○○</td><td>{reason}</td><td class=center>{way}</td><td class=center>{rng.choice(PEOPLE)}</td></tr>")
    return f"""<h1>고객 사과문 발송 대장</h1>
<p class=center style='font-size:15px;margin-top:-10px'>2026년 {month}월분</p>
<table class=meta><tr><th style='width:16%'>관리 부서</th><td>{team}</td><th style='width:16%'>보관 기간</th><td>3년</td></tr></table>
<table>
<tr><th style='width:13%'>접수번호</th><th style='width:14%'>발송일</th><th style='width:11%'>고객</th><th>사유</th><th style='width:10%'>발송 방법</th><th style='width:11%'>발송자</th></tr>
{rows}
</table>
<p style='margin-top:20px;font-size:13px'>※ 고객 성명은 성만 표기하고 연락처는 별도 시스템에서 관리합니다.</p>
<div class=foot>{COMPANY} {team}</div>"""


def return_disposal(i: int, rng: random.Random) -> str:
    supplier, biz_no = rng.choice(SUPPLIERS)
    month, day = rng.randint(1, 9), rng.randint(1, 25)
    rows, total = "", 0
    for n, (name, spec, price) in enumerate(rng.sample(GOODS, rng.randint(2, 4)), start=1):
        qty = rng.randint(1, 12)
        total += qty * price
        how = rng.choice(["폐기", "반송", "폐기"])
        rows += (f"<tr><td class=center>{n}</td><td>{name}</td><td>{spec}</td><td class=center>{qty}</td>"
                 f"<td class=right>{won(price)}</td><td class=right>{won(qty * price)}</td><td class=center>{how}</td></tr>")
    reason = rng.choice(["유통기한 경과", "포장 파손", "운송 중 변형", "이물 신고 접수"])
    return f"""<h1>반품·폐기 확인서</h1>
{approval_box(["담당", "팀장", "물류센터장"])}
<table class=meta>
<tr><th style='width:16%'>확인번호</th><td>RD-2026-{i:04d}</td><th style='width:16%'>처리일자</th><td>2026.{month:02d}.{day:02d}</td></tr>
<tr><th>거래처</th><td>{supplier}</td><th>사업자번호</th><td>{biz_no}</td></tr>
<tr><th>사 유</th><td>{reason}</td><th>처리 장소</th><td>용인 물류센터</td></tr>
</table>
<table>
<tr><th style='width:6%'>번호</th><th>품명</th><th style='width:16%'>규격</th><th style='width:8%'>수량</th><th style='width:12%'>단가</th><th style='width:14%'>금액</th><th style='width:10%'>처리</th></tr>
{rows}
<tr><th colspan=5>합 계</th><th class=right>{won(total)}</th><th></th></tr>
</table>
<p style='margin-top:24px;font-size:14px'>위 물품을 확인 후 표시된 방법으로 처리하였음을 확인합니다.</p>
<table style='width:60%;margin-left:auto;margin-top:12px'><tr><th style='width:30%'>확인자</th><td style='height:44px'></td></tr><tr><th>입회자</th><td style='height:44px'></td></tr></table>
<div class=foot>{COMPANY}</div>"""


def recipe_card(i: int, rng: random.Random) -> str:  # 사외 문서: 회사명·결재란 없음
    title, unit_servings, ingredients, steps = rng.choice(RECIPES)
    scale = rng.choice([1, 2])
    rows = "".join(f"<tr><td>{name}</td><td class=right>{amt * scale:g}{unit}</td></tr>" for name, amt, unit in ingredients)
    step_html = "".join(f"<li style='margin-bottom:8px'>{s}</li>" for s in steps)
    return f"""<h1 style='letter-spacing:2px'>{title}</h1>
<p class=center style='font-size:15px;margin-top:-10px'>{unit_servings * scale}개 분량 · 준비 {rng.choice([15, 20, 30])}분 · 굽기 {rng.choice([12, 18, 25, 35])}분 · 오븐 {rng.choice([170, 180, 190])}℃</p>
<h3 style='font-size:17px;margin:24px 0 8px'>재료</h3>
<table style='width:60%'><tr><th>재료</th><th style='width:35%'>분량</th></tr>{rows}</table>
<h3 style='font-size:17px;margin:24px 0 8px'>만드는 순서</h3>
<ol style='font-size:15px;line-height:1.8;padding-left:22px'>{step_html}</ol>
<p style='margin-top:24px;font-size:13px;color:#555'>Tip. {rng.choice(['버터는 미리 실온에 꺼내 둔다.', '반죽은 30분 이상 냉장 휴지한다.', '식힌 뒤 밀폐 용기에 보관하면 3일간 맛이 유지된다.'])}</p>"""


def sheet_music(i: int, rng: random.Random) -> str:  # 사외 문서: 가상의 곡, 오선 위에 음표만 무작위 배치
    title = rng.choice(["아침 산책", "봄날의 왈츠", "골목길 노래", "푸른 저녁", "바람의 언덕", "작은 정원"])
    composer = rng.choice(PEOPLE)
    beats = rng.choice([("4", "4"), ("3", "4")])
    systems = ""
    for s in range(5):
        y0 = 40 + s * 170
        lines = "".join(f"<line x1=10 x2=670 y1={y0 + k * 12} y2={y0 + k * 12} stroke=#111 />" for k in range(5))
        bars = "".join(f"<line x1={x} x2={x} y1={y0} y2={y0 + 48} stroke=#111 />" for x in (10, 175, 340, 505, 670))
        notes = ""
        for k in range(12):
            x = 40 + k * 52 + (k // 3) * 8
            step = rng.randint(-2, 9)  # 0 = 맨 아래 줄, 반음계 칸 단위
            y = y0 + 48 - step * 6
            notes += f"<ellipse cx={x} cy={y} rx=7 ry=5 fill=#111 transform='rotate(-20 {x} {y})' />"
            notes += (f"<line x1={x + 6} x2={x + 6} y1={y} y2={y - 34} stroke=#111 />" if step < 5
                      else f"<line x1={x - 6} x2={x - 6} y1={y} y2={y + 34} stroke=#111 />")
        systems += lines + bars + notes
    return f"""<h1 style='letter-spacing:2px;margin-bottom:6px'>{title}</h1>
<p style='text-align:right;font-size:15px;margin:0 20px 14px 0'>작곡 {composer}</p>
<p style='font-size:15px;margin:0 0 6px 10px'>♩ = {rng.choice([72, 88, 96, 108])} &nbsp; {beats[0]}/{beats[1]}</p>
<svg width=690 height=880 viewBox='0 0 690 880' xmlns='http://www.w3.org/2000/svg'>{systems}</svg>"""


def waybill(i: int, rng: random.Random) -> str:  # 사외 문서: 택배 운송장 한 장을 A4 윗부분에 놓는다 (실제는 소형 스티커)
    no = "".join(str(rng.randint(0, 9)) for _ in range(12))
    surname = lambda: rng.choice(["김", "이", "박", "최", "정", "강", "윤", "장"])
    goods = rng.choice(["과자 선물세트", "수제 쿠키 상자", "음료 세트", "건과일 모음", "베이커리 소포장"])
    bars = "".join(f"<rect x={x} y=0 width={rng.choice([2, 3, 4])} height=60 fill=#111 />" for x in range(0, 300, 7))
    month, day = rng.randint(1, 9), rng.randint(1, 27)
    return f"""<div style='border:2px solid #111;padding:18px 20px;margin-top:10px'>
<div style='display:flex;justify-content:space-between;align-items:center;font-size:22px;font-weight:700'><span>바른택배</span><span>{no[:4]}-{no[4:8]}-{no[8:]}</span></div>
<svg width=300 height=60 style='margin:10px 0'>{bars}</svg>
<table style='font-size:14px'>
<tr><th style='width:14%'>보내는 분</th><td>{surname()}○○ &nbsp; 010-****-{rng.randint(1000, 9999)}</td><th style='width:12%'>접수일</th><td>2026.{month:02d}.{day:02d}</td></tr>
<tr><th>받는 분</th><td>{surname()}○○ &nbsp; 010-****-{rng.randint(1000, 9999)}</td><th>운임</th><td>{won(rng.choice([3500, 4000, 5000, 6000]))}원 ({rng.choice(['선불', '착불'])})</td></tr>
<tr><th>주 소</th><td colspan=3>{rng.choice(['서울 송파구', '경기 용인시', '부산 해운대구', '대전 유성구', '광주 서구'])} {rng.randint(1, 99)}길 {rng.randint(1, 120)}</td></tr>
<tr><th>품 목</th><td>{goods}</td><th>수량</th><td>{rng.randint(1, 3)}박스</td></tr>
<tr><th>배송 메모</th><td colspan=3>{rng.choice(['문 앞에 놓아 주세요', '부재 시 경비실 보관', '깨지기 쉬운 물품'])}</td></tr>
</table></div>"""


DEV2_FORMS = [("DEVOOD-07", "시설점검일지", facility_log),
              ("DEVOOD-08", "고객사과문발송대장", apology_ledger),
              ("DEVOOD-09", "반품폐기확인서", return_disposal),
              ("DEVOOD-10", "제과레시피카드", recipe_card),
              ("DEVOOD-11", "악보", sheet_music),
              ("DEVOOD-12", "택배운송장", waybill)]
DEV2_SOURCE = {"DEVOOD-07": "HS리테일", "DEVOOD-08": "HS리테일", "DEVOOD-09": "HS리테일",
               "DEVOOD-10": "사외", "DEVOOD-11": "사외", "DEVOOD-12": "사외"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dev", action="store_true", help="개발용 OOD 6종 × 10건을 따로 만든다 (최종 OOD셋은 그대로)")
    parser.add_argument("--dev2", action="store_true", help="새 개발용 OOD(DEVOOD-07~12) 6종 × 10건을 따로 만든다")
    args = parser.parse_args()
    if args.dev2:
        render(DEV2_FORMS, DEV2_PER_FORM, DEV2_SEED, DEV2_OUT_DIR, DEV2_LABELS, strict=True)
    elif args.dev:
        render(DEV_FORMS, DEV_PER_FORM, DEV_SEED, DEV_OUT_DIR, DEV_LABELS)
    else:
        render(FORMS, PER_FORM, SEED, OUT_DIR, LABELS)


def render(forms, per_form: int, seed: int, out_dir: Path, labels: Path, strict: bool = False):
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):  # 이전 버전 이미지(정답 단서 포함)를 남기지 않는다
        old.unlink()
    rng = random.Random(seed)
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": A4_CSS[0], "height": A4_CSS[1]}, device_scale_factor=SCALE)
        for code, title, build in forms:
            for i in range(1, per_form + 1):
                html = f"<!DOCTYPE html><html lang=ko><head><meta charset=utf-8><style>{BASE_CSS}</style></head><body>{build(i, rng)}</body></html>"
                page.set_content(html)
                if strict and page.evaluate("document.documentElement.scrollHeight") > A4_CSS[1]:
                    raise SystemExit(f"A4 한 장을 넘칩니다: {code} {title} {i}번")
                name = f"{code}_{title}_{i:03d}.png"
                page.screenshot(path=str(out_dir / name))  # A4 한 장 크기로 자름
                rows.append({"file": name, "ood_code": code, "title": title, "company": DEV2_SOURCE.get(code, "HS리테일"),
                             "expected_status": "pending_review"})
        browser.close()
    with labels.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"OOD 이미지 {len(rows)}장 → {out_dir}, 라벨 → {labels}")


if __name__ == "__main__":
    main()
