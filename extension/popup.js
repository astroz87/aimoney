// popup.js — 활성 탭에서 content.js 의 collectSource() 를 실행하고 서버로 전송한다.

const $ = (id) => document.getElementById(id);

// 저장된 서버 주소 복원
chrome.storage.sync.get(["server", "category"], (v) => {
  if (v.server) $("server").value = v.server;
  if (v.category) $("category").value = v.category;
});

function setStatus(msg, cls) {
  const el = $("status");
  el.textContent = msg;
  el.className = cls || "";
}

$("send").addEventListener("click", async () => {
  const server = $("server").value.replace(/\/+$/, "");
  const category = $("category").value.trim();
  chrome.storage.sync.set({ server, category });
  setStatus("페이지에서 수집 중...");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });
    const payload = results[0]?.result;
    if (!payload) throw new Error("수집 실패 (페이지 접근 불가)");
    if (category) payload.category = category;

    setStatus("전송 중...");
    const res = await fetch(`${server}/api/import-source`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    const proj = await res.json();
    setStatus(`✓ 생성됨: ${proj.id} (영상후보 ${payload.video_candidates.length}개)`, "ok");
  } catch (e) {
    setStatus("실패: " + e.message, "err");
  }
});
