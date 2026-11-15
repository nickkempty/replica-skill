"use strict";
const app = document.getElementById("app");
let state = { project: null, cid: null, timer: null, rec: null };
let saveTimer = null;

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function fill(box, ...kids) {
  box.replaceChildren(...kids.flat().filter(k => k != null && k !== false));
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.style.display = "none"), 6000);
}

async function api(path, opts) {
  const res = await fetch("/api" + path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* not json */ }
    throw new Error(msg);
  }
  return res.json();
}
const post = (path, body) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}) });

function clock(s) {
  s = Math.max(0, Math.round(s));
  const hh = Math.floor(s / 3600), mm = Math.floor(s / 60) % 60, ss = s % 60;
  return (hh ? hh + ":" + String(mm).padStart(2, "0") : mm) + ":" + String(ss).padStart(2, "0");
}

/* ---------- YouTube connection ---------- */
async function refreshYoutube() {
  const yt = await api("/youtube");
  const btn = document.getElementById("yt");
  btn.textContent = yt.connected ? "YouTube: เชื่อมแล้ว" : "เชื่อมบัญชี YouTube";
  btn.onclick = async () => {
    if (!yt.has_client) {
      toast("ยังไม่มีไฟล์ client_secret.json ในโฟลเดอร์ " + yt.data_dir + " ดูวิธีทำใน README");
      return;
    }
    btn.textContent = "กำลังรอการลงชื่อเข้าใช้ Google...";
    try { await post("/youtube/connect"); } catch (e) { toast(e.message); }
    refreshYoutube();
  };
  state.youtube = yt.connected;
}

/* ---------- Home ---------- */
async function home() {
  stopPolling();
  const projects = await api("/projects");
  const f = {
    url: h("input", { type: "text", id: "url", placeholder: "https://www.youtube.com/watch?v=..." }),
    file: h("input", { type: "text", id: "file", placeholder: "เช่น C:\\Videos\\gta6.mp4" }),
    channel: h("input", { type: "text", id: "channel", placeholder: "ชื่อช่องต้นทาง" }),
    ok: h("input", { type: "checkbox", id: "ok" }),
    count: h("input", { type: "number", id: "count", value: 8, min: 1, max: 30 }),
    min: h("input", { type: "number", id: "min", value: 20, min: 5, max: 60 }),
    max: h("input", { type: "number", id: "max", value: 45, min: 5, max: 60 }),
    speech: h("input", { type: "checkbox", id: "speech" }),
  };
  const go = h("button", { onclick: async () => {
    go.disabled = true;
    try {
      const p = await post("/projects", {
        url: f.url.value, file_path: f.file.value, channel: f.channel.value,
        permission: f.ok.checked,
        settings: { count: f.count.value, min_len: f.min.value, max_len: f.max.value,
                    use_speech: f.speech.checked } });
      location.hash = "#p/" + p.id;
    } catch (e) { toast(e.message); go.disabled = false; }
  } }, "หาไฮไลท์ให้เลย");

  fill(app,
    h("div", { class: "panel" },
      h("h1", {}, "งานใหม่"),
      h("p", { class: "dim" }, "วางลิงก์วิดีโอ แล้วโปรแกรมจะเลือกช่วงไฮไลท์ที่น่าสนใจให้เอง"),
      h("label", { for: "url" }, "ลิงก์ YouTube"), f.url,
      h("label", { for: "file" }, "หรือ ที่อยู่ไฟล์วิดีโอในเครื่อง"), f.file,
      h("label", { for: "channel" }, "ช่องหรือเจ้าของวิดีโอต้นทาง (ใส่เป็นเครดิตในคำอธิบายคลิป)"), f.channel,
      h("label", { class: "check" }, f.ok,
        h("span", {}, "ฉันได้รับอนุญาตจากเจ้าของวิดีโอนี้ให้นำมาตัดและเผยแพร่บนช่องของฉัน")),
      h("details", {}, h("summary", { class: "dim small" }, "ตั้งค่าเพิ่มเติม"),
        h("div", { class: "row" },
          h("div", { class: "grow" }, h("label", { for: "count" }, "จำนวนคลิป"), f.count),
          h("div", { class: "grow" }, h("label", { for: "min" }, "สั้นสุด (วินาที)"), f.min),
          h("div", { class: "grow" }, h("label", { for: "max" }, "ยาวสุด (วินาที)"), f.max)),
        h("label", { class: "check" }, f.speech,
          h("span", {}, "ใช้คำพูดในวิดีโอต้นฉบับช่วยเลือกด้วย (แม่นขึ้นกับคลิปที่มีคนพูด แต่ช้ากว่ามาก)"))),
      h("div", { class: "row" }, go)),
    h("div", { class: "panel" },
      h("h2", {}, "งานที่ทำไว้"),
      projects.length ? h("div", { class: "list" }, projects.map(p =>
        h("a", { href: "#p/" + p.id },
          h("span", {}, p.title || p.channel),
          h("span", { class: "dim small" }, stageText(p.status), " · ", p.clips, " คลิป"))))
        : h("p", { class: "dim" }, "ยังไม่มีงาน")));
}

function stageText(st) {
  return { queued: "รอคิว", downloading: "กำลังดาวน์โหลด", analyzing: "กำลังวิเคราะห์",
           picking: "กำลังเลือกไฮไลท์", ready: "พร้อม", error: "ผิดพลาด" }[st.stage] || st.stage;
}

/* ---------- Project ---------- */
function stopPolling() {
  clearInterval(state.timer);
  state.timer = null;
  stopRecording(true);
}

async function openProject(pid) {
  stopPolling();
  state.cid = null;
  try { state.project = await api("/projects/" + pid); }
  catch (e) { toast(e.message); location.hash = ""; return; }
  drawProject();
  state.timer = setInterval(poll, 1000);
}

async function poll() {
  const p = state.project;
  if (!p) return;
  const busy = p.status.stage !== "ready" && p.status.stage !== "error";
  if (!busy && !p.clips.some(c => c.busy)) return;
  if (state.rec || saveTimer) return;
  const before = JSON.stringify(p);
  state.project = await api("/projects/" + p.id);
  if (JSON.stringify(state.project) !== before) {
    if (busy) drawProject(); else { drawList(); drawEditor(); }
  }
}

function drawProject() {
  const p = state.project, st = p.status;
  if (st.stage === "error") {
    fill(app, h("div", { class: "panel" },
      h("h1", {}, "ทำงานนี้ไม่สำเร็จ"), h("p", { class: "err" }, st.error),
      h("p", { class: "dim" }, "ตรวจลิงก์หรือที่อยู่ไฟล์ แล้วลองสร้างงานใหม่"),
      h("a", { href: "#" }, "กลับหน้าแรก")));
    return;
  }
  if (st.stage !== "ready") {
    fill(app, h("div", { class: "panel" },
      h("h1", {}, stageText(st) + "..."),
      h("p", { class: "dim" }, "วิดีโอยาวใช้เวลาหลายนาที เปิดหน้านี้ทิ้งไว้ได้"),
      h("div", { class: "bar" }, h("i", { style: "width:" + (st.progress || 3) + "%" }))));
    return;
  }
  if (!state.cid && p.clips.length) state.cid = p.clips[0].id;
  fill(app,
    h("h1", {}, p.title),
    h("p", { class: "dim" }, "ต้นทาง: ", p.channel, " · ยาว ", clock(p.duration),
      " · โปรแกรมเลือกไว้ ", p.clips.length, " คลิป เรียงจากน่าสนใจที่สุด"),
    h("div", { class: "work" }, h("div", { class: "clips", id: "list" }),
      h("div", { class: "panel", id: "editor" })));
  drawList();
  drawEditor(true);
}

function current() {
  return state.project.clips.find(c => c.id === state.cid);
}

function drawList() {
  const list = document.getElementById("list");
  if (!list) return;
  const p = state.project;
  fill(list,
    p.clips.map((c, i) => h("button", {
      class: "card" + (c.id === state.cid ? " on" : ""),
      onclick: () => { flushSave(); state.cid = c.id; drawList(); drawEditor(true); } },
      h("b", {}, "คลิป ", i + 1, "  "), clock(c.start), " ถึง ", clock(c.end),
      " (", Math.round(c.end - c.start), " วิ)",
      h("span", { class: "dim" }, c.reason),
      h("span", { class: "tag" + (c.has_voice && !c.voice_stale ? " ok" : "") },
        c.has_voice && !c.voice_stale ? "พากแล้ว" : "ยังไม่พาก"),
      c.rendered && h("span", { class: "tag ok" }, "ส่งออกแล้ว"),
      c.youtube_id && h("span", { class: "tag ok" }, "อัปแล้ว"))),
    h("button", { class: "ghost", onclick: async () => {
      try {
        const n = state.project.clips.length;
        state.project = await post("/projects/" + p.id + "/more");
        if (state.project.clips.length === n) toast("ไม่มีช่วงที่น่าสนใจเหลือแล้ว");
        drawList();
      } catch (e) { toast(e.message); }
    } }, "ขอไฮไลท์เพิ่มอีก"));
}

/* ---------- Saving edits ---------- */
function change(fields, redraw) {
  const c = current();
  Object.assign(c, fields);
  state.pending = Object.assign(state.pending || {}, fields);
  state.pendingCid = c.id;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushSave, 600);
  applyPreview();
  if ("start" in fields) {
    const video = document.getElementById("video");
    if (video) { video.pause(); video.currentTime = c.start; }
  }
  if (redraw) drawEditor();
}

async function flushSave() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (!state.pending) return;
  const body = state.pending, cid = state.pendingCid, pid = state.project.id;
  state.pending = null;
  try {
    const saved = await api("/projects/" + pid + "/clips/" + cid, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) });
    const i = state.project.clips.findIndex(c => c.id === cid);
    if (i >= 0 && !state.pending) { state.project.clips[i] = saved; drawList(); drawActions(); }
  } catch (e) {
    toast(e.message);
    state.project = await api("/projects/" + pid);
    drawList(); drawEditor();
  }
}

/* ---------- Editor ---------- */
function applyPreview() {
  const c = current(), video = document.getElementById("video");
  if (!c || !video) return;
  video.parentElement.classList.toggle("blur", c.crop_mode === "blur");
  video.style.objectPosition = (c.crop_x * 100) + "% 50%";
}

function playClip(withVoice) {
  const c = current(), video = document.getElementById("video");
  const voice = document.getElementById("voice");
  video.currentTime = c.start;
  video.volume = withVoice ? c.duck : 1;
  video.play();
  if (voice) {
    voice.pause();
    if (withVoice) { voice.currentTime = 0; voice.play(); }
  }
}

function onTime() {
  const c = current(), video = document.getElementById("video");
  if (!c || !video) return;
  const t = video.currentTime - c.start;
  if (video.currentTime >= c.end && !video.paused) {
    video.pause();
    const voice = document.getElementById("voice");
    if (voice) voice.pause();
    if (state.rec) stopRecording();
  }
  const sub = c.subtitles.find(s => t >= s.start && t < s.end);
  document.getElementById("sub").textContent = sub ? sub.text : "";
}

function num(label, key, step, min, max) {
  const c = current();
  const input = h("input", { type: "number", id: key, step: step, min: min, max: max,
    value: c[key], onchange: () => {
      const v = parseFloat(input.value);
      if (!isNaN(v)) change({ [key]: v });
    } });
  return h("div", { class: "grow" }, h("label", { for: key }, label), input);
}

function drawEditor(resetVideo) {
  const box = document.getElementById("editor");
  if (!box) return;
  const c = current(), p = state.project;
  if (!c) { fill(box, h("p", { class: "dim" }, "ไม่มีคลิป")); return; }
  const base = "/api/projects/" + p.id;
  let video = document.getElementById("video");
  if (!video || resetVideo) {
    video = h("video", { id: "video", src: base + "/video#t=" + c.start, playsinline: true,
      preload: "metadata", ontimeupdate: onTime });
  }
  const len = Math.round((c.end - c.start) * 10) / 10;

  fill(box, h("div", { class: "editor" },
    h("div", {},
      h("div", { class: "phone" }, video, h("div", { class: "sub", id: "sub" })),
      h("div", { class: "row", style: "margin-top:10px" },
        h("button", { class: "ghost", onclick: () => playClip(false) }, "เล่นคลิป"),
        h("button", { class: "ghost", onclick: () => {
          video.pause(); const v = document.getElementById("voice"); if (v) v.pause(); } }, "หยุด"))),
    h("div", {},
      h("div", { class: "step" },
        h("h2", {}, "1. ช่วงเวลาและกรอบภาพ"),
        h("p", { class: "dim small" }, "เหตุผลที่เลือก: ", c.reason, " · ยาว ", len, " วินาที"),
        h("div", { class: "row" },
          num("เริ่ม (วินาที)", "start", 1, 0, p.duration),
          num("จบ (วินาที)", "end", 1, 0, p.duration),
          h("div", { class: "grow" }, h("label", { for: "mode" }, "กรอบภาพ"),
            h("select", { id: "mode", onchange: e => change({ crop_mode: e.target.value }) },
              h("option", { value: "crop", selected: c.crop_mode === "crop" }, "ครอปเต็มจอ"),
              h("option", { value: "blur", selected: c.crop_mode === "blur" }, "ภาพเต็ม พื้นหลังเบลอ")))),
        h("label", { for: "cx" }, "เลื่อนกรอบซ้าย/ขวา"),
        h("input", { type: "range", id: "cx", min: 0, max: 1, step: 0.01, value: c.crop_x,
          oninput: e => change({ crop_x: parseFloat(e.target.value) }) })),
      h("div", { class: "step", id: "voicebox" }),
      h("div", { class: "step", id: "subbox" }),
      h("div", { class: "step" },
        h("h2", {}, "4. ชื่อและคำอธิบาย"),
        h("label", { for: "title" }, "ชื่อคลิป"),
        h("input", { type: "text", id: "title", maxlength: 100, value: c.title,
          oninput: e => change({ title: e.target.value }) }),
        h("label", { for: "desc" }, "คำอธิบาย (เครดิตช่องต้นทางจะถูกเติมท้ายให้อัตโนมัติ)"),
        h("textarea", { id: "desc", rows: 2, oninput: e => change({ description: e.target.value }) },
          c.description),
        h("label", { for: "tags" }, "แท็ก คั่นด้วยจุลภาค"),
        h("input", { type: "text", id: "tags", value: c.tags.join(", "),
          oninput: e => change({ tags: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }) })),
      h("div", { class: "step", id: "actions" }))));
  applyPreview();
  drawVoice(); drawSubs(); drawActions();
}

/* ---------- Voiceover ---------- */
function drawVoice() {
  const box = document.getElementById("voicebox");
  if (!box) return;
  const c = current(), p = state.project;
  const src = "/api/projects/" + p.id + "/clips/" + c.id + "/voice?v=" + Date.now();
  fill(box,
    h("h2", {}, "2. พากเสียงของคุณ"),
    h("p", { class: "warn" }, "ใส่หูฟังตอนอัด ไม่อย่างนั้นไมค์จะเก็บเสียงเกมจากลำโพงเข้าไปด้วย"),
    c.voice_stale && h("p", { class: "err small" }, "คุณเปลี่ยนช่วงเวลาหลังพากเสียง ต้องอัดเสียงพากใหม่"),
    h("div", { class: "row" },
      state.rec
        ? h("button", { class: "rec", onclick: () => stopRecording() }, "หยุดอัด")
        : h("button", { onclick: startRecording }, c.has_voice ? "อัดใหม่" : "เริ่มอัดเสียงพาก"),
      c.has_voice && !state.rec && h("button", { class: "ghost", onclick: () => playClip(true) },
        "ฟังพร้อมเสียงพาก"),
      state.rec && h("span", { class: "err" }, "กำลังอัด... พูดได้เลย")),
    c.has_voice && h("audio", { id: "voice", src: src, preload: "auto" }),
    h("label", { for: "duck" }, "ความดังเสียงเกมต้นฉบับใต้เสียงพาก: " + Math.round(c.duck * 100) + "%"),
    h("input", { type: "range", id: "duck", min: 0, max: 1, step: 0.05, value: c.duck,
      onchange: e => { change({ duck: parseFloat(e.target.value) }); drawVoice(); } }));
}

async function startRecording() {
  await flushSave();
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { toast("เปิดไมโครโฟนไม่ได้ กรุณาอนุญาตการใช้ไมค์ในเบราว์เซอร์"); return; }
  const c = current(), pid = state.project.id, cid = c.id;
  const rec = new MediaRecorder(stream), chunks = [];
  rec.ondataavailable = e => chunks.push(e.data);
  rec.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    const discard = state.discard;
    state.rec = null; state.discard = false;
    if (discard) return;
    try {
      const saved = await api("/projects/" + pid + "/clips/" + cid + "/voice", {
        method: "POST", body: new Blob(chunks, { type: rec.mimeType }) });
      const i = state.project.clips.findIndex(x => x.id === cid);
      if (i >= 0) state.project.clips[i] = saved;
    } catch (e) { toast(e.message); }
    drawList(); drawVoice(); drawSubs(); drawActions();
  };
  state.rec = rec;
  const video = document.getElementById("video");
  video.currentTime = c.start;
  video.volume = c.duck;
  rec.start();
  video.play();
  drawVoice();
}

function stopRecording(discard) {
  if (!state.rec) return;
  state.discard = !!discard;
  const video = document.getElementById("video");
  if (video) video.pause();
  if (state.rec.state !== "inactive") state.rec.stop();
}

/* ---------- Subtitles ---------- */
function drawSubs() {
  const box = document.getElementById("subbox");
  if (!box) return;
  const c = current();
  const edit = (i, key, value) => {
    const subs = c.subtitles.map(s => Object.assign({}, s));
    subs[i][key] = key === "text" ? value : (parseFloat(value) || 0);
    change({ subtitles: subs });
  };
  fill(box,
    h("h2", {}, "3. ซับไตเติล"),
    c.busy === "subtitles" && h("p", { class: "dim" }, "กำลังถอดเสียงพากเป็นซับ..."),
    c.subtitle_note && h("p", { class: "err small" }, c.subtitle_note),
    !c.subtitles.length && c.busy !== "subtitles" &&
      h("p", { class: "dim small" }, "ยังไม่มีซับ อัดเสียงพากแล้วโปรแกรมจะถอดให้ หรือเพิ่มเองด้านล่าง"),
    c.subtitles.map((s, i) => h("div", { class: "subrow" },
      h("input", { type: "number", step: 0.1, min: 0, value: s.start, "aria-label": "เริ่ม",
        onchange: e => edit(i, "start", e.target.value) }),
      h("input", { type: "number", step: 0.1, min: 0, value: s.end, "aria-label": "จบ",
        onchange: e => edit(i, "end", e.target.value) }),
      h("input", { type: "text", value: s.text, "aria-label": "ข้อความ",
        oninput: e => edit(i, "text", e.target.value) }),
      h("button", { class: "danger", "aria-label": "ลบบรรทัดนี้", onclick: () => {
        change({ subtitles: c.subtitles.filter((_, j) => j !== i) }); drawSubs(); } }, "×"))),
    h("button", { class: "ghost", onclick: () => {
      const last = c.subtitles[c.subtitles.length - 1];
      const start = last ? last.end : 0;
      change({ subtitles: c.subtitles.concat([{ start: start, end: start + 2, text: "" }]) });
      drawSubs();
    } }, "เพิ่มบรรทัดซับ"));
}

/* ---------- Export and upload ---------- */
function drawActions() {
  const box = document.getElementById("actions");
  if (!box) return;
  const c = current(), p = state.project;
  const base = "/projects/" + p.id + "/clips/" + c.id;
  const voiced = c.has_voice && !c.voice_stale;
  const act = (path, busy) => async () => {
    await flushSave();
    try { await post(base + path); current().busy = busy; drawActions(); }
    catch (e) { toast(e.message); }
  };
  fill(box,
    h("h2", {}, "5. ส่งออกและอัป"),
    c.error && h("p", { class: "err small" }, "ผิดพลาด: ", c.error),
    h("div", { class: "row" },
      h("button", { disabled: !!c.busy, onclick: act("/render", "render") },
        c.busy === "render" ? "กำลังส่งออก..." : (c.rendered ? "ส่งออกใหม่" : "ส่งออกคลิป")),
      c.rendered && h("a", { href: "/api" + base + "/file?download=1" },
        h("button", { class: "ghost" }, "บันทึกไฟล์ mp4")),
      h("button", { disabled: !!c.busy || !c.rendered || !voiced || !state.youtube,
        onclick: act("/upload", "upload") },
        c.busy === "upload" ? "กำลังอัป..." : "อัปขึ้น YouTube (ฉบับร่างส่วนตัว)"),
      h("button", { class: "danger", onclick: async () => {
        if (!confirm("เอาคลิปนี้ออกจากรายการ?")) return;
        await api(base, { method: "DELETE" });
        state.project = await api("/projects/" + p.id);
        state.cid = null;
        drawProject();
      } }, "เอาคลิปนี้ออก")),
    !voiced && h("p", { class: "dim small" }, "ต้องพากเสียงก่อนจึงจะอัปขึ้น YouTube ได้"),
    voiced && !c.rendered && h("p", { class: "dim small" }, "กดส่งออกคลิปก่อน แล้วจึงอัป"),
    voiced && c.rendered && !state.youtube &&
      h("p", { class: "dim small" }, "กดปุ่ม เชื่อมบัญชี YouTube ที่มุมขวาบนก่อน"),
    c.youtube_id && h("p", {}, "อัปแล้วเป็นฉบับร่างส่วนตัว ",
      h("a", { href: "https://studio.youtube.com/video/" + c.youtube_id + "/edit",
        target: "_blank", rel: "noopener" }, "เปิดใน YouTube Studio เพื่อตรวจและเผยแพร่")));
}

/* ---------- Router ---------- */
function route() {
  const m = location.hash.match(/^#p\/([0-9a-f]+)$/);
  if (m) openProject(m[1]); else home();
}
window.addEventListener("hashchange", route);
refreshYoutube().catch(() => {});
route();
