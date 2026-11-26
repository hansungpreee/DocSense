// 로컬 검사 서버 호출은 여기(서비스 워커)에서만 한다.
// 콘텐츠 스크립트에서 부르면 chatgpt.com 출처로 나가 CORS·크롬 사설망 접근 차단에 걸린다.
const SERVER = "http://127.0.0.1:8765";
const TIMEOUT_MS = 60000;

async function call(path, init) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const resp = await fetch(SERVER + path, { ...init, signal: ctrl.signal });
    return await resp.json();
  } catch (e) {
    const message = e.name === "AbortError"
      ? "검사 시간이 60초를 넘었습니다."
      : "검사 서버에 연결하지 못했습니다. 서버가 켜져 있는지 확인하세요.";
    return { status: "error", action: "error", message };
  } finally {
    clearTimeout(timer);
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type === "check") {
    // 메시지는 JSON만 오가므로 파일은 data URL로 받아 다시 바이트로 바꾼다
    fetch(msg.dataUrl)
      .then((r) => r.blob())
      .then((blob) => call("/check", { method: "POST", headers: { "X-Filename": encodeURIComponent(msg.name) }, body: blob }))
      .then(reply);
    return true; // 비동기 응답
  }
  if (msg.type === "decision") {
    call("/decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: msg.file, grade: msg.grade, choice: msg.choice }),
    }).then(reply);
    return true;
  }
});
