"""보안 현황 리포트: 기간 안에 분류한 문서의 보안 등급별·대분류별 건수 (강의계획서 주제 3 「현황 리포트 생성」).
집계는 services.grade_report()가 한다. 이 화면은 기간을 고르고 표·차트·CSV로 보여 준다."""
from datetime import date

import pandas as pd
import streamlit as st

import services
from i18n import t

store = st.session_state.store

st.title(t("보안 현황 리포트"))
st.caption(t("내가 분류한 문서의 보안 등급과 대분류 현황입니다. 등급은 지금 등급표 기준이며, 「기타」 문서는 분류 체계 밖이라 등급이 없습니다."))
history = store.list_history()
if not history:
    st.info(t("아직 분류 이력이 없습니다."))
    st.stop()

first = min(date.fromisoformat(r["created_at"][:10]) for r in history if r.get("created_at"))
today = date.today()
picked = st.date_input(t("기간"), (first, today), max_value=today, format="YYYY-MM-DD")
if len(picked) != 2:  # 시작일만 고른 상태
    st.info(t("종료일도 골라 주세요."))
    st.stop()
start, end = picked
rep = services.grade_report(history, start, end)

st.metric(t("검사 문서"), t("{n}건").format(n=rep["total"]))
if not rep["total"]:
    st.info(t("이 기간에 분류한 문서가 없습니다."))
    st.stop()

grades = pd.DataFrame(rep["by_grade"])
majors = pd.DataFrame(rep["by_major"])
c1, c2 = st.columns(2)
with c1:
    st.subheader(t("보안 등급별"))
    st.bar_chart(grades, x="보안 등급", y="건수", sort=False, horizontal=True, x_label="")
    st.dataframe(grades, hide_index=True, width="stretch")
with c2:
    st.subheader(t("대분류별"))
    st.bar_chart(majors, x="대분류", y="건수", sort=False, horizontal=True, x_label="")
    st.dataframe(majors, hide_index=True, width="stretch")

period = f"{start:%Y%m%d}-{end:%Y%m%d}"
summary = pd.concat([grades.rename(columns={"보안 등급": "항목"}).assign(구분="보안 등급"),
                     majors.rename(columns={"대분류": "항목"}).assign(구분="대분류")])[["구분", "항목", "건수", "비율(%)"]]
d1, d2 = st.columns(2)
d1.download_button(t("요약 CSV 내려받기"), summary.to_csv(index=False).encode("utf-8-sig"),  # 엑셀 한글 깨짐 방지(BOM)
                   file_name=f"보안현황_요약_{period}.csv", mime="text/csv", width="stretch")
d2.download_button(t("문서별 CSV 내려받기"), pd.DataFrame(rep["rows"]).to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"보안현황_문서별_{period}.csv", mime="text/csv", width="stretch")
