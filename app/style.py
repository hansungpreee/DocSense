"""화면 공통 스타일: 어두운 배경, 둥근 카드, 주황 포인트 (File Arbor 같은 데스크톱 앱 느낌).
색·글꼴 기본값은 .streamlit/config.toml, 여기서는 카드·사이드바·버튼 모양만 덧입힌다."""
import streamlit as st

CSS = """<style>
:root{--ink:#ececec;--mute:#9a9a9a;--card:#1b1b1b;--line:#2c2c2c;--accent:#d9622b;--accent-soft:#2a1c15;--side:#161616;--chip:#242424}
[data-testid="stSidebar"]{background:var(--side);border-right:1px solid var(--line)}
[data-testid="stSidebarNav"] a{border-radius:10px;padding:.45rem .7rem;margin:2px 0}
[data-testid="stSidebarNav"] a[aria-current="page"]{background:var(--accent-soft);color:var(--accent)}
[data-testid="stSidebarNav"] a[aria-current="page"] *{color:var(--accent)!important}
[data-testid="stLogo"],[data-testid="stSidebarLogo"]{height:3.2rem!important}
.block-container{padding-top:2.2rem;max-width:1180px}
h1{letter-spacing:-.5px}
.page-sub{color:var(--mute);margin:-.6rem 0 1.2rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.card.dash{border-style:dashed}
.card h4{margin:0 0 4px;font-size:15px}
.card .code{color:var(--accent);font-size:12px;font-weight:600}
.card .desc{color:var(--mute);font-size:13px;line-height:1.5;margin-top:6px}
.statbar{display:flex;gap:28px;flex-wrap:wrap;color:var(--mute);font-size:14px}
.statbar b{color:var(--ink);font-size:18px;margin-right:4px}
.empty{text-align:center;padding:56px 12px}
.empty .ico{width:72px;height:72px;border-radius:50%;background:var(--chip);margin:0 auto 16px;
display:flex;align-items:center;justify-content:center;font-size:30px}
.empty h3{margin:0 0 6px}
.empty p{color:var(--mute);margin:0 0 4px}
.usercard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:8px}
.usercard .n{font-weight:600}
.usercard .d{color:var(--mute);font-size:13px}
.pill{display:inline-block;background:var(--accent-soft);color:var(--accent);border-radius:999px;
padding:2px 10px;font-size:12px;margin:2px 4px 2px 0}
.stButton>button,.stDownloadButton>button{border-radius:999px}
.stButton>button[kind="primary"]{background:var(--accent);border-color:var(--accent);color:#fff}
.st-key-help_btn{position:fixed;left:16px;bottom:16px;z-index:1000;width:auto}
.st-key-help_btn button{width:40px;height:40px;min-height:40px;padding:0;border-radius:50%;
border:2px solid var(--mute);background:var(--side);font-weight:700;font-size:18px}
.st-key-help_btn button:hover{border-color:var(--accent);color:var(--accent)}
[data-testid="stFileUploaderDropzone"]{border-style:dashed;border-radius:14px;background:var(--card)}
</style>"""


# 대시보드 맵의 원 (크기는 대시보드가 키별로 정한다). -own- = 우리 부서(주황 빛)
BUBBLE_CSS = (
    '[class*="st-key-bub"] button{background:var(--card);border:2px solid var(--line);color:var(--ink)}'
    '[class*="st-key-bub"] button:hover{border-color:var(--accent);transform:scale(1.04)}'
    '[class*="st-key-bub"][class*="-own-"] button{background:radial-gradient(circle at 35% 30%,#f08a52,#d9622b 70%);'
    'border:3px solid #ffb184;color:#fff;box-shadow:0 0 28px rgba(217,98,43,.55);animation:bubglow 2.6s ease-in-out infinite}'
    '@keyframes bubglow{0%,100%{box-shadow:0 0 18px rgba(217,98,43,.4)}50%{box-shadow:0 0 42px rgba(217,98,43,.8)}}'
    '@keyframes zoomin{from{opacity:0;transform:scale(.3)}60%{opacity:1}to{opacity:1;transform:none}}'  # 작게 모였다가 확 퍼짐
    '@keyframes slidein{from{opacity:0;transform:translateX(48px)}to{opacity:1;transform:none}}'
    '.st-key-mapwrap{position:relative;animation:zoomin .6s cubic-bezier(.16,1,.3,1)}'
    '.st-key-detail{animation:slidein .45s ease-out}'
    '@media (prefers-reduced-motion:reduce){[class*="st-key-bub"] button,.st-key-mapwrap,.st-key-detail{animation:none!important}}'
)


# 투어용 숨은 iframe이 빈 칸을 만들지 않게 한다
HIDE_FRAME = '<style>[data-testid="stElementContainer"]:has(iframe[height="0"]){position:absolute;width:0;height:0;overflow:hidden}</style>'

# 글자 크기: 화면 배치(여백·칸 폭)는 그대로 두고 글자만 키운다. rem 기준이라 html 글자 크기를 바꾸면 화면 전체가 커지므로,
# 글자 요소마다 기본 크기 × 배율을 따로 정한다.
FONT_SIZES = {  # 선택자: 기본 글자 크기(rem)
    ".stApp p,.stApp li,.stApp label,.stApp td,.stApp th,.stApp summary,.stApp input,.stApp textarea,"
    '.stApp [data-testid="stWidgetLabel"] p,.stApp [data-baseweb="select"] div': 1,
    '.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p': 0.875,
    ".stApp h1": 2.75, ".stApp h2": 2.25, ".stApp h3": 1.75, ".stApp h4": 1.5,
    '.stApp [data-testid="stMetricValue"]': 2.25,
}


def font_css(percent: int) -> str:
    if percent == 100:
        return ""
    k = percent / 100
    return "<style>" + "".join(f"{sel}{{font-size:{base * k:.3f}rem}}" for sel, base in FONT_SIZES.items()) + "</style>"


def apply():
    """공통 스타일 + 글자 크기 설정을 입힌다. 설정은 session_state.settings (로그인 전에는 기본값)."""
    cfg = st.session_state.get("settings") or {}
    font = cfg.get("font", 100)
    st.markdown(CSS + HIDE_FRAME + font_css(font), unsafe_allow_html=True)


def card(title: str, body: str = "", code: str = "") -> str:
    """카드 HTML. 마크다운이 코드로 읽지 않도록 들여쓰기와 빈 줄을 두지 않는다. 안쪽 값은 호출하는 쪽에서 escape한다."""
    c = f'<div class="code">{code}</div>' if code else ""
    d = f'<div class="desc">{body}</div>' if body else ""
    return f'<div class="card">{c}<h4>{title}</h4>{d}</div>'
