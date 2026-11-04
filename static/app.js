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
  // een .torrent-bestand op het sleepvak: torrent starten in plaats van converteren
  if (/\.torrent$/i.test(file.name)) { const fd = new FormData(); fd.append("file", file); return startTorrent(fd); }
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

// ---------- video ophalen via een link (yt-dlp, alleen lokale versie)
let activeJob = null;
// Een taak volgen tot hij klaar is; geeft de laatste status terug.
async function followJob(id, bar) {
  activeJob = id;
  show($("urlStop"), true);
  try {
    for (;;) {
      const rr = await fetch("/api/job/" + id);
      const j = await rr.json();
      if (!rr.ok) throw new Error(j.error || "Taak kwijt.");
      bar.textContent = txtBar(j.progress, barWidth());
      $("urlMsg").textContent = "> " + j.message.toLowerCase();
      $("urlMsg").classList.remove("err");
      show($("urlMsg"), true);
      status(j.message.toLowerCase() + " " + Math.round(j.progress * 100) + "%");
      if (j.status === "error") throw new Error(j.error);
      if (j.status === "done") return j;
      await new Promise((res) => setTimeout(res, 700));
    }
  } finally {
    activeJob = null;
    show($("urlStop"), false);
  }
}
$("urlStop").addEventListener("click", () => { if (activeJob) fetch(`/api/job/${activeJob}/cancel`, { method: "POST" }); });

// ---------- viruscontrole
function virusText(v) {
  if (!v) return "";
  const eng = v.local && v.local.engine ? v.local.engine : "geen lokale scanner";
  const vt = (v.files || []).find((f) => f.vt);
  const vtTxt = vt ? ` · virustotal: ${vt.vt.detail}` : "";
  if (v.status === "infected") return `!! VIRUS GEVONDEN (${eng}): ${v.local.status === "infected" ? v.local.detail : vt ? vt.vt.detail : ""}`;
  if (v.status === "clean") return `✓ geen virus gevonden (${eng})${vtTxt}`;
  return `? niet zeker: ${v.local.detail}${vtTxt}`;
}
function virusNode(v, jobId) {
  const p = document.createElement("p");
  p.className = "scan-msg " + (v.status === "infected" ? "bad" : v.status === "clean" ? "good" : "warn");
  p.textContent = virusText(v) + " ";
  const one = (v.files || [])[0];
  if (one && v.files.length === 1) {
    const a = document.createElement("a");
    a.href = one.virustotal; a.target = "_blank"; a.rel = "noopener"; a.textContent = "[ VIRUSTOTAL ]";
    a.className = "btn small"; p.append(a);
  }
  if (v.status === "infected" && jobId) {
    const del = document.createElement("button");
    del.className = "btn small"; del.type = "button"; del.textContent = "[ VERWIJDEREN ]";
    del.addEventListener("click", async () => {
      await fetch(`/api/job/${jobId}/delete`, { method: "POST" });
      p.textContent = "// verwijderd van de schijf.";
      show($("torrentFiles"), false);
    });
    p.append(del);
  }
  return p;
}
function showScan(v) {
  const m = $("scanMsg");
  m.replaceWith(Object.assign(virusNode(v), { id: "scanMsg" }));
}
$("scanBtn").addEventListener("click", async () => {
  if (!current) return;
  $("scanBtn").disabled = true; $("scanBtn").textContent = "[ SCANNEN... ]";
  try {
    const r = await fetch("/api/scan/" + current.id, { method: "POST" });
    const v = await r.json();
    if (!r.ok) throw new Error(v.error || "Scan mislukt.");
    showScan(v);
  } catch (err) {
    const m = $("scanMsg"); m.className = "scan-msg bad"; m.textContent = "!! " + err.message;
  } finally {
    $("scanBtn").disabled = false; $("scanBtn").textContent = "[ VIRUSSCAN ]";
  }
});
fetch("/api/settings").then((r) => r.json()).then((s) => {
  $("scannerInfo").textContent = s.scanner
    ? `// gevonden scanner op deze computer: ${s.scanner}.`
    : "// geen virusscanner gevonden. windows: microsoft defender staat er standaard op. mac/linux: installeer clamav (brew install clamav / sudo apt install clamav).";
  if (s.vt_key_set) $("vtKey").placeholder = "sleutel opgeslagen ✓ (leeg laten = houden)";
}).catch(() => {});
$("vtSave").addEventListener("click", async () => {
  const r = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vt_key: $("vtKey").value.trim() }) });
  const j = await r.json();
  $("vtKey").value = "";
  $("vtKey").placeholder = r.ok ? (j.vt_key_set ? "sleutel opgeslagen ✓" : "sleutel verwijderd") : j.error;
});

// ---------- torrents (magnet-link of .torrent-bestand)
async function startTorrent(body) {
  const bar = $("urlBar"), msg = $("urlMsg");
  $("urlBtn").disabled = true; $("torrentBtn").disabled = true;
  show($("torrentFiles"), false); show(bar, true);
  bar.textContent = txtBar(0, barWidth());
  try {
    const scan = $("urlScan").checked;
    if (body instanceof FormData) body.append("scan", scan ? "1" : "0"); else body.scan = scan;
    const r = await fetch("/api/torrent", body instanceof FormData ? { method: "POST", body }
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j0 = await r.json();
    if (!r.ok) throw new Error(j0.error || "Torrent starten mislukt.");
    const j = await followJob(j0.id, bar);
    show(bar, false);
    $("urlInput").value = "";
    if (j.virus && j.virus.status === "infected") return showTorrentFiles(j);
    if (j.files.length === 1) return openTorrentFile(j.id, j.files[0].idx, j.virus);
    showTorrentFiles(j);
  } catch (err) {
    show(bar, false);
    msg.textContent = "!! " + err.message;
    msg.classList.add("err");
    show(msg, true);
    status("torrent mislukt");
  } finally {
    $("urlBtn").disabled = false; $("torrentBtn").disabled = false;
  }
}
function showTorrentFiles(j) {
  const box = $("torrentFiles");
  box.innerHTML = "";
  const head = document.createElement("p");
  head.className = "tor-head";
  const total = j.files.reduce((a, f) => a + f.size, 0);
  head.textContent = `TORRENT KLAAR: ${j.name} · ${j.files.length} bestanden · ${human(total)}`;
  box.append(head);
  const infected = j.virus && j.virus.status === "infected";
  if (j.virus) box.append(virusNode(j.virus, j.id));
  j.files.forEach((f, i) => {
    const row = document.createElement("div");
    row.className = "tor-row";
    const last = i === j.files.length - 1;
    row.innerHTML = `<span class="tor-pre">${last ? "└─" : "├─"}</span><span class="tor-name"></span><span class="tor-size"></span>` +
      `<button type="button" class="btn small" data-open>[ OPENEN ]</button><a class="btn small" data-dl>[↓]</a>`;
    row.querySelector(".tor-name").textContent = f.path;
    row.querySelector(".tor-name").title = f.path;
    row.querySelector(".tor-size").textContent = human(f.size);
    row.querySelector("[data-dl]").href = `/api/torrent/${j.id}/file/${f.idx}`;
    row.querySelector("[data-open]").addEventListener("click", () => openTorrentFile(j.id, f.idx, j.virus));
    if (infected) { row.querySelector("[data-open]").remove(); row.querySelector("[data-dl]").remove(); }
    box.append(row);
  });
  show(box, true);
  $("urlMsg").textContent = "// [ OPENEN ] zet een bestand in de converter; [↓] slaat het op.";
  status("torrent klaar");
}
async function openTorrentFile(jobId, idx, v) {
  const r = await fetch(`/api/torrent/${jobId}/open/${idx}`, { method: "POST" });
  const data = r.ok ? await r.json() : { error: r.status === 403 ? "Geblokkeerd: er is een virus gevonden." : "Openen mislukt." };
  if (!r.ok) { $("urlMsg").textContent = "!! " + data.error; return; }
  localFile = null;
  setup(data);
  if (v) showScan(v);
}
$("torrentBtn").addEventListener("click", () => $("torrentInput").click());
$("torrentInput").addEventListener("change", () => {
  const f = $("torrentInput").files[0];
  if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  $("torrentInput").value = "";
  startTorrent(fd);
});

$("urlForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("urlInput").value.trim();
  const bar = $("urlBar"), msg = $("urlMsg");
  if (!url) { $("urlInput").focus(); return; }
  if (/^magnet:\?/i.test(url)) return startTorrent({ magnet: url });
  $("urlBtn").disabled = true; $("urlBtn").textContent = "[ BEZIG... ]";
  show(msg, false); show(bar, true);
  bar.textContent = txtBar(0, barWidth());
  status("link ophalen...");
  try {
    const r = await fetch("/api/fetch", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, audio_only: $("urlAudio").checked, scan: $("urlScan").checked }) });
    const j0 = await r.json();
    if (!r.ok) throw new Error(j0.error || "Ophalen mislukt.");
    const j = await followJob(j0.id, bar);
    if (j.virus && j.virus.status === "infected") {
      show(bar, false);
      msg.replaceChildren(virusNode(j.virus, j.id));
      msg.classList.add("err");
      status("virus gevonden - niet geopend");
      return;
    }
    localFile = null;
    $("urlInput").value = "";
    show(bar, false);
    setup(j.upload);
    if (j.virus) showScan(j.virus);
  } catch (err) {
    show(bar, false);
    msg.textContent = "!! " + err.message;
    msg.classList.add("err");
    show(msg, true);
    status("ophalen mislukt");
  } finally {
    $("urlBtn").disabled = false; $("urlBtn").textContent = "[ OPHALEN ]";
  }
});

// ---------- opties opbouwen
function setup(data) {
  current = data;
  $("scanMsg").className = "scan-msg hidden"; $("scanMsg").textContent = "";
  show(drop, false);
  show($("urlForm"), false);
  // opgehaald via een link: origineel ook los op te slaan
  $("saveSrc").href = "/api/file/" + data.id + "?download=1";
  show($("saveSrc"), !localFile);
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
  for (const el of [v, a]) { if (el.src.startsWith("blob:")) URL.revokeObjectURL(el.src); el.removeAttribute("src"); show(el, false); }
  if (!["video", "audio"].includes(data.category)) return;
  const el = data.category === "video" ? v : a;
  el.src = localFile ? URL.createObjectURL(localFile) : "/api/file/" + data.id;
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
  show($("panel"), false); show(drop, true); show($("urlForm"), true);
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

// ---------- desktop-app: afsluiten, terminal, eigen venster
fetch("/api/ping").then((r) => r.json()).then((p) => {
  $("verLabel").textContent = "VER " + p.version.split(".").slice(0, 2).join(".");
  if (!p.desktop) return;
  $("modeLabel").textContent = "DESKTOP-APP";
  show($("termBtn"), true);
  // In een eigen venster sluit je het programma gewoon met het venster.
  show($("quitBtn"), !p.window || p.window === "browser");
}).catch(() => {});
$("quitBtn").addEventListener("click", async () => {
  try { await fetch("/api/quit", { method: "POST" }); } catch {}
  document.querySelector("main").innerHTML =
    '<pre class="logo-off">\n  ┌──────────────────────────────────────┐\n  │  ANYTHING CONVERTER IS AFGESLOTEN.   │\n  │  je kunt dit tabblad nu sluiten.     │\n  └──────────────────────────────────────┘</pre>';
});
$("termBtn").addEventListener("click", async () => {
  status("terminalversie openen…");
  try {
    const r = await fetch("/api/terminal", { method: "POST" });
    const j = await r.json();
    status(j.ok ? "terminalversie geopend in een nieuw venster" : j.error);
  } catch { status("terminalversie openen lukte niet"); }
});

// Eigen programmavenster (pywebview): downloads via een "Bewaar als"-venster, links naar buiten
// in de gewone browser, de PDF- en archief-werkbank in een tweede venster.
const nativeApi = () => window.pywebview && window.pywebview.api;
document.addEventListener("click", async (e) => {
  const a = e.target.closest && e.target.closest("a[href]");
  const api = nativeApi();
  if (!a || !api || e.defaultPrevented) return;
  const u = new URL(a.href, location.href);
  if (u.protocol === "blob:" || u.protocol === "data:" || u.hash && u.pathname === location.pathname) return;
  if (u.origin !== location.origin) { e.preventDefault(); api.open_external(u.href); return; }
  if (u.pathname.startsWith("/web/")) { e.preventDefault(); api.open_window(u.pathname + u.search); return; }
  if (a.hasAttribute("download") || /^\/api\/(download|file|torrent)\//.test(u.pathname)) {
    e.preventDefault();
    status("opslaan…");
    const r = await api.save_url(u.pathname + u.search);
    status(r.path ? "opgeslagen: " + r.path : r.cancelled ? "opslaan geannuleerd" : "opslaan mislukt: " + r.error);
  }
}, true);

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
