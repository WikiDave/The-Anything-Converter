// Colour picker: ready-made themes plus a free choice of text and background colour.
// Self-contained: used by the desktop app (static/) and inlined in the browser version (index.html).
(() => {
  const PRESETS = [
    ["green phosphor", "#a6ff5c", "#000000"], ["amber", "#ffb000", "#000000"], ["cyan", "#5ff5d0", "#000000"],
    ["white", "#e8e8e8", "#000000"], ["matrix", "#00ff41", "#0d0208"], ["red alert", "#ff5555", "#120000"],
    ["pink", "#ff79c6", "#1a0b14"], ["purple", "#c792ea", "#120b1a"], ["ice", "#9fdcff", "#04121c"],
    ["gold", "#ffd700", "#161200"], ["dos", "#d0d0d0", "#0000a8"], ["c64", "#a5a5ff", "#40318d"],
    ["solarized", "#93a1a1", "#002b36"], ["gruvbox", "#ebdbb2", "#282828"], ["nord", "#d8dee9", "#2e3440"],
    ["dracula", "#f8f8f2", "#282a36"], ["high contrast", "#ffff00", "#000000"], ["paper", "#1a1a1a", "#f4f1e8"],
    ["sepia", "#5b4636", "#f4ecd8"], ["green on white", "#0b6b00", "#f3fff0"],
  ];
  const KEY = "ac-colours";
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const toHex = (c) => "#" + c.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
  const mix = (a, b, t) => toHex(hex(a).map((v, i) => v + (hex(b)[i] - v) * t));
  const light = (h) => { const [r, g, b] = hex(h); return 0.2126 * r + 0.7152 * g + 0.0722 * b > 140; };

  function apply(fg, bg) {
    const s = document.documentElement.style;
    if (!fg || !bg) {
      for (const v of ["--fg", "--bg", "--panel", "--hi", "--dim", "--faint", "--glow"]) s.removeProperty(v);
      return;
    }
    const isLight = light(bg);
    const [r, g, b] = hex(fg);
    s.setProperty("--fg", fg);
    s.setProperty("--bg", bg);
    s.setProperty("--panel", bg);
    s.setProperty("--hi", mix(fg, isLight ? "#000000" : "#ffffff", 0.5));
    s.setProperty("--dim", mix(fg, bg, 0.45));
    s.setProperty("--faint", mix(fg, bg, 0.85));
    s.setProperty("--glow", `rgba(${r}, ${g}, ${b}, ${isLight ? 0.12 : 0.35})`);
    document.documentElement.style.colorScheme = isLight ? "light" : "dark";
  }
  function save(fg, bg) { try { fg ? localStorage.setItem(KEY, JSON.stringify([fg, bg])) : localStorage.removeItem(KEY); } catch {} }

  function build() {
    const group = document.querySelector(".themes, .skins");
    if (!group || document.getElementById("acColourBtn")) return;
    const btn = document.createElement("button");
    btn.type = "button"; btn.id = "acColourBtn"; btn.className = "btn small";
    btn.textContent = "[ COLOURS ]"; btn.setAttribute("aria-expanded", "false");
    group.after(btn);
    const box = document.createElement("div");
    box.id = "acColourBox"; box.hidden = true; box.className = "no-i18n";
    box.innerHTML = `<div class="acc-head">COLOURS · THEME</div><div class="acc-grid"></div>
      <div class="acc-row"><label>TEXT&gt; <input type="color" id="accFg"></label>
      <label>BACKGROUND&gt; <input type="color" id="accBg"></label>
      <button type="button" class="btn small" id="accSwap">[ SWAP ]</button>
      <button type="button" class="btn small" id="accReset">[ RESET ]</button></div>`;
    document.body.append(box);
    const grid = box.querySelector(".acc-grid");
    for (const [name, fg, bg] of PRESETS) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "acc-preset"; b.title = name;
      b.style.cssText = `color:${fg};background:${bg};border-color:${fg}`;
      b.textContent = name;
      b.addEventListener("click", () => set(fg, bg));
      grid.append(b);
    }
    const fgIn = box.querySelector("#accFg"), bgIn = box.querySelector("#accBg");
    const set = (fg, bg) => { apply(fg, bg); save(fg, bg); fgIn.value = fg; bgIn.value = bg; };
    fgIn.addEventListener("input", () => set(fgIn.value, bgIn.value));
    bgIn.addEventListener("input", () => set(fgIn.value, bgIn.value));
    box.querySelector("#accSwap").addEventListener("click", () => set(bgIn.value, fgIn.value));
    box.querySelector("#accReset").addEventListener("click", () => {
      apply(null); save(null);
      const cs = getComputedStyle(document.documentElement);
      fgIn.value = rgbToHex(cs.getPropertyValue("--fg")); bgIn.value = rgbToHex(cs.getPropertyValue("--bg"));
    });
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      box.hidden = !box.hidden;
      btn.setAttribute("aria-expanded", String(!box.hidden));
      const r = btn.getBoundingClientRect();
      box.style.top = (r.bottom + window.scrollY + 6) + "px";
      box.style.left = Math.max(8, Math.min(r.right - box.offsetWidth, window.innerWidth - box.offsetWidth - 8)) + "px";
    });
    document.addEventListener("click", (e) => { if (!box.hidden && !box.contains(e.target) && e.target !== btn) box.hidden = true; });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") box.hidden = true; });
    // the old [GREEN] [AMBER] [CYAN] buttons switch back to the built-in themes
    group.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { apply(null); save(null); }));
    const cs = getComputedStyle(document.documentElement);
    fgIn.value = rgbToHex(cs.getPropertyValue("--fg")); bgIn.value = rgbToHex(cs.getPropertyValue("--bg"));
  }
  function rgbToHex(v) {
    v = (v || "").trim();
    if (/^#[0-9a-f]{6}$/i.test(v)) return v.toLowerCase();
    const m = v.match(/\d+/g);
    return m ? toHex(m.slice(0, 3).map(Number)) : "#000000";
  }
  try { const c = JSON.parse(localStorage.getItem(KEY) || "null"); if (c) apply(c[0], c[1]); } catch {}
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
  const st = document.createElement("style");
  st.textContent = `#acColourBox{position:absolute;z-index:1000;width:min(460px,calc(100vw - 16px));background:var(--bg);color:var(--fg);
    border:1px solid var(--fg);box-shadow:0 0 18px var(--glow);padding:12px;font-family:var(--mono,monospace);font-size:12px}
    #acColourBox .acc-head{margin-bottom:8px;color:var(--hi)}
    #acColourBox .acc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:6px}
    #acColourBox .acc-preset{font:inherit;font-size:11px;padding:6px 4px;border:1px solid;cursor:pointer;text-transform:uppercase}
    #acColourBox .acc-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:10px}
    #acColourBox input[type=color]{width:38px;height:24px;border:1px solid var(--fg);background:none;padding:0;vertical-align:middle;cursor:pointer}`;
  document.head.append(st);
})();
