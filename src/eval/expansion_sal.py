"""영업/제안 확장 14종 (SAL-07~20). 각 함수는 (레이아웃 0/1, 난수) → HTML. 수치는 합성용 근사값이다."""
import random

from src.eval.expansion_common import (CLIENTS, COMPANY, NAMES, REGIONS, TEAMS, H, KV, P, T, UL, bar, date, doc,
                                       grid, page, won, ymd)

ITEMS = [("HS 버터쿠키", "과자", "200g", 3800), ("HS 초코칩쿠키", "과자", "180g", 3600), ("HS 웨하스", "과자", "150g", 2400), ("HS 현미 크런치바", "과자", "40g×6", 4900),
         ("HS 오렌지주스", "음료", "1L", 2800), ("HS 탄산수 레몬", "음료", "500ml", 1100), ("HS 아이스티 복숭아", "음료", "340ml", 1200), ("HS 콜드브루", "음료", "250ml", 2200),
         ("HS 단호박 에그타르트", "베이커리", "4입", 5200), ("HS 흑임자 롤케이크", "베이커리", "320g", 6800)]
POSTER_RESET = '<style>body { padding: 0 !important; }</style>'
COMP = ["달콤제과", "금빛베이커리", "리브제과", "청아식품", "바른푸드"]


def _no(rng, prefix):
    return f"{prefix}-{rng.randint(2025, 2026)}-{rng.randint(1, 99):03d}"


def sal07(layout, rng):  # 제안서
    to = rng.choice(CLIENTS)
    items = rng.sample(ITEMS, 5)
    theme = rng.choice(["가을 시즌 간식 매대 구성", "편의점 신규 음료 라인업 도입", "연말 선물세트 공동 기획", "저당 디저트 코너 신설"])
    rows = [(n, sp, won(pr), won(int(pr * rng.uniform(0.82, 0.92))), f"{rng.randint(1, 5) * 100}개") for n, c, sp, pr in items]
    if layout == 0:
        body = [KV([("제안 대상", f"{to} 구매팀"), ("제안 제목", theme)], 1), H("1. 제안 배경"), P("최근 소비 트렌드 변화에 따라 귀사 매장의 객단가 향상과 신규 고객 유입을 위한 상품 구성을 제안드립니다."),
                H("2. 제안 상품 및 공급 조건"), T(["상품", "규격", "소비자가", "제안 공급가", "최소 발주"], rows, num=(2, 3, 4)),
                H("3. 기대 효과"), UL(["매대 회전율 개선", "행사 기간 판촉 지원(시식·POP)", "정기 배송으로 결품 최소화"])]
    else:
        body = [f"<div class=card style='font-size:17px'><b>{to}</b> 귀중 &nbsp; | &nbsp; {theme}</div>",
                grid([f"<div><h3>제안 요약</h3>{UL(['상품 5종 공급', '초도 물량 판촉 지원', '월 2회 정기 배송'])}</div>", f"<div class=card><b>제안 총액(예상)</b><div class=big>{won(sum(int(r[3].replace(',', '')) * int(r[4][:-1]) for r in rows))}원</div></div>"], 2),
                H("상품 구성"), T(["상품", "공급가", "최소 발주"], [(r[0], r[3], r[4]) for r in rows], num=(1, 2)), H("거래 조건"), T(["항목", "내용"], [("결제", rng.choice(["월말 마감 익월 말 결제", "납품 후 30일", "납품 후 45일"])), ("배송", "주 2회 정기 배송"), ("유효 기간", f"{date(rng, 2026, 2026)}까지")], left=(1,))]
    return doc(layout, "제  안  서" if layout == 0 else "상품 공급 제안서", body, [("제안일", date(rng)), ("제안사", COMPANY)], _no(rng, "PR"), sign=("작성", "팀장", "이사"))


def sal08(layout, rng):  # 프로모션 기획서
    ev = rng.choice(["가을 맛집 페스타", "1+1 음료 위크", "신학기 간식 대전", "연말 감사 세일", "여름 시원 음료전"])
    y, m = rng.randint(2025, 2026), rng.randint(1, 12)
    ds = rng.sample(ITEMS, 4)
    if layout == 0:
        body = [KV([("행사명", ev), ("기간", f"{ymd(y, m, 1)} ~ {ymd(y, m, rng.randint(10, 28))}"), ("대상 채널", rng.choice(["편의점", "대형마트", "중소 슈퍼", "전 채널"])), ("목적", "매출 증대 및 신제품 인지도 제고")], 2),
                H("행사 구조"), T(["대상 상품", "행사 유형", "할인율·혜택", "행사 물량"], [(d[0], rng.choice(["1+1", "2+1", "즉시 할인", "증정"]), rng.choice(["50%", "33%", "20%", "사은품"]), f"{rng.randint(1, 20) * 100}개") for d in ds], num=(3,)),
                H("예상 효과"), T(["구분", "금액(원)"], [("예상 추가 매출", won(rng.randint(20, 90) * 1_000_000)), ("판촉비", won(rng.randint(5, 20) * 1_000_000)), ("예상 ROI", f"{rng.randint(120, 380)}%")], num=(1,))]
    else:
        wk = "".join(f"<div class=card style='flex:1'><b>{i}주차</b><br><small>{t}</small></div>" for i, t in enumerate(["사전 홍보·POP 배포", "행사 본 기간 1", "행사 본 기간 2", "결과 집계·정산"], 1))
        body = [f"<div class=card><span class=big>{ev}</span><br>{ymd(y, m, 1)} 시작 · 목표 매출 {won(rng.randint(30, 150) * 1_000_000)}원</div>", H("주간 운영 계획"), f"<div style='display:flex;gap:6px'>{wk}</div>",
                H("혜택 및 예산"), T(["상품", "혜택", "예산"], [(d[0], rng.choice(["1+1 증정", "20% 할인", "사은품 증정"]), won(rng.randint(2, 12) * 500_000)) for d in ds], num=(2,)),
                H("목표 지표"), "".join(f"<div style='display:flex;gap:10px;align-items:center;margin:6px 0'><span style='width:120px'>{k}</span><div style='flex:1'>{bar(v)}</div><b>{v}%</b></div>" for k, v in [("매출 증가", rng.randint(10, 40)), ("신규 거래 확대", rng.randint(5, 25)), ("재고 소진", rng.randint(60, 95))])]
    return doc(layout, "프로모션 기획서", body, [("기획", rng.choice(TEAMS)), ("작성일", date(rng))], _no(rng, "PM"))


def sal09(layout, rng):  # 판촉 행사 결과표
    ev = rng.choice(["가을 맛집 페스타", "1+1 음료 위크", "신학기 간식 대전", "연말 감사 세일"])
    ds = rng.sample(ITEMS, 5)
    rows = []
    for d in ds:
        plan = rng.randint(5, 40) * 100
        act = int(plan * rng.uniform(0.7, 1.4))
        rows.append((d[0], plan, act, act * d[3]))
    if layout == 0:
        body = [H("품목별 계획 대비 실적"), T(["품목", "계획 수량", "실적 수량", "달성률", "매출액(원)", "판촉비(원)"], [(r[0], won(r[1]), won(r[2]), f"{r[2] * 100 // r[1]}%", won(r[3]), won(rng.randint(1, 9) * 100_000)) for r in rows], num=(1, 2, 3, 4, 5),
                                                  foot=("합계", won(sum(r[1] for r in rows)), won(sum(r[2] for r in rows)), "", won(sum(r[3] for r in rows)), "")),
                H("총평"), UL(["주력 품목은 계획을 초과 달성했으나 일부 품목은 재고 부족으로 미달", "다음 행사에는 물량을 상향하고 POP 배치를 앞당긴다"])]
    else:
        st = rng.sample(CLIENTS, 5)
        tot = [rng.randint(5, 40) * 1_000_000 for _ in st]
        body = [H("거래처별 행사 매출"), "".join(f"<div style='display:flex;gap:10px;align-items:center;margin:6px 0'><span style='width:120px'>{s}</span><div style='flex:1'>{bar(v * 100 / max(tot))}</div><b>{won(v)}</b></div>" for s, v in zip(st, tot)),
                H("행사 전후 비교"), T(["구분", "행사 전 4주", "행사 기간", "증감"], [("주간 평균 매출", won(a := rng.randint(20, 60) * 1_000_000), won(b := int(a * rng.uniform(1.1, 1.8))), f"+{(b - a) * 100 // a}%"), ("평균 객단가", won(a := rng.randint(8, 20) * 1000), won(b := int(a * rng.uniform(0.95, 1.3))), f"{(b - a) * 100 // a:+d}%")], num=(1, 2, 3)),
                H("평가"), P("행사 기간 매출이 평균 대비 증가하였다. 증정 품목 소진 속도가 빨라 후반부 결품이 발생했다.")]
    return doc(layout, f"판촉 행사 결과표 ({ev})" if layout == 0 else "판촉 행사 결과 보고", body, [("행사 기간", date(rng)), ("작성", rng.choice(TEAMS))], _no(rng, "PE"))


def sal10(layout, rng):  # 상품 카탈로그
    items = rng.sample(ITEMS, 6)
    col = {"과자": "#e4b45c", "음료": "#7fb7d6", "베이커리": "#d99a7a"}
    pack = lambda c, n, h=90: f"<div style='height:{h}px;background:{col[c]};display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;text-align:center;padding:4px'>{n}</div>"
    if layout == 0:
        cards = [f"<div class=card>{pack(c, n)}<div style='margin-top:6px'><b>{n}</b></div><div style='font-size:13px'>{sp} · 코드 {rng.randint(10000, 99999)}</div><div class=big style='font-size:17px'>{won(pr)}원</div></div>" for n, c, sp, pr in items]
        body = [f"<p class=c style='font-size:15px'>{rng.choice(['가을 겨울 시즌 상품 안내', '신상품 소개', '인기 상품 모음'])} · 전 상품 B2B 공급가 기준</p>", grid(cards, 3, 10), P("가격은 부가세 별도이며 최소 주문 수량은 박스 단위입니다.")]
    else:
        rows = [f"<div style='display:flex;gap:12px;border-bottom:1px solid var(--b);padding:8px 0'><div style='width:120px'>{pack(c, c, 70)}</div><div style='flex:1'><b style='font-size:16px'>{n}</b><br>규격 {sp} · 입수 {rng.choice([12, 20, 24, 30])}개<br>공급가 <b>{won(pr)}원</b> · 유통기한 {rng.choice([60, 90, 180, 270])}일</div></div>" for n, c, sp, pr in items[:5]]
        body = [f"<div style='display:flex;gap:6px;margin-bottom:6px'>{''.join(f'<span class=card style=padding:3px 12px>{t}</span>' for t in ['전체', '과자', '음료', '베이커리'])}</div>", "".join(rows)]
    return doc(layout, "상품 카탈로그" if layout == 0 else "PRODUCT CATALOG 상품 안내", body, [("발행", COMPANY), ("개정", date(rng, 2025, 2026))], _no(rng, "CT"), sign=())


def sal11(layout, rng):  # 거래처 등급 기준표
    gr = ["S", "A", "B", "C", "D"]
    body = [H("등급별 기준 및 혜택"), T(["등급", "연 매출", "결제 이행", "거래 기간", "공급가 할인", "결제 조건", "판촉 지원"],
                                   [(g, f"{max(10 - i * 2, 1) * rng.choice([1, 1]) * 100}백만 원 이상", rng.choice(["무연체", "연체 1회 이하", "연체 2회 이하"]) if i < 4 else "연체 3회 이상", f"{max(5 - i, 1)}년 이상", f"{max(5 - i, 0)}.{rng.randint(0, 5)}%", rng.choice(["월말 마감 60일", "월말 마감 45일", "월말 마감 30일", "선결제"]) if i < 3 else "선결제", "전용 판촉비" if i < 2 else "기본 지원") for i, g in enumerate(gr)])]
    if layout == 0:
        body += [H("평가 항목 및 배점"), T(["평가 항목", "배점", "산정 방식"], [("매출 규모", 40, "전년 대비 매출액 순위"), ("수금 안정성", 30, "연체 건수·기간"), ("거래 기간", 15, "거래 시작일 기준"), ("협조도", 15, "행사 참여·진열 협조")], num=(1,), left=(2,), foot=("합계", 100, ""))]
    else:
        names = rng.sample(CLIENTS, 5)
        body += [H("거래처 평가 예시"), T(["거래처", "매출(40)", "수금(30)", "기간(15)", "협조(15)", "총점", "등급"], [(n, (a := rng.randint(15, 40)), (b := rng.randint(12, 30)), (c := rng.randint(5, 15)), (d := rng.randint(5, 15)), a + b + c + d, gr[min((100 - a - b - c - d) // 12, 4)]) for n in names], num=(1, 2, 3, 4, 5))]
    return doc(layout, "거래처 등급 기준표", body, [("적용 기간", f"{rng.randint(2025, 2026)}년 연간"), ("관리", "영업관리팀")], _no(rng, "GR"))


def sal12(layout, rng):  # 진열 계획도
    col = {"과자": "#e4b45c", "음료": "#7fb7d6", "베이커리": "#d99a7a"}
    def prod():
        n, c, *_ = rng.choice(ITEMS)
        return n, col[c]
    if layout == 0:  # 곤돌라 정면 (단 × 페이싱)
        shelf = ""
        for lv in range(4, 0, -1):
            cells = ""
            for _ in range(6):
                n, c = prod()
                cells += f"<div style='flex:{rng.choice([1, 1, 2])};background:{c};border:1px solid #fff;font-size:11px;text-align:center;color:#222;padding:14px 2px;overflow:hidden'>{n.replace('HS ', '')}</div>"
            shelf += f"<div style='display:flex;align-items:stretch'><div style='width:50px;text-align:center;padding-top:16px'><b>{lv}단</b></div><div style='flex:1;display:flex;border-bottom:6px solid #777;min-height:70px'>{cells}</div></div>"
        body = [KV([("매장", rng.choice(CLIENTS)), ("진열 위치", f"{rng.choice('ABCDEF')}-{rng.randint(1, 9):02d} 곤돌라"), ("카테고리", rng.choice(["과자", "음료", "디저트"])), ("단 구성", "4단 6열")], 2), H("진열 정면도"), shelf,
                H("진열 원칙"), UL(["눈높이 2~3단에 주력 상품 배치", "행사 상품은 엔드 매대에 별도 진열", "선입선출 정리, 가격표 부착 확인"])]
    else:  # 매장 평면 (통로·곤돌라 배치)
        zones = [rng.choice(["과자", "음료", "베이커리"]) for _ in range(12)]
        cells = "".join(f"<div style='background:{col[z]};border:2px solid #fff;height:70px;text-align:center;padding-top:22px;font-weight:600'>{'ABCD'[i // 3]}{i % 3 + 1}<br><small>{z}</small></div>" for i, z in enumerate(zones))
        body = [H("매장 평면 배치 (통로 기준)"), f"<div style='border:3px solid #555;padding:10px'><div class=grid style='grid-template-columns:repeat(3,1fr);gap:26px 10px'>{cells}</div><div style='text-align:center;margin-top:10px;background:var(--l)'>계산대 · 입구</div></div>",
                H("구역별 진열 계획"), T(["구역", "카테고리", "주력 상품", "페이싱"], [(f"{'ABCD'[i]}열", rng.choice(['과자', '음료', '베이커리']), prod()[0], rng.randint(3, 8)) for i in range(4)], num=(3,))]
    return doc(layout, "진열 계획도", body, [("작성", rng.choice(TEAMS)), ("적용일", date(rng))], _no(rng, "PL"))


def sal13(layout, rng):  # 행사 부스 운영 계획서
    ev = rng.choice(["서울 식품박람회", "베이커리 페어", "유통 상생 박람회", "지역 특산 푸드페스티벌"])
    d0 = rng.randint(1, 20)
    booth = ("<div style='border:3px solid #555;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;padding:6px;width:300px'>"
             "<div class=card style='grid-column:span 3;text-align:center'>상담 테이블</div><div class=card>시식대</div><div class=card>진열대</div><div class=card>시식대</div><div class=card style='grid-column:span 3;text-align:center'>입구 · 안내</div></div>")
    staff = [(n, rng.choice(["상담", "시식", "진열", "안내"]), rng.choice(["09~13시", "13~18시", "종일"])) for n in rng.sample(NAMES, 5)]
    if layout == 0:
        body = [KV([("행사명", ev), ("장소", rng.choice(["코엑스", "킨텍스", "벡스코"])), ("기간", f"{ymd(2026, 10, d0)} ~ {ymd(2026, 10, d0 + 2)}"), ("부스 규모", "3m × 3m")], 2), H("부스 배치"), booth,
                H("인력 배치"), T(["이름", "역할", "근무"], staff), H("준비 물품"), UL(["시식 용기·이쑤시개", "상품 샘플 박스 20개", "배너·카탈로그", "전기 멀티탭"])]
    else:
        days = [(f"{ymd(2026, 10, d0 + i)}", t) for i, t in enumerate(["설치 및 상품 진열", "본 행사 1일차: 시식·상담", "본 행사 2일차 및 철수"])]
        body = [f"<div class=card><b>{ev}</b> 참가 계획 &nbsp; 예산 {won(rng.randint(5, 30) * 1_000_000)}원</div>", H("일정"), T(["일자", "운영 내용"], days, left=(1,)), grid([f"<div><h3>부스 도면</h3>{booth}</div>", f"<div><h3>예산</h3>{T(['항목', '금액'], [('부스 임차', won(rng.randint(3, 10) * 1_000_000)), ('시식 재료', won(rng.randint(1, 5) * 500_000)), ('인건비', won(rng.randint(2, 8) * 500_000))], num=(1,))}</div>"], 2),
                H("운영 인력"), T(["담당", "역할", "시간"], staff[:4])]
    return doc(layout, "행사 부스 운영 계획서", body, [("작성", "마케팅팀"), ("작성일", date(rng, 2026, 2026))], _no(rng, "BT"))


def sal14(layout, rng):  # 시식 행사 안내 포스터
    it = rng.choice(ITEMS)
    prod = it[0]
    st = rng.choice(CLIENTS)
    day = f"{rng.randint(1, 12)}월 {rng.randint(1, 28)}일"
    time = f"오전 {rng.randint(10, 11)}시 ~ 오후 {rng.randint(3, 6)}시"
    if layout == 0:
        body = (f"{POSTER_RESET}<div style='background:#f6a43a;padding:70px 44px;height:1123px;box-sizing:border-box;overflow:hidden;text-align:center;color:#3b2200'>"
                f"<div style='font-size:30px;font-weight:700'>{st}에서 만나요</div><div style='font-size:76px;font-weight:900;line-height:1.15;margin:26px 0;letter-spacing:4px'>시식 행사<br>안내</div>"
                f"<div style='width:300px;height:300px;border-radius:50%;background:#fff3d9;margin:20px auto;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:700;text-align:center;word-break:keep-all;padding:0 30px'>{prod}</div>"
                f"<div style='font-size:34px;font-weight:700;margin-top:20px'>{day} · {time}</div><div style='font-size:26px;margin-top:14px'>시식 후 구매 시 <b>{rng.choice(['10% 할인', '1+1 증정', '사은품 증정'])}</b></div>"
                f"<div style='margin-top:50px;font-size:20px'>장소: {st} {rng.choice(['1층 입구', '식품 코너', '계산대 앞'])} · 주관 {COMPANY}</div></div>")
    else:
        body = (f"{POSTER_RESET}<div style='display:flex;height:1123px;overflow:hidden'><div style='width:36%;background:#c0392b;color:#fff;padding:60px 26px;font-size:30px;font-weight:700;line-height:1.5'>SPECIAL<br>TASTING<br>DAY<div style='font-size:18px;margin-top:40px;font-weight:400'>{day}<br>{time}</div></div>"
                f"<div style='flex:1;background:#fff8ec;padding:70px 40px'><div style='font-size:20px;color:#c0392b;font-weight:700'>{st}</div><div style='font-size:64px;font-weight:900;margin:10px 0 30px;line-height:1.15'>맛있게<br>먹어보세요!</div>"
                f"<div style='border:4px solid #c0392b;padding:26px;text-align:center;font-size:32px;font-weight:700'>{prod}<br><span style='font-size:20px;font-weight:400'>{it[2]} · 무료 시식</span></div>"
                f"<ul style='font-size:22px;line-height:2;margin-top:30px'><li>시식은 선착순 {rng.randint(1, 5) * 100}명</li><li>구매 고객 추첨 경품</li></ul><div style='margin-top:40px;font-size:18px'>주최 {COMPANY}</div></div></div>")
    return page(body, layout)


def sal15(layout, rng):  # 거래처 담당자 연락처 명부
    rows = []
    for c in rng.sample(CLIENTS, 12 if layout == 0 else 9):
        nm = rng.choice(NAMES)
        rows.append((c, nm, rng.choice(["구매팀", "상품팀", "MD팀", "점장"]), rng.choice(["과장", "대리", "팀장", "차장"]), f"010-{rng.randint(2000, 9999)}-{rng.randint(1000, 9999)}", f"{rng.choice(['kim', 'lee', 'park', 'choi', 'jung'])}{rng.randint(1, 99)}@{rng.choice(['hanbit', 'saerom', 'daon', 'green'])}.example.com", rng.choice(REGIONS)))
    if layout == 0:
        body = [T(["거래처", "담당자", "부서", "직책", "휴대전화", "이메일"], [r[:6] for r in rows], left=(5,), style="font-size:13px")]
    else:
        body = []
        for rg in sorted({r[6] for r in rows})[:4]:
            g = [r for r in rows if r[6] == rg]
            body += [H(f"{rg} 지역"), grid([f"<div class=card><b>{r[0]}</b> {r[1]} {r[3]}<br><small>{r[2]} · {r[4]}<br>{r[5]}</small></div>" for r in g], 2, 6)]
    return doc(layout, "거래처 담당자 연락처 명부", body, [("기준일", date(rng, 2026, 2026)), ("관리", "영업관리팀")], _no(rng, "CL"), sign=("작성", "확인") if layout == 0 else ())


def sal16(layout, rng):  # 파렛트 적재 기준표
    def pattern(per_layer, cols):
        rows_n = -(-per_layer // cols)
        return "<div style='display:inline-grid;grid-template-columns:repeat(%d,34px);gap:2px;border:3px solid #777;padding:4px;background:#ddd'>" % cols + "".join("<div style='height:30px;background:var(--c);opacity:.8'></div>" for _ in range(per_layer)) + "</div>"
    prods = []
    for it in rng.sample(ITEMS, 4 if layout == 0 else 3):
        pl, ly = rng.choice([(6, 3), (8, 4), (10, 5), (12, 4)]), rng.randint(4, 9)
        prods.append((it[0], f"{rng.randint(30, 45)}×{rng.randint(20, 30)}×{rng.randint(15, 25)}", f"{rng.randint(5, 14)}.{rng.randint(0, 9)}", pl[0], ly, pl[0] * ly, pl[1]))
    if layout == 0:
        body = [H("품목별 적재 기준 (파렛트 1100×1100)"), T(["상품", "박스 규격(cm)", "박스 중량(kg)", "단당 박스", "적재 단수", "파렛트당 박스"], [p[:6] for p in prods], num=(3, 4, 5)),
                H("단 적재 패턴 예시"), pattern(prods[0][3], prods[0][6]), P(f"{prods[0][0]} 단당 {prods[0][3]}박스 (가로 {prods[0][6]}열). 최대 높이 1.5m, 총 중량 1톤 이내.")]
    else:
        body = [grid([f"<div class=card><b>{p[0]}</b><br><small>{p[1]}cm · {p[2]}kg</small><br>{pattern(p[3], p[6])}<br>{p[3]}박스 × {p[4]}단 = <b>{p[5]}박스</b></div>" for p in prods], 3, 8),
                H("공통 기준"), UL(["파렛트 규격 1100×1100mm (T11)", "상단 랩핑 3회 이상, 모서리 보호대 사용", "냉장 상품은 높이 1.2m 이하"])]
    return doc(layout, "파렛트 적재 기준표", body, [("적용", "물류센터 입출고"), ("개정", date(rng, 2025, 2026))], _no(rng, "PT"))


def sal17(layout, rng):  # 제품 라벨 시안
    it = rng.choice(ITEMS)
    n = it[0]
    kind = {'과자': '과자', '음료': '음료', '베이커리': '빵류'}[it[1]]
    ing = rng.sample(["밀가루", "설탕", "버터", "달걀", "식물성 유지", "소금", "우유", "코코아분말", "현미", "팽창제", "정제수", "구연산"], 6)
    nut = [("열량", f"{rng.randint(90, 480)}kcal"), ("탄수화물", f"{rng.randint(10, 60)}g"), ("당류", f"{rng.randint(2, 30)}g"), ("단백질", f"{rng.randint(1, 9)}g"), ("지방", f"{rng.randint(1, 25)}g"), ("나트륨", f"{rng.randint(20, 300)}mg")]
    bars = "<div style='display:flex;height:50px;width:170px;padding:4px;background:#fff;border:1px solid #888'>" + "".join(f"<i style='display:block;background:#111;width:{rng.choice([2, 3, 4])}px;margin-right:{rng.choice([2, 3, 4])}px'></i>" for _ in range(24)) + "</div>"
    info = lambda: (f"<table style='font-size:13px'><tr><th>식품유형</th><td>{kind}</td><th>내용량</th><td>{it[2]}</td></tr><tr><th>원재료명</th><td colspan=3>{', '.join(ing)}</td></tr>"
                    f"<tr><th>보관</th><td>직사광선을 피해 서늘한 곳</td><th>소비기한</th><td>제조일로부터 {rng.choice([90, 180, 270])}일</td></tr><tr><th>알레르기</th><td colspan=3>{rng.choice(['밀, 우유, 대두 함유', '밀, 달걀, 우유 함유', '대두 함유'])}</td></tr></table>")
    nt = "<table style='font-size:13px'><tr><th colspan=2>영양정보</th></tr>" + "".join(f"<tr><td>{k}</td><td class=r>{v}</td></tr>" for k, v in nut) + "</table>"
    if layout == 0:
        label = (f"<div style='border:3px solid #333;padding:20px'><div style='background:var(--l);text-align:center;padding:26px'><div style='font-size:42px;font-weight:900;color:var(--c)'>{n}</div><div style='font-size:18px'>{it[2]}</div></div>"
                 f"<div style='margin-top:14px'>{info()}</div><div style='display:flex;gap:14px;margin-top:12px;align-items:flex-end'><div style='flex:1'>{nt}</div>{bars}</div><p style='font-size:12px'>제조원: {rng.choice(['(주)한결제과', '미래식품(주)'])} / 판매원: {COMPANY}</p></div>")
    else:
        label = (f"<div style='display:flex;gap:10px;border:3px solid #333;padding:12px'><div style='flex:1;background:var(--l);padding:40px 10px;text-align:center'><div style='font-size:34px;font-weight:900;color:var(--c)'>{n}</div><div style='font-size:20px;margin:12px 0'>{it[2]}</div><div style='border:2px solid var(--a);color:var(--a);display:inline-block;padding:4px 12px'>NEW</div></div>"
                 f"<div style='flex:1;font-size:12px'>{info()}<div style='margin-top:8px'>{nt}</div><div style='margin-top:8px'>{bars}</div></div></div>")
    body = [label, P("※ 위 시안은 인쇄 전 검토용이며 색상과 문구는 최종 확인 후 확정한다.")]
    return doc(layout, "제품 라벨 시안", body, [("시안 번호", f"LB-{rng.randint(100, 999)}"), ("버전", f"v{rng.randint(1, 4)}"), ("디자인", rng.choice(NAMES))], _no(rng, "LB"), sign=("디자인", "품질", "승인"))


def sal18(layout, rng):  # 경쟁사 제품 비교표
    cat = rng.choice(["버터쿠키", "레몬 탄산수", "초코 롤케이크", "곡물 바"])
    cs = rng.sample(COMP, 3)
    price = rng.randint(20, 60) * 100
    cols = ["당사", *cs]
    ps = [price] + [int(price * rng.uniform(0.85, 1.25)) for _ in cs]
    g = [rng.choice([120, 150, 200, 240]) for _ in cols]
    rows = [("판매가(원)", *[won(p) for p in ps]), ("용량", *[f"{x}g" for x in g]), ("100g당 가격", *[won(p * 100 // x) for p, x in zip(ps, g)]), ("주요 원료", *[rng.choice(["국산 밀·버터", "수입 밀·마가린", "현미·귀리", "무설탕 시럽"]) for _ in cols]),
            ("주 유통 채널", *[rng.choice(["편의점", "대형마트", "온라인", "슈퍼"]) for _ in cols]), ("행사 현황", *[rng.choice(["1+1", "2+1", "할인 없음", "증정"]) for _ in cols])]
    if layout == 0:
        rows += [("장점", *[rng.choice(["맛 평가 높음", "가격 경쟁력", "브랜드 인지도", "용량 큼"]) for _ in cols]), ("단점", *[rng.choice(["가격 높음", "패키지 단조", "유통 제한", "품절 잦음"]) for _ in cols])]
        body = [T(["비교 항목", *cols], rows, left=(0,)), P("가격은 조사일 판매가 기준(합성 수치). 100g당 가격은 용량 대비 환산값이다.")]
    else:
        sc = lambda: "●" * (v := rng.randint(2, 5)) + "○" * (5 - v)
        rows += [("맛", *[sc() for _ in cols]), ("포장 디자인", *[sc() for _ in cols]), ("가성비", *[sc() for _ in cols])]
        body = [T(["항목", *cols], rows, left=(0,)), H("포지셔닝 (가격 수준)"), "".join(f"<div style='display:flex;gap:10px;align-items:center;margin:6px 0'><span style='width:100px'>{c}</span><div style='flex:1'>{bar(p * 100 / max(ps))}</div><b>{won(p)}원</b></div>" for c, p in zip(cols, ps))]
    return doc(layout, f"경쟁사 제품 비교표 : {cat}" if layout == 0 else f"경쟁 제품 비교 ({cat})", body, [("조사일", date(rng, 2026, 2026)), ("작성", "영업기획팀")], _no(rng, "CM"))


def sal19(layout, rng):  # 상품 규격서
    it = rng.choice(ITEMS)
    n = it[0]
    ean = f"880{rng.randint(10 ** 9, 10 ** 10 - 1)}"
    unit = rng.choice([12, 20, 24, 30])
    pairs = [("상품명", n), ("상품 코드", f"P{rng.randint(10000, 99999)}"), ("바코드(GTIN)", ean), ("규격", it[2]), ("제조원", rng.choice(["(주)한결제과", "미래식품(주)", "대성음료(주)"])), ("원산지", "국내산"),
             ("보관 방법", rng.choice(["상온", "냉장 0~10℃", "냉동 -18℃ 이하"])), ("소비기한", f"제조일로부터 {rng.choice([90, 180, 270])}일")]
    pack = [("낱개", f"{rng.randint(10, 20)}×{rng.randint(5, 15)}×{rng.randint(3, 10)}", f"{rng.randint(100, 400)}g", 1), ("박스", f"{rng.randint(30, 45)}×{rng.randint(20, 30)}×{rng.randint(15, 25)}", f"{rng.randint(3, 10)}.{rng.randint(0, 9)}kg", unit), ("파렛트", "110×110×150", f"{rng.randint(300, 900)}kg", unit * rng.randint(20, 60))]
    if layout == 0:
        body = [KV(pairs, 2), H("포장 단위"), T(["단위", "크기(cm)", "중량", "입수(낱개)"], pack, num=(3,)), H("인증 및 유의사항"), UL(["HACCP 인증 제조시설", "알레르기 유발 성분은 포장에 표시"])]
    else:
        body = [T(["항목", "내용"], pairs, left=(1,)), H("물류 정보"), T(["단위", "중량", "입수", "크기(cm)"], [(a, c, d, b) for a, b, c, d in pack], num=(2,)), P(f"주문 단위 박스, 최소 주문 {unit * 2}개. 변경 시 규격 변경 통보서를 별도 발행한다.")]
    return doc(layout, "상품 규격서" if layout == 0 else "상품 규격 사양서", body, [("등록일", date(rng)), ("담당", "상품기획팀")], _no(rng, "SP"))


def sal20(layout, rng):  # 지역별 영업 담당 구역도
    regs = [("서울", 0, 1), ("경기북부", 0, 2), ("인천", 1, 0), ("경기남부", 1, 2), ("강원", 0, 3), ("충청", 2, 1), ("경북", 2, 3), ("전라", 3, 1), ("경남", 3, 3), ("제주", 4, 1)]
    mgr = rng.sample(NAMES, 4)
    owner = {r[0]: rng.choice(mgr) for r in regs}
    colors = dict(zip(mgr, ["#f0c070", "#8fc1de", "#a8d4a0", "#d9a0c8"]))
    cnt = {r[0]: rng.randint(8, 40) for r in regs}
    if layout == 0:
        cells = "".join(f"<div style='grid-row:{r + 1};grid-column:{c + 1};background:{colors[owner[n]]};border:2px solid #fff;text-align:center;padding:18px 2px;font-weight:600;font-size:15px'>{n}<br><small>{cnt[n]}곳</small></div>" for n, r, c in regs)
        legend = "".join(f"<span style='display:inline-block;width:14px;height:14px;background:{colors[m]};margin:0 4px 0 14px'></span>{m}" for m in mgr)
        body = [H("구역도"), f"<div class=grid style='grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(5,66px);gap:0;width:560px;margin:auto'>{cells}</div>", f"<p class=c>{legend}</p>",
                T(["담당자", "담당 구역", "거래처 수"], [(m, ", ".join(k for k, v in owner.items() if v == m), sum(cnt[k] for k, v in owner.items() if v == m)) for m in mgr if any(v == m for v in owner.values())], num=(2,), left=(1,))]
    else:
        body = [H("구역별 담당 현황")] + [f"<div style='display:flex;align-items:center;gap:10px;margin:7px 0'><span style='width:90px;background:{colors[owner[n]]};padding:6px;text-align:center'><b>{n}</b></span><span style='width:80px'>{owner[n]}</span><div style='flex:1'>{bar(cnt[n] * 100 / 40)}</div><b style='width:50px'>{cnt[n]}곳</b></div>" for n, _, _ in regs] + \
               [H("연간 매출 목표"), T(["담당자", "목표(백만 원)", "전년 실적"], [(m, won(rng.randint(5, 30) * 100), won(rng.randint(5, 30) * 100)) for m in mgr], num=(1, 2))]
    return doc(layout, "지역별 영업 담당 구역도", body, [("적용", f"{rng.randint(2025, 2026)}년 상반기"), ("작성", "영업기획팀")], _no(rng, "AR"))


FORMS = [("SAL-07", "제안서", sal07), ("SAL-08", "프로모션 기획서", sal08), ("SAL-09", "판촉 행사 결과표", sal09), ("SAL-10", "상품 카탈로그", sal10), ("SAL-11", "거래처 등급 기준표", sal11),
         ("SAL-12", "진열 계획도", sal12), ("SAL-13", "행사 부스 운영 계획서", sal13), ("SAL-14", "시식 행사 안내 포스터", sal14), ("SAL-15", "거래처 담당자 연락처 명부", sal15),
         ("SAL-16", "파렛트 적재 기준표", sal16), ("SAL-17", "제품 라벨 시안", sal17), ("SAL-18", "경쟁사 제품 비교표", sal18), ("SAL-19", "상품 규격서", sal19), ("SAL-20", "지역별 영업 담당 구역도", sal20)]
