"""이력 화면: 분류 결과 목록과 필터 (FR-11). 목록은 doclist가 그린다."""
import pandas as pd
import streamlit as st

import doclist
import services
from i18n import t

store = st.session_state.store  # services.open_store()가 만든 저장소
user = st.session_state.user

st.title(t("분류 이력"))
st.caption(t("내가 분류한 문서만 보입니다. 다른 사원의 이력과는 공유되지 않습니다."))
history = store.list_history()
if not history:
    st.info(t("아직 분류 이력이 없습니다."))
    st.stop()

rows = {r["id"]: services.result_row(r) for r in history}

SCOPES = ["우리 부서", "전체"]
scope = st.segmented_control(t("보기"), SCOPES, default=SCOPES[0], key="hist_scope", format_func=t,
                             help=t("우리 부서는 담당 대분류만, 전체는 모든 대분류의 이력을 보여줍니다.")) or SCOPES[1]
c1, c2, c3 = st.columns(3)
options = sorted({row["대분류"] for row in rows.values() if row["대분류"]})
majors = c1.multiselect(t("대분류"), options, format_func=t, help=t("비워 두면 위의 '보기' 범위를 따릅니다. 고르면 그 대분류만 봅니다."))
status = c2.multiselect(t("상태"), sorted({row["상태"] for row in rows.values() if row["상태"]}), format_func=t)
keyword = c3.text_input(t("파일명 검색")).strip().lower()
review = st.toggle(t("검토 필요만 보기"), key="hist_review",
                   help=t("「기타」로 빠졌거나, 분류에 실패했거나, 교차 확인에서 미확정인 문서만 보여줍니다. 담당자가 확인해야 하는 문서입니다."))

if not majors and scope == "우리 부서":
    majors = [m for m in user["majors"] if m in options]
found = [r for r in history
         if (not majors or rows[r["id"]]["대분류"] in majors)
         and (not status or rows[r["id"]]["상태"] in status)
         and (not review or rows[r["id"]]["상태"] != "확정" or rows[r["id"]]["교차 확인"] == "미확정")
         and keyword in str(rows[r["id"]]["파일명"]).lower()]

if found:
    doclist.show(found, "hist")
    df = pd.DataFrame([rows[r["id"]] for r in found])  # 화면에 보이는 조건 그대로 내려받는다
    st.download_button(t("CSV 내려받기"), df.to_csv(index=False).encode("utf-8-sig"),  # 엑셀에서 한글이 깨지지 않도록 BOM 포함
                       file_name="분류이력.csv", mime="text/csv")
else:
    st.info(t("조건에 맞는 이력이 없습니다."))
