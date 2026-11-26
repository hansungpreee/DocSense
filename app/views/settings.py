"""설정: 글자 크기, 언어, 사용 방법 안내. 바꾸면 바로 내 계정 설정 파일에 저장된다."""
import streamlit as st

import services
from i18n import t

user = st.session_state.user
cfg = st.session_state.settings

FONTS = {90: "작게", 100: "보통", 115: "크게", 130: "매우 크게"}
LANGS = {"ko": "한국어", "en": "English"}
TOURS = {"daily": "매일 처음 열 때 보여주기", "off": "끄기"}


def save(key: str):
    """위젯이 바뀌면 설정을 저장한다. 위젯 값은 session_state['set_<key>']에 있다."""
    value = st.session_state[f"set_{key}"]
    services.save_setting(user["id"], key, value)
    st.session_state.settings[key] = value


def choose(key: str, label: str, names: dict, translate: bool = True):
    st.radio(label, list(names), index=list(names).index(cfg[key]), key=f"set_{key}", horizontal=True,
             format_func=lambda v: t(names[v]) if translate else names[v], on_change=save, args=(key,))


st.title(t("설정"))
st.caption(t("설정은 내 계정에만 저장됩니다. 파일 이름과 AI가 쓴 판단 근거는 번역되지 않습니다."))
choose("font", t("글자 크기"), FONTS)
choose("lang", t("언어"), LANGS, translate=False)
choose("tour", t("사용 방법 안내"), TOURS)
if st.button(t("사용 방법 안내 다시 보기")):
    st.session_state.tour_force = True  # main.py가 다음 화면에서 한 번 보여 준다
    st.rerun()
