"""문서 양식: 회사에서 쓰는 모든 문서 양식을 대분류별로 찾고 내려받는 인트라넷식 목록."""
from html import escape

import streamlit as st

import services
import style
from i18n import t

style.apply()
user = st.session_state.user
st.title(t("문서 양식"))
st.markdown("<div class='page-sub'>" + t("회사에서 쓰는 모든 문서 양식을 대분류별로 찾아 내려받을 수 있습니다. "
            "내려받은 파일은 한글(HWP)·PDF 원본 그대로이니 열어서 작성하세요.") + "</div>", unsafe_allow_html=True)

query = st.text_input(t("양식 검색"), placeholder=t("문서 이름, 코드, 설명으로 검색"), label_visibility="collapsed").strip().lower()
majors = services.all_majors()
items = services.department_items(majors)
if query:
    items = [it for it in items if query in f"{it.code} {it.name} {it.definition}".lower()]


def label(m: str) -> str:
    n = sum(it.major == m for it in items)
    return f"{'★ ' if m in user['majors'] else ''}{t(m)} ({n})"


tabs = st.tabs([t("전체 ({n})", n=len(items))] + [label(m) for m in majors])
for tab, major in zip(tabs, [None] + majors):
    with tab:
        shown = [it for it in items if major is None or it.major == major]
        if not shown:
            st.info(t("조건에 맞는 양식이 없습니다."))
        for it in shown:
            with st.expander(f"{it.code} · {t(it.name)}" + (f"  ({t(it.major)})" if major is None else "")):
                st.write(it.definition)
                f = services.form_file(it.code)
                if f is None:
                    st.caption(t("양식 파일 준비 중"))
                else:  # 내려받는 이름은 문서 종류 이름 (예: 근로계약서.hwp)
                    st.download_button(f"⬇ {t(it.name)}", services.form_bytes(f), file_name=it.name + f.suffix,
                                       mime=services.form_mime(f), key=f"dl_{major}_{it.code}")
