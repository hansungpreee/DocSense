"""고객/거래처 12종 (CUS-04~CUS-15) 양식. 거래처 이름·대표자·사업자번호는 모두 지어낸 것이다 (번호는 일부를 가림)."""
import calendar
import datetime

from src.eval.plan75.common import (COMPANY, CUSTOMERS, HQ_ADDR, HQ_TEL, PRODUCTS, ROADS, TEAMS, addr, approval, biz_no,
                                    e, kd, kdk, kv, look, page, people, person, phone, rdate, seal, sign, square_seal,
                                    tbl, tel, won)


def cb(label, on):
    return f"<span class='cb{' on' if on else ''}'></span>{label}&nbsp;&nbsp;"


def cust_register(rng, seq):
    name = rng.choice(CUSTOMERS)
    pay = rng.choice(["월말 마감 익월 말일 현금", "월말 마감 익월 15일 현금", "납품 후 30일 현금", "어음 60일", "선입금 후 출고"])
    docs = ["사업자등록증 사본", "통장 사본", "인감증명서", "신용평가서", "대표자 신분증 사본"]
    body = (approval(["담당", "영업팀장", "재무팀장", "대표이사"]) + "<h1>거래처 등록 신청서</h1><div class=clr></div>"
            + kv([("신청일", kdk(rdate(rng))), ("신청 부서", rng.choice(["영업1팀", "영업2팀", "가맹사업팀"])),
                  ("상 호", name), ("대표자", person(rng)), ("사업자등록번호", biz_no(rng)),
                  ("업태 / 종목", rng.choice(["도소매 / 식품 유통", "도소매 / 식자재", "소매 / 슈퍼마켓", "도매 / 음료·과자"])),
                  ("사업장 주소", addr(rng)), ("전화", tel(rng)), ("거래 담당자", f"{person(rng)} ({phone(rng)})"),
                  ("거래 개시 희망일", kdk(rdate(rng, m1=8, m2=12))), ("결제 조건", pay),
                  ("거래 은행", f"{rng.choice(['새빛', '누리', '푸른', '한결'])}은행 {rng.randint(100, 999)}-****-{rng.randint(1000, 9999)}"),
                  ("예상 월 거래액", f"{won(rng.choice([5, 10, 20, 30, 50]) * 1000000)}원")], 2, lw=100)
            + "<h2>첨부 서류</h2><p>" + "".join(cb(d, rng.random() < 0.8) for d in docs) + "</p>"
            + "<p class=center style='margin-top:22px'>위와 같이 거래처 등록을 신청합니다.</p>"
            + sign(["신청 담당", "검토", "승인"]))
    return page(body, **look(rng))


def credit_eval(rng, seq):
    items = [("재무 안정성 (부채비율·유동비율)", 30), ("업력·사업 규모", 15), ("결제 이력 (연체 여부)", 25), ("담보·보증 제공", 15), ("업계 평판", 15)]
    got = [max(3, int(m * rng.uniform(0.45, 1.0))) for _, m in items]
    tot = sum(got)
    grade = "A" if tot >= 85 else "B" if tot >= 70 else "C" if tot >= 55 else "D"
    limit = {"A": 80000000, "B": 50000000, "C": 20000000, "D": 0}[grade]
    rows = [[n, m, g, ""] for (n, m), g in zip(items, got)]
    body = ("<h1>거래처 신용평가표</h1>"
            + kv([("거래처", rng.choice(CUSTOMERS)), ("평가일", kd(rdate(rng))), ("사업자등록번호", biz_no(rng)),
                  ("업력", f"{rng.randint(2, 25)}년"), ("대표자", person(rng)), ("평가 구분", rng.choice(["신규 등록", "정기 재평가"]))], 2)
            + tbl(["평가 항목", "배점", "득점", "비고"], rows, ["l", "c", "c", "l"], ["", "70px", "70px", "140px"],
                  foot=f"<td>합 계</td><td class=c>100</td><td class=c>{tot}</td><td></td>")
            + kv([("신용 등급", f"<b style='font-size:17px'>{grade}</b> (A 85↑ · B 70↑ · C 55↑ · D 55 미만)"),
                  ("여신 한도 권고", f"{won(limit)}원" if limit else "거래 보류 (선입금 거래)")], 1, lw=110)
            + "<h2>평가 의견</h2><div class=box style='min-height:70px'>최근 12개월 결제 기한 준수 여부와 재무 지표를 종합해 등급을 산정함. "
              "등급 변동 시 여신 한도를 재조정한다.</div>" + sign(["평가자", "재무팀장", "대표이사"]))
    return page(body, **look(rng))


CLAIMS = {
    "유통기한 임박 입고": ("납품 제품의 잔여 유통기한이 계약 기준(60%)에 못 미침", "출고 시 선입선출 확인이 누락됨", "제품 회수 후 신규 LOT로 교환", "출고 전 유통기한 이중 확인 절차 추가"),
    "포장 파손": ("박스 하단이 눌려 내부 제품 {n}개가 파손됨", "상차 적재 높이 초과와 운송 중 충격", "파손분 전량 교환 및 운임 당사 부담", "적재 단수 제한과 완충재 보강"),
    "수량 부족": ("발주 {n}박스 대비 {m}박스만 도착함", "출고 검수 시 수량 대조 누락", "부족 수량 익일 추가 배송", "출고 검수 시 이중 서명 시행"),
    "오배송": ("주문하지 않은 제품이 포함되어 도착함", "피킹 단계에서 유사 품번 혼동", "오배송 제품 회수 후 정상 제품 재출고", "유사 품번 위치 분리와 스캔 검수"),
}


def claim_report(rng, seq):
    k = rng.choice(list(CLAIMS))
    d, cause, act, prev = CLAIMS[k]
    n = rng.randint(3, 12)
    d = d.format(n=n, m=n - rng.randint(1, 2))
    pr = rng.choice(PRODUCTS)
    r = rdate(rng)
    body = ("<h1>클레임 처리 보고서</h1>"
            + kv([("접수번호", f"CL-{r.year}-{rng.randint(1, 300):03d}"), ("접수일", kd(r)), ("거래처", rng.choice(CUSTOMERS)),
                  ("거래처 담당", person(rng)), ("대상 품목", f"{pr[0]} ({pr[1]})"), ("LOT 번호", f"L{r.year % 100}{rng.randint(1000, 9999)}"),
                  ("클레임 유형", f"<b>{k}</b>"), ("처리 담당", f"{rng.choice(TEAMS)} {person(rng)}")], 2)
            + f"<h2>클레임 내용</h2><div class=box>{d}</div><h2>원인 분석</h2><div class=box>{cause}</div>"
            + f"<h2>조치 내용</h2><div class=box>{act}</div><h2>재발 방지 대책</h2><div class=box>{prev}</div>"
            + kv([("처리 결과", rng.choice(["완료 (거래처 확인)", "완료", "진행 중"])), ("처리 완료일", kd(r + datetime.timedelta(days=rng.randint(1, 7))))], 2)
            + sign(["담당", "팀장", "대표이사"]))
    return page(body, **look(rng))


def renewal_notice(rng, seq):
    c = rng.choice(CUSTOMERS)
    end = rdate(rng, m1=10, m2=12)
    body = (f"<div class=small>문서번호: 영업-{end.year}-{rng.randint(1, 200):03d} · 시행일 {kd(rdate(rng, m1=8, m2=10))}</div>"
            f"<p style='margin-top:18px'><b>수 신</b> : {c} 대표이사 귀하</p><p><b>참 조</b> : 구매 담당자</p>"
            "<h1 class=sm style='margin:20px 0'>제 목 : 거래 계약 갱신 안내</h1>"
            f"<p>1. 귀사의 일익 번창을 기원합니다.</p><p>2. 당사와 귀사 간 물품 공급 거래 계약이 {kdk(end)}자로 만료될 예정이므로 "
            "아래와 같이 계약 갱신 조건을 안내드립니다.</p>"
            + tbl(["구분", "현행", "갱신 후"], [["계약 기간", "1년", f"{rng.choice(['1년', '2년'])} (자동 연장 조항 포함)"],
                                                 ["결제 조건", "월말 마감 익월 말일", rng.choice(["월말 마감 익월 말일", "월말 마감 익월 15일"])],
                                                 ["최소 월 거래 규모", f"{won(rng.choice([5, 10]) * 1000000)}원", f"{won(rng.choice([8, 12, 15]) * 1000000)}원"],
                                                 ["배송 조건", "주 2회 정기 배송", rng.choice(["주 2회 정기 배송", "주 3회 정기 배송"])]],
                  ["c", "l", "l"], ["110px", "", ""])
            + f"<p>3. 갱신을 원하시면 {kdk(end - datetime.timedelta(days=30))}까지 아래 담당자에게 회신해 주시기 바랍니다.</p>"
              f"<p>4. 문의: 영업팀 {person(rng)} ({HQ_TEL} 내선 {rng.randint(300, 399)})</p>"
              f"<p style='margin-top:20px'>붙임: 거래 계약서(안) 1부. 끝.</p>"
              f"<div class=foot>{COMPANY} 대표이사 {seal(rng, '직인', 62)}</div>")
    return page(body, **look(rng))


def newsletter(rng, seq):
    m = rng.randint(1, 12)
    ps = rng.sample(PRODUCTS, 3)
    items = "".join(f"<div class=nb><b>{p[0]}</b><div class=small>{p[1]} · 공급가 {won(p[2])}원</div>"
                    f"<p>{rng.choice(['새로운 맛으로 출시했습니다.', '시즌 한정 포장으로 선보입니다.', '신규 거래처 대상 첫 주문 혜택이 있습니다.'])}</p></div>" for p in ps)
    promos = tbl(["기간", "행사 내용"], [[f"{m}/{rng.randint(1, 10)} ~ {m}/{rng.randint(15, 28)}", rng.choice(["10박스 이상 주문 시 1박스 추가", "신제품 첫 주문 5% 할인", "음료 전 품목 묶음 할인"])] for _ in range(3)],
                 ["c", "l"], ["110px", ""])
    notices = "".join(f"<li>{x}</li>" for x in rng.sample(["명절 연휴 전 마지막 출고일은 별도 공지합니다.", "배송 시간이 오전 중심으로 조정됩니다.", "발주 마감 시간은 오후 3시로 변경됩니다.", "냉장 제품은 하역 후 즉시 보관해 주세요."], 3))
    css = (".hd{background:var(--bg);color:#fff;padding:18px 22px;margin:-44px -48px 18px}.hd h1{color:#fff;text-align:left;letter-spacing:2px;font-size:26px}"
           ".g{display:grid;grid-template-columns:1fr 1fr;gap:18px}.nb{border-bottom:1px dashed #999;padding:8px 0}.nb p{margin:3px 0}")
    lk = look(rng)
    body = (f"<div class=hd style='--bg:{lk['ac']}'><h1>HS 파트너 소식 {m}월호</h1><div style='color:#eee;margin-top:4px'>"
            f"{COMPANY} 거래처 소식지 · 제{rng.randint(20, 90)}호</div></div>"
            f"<div class=g><div><h2>이달의 신제품</h2>{items}</div><div><h2>이달의 프로모션</h2>{promos}<h2>물류 공지</h2><ul class=b>{notices}</ul></div></div>"
            f"<h2>문의</h2><p>영업지원팀 {HQ_TEL} · 주문 마감 평일 15:00</p>")
    return page(body, extra=css, **lk)


def visitor_pass(rng, seq):
    zones = ["사무동", "물류창고 A동", "냉동·냉장창고", "하역장"]
    on = rng.sample(zones, rng.randint(1, 2))
    r = rdate(rng)
    st = rng.choice([9, 10, 13, 14])
    body = ("<div style='border:3px solid #1f3a5f;padding:22px 26px'>"
            f"<div class=small>허가번호 VP-{r.year}-{rng.randint(1, 999):04d}</div><h1 class=sm style='margin:8px 0 14px'>거래처 방문자 출입 허가증</h1>"
            + kv([("방문 회사", rng.choice(CUSTOMERS)), ("방문자", person(rng)), ("연락처", phone(rng)), ("차량번호", f"{rng.randint(10, 99)}가 {rng.randint(1000, 9999)}"),
                  ("방문 목적", rng.choice(["납품 입회", "계약 협의", "재고 확인", "시설 견학"])), ("면담 담당", f"{rng.choice(TEAMS)} {person(rng)}"),
                  ("허가 일시", f"{kd(r)} {st:02d}:00 ~ {st + rng.choice([2, 3]):02d}:00"), ("방문 인원", f"{rng.randint(1, 4)}명")], 2, lw=84)
            + "<p style='margin:12px 0 4px'><b>출입 허용 구역</b> : " + "".join(cb(z, z in on) for z in zones) + "</p>"
            + "<ul class=b><li>방문 중 안전모와 방문증을 착용해 주세요.</li><li>시설 내 촬영과 무단 출입을 금지합니다.</li><li>퇴실 시 방문증을 경비실에 반납해 주세요.</li></ul>"
            + sign(["신청", "면담자", "보안담당"]) + "</div>")
    return page(body, **look(rng))


def seal_cert(rng, seq):
    nm = person(rng)
    d = rdate(rng)
    body = ("<div style='border:2px solid #333;padding:26px 30px'>"
            f"<div class=small>발급번호 {d.year}-{rng.randint(10000, 99999)}</div><h1 style='margin:14px 0 20px'>인 감 증 명 서</h1>"
            + kv([("성 명", nm), ("생년월일", f"{rng.randint(55, 85)}****-*"), ("주 소", addr(rng)), ("용 도", rng.choice(["거래 계약", "물품 공급 계약", "법인 대표자 확인"]))], 1, lw=100)
            + f"<table class=kv><tr><th style='width:100px;height:96px'>인 영</th><td class=c style='height:96px'>{square_seal(rng, nm[-2:] + '<br>' + '印', 70)}</td></tr></table>"
            + f"<p class=center style='margin-top:18px'>위 인감이 신고되어 있음을 증명합니다.</p><p class=center>{kdk(d)}</p>"
            + f"<div class=foot>새빛시 누리구청장 {seal(rng, '직인', 58)}</div>"
            + "<p class=small center>※ 이 증명서는 발급일로부터 3개월간 사용할 수 있습니다.</p></div>")
    return page(body, font="serif", **look(rng, ta="center"))


def biz_reg(rng, seq):
    c = rng.choice(CUSTOMERS)
    nm = c.replace("(주)", "")
    d = rdate(rng, 2008, 1, 12)
    body = ("<div style='border:3px double #2f6f4f;padding:24px 30px'><div class=small>등록번호 : " + biz_no(rng) + "</div>"
            "<h1 style='margin:10px 0 18px'>사 업 자 등 록 증</h1><div class=center style='margin-bottom:10px'>( 법인사업자 )</div>"
            + kv([("법인명(단체명)", c), ("대 표 자", person(rng)), ("개업 연월일", kdk(d)), ("법인등록번호", f"{rng.randint(110000, 199999)}-*******"),
                  ("사업장 소재지", addr(rng)), ("본점 소재지", addr(rng)),
                  ("사업의 종류", f"업태 {rng.choice(['도매 및 소매업', '도소매업'])} / 종목 {rng.choice(['식료품', '음료 및 과자', '식자재'])}"),
                  ("발급 사유", rng.choice(["신규", "정정", "재발급"]))], 1, lw=120)
            + f"<p class=center style='margin-top:20px'>{kdk(rdate(rng))}</p><div class=foot>누리세무서장 {seal(rng, '직인', 60)}</div></div>")
    return page(body, **look(rng, ta="center"))


def map_svg(rng, dest):
    W, H = 700, 330
    xs = [0, rng.randint(200, 260), rng.randint(430, 500), W]
    ys = [0, rng.randint(100, 130), rng.randint(210, 240), H]
    poi = ["은행", "편의점", "주유소", "초등학교", "우체국", "약국", "카페", "공원", "주민센터", "마트"]
    rng.shuffle(poi)
    d = rng.randrange(9)
    out = f"<svg width={W} height={H} viewBox='0 0 {W} {H}' style='border:1.5px solid #444;background:#f6f4ec'>"
    for i in (1, 2):
        out += f"<rect x={xs[i] - 9} y=0 width=18 height={H} fill=#fff stroke=#bbb /><rect x=0 y={ys[i] - 9} width={W} height=18 fill=#fff stroke=#bbb />"
    k = 0
    for r in range(3):
        for c in range(3):
            x0, x1, y0, y1 = xs[c] + (9 if c else 12), xs[c + 1] - (9 if c < 2 else 12), ys[r] + (9 if r else 12), ys[r + 1] - (9 if r < 2 else 12)
            isd = (r * 3 + c) == d
            fill = "#e8b4b4" if isd else "#dfe6ec"
            out += f"<rect x={x0 + 12} y={y0 + 12} width={x1 - x0 - 24} height={y1 - y0 - 24} fill={fill} stroke=#778 />"
            label = dest if isd else poi[k % len(poi)]
            k += 1
            out += f"<text x={(x0 + x1) / 2} y={(y0 + y1) / 2 + 4} font-size={14 if isd else 12} text-anchor=middle fill=#222 font-weight={700 if isd else 400}>{label}</text>"
            if isd:
                out += f"<circle cx={(x0 + x1) / 2} cy={y0 + 22} r=7 fill=#c0282d />"
    rn = rng.sample(ROADS, 3)
    out += f"<text x=8 y={ys[1] + 4} font-size=11 fill=#555>{rn[0]}</text><text x=8 y={ys[2] + 4} font-size=11 fill=#555>{rn[1]}</text>"
    out += f"<text x={xs[1] - 4} y=130 font-size=11 fill=#555 transform='rotate(90 {xs[1] - 4} 130)'>{rn[2]}</text>"
    sx, sy = xs[rng.choice([1, 2])], ys[rng.choice([1, 2])]
    out += f"<circle cx={sx} cy={sy} r=11 fill=#2f6f4f /><text x={sx} y={sy + 4} font-size=10 text-anchor=middle fill=#fff>지하철</text>"
    out += "<text x=668 y=24 font-size=13 text-anchor=middle>N</text><polygon points='668,28 662,44 674,44' fill=#333 />"
    return out + "</svg>"


def location_map(rng, seq):
    c = rng.choice(CUSTOMERS)
    body = (f"<h1 class=sm>{c} 위치 약도</h1><div class=sub>방문 시 참고해 주세요</div><div style='margin:14px 0'>{map_svg(rng, c.replace('(주)', ''))}</div>"
            + kv([("주 소", addr(rng)), ("전 화", tel(rng)), ("담당자", f"{person(rng)} ({phone(rng)})")], 1, lw=90)
            + f"<h2>오시는 길</h2><ul class=b><li>지하철 {rng.randint(1, 9)}호선 {rng.randint(1, 6)}번 출구에서 도보 {rng.randint(3, 15)}분</li>"
              f"<li>버스 {rng.randint(10, 99)}번, {rng.randint(100, 999)}번 이용 후 정류장에서 도보 {rng.randint(2, 8)}분</li>"
              f"<li>자가용 이용 시 건물 뒤편 하역장 진입로를 이용해 주세요. 방문 주차 {rng.randint(2, 6)}대 가능</li></ul>")
    return page(body, **look(rng))


def appointment(rng, seq):
    c = rng.choice(CUSTOMERS)
    role = rng.choice(["HS 파트너스 자문위원", "우수 거래처 협의회 위원", "지역 협력점 대표", "신제품 모니터링 위원"])
    d = rdate(rng)
    body = ("<div style='border:6px double #7a3b2e;padding:34px 38px;margin-top:10px;text-align:center'>"
            f"<div class=small style='text-align:left'>제 {d.year}-{rng.randint(1, 80):03d} 호</div><h1 style='font-size:40px;letter-spacing:18px;margin:26px 0 30px'>위 촉 장</h1>"
            f"<p style='font-size:17px;margin:6px 0'><b>{c}</b></p><p style='font-size:17px;margin:6px 0'>대표 <b>{person(rng)}</b> 귀하</p>"
            f"<p style='font-size:16px;margin:30px 0 8px;line-height:2'>귀하를 {COMPANY}의 <b>{role}</b>(으)로 위촉합니다.<br>"
            f"위촉 기간은 {kd(d)}부터 {d.year + rng.choice([1, 2])}.{d.month:02d}.{d.day:02d}까지입니다.</p>"
            f"<p style='margin-top:34px;font-size:15px'>{kdk(d)}</p><div class=foot style='margin-top:24px'>{COMPANY} 대표이사 {person(rng)} {seal(rng, '직인', 66)}</div></div>")
    return page(body, font="serif", **look(rng, ta="center"))


def thanks_letter(rng, seq):
    c = rng.choice(CUSTOMERS)
    n = rng.randint(2, 15)
    d = rdate(rng, m1=11, m2=12)
    body = ("<div style='border:3px solid #8a5a14;outline:1px solid #8a5a14;outline-offset:6px;padding:34px 40px;margin:10px 8px;text-align:center'>"
            "<div style='color:#8a5a14;font-size:20px'>◆ ◆ ◆</div><h1 style='font-size:38px;letter-spacing:14px;margin:12px 0 26px;color:#8a5a14'>감 사 장</h1>"
            f"<p style='font-size:19px;margin:6px 0'><b>{c}</b></p><p style='font-size:15px;color:#555'>거래 {n}주년</p>"
            f"<p style='font-size:16px;line-height:2.1;margin:24px 0'>귀사는 지난 한 해 동안 변함없는 신뢰로 저희와 함께해 주셨습니다.<br>"
            f"덕분에 안정적인 공급을 이어 갈 수 있었기에 깊이 감사드리며,<br>앞으로도 상생의 파트너로 함께하기를 바랍니다.</p>"
            f"<p style='margin-top:30px'>{kdk(d)}</p><div class=foot style='margin-top:20px'>{COMPANY} 대표이사 {person(rng)} {seal(rng, '직인', 66)}</div></div>")
    return page(body, font="serif", **look(rng, ta="center"))


def event_calendar(rng, seq):
    y, m = 2026, rng.randint(1, 12)
    days = [x for w in calendar.Calendar(6).monthdayscalendar(y, m) for x in w]
    ev = {}
    kinds = [("정기 배송", "#dbe8f7"), ("프로모션", "#fbe3cc"), ("시식 행사", "#e3f1d9"), ("물류센터 휴무", "#f8d7da"), ("가격 개정", "#ece3f4")]
    for k, color in kinds:
        for _ in range(rng.randint(2, 4) if k != "가격 개정" else 1):
            ev[rng.randint(1, calendar.monthrange(y, m)[1])] = (k, color)
    head = "".join(f"<th style='color:{'#c0282d' if i == 0 else '#1b1f24'}'>{w}</th>" for i, w in enumerate("일월화수목금토"))
    rows = ""
    for i in range(0, len(days), 7):
        cells = ""
        for dd in days[i:i + 7]:
            if dd == 0:
                cells += "<td style='height:78px;background:#fafafa'></td>"
            else:
                k, col = ev.get(dd, ("", "#fff"))
                cells += f"<td style='height:78px;vertical-align:top;background:{col};padding:4px 5px'><b>{dd}</b><div style='font-size:11px;margin-top:6px'>{k}</div></td>"
        rows += f"<tr>{cells}</tr>"
    leg = " ".join(f"<span style='background:{c};padding:2px 8px;border:1px solid #999;margin-right:6px'>{k}</span>" for k, c in kinds)
    body = (f"<h1 class=sm>{y}년 {m}월 거래처 행사 캘린더</h1><div class=sub>{COMPANY} 영업지원팀</div>"
            f"<table class=t style='margin-top:14px'><tr>{head}</tr>{rows}</table><p>{leg}</p>"
            f"<p class=small>※ 일정은 물류 사정에 따라 변경될 수 있으며 변경 시 담당자가 개별 안내합니다. 문의 {HQ_TEL}</p>")
    return page(body, **look(rng), pad="40px 40px")


SPECS = [("CUS-04", "거래처 등록신청서", cust_register), ("CUS-05", "거래처 신용평가표", credit_eval),
         ("CUS-06", "클레임 처리 보고서", claim_report), ("CUS-07", "거래처 계약 갱신 통지서", renewal_notice),
         ("CUS-08", "거래처 월간 소식지", newsletter), ("CUS-09", "거래처 출입 허가증", visitor_pass),
         ("CUS-10", "거래처 대표자 인감증명서", seal_cert), ("CUS-11", "사업자등록증", biz_reg),
         ("CUS-12", "거래처 위치 약도", location_map), ("CUS-13", "거래처 위촉장", appointment),
         ("CUS-14", "거래처 감사장", thanks_letter), ("CUS-15", "거래처 월간 행사 캘린더", event_calendar)]
