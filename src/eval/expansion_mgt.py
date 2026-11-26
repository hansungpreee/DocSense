"""경영/전략 확장 12종 (MGT-03~14). 각 함수는 (레이아웃 0/1, 난수) → HTML. 수치는 합성용 근사값이다."""
import random

from src.eval.expansion_common import (CLIENTS, COMPANY, NAMES, REGIONS, TEAMS, H, KV, P, T, UL, bar, date, doc,
                                       grid, won, ymd)


def _no(rng, prefix):
    return f"{prefix}-{rng.randint(2025, 2026)}-{rng.randint(1, 99):03d}"


SUBJECTS = ["PB 쿠키 사업", "음료 B2B 유통 사업", "수도권 신규 거래처 확대", "온라인 주문 플랫폼", "냉동 베이커리 라인", "선물세트 사업", "편의점 채널 납품"]
PRODUCTS = ["HS 현미 크런치바", "HS 제로 탄산수 청귤", "HS 말차 쿠키", "HS 곡물 라떼", "HS 흑임자 롤케이크", "HS 콜드브루 스틱", "HS 단호박 에그타르트", "HS 요거트 그래놀라"]


def mgt03(layout, rng):  # SWOT 분석서
    pool = {"S": ["전국 120개 거래처 유통망", "자체 물류센터 보유", "PB 상품 기획력", "거래처와의 장기 신뢰 관계", "냉장·상온 통합 배송", "안정적 외상 회수율"],
            "W": ["온라인 채널 경험 부족", "신제품 개발 인력 부족", "특정 대형 거래처 매출 의존", "물류 비용 상승", "재고 관리 시스템 노후", "브랜드 인지도 낮음"],
            "O": ["편의점·디저트 시장 성장", "건강 지향 소비 확대", "중소 제조사의 판로 위탁 수요", "정부 유통 혁신 지원사업", "동남아 수출 문의 증가", "정기 구독형 B2B 수요"],
            "T": ["원재료 가격 인상", "대형 유통사의 PB 확대", "최저임금 인상", "소비 심리 위축", "신규 경쟁사 진입", "식품 안전 규제 강화"]}
    pick = {k: rng.sample(v, 4) for k, v in pool.items()}
    title = rng.choice(SUBJECTS)
    names = {"S": "강점 (Strength)", "W": "약점 (Weakness)", "O": "기회 (Opportunity)", "T": "위협 (Threat)"}
    meta = [("분석 대상", title), ("작성일", date(rng)), ("작성", rng.choice(TEAMS))]
    if layout == 0:
        cell = lambda k: f"<div class=card style='min-height:190px'><b>{names[k]}</b>{UL(pick[k])}</div>"
        body = [H("내부 · 외부 환경 분석"), grid([cell("S"), cell("W"), cell("O"), cell("T")], 2, 10),
                H("종합 의견"), P(f"{title}은(는) {pick['S'][0]}을(를) 바탕으로 {pick['O'][0]}에 대응할 수 있으나, {pick['W'][0]} 과제를 보완해야 한다.", "note")]
    else:
        st = {"SO": f"{pick['S'][0]}를 활용해 {pick['O'][0]} 선점", "WO": f"{pick['O'][1]}를 계기로 {pick['W'][0]} 보완",
              "ST": f"{pick['S'][1]}로 {pick['T'][0]} 영향 완화", "WT": f"{pick['W'][1]} 개선 및 {pick['T'][1]} 대비"}
        body = [T(["구분", "긍정 요인", "부정 요인"], [("내부 환경", UL(pick["S"][:3]), UL(pick["W"][:3])), ("외부 환경", UL(pick["O"][:3]), UL(pick["T"][:3]))], left=(1, 2)),
                H("전략 도출"), T(["전략", "내용"], [(k, v) for k, v in st.items()], left=(1,)), P("우선순위: SO → WO → ST → WT 순으로 실행 계획에 반영한다.")]
    return doc(layout, "SWOT 분석서", body, meta, _no(rng, "SW"))


def mgt04(layout, rng):  # 신제품 출시 계획서
    pr = rng.choice(PRODUCTS)
    y = rng.randint(2026, 2027)
    price = rng.randint(15, 60) * 100
    ms = [("콘셉트 확정", 1), ("시제품 개발", 2), ("소비자 테스트", 3), ("포장·디자인 확정", 4), ("초도 생산", 5), ("거래처 입점", 6)]
    if layout == 0:
        body = [KV([("제품명", pr), ("제품 구분", rng.choice(["과자류", "음료류", "베이커리"])), ("용량", f"{rng.choice([120, 150, 200, 330, 500])}g"), ("소비자가", f"{won(price)}원"),
                    ("목표 고객", rng.choice(["20~30대 직장인", "10대 학생", "30~40대 주부", "시니어"])), ("출시 목표", ymd(y, rng.randint(3, 10), 1))], 2),
                H("출시 일정"), T(["단계", "시기", "담당", "산출물"], [(a, ymd(y, m, 15)[:7], rng.choice(TEAMS), rng.choice(["보고서", "시제품", "시안", "계획서"])) for a, m in ms]),
                H("판매 목표"), T(["구분", "1분기", "2분기", "3분기", "4분기"], [("판매량(개)", *[won(rng.randint(5, 40) * 1000) for _ in range(4)]), ("매출(원)", *[won(rng.randint(10, 90) * 1_000_000) for _ in range(4)])], num=(1, 2, 3, 4))]
    else:
        body = [f"<div class=card><span class=big>{pr}</span> &nbsp; 소비자가 {won(price)}원 · 출시 {ymd(y, rng.randint(3, 10), 1)}</div>",
                H("개발 단계"), "<div style='display:flex;gap:6px'>" + "".join(f"<div class=card style='flex:1;text-align:center'><b>{i}</b><br>{a}<br><small>{y}-{m:02d}</small></div>" for i, (a, m) in enumerate(ms, 1)) + "</div>",
                H("포지셔닝 및 채널"), T(["항목", "내용"], [("차별점", rng.choice(["저당 · 곡물 함량 강화", "개별 포장 소용량", "국산 원료 100%"])), ("주요 채널", rng.choice(["편의점·대형마트", "백화점 식품관", "온라인 몰"])), ("프로모션", rng.choice(["입점 기념 1+1", "시식 행사", "SNS 체험단"]))], left=(1,)),
                H("예산"), T(["항목", "금액"], [("개발비", won(rng.randint(10, 60) * 1_000_000)), ("마케팅비", won(rng.randint(10, 80) * 1_000_000)), ("초도 생산비", won(rng.randint(20, 100) * 1_000_000))], num=(1,))]
    return doc(layout, "신제품 출시 계획서", body, [("작성", rng.choice(TEAMS)), ("작성일", date(rng))], _no(rng, "NP"))


def mgt05(layout, rng):  # 시장조사보고서
    cat = rng.choice(["간편 디저트", "RTD 음료", "건강 스낵", "냉동 베이커리", "선물용 과자"])
    base = rng.randint(8, 30) * 1000
    yrs = [2022 + i for i in range(5)]
    g = rng.uniform(0.03, 0.12)
    vals = [int(base * (1 + g) ** i) for i in range(5)]
    mx = max(vals)
    chart = "<div style='display:flex;align-items:flex-end;gap:14px;height:150px;border-bottom:2px solid #888;padding:0 14px'>" + "".join(
        f"<div style='flex:1;text-align:center;font-size:12px'>{won(v)}<div style='height:{v * 105 // mx}px;background:var(--c);margin-top:2px'></div></div>" for v in vals) + "</div>" + \
        "<div style='display:flex;gap:14px;padding:3px 14px'>" + "".join(f"<div style='flex:1;text-align:center;font-size:12px'>{y}</div>" for y in yrs) + "</div>"
    shares = sorted([rng.randint(8, 30) for _ in range(4)], reverse=True)
    survey = [("가격", rng.randint(20, 40)), ("맛", rng.randint(25, 45)), ("브랜드", rng.randint(5, 15)), ("포장·용량", rng.randint(5, 20))]
    if layout == 0:
        body = [H("조사 개요"), KV([("조사 주제", f"{cat} 시장"), ("조사 방법", "온라인 설문 + 유통 데이터"), ("표본", f"{rng.randint(5, 20) * 100}명"), ("조사 기간", date(rng, 2026, 2026))], 2),
                H(f"시장 규모 추이 (단위: 억 원)"), chart, H("시사점"), UL(["성장률이 연 5~10%대로 완만하게 둔화되는 추세", f"{rng.choice(['저당', '소용량', '프리미엄'])} 제품군의 비중 확대", "편의점 채널 중심의 신제품 회전이 빨라짐"])]
    else:
        body = [H("조사 개요"), P(f"{cat} 시장 소비자 인식 조사 (표본 {rng.randint(5, 20) * 100}명, 오차 ±3%p)"),
                H("구매 시 중요 요인 (%)"), "".join(f"<div style='display:flex;align-items:center;gap:10px;margin:5px 0'><span style='width:90px'>{k}</span><div style='flex:1'>{bar(v * 2)}</div><b>{v}%</b></div>" for k, v in survey),
                H("업체별 점유율 (%)"), T(["순위", "구분", "점유율"], [(i + 1, f"{c}", f"{s}%") for i, (c, s) in enumerate(zip(["A사", "B사", "C사", "기타"], shares))], num=(2,)),
                H("결론"), P("가격 민감도가 높은 대신 맛 만족도가 재구매를 좌우한다. 중가 · 소용량 라인업이 유효하다.")]
    return doc(layout, "시장조사보고서", body, [("작성", "경영기획팀"), ("작성일", date(rng, 2026, 2026))], _no(rng, "MR"))


def mgt06(layout, rng):  # 프로젝트 일정표 (간트차트)
    tasks = ["요구사항 정의", "거래처 인터뷰", "시스템 설계", "시제품 제작", "내부 테스트", "파일럿 운영", "개선 반영", "전사 확대", "결과 보고", "사후 점검"]
    n = rng.randint(7, 9)
    weeks = 16 if layout == 0 else 20
    t0, rows = 0, []
    for nm in tasks[:n]:
        s = min(t0 + rng.randint(0, 2), weeks - 2); e = min(s + rng.randint(2, 5), weeks); rows.append((nm, rng.choice(NAMES[:10]), s, e)); t0 = s + 1
    cols = "".join(f"<th style='padding:3px 0;font-size:10px'>{w + 1}</th>" for w in range(weeks))
    trs = ""
    for nm, who, s, e in rows:
        cells = "".join(f"<td style='padding:0;height:26px;{('background:var(--c)' if s <= w < e else '')}'></td>" for w in range(weeks))
        trs += f"<tr><td class=l style='white-space:nowrap'>{nm}</td><td>{who}</td>{cells}</tr>"
    if layout == 1:
        trs = trs.replace("background:var(--c)", "background:var(--a)")
    body = [f"<table style='font-size:13px'><tr><th>업무</th><th>담당</th>{cols}</tr>{trs}</table>",
            P(("◼ 표시 기간이 계획 구간. 숫자는 주차." if layout == 0 else "막대는 계획 구간, 주차 기준. 마일스톤은 주간 회의에서 확정한다.")),
            T(["마일스톤", "목표 주차", "확인"], [("시제품 완료", rows[min(3, n - 1)][3], ""), ("파일럿 종료", rows[min(5, n - 1)][3], ""), ("최종 보고", rows[-1][3], "")], num=(1,))]
    meta = [("프로젝트", rng.choice(["물류 시스템 개편", "신규 거래처 포털 구축", "PB 라인 확대", "재고 관리 개선"])), ("기간", f"{weeks}주"), ("PM", rng.choice(NAMES[:10]))]
    return doc(layout, "프로젝트 일정표 (간트차트)", body, meta, _no(rng, "PJ"))


def mgt07(layout, rng):  # 업무 처리 매뉴얼
    topics = {"신규 거래처 등록": ["사업자등록증 접수", "신용 조사 의뢰", "여신 한도 결정", "시스템 등록", "계약서 체결"],
              "반품 접수 및 처리": ["반품 요청 접수", "사유 확인", "회수 차량 배정", "검수 및 재입고", "대금 정정"],
              "입고 검수": ["입고 예약 확인", "차량 도착 확인", "수량·유통기한 검수", "불량 분리", "전산 입고 등록"],
              "외상대금 회수": ["연체 거래처 목록 추출", "담당자 연락", "독촉장 발송", "입금 확인", "법무 이관 검토"],
              "재고 실사": ["실사 일정 공지", "전산 재고 동결", "현장 실사", "차이 원인 분석", "재고 조정"]}
    t = rng.choice(list(topics))
    steps = topics[t]
    who = ["영업담당", "물류팀", "재무회계팀", "팀장", "구매팀"]
    if layout == 0:
        body = [KV([("목적", f"{t} 업무의 표준 절차를 정한다."), ("적용 범위", "전 사업장 및 협력 물류센터")], 1), H("처리 절차"),
                T(["단계", "담당", "업무 내용", "소요"], [(i + 1, rng.choice(who), s, f"{rng.randint(1, 3)}일") for i, s in enumerate(steps)], left=(2,)),
                H("유의사항"), UL(["증빙 서류는 5년간 보관한다.", "예외 처리는 팀장 승인 후 진행한다."]), H("개정 이력"), T(["개정", "일자", "내용"], [("1.0", date(rng, 2023, 2024), "최초 제정"), ("1.1", date(rng, 2025, 2026), "절차 보완")])]
    else:
        flow = "<div style='display:flex;align-items:stretch;gap:4px'>" + "<div style='align-self:center;color:var(--c)'>▶</div>".join(
            f"<div class=card style='flex:1;text-align:center'><b>{i + 1}</b><br>{s}<br><small style='color:#666'>{rng.choice(who)}</small></div>" for i, s in enumerate(steps)) + "</div>"
        body = [H("업무 흐름"), flow, H("단계별 점검"), T(["단계", "점검 항목", "관련 서식"], [(s, rng.choice(["누락 서류 확인", "승인자 서명", "시스템 등록 여부"]), rng.choice(["처리 대장", "확인서", "체크리스트"])) for s in steps], left=(1, 2)),
                H("예외 상황"), UL(["긴급 건은 구두 승인 후 24시간 내 서류를 보완한다.", "처리 지연 시 팀장에게 즉시 보고한다."])]
    return doc(layout, f"업무 처리 매뉴얼 : {t}", body, [("문서 관리번호", _no(rng, "MN")), ("시행일", date(rng))], _no(rng, "MN"))


def mgt08(layout, rng):  # 신규 물류센터 사업타당성 검토서
    sites = rng.sample(["이천", "용인", "평택", "김포", "천안", "안성"], 3)
    inv = rng.randint(30, 120) * 100_000_000
    irr = rng.uniform(6, 16)
    if layout == 0:
        body = [H("후보지 비교"), T(["항목", *sites], [("부지 면적(㎡)", *[won(rng.randint(5, 20) * 1000) for _ in sites]), ("월 임차료(만 원)", *[won(rng.randint(30, 90) * 100) for _ in sites]), ("수도권 접근(분)", *[rng.randint(25, 90) for _ in sites]), ("종합 점수", *[rng.randint(60, 95) for _ in sites])], num=(1, 2, 3)),
                H("투자비 및 수익성"), T(["구분", "금액"], [("토지·건물", won(int(inv * .6))), ("설비·시스템", won(int(inv * .3))), ("초기 운영비", won(int(inv * .1))), ("총 투자비", won(inv))], num=(1,)),
                KV([("NPV", f"{won(rng.randint(5, 60) * 10_000_000)}원"), ("IRR", f"{irr:.1f}%"), ("투자 회수", f"{rng.randint(4, 9)}년"), ("추천 후보지", sites[0])], 2)]
    else:
        sc = [("낙관", 1.2), ("기준", 1.0), ("비관", 0.75)]
        body = [P(f"검토 대상: {sites[0]} 부지 {rng.randint(8, 15) * 1000}㎡ 규모 상온·냉장 복합 물류센터. 총 투자비 {won(inv)}원."),
                H("시나리오별 수익성"), T(["시나리오", "연 처리 물동량", "연 영업이익", "IRR", "회수 기간"], [(n, f"{won(int(rng.randint(15, 25) * 10_000 * k))}박스", won(int(rng.randint(3, 8) * 100_000_000 * k)), f"{irr * k:.1f}%", f"{max(3, int(9 / k))}년") for n, k in sc], num=(1, 2)),
                H("민감도"), "".join(f"<div style='display:flex;gap:10px;align-items:center;margin:5px 0'><span style='width:110px'>{k}</span><div style='flex:1'>{bar(v)}</div><b>{v}%</b></div>" for k, v in [("임차료 ±10%", 35), ("물동량 ±10%", 70), ("인건비 ±10%", 50)]),
                H("검토 결론"), UL(["기준 시나리오에서 투자 회수가 가능하며 비관 시나리오에서도 손익분기를 넘는다.", "단계적 투자(1단계 60%)를 권고한다."])]
    return doc(layout, "신규 물류센터 사업타당성 검토서", body, [("작성", "경영기획팀"), ("검토일", date(rng, 2026, 2026))], _no(rng, "FS"))


def mgt09(layout, rng):  # 사업장 현황표
    kinds = [("본사", "서울", "임차"), ("용인 물류센터", "경기", "자가"), ("이천 냉장센터", "경기", "임차"), ("부산 지점", "경상", "임차"), ("광주 지점", "전라", "임차"), ("대전 지점", "충청", "임차"),
             ("강릉 영업소", "강원", "임차"), ("제주 영업소", "제주", "임차"), ("인천 영업소", "인천", "임차")]
    sel = rng.sample(kinds, rng.randint(5, 6))
    rows = [(nm, rg, f"{rg} {rng.choice(['중구', '동구', '서구', '남구'])} {rng.randint(1, 300)}번지", won(rng.randint(2, 300) * 100), ho, rng.randint(5, 120), date(rng, 2008, 2023)) for nm, rg, ho in sel]
    if layout == 0:
        body = [T(["사업장", "소재지", "면적(㎡)", "구분", "인원", "개설일"], [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in rows], num=(2, 4), left=(1,), foot=("합계", f"{len(rows)}개소", "", "", sum(r[5] for r in rows), ""))]
    else:
        body = []
        for rg in dict.fromkeys(r[1] for r in rows):
            g = [r for r in rows if r[1] == rg]
            body += [H(f"{rg} 권역"), T(["사업장", "주요 기능", "면적(㎡)", "인원", "가동률"], [(r[0], rng.choice(["영업·관리", "상온 물류", "냉장 물류", "영업 거점"]), r[3], r[5], f"{rng.randint(65, 98)}%") for r in g], num=(2, 3, 4))]
    return doc(layout, "사업장 현황표", body, [("기준일", date(rng, 2026, 2026)), ("작성", "인사총무팀")], _no(rng, "BS"))


def mgt10(layout, rng):  # ESG 경영 보고서
    y = rng.randint(2024, 2025)
    kp = lambda a, b: rng.randint(a, b)
    env = [("온실가스 배출량 (tCO2e)", kp(900, 1800)), ("에너지 사용량 (MWh)", kp(1500, 3200)), ("폐기물 재활용률 (%)", kp(55, 90)), ("친환경 포장재 비중 (%)", kp(10, 60))]
    soc = [("임직원 수 (명)", kp(180, 400)), ("여성 관리자 비율 (%)", kp(15, 40)), ("산업재해 건수", kp(0, 3)), ("1인당 교육시간 (h)", kp(15, 50))]
    gov = [("이사회 개최 횟수", kp(6, 12)), ("사외이사 비율 (%)", kp(20, 50)), ("윤리 교육 이수율 (%)", kp(85, 100)), ("협력사 행동규범 서약률 (%)", kp(70, 100))]
    if layout == 0:
        body = []
        for t, d in [("환경 (E)", env), ("사회 (S)", soc), ("지배구조 (G)", gov)]:
            body += [H(t), T(["지표", f"{y - 2}년", f"{y - 1}년", f"{y}년"], [(k, won(max(v + rng.randint(-v // 5, v // 5), 0)), won(max(v + rng.randint(-v // 8, v // 8), 0)), won(v)) for k, v in d], num=(1, 2, 3), left=(0,))]
    else:
        def col(t, d):
            return f"<div class=card><b style='font-size:16px'>{t}</b>" + "".join(f"<div style='margin:9px 0'><small>{k}</small><div class=big style='font-size:19px'>{won(v)}</div></div>" for k, v in d) + "</div>"
        body = [grid([col("E 환경", env), col("S 사회", soc), col("G 지배구조", gov)], 3, 10), H("중점 추진 목표"),
                "".join(f"<div style='display:flex;gap:10px;align-items:center;margin:6px 0'><span style='width:230px'>{k}</span><div style='flex:1'>{bar(v)}</div><b>{v}%</b></div>" for k, v in [("탄소 배출 감축 목표", kp(20, 70)), ("친환경 포장재 전환", kp(20, 70)), ("협력사 ESG 평가", kp(30, 90))])]
    return doc(layout, f"{y} ESG 경영 보고서", body, [("보고 기간", f"{y}-01-01 ~ {y}-12-31"), ("작성", "경영기획팀")], _no(rng, "ES"), sign=("작성", "검토", "대표이사"))


def mgt11(layout, rng):  # 리스크 관리 대장
    pool = [("원재료 가격 급등", "시장"), ("핵심 거래처 이탈", "영업"), ("물류센터 화재", "운영"), ("식품 위생 사고", "품질"), ("시스템 장애", "IT"), ("외상매출금 부실화", "재무"), ("환율 급변동", "재무"), ("핵심 인력 퇴사", "인사"),
            ("법규 위반 과태료", "법무"), ("배송 차량 사고", "운영")]
    sel = rng.sample(pool, rng.randint(7, 9) if layout == 0 else 6)
    rows = []
    for k, (nm, cat) in enumerate(sel, 1):
        p, i = rng.randint(1, 5), rng.randint(1, 5)
        rows.append((f"R-{k:02d}", nm, cat, p, i, p * i, rng.choice(["보험 가입", "대체 공급처 확보", "정기 점검 강화", "이중화 구축", "교육 실시", "한도 관리"]), rng.choice(NAMES[:10]), rng.choice(["관리 중", "대응 중", "모니터링"])))
    grade = lambda s: "상" if s >= 15 else ("중" if s >= 8 else "하")
    if layout == 0:
        body = [T(["번호", "리스크", "분류", "가능성", "영향도", "점수", "등급", "대응방안", "담당"], [(r[0], r[1], r[2], r[3], r[4], r[5], grade(r[5]), r[6], r[7]) for r in rows], style="font-size:13px")]
    else:
        heat = "<table style='width:300px;text-align:center'>" + "".join("<tr><th>" + str(pr) + "</th>" + "".join(
            f"<td style='height:34px;background:{'#e8a7a0' if pr * im >= 15 else '#f3dba0' if pr * im >= 8 else '#cfe5cf'}'>{''.join(r[0][2:] + ' ' for r in rows if r[3] == pr and r[4] == im)}</td>" for im in range(1, 6)) + "</tr>" for pr in range(5, 0, -1)) + "<tr><th></th>" + "".join(f"<th>{i}</th>" for i in range(1, 6)) + "</tr></table>"
        body = [H("리스크 매트릭스 (세로: 가능성, 가로: 영향도)"), heat, H("관리 대상"), T(["번호", "리스크", "점수", "대응방안", "상태"], [(r[0], r[1], r[5], r[6], r[8]) for r in rows], left=(1, 3))]
    return doc(layout, "리스크 관리 대장", body, [("점검 분기", f"{rng.randint(2025, 2026)}년 {rng.randint(1, 4)}분기"), ("관리", "경영기획팀")], _no(rng, "RK"))


def mgt12(layout, rng):  # 조직도
    heads = [("영업본부", ["영업1팀", "영업2팀", "가맹사업팀"]), ("물류본부", ["물류운영팀", "구매팀", "품질관리팀"]), ("경영지원본부", ["재무회계팀", "인사총무팀", "법무팀"]), ("마케팅본부", ["마케팅팀", "상품기획팀"])]
    heads = rng.sample(heads, 3) if layout == 1 else heads
    person = lambda: rng.choice(NAMES)
    box = lambda t, n, s="": f"<div class=card style='text-align:center;{s}'><b>{t}</b><br><small>{n}</small></div>"
    if layout == 0:
        cols = "".join(f"<div style='flex:1'>{box(h, person() + ' 본부장', 'background:var(--l)')}<div style='border-left:2px solid var(--c);margin:0 auto;height:14px;width:0'></div>" + "".join(box(t, person() + ' 팀장', 'margin-bottom:8px') for t in ts) + "</div>" for h, ts in heads)
        body = ["<div style='text-align:center;width:240px;margin:6px auto 0'>" + box("대표이사", person(), "background:var(--c);color:#fff") + "</div><div style='border-left:2px solid var(--c);margin:0 auto;height:18px;width:0'></div>"
                "<div style='border-top:2px solid var(--c);margin:0 12%'></div><div style='height:12px'></div>", f"<div style='display:flex;gap:12px'>{cols}</div>"]
    else:
        rows = "".join(f"<div style='display:flex;align-items:center;gap:10px;margin:12px 0'><div style='width:150px'>{box(h, person() + ' 본부장', 'background:var(--l)')}</div><div style='border-top:2px solid var(--c);width:20px'></div>" +
                       "".join(f"<div style='flex:1'>{box(t, person())}</div>" for t in ts) + "</div>" for h, ts in heads)
        body = [f"<div style='display:flex;gap:14px'><div style='width:140px;align-self:center'>{box('대표이사', person(), 'background:var(--c);color:#fff')}</div><div style='flex:1;border-left:2px solid var(--c);padding-left:10px'>{rows}</div></div>",
                T(["구분", "인원"], [(h, f"{rng.randint(12, 60)}명") for h, _ in heads], num=(1,), style="margin-top:14px;width:50%")]
    return doc(layout, "조 직 도" if layout == 0 else "조직도 (본부·팀)", body, [("기준일", date(rng, 2026, 2026)), ("작성", "인사총무팀")], _no(rng, "OG"), sign=("작성", "승인"))


def mgt13(layout, rng):  # 회사 소개서
    founded = rng.randint(1998, 2008)
    stats = [("설립", f"{founded}년"), ("임직원", f"{rng.randint(180, 420)}명"), ("연 매출", f"{rng.randint(800, 2500)}억 원"), ("거래처", f"{rng.randint(90, 320)}곳")]
    hist = [(founded, "법인 설립"), (founded + 4, "제과·음료 유통 사업 확대"), (founded + 9, "용인 물류센터 준공"), (founded + 13, "PB 브랜드 출시"), (founded + 16, "온라인 주문 시스템 도입")]
    biz = [("제과 유통", "전국 편의점·마트 대상 쿠키·스낵 공급"), ("음료 유통", "주스·탄산수·RTD 차 공급"), ("PB 상품", "자체 브랜드 기획·위탁 생산"), ("물류 서비스", "상온·냉장 통합 배송")]
    if layout == 0:
        body = [H("회사 개요"), KV([("회사명", COMPANY), ("대표이사", rng.choice(NAMES)), ("본사", "서울특별시 강남구"), *stats[:3], ("주요 사업", "제과·음료 B2B 유통")], 2), H("연혁"), T(["연도", "내용"], hist, left=(1,)),
                H("사업 영역"), T(["사업", "내용"], biz, left=(1,)), P("문의: 영업기획팀 02-" + f"{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}")]
    else:
        body = [f"<div style='background:var(--c);color:#fff;padding:20px;text-align:center'><div style='font-size:24px;font-weight:700'>{COMPANY}</div><div>맛있는 유통의 파트너</div></div>", grid([f"<div class=card style='text-align:center'><small>{k}</small><div class=big>{v}</div></div>" for k, v in stats], 4, 8),
                H("사업 분야"), grid([f"<div class=card><b>{k}</b><br><small>{v}</small></div>" for k, v in biz], 2, 8), H("주요 연혁"), "".join(f"<div style='margin:4px 0'><b style='color:var(--c)'>{y}</b> &nbsp; {t}</div>" for y, t in hist),
                H("주요 거래처"), P(" · ".join(rng.sample(CLIENTS, 6)))]
    return doc(layout, "회사 소개서" if layout == 0 else "COMPANY PROFILE 회사소개", body, [], _no(rng, "CP"), sign=())


def mgt14(layout, rng):  # 신년 경영 방침서
    y = rng.randint(2025, 2027)
    slogans = ["신뢰로 잇는 유통, 한 걸음 더", "현장 중심, 고객 중심", "함께 성장하는 파트너십", "지속가능한 성장, 효율의 한 해"]
    sl = rng.choice(slogans)
    goals = [("매출액", f"{rng.randint(900, 2600)}억 원", f"+{rng.randint(4, 12)}%"), ("영업이익률", f"{rng.randint(25, 60) / 10}%", f"+{rng.randint(2, 9) / 10}%p"), ("신규 거래처", f"{rng.randint(15, 60)}곳", ""), ("재고 회전율", f"{rng.randint(10, 18)}회", "")]
    strat = ["핵심 거래처 관계 강화", "PB 상품 라인업 확대", "물류 효율화 및 비용 절감", "데이터 기반 의사결정 정착"]
    if layout == 0:
        body = [f"<p class=c style='font-size:22px;font-weight:700;color:var(--c);margin:14px 0'>“{sl}”</p>", H("경영 목표"), T(["지표", f"{y}년 목표", "전년 대비"], goals, num=(1, 2)),
                H("핵심 전략"), UL(strat), H("부문별 중점 과제"), T(["부문", "중점 과제"], [(rng.choice(["영업", "물류", "재무", "인사"]) + "부문", s) for s in strat], left=(1,)), P("대표이사 " + rng.choice(NAMES) + " 올림", "note")]
    else:
        body = [f"<div style='background:var(--l);border-left:8px solid var(--c);padding:16px;font-size:22px;font-weight:700'>{y}년 경영 슬로건 &nbsp;|&nbsp; {sl}</div>",
                grid([f"<div class=card style='text-align:center'><small>{k}</small><div class=big>{v}</div><small>{d}</small></div>" for k, v, d in goals], 4, 8), H("4대 핵심 전략"),
                grid([f"<div class=card><b>{i}. {s}</b><br><small>{rng.choice(['분기별 점검', '팀별 KPI 반영', '월간 성과 공유'])}</small></div>" for i, s in enumerate(strat, 1)], 2, 8), H("대표 메시지"),
                P("지난 한 해의 성과를 바탕으로 올해는 내실을 다지고 거래처와의 신뢰를 더욱 깊게 하겠습니다. 전 임직원의 협력을 부탁드립니다.", "note")]
    return doc(layout, f"{y}년 신년 경영 방침서", body, [("시행일", ymd(y, 1, 2)), ("발신", "대표이사")], _no(rng, "MP"), sign=("작성", "대표이사"))


FORMS = [("MGT-03", "SWOT 분석서", mgt03), ("MGT-04", "신제품 출시 계획서", mgt04), ("MGT-05", "시장조사보고서", mgt05), ("MGT-06", "프로젝트 일정표(간트차트)", mgt06),
         ("MGT-07", "업무 처리 매뉴얼", mgt07), ("MGT-08", "신규 물류센터 사업타당성 검토서", mgt08), ("MGT-09", "사업장 현황표", mgt09), ("MGT-10", "ESG 경영 보고서", mgt10),
         ("MGT-11", "리스크 관리 대장", mgt11), ("MGT-12", "조직도", mgt12), ("MGT-13", "회사 소개서", mgt13), ("MGT-14", "신년 경영 방침서", mgt14)]
