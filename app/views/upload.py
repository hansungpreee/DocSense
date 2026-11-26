"""업로드 화면: 「분류」(파일 1개든 여러 개든 같은 방식)와 「분류 결과」 (FR-01, FR-02)"""
from pathlib import Path

import pandas as pd
import streamlit as st

import doclist
import evidence
import services
from i18n import t
from loading import loading

store = st.session_state.store  # services.open_store()가 만든 저장소
emp = st.session_state.user["id"]
TABS = ["분류", "분류 결과"]

st.session_state.setdefault("up_tab", TABS[0])
if st.session_state.pop("up_goto", None):  # 분류가 끝나면 결과 탭으로 옮긴다 (위젯을 만들기 전에만 값을 바꿀 수 있다)
    st.session_state.up_tab = TABS[1]

st.title(t("문서 업로드"))
tab = st.segmented_control(t("업로드 메뉴"), TABS, key="up_tab", format_func=t, label_visibility="collapsed") or TABS[0]

new_ids = st.session_state.pop("up_new", None)
if new_ids:  # 방금 분류가 끝났다: 근거 사진이 있는 결과 팝업을 먼저 보여 준다
    evidence.open_results(new_ids)


def keep_suffix(new: str, old: str) -> str:
    """확장자를 지우면 형식을 알 수 없으므로, 새 이름에 원래 확장자가 없으면 붙여 준다."""
    return new if Path(new).suffix.lower() == Path(old).suffix.lower() else new + Path(old).suffix


def ask_rename(files, names: list[str], taken: set[str]):
    """이름이 겹치는 파일의 새 이름을 묻는 팝업. 확인하면 up_names에 담고 분류를 시작한다."""
    bad = services.name_conflicts(names, taken)

    def start(renamed: dict[str, str] | None):
        st.session_state.up_names = renamed or {}
        st.session_state.up_start = True
        st.rerun()

    def body():
        st.caption(t("이미 분류한 문서나 이번에 올린 다른 파일과 이름이 같습니다. 새 이름을 정해 주세요."))
        used = set(taken) | {n for i, n in enumerate(names) if i not in bad}
        wanted, names_by_id = {}, {}
        for i in bad:
            suggestion = services.suggest_name(names[i], used)
            used.add(suggestion)
            wanted[files[i].file_id] = st.text_input(t("「{n}」의 새 이름", n=names[i]), value=suggestion, key=f"rn_{files[i].file_id}")
            names_by_id[files[i].file_id] = names[i]
        left, right = st.columns(2)
        if left.button(t("이 이름으로 분류"), type="primary", width="stretch"):
            fixed = {k: keep_suffix(v.strip(), names_by_id[k]) for k, v in wanted.items()}
            final = [fixed.get(f.file_id, n) for f, n in zip(files, names)]
            if all(Path(x).stem for x in final) and not services.name_conflicts(final, taken):
                start(fixed)
            st.error(t("이름이 비었거나 아직 겹칩니다: {n}", n=", ".join(final[i] for i in bad)))
        if right.button(t("이름 그대로 분류"), width="stretch"):
            start({})

    st.dialog(t("파일 이름이 겹칩니다"), width="medium")(body)()


def run(f, name: str, on_wait=None) -> int:
    path, digest = services.save_upload(name, f.getvalue())
    return store.save_result(services.classify(path, digest, store, on_wait))


if tab == TABS[0]:
    st.caption(t("PNG, JPG, PDF, TXT, CSV, DOC, DOCX 문서를 올리면 대분류와 소분류를 판별합니다. 한 개든 여러 개든 한 번에 올릴 수 있습니다."))
    files = st.file_uploader(t("문서"), type=services.SUPPORTED, accept_multiple_files=True, key="up_files",
                             label_visibility="collapsed")
    done = st.session_state.setdefault("up_done", {})  # 이미 끝난 파일 {file_id: 결과 ID}: 중단 뒤 이어서 할 때 건너뛴다
    if st.session_state.pop("up_running", False):  # 분류 도중 다른 버튼(중단 등)이 눌려 스크립트가 끊긴 채 다시 그려졌다
        st.session_state.up_stopped = True
    todo = [f for f in files if f.file_id not in done]  # 중단 뒤에는 남은 파일만
    if todo:
        files = todo
        if st.session_state.pop("up_stopped", False):
            btn = t("이어서 분류하기")
            st.warning(t("분류를 중단했습니다. {n}건은 이미 저장됐습니다. 「{b}」를 누르면 남은 문서부터 다시 시작합니다.", n=len(done), b=btn))
        if not services.is_mock():
            minutes = len(files) * services.MIN_INTERVAL / 60
            st.caption(t("호출 한도 보호를 위해 문서 사이에 {s:g}초씩 간격을 둡니다 (최소 약 {m:.1f}분).", s=services.MIN_INTERVAL, m=minutes))
        go = st.button(t("이어서 분류하기") if done else t("분류하기"), type="primary")
        names = [f.name for f in files]
        taken = {r["file"] for r in store.list_history()}
        if go and services.name_conflicts(names, taken):
            ask_rename(files, names, taken)  # 이름을 정하고 나면 팝업이 up_start를 켜고 다시 그린다
            go = False
        if st.session_state.pop("up_start", False):
            go = True
        if go:
            renamed = st.session_state.pop("up_names", {})
            st.caption(t("오래 걸리면 「✕ 중단」을 눌러 멈추고 다시 시작할 수 있습니다. 이미 끝난 문서는 저장됩니다. (지금 처리 중인 1건은 끝난 뒤 멈춥니다)"))
            st.button(t("✕ 중단"), key="up_stop")  # 누르면 스크립트가 다시 실행되며 아래 반복이 끊긴다
            st.session_state.up_running = True
            total = len(files) + len(done)
            single = total == 1  # 1건은 문서 전송 애니메이션, 여러 건은 진행 막대 (팀 결정: 일괄은 막대 유지)
            bar = None if single else st.progress(0.0, text=t("분류 중..."))
            for f in files:
                # 한 건이 실패해도 오류 결과로 남기고 다음 건을 계속 처리. 429로 기다리는 동안은 애니메이션·진행 막대 문구로 알린다
                name = renamed.get(f.file_id, f.name)
                if single:
                    with loading() as on_wait:
                        done[f.file_id] = run(f, name, on_wait)
                    continue
                done[f.file_id] = run(f, name, lambda msg: bar.progress(len(done) / total, text=f"{msg} · {f.name}"))
                bar.progress(len(done) / total, text=t("{i}/{n} 완료", i=len(done), n=total))
            st.session_state.up_running = False
            st.session_state.up_new = list(done.values())  # 결과 팝업에서 이 순서대로 한 건씩 본다
            done.clear()
            st.session_state.up_goto = True
            st.rerun()
else:
    results = store.list_history()  # 저장된 이력 전체 (서버를 다시 켜도 남아 있고, 방금 분류한 문서가 맨 위에 온다)
    if not results:
        st.info(t("아직 분류한 문서가 없습니다. 「분류」에서 문서를 올려 주세요."))
        st.stop()
    errors = sum(r.get("status") == "error" for r in results)
    if errors:
        st.warning(t("{n}건 중 {e}건이 실패했습니다. 해당 문서의 「분류 근거」에서 원인을 확인하세요.", n=len(results), e=errors))

    doclist.show(results, "up")

    df = pd.DataFrame([services.result_row(r) for r in results])
    st.download_button(t("CSV 내려받기"), df.to_csv(index=False).encode("utf-8-sig"),  # 엑셀에서 한글이 깨지지 않도록 BOM 포함
                       file_name="분류결과.csv", mime="text/csv")
