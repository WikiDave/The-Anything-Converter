"use strict";
const $ = (id) => document.getElementById(id);
const AUDIO_OUT = ["mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "aiff", "wma", "m4r", "mmf"];
const LOSSLESS_AUDIO = ["wav", "flac", "aiff", "mmf"];
const TEXT_OUT = ["txt", "srt", "vtt"];
let presetFormat = null; // gekozen via het gereedschap (bijv. "PDF to Word")
// Uitleg achter het formaat in de keuzelijst
const FMT_LABEL = {
  docx: "Word", doc: "Word 97-2003", odt: "OpenDocument text", xlsx: "Excel", xls: "Excel 97-2003",
  ods: "OpenDocument spreadsheet", iso: "ISO (datatrack)", cue: "one BIN + CUE (merged)", wav: "WAV",
  chd: "CHD (compact, for RetroArch/MAME/DuckStation)", cso: "CSO (PSP, compressed)", z64: "N64 big-endian",
  v64: "N64 byteswapped", n64: "N64 little-endian", sfc: "SNES without copier header", smc: "SNES with copier header",
  nds: "trimmed", patch: "apply patch (IPS/UPS/BPS)", zip: "zip", bin: "Mega Drive (plain)", pptx: "PowerPoint", ppt: "PowerPoint 97-2003", odp: "OpenDocument presentation",
  rtf: "Rich Text", txt: "plain text", html: "web page", xml: "XML", md: "Markdown", csv: "CSV",
  epub: "e-book", mobi: "Kindle (old)", azw3: "Kindle", fb2: "FictionBook", lit: "Microsoft Reader",
  lrf: "Sony Reader", pdb: "Palm", tcr: "Psion", pdf: "PDF", svg: "SVG (vector wrapper)", eps: "PostScript",
  tga: "Targa", wbmp: "WAP bitmap", exr: "OpenEXR (HDR)", hdr: "Radiance HDR", ico: "icon / favicon",
  m4r: "iPhone ringtone", mmf: "ringtone (SMAF)", wma: "Windows Media Audio", aiff: "Apple audio",
  wmv: "Windows Media Video", flv: "Flash video", mpg: "MPEG-2", ogv: "Ogg video", "3gp": "old phones",
  "3g2": "old phones", srt: "subtitles", vtt: "subtitles (web)", "7z": "7-Zip",
  "uitpakken": "extract (original file)", "json-mooi": "JSON, neatly indented", "yaml-mooi": "YAML, tidy", "xml-mooi": "XML, neatly indented", "sql": "SQL dump", "py": "Python", "plist": "macOS plist", "lrc": "lyrics", "sbv": "YouTube subtitles", "ttml": "XML subtitles", "ass": "styled subtitles", "m3u8": "playlist (UTF-8)", "pls": "playlist", "xspf": "playlist (XML)", "wpl": "Windows playlist", "kml": "Google Earth", "kmz": "Google Earth (zip)", "gpx": "GPS route", "geojson": "geodata", "tcx": "Garmin", "stl": "3D printing", "obj": "3D model", "ply": "3D model / scan", "glb": "3D for web/AR", "off": "3D model", "3mf": "3D print project", "woff": "web font", "woff2": "web font (small)", "ttf": "TrueType", "otf": "OpenType", "pem": "text (PEM)", "der": "binary (DER)", "eml": "e-mail message", "qcow2": "QEMU/Proxmox", "vmdk": "VMware", "vdi": "VirtualBox", "vhdx": "Hyper-V", "vhd": "Hyper-V (old)", "raw": "raw disk", "cbz": "comic book", "yaml": "YAML", "toml": "TOML", "json": "JSON", "eac3": "Dolby Digital Plus", "ac3": "Dolby Digital", "wv": "WavPack (lossless)", "tta": "True Audio (lossless)", "au": "Unix audio", "caf": "Apple Core Audio", "mka": "Matroska audio", "m4b": "audiobook", "spx": "Speex speech", "alac": "Apple Lossless (.m4a)", "m4v": "Apple video", "asf": "Windows Media", "ts": "MPEG transport stream", "m2ts": "Blu-ray/AVCHD", "mxf": "broadcast", "divx": "DivX", "rapport": "info report",
};
function fmtLabel(cat, t) {
  if (TEXT_OUT.includes(t) && (cat === "video" || cat === "audio")) return t === "txt" ? "speech to text" : "speech to subtitles";
  if (cat === "image" && ["txt", "docx", "rtf", "xlsx"].includes(t)) return "recognise text (OCR) → " + (FMT_LABEL[t] || t);
  if (cat === "pdf" && t === "pdf") return "compress / shrink PDF";
  if (cat === "disc" && t === "wav") return "audio tracks as WAV";
  if (cat === "rom" && t === "md") return "Mega Drive (plain)";
  if (cat === "info" && t === "txt") return "info report (what it is, details, checksums)";
  if (["archive2", "compressed", "vmdisk"].includes(cat) && t === "txt") return "list of contents";
  if (cat === "text" && t === "png") return "as an image (e.g. NFO art)";
  if (cat === "text" && t === "html") return "web page with colours";
  if (cat === "pdf" && ["png", "jpg"].includes(t)) return "every page as an image";
  return FMT_LABEL[t] || "";
}
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
  if (e.dataTransfer.files.length) upload(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => fileInput.files.length && upload(fileInput.files));

// Meerdere bestanden die bij elkaar horen (CUE + BIN's, ROM + patch) gaan samen; anders alleen het eerste.
const BELONG = /\.(cue|gdi|ccd|mds|ips|ups|bps)$/i;
function upload(fileOrList) {
  const list = fileOrList instanceof File ? [fileOrList] : [...fileOrList];
  const together = list.length > 1 && list.some((f) => BELONG.test(f.name));
  const file = list[0];
  if (together) return uploadFiles(list, list.find((f) => /\.(cue|gdi|ccd|mds)$/i.test(f.name)) || list.find((f) => !BELONG.test(f.name)) || file);
  return uploadFiles([file], file);
}
function uploadFiles(files, file) {
  // een .torrent-bestand op het sleepvak: torrent starten in plaats van converteren
  if (/\.torrent$/i.test(file.name)) { const fd = new FormData(); fd.append("file", file); return startTorrent(fd); }
  localFile = files.length === 1 ? file : null;
  const bar = $("uploadBar");
  show(bar, true);
  bar.textContent = txtBar(0, barWidth());
  status("uploaden: " + file.name);
  const fd = new FormData();
  for (const f of files) fd.append("file", f);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) bar.textContent = txtBar(e.loaded / e.total, barWidth()); };
  xhr.onload = () => {
    show(bar, false);
    let data;
    try { data = JSON.parse(xhr.responseText); } catch { data = { error: "Upload failed." }; }
    if (xhr.status !== 200) { status("ERROR: " + (data.error || "upload failed")); alert(data.error || "Upload failed."); return; }
    setup(data);
  };
  xhr.onerror = () => { show(bar, false); alert("Upload failed (connection)."); };
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
  const eng = v.local && v.local.engine ? v.local.engine : "no local scanner";
  const vt = (v.files || []).find((f) => f.vt);
  const vtTxt = vt ? ` · virustotal: ${vt.vt.detail}` : "";
  if (v.status === "infected") return `!! VIRUS FOUND (${eng}): ${v.local.status === "infected" ? v.local.detail : vt ? vt.vt.detail : ""}`;
  if (v.status === "clean") return `✓ no virus found (${eng})${vtTxt}`;
  return `? not sure: ${v.local.detail}${vtTxt}`;
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
    del.className = "btn small"; del.type = "button"; del.textContent = "[ DELETE ]";
    del.addEventListener("click", async () => {
      await fetch(`/api/job/${jobId}/delete`, { method: "POST" });
      p.textContent = "// deleted from the disk.";
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
    if (!r.ok) throw new Error(v.error || "Scan failed.");
    showScan(v);
  } catch (err) {
    const m = $("scanMsg"); m.className = "scan-msg bad"; m.textContent = "!! " + err.message;
  } finally {
    $("scanBtn").disabled = false; $("scanBtn").textContent = "[ VIRUS SCAN ]";
  }
});
fetch("/api/settings").then((r) => r.json()).then((s) => {
  $("scannerInfo").textContent = s.scanner
    ? `// scanner found on this computer: ${s.scanner}.`
    : "// no virus scanner found. windows: microsoft defender is built in. mac/linux: install clamav (brew install clamav / sudo apt install clamav).";
  if (s.vt_key_set) $("vtKey").placeholder = "key saved ✓ (leave empty = keep)";
}).catch(() => {});
$("vtSave").addEventListener("click", async () => {
  const r = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vt_key: $("vtKey").value.trim() }) });
  const j = await r.json();
  $("vtKey").value = "";
  $("vtKey").placeholder = r.ok ? (j.vt_key_set ? "key saved ✓" : "key removed") : j.error;
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
    if (!r.ok) throw new Error(j0.error || "Starting the torrent failed.");
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
    status("torrent failed");
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
  head.textContent = `TORRENT DONE: ${j.name} · ${j.files.length} files · ${human(total)}`;
  box.append(head);
  const infected = j.virus && j.virus.status === "infected";
  if (j.virus) box.append(virusNode(j.virus, j.id));
  j.files.forEach((f, i) => {
    const row = document.createElement("div");
    row.className = "tor-row";
    const last = i === j.files.length - 1;
    row.innerHTML = `<span class="tor-pre">${last ? "└─" : "├─"}</span><span class="tor-name"></span><span class="tor-size"></span>` +
      `<button type="button" class="btn small" data-open>[ OPEN ]</button><a class="btn small" data-dl>[↓]</a>`;
    row.querySelector(".tor-name").textContent = f.path;
    row.querySelector(".tor-name").title = f.path;
    row.querySelector(".tor-size").textContent = human(f.size);
    row.querySelector("[data-dl]").href = `/api/torrent/${j.id}/file/${f.idx}`;
    row.querySelector("[data-open]").addEventListener("click", () => openTorrentFile(j.id, f.idx, j.virus));
    if (infected) { row.querySelector("[data-open]").remove(); row.querySelector("[data-dl]").remove(); }
    box.append(row);
  });
  show(box, true);
  $("urlMsg").textContent = "// [ OPEN ] puts a file in the converter; [↓] saves it.";
  status("torrent done");
}
async function openTorrentFile(jobId, idx, v) {
  const r = await fetch(`/api/torrent/${jobId}/open/${idx}`, { method: "POST" });
  const data = r.ok ? await r.json() : { error: r.status === 403 ? "Blocked: a virus was found." : "Opening failed." };
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
  $("urlBtn").disabled = true; $("urlBtn").textContent = "[ BUSY... ]";
  show(msg, false); show(bar, true);
  bar.textContent = txtBar(0, barWidth());
  status("fetching link...");
  try {
    const r = await fetch("/api/fetch", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, audio_only: $("urlAudio").checked, scan: $("urlScan").checked }) });
    const j0 = await r.json();
    if (!r.ok) throw new Error(j0.error || "Download failed.");
    const j = await followJob(j0.id, bar);
    if (j.virus && j.virus.status === "infected") {
      show(bar, false);
      msg.replaceChildren(virusNode(j.virus, j.id));
      msg.classList.add("err");
      status("virus found - not opened");
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
    status("download failed");
  } finally {
    $("urlBtn").disabled = false; $("urlBtn").textContent = "[ DOWNLOAD ]";
  }
});

// ---------- opties opbouwen
function setup(data) {
  current = data;
  $("scanMsg").className = "scan-msg hidden"; $("scanMsg").textContent = "";
  show(drop, false);
  show($("urlForm"), false); show($("sampleBox"), false);
  show($("tools"), false);
  show($("hashBox"), false);
  // opgehaald via een link: origineel ook los op te slaan
  $("saveSrc").href = "/api/file/" + data.id + "?download=1";
  show($("saveSrc"), !localFile);
  show($("panel"), true);
  show($("result"), false);
  show($("progress"), false);
  step(2);
  status(`loaded: ${data.name} [${data.label.toLowerCase()}]`);

  $("fName").textContent = data.name;
  const meta = [data.label, human(data.size)];
  const i = data.info || {};
  if (i.width) meta.push(`${i.width}×${i.height}`);
  if (i.duration && data.category !== "image") meta.push(fmtTime(i.duration));
  if (i.files && i.files.length) meta.push("+ " + i.files.join(", "));
  if (i.kind) meta.push(i.kind);
  if (i.real_ext) meta.push("actually ." + i.real_ext);
  $("fMeta").textContent = meta.join(" · ");
  duration = i.duration || 0;

  const sel = $("format");
  sel.innerHTML = "";
  for (const t of data.targets) {
    const o = document.createElement("option");
    o.value = t;
    const lbl = fmtLabel(data.category, t);
    o.textContent = "." + t + (lbl ? "  · " + lbl : "") + (t === data.ext || (t === "jpg" && data.ext === "jpeg") ? "  (same format)" : "");
    sel.appendChild(o);
  }
  const same = data.targets.find((t) => t === data.ext || (t === "jpg" && data.ext === "jpeg"));
  sel.value = (presetFormat && data.targets.includes(presetFormat)) ? presetFormat : (same || data.targets[0]);
  presetFormat = null;

  // reset velden
  for (const id of ["targetSize", "scalePct", "imgW", "imgH", "gifWidth", "gifFps", "trimStart", "trimEnd"]) $(id).value = "";
  $("removeAudio").checked = false; $("fastTrim").checked = false; $("height").value = ""; $("device").value = "";
  document.querySelectorAll("#avBox input, #avBox select").forEach((el) => (el.value = ""));
  $("avSource").textContent = ""; mediaInfoFor = null;
  document.querySelector("input[name=sizeMode][value=quality]").checked = true;

  setupPreview(data);
  refresh();
  if (hashAfterUpload) { hashAfterUpload = false; runHash(); }
  show($("editBtn"), !!(data.info && data.info.edit));
  show($("dbBtn"), !!(data.info && data.info.db));
  show($("editBox"), false); show($("dbBox"), false);
  if (afterUpload === "edit" && data.info && data.info.edit) openEditor();
  if (afterUpload === "db" && data.info && data.info.db) openDb();
  afterUpload = null;
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
  const speech = isMedia && TEXT_OUT.includes(fmt);
  const textual = speech || (cat === "image" && ["txt", "docx", "rtf", "xlsx", "svg", "wbmp", "exr", "hdr", "eps", "tga"].includes(fmt)) ||
    (cat === "pdf" && fmt !== "pdf" && !["png", "jpg"].includes(fmt)) || (cat === "ebook" && fmt !== "pdf") ||
    cat === "disc" || cat === "rom" || !["video", "audio", "image", "pdf", "document", "spreadsheet",
      "presentation", "archive", "other"].includes(cat);
  const toVideo = cat === "video" && !AUDIO_OUT.includes(fmt) && fmt !== "gif" && !speech;
  const target = radio("sizeMode") === "target";

  const sizeable = (isMedia && !LOSSLESS_AUDIO.includes(fmt)) ||
    (cat === "image" && !["ico", "pdf"].includes(fmt)) ||
    fmt === "pdf" || ["archive", "other"].includes(cat);
  show($("sizeField"), !textual && (sizeable || isMedia || cat === "image"));
  show($("speechBox"), speech);
  document.querySelector("input[name=sizeMode][value=target]").disabled = !sizeable;
  if (!sizeable && target) document.querySelector("input[name=sizeMode][value=quality]").checked = true;

  const t = radio("sizeMode") === "target";
  show($("targetBox"), t);
  show($("qualityBox"), !t && !(cat === "audio" && LOSSLESS_AUDIO.includes(fmt)));
  show($("videoBox"), toVideo);
  const avOn = (toVideo || (isMedia && AUDIO_OUT.includes(fmt))) && !speech;
  show($("avBox"), avOn);
  document.querySelectorAll("#avBox .av-video").forEach((el) => show(el, toVideo));
  if (avOn) loadMediaInfo();
  show($("gifBox"), cat === "video" && fmt === "gif");
  show($("imageBox"), cat === "image" && !textual);
  show($("trimBox"), isMedia);
  $("fastTrim").parentElement.classList.toggle("hidden", fmt !== current.ext);

  let hint = "";
  if (cat === "video" && fmt !== "gif") hint = "Larger than the original works too: the bitrate is raised.";
  if (cat === "image") hint = "Smaller: lower quality and/or resolution. Larger: higher quality and resolution.";
  if (["archive", "other"].includes(cat)) hint = "Lossless packing; already compressed files barely get smaller.";
  if (cat === "pdf" || fmt === "pdf") hint = "PDFs get smaller by rescaling and compressing their images.";
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
  $("trimLen").textContent = sel ? fmtTime(sel.len) + (duration ? ` of ${fmtTime(duration)}` : "") : "ongeldig";
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
  show($("panel"), false); show(drop, true); show($("urlForm"), true); show($("tools"), true); show($("sampleBox"), true);
  step(1); status("ready");
});

$("goBtn").addEventListener("click", async () => {
  if (!current) return;
  const fmt = $("format").value;
  const opts = { format: fmt };
  if (radio("sizeMode") === "target") {
    if (!(+$("targetSize").value > 0)) { alert("Enter a target size."); return; }
    opts.target_size = $("targetSize").value;
    opts.target_unit = $("targetUnit").value;
  } else {
    opts.quality = radio("quality");
  }
  const cat = current.category;
  if (cat === "video") {
    opts.height = $("height").value;
    opts.remove_audio = $("removeAudio").checked;
    opts.device = $("device").value;
    opts.gif_width = $("gifWidth").value;
    opts.gif_fps = $("gifFps").value;
  }
  if ((cat === "video" || cat === "audio") && !$("avBox").classList.contains("hidden")) {
    Object.assign(opts, {
      vcodec: $("avVcodec").value, fps: $("avFps").value, video_bitrate: $("avVbr").value, crf: $("avCrf").value,
      preset: $("avPreset").value, pix_fmt: $("avPix").value, streams: $("avStreams").value, hw: $("avHw").value,
      acodec: $("avAcodec").value, audio_bitrate: $("avAbr").value, sample_rate: $("avRate").value,
      channels: $("avCh").value, volume: $("avVol").value, metadata: $("avMeta").value,
      meta_title: $("metaTitle").value, meta_artist: $("metaArtist").value, meta_album: $("metaAlbum").value,
      meta_date: $("metaDate").value, meta_comment: $("metaComment").value,
    });
    if (cat === "video" && $("avW").value) opts.width = $("avW").value;
    if (cat === "video" && $("avH").value) opts.height = $("avH").value;
  }
  if (cat === "image") {
    opts.scale_percent = $("scalePct").value;
    opts.width = $("imgW").value;
    opts.height = $("imgH").value;
  }
  if (cat === "video" || cat === "audio") {
    const s = parseTime($("trimStart").value), e = parseTime($("trimEnd").value);
    if (Number.isNaN(s) || Number.isNaN(e) || (s != null && e != null && e <= s)) { alert("Check the trim times."); return; }
    opts.trim_start = s; opts.trim_end = e;
    if (TEXT_OUT.includes(fmt)) {
      opts.language = $("speechLang").value;
      opts.speech_model = $("speechModel").value;
      opts.translate = $("speechTranslate").checked;
    }
    opts.fast_trim = $("fastTrim").checked && fmt === current.ext;
  }

  $("goBtn").disabled = true;
  $("goBtn").textContent = "[ BUSY... ]";
  step(4);
  show($("result"), false);
  show($("progress"), true);
  setProgress(0, "Versturen…");
  try {
    const r = await fetch("/api/convert", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: current.id, options: opts }) });
    const job = await r.json();
    if (!r.ok) throw new Error(job.error || "Failed");
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
<div class="cmp"><span class="lbl">FILE      </span><span class="fn"></span>
<span class="lbl">ORIGINAL  </span>${bar(j.original_size)} ${human(j.original_size)}
<span class="lbl">NEW       </span>${bar(j.size)} ${human(j.size)}
<span class="lbl">CHANGE    </span><span class="down">${arrow} ${Math.abs(diff).toFixed(1)}% ${diff <= 0 ? "smaller" : "larger"}</span></div>`;
  res.querySelector(".fn").textContent = j.filename;
  const a = document.createElement("a");
  a.className = "download";
  a.href = "/api/download/" + j.id;
  a.textContent = "[ ↓ DOWNLOAD ]";
  res.append(a);
  if (/\.(txt|srt|vtt)$/i.test(j.filename)) {
    // herkende tekst meteen laten zien
    fetch("/api/download/" + j.id).then((r) => r.text()).then((t) => {
      const pre = document.createElement("textarea");
      pre.className = "text-preview"; pre.readOnly = true; pre.rows = 10;
      pre.value = t.length > 50000 ? t.slice(0, 50000) + "\n…" : t;
      res.append(pre);
    }).catch(() => {});
  }
  show(res, true);
  status(`done: ${j.filename} (${human(j.size)})`);
}

function showError(msg) {
  show($("progress"), false);
  const res = $("result");
  res.className = "result error";
  res.innerHTML = '<span class="head">!! ERROR</span>\n';
  res.append(document.createTextNode(msg));
  status("error - see message");
  step(2);
  show(res, true);
}

// ---------- desktop-app: afsluiten, terminal, eigen venster
fetch("/api/ping").then((r) => r.json()).then((p) => {
  $("verLabel").textContent = "VER " + p.version;
  fetch("/api/update").then((r) => r.json()).then((u) => {
    if (!u.newer) return;
    const a = document.createElement("a");
    a.className = "btn small update-btn"; a.href = u.url; a.target = "_blank"; a.rel = "noopener";
    a.textContent = `[ UPDATE ${u.latest} AVAILABLE ]`;
    a.title = "You have " + u.current + ". Download the new version (your settings are kept).";
    $("verLabel").after(a);
  }).catch(() => {});
  if (!p.desktop) return;
  // Files from "Open with" / right-click > Convert with Anything Converter
  const takePending = async () => {
    try {
      const r = await fetch("/api/pending");
      const d = await r.json();
      const ok = (d.files || []).filter((f) => !f.error);
      (d.files || []).filter((f) => f.error).forEach((f) => status("ERROR: " + f.error));
      if (ok.length) {
        localFile = null;
        setup(ok[0]);
        if (ok.length > 1) status(`opened ${ok[0].name}; ${ok.length - 1} more file(s) were given: open them one by one`);
      }
    } catch {}
  };
  takePending();
  setInterval(takePending, 1500);
  $("modeLabel").textContent = "DESKTOP-APP";
  show($("termBtn"), true);
  document.querySelectorAll('.tool[data-fmt="drives"]').forEach((b) => b.classList.remove("hidden"));
  // In een eigen venster sluit je het programma gewoon met het venster.
  show($("quitBtn"), !p.window || p.window === "browser");
}).catch(() => {});
$("quitBtn").addEventListener("click", async () => {
  try { await fetch("/api/quit", { method: "POST" }); } catch {}
  document.querySelector("main").innerHTML =
    '<pre class="logo-off">\n  ┌──────────────────────────────────────┐\n  │  ANYTHING CONVERTER HAS BEEN CLOSED. │\n  │  you can close this tab now.         │\n  └──────────────────────────────────────┘</pre>';
});
$("termBtn").addEventListener("click", async () => {
  status("opening the terminal version…");
  try {
    const r = await fetch("/api/terminal", { method: "POST" });
    const j = await r.json();
    status(j.ok ? "terminal version opened in a new window" : j.error);
  } catch { status("could not open the terminal version"); }
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
    status("saving…");
    const r = await api.save_url(u.pathname + u.search);
    status(r.path ? "opgeslagen: " + r.path : r.cancelled ? "saving cancelled" : "saving failed: " + r.error);
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


// ---------- gereedschap: snelle keuzes (zoals "PDF to Word")
const OFFICE = ".doc,.docx,.odt", SHEET = ".xls,.xlsx,.ods,.csv", SLIDES = ".ppt,.pptx,.odp";
const MEDIA = "audio/*,video/*,.mkv,.flac,.opus,.m4a,.wma,.amr";
const TOOLS = [
  ["PDF", "DOC", "PDF to Word", ".pdf", "docx"], ["PDF", "XLS", "PDF to Excel", ".pdf", "xlsx"],
  ["PDF", "PPT", "PDF to PPT", ".pdf", "pptx"], ["PDF", "PNG", "PDF to PNG", ".pdf", "png"],
  ["PDF", "JPG", "PDF to JPEG", ".pdf", "jpg"], ["PDF", "RTF", "PDF to RTF", ".pdf", "rtf"],
  ["PDF", "TXT", "PDF to TXT", ".pdf", "txt"], ["PDF", "HTM", "PDF to HTML", ".pdf", "html"],
  ["PDF", "XML", "PDF to XML", ".pdf", "xml"], ["DOC", "PDF", "Word to PDF", OFFICE, "pdf"],
  ["XLS", "PDF", "Excel to PDF", SHEET, "pdf"], ["PPT", "PDF", "PPT to PDF", SLIDES, "pdf"],
  ["IMG", "PDF", "Image to PDF", "image/*,.heic,.heif", "pdf"], ["RTF", "PDF", "RTF to PDF", ".rtf", "pdf"],
  ["TXT", "PDF", "TXT to PDF", ".txt,.md", "pdf"], ["PDF", "+", "Merge PDFs", null, "web:pdf"],
  ["PDF", "÷", "Split PDF", null, "web:pdf"], ["PDF", "▼", "Compress PDF", ".pdf", "pdf"],
  ["IMG", "TXT", "File OCR", "image/*,.pdf", "txt"], ["[▢]", "TXT", "Screenshot-OCR", null, "screen"],
  ["♪", "TXT", "Audio/video to text", MEDIA, "txt"], ["▶", "SRT", "Make subtitles", MEDIA, "srt"],
  ["DOC", "EPUB", "Make e-book", ".doc,.docx,.odt,.txt,.md,.html,.pdf,.epub", "epub"],
  ["EPUB", "AZW", "E-book for Kindle", ".epub,.mobi,.fb2,.pdf,.docx", "azw3"],
  ["♪", "M4R", "iPhone ringtone", MEDIA, "m4r"], ["WWW", "PDF", "Website to PDF", null, "web"],
  ["BIN", "ISO", "CUE/BIN to ISO", ".cue,.bin,.img,.ccd,.mdf,.mds,.nrg,.zip,.7z", "iso"],
  ["BIN", "1×", "Merge BIN tracks", ".cue,.bin,.zip,.7z", "cue"],
  ["ISO", "CHD", "To CHD (RetroArch)", ".cue,.bin,.iso,.gdi,.zip,.7z", "chd"],
  ["ISO", "CSO", "PSP ISO to CSO", ".iso,.cso", "cso"],
  ["ROM", "IPS", "Patch ROM", "*", "patch"],
  ["N64", "Z64", "Convert N64 ROM", ".n64,.v64,.z64", "z64"],
  ["#", "SHA", "Checksum / hash", "*", "hash"],
  ["TXT", "✎", "Edit text", "*", "edit"], ["+", "TXT", "New text file", null, "newtext"],
  ["SQL", "▦", "Open database", ".sqlite,.sqlite3,.db,.db3,.sql,.csv,.tsv,.xlsx,.dbf,.json", "db"],
  ["USB", "HDD", "Drives: health / format", null, "drives"], ["+", "DB", "New database", null, "newdb"], ["*", "ZIP", "Pack (zip, 7z)", "*", "zip"],
];
(function buildTools() {
  const grid = $("toolGrid");
  for (const [a, b, label, accept, fmt] of TOOLS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tool";
    btn.innerHTML = '<span class="ticon"><span class="t1"></span><span class="t2"></span></span><span class="tlabel"></span>';
    btn.querySelector(".t1").textContent = a;
    btn.querySelector(".t2").textContent = b;
    btn.querySelector(".tlabel").textContent = label;
    btn.dataset.fmt = fmt;
    if (fmt === "drives") btn.classList.add("hidden");
    btn.addEventListener("click", () => runTool(accept, fmt, label));
    grid.append(btn);
  }
})();

let hashAfterUpload = false;
let afterUpload = null; // "edit" of "db": na het uploaden meteen openen
function runTool(accept, fmt, label) {
  if (fmt === "web:pdf") { const a = document.createElement("a"); a.href = "/web/#pdf"; document.body.append(a); a.click(); a.remove(); return; }
  if (fmt === "screen") return screenOcr();
  if (fmt === "web") { show($("webForm"), true); $("webUrl").focus(); return; }
  if (fmt === "newtext") return newText();
  if (fmt === "newdb") return newDb();
  if (fmt === "drives") return openDrives();
  if (fmt === "edit" || fmt === "db") {
    afterUpload = fmt; presetFormat = null;
    fileInput.accept = accept === "*" ? "" : accept;
    status("choose a file to " + (fmt === "edit" ? "edit" : "open as a database"));
    fileInput.click();
    setTimeout(() => { fileInput.accept = ""; }, 1000);
    return;
  }
  presetFormat = fmt === "hash" ? null : fmt;
  status("choose a file for: " + label.toLowerCase());
  if (fmt === "patch") status("choose the ROM and the patch (.ips/.ups/.bps) together");
  if (["iso", "cue", "chd"].includes(fmt) && accept && accept.includes(".cue")) status("choose the .cue together with all .bin files (or one zip)");
  hashAfterUpload = fmt === "hash";
  fileInput.accept = accept === "*" ? "" : accept;
  fileInput.click();
  setTimeout(() => { fileInput.accept = ""; }, 1000);
}

// ---------- herkende tekst tonen
function showText(text, title) {
  $("textOutTitle").textContent = "// " + title;
  $("textOutBox").value = text;
  show($("textOut"), true);
  $("textOutBox").scrollIntoView({ block: "nearest" });
}
$("textClose").addEventListener("click", () => show($("textOut"), false));
$("textCopy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($("textOutBox").value); status("text copied"); }
  catch { $("textOutBox").select(); document.execCommand("copy"); status("text copied"); }
});
$("textSave").addEventListener("click", async () => {
  const blob = new Blob([$("textOutBox").value], { type: "text/plain" });
  const api = nativeApi();
  if (api) {
    const r = await api.save_begin("text.txt");
    if (r.path) {
      const b64 = btoa(unescape(encodeURIComponent($("textOutBox").value)));
      await api.save_chunk(b64); const d = await api.save_end(); status("opgeslagen: " + d.path);
    }
    return;
  }
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "text.txt";
  document.body.append(a); a.click(); a.remove();
});

async function screenOcr() {
  status("select an area of your screen…");
  try {
    const r = await fetch("/api/ocr/screen", { method: "POST" });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    showText(j.text || "(no text found)", "text from screenshot");
    status("text recognised");
  } catch (err) { status("ERROR: " + err.message); alert(err.message); }
}

// Plakken (ctrl+v / cmd+v) van een schermafbeelding: direct tekst herkennen
document.addEventListener("paste", async (e) => {
  if (current || /^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName || "")) return;
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
  if (!item) return;
  e.preventDefault();
  const fd = new FormData();
  fd.append("file", item.getAsFile(), "plakken.png");
  status("recognising text in the pasted image…");
  try {
    const r = await fetch("/api/ocr/image", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    showText(j.text || "(no text found)", "text from the pasted image");
    status("text recognised");
  } catch (err) { status("ERROR: " + err.message); }
});

// ---------- checksum
async function runHash() {
  if (!current) return;
  show($("hashBox"), true);
  $("hashOut").textContent = "berekenen…";
  const r = await fetch("/api/hash/" + current.id, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: $("hashKey").value }) });
  const j = await r.json();
  if (!r.ok) { $("hashOut").textContent = j.error; return; }
  const w = Math.max(...Object.keys(j.hashes).map((k) => k.length));
  $("hashOut").textContent = ($("hashKey").value ? "HMAC\n" : "") +
    Object.entries(j.hashes).map(([k, v]) => k.padEnd(w + 1) + v).join("\n");
}
$("hashBtn").addEventListener("click", runHash);
$("hashKey").addEventListener("change", runHash);

// ---------- website opslaan als pdf/png/jpg
$("webGo").addEventListener("click", async () => {
  const url = $("webUrl").value.trim();
  if (!url) return;
  $("webGo").disabled = true;
  status("website laden…");
  try {
    const r = await fetch("/api/webshot", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, format: $("webFmt").value }) });
    let j = await r.json();
    if (!r.ok) throw new Error(j.error);
    for (;;) {
      const rr = await fetch("/api/job/" + j.id); j = await rr.json();
      if (j.status === "error") throw new Error(j.error);
      if (j.status === "done") break;
      await new Promise((res) => setTimeout(res, 700));
    }
    const a = document.createElement("a"); a.href = "/api/download/" + j.id; a.setAttribute("download", "");
    document.body.append(a); a.click(); a.remove();
    status("website opgeslagen: " + j.filename);
  } catch (err) { status("ERROR: " + err.message); alert(err.message); }
  finally { $("webGo").disabled = false; }
});


// ---------- teksteditor
const edText = $("edText");
let edDirty = false;
function edLines() {
  const n = edText.value.split("\n").length;
  let out = "";
  for (let i = 1; i <= n; i++) out += i + "\n";
  $("edLines").textContent = out;
  $("edLines").scrollTop = edText.scrollTop;
  const pos = edText.value.slice(0, edText.selectionStart).split("\n");
  $("edInfo").textContent = `${current ? current.name : ""} · ${n} lines · line ${pos.length}, column ${pos[pos.length - 1].length + 1}` + (edDirty ? " · not saved" : "");
}
async function openEditor() {
  if (!current) return;
  const r = await fetch("/api/text/" + current.id);
  const j = await r.json();
  if (!r.ok) { status("ERROR: " + j.error); return; }
  edText.value = j.text; edDirty = false;
  $("edDownload").href = "/api/file/" + current.id + "?download=1";
  $("edDownload").setAttribute("download", j.name);
  show($("dbBox"), false); show($("editBox"), true);
  edLines(); edText.focus(); edText.setSelectionRange(0, 0);
  $("edMsg").textContent = "// save keeps the working copy (you can convert it afterwards). your original does not change.";
  $("edMsg").className = "dim small";
  $("editBox").scrollIntoView({ block: "start" });
}
edText.addEventListener("input", () => { edDirty = true; edLines(); });
edText.addEventListener("scroll", () => { $("edLines").scrollTop = edText.scrollTop; });
for (const ev of ["click", "keyup"]) edText.addEventListener(ev, edLines);
edText.addEventListener("keydown", (e) => {
  if (e.key === "Tab") { // tab = twee spaties, in plaats van naar het volgende veld
    e.preventDefault();
    const a = edText.selectionStart, b = edText.selectionEnd;
    edText.setRangeText("  ", a, b, "end"); edDirty = true; edLines();
  }
});
// ctrl+s / cmd+s = opslaan zolang de editor open is (ook als de cursor op een knop staat)
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && !$("editBox").classList.contains("hidden")) {
    e.preventDefault(); edSave();
  }
});
function edNote(msg, kind) { $("edMsg").textContent = "// " + msg; $("edMsg").className = "small " + (kind || "dim"); }
$("edCheck").addEventListener("click", async () => {
  const r = await fetch("/api/text/" + current.id, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: edText.value, check: true }) });
  const j = await r.json();
  edNote(j.ok ? "no errors found ✓" : "error: " + j.error, j.ok ? "ok" : "err");
});
async function edSave() {
  const r = await fetch("/api/text/" + current.id, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: edText.value }) });
  const j = await r.json();
  if (!r.ok) { edNote("saving failed: " + j.error, "err"); return; }
  edDirty = false; edLines();
  current = j.upload; $("fMeta").textContent = current.label + " · " + human(j.size);
  edNote("opgeslagen ✓ (" + human(j.size) + ")" + (j.warning ? " — note: " + j.warning : ""), j.warning ? "err" : "ok");
}
$("edSave").addEventListener("click", edSave);
$("edClose").addEventListener("click", () => {
  if (edDirty && !confirm("Discard unsaved changes?")) return;
  show($("editBox"), false);
});
$("editBtn").addEventListener("click", openEditor);
async function newText() {
  const name = prompt("Name of the new file (with extension, e.g. notes.md or data.json):", "notities.txt");
  if (!name) return;
  const r = await fetch("/api/text/new", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
  const j = await r.json();
  if (!r.ok) { status("ERROR: " + j.error); return; }
  localFile = null; setup(j); openEditor();
}

// ---------- databasetester
let dbTable = null, dbOffset = 0, dbTotal = 0;
function grid(el, cols, rows) {
  el.innerHTML = "";
  if (!cols.length) { el.textContent = "(no columns)"; return; }
  const t = document.createElement("table");
  const head = t.insertRow();
  for (const c of cols) { const th = document.createElement("th"); th.textContent = c; head.append(th); }
  for (const r of rows) {
    const tr = t.insertRow();
    for (const v of r) { const td = tr.insertCell(); td.textContent = v === null ? "NULL" : String(v); if (v === null) td.className = "dim"; }
  }
  el.append(t);
}
function dbNote(msg, kind) { $("dbMsg").textContent = "// " + msg; $("dbMsg").className = "small " + (kind || "dim"); }
function dbTablesList(tables) {
  const ul = $("dbTables");
  ul.innerHTML = "";
  if (!tables.length) { const li = document.createElement("li"); li.className = "dim"; li.textContent = "(no tables yet — create one with SQL)"; ul.append(li); }
  for (const t of tables) {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn small" + (t.naam === dbTable ? " on" : "");
    b.textContent = `${t.soort === "view" ? "◇" : "▦"} ${t.naam} (${t.rijen})`;
    b.title = t.kolommen.map((c) => c.naam + (c.type ? " " + c.type : "") + (c.sleutel ? " 🔑" : "")).join("\n");
    b.addEventListener("click", () => { dbTable = t.naam; dbOffset = 0; dbShow(); dbTablesList(tables); });
    li.append(b); ul.append(li);
  }
}
async function openDb() {
  if (!current) return;
  dbNote("database laden…");
  const r = await fetch(`/api/db/${current.id}/open`, { method: "POST" });
  const j = await r.json();
  show($("editBox"), false); show($("dbBox"), true);
  if (!r.ok) { dbNote(j.error, "err"); return; }
  dbTable = j.tables.length ? j.tables[0].naam : null; dbOffset = 0;
  dbTablesList(j.tables);
  dbNote("you are working on a copy: the original file does not change. export to keep your changes.");
  if (dbTable) { $("dbSql").value = `SELECT * FROM "${dbTable}" LIMIT 50;`; dbShow(); } else { $("dbRows").innerHTML = ""; $("dbTitle").textContent = ""; }
  $("dbBox").scrollIntoView({ block: "start" });
}
async function dbShow() {
  if (!dbTable) return;
  const r = await fetch(`/api/db/${current.id}/table?name=${encodeURIComponent(dbTable)}&offset=${dbOffset}`);
  const j = await r.json();
  if (!r.ok) { dbNote(j.error, "err"); return; }
  dbTotal = j.totaal;
  $("dbTitle").textContent = `// ${dbTable}: ${j.totaal} rows`;
  grid($("dbRows"), j.kolommen, j.rijen);
  $("dbPage").textContent = j.totaal ? `${dbOffset + 1}–${Math.min(dbOffset + j.rijen.length, j.totaal)} of ${j.totaal}` : "empty";
}
$("dbPrev").addEventListener("click", () => { dbOffset = Math.max(0, dbOffset - 200); dbShow(); });
$("dbNext").addEventListener("click", () => { if (dbOffset + 200 < dbTotal) { dbOffset += 200; dbShow(); } });
async function dbRun() {
  const sql = $("dbSql").value;
  dbNote("working…");
  const r = await fetch(`/api/db/${current.id}/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sql }) });
  const j = await r.json();
  if (!r.ok) { dbNote(j.error, "err"); $("dbResult").innerHTML = ""; return; }
  const res = j.result;
  if (res.kolommen.length) grid($("dbResult"), res.kolommen, res.rijen); else $("dbResult").innerHTML = "";
  dbNote(res.kolommen.length ? `${res.rijen.length}${res.meer ? "+" : ""} rows` + (res.meer ? " (eerste 500 getoond)" : "")
    : `done ✓ — ${res.opdrachten} statement(s), ${res.gewijzigd} row(s) changed`, "ok");
  if (!dbTable && j.tables.length) dbTable = j.tables[0].naam;
  dbTablesList(j.tables);
  dbShow();
}
$("dbRun").addEventListener("click", dbRun);
$("dbSql").addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); dbRun(); } });
$("dbExamples").addEventListener("change", (e) => { if (e.target.value) { $("dbSql").value = e.target.value; e.target.value = ""; $("dbSql").focus(); } });
$("dbExport").addEventListener("click", () => {
  const v = $("dbExportFmt").value;
  const q = v.startsWith("q-") ? `&sql=${encodeURIComponent($("dbSql").value)}` : "";
  const a = document.createElement("a");
  a.href = `/api/db/${current.id}/export?fmt=${v.replace("q-", "")}${q}`;
  a.setAttribute("download", ""); document.body.append(a); a.click(); a.remove();
});
$("dbClose").addEventListener("click", () => show($("dbBox"), false));
$("dbBtn").addEventListener("click", openDb);
async function newDb() {
  const r = await fetch("/api/db/new", { method: "POST" });
  const j = await r.json();
  if (!r.ok) { status("ERROR: " + j.error); return; }
  localFile = null; setup(j); openDb();
  $("dbSql").value = "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT);\nINSERT INTO customers (name, city) VALUES ('Anna', 'Utrecht'), ('Bo', 'Ghent');\nSELECT * FROM customers;";
}


// ---------------------------------------------------------------- what is behind a media file
let mediaInfoFor = null;
async function loadMediaInfo() {
  if (!current || mediaInfoFor === current.id) return;
  mediaInfoFor = current.id;
  const box = $("avSource");
  box.textContent = "reading streams…";
  try {
    const r = await fetch(`/api/media/${current.id}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "?");
    const kb = (b) => (b ? Math.round(b / 1000) + " kbps" : "");
    const lines = [`SOURCE  ${d.container || "?"} · ${fmtTime(d.duration)} · ${kb(d.bitrate)}`];
    for (const st of d.streams) {
      const bits = [st.kind.toUpperCase(), (st.codec || "?").toUpperCase() + (st.profile ? ` (${st.profile})` : "")];
      if (st.kind === "video") bits.push(`${st.width}×${st.height}`, st.fps ? st.fps + " fps" : "", st.pix_fmt || "",
        st.cover ? "cover art" : "");
      if (st.kind === "audio") bits.push(st.sample_rate ? st.sample_rate / 1000 + " kHz" : "", st.layout || (st.channels ? st.channels + " ch" : ""));
      bits.push(kb(st.bitrate), st.language || "", st.title || "");
      lines.push("  #" + st.index + " " + bits.filter(Boolean).join(" · "));
    }
    const tags = Object.entries(d.tags || {}).filter(([k]) => !/^(major_brand|minor_version|compatible_brands|encoder)$/i.test(k));
    if (tags.length) lines.push("TAGS    " + tags.map(([k, v]) => `${k}=${v}`).join(" · "));
    if (d.chapters) lines.push(`CHAPTERS ${d.chapters}`);
    const hw = Object.values(d.hw || {}).filter(Boolean);
    lines.push("GPU     " + (hw.length ? hw.join(" · ") + " (used automatically for H.264/H.265/AV1)" : "no hardware encoder found; encoding in software"));
    box.textContent = lines.join("\n");
    const t = d.tags || {}, low = Object.fromEntries(Object.entries(t).map(([k, v]) => [k.toLowerCase(), v]));
    $("metaTitle").placeholder = low.title || "keep"; $("metaArtist").placeholder = low.artist || "keep";
    $("metaAlbum").placeholder = low.album || "keep"; $("metaDate").placeholder = low.date || low.creation_time || "keep";
    $("metaComment").placeholder = low.comment || "keep";
  } catch (e) {
    box.textContent = "(could not read the streams: " + e.message + ")";
  }
}


// ---------------------------------------------------------------- test files
(async () => {
  const sel = $("sampleSel");
  try {
    const r = await fetch("/api/samples");
    const d = await r.json();
    sel.innerHTML = "";
    const first = document.createElement("option");
    first.value = ""; first.textContent = "choose a file type…";
    sel.append(first);
    const popular = ["mp4", "mov", "mkv", "mp3", "flac", "wav", "jpg", "png", "heic", "webp", "gif", "pdf", "docx",
      "xlsx", "pptx", "epub", "zip", "7z", "srt", "csv", "json", "sqlite", "cue", "iso", "nes", "z64", "stl", "svg", "ttf"];
    const all = new Map(d.groups.flatMap((g) => g.items.map((it) => [it.ext, it.desc])));
    const pg = document.createElement("optgroup");
    pg.label = "POPULAR";
    for (const e of popular.filter((x) => all.has(x))) pg.append(new Option(`.${e}  · ${all.get(e)}`, e));
    sel.append(pg);
    for (const g of d.groups) {
      const og = document.createElement("optgroup");
      og.label = g.group.toUpperCase();
      for (const it of g.items) og.append(new Option(`.${it.ext}  · ${it.desc}`, it.ext));
      sel.append(og);
    }
  } catch {
    sel.innerHTML = "<option value=''>(list not available)</option>";
  }
})();
async function loadSample(ext) {
  if (!ext) return;
  const btn = $("sampleBtn");
  btn.disabled = true;
  status("making test file ." + ext + "…");
  try {
    const r = await fetch("/api/sample/" + encodeURIComponent(ext), { method: "POST" });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "?");
    localFile = null;
    setup(d);
  } catch (e) {
    status("ERROR: " + e.message);
    alert(e.message);
  } finally {
    btn.disabled = false;
  }
}
$("sampleBtn").addEventListener("click", () => loadSample($("sampleSel").value));
$("sampleSel").addEventListener("change", () => loadSample($("sampleSel").value));


// ---------------------------------------------------------------- drives: health and safe formatting
let drvSel = null;
function openDrives() {
  show($("drivesBox"), true);
  $("drivesBox").scrollIntoView({ behavior: "smooth" });
  loadDrives();
}
async function loadDrives() {
  const list = $("drvList");
  list.textContent = "looking for drives…";
  show($("drvForm"), false); show($("drvHealth"), false);
  try {
    const r = await fetch("/api/drives");
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    const fs = $("drvFs");
    if (!fs.options.length) for (const [k, v] of d.filesystems) fs.append(new Option(v, k));
    list.innerHTML = "";
    for (const dr of d.drives) {
      const row = document.createElement("div");
      row.className = "drv-row" + (dr.system ? " drv-sys" : "");
      const what = [dr.kind === "optical" ? "CD/DVD" : dr.bus.toUpperCase() || "DISK", dr.size_text,
        dr.labels.join(", "), dr.filesystems.join(", "), dr.mounts.join(" ")].filter(Boolean).join(" · ");
      row.innerHTML = '<span class="drv-name"></span><span class="drv-info dim"></span><span class="drv-btns"></span>';
      row.querySelector(".drv-name").textContent = `${dr.id}  ${dr.name}` + (dr.system ? "  [SYSTEM]" : "");
      row.querySelector(".drv-info").textContent = what + (dr.health ? " · health: " + dr.health : "");
      const hb = document.createElement("button");
      hb.className = "btn small"; hb.type = "button"; hb.textContent = "[ HEALTH ]";
      hb.addEventListener("click", () => driveHealth(dr));
      row.querySelector(".drv-btns").append(hb);
      const can = dr.can_format || ($("drvInternal").checked && !dr.system && dr.size && dr.why_not.startsWith("internal"));
      const fb = document.createElement("button");
      fb.className = "btn small"; fb.type = "button";
      fb.textContent = dr.kind === "optical" ? "[ ERASE DISC ]" : "[ FORMAT ]";
      fb.disabled = !can;
      fb.title = can ? "" : dr.why_not;
      fb.addEventListener("click", () => formatForm(dr));
      row.querySelector(".drv-btns").append(fb);
      list.append(row);
    }
    if (!d.drives.length) list.textContent = "(no drives found)";
  } catch (e) {
    list.textContent = "!! " + e.message;
  }
}
async function driveHealth(dr) {
  const box = $("drvHealth");
  show(box, true);
  box.textContent = `checking ${dr.id}…`;
  try {
    const r = await fetch("/api/drives/health?id=" + encodeURIComponent(dr.id));
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    const mark = { OK: "✓ OK", WARNING: "! WARNING", FAILING: "!! FAILING — back up now", UNKNOWN: "? UNKNOWN" }[d.verdict] || d.verdict;
    box.textContent = `HEALTH ${dr.id} ${dr.name}: ${mark}${d.source ? "  (" + d.source + ")" : ""}\n` + d.lines.map((l) => "  " + l).join("\n");
  } catch (e) {
    box.textContent = "!! " + e.message;
  }
}
async function formatForm(dr) {
  drvSel = dr;
  show($("drvForm"), true);
  $("drvTarget").textContent = `> ${dr.kind === "optical" ? "ERASE" : "FORMAT"}: ${dr.id} · ${dr.name} · ${dr.size_text}`;
  $("drvConfirmName").textContent = dr.id;
  $("drvConfirm").value = ""; $("drvGo").disabled = true; $("drvMsg").textContent = "";
  for (const id of ["drvFs", "drvLabel"]) $(id).closest("label").classList.toggle("hidden", dr.kind === "optical");
  if (dr.size > 32 * 1024 ** 3 && $("drvFs").value === "fat32") $("drvFs").value = "exfat";
  await drvPlan();
  $("drvConfirm").focus();
}
async function drvPlan() {
  if (!drvSel) return;
  try {
    const r = await fetch("/api/drives/plan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: drvSel.id, fs: $("drvFs").value, label: $("drvLabel").value, full: !!$("drvFull").value,
        allow_internal: $("drvInternal").checked }) });
    const d = await r.json();
    $("drvPlan").textContent = r.ok ? "// will run:\n" + d.commands.map((c) => "   " + c).join("\n") + (d.allowed ? "" : "\n!! " + d.why) : "!! " + d.error;
  } catch (e) { $("drvPlan").textContent = "!! " + e.message; }
}
["drvFs", "drvLabel", "drvFull"].forEach((id) => $(id).addEventListener("change", drvPlan));
$("drvConfirm").addEventListener("input", () => { $("drvGo").disabled = !drvSel || $("drvConfirm").value.trim() !== drvSel.id; });
$("drvInternal").addEventListener("change", loadDrives);
$("drvRefresh").addEventListener("click", loadDrives);
$("drvClose").addEventListener("click", () => show($("drivesBox"), false));
$("drvGo").addEventListener("click", async () => {
  if (!drvSel || $("drvConfirm").value.trim() !== drvSel.id) return;
  if (!confirm(`Last check: delete EVERYTHING on ${drvSel.id} (${drvSel.name}, ${drvSel.size_text})?`)) return;
  const bar = $("drvBar"), msg = $("drvMsg");
  $("drvGo").disabled = true; show(bar, true); msg.className = "small"; msg.textContent = "formatting… (approve the permission prompt if one appears)";
  try {
    const r = await fetch("/api/drives/format", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: drvSel.id, fs: $("drvFs").value, label: $("drvLabel").value, full: !!$("drvFull").value,
        allow_internal: $("drvInternal").checked, confirm: $("drvConfirm").value.trim() }) });
    let j = await r.json();
    if (!r.ok) throw new Error(j.error);
    for (;;) {
      const rr = await fetch("/api/job/" + j.id);
      j = await rr.json();
      bar.textContent = txtBar(j.progress, barWidth());
      if (j.status === "error") throw new Error(j.error);
      if (j.status === "done") break;
      await new Promise((res) => setTimeout(res, 1000));
    }
    msg.textContent = "✓ " + j.text;
    loadDrives();
  } catch (e) {
    msg.className = "small err"; msg.textContent = "!! " + e.message;
  } finally {
    show(bar, false); $("drvConfirm").value = "";
  }
});
