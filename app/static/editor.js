// 씬 편집기 — 슬라이드 리스트 + 씬 편집 패널 + 재렌더 미리보기
// 기존 API 재사용: GET /api/projects/{id}, PUT/POST/DELETE scenes, scenes/{n}/tts, render

const PID = document.getElementById("editor-root")?.dataset.pid;
let STATE = { scenes: [], clips: [], selected: null };

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

async function load() {
  const p = await api("GET", `/api/projects/${PID}`);
  STATE.scenes = (p.scenes || []).slice().sort((a, b) => a.scene_no - b.scene_no);
  STATE.clips = (p.clips || []).slice().sort((a, b) => b.hook_score - a.hook_score);
  if (STATE.selected == null && STATE.scenes.length) STATE.selected = STATE.scenes[0].scene_no;
  renderSlides();
  renderPanel();
  loadAudioPanel();
  loadTextPanel();
  loadTemplates();
}

// ---- ASS 색상(&HAABBGGRR) ↔ #RRGGBB ----
function assToHex(ass) {
  const m = /&H[0-9A-Fa-f]{2}([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})/.exec(ass || "");
  if (!m) return "#ffffff";
  return "#" + m[3] + m[2] + m[1]; // BGR→RGB
}
function hexToAss(hex) {
  const h = (hex || "#ffffff").replace("#", "");
  return "&H00" + h.slice(4, 6) + h.slice(2, 4) + h.slice(0, 2); // RGB→BGR
}

// ---- 자막·제목 스타일 (일괄 적용) ----
async function loadTextPanel() {
  let s;
  try { s = await api("GET", `/api/projects/${PID}/edit-settings`); }
  catch { return; }
  STATE.textcfg = s;
  const cap = s.subtitle_style || {};
  const ttl = s.title_style || {};
  const box = document.getElementById("text-panel");
  box.innerHTML = `
    <div class="grid2">
      <label>영상 맞춤
        <select id="t-fit">
          <option value="cover" ${s.fit_mode !== 'contain' ? 'selected' : ''}>꽉 채우기</option>
          <option value="contain" ${s.fit_mode === 'contain' ? 'selected' : ''}>박스형(제목·자막 공간)</option>
        </select>
      </label>
      <label>자막 위치
        <select id="t-align">
          <option value="2" ${(cap.alignment||2)==2?'selected':''}>하단</option>
          <option value="5" ${cap.alignment==5?'selected':''}>중앙</option>
          <option value="8" ${cap.alignment==8?'selected':''}>상단</option>
        </select>
      </label>
      <label>자막 크기<input id="t-size" type="number" min="30" max="120" value="${cap.size||60}"></label>
      <label>자막 색<input id="t-color" type="color" value="${assToHex(cap.primary||'&H00FFFFFF')}"></label>
      <label><input id="t-box" type="checkbox" ${(cap.box_color&&cap.box_color!=='&HFF000000')?'checked':''}> 자막 배경박스</label>
      <label>하단 여백<input id="t-mv" type="number" min="40" max="500" value="${cap.margin_v||220}"></label>
    </div>
    <hr style="border-color:var(--line);margin:10px 0">
    <label><input id="t-showtitle" type="checkbox" ${s.show_title?'checked':''}> 상단 고정 제목 표시</label>
    <div class="grid2">
      <label>제목 문구<input id="t-title" value="${(s.title_text||'').replace(/"/g,'&quot;')}" placeholder="비우면 첫 자막/상품명"></label>
      <label>제목 색<input id="t-tcolor" type="color" value="${assToHex(ttl.primary||'&H0000FFFF')}"></label>
    </div>
    <div class="panel-ops">
      <button class="btn primary" onclick="saveTextStyle()">모든 자막에 일괄 적용</button>
      <span id="text-msg" class="hint"></span>
    </div>`;
}

async function saveTextStyle() {
  const cap = { ...(STATE.textcfg.subtitle_style || {}) };
  cap.size = parseInt(val("t-size")); cap.primary = hexToAss(val("t-color"));
  cap.alignment = parseInt(val("t-align")); cap.margin_v = parseInt(val("t-mv"));
  cap.box_color = document.getElementById("t-box").checked ? "&H80000000" : "&HFF000000";
  cap.border_style = document.getElementById("t-box").checked ? 3 : 1;
  const ttl = { ...(STATE.textcfg.title_style || {}) };
  ttl.primary = hexToAss(val("t-tcolor"));
  const body = {
    fit_mode: val("t-fit"),
    show_title: document.getElementById("t-showtitle").checked,
    title_text: val("t-title"),
    subtitle_style: cap, title_style: ttl,
  };
  try { await api("PUT", `/api/projects/${PID}/edit-settings`, body); txtMsg("적용됨 ✓ 재렌더링하면 반영"); loadTextPanel(); }
  catch (e) { txtMsg("실패: " + e.message); }
}
const txtMsg = (m) => { const e = document.getElementById("text-msg"); if (e) e.textContent = m; };

// ---- 템플릿 ----
let TEMPLATES = [];
async function loadTemplates() {
  if (TEMPLATES.length) { fillTemplateSelect(); return; }
  try {
    const r = await api("GET", "/api/templates");
    TEMPLATES = r.templates || [];
    fillTemplateSelect();
  } catch { /* ignore */ }
}
function fillTemplateSelect() {
  const sel = document.getElementById("tpl-select");
  if (!sel) return;
  const cur = (STATE.audio && STATE.audio.template_id) || "";
  sel.innerHTML = TEMPLATES.map(t =>
    `<option value="${t.id}" ${t.id === cur ? "selected" : ""}>${t.name}</option>`).join("");
  showTplDesc();
  sel.onchange = showTplDesc;
}
function showTplDesc() {
  const sel = document.getElementById("tpl-select");
  const t = TEMPLATES.find(x => x.id === sel.value);
  document.getElementById("tpl-desc").textContent = t ? t.description : "";
}
async function applyTemplate() {
  const id = document.getElementById("tpl-select").value;
  tplMsg("적용 중...");
  try {
    await api("POST", `/api/projects/${PID}/apply-template`, { template_id: id });
    tplMsg("적용됨 ✓ (자막 스타일/배경/전환/톤 반영). 재렌더링하면 반영됩니다.");
    loadAudioPanel();
  } catch (e) { tplMsg("실패: " + e.message); }
}
const tplMsg = (m) => { const e = document.getElementById("tpl-msg"); if (e) e.textContent = m; };

// ---- 오디오/배경 (프로젝트) ----
async function loadAudioPanel() {
  let s;
  try { s = await api("GET", `/api/projects/${PID}/edit-settings`); }
  catch { return; }
  STATE.audio = s;
  const box = document.getElementById("audio-panel");
  box.innerHTML = `
    <div class="grid2">
      <label>배경색<input id="a-bg" type="color" value="${s.bg_color || '#202430'}"></label>
      <label>전환<select id="a-trans">
        <option value="none" ${s.transition === 'none' ? 'selected' : ''}>없음</option>
        <option value="fade" ${s.transition === 'fade' ? 'selected' : ''}>페이드</option>
      </select></label>
      <label>전환 길이(초)<input id="a-transdur" type="number" step="0.1" min="0" max="2" value="${s.transition_duration}"></label>
      <label>BGM 볼륨<input id="a-bgmvol" type="range" min="0" max="1" step="0.02" value="${s.bgm_volume}"></label>
    </div>
    <label style="margin-top:8px"><input type="checkbox" id="a-bgmon" ${s.bgm_enabled ? 'checked' : ''}> BGM 사용</label>
    <div class="panel-ops">
      <button class="btn primary" onclick="saveAudio()">배경/전환 저장</button>
      <label class="btn" style="cursor:pointer">BGM 업로드<input type="file" accept="audio/*" hidden onchange="uploadBgm(this.files[0])"></label>
      ${s.bgm_present ? '<button class="btn" onclick="delBgm()">BGM 제거</button>' : ''}
      <span id="audio-msg" class="hint">${s.bgm_present ? 'BGM 있음 ✓' : 'BGM 없음'}</span>
    </div>`;
}

async function saveAudio() {
  const body = {
    bg_color: document.getElementById("a-bg").value,
    transition: document.getElementById("a-trans").value,
    transition_duration: parseFloat(document.getElementById("a-transdur").value),
    bgm_volume: parseFloat(document.getElementById("a-bgmvol").value),
    bgm_enabled: document.getElementById("a-bgmon").checked,
  };
  try { await api("PUT", `/api/projects/${PID}/edit-settings`, body); audMsg("저장됨 ✓"); }
  catch (e) { audMsg("실패: " + e.message); }
}

async function uploadBgm(file) {
  if (!file) return;
  audMsg("BGM 업로드 중...");
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch(`/api/projects/${PID}/audio/bgm`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    audMsg("BGM 업로드 완료 ✓"); loadAudioPanel();
  } catch (e) { audMsg("실패: " + e.message); }
}

async function delBgm() {
  try { await api("DELETE", `/api/projects/${PID}/audio/bgm`); loadAudioPanel(); }
  catch (e) { audMsg("실패: " + e.message); }
}

const audMsg = (m) => { const e = document.getElementById("audio-msg"); if (e) e.textContent = m; };

// ---- 스톡 영상 검색/삽입 ----
async function stockSearch() {
  const q = document.getElementById("stock-q").value.trim();
  if (!q) return;
  stockMsg("검색 중...");
  try {
    const r = await api("GET", `/api/stock/search?q=${encodeURIComponent(q)}`);
    const grid = document.getElementById("stock-results");
    grid.innerHTML = "";
    if (!r.results.length) { stockMsg("결과 없음 (설정에서 Pexels 키/프로바이더 확인)"); return; }
    r.results.forEach(v => {
      const d = document.createElement("div");
      d.className = "stock-item";
      d.innerHTML = `${v.preview_image ? `<img src="${v.preview_image}" loading="lazy">` : '<div class="stock-noimg"></div>'}<span>${v.duration}s</span>`;
      d.title = `${v.provider} · ${v.author} · ${v.width}x${v.height}`;
      d.onclick = () => stockImport(v);
      grid.appendChild(d);
    });
    stockMsg(`${r.results.length}개 · 클릭하면 삽입`);
  } catch (e) { stockMsg("실패: " + e.message); }
}

async function stockImport(v) {
  if (!v.video_url) { stockMsg("이 결과는 삽입 불가(mock)"); return; }
  stockMsg("삽입 중(다운로드+분석)...");
  try {
    const r = await api("POST", `/api/projects/${PID}/stock/import`, { video_url: v.video_url, source_id: v.id });
    stockMsg(`삽입 완료 · 컷 ${r.clips_added}개 추가됨`);
    await load();  // 클립 목록 갱신 → 컷 지정 드롭다운에 반영
  } catch (e) { stockMsg("실패: " + e.message); }
}

const stockMsg = (m) => { const e = document.getElementById("stock-msg"); if (e) e.textContent = m; };

function sceneThumb(s) {
  // preferred_clip_id 있으면 그 클립, 없으면 hook 1위 클립
  const cid = s.preferred_clip_id || (STATE.clips[0] && STATE.clips[0].clip_id);
  return cid ? `/api/projects/${PID}/clips/${cid}/thumb.jpg` : "";
}

function renderSlides() {
  const box = document.getElementById("slide-list");
  box.innerHTML = "";
  STATE.scenes.forEach((s, i) => {
    const div = document.createElement("div");
    div.className = "slide-card" + (s.scene_no === STATE.selected ? " active" : "");
    const thumb = sceneThumb(s);
    div.innerHTML = `
      <div class="slide-thumb">${thumb ? `<img src="${thumb}" loading="lazy">` : ""}<span class="slide-dur">${(s.target_duration || 0).toFixed(1)}s</span></div>
      <div class="slide-meta">
        <span class="tag">#${i + 1} ${s.role}</span>
        <div class="slide-cap">${s.caption_text || "(자막 없음)"}</div>
      </div>
      <div class="slide-ops">
        <button title="위로" onclick="move(${s.scene_no},-1);event.stopPropagation()">▲</button>
        <button title="아래로" onclick="move(${s.scene_no},1);event.stopPropagation()">▼</button>
        <button title="삭제" onclick="delScene(${s.scene_no});event.stopPropagation()">✕</button>
      </div>`;
    div.onclick = () => { STATE.selected = s.scene_no; renderSlides(); renderPanel(); };
    box.appendChild(div);
  });
}

function renderPanel() {
  const panel = document.getElementById("edit-panel");
  const s = STATE.scenes.find(x => x.scene_no === STATE.selected);
  if (!s) { panel.innerHTML = '<p class="empty">씬을 선택하세요.</p>'; return; }
  const roles = ["hook", "problem", "solution", "proof", "cta"];
  const emotions = ["energetic", "relatable", "confident", "satisfied", "friendly", "neutral"];
  const paces = ["fast", "normal", "slow"];
  const clipOpts = STATE.clips.map(c =>
    `<option value="${c.clip_id}" ${s.preferred_clip_id === c.clip_id ? "selected" : ""}>`
    + `${c.clip_id} · hook ${c.hook_score.toFixed(2)} · ${(c.tags || []).join(",") || "no-tag"}</option>`
  ).join("");
  panel.innerHTML = `
    <h3>씬 #${s.scene_no} 편집</h3>
    <div class="grid2">
      <label>역할<select id="f-role">${roles.map(r => `<option ${s.role === r ? "selected" : ""}>${r}</option>`).join("")}</select></label>
      <label>길이(초)<input id="f-dur" type="number" step="0.1" min="0.5" value="${s.target_duration}"></label>
      <label>감정<select id="f-emotion">${emotions.map(e => `<option ${s.emotion === e ? "selected" : ""}>${e}</option>`).join("")}</select></label>
      <label>속도<select id="f-pace">${paces.map(p => `<option ${s.pace === p ? "selected" : ""}>${p}</option>`).join("")}</select></label>
    </div>
    <label>🎙 나레이션(voice_text)<textarea id="f-voice" rows="2">${s.voice_text || ""}</textarea></label>
    <label>💬 자막(caption_text)<textarea id="f-caption" rows="2">${s.caption_text || ""}</textarea></label>
    <label>연출 메모(visual_need)<input id="f-need" value="${s.visual_need || ""}"></label>
    <label>컷 지정<select id="f-clip"><option value="">자동 매칭</option>${clipOpts}</select></label>
    <div class="panel-ops">
      <button class="btn primary" onclick="saveScene()">저장</button>
      <button class="btn" onclick="sceneTTS()">🎙 이 씬 TTS</button>
      <label class="btn" style="cursor:pointer">🔊 효과음<input type="file" accept="audio/*" hidden onchange="uploadSfx(this.files[0])"></label>
      ${s.sfx_path ? '<button class="btn" onclick="delSfx()">효과음 제거</button>' : ''}
      <span id="scene-msg" class="hint">${s.sfx_path ? '효과음 있음 ✓' : ''}</span>
    </div>`;
}

async function saveScene() {
  const s = STATE.selected;
  const body = {
    role: val("f-role"), target_duration: parseFloat(val("f-dur")),
    emotion: val("f-emotion"), pace: val("f-pace"),
    voice_text: val("f-voice"), caption_text: val("f-caption"),
    visual_need: val("f-need"), preferred_clip_id: val("f-clip"),
  };
  try { await api("PUT", `/api/projects/${PID}/scenes/${s}`, body); msg("저장됨 ✓"); await load(); }
  catch (e) { msg("실패: " + e.message); }
}

async function sceneTTS() {
  msg("TTS 생성 중...");
  try { const r = await api("POST", `/api/projects/${PID}/scenes/${STATE.selected}/tts`, {}); msg(`TTS 완료 (${r.duration}s)`); }
  catch (e) { msg("TTS 실패: " + e.message); }
}

async function uploadSfx(file) {
  if (!file) return;
  msg("효과음 업로드 중...");
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch(`/api/projects/${PID}/scenes/${STATE.selected}/sfx`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    msg("효과음 업로드 완료 ✓"); await load();
  } catch (e) { msg("실패: " + e.message); }
}

async function delSfx() {
  try { await api("DELETE", `/api/projects/${PID}/scenes/${STATE.selected}/sfx`); msg("효과음 제거됨"); await load(); }
  catch (e) { msg("실패: " + e.message); }
}

async function addScene() {
  try { const r = await api("POST", `/api/projects/${PID}/scenes`, { after_scene_no: STATE.selected }); STATE.selected = r.scene_no; await load(); }
  catch (e) { alert(e.message); }
}

async function delScene(no) {
  if (!confirm(`씬 #${no} 삭제?`)) return;
  try { await api("DELETE", `/api/projects/${PID}/scenes/${no}`); if (STATE.selected === no) STATE.selected = null; await load(); }
  catch (e) { alert(e.message); }
}

async function move(no, dir) {
  const order = STATE.scenes.map(s => s.scene_no);
  const i = order.indexOf(no), j = i + dir;
  if (j < 0 || j >= order.length) return;
  [order[i], order[j]] = [order[j], order[i]];
  try { await api("POST", `/api/projects/${PID}/scenes/reorder`, { order }); await load(); }
  catch (e) { alert(e.message); }
}

async function reRender() {
  edJob("타임라인+렌더 시작...");
  try {
    await api("POST", `/api/projects/${PID}/timeline`, {});
    const r = await api("POST", `/api/projects/${PID}/render`, {});
    await pollRender(r.job_id);
  } catch (e) { edJob("실패: " + e.message); }
}

async function pollRender(jobId) {
  for (let i = 0; i < 600; i++) {
    await new Promise(r => setTimeout(r, 1500));
    const j = await api("GET", `/api/jobs/${jobId}`);
    edJob(`렌더: ${j.status} (${j.progress}%) ${j.log || ""}`);
    if (j.status === "done") {
      edJob("렌더 완료 ✓");
      const v = document.getElementById("preview");
      v.src = `/api/projects/${PID}/preview.mp4?t=` + Date.now();
      v.load();
      return;
    }
    if (j.status === "failed") { edJob("렌더 실패: " + j.log); return; }
  }
}

const val = (id) => document.getElementById(id).value;
const msg = (m) => { const e = document.getElementById("scene-msg"); if (e) e.textContent = m; };
const edJob = (m) => { document.getElementById("ed-job").textContent = m; };

if (PID) load();
