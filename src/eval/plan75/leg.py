"""법무/총무 15종 (LEG-04~LEG-18) 양식. 공공기관·인증기관은 실제 기관 대신 가상 이름(새빛·누리)을 쓰고 번호 일부를 가린다."""
import datetime

from src.eval.plan75.common import (COMPANY, CUSTOMERS, HQ_ADDR, HQ_TEL, PRODUCTS, TEAMS, addr, approval, biz_no, e, kd, kdk,
                                    kv, look, page, people, person, phone, rdate, seal, sign, square_seal, tbl, tel, won)


def cb(label, on):
    return f"<span class='cb{' on' if on else ''}'></span>{label}&nbsp;&nbsp;"


ACCIDENTS = {
    "넘어짐": ("상차장 바닥에 흘린 음료를 밟아 미끄러져 넘어짐", "바닥 이물질 방치와 미끄럼 방지 조치 미흡", "바닥 청소 주기 단축과 미끄럼 방지 매트 설치"),
    "끼임": ("팔레트 이동 중 손이 적재 박스와 랙 사이에 끼임", "작업 신호 체계 미준수와 보호 장갑 미착용", "작업 전 신호 확인 절차 교육과 보호 장갑 지급"),
    "부딪힘": ("지게차 이동 경로에서 보행자와 접촉함", "보행자 통로와 지게차 통로 미분리", "통로 구분선 재도색과 보행자 전용 통로 설치"),
    "낙하물": ("상단 랙에서 박스가 떨어져 어깨에 맞음", "적재 높이 초과와 박스 고정 불량", "적재 높이 기준 표지와 고정 밴드 사용 의무화"),
    "베임": ("박스 개봉 중 커터칼에 손가락을 베임", "안전 커터 미사용과 작업 장갑 미착용", "안전 커터로 교체와 절단 방지 장갑 지급"),
}


def accident_report(rng, seq):
    k = rng.choice(list(ACCIDENTS))
    how, cause, prev = ACCIDENTS[k]
    d = rdate(rng)
    n = rng.randint(2, 28)
    body = (approval(["작성", "안전관리자", "센터장", "대표이사"]) + "<h1>산업재해 발생 보고서</h1><div class=clr></div>"
            + kv([("보고일", kdk(d + datetime.timedelta(days=1))), ("발생 일시", f"{kdk(d)} {rng.randint(7, 22):02d}:{rng.choice(['05', '20', '40'])}"),
                  ("발생 장소", rng.choice(["물류센터 A동 상차장", "물류센터 B동 피킹 구역", "냉동창고 입구", "하역장"])),
                  ("재해자", f"{person(rng)} ({rng.choice(TEAMS)}, 근속 {rng.randint(1, 12)}년)"), ("재해 유형", f"<b>{k}</b>"),
                  ("부상 부위", rng.choice(["손가락", "발목", "무릎", "어깨", "허리"])),
                  ("치료 정도", f"{rng.choice(['통원 치료', '병원 치료'])} {n}일"), ("산재 신청", cb("신청", n > 4) + cb("미신청", n <= 4))], 2, lw=84)
            + f"<h2>발생 경위</h2><div class=box>{how}</div><h2>원인</h2><div class=box>{cause}</div>"
            + f"<h2>조치 사항</h2><div class=box>현장 응급 조치 후 병원 이송, 작업 구역 임시 통제 및 현장 보존</div><h2>재발 방지 대책</h2><div class=box>{prev}</div>"
            + sign(["작성자", "안전관리자", "대표이사"]))
    return page(body, **look(rng))


def haccp_cert(rng, seq):
    d = rdate(rng, 2023, 1, 12)
    item = rng.choice(["과자류 보관·유통", "음료류 보관·유통", "과자·음료류 보관·유통"])
    body = ("<div style='border:7px double #2f6f4f;padding:34px 38px;margin-top:6px;text-align:center'>"
            f"<div class=small style='text-align:left'>인증번호 : 제 {d.year}-{rng.randint(1000, 9999)} 호</div>"
            "<h1 style='font-size:40px;letter-spacing:10px;margin:20px 0 6px'>HACCP 인증서</h1><div style='color:#2f6f4f;margin-bottom:22px'>식품 보관·유통 업소 위해요소중점관리기준</div>"
            + kv([("업소명", COMPANY), ("대표자", person(rng)), ("소재지", HQ_ADDR), ("인증 품목", item),
                  ("인증 유효기간", f"{kd(d)} ~ {d.year + 3}.{d.month:02d}.{d.day:02d}")], 1, lw=110)
            + f"<p style='font-size:15px;line-height:2;margin:26px 0'>위 업소는 식품 보관·유통 단계의 위해요소중점관리기준을 적용하여<br>"
              f"관리하고 있음을 인증합니다.</p><p>{kdk(d)}</p>"
              f"<div class=foot style='margin-top:20px'>새빛식품안전인증원장 {seal(rng, '직인', 64)}</div></div>")
    return page(body, font="serif", **look(rng, ta="center"))


TESTS = {
    "과자": [("세균수", "10,000/g 이하", lambda r: f"{r.randint(0, 9)}00/g"), ("대장균군", "음성", lambda r: "음성"),
           ("수분", "5.0% 이하", lambda r: f"{r.uniform(2.0, 4.8):.1f}%"), ("산가", "1.0 이하", lambda r: f"{r.uniform(0.1, 0.9):.1f}")],
    "음료": [("일반세균수", "100/mL 이하", lambda r: f"{r.randint(0, 6)}0/mL"), ("대장균군", "음성", lambda r: "음성"),
           ("pH", "3.0~4.0", lambda r: f"{r.uniform(3.1, 3.9):.1f}"), ("보존료(소브산)", "불검출", lambda r: "불검출")],
}


def quality_report(rng, seq):
    pr = rng.choice(PRODUCTS)
    kind = "음료" if any(x in pr[0] for x in ["주스", "탄산", "아이스티", "보리차", "생수"]) else "과자"
    d = rdate(rng)
    rows = [[i + 1, n, std, f(rng), "적합"] for i, (n, std, f) in enumerate(TESTS[kind])]
    body = (f"<div class=small>성적서 번호 : QT-{d.year}-{rng.randint(1000, 9999)}</div><h1>시 험 · 검 사 성 적 서</h1>"
            + kv([("의뢰인", COMPANY), ("시 료 명", f"{pr[0]} ({pr[1]})"), ("접수일", kd(d)), ("검사일", kd(d + datetime.timedelta(days=rng.randint(2, 6)))),
                  ("제조일", kd(d - datetime.timedelta(days=rng.randint(10, 40)))), ("검사 목적", rng.choice(["자가품질검사", "입고 품질 확인", "정기 검사"]))], 2, lw=84)
            + "<h2>검사 결과</h2>" + tbl(["번호", "검사 항목", "기준", "결과", "판정"], rows, widths=["46px", "", "", "", "70px"])
            + kv([("종합 판정", "<b>적합</b>"), ("비고", "위 결과는 접수된 시료에 한한 것임")], 1, lw=100)
            + f"<p class=right style='margin-top:26px'>새빛식품시험연구원 시험책임자 {person(rng)} {seal(rng, '직인', 56)}</p>")
    return page(body, **look(rng))


def origin_cert(rng, seq):
    d = rdate(rng)
    dest = rng.choice(["베트남 호치민", "일본 오사카", "중국 상하이", "태국 방콕", "미국 로스앤젤레스"])
    rows = []
    for i, pr in enumerate(rng.sample(PRODUCTS, rng.randint(2, 4))):
        rows.append([i + 1, pr[0], f"{rng.choice(['1905', '2202', '2106'])}.**", f"{rng.randint(5, 80) * 10}박스", f"{rng.randint(2, 40) * 50}kg", "대한민국"])
    body = (f"<div class=small>발급번호 : CO-{d.year}-{rng.randint(10000, 99999)}</div><h1>원 산 지 증 명 서</h1><div class=sub>CERTIFICATE OF ORIGIN</div>"
            + kv([("수출자", f"{COMPANY} / {HQ_ADDR}"), ("수입자", f"{rng.choice(['Saehan Foods Co.', 'Nuri Trading Ltd.', 'Haneul Mart Inc.'])} / {dest}"),
                  ("운송 수단", rng.choice(["해상 (컨테이너)", "항공"])), ("선적일", kd(d)), ("선적항", "새빛항"), ("도착지", dest)], 2, lw=84)
            + "<h2>품목</h2>" + tbl(["번호", "품명", "HS 코드", "수량", "중량", "원산지"], rows, widths=["40px", "", "90px", "80px", "80px", "80px"])
            + f"<p style='margin-top:18px'>위 물품의 원산지가 대한민국임을 증명합니다.</p><p>{kdk(d)}</p>"
              f"<div class=foot>새빛상공회의소 {square_seal(rng, '발급<br>기관', 60)}</div>")
    return page(body, **look(rng))


def import_declaration(rng, seq):
    d = rdate(rng)
    origin = rng.choice([("베트남", "초콜릿 쿠키"), ("태국", "과일 주스 농축액"), ("일본", "녹차 과자"), ("폴란드", "웨하스 제품"), ("미국", "시리얼 바")])
    qty = rng.randint(2, 40) * 100
    body = (f"<h1 class=sm>수입식품등 수입신고 확인증</h1><div class=small style='text-align:center'>신고번호 : {d.year}-{rng.randint(100000, 999999)}</div>"
            + kv([("신고일", kd(d)), ("수리일", kd(d + datetime.timedelta(days=rng.randint(1, 3)))), ("영업자", COMPANY), ("영업소 소재지", HQ_ADDR),
                  ("제품명", origin[1]), ("원산지", origin[0]), ("제조업소", f"{rng.choice(['Sunrise Foods', 'Greenfield Co.', 'Nova Bakery'])} ({origin[0]})"),
                  ("수량", f"{qty}박스"), ("중량", f"{qty * rng.choice([6, 8, 10]):,}kg"), ("유통기한", f"제조일로부터 {rng.choice([9, 12, 18])}개월"),
                  ("보관 방법", rng.choice(["실온 보관", "냉장 보관 (0~10℃)"])), ("검사 결과", "서류검사 적합")], 2, lw=92)
            + f"<p class=center style='margin-top:22px'>수입식품안전관리 특별법에 따라 신고하신 내용이 수리되었음을 확인합니다.</p>"
              f"<div class=foot>누리식품안전청 수입검사과 {seal(rng, '직인', 60)}</div>")
    return page(body, **look(rng))


def vehicle_log(rng, seq):
    d = rdate(rng, m1=1, m2=9)
    odo = rng.randint(30, 90) * 1000
    rows, tot = [], 0
    spots = ["물류센터", "수원 거래처", "성남 거래처", "인천 거래처", "화성 거래처", "평택 거래처", "서울 강서 거래처"]
    for i in range(rng.randint(10, 13)):
        dist = rng.randint(18, 140)
        a, b = rng.sample(spots, 2)
        rows.append([f"{d.month}/{rng.randint(1, 28):02d}", a, b, won(odo), won(odo + dist), dist, rng.choice(["납품", "회수", "입고 운송", "거래처 방문"]), ""])
        odo += dist
        tot += dist
    rows.sort(key=lambda r: r[0])
    fuel = tbl(["주유일", "주유량(L)", "금액(원)"], [[f"{d.month}/{rng.randint(1, 28):02d}", f"{rng.randint(35, 60)}", won(rng.randint(5, 9) * 10000)] for _ in range(3)])
    body = (approval(["담당", "팀장"]) + f"<h1 class=sm>차량 운행 일지</h1><div class=clr></div>"
            + kv([("차량번호", f"{rng.randint(10, 99)}가 {rng.randint(1000, 9999)}"), ("차 종", rng.choice(["1톤 냉동탑차", "1톤 카고", "2.5톤 탑차"])),
                  ("운전자", person(rng)), ("운행 월", f"{d.year}년 {d.month}월")], 2, lw=84)
            + tbl(["일자", "출발지", "도착지", "출발 km", "도착 km", "거리", "목적", "비고"], rows, ["c", "l", "l", "r", "r", "r", "c", "c"],
                  ["44px", "", "", "66px", "66px", "44px", "64px", "40px"], foot=f"<td colspan=5>월 합계</td><td class=r>{tot}</td><td colspan=2></td>", cls="s11")
            + "<h2>주유 기록</h2>" + fuel)
    return page(body, extra=".s11 td,.s11 th{font-size:11.5px;padding:4px 5px}", **look(rng), pad="38px 40px")


def evac_map(rng, seq):
    W, H = 660, 380
    xs = sorted(rng.sample(range(150, 500), 2))
    xs = [30, xs[0], xs[1], W - 30]
    names = rng.sample(["사무실", "회의실", "탕비실", "창고", "휴게실", "전산실", "검수실", "상담실", "보관실"], 6)
    cy0, cy1 = 160, 220
    out = f"<svg width={W} height={H} viewBox='0 0 {W} {H}' style='background:#fff;border:1.5px solid #333'>"
    out += f"<rect x=30 y=40 width={W - 60} height={H - 80} fill=#fafafa stroke=#333 stroke-width=3 /><rect x=30 y={cy0} width={W - 60} height={cy1 - cy0} fill=#fff4d6 stroke=#bbb />"
    k = 0
    for row, (y0, y1) in enumerate([(40, cy0), (cy1, H - 40)]):
        for c in range(3):
            out += f"<rect x={xs[c]} y={y0} width={xs[c + 1] - xs[c]} height={y1 - y0} fill=none stroke=#555 /><text x={(xs[c] + xs[c + 1]) / 2} y={(y0 + y1) / 2 + 4} font-size=13 text-anchor=middle>{names[k]}</text>"
            k += 1
    ex = [(30, "비상구"), (W - 30, "비상구")]
    for x, t in ex:
        out += f"<rect x={x - 12} y={cy0 + 12} width=24 height=36 fill=#2f8f4f /><text x={x + (20 if x < 100 else -20)} y={cy1 + 20} font-size=11 text-anchor=middle fill=#2f8f4f>{t}</text>"
    me = rng.randint(xs[0] + 40, xs[2] - 40)
    my = (cy0 + cy1) // 2
    tgt = 30 if me < W / 2 else W - 30
    out += f"<line x1={me} y1={my} x2={tgt + (14 if tgt < 100 else -14)} y2={my} stroke=#c0282d stroke-width=4 stroke-dasharray='10 6' /><circle cx={me} cy={my} r=9 fill=#1f4fa8 /><text x={me} y={my - 16} font-size=12 text-anchor=middle fill=#1f4fa8 font-weight=700>현재 위치</text>"
    for _ in range(3):
        fx = rng.randint(60, W - 60)
        out += f"<rect x={fx} y={cy0 + 4} width=14 height=14 fill=#c0282d /><text x={fx + 7} y={cy0 + 15} font-size=10 text-anchor=middle fill=#fff>F</text>"
    return out + "</svg>"


def evacuation_plan(rng, seq):
    fl = rng.choice(["1층", "2층", "3층"])
    body = (f"<h1 class=sm>비상 대피 안내도</h1><div class=sub>{COMPANY} {rng.choice(['사무동', '물류센터 관리동'])} {fl}</div>"
            f"<div style='margin:14px 0'>{evac_map(rng, seq)}</div>"
            "<p>● 현재 위치 &nbsp; <span style='color:#c0282d'>- - -</span> 대피 경로 &nbsp; <span style='background:#2f8f4f;color:#fff;padding:0 6px'>비상구</span> &nbsp; "
            "<span style='background:#c0282d;color:#fff;padding:0 5px'>F</span> 소화기</p>"
            "<h2>화재 발생 시 행동 요령</h2><ol style='margin:4px 0 4px 20px;padding:0'><li>큰 소리로 주변에 알리고 화재 경보기를 누릅니다.</li>"
            "<li>낮은 자세로 젖은 수건으로 코와 입을 막고 대피 경로를 따라 이동합니다.</li><li>엘리베이터를 사용하지 않고 계단으로 대피합니다.</li>"
            f"<li>건물 밖 집결지({rng.choice(['주차장 입구', '정문 앞 광장'])})에 모여 인원을 확인합니다.</li></ol>"
            f"<p class=small>비상 연락 : 119 · 안전관리자 {person(rng)} {HQ_TEL}</p>")
    return page(body, **look(rng))


def power_of_attorney(rng, seq):
    task = rng.choice(["거래 계약의 체결 및 이행에 관한 일체의 행위", "세무서 제출 서류의 발급 및 수령", "물품 인수 및 대금 수령", "입찰 참가 및 관련 서류 제출", "은행 거래 서류의 제출 및 수령"])
    d = rdate(rng)
    body = ("<h1>위 임 장</h1><h2>위임인</h2>"
            + kv([("상 호", COMPANY), ("대표자", person(rng)), ("사업자번호", biz_no(rng)), ("주 소", HQ_ADDR)], 2, lw=84)
            + "<h2>수임인</h2>"
            + kv([("성 명", person(rng)), ("생년월일", f"{rng.randint(70, 99)}****-*"), ("소 속", rng.choice(TEAMS)), ("연락처", phone(rng))], 2, lw=84)
            + f"<h2>위임 사항</h2><div class=box style='min-height:70px'>{task}</div>"
            + f"<h2>위임 기간</h2><p>{kdk(d)}부터 {kdk(d + datetime.timedelta(days=rng.choice([30, 90, 180])))}까지</p>"
            + f"<p class=center style='margin-top:26px'>위 사항을 위임합니다.</p><p class=center>{kdk(d)}</p>"
              f"<p class=right style='margin-top:20px'>위임인 {COMPANY} 대표이사 {person(rng)} {seal(rng, '인', 52)}</p>")
    return page(body, **look(rng))


NOTICE = {
    "물품 대금 지급 촉구": "귀사는 {d1}에 납품받은 물품의 대금 {a}원을 약정한 {d2}까지 지급하지 않았습니다. 본 내용증명 수령 후 {n}일 이내에 위 금액을 지급해 주시기 바랍니다.",
    "계약 이행 촉구": "귀사는 {d1}자 공급 계약에 따른 최소 구매 수량을 이행하지 않고 있습니다. 본 서면 수령 후 {n}일 이내에 이행하여 주시기 바랍니다.",
    "지연 배상금 청구": "귀사의 대금 지급 지연으로 약정에 따른 지연 배상금 {a}원이 발생하였습니다. 본 서면 수령 후 {n}일 이내에 지급해 주시기 바랍니다.",
    "계약 갱신 거절 통보": "{d1}자 거래 계약은 만료일 {d2}에 갱신하지 않을 예정임을 통보합니다. 만료일 전까지 잔여 물품의 정산을 요청드립니다.",
}


def notice_letter(rng, seq):
    k = rng.choice(list(NOTICE))
    d = rdate(rng)
    t = NOTICE[k].format(d1=kdk(d - datetime.timedelta(days=rng.randint(60, 150))), d2=kdk(d - datetime.timedelta(days=rng.randint(10, 30))),
                        a=won(rng.randint(5, 80) * 100000), n=rng.choice([7, 10, 14]))
    body = ("<h1 style='letter-spacing:12px'>내 용 증 명</h1>"
            + kv([("수신인", f"{rng.choice(CUSTOMERS)} 대표 {person(rng)}"), ("주 소", addr(rng)), ("발신인", f"{COMPANY} 대표이사 {person(rng)}"), ("주 소", HQ_ADDR)], 1, lw=84)
            + f"<h2>제 목 : {k}</h2><p>1. 귀사의 평안을 기원합니다.</p><p>2. {t}</p>"
              "<p>3. 위 기한 내 이행되지 않을 경우 부득이 법적 절차를 진행할 수 있음을 알려드립니다.</p>"
              f"<p class=center style='margin-top:34px'>{kdk(d)}</p><p class=right>발신인 {COMPANY} 대표이사 {person(rng)} {seal(rng, '인', 52)}</p>")
    return page(body, font="serif", **look(rng))


def notice_board(rng, seq):
    d = rdate(rng)
    kinds = [("연말 휴무일 안내", f"{d.year}년 12월 {rng.randint(24, 31)}일", "전 임직원", "회사 휴무일로 지정되며 긴급 업무는 비상 연락망을 이용합니다."),
             ("정기 소방 훈련 실시", kdk(d), "사무동·물류센터 전 직원", "화재 경보 후 대피와 소화기 사용 실습을 진행합니다."),
             ("주차장 공사에 따른 이용 제한", f"{kd(d)} ~ {kd(d + datetime.timedelta(days=rng.randint(5, 14)))}", "차량 이용 임직원", "지하 1층 주차장 일부 구역을 사용할 수 없으니 지상 주차장을 이용해 주세요."),
             ("정보 시스템 점검 안내", f"{kdk(d)} 22:00 ~ 24:00", "전 임직원", "점검 시간 동안 사내 시스템 접속이 제한됩니다."),
             ("하계 휴가 사용 안내", f"{d.year}년 7월 ~ 8월", "전 임직원", "팀별 일정을 조정해 인사총무팀에 제출해 주세요."),
             ("개인정보보호 교육 실시", kdk(d), "전 임직원", "온라인 교육을 이수해야 하며 이수 확인서는 별도 제출하지 않습니다.")]
    t, when, who, what = rng.choice(kinds)
    css = ".bn{background:%s;color:#fff;padding:14px;text-align:center;font-size:28px;letter-spacing:26px;font-weight:800;margin:-44px -48px 24px}"
    lk = look(rng)
    body = (f"<div class=bn>공 고</div><div class=small>공고 번호 : {d.year}-총무-{rng.randint(1, 120):03d} · 게시 기간 {kd(d)} ~ {kd(d + datetime.timedelta(days=14))}</div>"
            f"<h1 class=sm style='margin:16px 0'>{t}</h1><p>임직원 여러분께 다음과 같이 안내드립니다.</p>"
            + kv([("일 시", when), ("대 상", who), ("내 용", what)], 1, lw=84)
            + f"<ul class=b><li>사정이 있는 경우 {rng.choice(TEAMS)} 담당자에게 사전 문의해 주세요.</li><li>자세한 내용은 사내 게시판을 참고하시기 바랍니다.</li></ul>"
            + f"<div class=foot style='margin-top:30px'>{COMPANY} 인사총무팀</div>")
    return page(body, extra=css % lk["ac"], **lk)


def privacy_consent(rng, seq):
    who = rng.choice(["거래처 담당자", "임직원", "방문자"])
    purpose = {"거래처 담당자": "거래 관리 및 연락", "임직원": "인사 관리 및 급여 지급", "방문자": "출입 관리 및 안전 확보"}[who]
    items = {"거래처 담당자": "성명, 소속, 직위, 연락처, 이메일", "임직원": "성명, 생년월일, 연락처, 주소, 계좌 정보", "방문자": "성명, 소속, 연락처, 차량번호"}[who]
    keep = {"거래처 담당자": "거래 종료 후 5년", "임직원": "퇴직 후 3년", "방문자": "방문일로부터 6개월"}[who]
    agree = rng.random() < 0.85
    body = (f"<h1 class=sm>개인정보 수집·이용 동의서 ({who})</h1>"
            f"<p>{COMPANY}은(는) 개인정보 보호법에 따라 아래와 같이 개인정보를 수집·이용합니다.</p>"
            + tbl(["구분", "내용"], [["수집·이용 목적", purpose], ["수집 항목", items], ["보유·이용 기간", keep], ["제3자 제공", "제공하지 않음 (법령에 근거한 경우 제외)"]], ["c", "l"], ["130px", ""])
            + "<p class=small>※ 위 개인정보 수집·이용에 대한 동의를 거부할 권리가 있으며, 거부 시 해당 업무 수행에 제한이 있을 수 있습니다.</p>"
            + f"<p style='margin-top:14px'><b>위 내용에 대해</b> {cb('동의합니다', agree)}{cb('동의하지 않습니다', not agree)}</p>"
            + f"<p class=center style='margin-top:30px'>{kdk(rdate(rng))}</p>"
            + kv([("성 명", f"{person(rng)} (서명)"), ("소 속", rng.choice(CUSTOMERS) if who != "임직원" else rng.choice(TEAMS))], 1, lw=100))
    return page(body, **look(rng))


DOC_TITLES = ["세금계산서 합계표 제출", "거래처 계약서 회신", "소방시설 점검 결과 통보", "보험 갱신 안내", "사업자 현황 신고",
              "납품 단가 조정 요청", "거래 명세서 송부", "물류센터 임대차 갱신 문의", "산업안전 점검 결과", "건강보험 자격 변경"]


def doc_ledger(rng, seq):
    d = rdate(rng, m1=1, m2=9)
    no = rng.randint(1, 60)
    rows = []
    for i in range(rng.randint(13, 16)):
        k = rng.choice(["수신", "발신"])
        rows.append([no + i, f"{d.month}/{rng.randint(1, 28):02d}", k, f"{'수' if k == '수신' else '발'}-{d.year}-{no + i:04d}", rng.choice(DOC_TITLES),
                     rng.choice(CUSTOMERS + ["누리세무서", "새빛시청", "건강보험공단"]), person(rng), ""])
    rows.sort(key=lambda r: r[1])
    body = (approval(["담당", "팀장"]) + f"<h1 class=sm>문서 수발 대장</h1><div class=sub>{d.year}년 · 인사총무팀</div><div class=clr></div>"
            + tbl(["번호", "일자", "구분", "문서번호", "문서 제목", "상대 기관", "담당자", "확인"], rows, ["c", "c", "c", "c", "l", "l", "c", "c"],
                  ["38px", "46px", "40px", "88px", "", "108px", "56px", "40px"], cls="s11"))
    return page(body, extra=".s11 td,.s11 th{font-size:11.5px;padding:5px 4px}", **look(rng), pad="36px 34px")


def parking_permit(rng, seq):
    d = rdate(rng)
    plate = f"{rng.randint(10, 99)}가 {rng.randint(1000, 9999)}"
    body = ("<div style='width:600px;margin:20px auto;border:4px solid #1f3a5f;padding:26px 30px;text-align:center'>"
            "<div style='background:#1f3a5f;color:#fff;font-size:26px;letter-spacing:10px;padding:8px;font-weight:800'>주 차 허 가 증</div>"
            f"<div style='border:3px solid #222;margin:22px auto;padding:10px;width:340px;font-size:34px;font-weight:800;border-radius:6px'>{plate}</div>"
            + kv([("허가번호", f"PK-{d.year}-{rng.randint(1, 300):04d}"), ("성 명", person(rng)), ("소 속", rng.choice(TEAMS)), ("차 종", rng.choice(["승용", "SUV", "승합"])),
                  ("주차 구역", rng.choice(["지상 A구역", "지상 B구역", "지하 1층"])), ("유효 기간", f"{kd(d)} ~ {d.year + 1}.{d.month:02d}.{d.day:02d}")], 1, lw=100)
            + f"<p class=small style='margin-top:12px'>※ 차량 전면 유리 안쪽에 부착해 주세요. 양도·대여를 금지하며 분실 시 인사총무팀에 신고해 주세요.</p>"
              f"<p style='margin-top:10px'>{COMPANY} 인사총무팀 {seal(rng, '직인', 50)}</p></div>")
    return page(body, **look(rng, ta="center"))


def corp_registry(rng, seq):
    c = rng.choice([COMPANY] + CUSTOMERS[:8])
    nm = c
    d = rdate(rng)
    objs = rng.sample(["식료품 도소매업", "음료 도소매업", "물류 및 창고업", "무역업", "전자상거래업", "프랜차이즈 사업", "부동산 임대업", "소프트웨어 개발업"], 5)
    ceo = person(rng)
    rows = [["대표이사", ceo, f"{rng.randint(65, 85)}****-*******", addr(rng)], ["이사", person(rng), f"{rng.randint(65, 90)}****-*******", addr(rng)],
            ["이사", person(rng), f"{rng.randint(65, 90)}****-*******", addr(rng)], ["감사", person(rng), f"{rng.randint(60, 90)}****-*******", addr(rng)]]
    body = (f"<div class=small>고유번호 {rng.randint(1100, 1999)}-{rng.randint(10, 99)}-{rng.randint(100000, 999999)}</div><h1 class=sm>등기사항전부증명서 (현재 사항)</h1>"
            + kv([("상 호", nm), ("본 점", addr(rng)), ("공고 방법", "회사의 인터넷 홈페이지에 게재"), ("1주의 금액", "금 5,000원"),
                  ("발행할 주식 총수", f"{rng.choice([100000, 200000, 500000]):,}주"), ("발행 주식 총수", f"{rng.choice([20000, 40000, 100000]):,}주"),
                  ("자본금", f"금 {rng.choice([100, 200, 500]) * 1000000:,}원")], 1, lw=130)
            + "<h2>목 적</h2><ol style='margin:2px 0 6px 20px;padding:0'>" + "".join(f"<li>{o}</li>" for o in objs) + "<li>위 각호에 관련된 부대사업 일체</li></ol>"
            + "<h2>임원에 관한 사항</h2>" + tbl(["직책", "성명", "주민등록번호", "주소"], rows, ["c", "c", "c", "l"], ["64px", "70px", "130px", ""], cls="s11")
            + f"<p class=center style='margin-top:14px'>위 등기사항이 등기부의 내용과 틀림없음을 증명합니다.</p><p class=center>{kdk(d)}</p>"
              f"<div class=foot style='margin-top:12px'>새빛지방법원 누리등기소 등기관 {seal(rng, '직인', 54)}</div>")
    return page(body, extra=".s11 td,.s11 th{font-size:11.5px;padding:4px 6px}", **look(rng, ta="center"), pad="36px 46px")


OPINIONS = {
    "거래처 대금 미지급 시 조치": ("거래처가 납품 대금 {a}원을 {n}개월째 지급하지 않고 있음.", "미지급 대금을 청구하기 위해 취할 수 있는 법적 조치와 순서",
                           ["내용증명으로 지급을 최고하고 지급 기한을 명시하면 이후 소송에서 지연 이행의 증거로 활용할 수 있습니다.", "지급이 이루어지지 않으면 지급명령 신청이 비용과 기간 면에서 효율적입니다. 이의가 제기되면 정식 소송으로 이행합니다.", "거래 계약서의 지연 배상 조항을 확인해 약정 이율에 따른 지연 손해금을 함께 청구할 수 있습니다."],
                           "내용증명 발송 후 지급명령을 신청하는 순서를 권합니다."),
    "상표 사용 권리": ("자사 제품명 '{p}'를 거래처가 자기 포장에 사용하고 있음.", "상표권 침해 여부와 중지 요청의 근거",
                  ["등록된 상표와 동일·유사한 표장을 동일한 상품에 사용하면 상표권 침해가 성립할 수 있습니다.", "등록 여부와 지정 상품 범위를 먼저 확인해야 하며, 미등록이라면 부정경쟁방지법상 보호 가능성을 검토합니다.", "경고장을 통해 사용 중지를 요청하고 불응 시 침해금지를 구하는 절차를 검토할 수 있습니다."],
                  "등록 여부를 확인한 뒤 경고장을 발송하는 것이 우선입니다."),
    "표시 광고 위반 가능성": ("신제품 포장에 '{p} 무첨가'라는 문구를 사용하려 함.", "해당 표시가 표시광고법상 문제가 되는지 여부",
                      ["무첨가 표시는 실제 원료와 공정에서 첨가물이 사용되지 않았음을 입증할 수 있어야 합니다.", "일부 원료에 첨가물이 포함되어 있다면 소비자를 오인시켜 부당한 표시로 판단될 수 있습니다.", "표시 문구를 확정하기 전 원료 성분표와 제조 공정 자료를 보관해 입증 책임에 대비해야 합니다."],
                      "원료 성분을 확인해 입증 가능한 범위에서만 표시하기를 권합니다."),
    "계약 해지의 효력": ("거래처의 반복적인 납기 지연을 이유로 공급 계약을 해지하려 함.", "해지 통보가 유효하려면 갖춰야 할 요건",
                    ["계약서의 해지 사유와 사전 시정 요구 절차를 충족해야 해지가 유효하게 인정됩니다.", "시정 요구 없이 곧바로 해지하면 부당 해지로 손해배상 책임이 생길 수 있습니다.", "납기 지연 사실을 입증할 발주서와 입고 기록을 보관하는 것이 중요합니다."],
                    "서면으로 시정을 요구한 뒤 기한 경과 시 해지하는 순서를 권합니다."),
}


def legal_opinion(rng, seq):
    k = rng.choice(list(OPINIONS))
    case, q, paras, concl = OPINIONS[k]
    case = case.format(a=won(rng.randint(5, 80) * 100000), n=rng.randint(2, 6), p=rng.choice(PRODUCTS)[0])
    firm = rng.choice(["법무법인 새빛", "법무법인 누리", "법률사무소 한결"])
    d = rdate(rng)
    body = (f"<div style='border-bottom:3px solid #1f3a5f;padding-bottom:8px;margin-bottom:12px'><b style='font-size:20px;color:#1f3a5f'>{firm}</b>"
            f"<span class=small style='float:right'>서울 새빛구 누리로 {rng.randint(10, 300)} · {tel(rng, '02')}</span></div>"
            f"<h1 class=sm style='margin:14px 0'>법 률 자 문 의 견 서</h1>"
            + kv([("의뢰인", COMPANY), ("작성일", kdk(d)), ("주 제", k), ("관련 부서", rng.choice(TEAMS))], 2, lw=84)
            + f"<h2>1. 사안 개요</h2><p>{case}</p><h2>2. 질의</h2><p>{q}</p><h2>3. 의견</h2>"
            + "".join(f"<p>({i + 1}) {p}</p>" for i, p in enumerate(paras))
            + f"<h2>4. 결론</h2><p>{concl}</p><p class=small>※ 본 의견은 제공된 자료를 전제로 한 것으로, 사실관계가 달라지면 결론이 달라질 수 있습니다.</p>"
              f"<p class=right style='margin-top:24px'>{firm} 변호사 {person(rng)} {seal(rng, '인', 50)}</p>")
    return page(body, font="serif", **look(rng, ta="left"))


SPECS = [("LEG-04", "산업재해 발생 보고서", accident_report), ("LEG-05", "HACCP 인증서", haccp_cert),
         ("LEG-06", "품질검사 성적서", quality_report), ("LEG-07", "원산지 증명서", origin_cert),
         ("LEG-08", "수입식품 신고필증", import_declaration), ("LEG-09", "차량운행일지", vehicle_log),
         ("LEG-10", "비상 대피 안내도", evacuation_plan), ("LEG-11", "위임장", power_of_attorney),
         ("LEG-12", "내용증명", notice_letter), ("LEG-13", "사내 공고문", notice_board),
         ("LEG-14", "개인정보 수집·이용 동의서", privacy_consent), ("LEG-15", "문서수발대장", doc_ledger),
         ("LEG-16", "주차 허가증", parking_permit), ("LEG-17", "법인 등기사항증명서", corp_registry),
         ("LEG-18", "법률 자문 의견서", legal_opinion)]
