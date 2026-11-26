"""데모 진입점: 페이지 등록과 공통 사이드바. 사번으로 로그인한 뒤에만 화면이 열린다 (데모용 가상 비밀번호, 보안 기능 아님). 분류 이력은 사원마다 따로 저장한다.

실행 (저장소 루트에서): streamlit run app/main.py
"""
from html import escape

import streamlit as st

from pathlib import Path

import guide
import services
import style
import tour
from i18n import t

st.set_page_config(page_title="HS리테일 문서 분류", page_icon="🐢", layout="wide")

@st.cache_resource
def get_store(emp_id: str):
    """사원마다 하나씩 만든다 (같은 사원이 새로고침하거나 탭을 여러 개 열어도 같은 이력을 본다). 사원끼리는 이력을 공유하지 않는다.
    어떤 저장소를 쓸지는 services.open_store()가 정한다."""
    return services.open_store(emp_id)


st.logo(str(Path(__file__).parent / "assets" / "hs_logo.svg"), size="large")

if "user" not in st.session_state:
    st.navigation([st.Page("views/login.py", title="로그인", icon=":material/login:")]).run()
    st.stop()

user = st.session_state.user
st.session_state.store = get_store(user["id"])
if "settings" not in st.session_state:  # 로그인할 때 한 번 읽는다 (바뀌면 설정 화면이 session_state와 파일을 함께 고친다)
    st.session_state.settings = services.load_settings(user["id"])
settings = st.session_state.settings
pages = [
    st.Page("views/dashboard.py", title=t("대시보드"), icon=":material/dashboard:", default=True),
    st.Page("views/upload.py", title=t("업로드"), icon=":material/upload_file:"),
    st.Page("views/history.py", title=t("이력"), icon=":material/history:"),
    st.Page("views/report.py", title=t("보안 현황"), icon=":material/shield:"),
    st.Page("views/forms.py", title=t("문서 양식"), icon=":material/description:"),
    st.Page("views/settings.py", title=t("설정"), icon=":material/settings:"),
]
nav = st.navigation(pages)
style.apply()

with st.sidebar:
    st.markdown(f"<div class='usercard'><div class='n'>{escape(user['name'])} {escape(t(user['title']))}</div>"
                f"<div class='d'>{escape(t(user['department']))} · {escape(user['id'])}</div></div>", unsafe_allow_html=True)
    if st.button(t("로그아웃"), width="stretch"):
        for k in ("user", "store", "map_view", "map_from", "up_tab", "settings", "up_names", "up_done", "up_new"):
            st.session_state.pop(k, None)
        st.rerun()
    if st.button("?", key="help_btn", help=t("프로그램 설명")):  # 왼쪽 아래 동그라미 안의 물음표 (위치는 style.py)
        guide.open_dialog()

# 사용 방법 안내: 설정이 「매일」이면 하루에 한 번, 「설정 > 다시 보기」를 누르면 바로 (조건은 tour.py의 스크립트가 판단)
replay = st.session_state.pop("tour_force", False)
if replay or settings["tour"] == "daily":
    tour.show(user["id"], force=replay)

nav.run()
