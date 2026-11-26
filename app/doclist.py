"""분류한 문서 목록: 정렬(최신순/중요도순), 파일명 · 분류 · 별 · 「분류 근거 보기」. 업로드 결과·이력·대시보드가 같이 쓴다."""
import streamlit as st

import evidence
import services
from i18n import t


def show(results: list[dict], key: str):
    """results를 한 줄씩 나열한다. key는 화면마다 달라야 한다 (위젯 키 충돌 방지)."""
    emp = st.session_state.user["id"]
    stars = services.starred(emp)
    ORDERS = ["최신순", "중요도순"]
    order = st.segmented_control(t("정렬"), ORDERS, default=ORDERS[0], key=f"{key}_sort", format_func=t) or ORDERS[0]
    rows = sorted(results, key=lambda r: -r["id"])  # 최신순 (ID가 클수록 나중에 분류한 것)
    if order == "중요도순":
        rows = sorted(rows, key=lambda r: r["id"] not in stars)  # 별 붙인 문서가 위로, 같은 무리 안에서는 최신순 그대로

    widths = [3.6, 2, 3, 1.2, 1.2, 0.7, 1.7]
    for col, name in zip(st.columns(widths), ["파일명", "대분류", "소분류", "확신도", "교차 확인", "중요", ""]):
        col.markdown(f"**{t(name)}**")
    for r in rows:
        major, _, name = services.shown(r)
        failed = r.get("status") == "error"
        c = st.columns(widths, vertical_alignment="center")
        c[0].write(services.plain(r.get("file")))
        c[1].write(t(major) if major else "-")
        c[2].write(t("분류 실패") if failed else t(name))
        c[3].write("-" if failed else f"{r['confidence']:.0%}")
        c[4].write(t(services.cross_label(r)) if services.cross_label(r) else "-")  # 합산 결과가 없으면 -
        on = r["id"] in stars
        c[5].button("★" if on else "☆", key=f"{key}_star_{r['id']}", type="tertiary", on_click=services.toggle_star,
                    args=(emp, r["id"]), help=t("중요 표시 취소") if on else t("중요 표시"))
        if c[6].button(t("분류 근거 보기"), key=f"{key}_ev_{r['id']}", width="stretch"):
            evidence.open_dialog(r["id"])
