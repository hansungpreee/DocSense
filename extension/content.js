// ChatGPT(chatgpt.com) 파일 업로드를 가로채 로컬 DocSense 서버로 검사한다 (시연용 시제품).
// 범위: 파일 선택(input[type=file])과 드래그 놓기만. 텍스트·클립보드 붙여넣기, 다른 사이트·브라우저는 막지 못한다.
// 동작: 서버가 준 action 그대로 — block(기밀: 사유 체크 후에만 업로드), confirm(대외비·「기타」·미확정: 확인 창),
//       pass(사내한정·공개: 등급만 잠깐 표시), error(검사 실패: 취소가 기본인 확인 창).
// ponytail: ChatGPT 화면 구조에 기대지 않고 window 캡처 단계에서 이벤트를 멈췄다 다시 보낸다.
//           ChatGPT가 다른 경로(붙여넣기 등)로 파일을 받게 바뀌면 그 경로는 검사되지 않는다.
(() => {
  const ours = new WeakSet(); // 우리가 다시 보낸 이벤트는 통과시킨다
  const GRADE_COLOR = { 기밀: "#b3261e", 대외비: "#b25e00", 사내한정: "#1f5fa8", 공개: "#2e7d32" };

  // 파일 선택 ------------------------------------------------------------
  const pendingInputs = new WeakSet();
  const onFileInput = (e) => {
    const input = e.target;
    if (ours.has(e) || !(input instanceof HTMLInputElement) || input.type !== "file" || !input.files?.length) return;
    e.stopImmediatePropagation();
    if (e.type !== "change" || pendingInputs.has(input)) return; // input·change 둘 다 오므로 change에서 한 번만 검사
    pendingInputs.add(input);
    const files = [...input.files];
    input.value = ""; // 검사하는 동안 페이지가 input.files를 직접 읽어도(포커스 복귀 등) 파일이 보이지 않게 비운다
    review(files).then((allowed) => {
      pendingInputs.delete(input);
      if (!allowed.length) {
        input.value = "";
        return;
      }
      const dt = new DataTransfer();
      allowed.forEach((f) => dt.items.add(f));
      input.files = dt.files;
      for (const type of ["input", "change"]) {
        const ev = new Event(type, { bubbles: true });
        ours.add(ev);
        input.dispatchEvent(ev);
      }
    });
  };
  window.addEventListener("input", onFileInput, true);
  window.addEventListener("change", onFileInput, true);

  // 드래그 놓기 ----------------------------------------------------------
  // ChatGPT는 dragenter에서 「무엇이든 추가하세요」 오버레이를 띄우고 drop·dragleave에서 닫는다.
  // drop을 멈추면 오버레이가 남으므로, 멈춘 즉시 dragleave를 보내고 검사 뒤에는 취소해도 빈 drop을 보내 상태를 닫는다.
  const fire = (target, type, files, { clientX, clientY }) => {
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    const ev = new DragEvent(type, { bubbles: true, cancelable: true, composed: true, dataTransfer: dt, clientX, clientY });
    ours.add(ev);
    (target.isConnected ? target : document.body).dispatchEvent(ev);
  };
  window.addEventListener("drop", (e) => {
    if (ours.has(e) || !e.dataTransfer?.files?.length) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const target = e.target;
    const pos = { clientX: e.clientX, clientY: e.clientY };
    fire(target, "dragleave", [], pos);
    review([...e.dataTransfer.files]).then((allowed) => fire(target, "drop", allowed, pos)); // 모두 취소면 빈 drop
  }, true);

  // 검사 -----------------------------------------------------------------
  async function review(files) {
    const allowed = [];
    for (const file of files) {
      const busy = showBusy(file.name);
      const result = await check(file);
      busy.remove();
      if (result.action === "pass") {
        toast(`${result.handling_grade} · ${result.minor_name}${result.cached ? " (기존 검사 결과 사용)" : ""} — 업로드합니다`,
          GRADE_COLOR[result.handling_grade]);
        allowed.push(file);
        continue;
      }
      const choice = await ask(file, result);
      try { // 기록 실패(확장을 다시 읽어 들인 뒤 새로 고침하지 않은 탭 등)해도 사용자의 선택대로 업로드 판단은 계속한다
        chrome.runtime.sendMessage({ type: "decision", file: file.name, grade: result.handling_grade || "검사 실패", choice });
      } catch (err) {
        toast("확장이 갱신되어 선택이 기록되지 않았습니다. 페이지를 새로 고침하세요.", "#555");
      }
      if (choice === "upload") allowed.push(file);
    }
    return allowed;
  }

  function check(file) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          chrome.runtime.sendMessage({ type: "check", name: file.name, dataUrl: reader.result }, (r) => {
            resolve(r || { action: "error", message: chrome.runtime.lastError?.message || "확장 내부 오류입니다." });
          });
        } catch (err) { // 확장을 다시 읽어 들인 뒤 새로 고침하지 않은 탭
          resolve({ action: "error", message: "확장이 갱신되었습니다. 페이지를 새로 고침하세요." });
        }
      };
      reader.onerror = () => resolve({ action: "error", message: "파일을 읽지 못했습니다." });
      reader.readAsDataURL(file);
    });
  }

  // 화면 (Shadow DOM으로 ChatGPT 스타일과 분리) -------------------------------
  const CSS = `
    .back{position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;
          z-index:2147483647;font:15px/1.5 system-ui,"Malgun Gothic",sans-serif}
    .box{background:#fff;color:#1b1b1b;border-radius:12px;max-width:440px;width:calc(100% - 32px);padding:20px 22px;
         box-shadow:0 10px 30px rgba(0,0,0,.3);border-top:6px solid var(--c)}
    h2{margin:0 0 10px;font-size:18px;color:var(--c)}
    .badge{display:inline-block;background:var(--c);color:#fff;border-radius:6px;padding:1px 8px;font-weight:600}
    dl{margin:10px 0;display:grid;grid-template-columns:auto 1fr;gap:4px 12px}
    dt{color:#555}dd{margin:0;word-break:break-all}
    label{display:flex;gap:8px;align-items:flex-start;margin:12px 0}
    .btns{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
    button{font:inherit;border-radius:8px;padding:7px 14px;border:1px solid #888;background:#fff;cursor:pointer}
    button.primary{background:#1b1b1b;color:#fff;border-color:#1b1b1b}
    button:disabled{opacity:.4;cursor:not-allowed}
    button:focus-visible,input:focus-visible{outline:3px solid #1f5fa8;outline-offset:2px}
    .note{color:#666;font-size:12px;margin-top:12px}
    .toast{position:fixed;right:20px;bottom:20px;background:var(--c);color:#fff;border-radius:8px;padding:10px 14px;
           z-index:2147483647;font:14px system-ui,"Malgun Gothic",sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.25)}`;

  function mount(html, color) {
    const host = document.createElement("div");
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${CSS}</style>${html}`;
    root.firstElementChild.nextElementSibling.style.setProperty("--c", color || "#444");
    document.documentElement.appendChild(host);
    return { host, root, remove: () => host.remove() };
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

  function showBusy(name) {
    return mount(`<div class="back" role="status" aria-live="polite"><div class="box">
      <h2>DocSense 검사 중…</h2><div>${esc(name)}</div><div class="note">보안 등급을 확인하고 있습니다. 처음 보는 파일은 10~20초 걸립니다.</div></div></div>`);
  }

  function toast(text, color) {
    setTimeout(mount(`<div class="toast" role="status">${esc(text)}</div>`, color).remove, 3000);
  }

  function ask(file, r) {
    const failed = r.action === "error";
    const block = r.action === "block";
    const grade = r.handling_grade;
    const title = failed ? "검사하지 못했습니다" : block ? "기밀 문서입니다" : `${grade} 문서입니다`;
    const rows = failed
      ? `<dt>파일</dt><dd>${esc(file.name)}</dd><dt>사유</dt><dd>${esc(r.message)}</dd>`
      : `<dt>파일</dt><dd>${esc(file.name)}</dd>
         <dt>분류</dt><dd>${esc(r.minor_code ? `${r.minor_code} ${r.minor_name}` : r.minor_name)}</dd>
         <dt>등급</dt><dd><span class="badge">${esc(grade)}</span>${r.provisional ? " (잠정)" : ""}</dd>
         <dt>근거</dt><dd>${esc(r.grade_basis)}</dd>
         ${r.cached ? "<dt>검사</dt><dd>기존 검사 결과 사용 (같은 파일, 등급은 현재 등급표 기준)</dd>" : ""}`;
    const lead = failed
      ? "보안 등급을 확인하지 못했습니다. 외부 AI에 올려도 되는 문서인지 직접 확인하세요."
      : block ? "외부 AI(ChatGPT)에 올리면 안 되는 문서로 분류되었습니다."
        : "외부 AI(ChatGPT)에 올리기 전에 확인이 필요합니다.";
    const ui = mount(`<div class="back"><div class="box" role="alertdialog" aria-modal="true" aria-labelledby="t" aria-describedby="d">
      <h2 id="t">${esc(title)}</h2><div id="d">${esc(lead)}</div><dl>${rows}</dl>
      ${block ? `<label><input type="checkbox" id="ok"> 업무상 반드시 필요하며 책임자 승인을 받았습니다</label>` : ""}
      <div class="btns"><button id="up">그래도 업로드</button><button id="no" class="primary">취소</button></div>
      <div class="note">DocSense 시연용 경고입니다. 텍스트 붙여넣기나 다른 사이트는 검사하지 않습니다.</div>
    </div></div>`, failed ? "#444" : GRADE_COLOR[grade]);
    const $ = (s) => ui.root.querySelector(s);
    if (block) {
      $("#up").disabled = true;
      $("#ok").addEventListener("change", (e) => ($("#up").disabled = !e.target.checked));
    }
    $("#no").focus();
    return new Promise((resolve) => {
      const done = (choice) => { ui.remove(); resolve(choice); };
      $("#up").addEventListener("click", () => done("upload"));
      $("#no").addEventListener("click", () => done("cancel"));
      ui.root.addEventListener("keydown", (e) => {
        if (e.key === "Escape") done("cancel");
        if (e.key === "Tab") { // 대화 상자 안에서만 초점 이동
          const items = [...ui.root.querySelectorAll("input,button:not(:disabled)")];
          const i = items.indexOf(ui.root.activeElement);
          const next = items[(i + (e.shiftKey ? -1 : 1) + items.length) % items.length];
          e.preventDefault();
          next.focus();
        }
      });
    });
  }
})();
