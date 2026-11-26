"""재무/회계 확장 12종 (FIN-11~22). 각 함수는 (레이아웃 0/1, 난수) → HTML. 수치는 합성용 근사값이다."""
import random

from src.eval.expansion_common import (BANKS, CLIENTS, COMPANY, NAMES, SUPPLIERS, H, KV, P, T, UL, bar, date, doc,
                                       grid, korean_amount, seal, won, ymd)


def _no(rng, prefix):
    return f"{prefix}-{rng.randint(2025, 2026)}-{rng.randint(1, 999):04d}"


def fin11(layout, rng):  # 외상매출금 연령분석표
    n = rng.randint(8, 11) if layout == 0 else rng.randint(7, 9)
    rows, tot = [], [0] * 4
    for c in rng.sample(CLIENTS, n):
        b = [rng.randint(2, 90) * 100_000, rng.randint(0, 40) * 100_000, rng.choice([0, 0, 1, 2, 5]) * 100_000, rng.choice([0, 0, 0, 1, 3]) * 100_000]
        tot = [t + v for t, v in zip(tot, b)]
        rows.append((c, b))
    y, m = rng.randint(2025, 2026), rng.randint(1, 12)
    if layout == 0:
        body = [H("거래처별 연령 분석 (단위: 원)"),
                T(["거래처", "채권 잔액", "30일 이내", "31~60일", "61~90일", "91일 이상", "비고"],
                  [(c, won(sum(b)), won(b[0]), won(b[1]), won(b[2]), won(b[3]), "회수 독촉" if b[3] else "") for c, b in rows],
                  num=(1, 2, 3, 4, 5), foot=("합계", won(sum(tot)), *map(won, tot), ""))]
        meta = [("기준일", ymd(y, m, 28)), ("작성부서", "재무회계팀")]
    else:
        body = [H("기간별 구성비"), grid([f"<div class=card><b>{l}</b><div class=big>{sum(tot) and tot[i] * 100 // sum(tot)}%</div>{bar(sum(tot) and tot[i] * 100 / sum(tot))}</div>"
                                          for i, l in enumerate(["30일 이내", "31~60일", "61~90일", "91일 초과"])], 4),
                H("거래처별 상세"),
                T(["코드", "거래처", "담당", "여신한도", "미수 잔액", "0~30", "31~60", "61~90", "90초과", "연체율"],
                  [(f"C{rng.randint(100, 999)}", c, rng.choice(NAMES[:10]), won(sum(b) + rng.randint(1, 30) * 1_000_000), won(sum(b)), won(b[0]), won(b[1]),
                    won(b[2]), won(b[3]), f"{(b[2] + b[3]) * 100 / max(sum(b), 1):.1f}%") for c, b in rows],
                  num=(3, 4, 5, 6, 7, 8, 9))]
        meta = [("조회 기준", ymd(y, m, 28)), ("채권 구분", "외상매출금"), ("출력", "재무회계팀")]
    return doc(layout, "외상매출금 연령분석표", body, meta, _no(rng, "AR"))


def fin12(layout, rng):  # 환율 변동 손익표
    cur = {"USD": rng.randint(1280, 1420), "EUR": rng.randint(1400, 1550), "JPY": rng.randint(880, 960) / 10, "CNY": rng.randint(185, 205) / 10}
    rows = []
    for _ in range(rng.randint(6, 8)):
        c = rng.choice(list(cur))
        amt = rng.randint(5, 80) * 1000
        r0 = round(cur[c] * rng.uniform(0.95, 1.04), 1)
        r1 = round(cur[c] * rng.uniform(0.97, 1.05), 1)
        sup = rng.choice(SUPPLIERS)[0]
        rows.append((date(rng, 2026, 2026), sup, c, amt, r0, r1, round(amt * r0), round(amt * r1)))
    if layout == 0:
        gains = [r[6] - r[7] for r in rows]  # 외화 매입채무: 환율이 오르면 손실
        body = [H("외화 거래별 환산 손익 (단위: 원)"),
                T(["거래일", "거래처", "통화", "외화금액", "거래일 환율", "기말 환율", "장부금액", "평가금액", "손익"],
                  [(*r[:3], won(r[3]), r[4], r[5], won(r[6]), won(r[7]), won(g)) for r, g in zip(rows, gains)], num=(3, 4, 5, 6, 7, 8),
                  foot=("합계", "", "", "", "", "", won(sum(r[6] for r in rows)), won(sum(r[7] for r in rows)), won(sum(gains)))),
                P("외화 매입채무 기준. 기말 환율이 거래일보다 높으면 손실, 낮으면 이익으로 본다.")]
        meta = [("회계기간", "2026-01-01 ~ 2026-12-31"), ("구분", "외화환산손익")]
    else:
        by = {}
        for r in rows:
            d = by.setdefault(r[2], [0, 0, 0])
            d[0] += r[3]; d[1] += r[6]; d[2] += r[7]
        body = [H("통화별 요약 (단위: 원)"),
                T(["통화", "외화 합계", "평균 거래환율", "기말 환율", "장부금액", "기말평가액", "환차익", "환차손"],
                  [(c, won(v[0]), round(v[1] / v[0], 1), cur[c], won(v[1]), won(v[2]), won(max(v[1] - v[2], 0)), won(max(v[2] - v[1], 0))) for c, v in by.items()],
                  num=(1, 2, 3, 4, 5, 6, 7)),
                H("결제 건별 외환차손익"),
                T(["결제일", "거래처", "통화", "외화금액", "결제 환율", "차손익"],
                  [(r[0], r[1], r[2], won(r[3]), r[5], won(r[6] - r[7])) for r in rows[:6]], num=(3, 4, 5)),
                P("순손익 = 환차익 - 환차손. 영업외손익(외환차손익·외화환산손익)으로 반영한다.")]
        meta = [("작성 월", ymd(2026, rng.randint(1, 12), 1)[:7]), ("작성", "재무회계팀")]
    return doc(layout, "환율 변동 손익표", body, meta, _no(rng, "FX"))


def fin13(layout, rng):  # 판매장려금(리베이트) 정산서
    c = rng.choice(CLIENTS)
    y = rng.randint(2025, 2026)
    if layout == 0:
        months = [rng.randint(20, 90) * 1_000_000 for _ in range(3)]
        total = sum(months)
        tiers = [(0, 100_000_000, 1.0), (100_000_000, 200_000_000, 1.5), (200_000_000, 10 ** 10, 2.0)]
        rebate, lines = 0, []
        for lo, hi, rate in tiers:
            part = max(min(total, hi) - lo, 0)
            amt = int(part * rate / 100); rebate += amt
            lines.append((f"{won(lo)} ~ {'' if hi == 10 ** 10 else won(hi)}", won(part), f"{rate}%", won(amt)))
        body = [H("분기 매출 내역"), T(["월", "공급가액", "비고"], [(f"{y}년 {m}월", won(v), "") for m, v in zip(range(1, 4), months)], num=(1,), foot=("합계", won(total), "")),
                H("누진 구간별 장려금"), T(["매출 구간", "구간 매출", "적용 요율", "장려금"], lines, num=(1, 2, 3), foot=("합계", "", "", won(rebate))),
                H("지급 내역"), KV([("공급가액", won(rebate)), ("부가세", won(rebate // 10)), ("지급액", won(rebate + rebate // 10)), ("지급예정일", date(rng, y, y)),
                                  ("입금계좌", f"{rng.choice(BANKS)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(100000, 999999)}"), ("예금주", c)])]
    else:
        lines, rebate = [], 0
        for g in ["과자류", "음료류", "선물세트", "베이커리"]:
            goal = rng.randint(20, 80) * 1_000_000
            act = int(goal * rng.uniform(0.7, 1.3))
            rate = 3.0 if act >= goal else 1.0
            amt = int(act * rate / 100); rebate += amt
            lines.append((g, won(goal), won(act), f"{act * 100 // goal}%", f"{rate}%", won(amt)))
        body = [H("품목군별 목표 달성 장려금"), T(["품목군", "목표 매출", "실적 매출", "달성률", "적용 요율", "장려금"], lines, num=(1, 2, 3, 4, 5), foot=("합계", "", "", "", "", won(rebate))),
                P("목표 100% 이상 달성 시 3.0%, 미달 시 1.0%를 적용한다. 반품분은 실적에서 제외한다."),
                KV([("정산 방식", rng.choice(["다음 달 외상대금 상계", "계좌 입금", "세금계산서 발행 후 지급"])), ("지급 예정일", date(rng, y, y)), ("정산 확정", "영업관리팀"), ("확인", c + " 담당자")])]
    meta = [("거래처", c), ("정산 기간", f"{y}년 {rng.choice(['1~3월', '4~6월', '7~9월', '10~12월'])}")]
    return doc(layout, "판매장려금 정산서", body, meta, _no(rng, "RB"))


def fin14(layout, rng):  # 입금확인증
    amt = rng.randint(5, 400) * 100_000
    if layout == 0:
        bank = rng.choice(BANKS)
        pairs = [("입금자", rng.choice(CLIENTS)), ("입금일시", date(rng, 2025, 2026) + f" {rng.randint(9, 17):02d}:{rng.randint(0, 59):02d}"),
                 ("입금계좌", f"{bank} {rng.randint(100, 999)}-{rng.randint(100, 999)}-{rng.randint(100000, 999999)}"), ("예금주", COMPANY),
                 ("입금금액", f"일금 {korean_amount(amt)} (₩{won(amt)})"), ("거래번호", f"{rng.randint(10 ** 9, 10 ** 10 - 1)}"), ("적요", rng.choice(["물품대금", "외상대금 입금", "납품대금"]))]
        body = [P("위 금액이 상기 계좌에 입금되었음을 확인합니다.", "note"), KV(pairs, 1),
                f"<p class=c style='margin-top:30px'>{date(rng, 2025, 2026)}</p><p class=c style='font-size:16px'><b>{bank}</b> {rng.choice(['강남', '여의도', '서초', '마포'])}지점장 {seal(bank[:2])}</p>"]
        return doc(0, "입금확인증", body, [("발급번호", _no(rng, "DP"))], "", issuer=bank, sign=())
    rows = [(date(rng, 2026, 2026), rng.choice(["물품대금", "외상대금", "선수금"]), won(rng.randint(2, 60) * 100_000), f"{rng.choice(BANKS)}") for _ in range(rng.randint(4, 6))]
    tot = sum(int(r[2].replace(",", "")) for r in rows)
    body = [P(f"귀사({rng.choice(CLIENTS)})가 당사에 입금하신 내역이 아래와 같음을 확인합니다."),
            T(["입금일", "내용", "입금액", "입금 은행"], rows, num=(2,), foot=("합계", "", won(tot), "")),
            KV([("입금 합계(한글)", f"일금 {korean_amount(tot)}"), ("미수 잔액", won(rng.randint(0, 50) * 100_000))], 1),
            f"<p class=r style='margin-top:26px'>{date(rng, 2026, 2026)} &nbsp; {COMPANY} 대표이사 {seal('HS리테일')}</p>"]
    return doc(1, "입금 확인증", body, [("수신", rng.choice(CLIENTS) + " 귀중")], _no(rng, "DC"), sign=("작성", "확인"))


def fin15(layout, rng):  # 대출금 상환계획표
    principal = rng.randint(3, 30) * 100_000_000
    rate = rng.randint(32, 62) / 10
    years = rng.choice([3, 5, 7]) if layout == 1 else rng.choice([1, 2, 3])
    n = years * 12
    r = rate / 1200
    bank = rng.choice(BANKS)
    meta = [("대출처", bank), ("대출 종류", rng.choice(["시설자금대출", "운전자금대출", "물류센터 담보대출"])), ("대출원금", won(principal)), ("금리", f"연 {rate}%"),
            ("기간", f"{years}년"), ("상환방식", "원리금균등" if layout == 0 else "원금균등")]
    rows, bal = [], principal
    pay = principal * r / (1 - (1 + r) ** -n)
    for k in range(1, n + 1):
        i = int(bal * r)
        p = bal if k == n else (int(pay - i) if layout == 0 else principal // n)  # 마지막 회차에 잔액을 모두 상환
        rows.append((k, ymd(2026 + k // 12, k % 12 + 1, 25), p, i, p + i, bal - p)); bal -= p
    if layout == 0:
        sel = rows[:12]
        body = [H("회차별 상환 계획 (최초 12회)"), T(["회차", "납입일", "원금", "이자", "납입액", "잔액"], [(a, b, won(c), won(d), won(e), won(f)) for a, b, c, d, e, f in sel], num=(2, 3, 4, 5)),
                P(f"전체 {n}회 중 앞 12회를 표시한다. 총 이자 약 {won(sum(x[3] for x in rows))}원.")]
        return doc(0, "대출금 상환계획표", body, meta, _no(rng, "LN"))
    ys = []
    for y in range(years):
        ch = rows[y * 12:(y + 1) * 12]
        ys.append((f"{y + 1}년차", won(sum(c[2] for c in ch)), won(sum(c[3] for c in ch)), won(sum(c[4] for c in ch)), won(ch[-1][5]), bar(ch[-1][5] * 100 / principal)))
    body = [H("연차별 상환 요약"), T(["연차", "원금 상환", "이자", "납입 합계", "연말 잔액", "잔액 비중"], ys, num=(1, 2, 3, 4)),
            H("초기 6개월 상세"), T(["회차", "납입일", "원금", "이자", "납입액"], [(a, b, won(c), won(d), won(e)) for a, b, c, d, e, _ in rows[:6]], num=(2, 3, 4))]
    return doc(1, "대출금 상환 계획표", body, meta, _no(rng, "LN"))


def fin16(layout, rng):  # 이행보증보험증권
    ins = "한성보증보험(주)"
    amt = rng.randint(2, 50) * 10_000_000
    y = rng.randint(2025, 2026)
    to = rng.choice(["대한유통(주)", "한국마트(주)", "전국편의점협동조합", "나라푸드서비스(주)"])
    pairs = [("증권번호", f"제 {rng.randint(100, 999)}-{rng.randint(100000, 999999)} 호"), ("보험계약자", COMPANY), ("피보험자", to),
             ("보험가입금액", f"일금 {korean_amount(amt)} (₩{won(amt)})"), ("보험기간", f"{ymd(y, 3, 1)} ~ {ymd(y + 1, 2, 28)}"),
             ("보험료", f"{won(int(amt * rng.uniform(0.002, 0.005)))}원"), ("보증 대상 계약", f"{rng.choice(['과자류', '음료류', '선물세트'])} 연간 공급계약 ({ymd(y, 2, 20)})")]
    clauses = ["보험계약자가 계약상의 채무를 이행하지 아니함으로써 피보험자가 입은 손해를 보험가입금액 한도에서 보상합니다.",
               "보험기간 중 보험료가 납입되지 아니한 경우 이 증권에 의한 보상은 효력이 없습니다.",
               "피보험자는 채무불이행 사실을 안 날부터 30일 이내에 회사에 통지하여야 합니다.",
               "보험금 청구 시 계약서 사본과 손해 증빙서류를 제출하여야 합니다."]
    if layout == 0:
        body = [KV(pairs, 1), H("보험 약관 요약"), UL(clauses), f"<p class=c style='margin-top:20px'>위와 같이 보험계약이 체결되었음을 증명합니다.</p><p class=c>{date(rng, y, y)} &nbsp; <b>{ins}</b> 대표이사 {seal('한성보증')}</p>"]
        return doc(0, "이행보증보험증권", body, [], "", issuer=ins, sign=())
    body = [grid([f"<div class=card><b>보험계약자</b><br>{COMPANY}</div>", f"<div class=card><b>피보험자</b><br>{to}</div>"], 2),
            T(["항목", "내용"], [(k, v) for k, v in pairs[:1] + pairs[3:]], left=(1,)), H("보상 및 유의사항"), UL(clauses[:3]),
            f"<p class=r style='margin-top:18px'>발행일 {date(rng, y, y)} &nbsp; {ins} {seal('한성보증')}</p>"]
    return doc(1, "이행보증보험증권", body, [("보험종목", "계약이행보증")], "", issuer=ins, sign=())


def fin17(layout, rng):  # 주주명부
    total = rng.choice([100_000, 200_000, 500_000])
    n = rng.randint(6, 9)
    cuts = sorted(rng.sample(range(1, 100), n - 1))
    shares = [round(total * (b - a) / 100) for a, b in zip([0] + cuts, cuts + [100])]
    names = rng.sample(NAMES, n - 2) + ["(주)한결투자", "미래창업투자(주)"]
    rows = []
    for k, (nm, sh) in enumerate(sorted(zip(names, shares), key=lambda x: -x[1]), 1):
        rows.append((k, nm, f"{rng.randint(60, 99):02d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}-*******" if "(주)" not in nm else f"110111-*******",
                     rng.choice(["서울", "경기", "인천", "부산"]) + f" {rng.choice(['강남구', '분당구', '해운대구', '남동구'])}", sh))
    tot = sum(r[4] for r in rows)
    if layout == 0:
        body = [T(["번호", "주주명", "등록번호", "주소", "소유 주식수", "지분율"],
                  [(a, b, c, d, won(e), f"{e * 100 / tot:.2f}%") for a, b, c, d, e in rows], num=(4, 5), left=(3,), foot=("합계", "", "", "", won(tot), "100.00%")),
                P(f"발행주식 총수 {won(tot)}주 (1주 액면 5,000원) / 자본금 {won(tot * 5000)}원"),
                f"<p class=r style='margin-top:20px'>위 주주명부는 사실과 상위 없음을 확인합니다. &nbsp; 대표이사 {seal('HS리테일')}</p>"]
        return doc(0, "주 주 명 부", body, [("기준일", ymd(rng.randint(2025, 2026), 12, 31)), ("회사명", COMPANY)], _no(rng, "SH"), sign=("작성", "대표"))
    kinds = [rng.choice(["보통주", "보통주", "우선주"]) for _ in rows]
    body = [T(["No.", "성명·상호", "구분", "주식 종류", "주식수", "지분 비중", "취득일"],
              [(a, b, "법인" if "(주)" in b else "개인", k, won(e), bar(e * 100 / tot), date(rng, 2018, 2025)) for (a, b, _, _, e), k in zip(rows, kinds)], num=(4,), left=(1,)),
            T(["주식 종류", "주식수", "비율"], [(k, won(sum(r[4] for r, kk in zip(rows, kinds) if kk == k)), f"{sum(r[4] for r, kk in zip(rows, kinds) if kk == k) * 100 / tot:.1f}%") for k in sorted(set(kinds))], num=(1, 2), style="margin-top:12px;width:50%")]
    return doc(1, "주주명부", body, [("작성 기준일", ymd(rng.randint(2025, 2026), 12, 31)), ("총 주식수", won(tot))], _no(rng, "SH"), sign=("작성", "확인", "대표이사"))


def fin18(layout, rng):  # 고정자산 감가상각 명세서
    pool = [("본사 사옥 건물", "건물", 40, 0), ("용인 물류센터", "건물", 40, 0), ("냉동창고 설비", "기계장치", 8, 1), ("지게차 3톤", "기계장치", 5, 1), ("자동분류기", "기계장치", 8, 1),
            ("배송 냉장탑차", "차량운반구", 5, 1), ("업무용 승합차", "차량운반구", 5, 1), ("서버 및 네트워크", "비품", 5, 1), ("사무용 가구", "비품", 5, 1), ("매장 진열대", "비품", 5, 1)]
    rows = []
    for nm, kind, life, _ in rng.sample(pool, rng.randint(6, 8)):
        cost = rng.randint(3, 400) * 10_000_000 if kind == "건물" else rng.randint(2, 60) * 3_000_000
        y0 = rng.randint(2016, 2024)
        yrs = 2026 - y0
        annual = cost // life
        prev = min(annual * (yrs - 1), cost); cur = min(annual, cost - prev)
        rows.append((nm, kind, y0, cost, life, prev, cur, prev + cur, cost - prev - cur))
    if layout == 0:
        body = [H("자산별 감가상각 (정액법, 단위: 원)"),
                T(["자산명", "취득", "취득가액", "연수", "전기말 누계", "당기 상각", "기말 누계", "장부가액"],
                  [(r[0], r[2], won(r[3]), f"{r[4]}년", won(r[5]), won(r[6]), won(r[7]), won(r[8])) for r in rows], num=(2, 4, 5, 6, 7), left=(0,), style="font-size:12.5px",
                  foot=("합계", "", won(sum(r[3] for r in rows)), "", won(sum(r[5] for r in rows)), won(sum(r[6] for r in rows)), won(sum(r[7] for r in rows)), won(sum(r[8] for r in rows))))]
        meta = [("회계연도", "2026"), ("상각방법", "정액법")]
    else:
        body = []
        for kind in dict.fromkeys(r[1] for r in rows):
            g = [r for r in rows if r[1] == kind]
            body += [H(f"{kind}"), T(["자산명", "취득가액", "상각률", "당기 상각비", "장부가액"], [(r[0], won(r[3]), f"{100 / r[4]:.1f}%", won(r[6]), won(r[8])) for r in g], num=(1, 2, 3, 4),
                                    foot=("소계", won(sum(r[3] for r in g)), "", won(sum(r[6] for r in g)), won(sum(r[8] for r in g))))]
        body.append(P(f"당기 감가상각비 합계 {won(sum(r[6] for r in rows))}원"))
        meta = [("대상 기간", "2026-01-01 ~ 12-31"), ("작성", "재무회계팀")]
    return doc(layout, "고정자산 감가상각 명세서", body, meta, _no(rng, "DP"))


def fin19(layout, rng):  # 현금출납부
    items = [("거래처 식대", 0), ("소액 비품 구입", 0), ("택배비", 0), ("차량 주유", 0), ("회식비", 0), ("매장 현금 매출 입금", 1), ("가지급금 반납", 1), ("잡수입", 1), ("행사 다과 구입", 0), ("전기료 납부", 0)]
    bal = rng.randint(2, 20) * 100_000
    rows = [("", "전일 이월", "", "", won(bal))]
    ti = to = 0
    for day in sorted(rng.randint(1, 28) for _ in range(rng.randint(11, 15))):
        nm, inc = rng.choice(items)
        v = rng.randint(1, 60) * 10_000
        if not inc and v > bal: v, inc, nm = v, 1, "매장 현금 매출 입금"
        bal += v if inc else -v; ti += v if inc else 0; to += 0 if inc else v
        rows.append((f"{day:02d}일", nm, won(v) if inc else "", "" if inc else won(v), won(bal)))
    y, m = rng.randint(2025, 2026), rng.randint(1, 12)
    if layout == 0:
        body = [T(["일자", "적요", "입금", "출금", "잔액"], rows, num=(2, 3, 4), left=(1,), foot=("", "합계", won(ti), won(to), won(bal)))]
        return doc(0, "현금출납부", body, [("기간", f"{y}년 {m}월"), ("계정", "현금")], _no(rng, "CB"), sign=("담당", "경리", "팀장"))
    acct = ["복리후생비", "소모품비", "운반비", "차량유지비", "접대비", "현금매출", "잡이익"]
    rows2 = [(r[0], r[1], rng.choice(acct) if r[1] != "전일 이월" else "", f"V-{rng.randint(1000, 9999)}" if r[1] != "전일 이월" else "", r[2], r[3], r[4]) for r in rows]
    body = [T(["날짜", "내용", "계정과목", "증빙번호", "수입", "지출", "잔고"], rows2, num=(4, 5, 6), left=(1,), foot=("", "월 합계", "", "", won(ti), won(to), won(bal))),
            KV([("현금 시재 확인", won(bal)), ("실사 차액", "0")], 2)]
    return doc(1, "현금 출납부", body, [("대상 월", f"{y}-{m:02d}"), ("관리", "재무회계팀")], _no(rng, "CB"))


def fin20(layout, rng):  # 어음관리대장
    def bill(kind):
        d0 = date(rng, 2026, 2026)
        mo = int(d0[5:7]) + rng.randint(1, 4)
        due = ymd(2026 + (mo - 1) // 12, (mo - 1) % 12 + 1, rng.randint(1, 28))
        return (f"{rng.randint(10 ** 7, 10 ** 8 - 1)}", kind, rng.choice(CLIENTS) if kind == "받을어음" else rng.choice(SUPPLIERS)[0], d0, due, rng.randint(3, 90) * 1_000_000, rng.choice(BANKS),
                rng.choice(["보관", "보관", "추심 의뢰", "결제 완료", "할인"] if kind == "받을어음" else ["미결제", "미결제", "결제 완료"]))
    if layout == 0:
        rows = [bill(rng.choice(["받을어음", "지급어음"])) for _ in range(rng.randint(8, 10))]
        body = [T(["어음번호", "구분", "거래처", "발행일", "만기일", "금액", "지급은행", "상태"], [(*r[:5], won(r[5]), r[6], r[7]) for r in sorted(rows, key=lambda r: r[4])], num=(5,))]
        return doc(0, "어음관리대장", body, [("관리 기준", "만기일 순"), ("작성부서", "재무회계팀")], _no(rng, "NT"), sign=("담당", "팀장"))
    rec = [bill("받을어음") for _ in range(5)]; pay = [bill("지급어음") for _ in range(5)]
    body = [H("받을어음 (수취)"), T(["번호", "발행인", "만기일", "금액", "은행", "상태"], [(r[0], r[2], r[4], won(r[5]), r[6], r[7]) for r in rec], num=(3,), foot=("소계", "", "", won(sum(r[5] for r in rec)), "", "")),
            H("지급어음 (발행)"), T(["번호", "수취인", "만기일", "금액", "은행", "상태"], [(r[0], r[2], r[4], won(r[5]), r[6], r[7]) for r in pay], num=(3,), foot=("소계", "", "", won(sum(r[5] for r in pay)), "", ""))]
    return doc(1, "어음 관리 대장", body, [("기준일", date(rng, 2026, 2026))], _no(rng, "NT"))


def fin21(layout, rng):  # 퇴직연금 가입 내역서
    co = rng.choice(["한성증권(주)", "동양생명보험(주)", "새한은행"])
    kind = rng.choice(["확정기여형(DC)", "확정급여형(DB)", "기업형 IRP"])
    prods = [("정기예금(원리금보장)", rng.uniform(1.2, 3.8)), ("국내채권형 펀드", rng.uniform(-1, 4.5)), ("TDF 2040", rng.uniform(0, 9)), ("국내주식형 펀드", rng.uniform(-6, 12)), ("MMF", rng.uniform(1, 3))]
    chosen = rng.sample(prods, 4)
    amts = [rng.randint(5, 80) * 1_000_000 for _ in chosen]
    tot = sum(amts)
    if layout == 0:
        nm = rng.choice(NAMES)
        body = [KV([("가입자", nm), ("소속", COMPANY), ("입사일", date(rng, 2012, 2024)), ("제도 유형", kind), ("계좌번호", f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(100000, 999999)}"), ("연간 부담금", won(rng.randint(24, 60) * 100_000))], 2),
                H("운용 상품 현황"), T(["운용 상품", "평가금액", "비중", "수익률(연)"], [(p, won(a), f"{a * 100 / tot:.1f}%", f"{r:.2f}%") for (p, r), a in zip(chosen, amts)], num=(1, 2, 3), foot=("합계", won(tot), "100%", "")),
                H("최근 납입 내역"), T(["납입일", "구분", "금액"], [(ymd(2026, m, 25), "사용자 부담금", won(rng.randint(2, 5) * 100_000)) for m in (7, 8, 9)], num=(2,))]
        return doc(0, "퇴직연금 가입 내역서", body, [("기준일", date(rng, 2026, 2026))], _no(rng, "RP"), issuer=co, sign=())
    people = rng.sample(NAMES, 7)
    rows = [(n, rng.choice(["영업1팀", "물류운영팀", "재무회계팀", "마케팅팀"]), date(rng, 2010, 2024), won(rng.randint(24, 60) * 100_000), won(rng.randint(10, 300) * 1_000_000)) for n in people]
    body = [KV([("사업장", COMPANY), ("제도 유형", kind), ("가입자 수", f"{len(rows)}명 (표시분)"), ("관리 금융사", co)], 2),
            H("가입자별 적립 현황"), T(["가입자", "부서", "가입일", "연간 부담금", "적립금"], rows, num=(3, 4), foot=("합계", "", "", "", won(sum(int(r[4].replace(",", "")) for r in rows)))),
            P("적립금은 운용 수익을 포함한 평가금액이며 기준일 종가 기준이다.")]
    return doc(1, "퇴직연금 가입자 내역서", body, [("조회일", date(rng, 2026, 2026))], _no(rng, "RP"), issuer=co, sign=("담당", "검토"))


def fin22(layout, rng):  # 정부 보조금 교부 결정 통지서
    ag = rng.choice(["한국식품산업진흥원", "중소유통물류진흥원", "지역상권발전재단"])
    prog = rng.choice(["콜드체인 물류 효율화 지원사업", "중소 식품유통기업 스마트 설비 지원사업", "친환경 포장재 전환 지원사업", "청년 고용 연계 유통혁신 사업"])
    amt = rng.randint(3, 40) * 10_000_000
    y = rng.randint(2025, 2026)
    conds = ["교부받은 보조금은 신청서에 기재한 용도 외에 사용할 수 없다.", "보조금 전용 계좌를 별도로 개설하여 관리하여야 한다.", "사업 종료 후 30일 이내에 정산 보고서를 제출하여야 한다.", "허위 신청 또는 목적 외 사용 시 교부 결정을 취소하고 환수한다."]
    if layout == 0:
        body = [KV([("수신", COMPANY + " 대표이사"), ("제목", f"{prog} 보조금 교부 결정 통지")], 1),
                P(f"귀사가 신청한 「{prog}」에 대하여 보조금 교부를 아래와 같이 결정하였기에 통지합니다.", "note"),
                KV([("교부결정액", f"일금 {korean_amount(amt)} (₩{won(amt)})"), ("사업기간", f"{ymd(y, 4, 1)} ~ {ymd(y, 12, 31)}"), ("교부방법", "2회 분할 (선금 70%, 정산 후 잔금 30%)")], 1),
                H("교부 조건"), UL(conds), f"<p class=c style='margin-top:26px;font-size:15px'><b>{ag}장</b> {seal(ag[:4])}</p>"]
        return doc(0, "보조금 교부 결정 통지서", body, [], _no(rng, "문서번호 사업"), issuer=ag, sign=())
    own = int(amt * 0.25)
    body = [grid([f"<div class=card><b>교부 대상</b><br>{COMPANY}</div>", f"<div class=card><b>사업명</b><br>{prog}</div>"], 2),
            H("자금 구성"), T(["구분", "금액", "비율"], [("국고 보조금", won(amt), "75%"), ("자부담", won(own), "25%"), ("총사업비", won(amt + own), "100%")], num=(1, 2)),
            H("지급 일정"), T(["회차", "지급 시기", "금액"], [("1차 (선금)", ymd(y, 4, 20), won(int(amt * 0.7))), ("2차 (잔금)", ymd(y + 1, 1, 31), won(amt - int(amt * 0.7)))], num=(2,)),
            H("준수 사항"), UL(conds[:3]), f"<p class=r style='margin-top:16px'>{date(rng, y, y)} &nbsp; <b>{ag}</b> {seal(ag[:4])}</p>"]
    return doc(1, "보조금 교부결정서", body, [("결정일", date(rng, y, y))], _no(rng, "결정"), issuer=ag, sign=())


FORMS = [("FIN-11", "외상매출금 연령분석표", fin11), ("FIN-12", "환율 변동 손익표", fin12), ("FIN-13", "판매장려금(리베이트) 정산서", fin13),
         ("FIN-14", "입금확인증", fin14), ("FIN-15", "대출금 상환계획표", fin15), ("FIN-16", "이행보증보험증권", fin16), ("FIN-17", "주주명부", fin17),
         ("FIN-18", "고정자산 감가상각 명세서", fin18), ("FIN-19", "현금출납부", fin19), ("FIN-20", "어음관리대장", fin20),
         ("FIN-21", "퇴직연금 가입 내역서", fin21), ("FIN-22", "정부 보조금 교부 결정 통지서", fin22)]
