"""로그인 화면: 사번과 가상 비밀번호가 맞으면 이름·부서가 붙는다 (데모용, 보안 기능 아님)."""
import streamlit as st

from pathlib import Path

import services
import style
from i18n import t

LOGO = Path(__file__).resolve().parents[1] / "assets" / "hs_logo.svg"

style.apply()
_, mid, _ = st.columns([1, 1.4, 1])
with mid:
    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
    st.image(str(LOGO), width=360)
    st.markdown("### " + t("한성부기들의 서류 정리방"))
    st.markdown("<div class='page-sub'>" + t("사번과 비밀번호를 입력해 시작하세요. 소속 부서에 맞는 문서를 먼저 보여드립니다.") + "</div>",
                unsafe_allow_html=True)
    with st.form("login"):
        emp_id = st.text_input(t("사번"))
        password = st.text_input(t("비밀번호"), type="password")
        ok = st.form_submit_button(t("로그인"), type="primary", width="stretch")
    if ok:
        emp = services.login(emp_id, password)
        if emp is None:
            st.error(t("사번 또는 비밀번호가 올바르지 않습니다."))
        else:
            st.session_state.user = emp
            st.rerun()
