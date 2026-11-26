"""분류 대기 화면 (문서 전송, 429 재시도 서류철). 업로드 화면과 결과 화면의 다시 시도 버튼이 함께 쓴다."""
from contextlib import contextmanager
from html import escape

import streamlit as st

# 분류 대기 화면: 문서가 「업로드」 폴더에서 「분류」 폴더로 날아가는 CSS 애니메이션.
# Python이 응답을 기다리는 동안에도 브라우저가 움직인다. 마크다운이 코드로 읽지 않도록 들여쓰기와 빈 줄을 두지 않는다.
LOADING_HTML = """<style>
.docsend{display:flex;align-items:center;gap:14px;padding:6px 0;color:inherit}
.docsend .row{display:flex;align-items:flex-end;gap:10px;flex:none}
.docsend .tray{position:relative;width:54px;height:40px;border:2px solid #6f87b8;border-radius:4px 4px 8px 8px;
background:#e4eaf6;box-sizing:border-box}
.docsend .tray::before{content:"";position:absolute;left:-2px;top:-9px;width:22px;height:9px;border:2px solid #6f87b8;
border-bottom:0;border-radius:4px 4px 0 0;background:#e4eaf6;box-sizing:border-box}
.docsend .tray small{position:absolute;inset:auto 0 3px 0;text-align:center;font-size:11px;color:#3d4f78}
.docsend .lane{position:relative;width:132px;height:40px;flex:none}
.docsend .lane i{position:absolute;left:0;top:8px;width:18px;height:24px;box-sizing:border-box;
border:1px solid #aab4c6;border-radius:2px;background:repeating-linear-gradient(#fff 0 5px,#d9deea 5px 6px);
box-shadow:0 1px 2px rgba(0,0,0,.2);opacity:0;animation:docsend 1.6s linear infinite}
.docsend .lane i:nth-child(2){animation-delay:-.4s}
.docsend .lane i:nth-child(3){animation-delay:-.8s}
.docsend .lane i:nth-child(4){animation-delay:-1.2s}
@keyframes docsend{0%{transform:translate(0,0) rotate(-10deg) scale(.7);opacity:0}12%{opacity:1}
50%{transform:translate(58px,-12px) rotate(4deg) scale(1)}88%{opacity:1}
100%{transform:translate(116px,0) rotate(12deg) scale(.7);opacity:0}}
@media (prefers-reduced-motion:reduce){.docsend .lane i{animation:none;opacity:.9}
.docsend .lane i:nth-child(n+3){display:none}}
</style>
<div class="docsend" role="status"><div class="row"><div class="tray"><small>업로드</small></div>
<div class="lane"><i></i><i></i><i></i><i></i></div><div class="tray"><small>분류</small></div></div>
<span>분류 중입니다...</span></div>"""

# 429 재시도 대기 화면: 서류철에 종이 2장이 장당 약 2초 속도로 들어가는 반복 애니메이션. 속도는 대기 시간과 무관하게 고정이고,
# 남은 시간은 문구가 알린다. 문구 자리({msg})는 on_wait가 받은 안내 문구로 바꾼다.
WAIT_HTML = """<style>
.putwait{display:flex;align-items:center;gap:20px;padding:6px 0;color:inherit}
.putwait .file{position:relative;width:84px;height:92px;flex:none}
.putwait .back{position:absolute;left:0;bottom:0;width:84px;height:52px;border:2px solid #6f87b8;
border-radius:4px 6px 6px 6px;background:#cfd9ee;box-sizing:border-box}
.putwait .back::before{content:"";position:absolute;left:-2px;top:-10px;width:28px;height:10px;border:2px solid #6f87b8;
border-bottom:0;border-radius:4px 4px 0 0;background:#cfd9ee;box-sizing:border-box}
.putwait .sheet{position:absolute;bottom:8px;width:44px;height:50px;box-sizing:border-box;border:1px solid #aab4c6;
border-radius:2px;background:repeating-linear-gradient(#fff 0 7px,#d9deea 7px 8px);box-shadow:0 1px 2px rgba(0,0,0,.2);
animation:putin-a 4.4s linear infinite}
.putwait .sheet.a{left:8px}
.putwait .sheet.b{left:30px;animation-name:putin-b}
.putwait .front{position:absolute;left:0;bottom:0;width:84px;height:32px;border:2px solid #6f87b8;
border-radius:3px 3px 6px 6px;background:#e4eaf6;box-sizing:border-box}
@keyframes putin-a{0%{transform:translateY(-38px);opacity:1}45%,92%{transform:translateY(0);opacity:1}
96%{transform:translateY(0);opacity:0}96.1%{transform:translateY(-38px);opacity:0}
100%{transform:translateY(-38px);opacity:1}}
@keyframes putin-b{0%,45%{transform:translateY(-38px);opacity:1}90%,92%{transform:translateY(0);opacity:1}
96%{transform:translateY(0);opacity:0}96.1%{transform:translateY(-38px);opacity:0}
100%{transform:translateY(-38px);opacity:1}}
@media (prefers-reduced-motion:reduce){.putwait .sheet{animation:none;transform:translateY(-14px)}}
</style>
<div class="putwait" role="status"><div class="file"><div class="back"></div><div class="sheet a"></div>
<div class="sheet b"></div><div class="front"></div></div><b>{msg}</b></div>"""


@contextmanager
def loading():
    """분류하는 동안 대기 애니메이션을 보여 주고, 끝나거나 오류가 나면 지운다. 429 대기 때 쓸 on_wait 함수를 넘겨 준다."""
    box = st.empty()
    box.markdown(LOADING_HTML, unsafe_allow_html=True)

    def on_wait(msg):  # 429로 기다리는 동안은 서류철 애니메이션으로 바꾸고, 재시도 요청 중에도 그대로 둔다
        box.markdown(WAIT_HTML.replace("{msg}", escape(msg)), unsafe_allow_html=True)

    try:
        yield on_wait
    finally:
        box.empty()
