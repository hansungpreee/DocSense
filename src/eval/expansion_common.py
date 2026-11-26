"""확장 데이터셋(FIN-11~22, MGT-03~14, SAL-07~20) 공통 부품: 양식 틀 2종, 표·블록 도우미, 합성 내용 풀.

- 레이아웃 0: 중앙 제목 + 우측 결재란 (남색). 레이아웃 1: 좌측 제목 띠 + 하단 서명란 (초록).
  소분류마다 두 레이아웃의 본문 구성도 다르게 짠다 (열·항목·배치). 숫자만 바꾼 복제를 피하기 위해서다.
- 문서 안에 정답 단서(확장·계획·OOD 등)를 넣지 않는다. 금액·요율·수치는 합성용 근사값이다.
"""
import random

# ponytail: render_ood·render_new_forms에서 값을 가져오면 playwright가 없는 PC에서 테스트가 import 단계에서 실패한다.
# 그래서 필요한 값만 복사했다. 두 파일의 값이 바뀌어도 이 데이터셋은 그대로여야 하므로 (재생성 시 같은 문서) 복사가 맞다.
COMPANY = "(주)에이치에스리테일"
A4_CSS = (794, 1123)  # A4를 96dpi CSS 픽셀로
SCALE = 1656 / 794  # 본 데이터(200dpi, 1656×2342)와 같은 크기로 저장
PEOPLE = ["김민수", "이서연", "박지훈", "최유진", "정다은", "강현우", "윤채원", "장도윤", "한지민", "오승현"]
NAMES = PEOPLE + ["조은서", "임하준", "서지우", "문태영", "배수아", "신우진", "홍예린", "권도현", "노가은", "백시우"]
TEAMS = ["영업1팀", "영업2팀", "재무회계팀", "물류운영팀", "인사총무팀", "마케팅팀", "구매팀", "가맹사업팀"]
BANKS = ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행", "기업은행"]
SUPPLIERS = [("(주)한결제과", "214-81-3****"), ("대성음료(주)", "128-86-5****"), ("(주)푸른포장", "305-81-7****"),
             ("미래식품(주)", "617-81-2****"), ("(주)동원유통", "110-81-9****")]
DIGITS = "영일이삼사오육칠팔구"


def won(n: int) -> str:
    return f"{n:,}"


def korean_amount(n: int) -> str:
    """3,245,670 → 삼백이십사만오천육백칠십원정 (일 단위의 '일'은 십·백·천 앞에서 생략)."""
    parts, units = [], ["", "만", "억"]
    for group in range(2, -1, -1):  # 억, 만, 일 묶음
        chunk = n // 10_000 ** group % 10_000
        if not chunk:
            continue
        text = ""
        for place, unit in zip((1000, 100, 10, 1), ("천", "백", "십", "")):
            d = chunk // place % 10
            if d:
                text += ("" if d == 1 and unit else DIGITS[d]) + unit
        parts.append(text + units[group])
    return "".join(parts) + "원정"


CLIENTS = ["한빛마트", "새롬유통", "그린플러스", "가온슈퍼", "별빛상회", "다온마트", "푸른들유통", "누리편의점본부",
           "해든식품", "모아로지스", "세종푸드마켓", "온누리상사", "한울물산", "미래스토어", "청솔마트", "도담유통"]
REGIONS = ["서울", "경기", "인천", "강원", "충청", "전라", "경상", "제주"]
CSS = """
body { font-family: 'Noto Sans CJK KR', 'Malgun Gothic', sans-serif; margin: 0; padding: 34px 44px; color: #1b1f24; font-size: 16px; line-height: 1.45; }
.t0 { --c: #1f3a5f; --l: #eef1f6; --b: #c3cbd6; --a: #d9822b; }
.t1 { --c: #1d6b57; --l: #e9f4f0; --b: #b9d4cb; --a: #c0562f; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--b); padding: 9px 8px; }
th { background: var(--l); color: var(--c); font-weight: 600; text-align: center; white-space: nowrap; }
.nb > tbody > tr > td { border: none; padding: 0; vertical-align: top; }
.brand { font-size: 20px; font-weight: 700; color: var(--c); letter-spacing: 1px; }
.docno { font-size: 12px; color: #55627a; margin-top: 3px; }
h1 { text-align: center; font-size: 31px; letter-spacing: 8px; margin: 14px 0 16px; color: var(--c); }
.band { background: var(--c); color: #fff; padding: 14px 18px; margin: 0 0 14px; display: flex; justify-content: space-between; align-items: baseline; }
.band .t { font-size: 29px; font-weight: 700; letter-spacing: 3px; } .band .s { font-size: 12px; opacity: .85; }
h3 { font-size: 16px; margin: 16px 0 7px; color: var(--c); }
.t1 h3 { border-left: 5px solid var(--c); padding-left: 8px; }
.t0 h3 { border-bottom: 2px solid var(--c); padding-bottom: 2px; }
.r { text-align: right; } .c { text-align: center; } .l { text-align: left; }
.tot td, .tot th { background: var(--l); font-weight: 700; }
.note { font-size: 13px; color: #444; line-height: 1.6; margin: 8px 0; }
ul { margin: 3px 0; padding-left: 18px; } li { margin: 2px 0; }
.sign th { width: 62px; } .sign td { height: 48px; width: 62px; }
.seal { display: inline-block; width: 56px; height: 56px; border: 2px solid #c0392b; color: #c0392b; border-radius: 50%; text-align: center;
        font-size: 11px; line-height: 1.2; padding-top: 14px; box-sizing: border-box; transform: rotate(-8deg); font-weight: 700; }
.bar { height: 11px; background: var(--l); border: 1px solid var(--b); } .bar i { display: block; height: 100%; background: var(--c); }
.card { border: 1px solid var(--b); padding: 8px 10px; } .card b { color: var(--c); }
.grid { display: grid; gap: 8px; }
.big { font-size: 22px; font-weight: 700; color: var(--c); }
.ph { background: var(--l); border: 1px dashed var(--b); }
"""


def page(body: str, layout: int = 0) -> str:
    return f"<!DOCTYPE html><html lang=ko><head><meta charset=utf-8><style>{CSS}</style></head><body class=t{layout}>{body}</body></html>"


def H(text: str) -> str:
    return f"<h3>{text}</h3>"


def P(text: str, cls: str = "note") -> str:
    return f"<p class={cls}>{text}</p>"


def UL(items) -> str:
    return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def T(head, rows, num=(), foot=None, left=(), style: str = "") -> str:
    """표. num 열은 오른쪽 정렬, left 열은 왼쪽 정렬, foot은 합계 줄."""
    def cell(j, v, tag="td"):
        cls = "r" if j in num else ("l" if j in left else "c")
        return f"<{tag} class={cls}>{v}</{tag}>"
    html = f"<table style='{style}'><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"
    for row in rows:
        html += "<tr>" + "".join(cell(j, v) for j, v in enumerate(row)) + "</tr>"
    if foot:
        html += "<tr class=tot>" + "".join(cell(j, v) for j, v in enumerate(foot)) + "</tr>"
    return html + "</table>"


def KV(pairs, cols: int = 2) -> str:
    """(항목, 값) 쌍을 cols개씩 한 줄에 놓는 표."""
    html = "<table>"
    for k in range(0, len(pairs), cols):
        html += "<tr>"
        for key, val in pairs[k:k + cols]:
            html += f"<th style='width:90px'>{key}</th><td>{val}</td>"
        html += "</tr>"
    return html + "</table>"


def bar(pct: float, color: str = "") -> str:
    bg = f";background:{color}" if color else ""
    return f"<div class=bar><i style='width:{min(max(pct, 0), 100):.0f}%{bg}'></i></div>"


def grid(cells, cols: int, gap: int = 8) -> str:
    return f"<div class=grid style='grid-template-columns:repeat({cols},1fr);gap:{gap}px'>" + "".join(cells) + "</div>"


def seal(text: str) -> str:
    return f"<span class=seal>{text}</span>"


def date(rng: random.Random, y0: int = 2025, y1: int = 2026) -> str:
    return f"{rng.randint(y0, y1)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def ymd(y: int, m: int, d: int) -> str:
    return f"{y}-{m:02d}-{d:02d}"


def doc(layout: int, title: str, blocks, meta=(), no: str = "", issuer: str = COMPANY, sign=("담당", "팀장", "이사")) -> str:
    """양식 틀. 레이아웃 0은 중앙 제목·우측 결재란, 1은 제목 띠·하단 서명란."""
    body = "".join(blocks)
    if layout == 0:
        appr = ""
        if sign:
            appr = ("<table class=sign><tr>" + "".join(f"<th>{s}</th>" for s in sign) + "</tr><tr>" + "<td></td>" * len(sign) + "</tr></table>")
        head = (f"<table class=nb><tr><td><div class=brand>{issuer}</div><div class=docno>{no}</div></td>"
                f"<td style='width:{62 * len(sign) + 4}px'>{appr}</td></tr></table><h1>{title}</h1>")
        metas = KV(list(meta), 2) if meta else ""
        return page(head + metas + body, 0)
    head = f"<div class=band><span class=t>{title}</span><span class=s>{issuer}{' · ' + no if no else ''}</span></div>"
    metas = ("<div style='display:flex;flex-wrap:wrap;gap:4px 22px;font-size:14px;margin:0 0 8px'>"
             + "".join(f"<span><b style='color:var(--c)'>{k}</b> {v}</span>" for k, v in meta) + "</div>") if meta else ""
    foot = ""
    if sign:
        foot = ("<table class=nb style='margin-top:14px'><tr>" + "".join(
            f"<td style='text-align:center;font-size:12px;color:#55627a;padding-top:22px'><div style='border-top:1px solid #888;margin:0 14px;padding-top:3px'>{s}</div></td>"
            for s in sign) + "</tr></table>")
    return page(head + metas + body + foot, 1)
