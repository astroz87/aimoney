// 공통 fetch 헬퍼
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`${res.status}: ${t}`);
  }
  return res.status === 204 ? null : res.json();
}

function pid() {
  const root = document.getElementById("project-root");
  return root ? root.dataset.pid : null;
}

// --- 대시보드: 새 프로젝트 ---
async function createProject(ev) {
  ev.preventDefault();
  const f = ev.target;
  const payload = {
    product_ko: f.product_ko.value,
    product_zh: f.product_zh.value,
    category: f.category.value,
    source_site: f.source_site.value,
    source_url: f.source_url.value,
  };
  try {
    const p = await api("POST", "/api/projects", payload);
    location.href = `/projects/${p.id}`;
  } catch (e) { alert("생성 실패: " + e.message); }
  return false;
}

// --- 프로젝트 상세 ---
async function updateUsage(value) {
  try { await api("PATCH", `/api/projects/${pid()}`, { usage_status: value }); }
  catch (e) { alert(e.message); }
}

async function genSearchQueries() {
  setJob("검색어 생성 중...", "running");
  try {
    const r = await api("POST", `/api/projects/${pid()}/search-queries`, {});
    const box = document.getElementById("search-queries");
    box.innerHTML = "<ul>" + (r.search_queries || []).map(q => `<li class="mono">${q}</li>`).join("") + "</ul>";
    setJob("검색어 생성 완료", "done");
  } catch (e) { setJob("실패: " + e.message, "failed"); }
}

async function uploadVideos(files) {
  if (!files.length) return;
  setJob(`영상 ${files.length}개 업로드 중...`, "running");
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  try {
    const res = await fetch(`/api/projects/${pid()}/assets/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    setJob("업로드 완료 — 새로고침", "done");
    setTimeout(() => location.reload(), 800);
  } catch (e) { setJob("업로드 실패: " + e.message, "failed"); }
}

async function runScript() {
  setJob("대본 생성 중...", "running");
  try {
    await api("POST", `/api/projects/${pid()}/script`, {});
    setJob("대본 생성 완료 — 새로고침", "done");
    setTimeout(() => location.reload(), 800);
  } catch (e) { setJob("실패: " + e.message, "failed"); }
}

async function runTimeline() {
  setJob("타임라인 매칭 중...", "running");
  try {
    await api("POST", `/api/projects/${pid()}/timeline`, {});
    setJob("타임라인 완료", "done");
  } catch (e) { setJob("실패: " + e.message, "failed"); }
}

// 비동기 잡(analyze/tts/render/package) 실행 + 폴링
async function runJob(kind) {
  setJob(`${kind} 시작...`, "running");
  try {
    const r = await api("POST", `/api/projects/${pid()}/${kind}`, {});
    await pollJob(r.job_id, kind);
  } catch (e) { setJob(`${kind} 실패: ` + e.message, "failed", () => runJob(kind)); }
}

async function pollJob(jobId, kind) {
  for (let i = 0; i < 600; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const j = await api("GET", `/api/jobs/${jobId}`);
    setJob(`${kind}: ${j.status} (${j.progress}%) ${j.log || ""}`, j.status === "failed" ? "failed" : "running");
    if (j.status === "done") { setJob(`${kind} 완료 — 새로고침`, "done"); setTimeout(() => location.reload(), 800); return; }
    if (j.status === "failed") { setJob(`${kind} 실패: ${j.log}`, "failed", () => runJob(kind)); return; }
  }
}

// 실패 시 retryFn 을 넘기면 "재시도" 버튼이 함께 표시된다
function setJob(msg, cls, retryFn) {
  const el = document.getElementById("job-status");
  if (!el) return;
  el.textContent = msg;
  el.className = "job-status " + (cls || "");
  if (retryFn) {
    const b = document.createElement("button");
    b.className = "btn small";
    b.textContent = "재시도";
    b.style.marginLeft = "8px";
    b.onclick = retryFn;
    el.appendChild(b);
  }
}

// --- 프로젝트 삭제 ---
async function deleteProject(id, ev) {
  if (ev) ev.stopPropagation();
  if (!confirm(`프로젝트 ${id} 를 삭제할까요?\nDB 기록과 data/output 폴더가 모두 지워집니다.`)) return;
  try {
    await api("DELETE", `/api/projects/${id}`);
    if (pid() === id) location.href = "/";
    else location.reload();
  } catch (e) { alert("삭제 실패: " + e.message); }
}

// --- 설정 ---
async function saveSettings(ev) {
  ev.preventDefault();
  const f = ev.target;
  const values = {};
  for (const el of f.elements) if (el.name) values[el.name] = el.value;
  try {
    await api("PUT", "/api/settings", { values });
    document.getElementById("save-status").textContent = "저장됨 ✓";
  } catch (e) { document.getElementById("save-status").textContent = "실패: " + e.message; }
  return false;
}

async function testProvider(provider) {
  try {
    const r = await api("POST", "/api/settings/test", { provider });
    alert(`${provider}: ${r.ok ? "연결 성공 ✓" : "실패"} ${r.detail || ""}`);
  } catch (e) { alert(`${provider} 테스트 실패: ` + e.message); }
}
