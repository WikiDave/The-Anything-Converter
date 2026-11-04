"use strict";
const $ = (id) => document.getElementById(id);
const AUDIO_OUT = ["mp3", "m4a", "aac", "wav", "flac", "ogg", "opus"];
const LOSSLESS_AUDIO = ["wav", "flac"];
let current = null;   // upload-info van de server
let localFile = null; // het bestand zelf, voor de preview
let duration = 0;

// ---------- hulpfuncties
function human(n) {
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n.toFixed(0) : n.toFixed(2)) + " " + u[i];
}
function fmtTime(s) {
  if (!isFinite(s)) return "–";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const ss = sec.toFixed(1).padStart(4, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}
function parseTime(v) {
  v = String(v || "").trim().replace(",", ".");
  if (!v) return null;
  const parts = v.split(":").map(Number);
  if (parts.some(isNaN)) return NaN;
  return parts.reduce((a, b) => a * 60 + b, 0);
}
function txtBar(f, width = 32) {
  const n = Math.round(Math.max(0, Math.min(1, f)) * width);
  return "[" + "█".repeat(n) + "░".repeat(width - n) + "] " + String(Math.round(f * 100)).padStart(3) + "%";
}
function barWidth() { return window.innerWidth < 480 ? 20 : 32; }
function status(msg) { $("status").textContent = "> " + msg; }
function step(n) {
  document.querySelectorAll(".menubar span").forEach((el) => {
    const k = +el.dataset.step;
    el.classList.toggle("on", n === 2 ? k >= 2 && k <= 3 : k === n);
    el.classList.toggle("done", k < (n === 2 ? 2 : n));
  });
}
const radio = (name) => document.querySelector(`input[name=${name}]:checked`).value;
const show = (el, on) => el.classList.toggle("hidden", !on);

// ---------- upload
const drop = $("drop"), fileInput = $("fileInput");
drop.addEventListener("click", () => fileInput.click());
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault(); drop.classList.remove("over");
  if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => fileInput.files[0] && upload(fileInput.files[0]));

function upload(file) {
  localFile = file;
  const bar = $("uploadBar");
  show(bar, true);
  bar.textContent = txtBar(0, barWidth());
  status("uploaden: " + file.name);
  const fd = new FormData();
  fd.append("file", file);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) bar.textContent = txtBar(e.loaded / e.total, barWidth()); };
  xhr.onload = () => {
    show(bar, false);
    let data;
    try { data = JSON.parse(xhr.responseText); } catch { data = { error: "Upload mislukt." }; }
    if (xhr.status !== 200) { status("FOUT: " + (data.error || "upload mislukt")); alert(data.error || "Upload mislukt."); return; }
    setup(data);
  };
  xhr.onerror = () => { show(bar, false); alert("Upload mislukt (verbinding)."); };
  xhr.send(fd);
}

// ---------- opties opbouwen
function setup(data) {
  current = data;
  show(drop, false);
  show($("panel"), true);
  show($("result"), false);
  show($("progress"), false);
  step(2);
  status(`geladen: ${data.name} [${data.label.toLowerCase()}]`);

  $("fName").textContent = data.name;
  const meta = [data.label, human(data.size)];
  const i = data.info || {};
  if (i.width) meta.push(`${i.width}×${i.height}`);
  if (i.duration && data.category !== "image") meta.push(fmtTime(i.duration));
  $("fMeta").textContent = meta.join(" · ");
  duration = i.duration || 0;

  const sel = $("format");
  sel.innerHTML = "";
  for (const t of data.targets) {
    const o = document.createElement("option");
    o.value = t;
    o.textContent = "." + t + (t === data.ext || (t === "jpg" && data.ext === "jpeg") ? "  (zelfde formaat)" : "");
    sel.appendChild(o);
  }
  const same = data.targets.find((t) => t === data.ext || (t === "jpg" && data.ext === "jpeg"));
  sel.value = same || data.targets[0];

  // reset velden
  for (const id of ["targetSize", "scalePct", "imgW", "imgH", "gifWidth", "gifFps", "trimStart", "trimEnd"]) $(id).value = "";
  $("removeAudio").checked = false; $("fastTrim").checked = false; $("height").value = "";
  document.querySelector("input[name=sizeMode][value=quality]").checked = true;

  setupPreview(data);
  refresh();
}

function setupPreview(data) {
  const v = $("preview"), a = $("previewAudio");
  for (const el of [v, a]) { if (el.src) URL.revokeObjectURL(el.src); el.removeAttribute("src"); show(el, false); }
  if (!["video", "audio"].includes(data.category)) return;
  const el = data.category === "video" ? v : a;
  el.src = URL.createObjectURL(localFile);
  el.onloadedmetadata = () => { if (!duration && isFinite(el.duration)) { duration = el.duration; syncSliders(); } };
  el.onerror = () => show(el, false); // browser kan dit formaat niet afspelen; knippen via tijden blijft werken
  show(el, true);
  $("rStart").value = 0; $("rEnd").value = 1000;
  syncSel();
}

function refresh() {
  if (!current) return;
  const cat = current.category, fmt = $("format").value;
  const isMedia = cat === "video" || cat === "audio";
  const toVideo = cat === "video" && !AUDIO_OUT.includes(fmt) && fmt !== "gif";
  const target = radio("sizeMode") === "target";

  const sizeable = (isMedia && !LOSSLESS_AUDIO.includes(fmt)) ||
    (cat === "image" && !["ico", "pdf"].includes(fmt)) ||
    fmt === "pdf" || ["archive", "other"].includes(cat);
  show($("sizeField"), sizeable || isMedia || cat === "image");
  document.querySelector("input[name=sizeMode][value=target]").disabled = !sizeable;
  if (!sizeable && target) document.querySelector("input[name=sizeMode][value=quality]").checked = true;

  const t = radio("sizeMode") === "target";
  show($("targetBox"), t);
  show($("qualityBox"), !t && !(cat === "audio" && LOSSLESS_AUDIO.includes(fmt)));
  show($("videoBox"), toVideo);
  show($("gifBox"), cat === "video" && fmt === "gif");
  show($("imageBox"), cat === "image");
  show($("trimBox"), isMedia);
  $("fastTrim").parentElement.classList.toggle("hidden", fmt !== current.ext);

  let hint = "";
  if (cat === "video" && fmt !== "gif") hint = "Groter dan het origineel kan ook: dan wordt de bitrate verhoogd.";
  if (cat === "image") hint = "Kleiner: lagere kwaliteit en/of resolutie. Groter: hogere kwaliteit en resolutie.";
  if (["archive", "other"].includes(cat)) hint = "Verliesvrij inpakken; al gecomprimeerde bestanden worden nauwelijks kleiner.";
  if (cat === "pdf" || fmt === "pdf") hint = "PDF's worden kleiner door afbeeldingen te herschalen en te comprimeren.";
  $("targetHint").textContent = hint;
}
$("format").addEventListener("change", refresh);
document.querySelectorAll("input[name=sizeMode]").forEach((r) => r.addEventListener("change", refresh));

$("sizeChips").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b || !current) return;
  let bytes = b.dataset.abs ? Number(b.dataset.abs) * 1024 * 1024 : current.size * Number(b.dataset.f);
  // houd rekening met knippen: verhoudingsknoppen gelden voor het geknipte deel
  if (b.dataset.f && duration) { const sel = selection(); if (sel) bytes *= sel.len / duration; }
  const unit = bytes < 1024 * 1024 ? "kb" : bytes < 1024 ** 3 ? "mb" : "gb";
  $("targetUnit").value = unit;
  $("targetSize").value = +(bytes / { kb: 1024, mb: 1024 ** 2, gb: 1024 ** 3 }[unit]).toFixed(2);
});

// image: schaal% óf breedte/hoogte
$("scalePct").addEventListener("input", () => { if ($("scalePct").value) { $("imgW").value = ""; $("imgH").value = ""; } });
for (const id of ["imgW", "imgH"]) $(id).addEventListener("input", () => { if ($(id).value) $("scalePct").value = ""; });

// ---------- knippen
function player() { return current && current.category === "video" ? $("preview") : $("previewAudio"); }
function selection() {
  const s = parseTime($("trimStart").value) ?? 0;
  const e = parseTime($("trimEnd").value) ?? duration;
  if (isNaN(s) || isNaN(e) || e <= s) return null;
  return { s, e, len: e - s };
}
function syncSel() {
  const a = +$("rStart").value, b = +$("rEnd").value;
  $("trimSel").style.left = a / 10 + "%";
  $("trimSel").style.width = Math.max(0, b - a) / 10 + "%";
  const sel = selection();
  $("trimLen").textContent = sel ? fmtTime(sel.len) + (duration ? ` van ${fmtTime(duration)}` : "") : "ongeldig";
}
function syncSliders() {
  if (!duration) return syncSel();
  const s = parseTime($("trimStart").value) ?? 0, e = parseTime($("trimEnd").value) ?? duration;
  if (!isNaN(s)) $("rStart").value = Math.round(1000 * s / duration);
  if (!isNaN(e)) $("rEnd").value = Math.round(1000 * Math.min(e, duration) / duration);
  syncSel();
}
function sliderInput(which) {
  if (!duration) return;
  let a = +$("rStart").value, b = +$("rEnd").value;
  if (a > b - 1) { if (which === "s") a = b - 1; else b = a + 1; $("rStart").value = a; $("rEnd").value = b; }
  $("trimStart").value = a === 0 ? "" : fmtTime(a * duration / 1000);
  $("trimEnd").value = b === 1000 ? "" : fmtTime(b * duration / 1000);
  const p = player();
  if (p && p.src && !p.classList.contains("hidden")) p.currentTime = (which === "s" ? a : b) * duration / 1000;
  syncSel();
}
$("rStart").addEventListener("input", () => sliderInput("s"));
$("rEnd").addEventListener("input", () => sliderInput("e"));
$("trimStart").addEventListener("input", syncSliders);
$("trimEnd").addEventListener("input", syncSliders);
$("setStart").addEventListener("click", () => { $("trimStart").value = fmtTime(player().currentTime || 0); syncSliders(); });
$("setEnd").addEventListener("click", () => { $("trimEnd").value = fmtTime(player().currentTime || 0); syncSliders(); });

// ---------- starten
$("resetBtn").addEventListener("click", () => {
  current = null; fileInput.value = "";
  const p = $("preview"); p.pause && p.pause();
  show($("panel"), false); show(drop, true);
  step(1); status("gereed");
});

$("goBtn").addEventListener("click", async () => {
  if (!current) return;
  const fmt = $("format").value;
  const opts = { format: fmt };
  if (radio("sizeMode") === "target") {
    if (!(+$("targetSize").value > 0)) { alert("Vul een doelgrootte in."); return; }
    opts.target_size = $("targetSize").value;
    opts.target_unit = $("targetUnit").value;
  } else {
    opts.quality = radio("quality");
  }
  const cat = current.category;
  if (cat === "video") {
    opts.height = $("height").value;
    opts.remove_audio = $("removeAudio").checked;
    opts.gif_width = $("gifWidth").value;
    opts.gif_fps = $("gifFps").value;
  }
  if (cat === "image") {
    opts.scale_percent = $("scalePct").value;
    opts.width = $("imgW").value;
    opts.height = $("imgH").value;
  }
  if (cat === "video" || cat === "audio") {
    const s = parseTime($("trimStart").value), e = parseTime($("trimEnd").value);
    if (Number.isNaN(s) || Number.isNaN(e) || (s != null && e != null && e <= s)) { alert("Controleer de knip-tijden."); return; }
    opts.trim_start = s; opts.trim_end = e;
    opts.fast_trim = $("fastTrim").checked && fmt === current.ext;
  }

  $("goBtn").disabled = true;
  $("goBtn").textContent = "[ BEZIG... ]";
  step(4);
  show($("result"), false);
  show($("progress"), true);
  setProgress(0, "Versturen…");
  try {
    const r = await fetch("/api/convert", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: current.id, options: opts }) });
    const job = await r.json();
    if (!r.ok) throw new Error(job.error || "Mislukt");
    await poll(job.id);
  } catch (err) {
    showError(err.message);
  } finally {
    $("goBtn").disabled = false;
    $("goBtn").textContent = "[ ▶ START ]";
  }
});

function setProgress(f, msg) {
  $("progBar").textContent = txtBar(f, barWidth());
  $("progMsg").textContent = "> " + msg.toLowerCase() + "...";
  status(msg.toLowerCase() + " " + Math.round(f * 100) + "%");
}

async function poll(id) {
  for (;;) {
    const r = await fetch("/api/job/" + id);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Taak kwijt");
    setProgress(j.progress, j.message);
    if (j.status === "done") return showResult(j);
    if (j.status === "error") throw new Error(j.error);
    await new Promise((res) => setTimeout(res, 700));
  }
}

function showResult(j) {
  show($("progress"), false);
  const res = $("result");
  res.className = "result";
  const diff = (j.size - j.original_size) / j.original_size * 100;
  const w = barWidth() - 8;
  const max = Math.max(j.size, j.original_size);
  const bar = (n) => { const k = Math.max(1, Math.round(n / max * w)); return "█".repeat(k) + "░".repeat(w - k); };
  const arrow = diff <= 0 ? "▼" : "▲";
  res.innerHTML = `<span class="head">STATUS: OK</span>
<div class="cmp"><span class="lbl">BESTAND   </span><span class="fn"></span>
<span class="lbl">ORIGINEEL </span>${bar(j.original_size)} ${human(j.original_size)}
<span class="lbl">NIEUW     </span>${bar(j.size)} ${human(j.size)}
<span class="lbl">VERSCHIL  </span><span class="down">${arrow} ${Math.abs(diff).toFixed(1)}% ${diff <= 0 ? "kleiner" : "groter"}</span></div>`;
  res.querySelector(".fn").textContent = j.filename;
  const a = document.createElement("a");
  a.className = "download";
  a.href = "/api/download/" + j.id;
  a.textContent = "[ ↓ DOWNLOAD ]";
  res.append(a);
  show(res, true);
  status(`klaar: ${j.filename} (${human(j.size)})`);
}

function showError(msg) {
  show($("progress"), false);
  const res = $("result");
  res.className = "result error";
  res.innerHTML = '<span class="head">!! FOUT</span>\n';
  res.append(document.createTextNode(msg));
  status("fout - zie melding");
  step(2);
  show(res, true);
}

// ---------- thema

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  document.querySelectorAll(".themes button").forEach((b) => b.classList.toggle("on", b.dataset.theme === t));
  try { localStorage.setItem("ac-theme", t); } catch {}
}
document.querySelectorAll(".themes button").forEach((b) => b.addEventListener("click", () => setTheme(b.dataset.theme)));
let savedTheme = "groen";
try { savedTheme = localStorage.getItem("ac-theme") || "groen"; } catch {}
setTheme(savedTheme);
