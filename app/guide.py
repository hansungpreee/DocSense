"""프로그램 설명 팝업: 사이드바 왼쪽 아래의 ? 버튼으로 연다."""
import streamlit as st

import services
from i18n import t


def open_dialog():
    st.dialog(t("프로그램 설명"), width="large")(_body)()


def _body():
    st.markdown(f"#### {t('한성부기들의 서류 정리방')}: {t('문서를 올리면, 어떤 문서인지 알려 줍니다')}")
    st.caption(t("스캔본·사진·PDF를 AI가 직접 보고 대분류와 소분류를 고릅니다. 판단한 근거도 함께 보여 줍니다."))

    c1, c2, c3 = st.columns(3)
    c1.markdown(t("**① 올리기**  \n문서를 한 개든 여러 개든 올립니다."))
    c2.markdown(t("**② 분류하기**  \n버튼을 누르면 대분류·소분류가 정해집니다."))
    c3.markdown(t("**③ 근거 보기**  \n문서 위에 판단 근거가 표시됩니다."))

    st.divider()
    st.markdown(f"#### {t('메뉴')}")
    st.markdown(t("""| 메뉴 | 할 수 있는 일 |
| --- | --- |
| 대시보드 | 대분류 맵을 보고, 원을 눌러 그 대분류의 내 문서를 봅니다 |
| 업로드 | 문서를 올려 분류하고, 결과에서 「분류 근거」를 봅니다 |
| 이력 | 내가 분류한 문서 기록을 찾아봅니다 |
| 보안 현황 | 기간을 골라 보안 등급별·대분류별 건수를 보고 CSV로 내려받습니다 |
| 문서 양식 | 회사 문서 양식을 대분류별로 내려받습니다 |
| 설정 | 글자 크기·언어·사용 방법 안내를 바꿉니다 |"""))

    st.markdown(f"#### {t('알아 두세요')}")
    st.markdown(t("""- 분류 체계에 없거나 확신이 낮은 문서는 **「기타」** 로 분류됩니다.
- **확신도**가 낮을수록 사람이 한 번 더 확인하는 것이 좋습니다.
- 분류 이력은 **내 계정에만** 저장되고 다른 사원에게 보이지 않습니다."""))

    tax = services.taxonomy()
    with st.expander(t("분류 체계 보기")):
        st.caption(f"대분류 {len(services.all_majors())}개 · 소분류 {len(tax.classifiable_items)}개 + 기타")
        rows = "\n".join(f"| {t(m)} | {', '.join(t(i.name) for i in tax.classifiable_items if i.major == m)} |"
                         for m in services.all_majors())  # 표(st.dataframe)는 색을 못 바꿔서 마크다운 표로 쓴다
        st.markdown(f"| {t('대분류')} | {t('소분류')} |\n| --- | --- |\n{rows}")
    with st.expander(t("HS리테일은 어떤 회사인가요?")):
        st.markdown("""
| 항목 | 내용 |
| --- | --- |
| 업종 | 제과·음료 B2B 도매 유통, PB 상품, 카페 프랜차이즈(HS커피) |
| 규모 | 연 매출 약 450억 원, 임직원 약 120명 |
| 소재지 | 본사 서울 송파구, 물류센터 경기 용인 |
| 거래처 | 대형 마트 체인, PB 제조 공장, 가맹점, 건물 임대인 |
""")
        st.caption(t("HS리테일은 이 프로젝트를 위해 설정한 가상의 회사입니다. 사번·문서·거래처는 모두 가상입니다."))
