"""분류 근거 화면(팝업): 원본 + 근거 박스, 분류 결과, 판단 근거 (FR-04, FR-06, FR-07). 업로드·이력 화면이 같이 쓴다."""
from pathlib import Path

import streamlit as st

import services
from i18n import lang, t
from loading import loading

# 분류 실패 화면 그림: 종이가 서류철에 들어가지 못하고 걸려 있는 모습 (429 대기 화면의 서류철과 같은 그림을 2.2배로 가운데에 둔다).
# 오류 원인은 429만이 아니므로 그림 옆 문구는 일반적으로 쓰고, 원인은 아래 오류 박스가 알린다. 빈 줄·들여쓰기 없이 쓴다.
FAIL_HTML = """<style>
.failfile{display:flex;flex-direction:column;align-items:center;gap:14px;padding:10px 0 18px;color:inherit}
.failfile .file{position:relative;width:84px;height:100px;flex:none;zoom:2.2}
.failfile b{font-size:22px}
.failfile .back{position:absolute;left:0;bottom:0;width:84px;height:52px;border:2px solid #6f87b8;
border-radius:4px 6px 6px 6px;background:#cfd9ee;box-sizing:border-box}
.failfile .back::before{content:"";position:absolute;left:-2px;top:-10px;width:28px;height:10px;
border:2px solid #6f87b8;border-bottom:0;border-radius:4px 4px 0 0;background:#cfd9ee;box-sizing:border-box}
.failfile .sheet{position:absolute;left:20px;bottom:8px;width:44px;height:50px;box-sizing:border-box;
border:1px solid #aab4c6;border-radius:2px;background:repeating-linear-gradient(#fff 0 7px,#d9deea 7px 8px);
box-shadow:0 1px 2px rgba(0,0,0,.2);transform:translateY(-34px) rotate(10deg);
animation:failbump 2.4s ease-in-out infinite}
.failfile .front{position:absolute;left:0;bottom:0;width:84px;height:32px;border:2px solid #6f87b8;
border-radius:3px 3px 6px 6px;background:#e4eaf6;box-sizing:border-box}
.failfile .mark{position:absolute;right:-6px;top:0;width:22px;height:22px;border-radius:50%;background:#d6453d;
color:#fff;font:700 14px/22px sans-serif;text-align:center}
@keyframes failbump{0%,55%,100%{transform:translateY(-34px) rotate(10deg)}
70%{transform:translateY(-22px) rotate(4deg)}82%{transform:translateY(-30px) rotate(8deg)}}
@media (prefers-reduced-motion:reduce){.failfile .sheet{animation:none}}
</style>
<div class="failfile"><div class="file"><div class="back"></div><div class="sheet"></div><div class="front"></div>
<div class="mark" aria-hidden="true">!</div></div><b>__FAIL__</b></div>"""



CROSS_REASONS = {  # 미확정 사유 (합산 결과의 reason 값)
    "disagree": "Gemini와 Qwen의 분류가 서로 다릅니다.",
    "low_confidence": "Gemini의 확신도가 기준({th}) 미만입니다.",
    "gemini_unavailable": "Gemini를 쓸 수 없어 Qwen 결과만 있습니다.",
    "qwen_unavailable": "Qwen을 쓸 수 없어 Gemini 결과만 있습니다.",
    "etc": "두 모델 모두 기존 분류 체계에 없는 문서(「기타」)로 판단했습니다.",
}
GRADE_COLORS = {"기밀": "red", "대외비": "orange", "사내한정": "blue", "공개": "green", "미산정": "gray"}  # 색만으로 구분하지 않게 글자도 같이 쓴다


def cross_check(cc: dict | None):
    """Gemini+Qwen 교차 확인 결과: 확정이면 안심 문구, 미확정이면 담당자 확인이 필요하다는 경고와 사유, Gemini의 분류를 나란히 보여 준다."""
    if not cc:
        return  # 합산 결과가 없는 문서는 아무것도 보여 주지 않는다
    gem = cc.get("gemini") or {}
    item = services.taxonomy().get(gem.get("minor_code") or "")  # Gemini가 「기타」로 봤으면 minor_code는 ETC-00 → 「기타」로 보인다
    if cc.get("confirmed"):
        st.success(t("확정 — Gemini와 Qwen이 같은 분류로 판단했습니다."))
    else:
        why = t(CROSS_REASONS.get(cc.get("reason"), "두 모델의 결과가 일치하지 않습니다."), th=cc.get("threshold", "-"))  # 기준값은 결과가 담아 준다(화면에 하드코딩하지 않음)
        st.warning(t("미확정 — 담당자 확인이 필요합니다. {why}", why=why))
    if item:
        st.caption(t("Gemini 판단: {n} ({c}) · 확신도 {p:.0%}", n=t(item.name), c=item.code, p=float(gem.get("confidence") or 0)))


def security_grade(r: dict):
    """보안 등급 표시(표시 전용: 마스킹·전송 차단은 하지 않는다). 「기타」는 등급 없이 담당자 확인 안내, 미확정·미산정은 잠정 표시."""
    info = services.grade_info(r)
    if not info:
        return
    if info["etc"]:
        st.info(t("분류 체계 밖 문서, 담당자 확인 필요"))
        st.caption(t("확인 전까지 {g} 이상으로 취급합니다.", g=t(info["handling"])))
        return
    st.caption(t("보안 등급"))
    label = t(info["grade"]) + (t(" (잠정)") if info["provisional"] else "")
    st.badge(label, color=GRADE_COLORS.get(info["grade"], "gray"))
    if info["provisional"]:
        st.caption(t("분류가 확정되기 전까지 {g} 이상으로 취급합니다.", g=t(info["handling"])))
    if info["basis"]:
        st.caption(t("등급 근거: {b}", b=services.plain(info["basis"])))


def show(r: dict, store):
    """분류 결과 한 건의 근거를 그린다. 오류 결과는 실패 안내와 「다시 시도」를 보여 준다."""
    if r.get("status") == "error":
        st.markdown(FAIL_HTML.replace("__FAIL__", t("문서를 분류하지 못했습니다")), unsafe_allow_html=True)
        retry = f" (형식 오류로 재요청 {r['retries']}회 후 실패)" if r.get("retries") else ""  # 오류 원인 문구는 번역하지 않는다
        st.error(f"{t('분류에 실패했습니다')}{retry}: " + " / ".join(services.plain(e) for e in r.get("errors", [])))
        st.caption(t("파일: {f}", f=services.plain(r.get("file"))))
        if st.button(t("다시 시도"), type="primary"):  # 올린 파일을 그대로 다시 분류한다. 새 결과가 이력에 하나 더 쌓인다
            with loading() as on_wait:
                store.save_result(services.classify(Path(r["path"]), r["file_hash"], store, on_wait))
            st.rerun()
        return

    left, right = st.columns([3, 2], gap="large")
    with left:
        pages = services.load_preview_pages(r["path"])
        page = st.radio(t("페이지"), range(1, len(pages) + 1), horizontal=True) if len(pages) > 1 else 1
        show_box = st.toggle(t("근거 영역 표시"), value=True)
        img = pages[page - 1]
        if show_box:
            img = services.draw_evidence(img, r.get("evidence", []), page=page)
        st.image(img, caption=r["file"], width="stretch")

    with right:
        major, code, name = services.shown(r)
        etc = r.get("status") == "pending_review"
        if etc and (r.get("new_class") or {}).get("trigger") == "low_confidence":
            st.warning(t("확신도가 기준보다 낮아 「기타」로 분류했습니다."))
        elif etc:
            st.warning(t("기존 분류 체계에 없는 문서로 판단되어 「기타」로 분류했습니다."))
        st.metric(t("대분류"), t(major))
        st.metric(t("소분류"), f"{t(name)}  ({code})")
        st.progress(float(r["confidence"]), text=t("확신도 {c:.0%}", c=float(r["confidence"])))

        cross_check(r.get("cross_check"))
        security_grade(r)

        st.subheader(t("판단 근거"))  # 모델이 쓴 글은 plain()으로 마크다운 기호를 무력화해 그대로 보여 준다
        if lang() == "en":  # ponytail: 근거는 번역하지 않고 안내만 한다; 영어 근거가 필요해지면 프롬프트 언어 지시(백엔드 1)를 검토
            st.caption(t("판단 근거는 모델이 쓴 원문(한국어)을 그대로 보여 줍니다."))
        for reason in r.get("reasons", []):
            st.markdown(f"- {services.plain(reason)}")

        if etc and (r.get("new_class") or {}).get("proposed_name"):
            st.caption(f"참고: 모델이 본 문서 종류는 '{services.plain(r['new_class']['proposed_name'])}'에 가깝습니다.")

        cached = " · 이전 결과 재사용 (API 미호출)" if r.get("cached") else ""
        st.caption(f"모델 {r.get('model')} · 프롬프트 {r.get('prompt_version')} · {r.get('latency_ms')}ms{cached}")


def open_dialog(result_id: int):
    """문서 1건의 분류 근거 팝업 (목록의 「분류 근거 보기」). 제목을 현재 언어로 쓰려고 호출할 때 dialog를 씌운다."""
    def body():
        store = st.session_state.store
        show(store.get(result_id), store)
    st.dialog(t("분류 근거"), width="large")(body)()


def open_results(ids: list[int]):
    """방금 분류한 문서들의 결과 팝업. 근거 사진을 먼저 보여 주고, 문서가 여러 개면 ◀ ▶ 로 한 건씩 넘겨 본다.
    X나 팝업 바깥을 눌러야 닫힌다 (버튼은 팝업 안에서만 다시 그려진다)."""
    st.session_state.ev_idx = 0

    def prev_next(step: int):
        st.session_state.ev_idx = min(max(st.session_state.ev_idx + step, 0), len(ids) - 1)

    def body():
        store = st.session_state.store
        i = st.session_state.ev_idx
        left, mid, right = st.columns([1, 3, 1], vertical_alignment="center")
        if len(ids) > 1:
            left.button(t("◀ 이전"), on_click=prev_next, args=(-1,), disabled=i == 0, key="ev_prev", width="stretch")
            right.button(t("다음 ▶"), on_click=prev_next, args=(1,), disabled=i == len(ids) - 1, key="ev_next", width="stretch")
        r = store.get(ids[i])
        mid.markdown(f"**{i + 1} / {len(ids)}** · {services.plain(r.get('file'))}")
        show(r, store)

    st.dialog(t("분류 결과"), width="large")(body)()
