"""새 소분류 6종(재직증명서·세금계산서·연간사업계획서·재고조사표·발주서·납품확인서)의 문서를 만든다.
내용(코드가 계산) → HTML(Jinja2) → A4 PNG(1656×2342), 라벨 CSV.

실행 (저장소 루트): python src/eval/render_new_minors.py [--only 재직증명서,발주서]
- B안: 6종 모두 양식 2종 × 10건 (연간사업계획서·재고조사표의 양식 2는 10/31 백엔드 1 요청으로 추가) (총 100건).
  같은 소분류의 양식 2종은 레이아웃·항목 구성이 다르다. 금액만 바꾼 복제가 아니라 항목 수·품목·거래처·날짜가 문서마다 다르다.
- 번호 끝자리 규칙(split.py와 같음): 1 → fewshot, 2~5 → dev, 6~9와 0 → test. 시험용(test) 이미지는 만들기만 하고 열지 않는다.
- 난수는 문서마다 고정 시드라 다시 실행해도 같은 결과다. 합계·세액은 코드가 계산하고 assert로 확인한다.
- 라벨은 labels.csv가 아니라 labels_new_minors.csv에 쓴다 (분류 체계 PR 전까지 기존 평가에 영향을 주지 않기 위해).
- 코드·대분류는 가안이다 (10/29 회의에서 확정, taxonomy.yaml은 아직 바꾸지 않았다).
- 회사·사람·사업자번호는 모두 지어낸 값이다. 실제 사업자번호·주민번호가 아니다.
"""
import argparse
import csv
import datetime
import json
import random
from pathlib import Path

from jinja2 import Template
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
JSON_OUT = ROOT / "data" / "html" / "new_minors.json"
IMG_DIR = ROOT / "data" / "images" / "new"
LABELS_OUT = ROOT / "data" / "meta" / "labels_new_minors.csv"
A4_CSS = (794, 1123)
SCALE = 1656 / 794

# 이름: (코드, 대분류 코드, 대분류, 양식 수). ponytail: 코드는 가안 (기존 코드 다음 번호)
MINORS = {
    "재직증명서": ("HR-04", "HR", "인사/채용", 2),
    "세금계산서": ("FIN-10", "FIN", "재무/회계", 2),
    "연간사업계획서": ("MGT-02", "MGT", "경영/전략", 2),
    "재고조사표": ("SAL-03", "SAL", "영업/제안", 2),
    "발주서": ("SAL-04", "SAL", "영업/제안", 2),
    "납품확인서": ("SAL-05", "SAL", "영업/제안", 2),
}

HS = {"상호": "(주)에이치에스리테일", "등록번호": "214-86-10325", "대표자": "한도윤", "주소": "서울특별시 강서구 마곡중앙로 118",
      "업태": "도소매", "종목": "제과·음료 유통", "전화": "02-6670-4100"}
PARTNERS = [
    ("한빛유통(주)", "대표 오세진", "경기도 성남시 분당구 판교로 256", "도소매", "식품"),
    ("새봄푸드 주식회사", "대표 임하윤", "인천광역시 남동구 능허대로 702", "제조", "제과"),
    ("대양식품(주)", "대표 정우성", "대전광역시 유성구 테크노중앙로 45", "도소매", "식자재"),
    ("청명음료상사", "대표 문지안", "경기도 용인시 처인구 백옥대로 1043", "도소매", "음료"),
    ("미소마트 유한회사", "대표 배서준", "부산광역시 해운대구 센텀남대로 35", "소매", "슈퍼마켓"),
    ("(주)푸른들상회", "대표 신예린", "광주광역시 북구 첨단과기로 123", "도소매", "식품"),
    ("달콤제과(주)", "대표 곽민재", "경기도 부천시 길주로 210", "제조", "베이커리"),
    ("동행유통 주식회사", "대표 서지후", "충청북도 청주시 흥덕구 오송생명로 78", "도소매", "식품"),
    ("해든카페푸드", "대표 노다은", "경기도 고양시 일산동구 중앙로 1275", "서비스", "카페 납품"),
    ("(주)온누리식자재", "대표 류시우", "강원특별자치도 원주시 시청로 60", "도소매", "식자재"),
]
# (품명, 단위, 규격, 단가)
ITEMS = [
    ("강력밀가루", "포", "20kg", 27800), ("박력분", "포", "20kg", 26400), ("무가당 생크림", "박스", "1L×12", 84000),
    ("무염버터", "박스", "450g×20", 298000), ("카카오 초콜릿칩", "봉", "1kg", 16800), ("바닐라 에센스", "병", "500ml", 21500),
    ("백설탕", "포", "15kg", 23900), ("아몬드슬라이스", "봉", "500g", 12400), ("생수 500ml", "박스", "20입", 7600),
    ("탄산음료 250ml 캔", "박스", "30입", 19800), ("오렌지주스 1L", "박스", "12입", 18300), ("블렌드 원두", "봉", "1kg", 23400),
    ("우유 900ml", "박스", "10입", 21000), ("쿠키 선물세트", "박스", "24입", 42500), ("에너지바", "박스", "40입", 35200),
    ("냉동 크루아상 생지", "박스", "60개", 64000), ("포장용 쇼핑백(중)", "묶음", "100매", 9800), ("유산지", "권", "500매", 11400),
    ("딸기잼", "통", "3kg", 18700), ("미니 머핀 믹스", "봉", "5kg", 31500),
]
CENTERS = ["용인물류센터", "김포물류센터", "대전물류센터", "부산물류센터"]
DEPTS = ["영업1팀", "영업2팀", "구매팀", "재무회계팀", "물류운영팀", "품질관리팀", "마케팅팀", "인사총무팀", "가맹사업팀", "상품기획팀"]
RANKS = ["사원", "주임", "대리", "과장", "차장", "부장"]
NAMES = ["한서윤", "정민재", "오하늘", "윤태오", "임수현", "문지호", "배도현", "노지안", "서하린", "하승우", "강민서", "조은우",
         "백시현", "장유진", "권도영", "송지아", "유재민", "홍서진", "전하준", "안소율"]
GU = ["강서구", "마포구", "송파구", "성동구", "영등포구", "관악구", "노원구", "서초구"]
ROAD = ["가로공원로", "양화로", "올림픽로", "왕십리로", "여의대방로", "봉천로", "동일로", "반포대로"]


def won(n: int) -> str:
    return f"{n:,}"


def date(rng: random.Random, y: int, m1: int = 1, m2: int = 12) -> str:
    return f"{y}.{rng.randint(m1, m2):02d}.{rng.randint(1, 28):02d}"


def biz_no(rng: random.Random) -> str:
    return f"{rng.randint(100, 899)}-{rng.randint(10, 99)}-{rng.randint(10000, 99999)}"


def partner(rng: random.Random) -> dict:
    name, rep, addr, kind, item = rng.choice(PARTNERS)
    return {"상호": name, "대표자": rep.replace("대표 ", ""), "주소": addr, "업태": kind, "종목": item, "등록번호": biz_no(rng),
            "전화": f"0{rng.choice([31, 32, 42, 51, 62])}-{rng.randint(200, 899)}-{rng.randint(1000, 9999)}"}


def pick_items(rng: random.Random, lo: int, hi: int) -> list[dict]:
    """품목 lo~hi개: 수량과 단가(±5% 변동)를 문서마다 다르게 정한다."""
    rows = []
    for name, unit, spec, price in rng.sample(ITEMS, rng.randint(lo, hi)):
        qty = rng.choice([2, 3, 5, 8, 10, 12, 15, 20, 24, 30, 40, 50])
        unit_price = round(price * rng.uniform(0.95, 1.05), -2)
        rows.append({"품명": name, "단위": unit, "규격": spec, "수량": qty, "단가": int(unit_price), "금액": int(unit_price) * qty})
    return rows


def money(rows: list[dict]) -> dict:
    supply = sum(r["금액"] for r in rows)
    tax = supply // 10
    assert supply > 0 and tax * 10 <= supply < (tax + 1) * 10
    return {"공급가액": supply, "세액": tax, "합계": supply + tax}


def fmt_rows(rows: list[dict], keys=("단가", "금액")) -> list[dict]:
    return [dict(r, **{k: won(r[k]) for k in keys if k in r}) for r in rows]


# ---------------------------------------------------------------- 재직증명서
def build_cert(rng: random.Random, seq: int, form: int) -> dict:
    y0 = rng.randint(2012, 2025)
    start = f"{y0}.{rng.randint(1, 12):02d}.{rng.randint(1, 28):02d}"
    issue = date(rng, 2026, 1, 10)
    months = (2026 - y0) * 12 + int(issue[5:7]) - int(start[5:7]) - (int(issue[8:]) < int(start[8:]))  # 입사일~발급일 만 개월 수
    leave = rng.choice([None, None, f"{min(y0 + 3, 2025)}.03.01 ~ {min(y0 + 3, 2025)}.12.31 (육아휴직)"])
    purposes = [("금융기관 제출용", "신한은행 강서지점"), ("관공서 제출용", "강서구청 민원여권과"), ("비자 발급용", "대사관 영사과"),
                ("어학시험 접수용", "한국어능력평가원"), ("임대차 계약 제출용", "공인중개사무소"), ("보험 가입용", "한국생명보험(주)")]
    use, to = rng.choice(purposes)
    d = {
        "형식": form, "발급번호": f"HS-{2026}-{rng.randint(100, 999):03d}", "성명": rng.choice(NAMES), "생년월일": f"{rng.randint(1975, 2000)}.{rng.randint(1, 12):02d}.{rng.randint(1, 28):02d}",
        "주소": f"서울특별시 {rng.choice(GU)} {rng.choice(ROAD)} {rng.randint(3, 190)}, {rng.randint(101, 1504)}호",
        "소속": rng.choice(DEPTS), "직위": rng.choice(RANKS), "입사일": start, "근속": f"{months // 12}년 {months % 12}개월",
        "용도": use, "제출처": to, "발급일": issue,"확인번호": f"{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
        "담당업무": rng.choice(["수도권 대형마트 거래처 영업 관리", "원부자재 구매 및 공급사 관리", "물류센터 입출고 및 재고 관리", "제품 품질 검사 및 식품 안전 관리",
                              "월 결산 및 세무 신고 지원", "신제품 기획 및 프로모션 운영", "가맹점 운영 지원 및 교육"]),
        "휴직": leave or "해당 없음", "회사": HS,
    }
    d["연번"] = seq
    return d


# ---------------------------------------------------------------- 세금계산서
def build_tax(rng: random.Random, seq: int, form: int) -> dict:
    buyer_is_hs = rng.random() < 0.3
    other = partner(rng)
    seller, buyer = (other, HS) if buyer_is_hs else (HS, other)
    rows = pick_items(rng, 2, 5 if form == 1 else 6)
    m = money(rows)
    d = {"형식": form, "공급자": seller, "공급받는자": buyer, "작성일": date(rng, 2026), "품목": rows, **m,
         "승인번호": f"2026{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}-{rng.randint(10000000, 99999999)}-{rng.randint(10000000, 99999999)}",
         "영수청구": rng.choice(["영수", "청구"]), "결제": rng.choice(["외상미수금", "현금", "어음", "수표"]),
         "일련번호": rng.randint(1000, 9999), "권": rng.randint(1, 9), "호": rng.randint(10, 99)}
    for r in rows:
        r["세액"] = r["금액"] // 10  # 단가가 100원 단위라 줄별 세액이 딱 떨어진다
    assert sum(r["세액"] for r in rows) == d["세액"]
    d["품목"] = fmt_rows(rows, keys=("단가", "금액", "세액"))
    d["월일"] = [f"{d['작성일'][5:7]}/{d['작성일'][8:]}"] * len(rows)
    for k in ("공급가액", "세액", "합계"):
        d[f"{k}_표시"] = won(d[k])
    return d


# ---------------------------------------------------------------- 발주서
def build_po(rng: random.Random, seq: int, form: int) -> dict:
    supplier = partner(rng)
    rows = pick_items(rng, 3, 7)
    m = money(rows)
    order_date = date(rng, 2026, 1, 11)
    due = f"{order_date[:5]}{min(int(order_date[5:7]) + 1, 12):02d}.{rng.randint(1, 28):02d}"
    d = {"형식": form, "발주번호": f"PO-2026-{rng.randint(100, 999):04d}", "발주일": order_date, "납기일": due, "공급처": supplier, "발주처": HS,
         "담당자": rng.choice(NAMES), "납품장소": rng.choice(CENTERS), "결제조건": rng.choice(["납품 후 익월 말일 현금", "납품 후 30일 이내 계좌이체", "월 마감 후 15일 어음", "선결제 후 납품"]),
         "특기사항": rng.choice(["유통기한 잔여 70% 이상 제품만 납품", "냉장 제품은 5℃ 이하 차량으로 배송", "포장 파손 시 전량 반품", "납기 지연 시 사전 통보 필수", "인증서(HACCP) 사본 첨부"]),
         "품목": fmt_rows(rows), **m}
    for k in ("공급가액", "세액", "합계"):
        d[f"{k}_표시"] = won(d[k])
    return d


# ---------------------------------------------------------------- 납품확인서
def build_delivery(rng: random.Random, seq: int, form: int) -> dict:
    to = partner(rng)
    day = date(rng, 2026, 1, 11)
    rows = []
    for name, unit, spec, _ in rng.sample(ITEMS, rng.randint(3, 6)):
        expiry = (datetime.date(2026, int(day[5:7]), int(day[8:])) + datetime.timedelta(days=rng.randint(60, 240))).strftime("%Y.%m.%d")  # 납품일 이후
        ordered = rng.choice([5, 10, 12, 20, 24, 30, 40])
        got = ordered - rng.choice([0, 0, 0, 0, 1, 2])
        bad = rng.choice([0, 0, 0, 1])
        rows.append({"품명": name, "단위": unit, "규격": spec, "발주수량": ordered, "납품수량": got, "불량": bad,
                     "유통기한": expiry, "온도": rng.choice(["상온", "5℃", "3℃", "-18℃"]),
                     "판정": "합격" if bad == 0 else "일부 불량"})
    assert all(r["납품수량"] >= 0 for r in rows)
    return {"형식": form, "납품번호": f"DL-2026-{rng.randint(1000, 9999)}", "발주번호": f"PO-2026-{rng.randint(100, 999):04d}",
            "납품일": day, "납품자": HS, "납품처": to, "납품장소": f"{to['상호']} {rng.choice(['본사 창고', '1센터', '물류동'])}",
            "배송기사": rng.choice(NAMES), "차량번호": f"{rng.randint(10, 99)}{rng.choice('가나다라마')} {rng.randint(1000, 9999)}",
            "인수자": rng.choice(NAMES), "품목": rows, "총납품": sum(r["납품수량"] for r in rows), "총발주": sum(r["발주수량"] for r in rows),
            "비고": rng.choice(["부족 수량은 차주 화요일 추가 납품", "특이사항 없음", "파손 박스는 현장에서 사진 촬영 후 인수", "하차 시간 오전 9시 지정"])}


# ---------------------------------------------------------------- 재고조사표
def build_inventory(rng: random.Random, seq: int, form: int) -> dict:
    if form == 2:
        return build_inventory2(rng)
    rows = []
    for i, (name, unit, spec, _) in enumerate(rng.sample(ITEMS, rng.randint(12, 16)), 1):
        book = rng.randint(20, 400)
        diff = rng.choice([0, 0, 0, 0, -1, -2, -3, 1, 2])
        rows.append({"번호": i, "코드": f"{rng.choice('ABCD')}{rng.randint(1000, 9999)}", "품명": name, "단위": unit, "규격": spec, "장부": book,
                     "실사": book + diff, "차이": diff, "비고": rng.choice(["", "", "", "파손", "유통기한 임박", "위치 이동", "미입고분"]) if diff else ""})
    assert all(r["실사"] == r["장부"] + r["차이"] for r in rows)
    return {"형식": 1, "센터": rng.choice(CENTERS), "조사일": date(rng, 2026), "구역": f"{rng.choice('ABCD')}-{rng.randint(1, 9)}동 {rng.choice(['상온', '냉장', '냉동'])}",
            "조사자": rng.choice(NAMES), "입회자": rng.choice(NAMES), "확인자": rng.choice(NAMES), "품목": rows,
            "장부합계": sum(r["장부"] for r in rows), "실사합계": sum(r["실사"] for r in rows), "차이합계": sum(r["차이"] for r in rows)}


def build_inventory2(rng: random.Random) -> dict:
    """형식2: 로케이션(랙-단-칸)·LOT·유통기한 기준의 실사표. 차이 품목은 조정 사유와 금액이 붙는다."""
    rows = []
    for i, (name, unit, spec, price) in enumerate(rng.sample(ITEMS, rng.randint(9, 13)), 1):
        book = rng.randint(30, 600)
        diff = rng.choice([0, 0, 0, 0, -1, -2, -4, 1, 3, -6])
        rows.append({"번호": i, "위치": f"R{rng.randint(1, 12):02d}-{rng.randint(1, 4)}-{rng.randint(1, 6):02d}", "품명": name, "규격": spec,
                     "LOT": f"L{rng.randint(260301, 261015)}-{rng.randint(1, 9)}", "유통기한": date(rng, 2027, 1, 12), "장부": book,
                     "실사": book + diff, "차이": diff, "금액": diff * price,
                     "사유": rng.choice(["파손 폐기", "출고 전표 누락", "입고 검수 오기", "위치 이동", "샘플 출고"]) if diff else ""})
    assert all(r["실사"] == r["장부"] + r["차이"] for r in rows)
    return {"형식": 2, "센터": rng.choice(CENTERS), "조사일": date(rng, 2026), "구분": rng.choice(["정기 실사", "월말 실사", "분기 실사"]),
            "조사팀": ", ".join(rng.sample(NAMES, 2)), "품목": rows, "품목수": len(rows),
            "차이건수": sum(1 for r in rows if r["차이"]), "장부합계": sum(r["장부"] for r in rows), "실사합계": sum(r["실사"] for r in rows),
            "차이금액": sum(r["금액"] for r in rows)}


# ---------------------------------------------------------------- 연간사업계획서
def build_plan(rng: random.Random, seq: int, form: int) -> dict:
    if form == 2:
        return build_plan2(rng)
    dept = rng.choice(["영업본부", "상품본부", "물류본부", "가맹사업본부", "마케팅본부"])
    target = rng.randint(80, 600) * 100  # 백만원
    weights = [rng.uniform(0.6, 1.4) for _ in range(12)]
    months = [int(target * w / sum(weights)) for w in weights]
    months[-1] += target - sum(months)
    assert sum(months) == target
    tasks = []
    for t in rng.sample(["신규 거래처 개척", "PB상품 라인업 확대", "물류 리드타임 단축", "가맹점 교육 프로그램 개편", "재고 회전율 개선", "온라인 주문 채널 구축",
                         "수입 원두 공급처 다변화", "냉장 물류 설비 확충"], 5):
        tasks.append({"과제": t, "담당": rng.choice(DEPTS), "기한": f"2027.{rng.randint(3, 12):02d}", "예산": rng.randint(5, 80) * 10})
    return {"형식": 1, "연도": 2027, "부서": dept, "작성일": date(rng, 2026, 10, 12), "작성자": rng.choice(NAMES), "목표매출": target, "영업이익": int(target * rng.uniform(0.04, 0.09)),
            "신규거래처": rng.randint(8, 40), "월": [{"월": f"{i + 1}월", "매출": v} for i, v in enumerate(months)], "과제": tasks,
            "예산합계": sum(t["예산"] for t in tasks)}


def build_plan2(rng: random.Random) -> dict:
    """형식2: 분기별 목표 + 전략과제(KPI·우선순위) + 인력 계획. 형식1의 월별 표와 달리 분기 카드와 KPI 중심이다."""
    dept = rng.choice(["영업본부", "상품본부", "물류본부", "가맹사업본부", "마케팅본부"])
    target = rng.randint(80, 600) * 100  # 백만원
    weights = [rng.uniform(0.7, 1.3) for _ in range(4)]
    qs = [int(target * w / sum(weights)) for w in weights]
    qs[-1] += target - sum(qs)
    assert sum(qs) == target
    focus = rng.sample(["신규 거래처 계약", "PB상품 출시", "물류센터 자동화 1단계", "가맹점 교육 개편", "재고 회전 개선", "온라인 주문 확대",
                        "원두 공급처 다변화", "냉장 설비 확충", "거래처 채권 관리 강화"], 4)
    tasks = []
    for t, kpi in rng.sample([("신규 거래처 개척", "신규 계약 {}곳"), ("물류 리드타임 단축", "평균 {}시간 이내"), ("재고 회전율 개선", "회전일수 {}일"),
                              ("가맹점 교육 프로그램", "이수율 {}%"), ("PB상품 라인업 확대", "신규 SKU {}개")], 4):
        value = {"신규 거래처 개척": rng.randint(8, 40), "물류 리드타임 단축": rng.randint(18, 36), "재고 회전율 개선": rng.randint(25, 45),
                 "가맹점 교육 프로그램": rng.randint(80, 98), "PB상품 라인업 확대": rng.randint(4, 15)}[t]
        tasks.append({"과제": t, "지표": kpi.format(value), "담당": rng.choice(DEPTS), "예산": rng.randint(5, 80) * 10,
                      "우선순위": rng.choice(["상", "상", "중", "하"])})
    return {"형식": 2, "연도": 2027, "부서": dept, "작성일": date(rng, 2026, 10, 12), "작성자": rng.choice(NAMES), "목표매출": target,
            "전년매출": int(target / rng.uniform(1.04, 1.25)), "분기": [{"분기": f"{i + 1}분기", "매출": v, "중점": focus[i]} for i, v in enumerate(qs)],
            "과제": tasks, "예산합계": sum(t["예산"] for t in tasks), "현원": rng.randint(12, 60), "증원": rng.randint(0, 8)}


BUILDERS = {"재직증명서": build_cert, "세금계산서": build_tax, "발주서": build_po, "납품확인서": build_delivery,
            "재고조사표": build_inventory, "연간사업계획서": build_plan}


def split_of(seq: int) -> str:
    return {1: "fewshot", 2: "dev", 3: "dev", 4: "dev", 5: "dev"}.get(seq % 10, "test")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", help="쉼표로 구분한 소분류 이름만 만든다 (예: 재직증명서,발주서)")
    args = parser.parse_args()
    names = args.only.split(",") if args.only else list(MINORS)
    unknown = [n for n in names if n not in MINORS]
    if unknown:
        raise SystemExit(f"알 수 없는 소분류: {unknown} (가능: {list(MINORS)})")

    template = Template((ROOT / "data" / "html" / "template_new_minors.html").read_text(encoding="utf-8"))
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    docs, rows = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": A4_CSS[0], "height": A4_CSS[1]}, device_scale_factor=SCALE)
        for name in names:
            code, major_code, major, forms = MINORS[name]
            for form in range(1, forms + 1):
                for k in range(1, 11):
                    seq = (form - 1) * 10 + k
                    doc = BUILDERS[name](random.Random(f"{name}-{form}-{seq}"), seq, form)
                    doc_id = f"{code}_{name}_{seq:03d}"
                    page.set_content(template.render(kind=name, doc=doc))
                    h, w = page.evaluate("[document.documentElement.scrollHeight, document.documentElement.scrollWidth]")
                    if h > A4_CSS[1] or w > A4_CSS[0]:  # 한 쪽을 넘치면 그림이 잘린다 (이미지는 열지 않고 크기만 확인)
                        raise SystemExit(f"⚠️ {doc_id}: 내용이 A4 한 쪽을 넘습니다 ({w}×{h})")
                    page.screenshot(path=str(IMG_DIR / f"{doc_id}.png"))
                    docs.append({"문서ID": doc_id, "소분류": name, **doc})
                    rows.append({"file": f"{doc_id}.png", "major_code": major_code, "major": major, "minor_code": code,
                                 "minor": name, "split": split_of(seq)})
        browser.close()

    JSON_OUT.write_text(json.dumps({"문서목록": docs}, ensure_ascii=False, indent=2), encoding="utf-8")
    with LABELS_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}장 → {IMG_DIR}, 라벨 → {LABELS_OUT}, 내용 → {JSON_OUT}")


if __name__ == "__main__":
    main()
