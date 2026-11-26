"""인사/채용 10종 (HR-06~HR-15) 양식. 각 함수는 (rng, 번호)를 받아 A4 한 쪽 HTML을 돌려준다."""
from src.eval.plan75.common import *  # noqa: F401,F403
from src.eval.plan75.common import (people, COMPANY, HQ_ADDR, POSITIONS, TEAMS, approval, e, kd, kdk, kv, look, page, person,
                                    rdate, seal, sign, square_seal, tbl, won)


def welfare(rng, seq):
    a, b = rng.choice([15, 20, 30, 40]), rng.choice([30, 50, 70, 100])
    items = [
        ("건강검진 지원", "재직 1년 이상 전 임직원", f"연 1회 종합검진 비용 최대 {a}만원 지원", "사내 포털 신청 후 검진 결과 제출"),
        ("경조사비 지원", "전 임직원", f"결혼 {b}만원, 조의 {b // 2}만원, 출산 {b // 2}만원 지급", "증빙서류 첨부 후 인사총무팀 제출"),
        ("자녀 학자금", "초·중·고 자녀를 둔 임직원", f"분기당 최대 {rng.choice([30, 40, 50])}만원 지원", "재학증명서 제출"),
        ("명절 선물", "전 임직원", "설·추석 자사 제품 선물 세트 지급", "별도 신청 없음"),
        ("휴양시설 이용", "재직 6개월 이상", f"제휴 리조트 연 {rng.choice([2, 3, 4])}박 할인", "예약 후 사내 포털에 등록"),
        ("교육비 지원", "전 임직원", f"직무 관련 교육 수강료 {rng.choice([50, 70, 100])}% 지원", "수료증 제출 후 정산"),
        ("식대 지원", "전 임직원", f"중식 월 {rng.choice([10, 12, 15])}만원 지급", "급여에 합산 지급"),
        ("통근버스 운행", "물류센터 근무자", "용인·수원 노선 출퇴근 운행", "노선표 확인 후 탑승 등록"),
        ("동호회 활동비", "3인 이상 동호회", f"분기당 인당 {rng.choice([2, 3, 5])}만원 지원", "활동 사진과 영수증 제출"),
        ("장기근속 포상", "근속 5·10·15년", f"기념품과 특별휴가 {rng.choice([3, 5])}일 부여", "해당 월 자동 안내"),
        ("단체상해보험", "전 임직원", f"상해 사고 시 최대 {rng.choice([3, 5, 10])}천만원 보장", "입사 시 자동 가입"),
        ("육아휴직 지원", "만 8세 이하 자녀 양육자", "최대 1년 휴직과 복직 보장", "시작 30일 전 신청"),
    ]
    rows = [[i + 1, f"<b>{n}</b>", t, c, m] for i, (n, t, c, m) in enumerate(rng.sample(items, rng.randint(7, 9)))]
    body = (f"<h1 class=sm>{rdate(rng).year}년 임직원 복지제도 안내</h1><div class=sub>{COMPANY} 인사총무팀</div>"
            "<h2>1. 안내 목적</h2><p>임직원의 근무 만족도를 높이고 생활 안정을 지원하기 위한 복지제도를 아래와 같이 안내합니다. "
            "각 제도의 대상과 신청 방법을 확인해 기한 내 신청해 주시기 바랍니다.</p>"
            "<h2>2. 제도 목록</h2>"
            + tbl(["번호", "제도", "대상", "지원 내용", "신청 방법"], rows, ["c", "l", "l", "l", "l"],
                  ["40px", "100px", "130px", "", "170px"])
            + "<h2>3. 유의 사항</h2><ul class=b><li>중복 지원이 불가능한 제도는 신청 시 담당자가 안내합니다.</li>"
              "<li>증빙서류 제출 기한은 사유 발생일로부터 30일 이내입니다.</li>"
              f"<li>제도의 세부 기준은 회사 사정에 따라 변경될 수 있습니다.</li></ul>"
              f"<h2>4. 문의</h2><p>인사총무팀 {person(rng)} {rng.choice(POSITIONS)} (내선 {rng.randint(200, 299)})</p>")
    return page(body, **look(rng))


def personnel_order(rng, seq):
    kinds = ["승진", "전보", "직책 임명", "겸직", "파견", "복직"]
    n = rng.randint(1, 4)
    rows = []
    for _ in range(n):
        k = rng.choice(kinds)
        t1, t2 = rng.sample(TEAMS, 2)
        p1 = rng.randrange(len(POSITIONS) - 1)
        cur = f"{t1} {POSITIONS[p1]}"
        before, after = {
            "승진": (cur, f"{t1} {POSITIONS[p1 + 1]}"),
            "전보": (cur, f"{t2} {POSITIONS[p1]}"),
            "직책 임명": (cur, f"{t1} 팀장 보임"),
            "겸직": (cur, f"{cur} / {t2} 겸직"),
            "파견": (cur, f"{t2} 파견 (6개월)"),
            "복직": ("육아휴직 중", cur),
        }[k]
        rows.append([person(rng), f"HS{rng.randint(1000, 9999)}", k, before, after])
    d = rdate(rng)
    body = (f"<div class=small>문서번호: 인사-{d.year}-{rng.randint(1, 120):03d}</div><h1>인 사 발 령 통 지 서</h1>"
            f"<p style='margin-top:24px'><b>수 신</b> : 전 임직원 및 관련 부서장</p><p><b>발령일</b> : {kdk(d)}</p>"
            "<p>아래 임직원에 대해 다음과 같이 인사 발령하오니 업무에 차질이 없도록 인수인계 바랍니다.</p>"
            + tbl(["성명", "사번", "구분", "발령 전", "발령 후"], rows, ["c", "c", "c", "l", "l"])
            + f"<p style='margin-top:30px' class=center>위와 같이 발령합니다.</p><p class=center>{kdk(d)}</p>"
              f"<div class=foot>{COMPANY} 대표이사 {person(rng)} {seal(rng, '직인', 64)}</div>")
    return page(body, **look(rng))


def hygiene_cert(rng, seq):
    course = rng.choice(["식품위생 신규 교육", "식품위생 정기 교육", "물류센터 위생관리 교육", "식품 운반·보관 위생 교육"])
    d = rdate(rng)
    body = ("<div style='border:4px double #1f3a5f;padding:34px 36px;margin-top:20px'>"
            f"<div class=small>확인번호 : HYG-{d.year}-{rng.randint(10000, 99999)}</div><h1 style='margin:20px 0 28px'>위생교육 이수확인서</h1>"
            + kv([("성 명", person(rng)), ("생년월일", f"{rng.randint(70, 99)}****-*"), ("소 속", rng.choice(TEAMS)),
                  ("직 위", rng.choice(POSITIONS)), ("교육과정", course), ("교육시간", f"{rng.choice([3, 4, 6, 8])}시간"),
                  ("교육기간", kd(d)), ("교육기관", "새빛식품위생교육원")], cols=2, lw=88)
            + "<p style='margin:30px 0 8px;text-align:center;font-size:15px'>위 사람은 식품 취급 종사자로서 위의 교육 과정을 "
              "이수하였음을 확인합니다.</p>"
              f"<p class=center style='margin-top:26px'>{kdk(d)}</p>"
              f"<div class=foot style='margin-top:30px'>새빛식품위생교육원장 {square_seal(rng, '교육원<br>직인', 64)}</div></div>")
    return page(body, font="serif", **look(rng, ta="center"))


def health_check(rng, seq):
    d = rdate(rng)
    items = [("장티푸스", "혈액 배양", "음성"), ("폐결핵", "흉부 방사선", "이상 없음"), ("전염성 피부질환", "시진·문진", "이상 없음")]
    if rng.random() < 0.5:
        items.append(("B형 간염 항원", "혈액", "음성"))
    rows = [[i + 1, a, b, c, "적합"] for i, (a, b, c) in enumerate(items)]
    body = (f"<h1 class=sm>건강진단결과서 <span style='font-size:15px;font-weight:500'>(식품 등 종사자용)</span></h1>"
            + kv([("성 명", person(rng)), ("성 별", rng.choice(["남", "여"])), ("생년월일", f"{rng.randint(70, 99)}****-*"),
                  ("업 종", "식품 취급(물류·유통)"), ("영업소", COMPANY), ("검진 번호", f"H-{rng.randint(100000, 999999)}")], 2)
            + "<h2>검사 결과</h2>" + tbl(["번호", "검사 항목", "검사 방법", "결과", "판정"], rows, widths=["50px", "", "", "", "90px"])
            + kv([("종합 판정", "<b>적합</b> (식품위생 관련 업무 종사 가능)"), ("검진일", kdk(d)),
                  ("유효기간", f"{kdk(d.replace(year=d.year + 1))}까지")], 1)
            + f"<p class=right style='margin-top:26px'>{rng.choice(['새빛의원', '누리병원 건강증진센터', '푸른내과의원'])} "
              f"의사 {person(rng)} {seal(rng, '인', 52)}</p>")
    return page(body, **look(rng))


def shift_table(rng, seq):
    d0 = rdate(rng, m1=1, m2=9)
    days = [d0 + __import__("datetime").timedelta(days=i) for i in range(14)]
    wk = "월화수목금토일"
    names = people(rng, rng.randint(7, 10))
    pat = [["D", "D", "D", "OFF", "N", "N", "N"], ["E", "E", "OFF", "D", "D", "D", "OFF"], ["N", "N", "OFF", "OFF", "E", "E", "E"]]
    head = "".join(f"<th style='font-size:10.5px;padding:3px 0'>{x.day}<br>{wk[x.weekday()]}</th>" for x in days)
    rows = ""
    for n in names:
        p = rng.choice(pat)
        off = rng.randrange(7)
        cells = "".join(f"<td class=c style='font-size:10.5px;padding:5px 0;{'background:#f0f0f0' if p[(i + off) % 7] == 'OFF' else ''}'>"
                        f"{p[(i + off) % 7]}</td>" for i in range(14))
        rows += f"<tr><td class=c style='font-size:11.5px;padding:5px 2px'>{n}</td>{cells}</tr>"
    zone = rng.choice(["입출고 A조", "입출고 B조", "피킹 1조", "상하차 조"])
    body = (f"<h1 class=sm>{d0.month}월 {(d0.day - 1) // 7 + 1}주차 교대근무표</h1><div class=sub>{COMPANY} 물류센터 · {zone} (기간 {kd(days[0])} ~ {kd(days[-1])})</div>"
            f"<table class=t style='margin-top:16px'><tr><th style='width:64px'>성명</th>{head}</tr>{rows}</table>"
            "<p class=small>D: 주간(06~15시) · E: 오후(14~23시) · N: 야간(22~07시) · OFF: 휴무 (회색 칸)</p>"
            + sign(["작성", "센터장"]))
    return page(body, **look(rng), pad="36px 34px 30px")


def training_plan(rng, seq):
    courses = [("식품위생 법정교육", "전 직원", "위생교육원", 4), ("산업안전보건 교육", "물류센터 전원", "자체", 6),
               ("지게차 안전 교육", "상하차 담당", "외부", 8), ("신입사원 입문 과정", "신입사원", "자체", 16),
               ("리더십 과정", "팀장급", "외부", 12), ("영업 협상 스킬", "영업팀", "외부", 8),
               ("재고관리 실무", "물류운영팀", "자체", 6), ("개인정보보호 교육", "전 직원", "온라인", 2),
               ("엑셀 활용 실무", "사무직", "온라인", 8), ("고객응대 서비스", "영업·CS", "외부", 6)]
    pick = rng.sample(courses, rng.randint(7, 9))
    rows, tot = [], 0
    for i, (n, t, org, h) in enumerate(sorted(pick, key=lambda x: rng.random())):
        cost = rng.randint(2, 40) * 50000
        tot += cost
        rows.append([i + 1, n, t, f"{rng.randint(1, 12)}월", f"{h}시간", org, won(cost)])
    y = rdate(rng).year
    body = (f"<h1 class=sm>{y}년 교육훈련 계획표</h1><div class=sub>작성부서 인사총무팀</div>"
            + tbl(["번호", "교육과정", "대상", "시기", "시간", "교육기관", "예산(원)"], rows,
                  ["c", "l", "l", "c", "c", "c", "r"], ["46px", "", "110px", "50px", "58px", "74px", "92px"],
                  foot=f"<td colspan=6>합 계</td><td class=r>{won(tot)}</td>")
            + "<p class=small>※ 교육 일정은 업무 사정에 따라 조정될 수 있으며 변경 시 사전 공지합니다.</p>"
            + sign(["작성", "팀장", "대표이사"]))
    return page(body, **look(rng))


def award_recommend(rng, seq):
    kinds = ["우수사원상", "안전관리 모범상", "영업 우수상", "고객만족상", "장기근속상", "개선 제안상"]
    k = rng.choice(kinds)
    t = rng.choice(TEAMS)
    merits = {
        "우수사원상": ["담당 업무에서 연간 목표를 {p}% 초과 달성함", "신규 직원 교육에 적극 참여해 팀 적응을 도움", "고객 불만 사례를 신속히 처리함"],
        "안전관리 모범상": ["무사고 {p}일 연속 기록에 기여함", "작업 전 안전 점검표를 개선해 사고 위험을 줄임", "야간 근무자 안전 수칙 교육을 주도함"],
        "영업 우수상": ["신규 거래처 {n}곳을 개설함", "분기 매출 목표를 {p}% 초과 달성함", "거래처 미수금을 기한 내 전액 회수함"],
        "고객만족상": ["거래처 만족도 조사에서 최고 점수를 받음", "클레임 {n}건을 당일 처리해 재발을 막음", "배송 지연 문의에 선제 대응함"],
        "장기근속상": ["{n}년간 성실히 근무하며 팀의 안정에 기여함", "부서 간 협업을 이끌어 업무 효율을 높임"],
        "개선 제안상": ["피킹 동선을 개선해 작업 시간을 {p}% 단축함", "포장 규격 표준화로 파손률을 낮춤", "재고 조회 절차를 간소화함"],
    }[k]
    ms = [m.format(p=rng.choice([8, 12, 15, 20]), n=rng.choice([3, 4, 5, 7, 10])) for m in rng.sample(merits, min(len(merits), 3))]
    body = (f"<h1>포 상 추 천 서</h1><div class=sub>{k} 추천</div>"
            + kv([("추천 대상자", person(rng)), ("사번", f"HS{rng.randint(1000, 9999)}"), ("소 속", t), ("직 위", rng.choice(POSITIONS)),
                  ("입사일", kd(rdate(rng, 2015, 1, 12))), ("포상 종류", k)], 2)
            + "<h2>공적 사항</h2>" + tbl(["번호", "공적 내용"], [[i + 1, m] for i, m in enumerate(ms)], ["c", "l"], ["50px", ""])
            + "<h2>추천 사유</h2><div class=box style='min-height:110px'>위 직원은 평소 맡은 업무에 책임감을 가지고 임하며 "
              "동료와 협력하여 부서 성과에 크게 기여하였기에 위와 같이 추천합니다.</div>"
            + f"<p class=center style='margin-top:20px'>{kdk(rdate(rng))}</p>"
            + sign(["추천인", "부서장", "인사위원회", "대표이사"]))
    return page(body, **look(rng))


def cert_status(rng, seq):
    certs = [("지게차운전기능사", "한국산업인력공단", 150000), ("물류관리사", "한국교통연구원", 200000),
             ("컴퓨터활용능력 1급", "대한상공회의소", 100000), ("식품안전관리 실무자", "식품안전교육원", 80000),
             ("냉동공조기능사", "한국산업인력공단", 120000), ("운전면허 1종 대형", "도로교통공단", 100000),
             ("산업안전기사", "한국산업인력공단", 180000), ("유통관리사 2급", "대한상공회의소", 100000)]
    rows, tot = [], 0
    for i in range(rng.randint(9, 13)):
        c, org, amt = rng.choice(certs)
        tot += amt
        rows.append([i + 1, person(rng), f"HS{rng.randint(1000, 9999)}", rng.choice(TEAMS), c, kd(rdate(rng, 2022, 1, 12)), org, won(amt)])
    y = rdate(rng).year
    body = (f"<h1 class=sm>{y}년 자격증 취득 현황표</h1><div class=sub>기준일 {y}.12.31 · 인사총무팀</div>"
            + tbl(["번호", "성명", "사번", "소속", "자격증명", "취득일", "발급기관", "월 수당(원)"], rows,
                  ["c", "c", "c", "c", "l", "c", "l", "r"],
                  ["34px", "62px", "66px", "76px", "", "78px", "104px", "82px"],
                  foot=f"<td colspan=7>합 계 ({len(rows)}명)</td><td class=r>{won(tot)}</td>", cls="s11")
            + "<p class=small>※ 월 수당은 자격 수당 지급 규정에 따른 금액이며 급여에 합산 지급합니다.</p>" + sign(["작성", "팀장"]))
    return page(body, extra=".s11 td,.s11 th{font-size:11.5px;padding:5px 5px}", **look(rng), pad="40px 36px")


def interview_form(rng, seq):
    crit = ["직무 지식", "의사소통 능력", "문제 해결력", "책임감·성실성", "조직 적합성", "성장 가능성"]
    scores = [rng.choice([3, 3, 4, 4, 5, 2]) for _ in crit]
    rows = []
    for c, s in zip(crit, scores):
        marks = "".join(f"<td class=c>{'●' if s == v else ''}</td>" for v in (5, 4, 3, 2, 1))
        rows.append(f"<tr><td class=l>{c}</td>{marks}<td class=c><b>{s}</b></td></tr>")
    tot = sum(scores)
    verdict = "합격" if tot >= 22 else ("보류" if tot >= 18 else "불합격")
    cb = "".join(f"<span class='cb{' on' if v == verdict else ''}'></span>{v}&nbsp;&nbsp;" for v in ("합격", "보류", "불합격"))
    body = ("<h1>면 접 평 가 표</h1>"
            + kv([("지원번호", f"R-{rng.randint(1000, 9999)}"), ("지원자", person(rng)), ("지원 직무", rng.choice(["영업관리", "물류운영", "재무회계", "마케팅", "품질관리"])),
                  ("면접일", kd(rdate(rng))), ("면접 유형", rng.choice(["1차 실무면접", "2차 임원면접"])), ("면접위원", f"{person(rng)} / {person(rng)}")], 2)
            + "<table class=t><tr><th rowspan=2>평가 항목</th><th colspan=5>평 점</th><th rowspan=2 style='width:60px'>점수</th></tr>"
              "<tr><th>매우우수(5)</th><th>우수(4)</th><th>보통(3)</th><th>미흡(2)</th><th>부족(1)</th></tr>"
            + "".join(rows) + f"<tr class=ft><td colspan=6>총 점 (30점 만점)</td><td class=c>{tot}</td></tr></table>"
            + "<h2>종합 의견</h2><div class=box style='min-height:80px'>직무 이해도가 높고 질문 의도를 정확히 파악해 답변함. "
              "팀 업무 경험을 구체적인 사례로 설명함.</div>"
            + f"<p style='margin-top:14px'><b>면접 결과</b> : {cb}</p>" + sign(["면접위원 1", "면접위원 2", "인사담당"]))
    return page(body, **look(rng))


def job_description(rng, seq):
    jobs = [("영업관리", "영업1팀", "거래처 매출 관리와 신규 거래처 개설을 담당한다.",
             [("거래처 관리·방문", "거래처별 매출·미수금 확인과 정기 방문", 40), ("견적·계약 지원", "견적서 작성과 계약 조건 협의", 30), ("매출 분석", "월간 매출 보고서 작성", 30)]),
            ("물류운영", "물류운영팀", "입출고와 재고를 정확하게 운영해 적기 배송을 지원한다.",
             [("입출고 관리", "입고 검수와 출고 지시 처리", 45), ("재고 관리", "정기 재고 실사와 차이 분석", 35), ("배송 조율", "배차 계획과 운송업체 소통", 20)]),
            ("재무회계", "재무회계팀", "회계 기록과 결산, 세무 신고를 지원한다.",
             [("전표 처리", "매입·매출 전표 입력과 검증", 40), ("채권 관리", "미수금 확인과 독촉", 30), ("결산 지원", "월 마감과 재무제표 작성 보조", 30)]),
            ("품질관리", "품질관리팀", "입고 식품의 품질과 위생 기준 준수를 점검한다.",
             [("입고 검수", "유통기한·온도 확인", 40), ("위생 점검", "보관 구역 위생 점검", 35), ("클레임 대응", "품질 이슈 원인 분석", 25)])]
    n, t, goal, duties = rng.choice(jobs)
    caps = rng.sample(["엑셀 활용", "거래처 협상", "재고 시스템 사용", "식품위생 이해", "문서 작성", "데이터 분석", "원가 이해"], 4)
    body = ("<h1>직 무 기 술 서</h1>"
            + kv([("직무명", n), ("소 속", t), ("직 급", rng.choice(["사원~대리", "대리~과장", "과장급"])),
                  ("보고 대상", f"{t.replace('팀', '')}팀장"), ("고용 형태", "정규직"), ("작성일", kd(rdate(rng)))], 2)
            + f"<h2>직무 목적</h2><p>{goal}</p><h2>주요 업무</h2>"
            + tbl(["업무", "세부 내용", "비중(%)"], [[a, b, c] for a, b, c in duties], ["l", "l", "c"], ["130px", "", "70px"])
            + "<h2>자격 요건</h2><ul class=b><li>관련 분야 학력 또는 동등 경력 보유</li>"
              f"<li>유관 업무 경력 {rng.choice(['1년 이상', '2년 이상', '3년 이상'])}</li><li>운전면허 소지자 우대</li></ul>"
              f"<h2>필요 역량</h2><p>{' · '.join(caps)}</p><h2>근무 조건</h2><p>근무지 {HQ_ADDR} · 주 5일, 09:00~18:00</p>")
    return page(body, **look(rng))


SPECS = [("HR-06", "복지제도 안내서", welfare), ("HR-07", "인사발령통지서", personnel_order),
         ("HR-08", "위생교육 이수확인서", hygiene_cert), ("HR-09", "건강진단결과서", health_check),
         ("HR-10", "교대근무표", shift_table), ("HR-11", "교육훈련 계획표", training_plan),
         ("HR-12", "포상 추천서", award_recommend), ("HR-13", "자격증 취득 현황표", cert_status),
         ("HR-14", "면접평가표", interview_form), ("HR-15", "직무기술서", job_description)]
