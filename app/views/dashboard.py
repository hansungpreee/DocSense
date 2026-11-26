"""대시보드: 대분류 맵. 로그인하면 바로 나온다. 우리 부서 대분류는 가운데에서 가장 크고 주황색으로 빛나고, 나머지 원이 둘러싼다.
원을 누르면 맵이 슬라이드로 넘어가며 그 대분류로 분류한 내 문서 목록이 나온다."""
from html import escape

import streamlit as st

import math

import doclist
import services
import style
from i18n import t

style.apply()
store = st.session_state.store
user = st.session_state.user
mine = set(user["majors"])

history = [r for r in store.list_history() if r.get("status") != "error"]
majors = sorted(services.map_majors(), key=lambda m: m not in mine)  # 우리 부서 대분류가 앞에 온다 (정렬은 안정적)
docs = {m: [r for r in history if services.shown(r)[0] == m] for m in majors}
items = {m: services.department_items([m]) for m in majors}
st.session_state.setdefault("map_view", None)  # 문서 목록을 보고 있는 대분류 (None이면 맵)


def open_major(m: str | None):
    st.session_state.map_view = m
    if m:  # 누른 원을 기억해 두었다가, 맵으로 돌아올 때 그 원에서부터 확대한다
        st.session_state.map_from = m


def minor_pills(m: str) -> str:
    return "".join(f"<span class='pill'>{escape(t(it.name))}</span>" for it in items[m]) or f"<span class='pill'>{t('분류 체계 밖 문서')}</span>"


st.markdown("<style>" + style.BUBBLE_CSS + "</style>", unsafe_allow_html=True)
view = st.session_state.map_view

if view in docs:  # 문서 목록 화면
    with st.container(key="detail"):
        st.button(t("← 대분류 맵으로"), on_click=open_major, args=(None,))
        st.markdown(f"## {escape(t(view))}" + (f" <span class='pill'>{t('우리 부서')}</span>" if view in mine else ""), unsafe_allow_html=True)
        st.markdown(minor_pills(view), unsafe_allow_html=True)
        if docs[view]:
            doclist.show(docs[view], "dash")
        else:
            st.info(t("이 대분류로 분류한 문서가 아직 없습니다."))
    st.stop()

head, switch = st.columns([3, 1.4], vertical_alignment="bottom")
head.title(t("대시보드"))
MODES = {"map": "맵", "list": "목록"}
mode = switch.segmented_control(t("보기"), list(MODES), default="map", key="dash_view", format_func=lambda v: t(MODES[v]),
                                label_visibility="collapsed") or "map"
st.markdown(f"<div class='page-sub'>"
            + t("{n} {t}님, 주황색으로 빛나는 가운데 원이 <b>{d}</b> 담당 대분류입니다. 원을 누르면 그 대분류의 문서가 나옵니다.",
                n=escape(user["name"]), t=escape(t(user["title"])), d=escape(t(user["department"]))) + "</div>",
            unsafe_allow_html=True)

BIG, SMALL, GAP = 230, 160, 28  # 가운데(우리 부서) 원, 둘러싼 원의 지름, 원 사이 최소 간격 (px)


def code_of(m: str) -> str:
    """원 안에 쓰는 대분류 코드: 소분류 코드의 앞부분 (HR-01 → HR). 소분류가 없는 「기타」는 ETC."""
    return items[m][0].code.split("-")[0] if items[m] else "ETC"


MAP_TOP = 190  # 맵 위쪽(제목·안내·여백)이 차지하는 높이 (px). 화면 높이에서 이만큼을 뺀 만큼만 맵에 쓴다.


def u(v: float) -> str:
    """맵 안의 길이(px). --u는 맵이 화면 높이에 맞게 줄어드는 비율(최대 1px)이라, 화면이 낮으면 맵 전체가 같이 작아진다."""
    return f"{v:.0f} * var(--u)"


if mode == "map":
    with st.container(key="mapwrap"):
        center, ring = majors[0], majors[1:]  # majors는 우리 부서 대분류가 맨 앞
        n = len(ring)
        # 둘러싼 원끼리, 그리고 가운데 원과 겹치지 않는 가장 작은 반지름
        radius = max((BIG + SMALL) / 2 + GAP, (SMALL + GAP) / (2 * math.sin(math.pi / n)) if n > 2 else 0)
        height = int(2 * radius + SMALL + 40)
        # 제목을 위로 붙이고(여백 축소), 맵은 화면 높이에 다 들어오게 0.62~1배로 줄인다
        css = (".block-container{padding-top:1rem}.stApp h1{padding:.2rem 0 .3rem}.page-sub{margin:-.6rem 0 .4rem}"
               f".st-key-mapwrap{{--u:max(.62px,min(1px,calc((100vh - {MAP_TOP}px) / {height})));"
               f"height:calc({u(height)});min-width:calc({u(int(2 * radius + SMALL))})}}")
        spots = [(center, 0.0, 0.0, BIG)] + [
            (m, radius * math.cos(math.radians(-90 + 360 * k / n)), radius * math.sin(math.radians(-90 + 360 * k / n)), SMALL)
            for k, m in enumerate(ring)]
        # 맵이 나올 때 확대가 시작하는 점: 마지막으로 누른 원의 중심 (처음 열 때는 가운데)
        ox, oy = next(((dx, dy) for m, dx, dy, _ in spots if m == st.session_state.get("map_from")), (0.0, 0.0))
        css += f".st-key-mapwrap{{transform-origin:calc(50% + {u(ox)}) calc({u(height // 2 + oy)})}}"
        for i, (m, dx, dy, size) in enumerate(spots):
            key = f"bub{i}-{'own' if m in mine else 'oth'}-"
            css += (f".st-key-{key}{{position:absolute;width:calc({u(size)});left:calc(50% + {u(dx)} - {u(size // 2)});"
                    f"top:calc({u(height // 2 + dy)});margin-top:calc(-1 * {u(size // 2)})}}"
                    f".st-key-{key} button{{width:calc({u(size)});height:calc({u(size)});border-radius:50%;"
                    f"white-space:normal;line-height:1.35}}")
            st.button(f"**{code_of(m)}**\n\n{t(m)}", key=key, on_click=open_major, args=(m,),
                      help=t("문서 {n}건", n=len(docs[m])))
        st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)
else:
    for i, m in enumerate(majors):
        with st.expander(f"{'★ ' if m in mine else ''}{t(m)} · {t('문서 {n}건', n=len(docs[m]))}", expanded=m in mine):
            st.markdown(minor_pills(m), unsafe_allow_html=True)
            if docs[m]:
                doclist.show(docs[m], f"dashl{i}")
            else:
                st.info(t("이 대분류로 분류한 문서가 아직 없습니다."))
