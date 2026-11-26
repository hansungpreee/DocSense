"""계획 75종 중 인사/채용·고객/거래처·법무/총무 양식 생성에 같이 쓰는 부품 (표·서명란·도장·이름 풀·페이지 틀).

회사는 본 데이터와 같은 '(주)에이치에스리테일'이고, 사람·거래처·기관 이름은 모두 지어낸 것이다.
공공기관은 실제 기관 대신 가상 지명(새빛시·누리구·누리세무서)을 쓰고, 번호는 일부를 가린다 (예: 617-81-2****).
"""
import datetime
import html
import random

COMPANY = "(주)에이치에스리테일"
COMPANY_SHORT = "에이치에스리테일"
HQ_ADDR = "경기도 용인시 처인구 물류단지로 128"
HQ_TEL = "031-555-0100"

SURNAMES = list("김이박최정강조윤장임한오서신권황안송류홍")
GIVEN = ["민수", "서연", "지훈", "유진", "다은", "현우", "채원", "도윤", "지민", "승현", "예진", "준호", "하늘", "수빈",
         "태윤", "나연", "주원", "시우", "소영", "재현", "은지", "동현", "미래", "성민", "혜원", "보람", "규원", "아린"]
TEAMS = ["영업1팀", "영업2팀", "재무회계팀", "물류운영팀", "인사총무팀", "마케팅팀", "구매팀", "가맹사업팀", "품질관리팀"]
POSITIONS = ["사원", "주임", "대리", "과장", "차장", "부장"]
CUSTOMERS = ["미래식품(주)", "한울푸드(주)", "청솔유통(주)", "대성마트(주)", "새롬식자재(주)", "행복나눔유통", "우리동네마트",
             "푸른들F&B(주)", "삼일상사(주)", "동행물산(주)", "가온리테일(주)", "늘봄유통(주)", "(주)바른식품", "해든푸드",
             "하나로상회", "(주)다온마켓", "누리유통", "새벽식품(주)", "(주)이음상사", "보람F&C", "(주)온누리마트",
             "솔빛유통", "(주)한결식자재", "청명유통(주)", "두레푸드(주)"]
ROADS = ["물류단지로", "중앙로", "산업로", "한강로", "시청로", "상공로", "평화로", "대학로", "송림로", "호수로", "청계로"]
CITIES = ["경기도 용인시 처인구", "경기도 수원시 영통구", "경기도 성남시 중원구", "서울특별시 강서구", "서울특별시 송파구",
          "인천광역시 남동구", "경기도 화성시", "경기도 평택시", "충청북도 청주시 흥덕구", "대전광역시 유성구",
          "부산광역시 강서구", "경상북도 구미시", "광주광역시 광산구", "경기도 안성시"]
PRODUCTS = [("HS 오렌지주스", "1L×12병", 21600), ("HS 웨하스", "150g×30입", 29700), ("HS 초코쿠키", "90g×40입", 33200),
            ("HS 탄산음료", "355ml×24캔", 18900), ("HS 딸기잼 쿠키", "120g×36입", 36500), ("HS 사과주스", "500ml×20병", 24800),
            ("HS 버터크래커", "200g×24입", 27400), ("HS 아이스티", "500ml×24병", 22100), ("HS 마들렌", "35g×60입", 31800),
            ("HS 보리차", "1.5L×12병", 14400), ("HS 오트밀바", "40g×50입", 38900), ("HS 생수", "2L×6병", 5400)]
STATUS = ["", "비고 없음"]


def person(rng):
    return rng.choice(SURNAMES) + rng.choice(GIVEN)


def rdate(rng, y=2026, m1=1, m2=10):
    m = rng.randint(m1, m2)
    d = rng.randint(1, 28)
    return datetime.date(y, m, d)


def kd(d, sep="."):
    return f"{d.year}{sep}{d.month:02d}{sep}{d.day:02d}"


def kdk(d):
    return f"{d.year}년 {d.month}월 {d.day}일"


def phone(rng):
    return f"010-****-{rng.randint(1000, 9999)}"


def tel(rng, area="031"):
    return f"{area}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}"


def biz_no(rng):
    return f"{rng.randint(105, 899)}-{rng.randint(10, 99)}-{rng.randint(1, 9)}****"


def addr(rng):
    return f"{rng.choice(CITIES)} {rng.choice(ROADS)} {rng.randint(10, 400)}"


def won(n):
    return f"{n:,}"


def e(s):
    return html.escape(str(s))


def kv(pairs, cols=2, lw=None):
    """라벨·값 표. pairs는 (라벨, 값) 목록이고 값에 HTML을 그대로 쓸 수 있다. cols=1이면 한 줄에 한 쌍."""
    rows = []
    for i in range(0, len(pairs), cols):
        cells = ""
        for lab, val in pairs[i:i + cols]:
            cells += f"<th{f' style=width:{lw}px' if lw else ''}>{lab}</th><td>{val}</td>"
        miss = cols - len(pairs[i:i + cols])
        if miss:
            cells += "<td colspan=%d></td>" % (miss * 2)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table class=kv>{''.join(rows)}</table>"


def tbl(headers, rows, aligns=None, widths=None, foot=None, cls=""):
    aligns = aligns or ["c"] * len(headers)
    cg = "".join(f"<col style=width:{w}>" for w in widths) if widths else ""
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td class={a}>{c}</td>" for a, c in zip(aligns, r)) + "</tr>"
    ft = f"<tr class=ft>{foot}</tr>" if foot else ""
    return f"<table class='t {cls}'><colgroup>{cg}</colgroup><tr>{th}</tr>{body}{ft}</table>"


def approval(labels, h=58):
    ths = "".join(f"<th>{x}</th>" for x in labels)
    tds = "".join(f"<td style=height:{h}px></td>" for _ in labels)
    return f"<table class=appr><tr><th rowspan=2 class=ap>결<br>재</th>{ths}</tr><tr>{tds}</tr></table>"


def sign(labels, h=54):
    ths = "".join(f"<th>{x}</th>" for x in labels)
    tds = "".join(f"<td style=height:{h}px></td>" for _ in labels)
    return f"<table class=sg><tr>{ths}</tr><tr>{tds}</tr></table>"


def seal(rng, text="인", size=54, extra=""):
    rot = rng.randint(-14, 14)
    return (f"<span class=seal style='width:{size}px;height:{size}px;line-height:{size - 6}px;"
            f"font-size:{size * 0.34:.0f}px;transform:rotate({rot}deg);{extra}'>{text}</span>")


def square_seal(rng, text, size=64):
    rot = rng.randint(-8, 8)
    return (f"<span class=sseal style='width:{size}px;height:{size}px;font-size:{size * 0.3:.0f}px;"
            f"transform:rotate({rot}deg)'>{text}</span>")


BASE_CSS = """
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#fff}
body{font-family:%(font)s;color:#1b1f24;font-size:%(fs)s;line-height:1.5;width:794px}
.pg{width:794px;padding:%(pad)s;position:relative}
h1{margin:0;text-align:%(ta)s;font-size:27px;letter-spacing:%(ls)s;font-weight:800}
h1.sm{font-size:22px}
.sub{text-align:center;color:#555;margin:6px 0 0;font-size:13px}
h2{font-size:14.5px;margin:18px 0 6px;font-weight:700;color:%(ac)s;border-left:4px solid %(ac)s;padding-left:7px}
p{margin:6px 0}
table{border-collapse:collapse;width:100%%}
th,td{border:1px solid %(bc)s;padding:6px 8px;vertical-align:middle}
th{background:%(th)s;color:%(thc)s;font-weight:700;font-size:12.5px;text-align:center}
td.l{text-align:left}td.r{text-align:right}td.c{text-align:center}
.kv{margin:12px 0}.kv th{width:96px}
.t{margin:10px 0}.t tr.ft td,.t tr.ft th{background:%(th)s;color:%(thc)s;font-weight:700}
.appr{width:auto;float:right;margin:0 0 12px 12px}.appr th{width:70px;font-size:12px;padding:4px}.appr th.ap{width:28px}
.sg{width:auto;margin:14px 0 0 auto}.sg th{width:86px;font-size:12px;padding:4px}
.right{text-align:right}.center{text-align:center}.small{font-size:11.5px;color:#444}.muted{color:#666}
.foot{text-align:center;font-weight:700;font-size:16px;margin-top:26px;letter-spacing:1px}
.seal{display:inline-block;border:2.5px solid #c0282d;border-radius:50%%;color:#c0282d;text-align:center;font-weight:800;vertical-align:middle;opacity:.88}
.sseal{display:inline-flex;align-items:center;justify-content:center;border:2.5px solid #c0282d;color:#c0282d;font-weight:800;text-align:center;line-height:1.15;opacity:.88}
.box{border:1px solid #444;padding:10px 12px;margin:8px 0}
.cb{display:inline-block;width:12px;height:12px;border:1.4px solid #333;vertical-align:-1px;margin-right:4px}
.cb.on{background:#333}
.clr{clear:both}
ul.b{margin:4px 0 4px 18px;padding:0}ul.b li{margin:2px 0}
"""


def page(body, font="sans", ac="#1f3a5f", th="#eceff3", thc="#1b1f24", bc="#444", fs="13px", ta="center",
         pad="44px 48px 40px", ls="6px", extra=""):
    ff = {"sans": "'Noto Sans CJK KR','Noto Sans KR',sans-serif",
          "serif": "'Noto Serif CJK KR','Noto Serif KR',serif"}[font]
    css = BASE_CSS % {"font": ff, "ac": ac, "th": th, "thc": thc, "bc": bc, "fs": fs, "ta": ta, "pad": pad, "ls": ls}
    return f"<!DOCTYPE html><html lang=ko><head><meta charset=utf-8><style>{css}{extra}</style></head><body><div class=pg>{body}</div></body></html>"


ACCENTS = ["#1f3a5f", "#2f6f4f", "#7a3b2e", "#3d3d8f", "#555555", "#8a5a14"]
THS = ["#eceff3", "#eef3ec", "#f3eeea", "#ececf6", "#f0f0f0", "#f6f1e6"]


def look(rng, **over):
    """문서마다 조금씩 다른 강조색·머리글·테두리·글자 크기·제목 정렬 (같은 양식의 다른 회사 복사본처럼 보이게)."""
    i = rng.randrange(len(ACCENTS))
    dark = rng.random() < 0.3
    d = {"ac": ACCENTS[i], "th": "#2b3645" if dark else THS[i], "thc": "#ffffff" if dark else "#1b1f24",
         "bc": rng.choice(["#444", "#222", "#666"]), "fs": rng.choice(["12.5px", "13px", "13.5px"]),
         "ta": rng.choice(["center", "center", "left"])}
    d.update(over)
    return d


def people(rng, n):
    """겹치지 않는 이름 n개."""
    out = []
    while len(out) < n:
        p = person(rng)
        if p not in out:
            out.append(p)
    return out
