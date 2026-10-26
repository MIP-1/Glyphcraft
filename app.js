const DEFAULT_ADJ = { brightness: 0, contrast: 0, saturation: 0, hue: 0, highlights: 0, shadows: 0, sharpen: 0, blur: 0, invert: false, sepia: false };

// Snap a value to the control's own step grid so 0.1 + 0.2 never becomes
// 0.30000000004, then clamp to the control's own range.
function roundToStep(value, step, base) {
  if (!Number.isFinite(value)) return base;
  const size = step > 0 ? step : 1;
  const decimals = (String(size).split(".")[1] || "").length;
  const snapped = Math.round((value - base) / size) * size + base;
  return parseFloat(snapped.toFixed(decimals));
}
function clampToParam(value, param) {
  return Math.min(param.max, Math.max(param.min, roundToStep(value, param.step, param.min)));
}

// One stepper component for every numeric control. The whole control is a
// single 44x44 button (the gate's minimum touch target): its top half steps up,
// its bottom half steps down. A pointerdown applies one step synchronously;
// holding repeats after a short delay. Rendering is never started while the
// gesture is in progress, so a slow render can never delay or lose a change.
const STEP_INITIAL_DELAY = 300;
const STEP_REPEAT_MS = 35;

function attachStepper(container, controlId, label, onStep, onEnd) {
  if (!container) return null;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "stepper";
  btn.dataset.control = controlId;
  btn.setAttribute("aria-label", (label || "Value") + " stepper. Top half increases, bottom half decreases; arrow keys also work.");
  ["up", "down"].forEach(dir => {
    const half = document.createElement("span");
    half.className = "step-btn";
    half.dataset.step = dir;
    half.setAttribute("aria-hidden", "true");
    half.innerHTML = dir === "up"
      ? '<svg viewBox="0 0 10 6" focusable="false"><path d="M1 5l4-4 4 4"/></svg>'
      : '<svg viewBox="0 0 10 6" focusable="false"><path d="M1 1l4 4 4-4"/></svg>';
    btn.appendChild(half);
  });

  let delayTimer = null;
  let repeatTimer = null;
  let active = false;
  let direction = "up";
  const stop = () => {
    if (!active) return;
    active = false;
    clearTimeout(delayTimer);
    clearInterval(repeatTimer);
    delayTimer = repeatTimer = null;
    if (onEnd) onEnd();
  };
  const directionAt = e => {
    const half = e.target && e.target.closest ? e.target.closest("[data-step]") : null;
    if (half) return half.dataset.step;
    const box = btn.getBoundingClientRect();
    return e.clientY - box.top < box.height / 2 ? "up" : "down";
  };
  btn.addEventListener("pointerdown", e => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    if (active) stop();
    active = true;
    direction = directionAt(e);
    if (btn.setPointerCapture) { try { btn.setPointerCapture(e.pointerId); } catch (err) {} }
    onStep(direction, true);
    delayTimer = setTimeout(() => {
      if (!active) return;
      repeatTimer = setInterval(() => { if (active) onStep(direction, false); }, STEP_REPEAT_MS);
    }, STEP_INITIAL_DELAY);
  });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(ev => btn.addEventListener(ev, stop));
  btn.addEventListener("keydown", e => {
    const dir = e.key === "ArrowDown" ? "down" : (e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") ? "up" : null;
    if (!dir) return;
    e.preventDefault();
    e.stopPropagation();
    onStep(dir, true);
    if (onEnd) onEnd();
  });
  btn.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); });
  // The browser's own spinner is only hidden where this control replaces it,
  // so numeric fields outside the shared component keep their arrows.
  const field = container.querySelector('input[type="number"]');
  if (field) field.classList.add("has-stepper");
  container.appendChild(btn);
  return btn;
}

function defaultEffects() {
  return (typeof EFFECTS !== "undefined" ? EFFECTS : []).map(e => makeEffect(e.id, false));
}

function defaultOpts() {
  return {
    mode: "script",
    depth: 80,
    charCategory: "all",
    charSet: "all",
    charInject: "",
    charOffset: 0,
    textStyle: "regular",
    charPreset: "ascii",
    customCharset: "",
    cellSize: 8,
    glyphWeight: 400,
    glyphInvert: false,
    glyphColor: true,
    usePalette: true,
    transparentBg: false,
    autoLevels: true,
    bgColor: "#0b0b0c",
    colorMode: "spectrum",
    palette: "Default",
    customPalette: null,
    monoColor: "#e9dfc8",
    ditherKernel: "floyd-steinberg",
    ditherDepth: 4,
    ditherSerpentine: true,
    adj: { ...DEFAULT_ADJ },
    outputPreset: "original",
    outputWidth: 1920,
    outputHeight: 1080,
    outputFit: "contain",
    outputLockRatio: true,
    exportFormat: "png",
    jpgQuality: 90,
    effects: defaultEffects()
  };
}

const state = {
  source: null,
  sourceType: null,
  sourceW: 0,
  sourceH: 0,
  video: null,
  rafId: null,
  renderTimer: null,
  renderId: null,
  renderDirty: false,
  lastRenderKey: "",
  renderCache: null,
  cacheDisabled: false,
  sourceId: 0,
  sourceUrl: null,
  pan: { x: 0, y: 0 },
  scale: 1,
  zoom: 1,
  fullPage: false,
  spaceDown: false,
  opts: defaultOpts(),
  ramp: null,
  paletteColors: null,
  lastRender: 0,
  compare: false,
  compareFrac: 0.5,
  showOriginal: false,
  presetOpen: false,
  presetExpanded: false,
  videoExporting: false,
  videoExportFrames: 0,
  videoExportTotal: 0,
  history: { undo: [], redo: [], lastKey: "", lastAt: 0 },
  pendingReset: false,
  exportProgress: { active: false, format: "", progress: 0, total: 0 }
};

const PREVIEW_MAX = 1600;
const MAX_PREVIEW_PIXELS = 1600 * 1600;
const els = {};
function $(id) { return document.getElementById(id); }
function on(el, ev, fn, opts) { if (el) el.addEventListener(ev, fn, opts); }

function initEls() {
  els.canvas = $("canvas");
  els.canvasArea = $("canvas-area");
  els.workspace = document.querySelector(".workspace");
  els.dropZone = $("drop-zone");
  els.ctx = els.canvas.getContext("2d", { willReadFrequently: true });
  els.fileInput = $("file-input");
  els.panel = $("panel");
  els.panelToggleBtn = $("panel-toggle-btn");
  els.panelSearch = $("panel-search");
  els.btnExport = $("btn-export");
  els.btnReset = $("btn-reset");
  els.selectMode = $("select-mode");
  els.depth = $("depth");
  els.depthNum = $("depth-num");
  els.charCategory = $("char-category");
  els.charSet = $("char-set");
  els.charInject = $("char-inject");
  els.charOffset = $("char-offset");
  els.charOffsetNum = $("char-offset-num");
  els.textStyle = $("text-style");
  els.usePalette = $("use-palette");
  els.transparentBg = $("transparent-bg");
  els.autoLevels = $("auto-levels");
  els.bgColor = $("bg-color");
  els.colorMode = $("color-mode");
  els.paletteSelect = $("palette-select");
  els.controlPalette = $("control-palette");
  els.paletteSwatches = $("palette-swatches");
  els.adjBrightness = $("adj-brightness");
  els.adjBrightnessNum = $("adj-brightness-num");
  els.adjContrast = $("adj-contrast");
  els.adjContrastNum = $("adj-contrast-num");
  els.adjSaturation = $("adj-saturation");
  els.adjSaturationNum = $("adj-saturation-num");
  els.adjHue = $("adj-hue");
  els.adjHueNum = $("adj-hue-num");
  els.adjHighlights = $("adj-highlights");
  els.adjHighlightsNum = $("adj-highlights-num");
  els.adjShadows = $("adj-shadows");
  els.adjShadowsNum = $("adj-shadows-num");
  els.adjSharpen = $("adj-sharpen");
  els.adjSharpenNum = $("adj-sharpen-num");
  els.adjBlur = $("adj-blur");
  els.adjBlurNum = $("adj-blur-num");
  els.adjInvert = $("adj-invert");
  els.adjSepia = $("adj-sepia");
  els.outputPreset = $("output-preset");
  els.outputWidth = $("output-width");
  els.outputHeight = $("output-height");
  els.outputFit = $("output-fit");
  els.exportFormat = $("export-format");
  els.ditherKernel = $("dither-kernel");
  els.ditherDepth = $("dither-depth");
  els.ditherDepthNum = $("dither-depth-num");
 
  els.statusBar = $("status-bar");
  els.statusZoom = $("status-zoom");
  els.statusSize = $("status-size");
  els.statusTime = $("status-time");
  els.menuFile = $("menu-file"); els.dropdownFile = $("dropdown-file");
  els.menuView = $("menu-view"); els.dropdownView = $("dropdown-view");
  els.menuEdit = $("menu-edit"); els.dropdownEdit = $("dropdown-edit");
  els.sectionScript = $("section-script");
  els.sectionDither = $("section-dither");
  els.sectionColor = $("section-color");
  els.sectionAdjustments = $("section-adjustments");
  els.sectionEffects = $("section-effects");
  els.sectionOutput = $("section-output");
  els.effectsList = $("effects-list");
  els.presetsBar = $("presets-bar");
  els.compareOverlay = $("compare-overlay");
  els.compareSlider = $("compare-slider");
  els.outputPresetSearch = $("output-preset-search");
  els.outputPresetTrigger = $("output-preset-trigger");
  els.outputPresetPopup = $("output-preset-popup");
  els.outputPresetList = $("output-preset-list");
  els.outputPresetValue = $("output-preset-value");
  els.outputPresetSwatch = $("output-preset-swatch");
  els.presetPicker = $("preset-picker");
  els.outputCustomRow = $("output-custom-row");
  els.outputLockRatio = $("output-lock-ratio");
  els.outputWarn = $("output-warn");
  els.ditherSerpentine = $("dither-serpentine");
  els.customPaletteBuilder = $("custom-palette-builder");
  els.paletteBuilder = $("palette-builder");
  els.paletteAddColor = $("palette-add-color");
  els.paletteSaveCustom = $("palette-save-custom");
  els.charPreset = $("char-preset");
  els.customCharsetRow = $("custom-charset-row");
  els.customCharset = $("custom-charset");
  els.cellSize = $("cell-size");
  els.cellSizeNum = $("cell-size-num");
 
  els.glyphWeight = $("glyph-weight");
  els.glyphWeightNum = $("glyph-weight-num");
 
  els.glyphInvert = $("glyph-invert");
  els.glyphColor = $("glyph-color");
  els.jpgQuality = $("jpg-quality");
  els.jpgQualityNum = $("jpg-quality-num");
 
  els.jpgQualityControl = $("jpg-quality-control");
  els.openFileBtn = $("open-file-btn");
  els.dropHint = document.querySelector("#drop-zone .drop-hint");
  els.dropError = document.querySelector("#drop-zone .drop-error");
  els.dropLoadingText = document.querySelector("#drop-zone .drop-loading-text");
  els.themeToggle = $("theme-toggle");
  els.zoomIn = $("zoom-in");
  els.zoomOut = $("zoom-out");
  els.zoomLevel = $("zoom-level");
  els.zoomMenu = $("zoom-menu");
  els.btnSavePreset = $("btn-save-preset");
  els.btnLoadPreset = $("btn-load-preset");
}

/* ---------------- Theme ---------------- */

function currentTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function setTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("glyphcraft-theme", next); } catch (e) {}

  const target = next === "dark" ? "light" : "dark";
  const label = target === "light" ? "Switch to light theme" : "Switch to dark theme";
  if (els.themeToggle) {
    els.themeToggle.setAttribute("aria-label", label);
    els.themeToggle.title = label;
  }
  applyZoomUI();
}

function toggleTheme() {
  setTheme(currentTheme() === "dark" ? "light" : "dark");
}

function loadTheme() {
  let saved = null;
  try { saved = localStorage.getItem("glyphcraft-theme"); } catch (e) {}
  if (saved === "dark" || saved === "light") { setTheme(saved); return; }
  const dark = !window.matchMedia || window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(dark ? "dark" : "light");
}

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  if (bytes >= 1024) return Math.round(bytes / 1024) + " KB";
  return bytes + " B";
}

function populatePalettes() {
  const select = els.paletteSelect;
  if (!select) return;
  select.innerHTML = "";
  BUILTIN_PALETTES.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.name; opt.textContent = p.name;
    if (p.editable) opt.dataset.editable = "true";
    select.appendChild(opt);
  });
  const autoOpt = document.createElement("option");
  autoOpt.value = "__auto__"; autoOpt.textContent = "Auto-extract";
  select.appendChild(autoOpt);
  select.value = state.opts.palette;
  updatePaletteSwatches();
  updateCustomPaletteBuilder();
}

function currentPalette() {
  if (state.opts.palette === "__auto__") return state.opts.customPalette || [];
  if (state.opts.palette === "__custom__") return state.opts.customPalette || [];
  const builtin = BUILTIN_PALETTES.find(p => p.name === state.opts.palette);
  return builtin ? builtin.colors.slice() : [];
}

function updatePaletteSwatches() {
  if (!els.paletteSwatches) return;
  els.paletteSwatches.innerHTML = "";
  const palette = currentPalette();
  state.paletteColors = palette;
  palette.forEach((c, i) => {
    const sw = document.createElement("div");
    sw.className = "palette-swatch";
    sw.style.background = c;
    sw.title = c;
    sw.dataset.color = c;
    sw.dataset.index = i;
    if (c === state.opts.monoColor) sw.classList.add("active");
    sw.addEventListener("click", () => {
      state.opts.monoColor = c;
      updatePaletteSwatches();
      pushHistory("palette-color");
      scheduleRender();
    });
    els.paletteSwatches.appendChild(sw);
  });
}

function updateCustomPaletteBuilder() {
  if (!els.customPaletteBuilder || !els.paletteBuilder) return;
  const paletteName = state.opts.palette;
  const builtin = BUILTIN_PALETTES.find(p => p.name === paletteName);
  const isEditable = builtin && builtin.editable;
  const isCustom = paletteName === "__custom__";
  
  if (isEditable || isCustom) {
    els.customPaletteBuilder.hidden = false;
    renderPaletteBuilder(paletteName);
  } else {
    els.customPaletteBuilder.hidden = true;
  }
}

function renderPaletteBuilder(paletteName) {
  if (!els.paletteBuilder) return;
  const colors = state.opts.customPalette && state.opts.customPalette.length 
    ? state.opts.customPalette.slice() 
    : (builtin = BUILTIN_PALETTES.find(p => p.name === paletteName)) 
      ? builtin.colors.slice() 
      : ["#000", "#fff"];
  
  els.paletteBuilder.innerHTML = "";
  colors.forEach((c, i) => {
    const wrap = document.createElement("div");
    wrap.style.display = "flex";
    wrap.style.alignItems = "center";
    wrap.style.gap = "4px";
    wrap.style.marginBottom = "4px";
    
    const input = document.createElement("input");
    input.type = "color";
    input.value = c;
    input.style.width = "32px";
    input.style.height = "24px";
    input.style.border = "1px solid var(--line)";
    input.style.borderRadius = "4px";
    input.addEventListener("input", (e) => {
      colors[i] = e.target.value;
      state.opts.customPalette = colors;
      updatePaletteSwatches();
      pushHistory("custom-palette");
      scheduleRender();
    });
    wrap.appendChild(input);
    
    const removeBtn = document.createElement("button");
    removeBtn.className = "btn btn-small";
    removeBtn.textContent = "×";
    removeBtn.style.padding = "2px 6px";
    removeBtn.style.lineHeight = "1";
    removeBtn.addEventListener("click", () => {
      colors.splice(i, 1);
      state.opts.customPalette = colors;
      renderPaletteBuilder(paletteName);
      updatePaletteSwatches();
      pushHistory("custom-palette");
      scheduleRender();
    });
    wrap.appendChild(removeBtn);
    els.paletteBuilder.appendChild(wrap);
  });
  state.opts.customPalette = colors;
  state.opts.palette = paletteName === "__custom__" ? "__custom__" : paletteName;
}

function saveCustomPalette() {
  const name = (window.prompt("Custom palette name:", "") || "").trim();
  if (!name) return;
  const custom = { name, colors: state.opts.customPalette || [], editable: true };
  try {
    const customs = JSON.parse(localStorage.getItem("glyphcraft-custom-palettes") || "[]");
    customs.push(custom);
    localStorage.setItem("glyphcraft-custom-palettes", JSON.stringify(customs));
    populatePalettes();
    state.opts.palette = name;
    state.opts.customPalette = custom.colors.slice();
    updatePaletteSwatches();
    pushHistory("custom-palette-save");
    scheduleRender();
  } catch (e) { alert("Could not save palette"); }
}

const CHAR_PRESETS = {
  ascii: " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
  blocks: " ░▒▓█▄▌▐▀▄▌▐▀■□▪▫▬▭▮▯▰▱▲△▴▵▶▷▸▹►▻▼▽▾▿◀◁◂◃◄◅◆◇◈◉◊○◌●◍◎●◐◑◒◓◔◕◖◗◘◙◚◛◜◝◞◟◠◡◢◣◤◥◦◧◨◩◪◫◬◭◮◯◰◱◲◳◴◵◶◷◸◹◺◻◼◽◾◿",
  braille: "⠀⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿⡀⡁⡂⡃⡄⡅⡆⡇⡈⡉⡊⡋⡌⡍⡎⡏⡐⡑⡒⡓⡔⡕⡖⡗⡘⡙⡚⡛⡜⡝⡞⡟⡠⡡⡢⡣⡤⡥⡦⡧⡨⡩⡪⡫⡬⡭⡮⡯⡰⡱⡲⡳⡴⡵⡶⡷⡸⡹⡺⡻⡼⡽⡾⡿⢀⢁⢂⢃⢄⢅⢆⢇⢈⢉⢊⢋⢌⢍⢎⢏⢐⢑⢒⢓⢔⢕⢖⢗⢘⢙⢚⢛⢜⢝⢞⢟⢠⢡⢢⢣⢤⢥⢦⢧⢨⢩⢪⢫⢬⢭⢮⢯⢰⢱⢲⢳⢴⢵⢶⢷⢸⢹⢺⢻⢼⢽⢾⢿⣀⣁⣂⣃⣄⣅⣆⣇⣈⣉⣊⣋⣌⣍⣎⣏⣐⣑⣒⣓⣔⣕⣖⣗⣘⣙⣚⣛⣜⣝⣞⣟⣠⣡⣢⣣⣤⣥⣦⣧⣨⣩⣪⣫⣬⣭⣮⣯⣰⣱⣲⣳⣴⣵⣶⣷⣸⣹⣺⣻⣼⣽⣾⣿",
  binary: "01",
  minimal: "@#:.",
  dense: "█▓▒░"
};

function applyCharPreset(preset) {
  const chars = CHAR_PRESETS[preset];
  if (!chars) return;
  if (preset === "custom") return;
  state.opts.charInject = "";
  state.opts.charCategory = "all";
  state.opts.charSet = "all";
  state.opts.customCharset = chars;
  els.customCharset.value = chars;
  els.charCategory.value = "all";
  els.charSet.value = "all";
}

function rebuildRamp() {
  let inject = state.opts.charInject;
  if (state.opts.charPreset !== "custom" && state.opts.charPreset !== "ascii") {
    inject = state.opts.customCharset || CHAR_PRESETS[state.opts.charPreset] || "";
  }
  state.ramp = buildRamp(state.opts.charCategory, state.opts.charSet, inject, state.opts.textStyle);
}

function snapshot() { return JSON.stringify(state.opts); }

function pushHistory(key) {
  const h = state.history, now = performance.now(), snap = snapshot();
  if (h.undo.length && h.undo[h.undo.length - 1] === snap) return;
  if (key && key === h.lastKey && now - h.lastAt < 600 && h.undo.length) {
    h.undo[h.undo.length - 1] = snap;
  } else {
    h.undo.push(snap);
  }
  if (h.undo.length > 60) h.undo.shift();
  h.redo.length = 0;
  h.lastKey = key || "";
  h.lastAt = now;
}

function restoreSnapshot(snap) {
  const opts = JSON.parse(snap);
  opts.adj = { ...DEFAULT_ADJ, ...(opts.adj || {}) };
  const byId = new Map((opts.effects || []).map(e => [e.id, e]));
  opts.effects = defaultEffects().map(def => {
    const found = byId.get(def.id);
    return found ? { id: def.id, enabled: !!found.enabled, params: { ...def.params, ...(found.params || {}) } } : def;
  });
  state.opts = opts;
  rebuildRamp();
  updatePaletteSwatches();
  syncUIFromState();
  scheduleRender(0);
}

function undo() {
  const h = state.history;
  if (h.undo.length < 2) return;
  h.redo.push(h.undo.pop());
  h.lastKey = "";
  restoreSnapshot(h.undo[h.undo.length - 1]);
}

function redo() {
  const h = state.history;
  if (!h.redo.length) return;
  const snap = h.redo.pop();
  h.undo.push(snap);
  h.lastKey = "";
  restoreSnapshot(snap);
}

function renderOpts() {
  return {
    ...state.opts,
    offset: state.opts.charOffset,
    ramp: state.ramp,
    palette: state.paletteColors,
    colorDepth: state.opts.ditherDepth,
    effects: state.opts.effects,
    adj: state.opts.adj
  };
}

function previewSize(full) {
  const maxDim = Math.max(full.w, full.h);
  const maxPixels = full.w * full.h;
  let scale = 1;
  if (maxDim > PREVIEW_MAX) scale = Math.min(scale, PREVIEW_MAX / maxDim);
  if (maxPixels > MAX_PREVIEW_PIXELS) scale = Math.min(scale, Math.sqrt(MAX_PREVIEW_PIXELS / maxPixels));
  return { w: Math.max(1, Math.round(full.w * scale)), h: Math.max(1, Math.round(full.h * scale)), scale };
}

function scheduleRender(delay) {
  // Mark dirty, then coalesce: many changes before the next frame produce one
  // render of the latest state. Only callers that explicitly debounce (slider
  // input that would otherwise render every pointer event) wait on a timer.
  state.renderDirty = true;
  if (delay) {
    clearTimeout(state.renderTimer);
    state.renderTimer = setTimeout(() => {
      state.renderTimer = null;
      requestRenderFrame();
    }, delay);
    return;
  }
  requestRenderFrame();
}

function requestRenderFrame() {
  if (state.renderId) return;
  state.renderId = requestAnimationFrame(() => {
    state.renderId = null;
    if (!state.renderDirty) return;
    state.renderDirty = false;
    render();
  });
}

function renderToContext(base, ctx, w, h, opts) {
  if (opts.mode === "script") renderScript(base, ctx, w, h, { ...opts, preApplied: true });
  else if (opts.mode === "dither") renderDither(base, ctx, w, h, { ...opts, preApplied: true });
  else ctx.drawImage(base, 0, 0, w, h);
}

function drawOriginal(destCtx, w, h, clipW) {
  if (!state.source) return;
  const sw = state.sourceW, sh = state.sourceH;
  const s = Math.max(w / sw, h / sh);
  const dw = sw * s, dh = sh * s;
  const dx = (w - dw) / 2, dy = (h - dh) / 2;
  destCtx.save();
  if (clipW != null) { destCtx.beginPath(); destCtx.rect(0, 0, clipW, h); destCtx.clip(); }
  destCtx.drawImage(state.source, dx, dy, dw, dh);
  destCtx.restore();
}

function render() {
  if (!state.source) {
    setStatusSegments("", "No image loaded", "");
    return;
  }
  state.renderDirty = false;
  const start = performance.now();
  const full = computeOutputSize(state.sourceW, state.sourceH, state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight, state.opts.outputFit);
  const pv = previewSize(full);
  const opts = renderOpts();
  const optsKey = JSON.stringify(opts);
  const still = state.sourceType !== "video" && !state.videoExporting && !state.cacheDisabled;
  const viewKey = optsKey + "|" + (state.compare ? state.compareFrac : "-") + "|" + (state.showOriginal ? "orig" : "");
  const stateKey = pv.w + "x" + pv.h + "|" + state.sourceId + "|" + viewKey;
  // A render that would produce the identical frame is skipped entirely. The
  // key covers every input that changes pixels or compositing; pan/zoom are
  // CSS transforms and are not part of it.
  if (still && stateKey === state.lastRenderKey) return;

  // Setting width/height to the same value still resets a canvas, so only
  // resize when the preview size actually changed.
  if (els.canvas.width !== pv.w || els.canvas.height !== pv.h) {
    els.canvas.width = pv.w;
    els.canvas.height = pv.h;
  }
  state.scale = scaleForZoom(state.zoom);
  // Compare split drags and toggles only change how the finished frame is
  // composited. Cache the post-pipeline frame keyed by every input that can
  // change it, so moving the split never re-runs effects or the Script stage.
  const key = still ? pv.w + "x" + pv.h + "|" + state.sourceId + "|" + optsKey : null;
  const cached = state.renderCache;
  if (still && cached && cached.key === key
      && cached.canvas.width === pv.w && cached.canvas.height === pv.h) {
    els.ctx.drawImage(cached.canvas, 0, 0);
  } else {
    // The stage cache key deliberately leaves the effects out: each stage is
    // keyed by the chain before it, so changing effect k reuses 0..k-1.
    const stageBaseKey = still
      ? pv.w + "x" + pv.h + "|" + state.sourceId + "|" + JSON.stringify(opts.adj || {})
      : null;
    const base = prepareBase(state.source, pv.w, pv.h, opts, stageBaseKey);
    renderToContext(base, els.ctx, pv.w, pv.h, opts);
    if (still) cacheRenderedFrame(key, pv);
  }

  if (state.showOriginal) {
    drawOriginal(els.ctx, pv.w, pv.h, null);
  } else if (state.compare) {
    drawOriginal(els.ctx, pv.w, pv.h, Math.round(pv.w * state.compareFrac));
  }

  state.lastRender = performance.now() - start;
  if (still) state.lastRenderKey = stateKey;
  applyTransform();
  applyZoomUI();
  updateCompareUI();
  updateStatus(full);
}

function cacheRenderedFrame(key, pv) {
  let cache = state.renderCache;
  if (!cache) {
    cache = state.renderCache = { canvas: document.createElement("canvas"), key: null };
  }
  if (cache.canvas.width !== pv.w || cache.canvas.height !== pv.h) {
    cache.canvas.width = pv.w;
    cache.canvas.height = pv.h;
  }
  const cctx = cache.canvas.getContext("2d");
  cctx.clearRect(0, 0, pv.w, pv.h);
  cctx.drawImage(els.canvas, 0, 0);
  cache.key = key;
}

function outputMeta() {
  const full = computeOutputSize(state.sourceW, state.sourceH, state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight, state.opts.outputFit);
  const pv = previewSize(full);
  return { full, pv };
}

/* Zoom is stored relative to the output image's real pixels (1 = 100%). */
function zoomForScale(scale) {
  const { full, pv } = outputMeta();
  if (!full.w || !pv.w) return scale;
  return scale * (full.w / pv.w);
}

function scaleForZoom(zoom) {
  const { full, pv } = outputMeta();
  if (!full.w || !pv.w) return zoom;
  return zoom * (pv.w / full.w);
}

function applyZoomUI() {
  const z = Math.max(0.01, state.zoom || 1);
  const pct = Math.round(z * 100);
  if (els.zoomLevel) {
    els.zoomLevel.textContent = pct + "%";
    els.zoomLevel.setAttribute("aria-label", "Zoom level: " + pct + "%");
  }
  if (els.zoomIn) els.zoomIn.disabled = !state.source || z >= 8 - 0.001;
  if (els.zoomOut) els.zoomOut.disabled = !state.source || z <= 0.1 + 0.001;
  if (els.zoomLevel) els.zoomLevel.disabled = !state.source;
  if (els.canvas) els.canvas.style.imageRendering = state.scale > 1.001 ? "pixelated" : "auto";
  if (els.zoomMenu) {
    els.zoomMenu.querySelectorAll("[data-zoom]").forEach(item => {
      const v = parseFloat(item.dataset.zoom);
      const active = isFinite(v) && Math.abs(z - v) < 0.005;
      item.setAttribute("aria-checked", active ? "true" : "false");
    });
  }
}

function setStatusSegments(zoom, size, time) {
  if (!els.statusBar) return;
  const values = [zoom, size, time];
  [els.statusZoom, els.statusSize, els.statusTime].forEach((el, i) => {
    if (!el) return;
    el.textContent = values[i];
    el.hidden = !values[i];
  });
  els.statusBar.classList.toggle("is-empty", values.filter(Boolean).length <= 1);
}

function updateStatus(full) {
  if (!els.statusBar) return;
  if (state.videoExporting) {
    setStatusSegments("", `Exporting video: ${state.videoExportFrames}/${state.videoExportTotal} frames`, "");
    return;
  }
  if (!state.source) { setStatusSegments("", "No image loaded", ""); return; }
  const zoom = Math.round(state.zoom * 100);
  setStatusSegments(`${zoom}%`, `${state.sourceW}×${state.sourceH}`, `${Math.round(state.lastRender)}ms`);
}

function updateCompareUI() {
  if (!els.compareOverlay || !els.compareSlider) return;
  const active = state.compare && state.source && !state.showOriginal;
  els.compareOverlay.hidden = !active;
  if (!active) return;
  const left = state.pan.x + els.canvas.width * state.scale * state.compareFrac;
  els.compareSlider.style.left = `${left}px`;
  els.compareSlider.style.top = `${state.pan.y}px`;
  els.compareSlider.style.height = `${els.canvas.height * state.scale}px`;
  els.compareSlider.style.bottom = "auto";
}

function centerCanvas() {
  const area = els.canvasArea.getBoundingClientRect();
  state.pan.x = (area.width - els.canvas.width * state.scale) / 2;
  state.pan.y = (area.height - els.canvas.height * state.scale) / 2;
}

function setZoom(zoom, anchor) {
  if (!state.source) return;
  const next = Math.max(0.1, Math.min(8, zoom));
  if (!isFinite(next) || next <= 0) return;
  const area = els.canvasArea.getBoundingClientRect();
  const ax = anchor && isFinite(anchor.x) ? anchor.x : area.width / 2;
  const ay = anchor && isFinite(anchor.y) ? anchor.y : area.height / 2;
  const nextScale = scaleForZoom(next);
  const curScale = state.scale || 1;
  const dx = (ax - state.pan.x) / curScale;
  const dy = (ay - state.pan.y) / curScale;
  state.scale = nextScale;
  state.zoom = next;
  state.pan.x = ax - dx * nextScale;
  state.pan.y = ay - dy * nextScale;
  applyTransform();
  applyZoomUI();
  updateStatus();
}

function zoomBy(factor) { setZoom(state.zoom * factor); }

function fitScaleValue() {
  const area = els.canvasArea.getBoundingClientRect();
  const w = els.canvas.width || 1, h = els.canvas.height || 1;
  if (!area.width || !area.height) return 1;
  return Math.min(area.width / w, area.height / h) * 0.94;
}

function fitToWindow() {
  if (!state.source) return;
  state.scale = fitScaleValue();
  state.zoom = Math.max(0.01, Math.min(1, zoomForScale(state.scale)));
  state.scale = scaleForZoom(state.zoom);
  centerCanvas();
  applyTransform();
  applyZoomUI();
  updateStatus();
}

function fitSmall() {
  if (!state.source) return;
  fitToWindow();
  setZoom(state.zoom * 0.5);
}

function setFullPage(on) {
  state.fullPage = !!on;
  if (els.workspace) els.workspace.classList.toggle("fullpage", state.fullPage);
  requestAnimationFrame(() => { if (state.source) fitToWindow(); });
}

function applyTransform() {
  els.canvas.style.transform = `translate(${state.pan.x}px, ${state.pan.y}px) scale(${state.scale})`;
  updateCompareUI();
}

function handleWheel(e) {
  if (!state.source) return;
  e.preventDefault();
  const rect = els.canvasArea.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const factor = e.deltaY > 0 ? 1 / 1.12 : 1.12;
  setZoom(state.zoom * factor, { x: mx, y: my });
}

let isPanning = false, panStart = { x: 0, y: 0 };
const activePointers = new Map();
let pinchStart = null;

function canvasFitsView() {
  const area = els.canvasArea.getBoundingClientRect();
  const w = els.canvas.width * state.scale;
  const h = els.canvas.height * state.scale;
  return w <= area.width + 1 && h <= area.height + 1;
}

function handlePointerDown(e) {
  if (!state.source) return;
  // The compare handle owns its gesture; never start a canvas pan from it
  // (a left-drag on the handle used to pan the image whenever it overflowed).
  if (e.target && e.target.closest && e.target.closest("#compare-slider")) return;
  if (e.pointerType === "touch") {
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.size === 2) {
      const pts = Array.from(activePointers.values());
      pinchStart = {
        dist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y),
        zoom: state.zoom,
        cx: (pts[0].x + pts[1].x) / 2,
        cy: (pts[0].y + pts[1].y) / 2
      };
      isPanning = false;
      return;
    }
  }
  if (e.button === 2) return;
  const canPan = e.button === 1 || state.spaceDown || (!canvasFitsView() && e.button === 0);
  if (!canPan) return;
  e.preventDefault();
  isPanning = true;
  panStart = { x: e.clientX - state.pan.x, y: e.clientY - state.pan.y };
  els.canvasArea.classList.add("panning");
  if (els.canvasArea.setPointerCapture) { try { els.canvasArea.setPointerCapture(e.pointerId); } catch (err) {} }
}

function handlePointerMove(e) {
  if (e.pointerType === "touch" && activePointers.has(e.pointerId)) {
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  }
  if (pinchStart && activePointers.size === 2) {
    const pts = Array.from(activePointers.values());
    const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
    if (pinchStart.dist > 0 && dist > 0) {
      const rect = els.canvasArea.getBoundingClientRect();
      setZoom(pinchStart.zoom * (dist / pinchStart.dist), { x: pinchStart.cx - rect.left, y: pinchStart.cy - rect.top });
    }
    return;
  }
  if (!isPanning) return;
  state.pan.x = e.clientX - panStart.x;
  state.pan.y = e.clientY - panStart.y;
  applyTransform();
}

function handlePointerUp(e) {
  if (e && e.pointerType === "touch") activePointers.delete(e.pointerId);
  if (activePointers.size < 2) pinchStart = null;
  if (isPanning) {
    isPanning = false;
    els.canvasArea.classList.remove("panning");
  }
}

const MAX_FILE_BYTES = 40 * 1024 * 1024;

function setDropZoneState(stateName, detail) {
  if (!els.dropZone) return;
  els.dropZone.dataset.state = stateName;
  if (stateName === "idle" && els.dropHint) {
    els.dropHint.textContent = "Drop an image or video here, paste it (Ctrl+V), or open a file.";
  }
  if (stateName === "hover" && els.dropHint) {
    els.dropHint.textContent = "Release to load it.";
  }
  if (stateName === "loading" && els.dropLoadingText) {
    els.dropLoadingText.textContent = `Loading ${(detail && detail.name) || "…"}…`;
  }
}

function showDropError(message) {
  if (!els.dropZone) return;
  if (els.dropError) els.dropError.textContent = message;
  setDropZoneState("error");
}

function loadFile(file) {
  if (!file) return;
  const type = file.type || "";
  if (!/^(image|video)\//.test(type)) {
    showDropError("That file type is not supported. Try a PNG, JPG or WebP image, or a WebM/MP4 video.");
    return;
  }
  if (file.size > MAX_FILE_BYTES) {
    showDropError(`This file is too large (${formatBytes(file.size)}). Try a smaller file (under ${formatBytes(MAX_FILE_BYTES)}).`);
    return;
  }
  setDropZoneState("loading", { name: file.name });
  const url = URL.createObjectURL(file);
  const previousUrl = state.sourceUrl;
  const isVideo = type.startsWith("video/");
  if (isVideo) {
    const vid = document.createElement("video");
    vid.src = url; vid.muted = true; vid.playsInline = true; vid.loop = true;
    vid.addEventListener("play", startVideoLoop);
    vid.addEventListener("pause", stopVideoLoop);
    vid.addEventListener("ended", stopVideoLoop);
    vid.addEventListener("loadedmetadata", () => {
      stopVideoLoop();
      if (state.video && state.video !== vid) state.video.pause();
      state.video = vid;
      state.source = vid;
      state.sourceType = "video";
      state.sourceW = vid.videoWidth;
      state.sourceH = vid.videoHeight;
      state.sourceId++;
      clearStageCache();
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      state.sourceUrl = url;
      els.canvasArea.classList.add("has-content");
      vid.play().catch(() => {});
      startVideoLoop();
      if (state.opts.palette === "__auto__") extractAutoPalette(vid);
      scheduleRender(0);
      setTimeout(fitToWindow, 30);
      setDropZoneState("idle");
    }, { once: true });
    vid.addEventListener("error", () => {
      URL.revokeObjectURL(url);
      showDropError("Couldn’t play this video. Try MP4 (H.264) or WebM (VP9).");
    }, { once: true });
  } else {
    const img = new Image();
    img.onload = () => {
      stopVideoLoop();
      if (state.video) { state.video.pause(); state.video = null; }
      state.source = img;
      state.sourceType = "image";
      state.sourceW = img.naturalWidth;
      state.sourceH = img.naturalHeight;
      state.sourceId++;
      clearStageCache();
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      state.sourceUrl = url;
      els.canvasArea.classList.add("has-content");
      if (state.opts.palette === "__auto__") extractAutoPalette(img);
      scheduleRender(0);
      requestAnimationFrame(() => { render(); fitToWindow(); pushHistory("load"); });
      setDropZoneState("idle");
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      showDropError("Couldn’t decode this file. Try re-saving it as PNG or MP4, then open it again.");
    };
    img.src = url;
  }
}

function extractAutoPalette(source) {
  const tmp = document.createElement("canvas");
  const maxDim = 200;
  const w = source.naturalWidth || source.videoWidth || source.width;
  const h = source.naturalHeight || source.videoHeight || source.height;
  const scale = Math.min(maxDim / w, maxDim / h, 1);
  tmp.width = Math.max(1, Math.round(w * scale));
  tmp.height = Math.max(1, Math.round(h * scale));
  const ctx = tmp.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(source, 0, 0, tmp.width, tmp.height);
  state.opts.customPalette = extractPalette(ctx.getImageData(0, 0, tmp.width, tmp.height), 8);
  if (state.opts.palette === "__auto__") updatePaletteSwatches();
}

function startVideoLoop() {
  stopVideoLoop();
  if (!state.video || state.video.paused || state.video.ended) return;
  if (document.hidden) return;
  function loop() {
    state.rafId = null;
    if (!state.video || state.video.paused || state.video.ended || state.videoExporting) return;
    if (document.hidden) return;
    render();
    state.rafId = requestAnimationFrame(loop);
  }
  state.rafId = requestAnimationFrame(loop);
}

function stopVideoLoop() {
  if (state.rafId) cancelAnimationFrame(state.rafId);
  state.rafId = null;
}

function openFile() { els.fileInput.click(); }

const NAMED_PRESETS = {
  terminal: { mode: "script", colorMode: "mono", monoColor: "#5dff8a", bgColor: "#03140a", usePalette: true,
    effects: ["crt", "grain"], effectParams: { crt: { scan: 55, curve: 20, mask: 30 }, grain: { amount: 18 } } },
  newsprint: { mode: "script", colorMode: "mono", monoColor: "#1b1a17", bgColor: "#f2ead8", autoLevels: true,
    effects: ["halftone"], effectParams: { halftone: { size: 4 } } },
  cyber: { mode: "script", colorMode: "spectrum", bgColor: "#08040f",
    effects: ["glitch", "bloom"], effectParams: { glitch: { shift: 12, slices: 14 }, bloom: { radius: 10, amount: 65 } } },
  gameboy: { mode: "dither", ditherKernel: "bayer4", ditherDepth: 4, palette: "Default",
    effects: ["retro"], effectParams: { retro: { palette: "gameboy" } } },
  blueprint: { mode: "script", colorMode: "spectrum", bgColor: "#04122a", autoLevels: true,
    effects: ["duotone", "edges"], effectParams: { duotone: { dark: "#041634", light: "#b9e6ff" }, edges: { amount: 35 } } },
  oldphoto: { mode: "script", colorMode: "spectrum", bgColor: "#120d08",
    effects: ["sepia", "grain", "vignette"], effectParams: { sepia: { amount: 85 }, grain: { amount: 30 }, vignette: { amount: 50, size: 70 } } },
  thermal: { mode: "script", colorMode: "spectrum", bgColor: "#080005",
    effects: ["thermal", "bloom"], effectParams: { thermal: { amount: 90 }, bloom: { radius: 9, amount: 70 } } }
};

function customPresets() {
  try { return JSON.parse(localStorage.getItem("glyphcraft-presets") || "{}") || {}; } catch (e) { return {}; }
}

function applyNamedPreset(name) {
  const p = NAMED_PRESETS[name] || customPresets()[name];
  if (!p) return;
  const base = defaultOpts();
  const effectList = p.effects || [];
  const idList = effectList.length === 0 || typeof effectList[0] === "string";
  state.opts = { ...base, ...p, effects: base.effects.map(fx => {
    if (idList) {
      return { id: fx.id, enabled: effectList.includes(fx.id), params: { ...fx.params, ...((p.effectParams || {})[fx.id] || {}) } };
    }
    const found = effectList.find(e => e.id === fx.id);
    return found ? { id: fx.id, enabled: !!found.enabled, params: { ...fx.params, ...(found.params || {}) } } : fx;
  }) };
  state.opts.adj = { ...DEFAULT_ADJ, ...(p.adj || {}) };
  rebuildRamp();
  updatePaletteSwatches();
  syncUIFromState();
  pushHistory("preset");
  scheduleRender(0);
  if (state.source) fitToWindow();
}

function savePreset() {
  const name = (window.prompt("Preset name:", "") || "").trim();
  if (!name) return;
  const all = customPresets();
  all[name] = JSON.parse(snapshot());
  try { localStorage.setItem("glyphcraft-presets", JSON.stringify(all)); } catch (e) { alert("Could not save preset"); }
}

function loadPreset() {
  const customs = Object.keys(customPresets());
  const names = [...Object.keys(NAMED_PRESETS), ...customs];
  const name = (window.prompt("Load preset:\n" + names.join(", "), "") || "").trim();
  if (name) applyNamedPreset(name);
}

async function exportImage() {
  if (!state.source || state.videoExporting) return;
  const full = computeOutputSize(state.sourceW, state.sourceH, state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight, state.opts.outputFit);
  const opts = renderOpts();
  const base = prepareBase(state.source, full.w, full.h, opts);
  const format = state.opts.exportFormat;

  if (format === "svg") {
    const svg = canvasToSvg(base, { ...opts, preApplied: true });
    saveBlob(new Blob([svg], { type: "image/svg+xml" }), "glyphcraft.svg");
    showToast("SVG exported");
    return;
  }
  if (format === "txt") {
    const txt = canvasToTxt(base, { ...opts, preApplied: true });
    saveBlob(new Blob([txt], { type: "text/plain" }), "glyphcraft.txt");
    showToast("TXT exported");
    return;
  }
  if (format === "webm") {
    await exportVideo(full, opts);
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = full.w; canvas.height = full.h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  renderToContext(base, ctx, full.w, full.h, opts);
  const quality = format === "jpg" ? state.opts.jpgQuality / 100 : 0.95;
  const typeMap = { png: "image/png", jpg: "image/jpeg", webp: "image/webp" };
  const blob = await canvasToBlob(canvas, typeMap[format] || "image/png", quality);
  saveBlob(blob, `glyphcraft.${format}`);
  showToast(`${format.toUpperCase()} exported`);
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function exportVideo(full, opts) {
  if (!window.MediaRecorder) { alert("WebM export is not supported in this browser"); return; }
  state.videoExporting = true;
  state.exportProgress = { active: true, format: "webm", progress: 0, total: 0 };
  const canvas = document.createElement("canvas");
  canvas.width = full.w; canvas.height = full.h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const video = state.video;
  const fps = 24;
  const duration = video && isFinite(video.duration) ? Math.min(video.duration, 20) : 1;
  const total = Math.max(1, Math.ceil(duration * fps));
  state.videoExportTotal = total;
  state.videoExportFrames = 0;
  state.exportProgress.total = total;

  if (video) { video.pause(); video.currentTime = 0; }

  const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm";
  const stream = canvas.captureStream(fps);
  const chunks = [];
  const recorder = new MediaRecorder(stream, { mimeType });
  recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
  const done = new Promise(resolve => {
    recorder.onstop = () => {
      saveBlob(new Blob(chunks, { type: mimeType }), "glyphcraft.webm");
      state.videoExporting = false;
      state.exportProgress.active = false;
      updateStatus();
      updateExportButton();
      showToast("WebM exported");
      resolve();
    };
  });
  recorder.start(500);

  for (let i = 0; i < total; i++) {
    if (video) {
      video.currentTime = i / fps;
      await new Promise(r => { video.onseeked = r; setTimeout(r, 120); });
    }
    const base = prepareBase(video || state.source, full.w, full.h, opts);
    renderToContext(base, ctx, full.w, full.h, opts);
    state.videoExportFrames = i + 1;
    state.exportProgress.progress = i + 1;
    updateStatus();
    updateExportButton();
    await new Promise(r => setTimeout(r, 1000 / fps));
  }
  recorder.stop();
  if (video) video.play().catch(() => {});
  await done;
}

function saveSectionCollapse() {
  try {
    const collapsed = {};
    document.querySelectorAll(".panel-section").forEach(sec => {
      collapsed[sec.id] = sec.classList.contains("collapsed");
    });
    localStorage.setItem("glyphcraft-section-collapse", JSON.stringify(collapsed));
  } catch (e) {}
}
function loadSectionCollapse() {
  try {
    const collapsed = JSON.parse(localStorage.getItem("glyphcraft-section-collapse") || "{}");
    Object.entries(collapsed).forEach(([id, isCollapsed]) => {
      const sec = document.getElementById(id);
      if (sec && isCollapsed) sec.classList.add("collapsed");
    });
  } catch (e) {}
}

function showToast(message, duration = 2500) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  if (!document.getElementById("toast-style")) {
    const style = document.createElement("style");
    style.id = "toast-style";
    style.textContent = `
      @keyframes toast-in { from { opacity: 0; transform: translateX(-50%) translateY(16px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
      @keyframes toast-out { from { opacity: 1; transform: translateX(-50%) translateY(0); } to { opacity: 0; transform: translateX(-50%) translateY(16px); } }
    `;
    document.head.appendChild(style);
  }
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "toast-out 0.2s ease-in forwards";
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

function updateExportButton() {
  if (!els.btnExport) return;
  if (state.exportProgress.active) {
    const pct = Math.round((state.exportProgress.progress / state.exportProgress.total) * 100);
    els.btnExport.textContent = `Exporting ${state.exportProgress.format.toUpperCase()} ${pct}%`;
    els.btnExport.disabled = true;
  } else if (state.videoExporting) {
    els.btnExport.textContent = "Exporting...";
    els.btnExport.disabled = true;
  } else {
    els.btnExport.textContent = "Export Image";
    els.btnExport.disabled = false;
  }
}

function resetAll() {
  if (state.pendingReset) {
    state.opts = defaultOpts();
    state.compare = false;
    rebuildRamp();
    updatePaletteSwatches();
    syncUIFromState();
    pushHistory("reset");
    state.pendingReset = false;
    if (state.source) { scheduleRender(0); requestAnimationFrame(fitToWindow); }
    showToast("All settings reset");
    return;
  }
  state.pendingReset = true;
  showToast("Press Reset All again to confirm");
  setTimeout(() => { state.pendingReset = false; }, 3000);
}

function resetSection(name) {
  const o = state.opts;
  if (name === "mode") o.mode = "script";
  if (name === "script") {
    Object.assign(o, { depth: 80, charCategory: "all", charSet: "all", charInject: "", charOffset: 0,
      textStyle: "regular", usePalette: true, transparentBg: false, autoLevels: true, bgColor: "#0b0b0c" });
    rebuildRamp();
  }
  if (name === "dither") { o.ditherKernel = "floyd-steinberg"; o.ditherDepth = 4; }
  if (name === "color") { o.colorMode = "spectrum"; o.palette = "Default"; o.customPalette = null; o.monoColor = "#e9dfc8"; }
  if (name === "adjustments") o.adj = { ...DEFAULT_ADJ };
  if (name === "effects") o.effects = defaultEffects();
  if (name === "output") { o.outputPreset = "original"; o.outputWidth = 1920; o.outputHeight = 1080; o.outputFit = "contain"; o.exportFormat = "png"; }
  updatePaletteSwatches();
  syncUIFromState();
  pushHistory("reset-" + name);
  scheduleRender(0);
}

function syncUIFromState() {
  const o = state.opts;
  els.selectMode.value = o.mode;
  els.depth.value = o.depth; els.depthNum.value = o.depth;
  els.charCategory.value = o.charCategory;
  els.charSet.value = o.charSet;
  els.charInject.value = o.charInject;
  els.charOffset.value = o.charOffset; els.charOffsetNum.value = o.charOffset;
  els.textStyle.value = o.textStyle;
  els.charPreset.value = o.charPreset;
  els.customCharset.value = o.customCharset;
  els.customCharsetRow.hidden = o.charPreset !== "custom";
  els.cellSize.value = o.cellSize; els.cellSizeNum.value = o.cellSize;
  els.glyphWeight.value = o.glyphWeight; els.glyphWeightNum.value = o.glyphWeight;
  els.glyphInvert.checked = o.glyphInvert;
  els.glyphColor.checked = o.glyphColor;
  els.usePalette.checked = o.usePalette;
  els.transparentBg.checked = o.transparentBg;
  els.autoLevels.checked = o.autoLevels;
  els.bgColor.value = o.bgColor;
  els.colorMode.value = o.colorMode;
  els.paletteSelect.value = o.palette;
  els.ditherKernel.value = o.ditherKernel;
  els.ditherDepth.value = o.ditherDepth; els.ditherDepthNum.value = o.ditherDepth;
  els.ditherSerpentine.checked = o.ditherSerpentine;
  const names = ["Brightness", "Contrast", "Saturation", "Hue", "Highlights", "Shadows", "Sharpen", "Blur"];
  names.forEach(n => {
    const key = n.toLowerCase();
    els["adj" + n].value = o.adj[key];
    els["adj" + n + "Num"].value = o.adj[key];
  });
  els.adjInvert.checked = o.adj.invert;
  els.adjSepia.checked = o.adj.sepia;
  if (!SIZE_PRESETS.some(p => p.id === o.outputPreset)) o.outputPreset = "original";
  els.outputPreset.value = o.outputPreset;
  syncPresetPicker();
  els.outputWidth.value = o.outputWidth;
  els.outputHeight.value = o.outputHeight;
  els.outputFit.value = o.outputFit;
  els.outputLockRatio.checked = o.outputLockRatio;
  els.exportFormat.value = o.exportFormat;
  els.jpgQuality.value = o.jpgQuality; els.jpgQualityNum.value = o.jpgQuality;
  els.jpgQualityControl.hidden = o.exportFormat !== "jpg";
  updateOutputCustomVisibility();
  toggleModeSections();
  renderEffectsList();
  updatePaletteSwatches();
}

function toggleModeSections() {
  const mode = state.opts.mode;
  els.sectionScript.style.display = mode === "script" ? "" : "none";
  els.sectionDither.style.display = mode === "dither" ? "" : "none";
  els.sectionColor.style.display = mode === "script" ? "" : "none";
  els.controlPalette.hidden = state.opts.colorMode !== "palette";
}

function renderEffectsList() {
  if (!els.effectsList) return;
  els.effectsList.innerHTML = "";
  if (state.opts.effects.length === 0) {
    const empty = document.createElement("div");
    empty.className = "effect-empty";
    empty.style.cssText = "padding: var(--space-4); text-align: center; color: var(--text-muted); font-size: 13px;";
    empty.textContent = "No effects added. Enable effects from the presets or add them manually.";
    els.effectsList.appendChild(empty);
    return;
  }
  state.opts.effects.forEach((fx, index) => {
    const def = EFFECTS.find(e => e.id === fx.id);
    if (!def) return;
    const item = document.createElement("div");
    item.className = "effect-item";
    item.dataset.index = index;
    item.dataset.id = fx.id;

    const handle = document.createElement("button");
    handle.type = "button";
    handle.className = "drag-handle";
    handle.textContent = "⠿";
    handle.title = "Drag, or press Alt+Up / Alt+Down, to reorder";
    handle.setAttribute("aria-label", "Reorder " + def.name + ". Press Alt+Up or Alt+Down to move.");

    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = fx.enabled;
    check.title = "Enable " + def.name;
    check.setAttribute("aria-label", "Enable " + def.name);
    check.addEventListener("change", () => {
      fx.enabled = check.checked;
      pushHistory("fx-toggle-" + fx.id);
      scheduleRender(80);
    });

    const name = document.createElement("span");
    name.className = "effect-name";
    name.textContent = def.name;

    const actions = document.createElement("div");
    actions.className = "effect-actions";

    const resetBtn = document.createElement("button");
    resetBtn.className = "btn btn-small";
    resetBtn.textContent = "Reset";
    resetBtn.title = "Reset to defaults";
    resetBtn.setAttribute("aria-label", "Reset " + def.name);
    resetBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      Object.assign(fx.params, effectDefaults(fx.id));
      renderEffectsList();
      pushHistory("fx-reset-" + fx.id);
      scheduleRender(80);
    });

    const removeBtn = document.createElement("button");
    removeBtn.className = "btn btn-small";
    removeBtn.textContent = "Remove";
    removeBtn.title = "Remove effect";
    removeBtn.setAttribute("aria-label", "Remove " + def.name);
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      state.opts.effects.splice(index, 1);
      pushHistory("fx-remove-" + fx.id);
      renderEffectsList();
      scheduleRender(80);
    });

    actions.appendChild(resetBtn);
    actions.appendChild(removeBtn);

    const head = document.createElement("div");
    head.className = "effect-head";
    head.append(handle, check, name, actions);
    item.appendChild(head);

    if (def.params.length) {
      const params = document.createElement("div");
      params.className = "effect-params";
      def.params.forEach(p => {
        const wrap = document.createElement("label");
        wrap.className = "param";
        const label = document.createElement("span");
        label.textContent = p.label;
        wrap.appendChild(label);
        let input;
        if (p.type === "color") {
          input = document.createElement("input");
          input.type = "color";
          input.value = fx.params[p.key];
        } else if (p.type === "select") {
          input = document.createElement("select");
          (p.options || []).forEach(([val, text]) => {
            const opt = document.createElement("option");
            opt.value = val; opt.textContent = text;
            input.appendChild(opt);
          });
          input.value = fx.params[p.key];
        } else {
          // Create wrapper for slider + number input
          const inputWrap = document.createElement("div");
          inputWrap.className = "control-input-wrap";
          inputWrap.style.display = "flex";
          inputWrap.style.alignItems = "center";
          inputWrap.style.gap = "8px";
          inputWrap.style.width = "100%";

          input = document.createElement("input");
          input.type = "range";
          input.min = p.min; input.max = p.max; input.step = p.step;
          input.value = fx.params[p.key];
          input.style.flex = "1";

          const numInput = document.createElement("input");
          numInput.type = "number";
          numInput.min = p.min; numInput.max = p.max; numInput.step = p.step;
          numInput.value = fx.params[p.key];

          // Commit a finished value: clamp, snap to the step grid, rewrite both
          // controls, and re-render. Typing uses a separate path so a partial
          // entry ("" or "1" on the way to "12") is never rewritten mid-typing.
          const commit = (value, history, notify = true) => {
            const next = clampToParam(Number.isFinite(value) ? value : p.def, p);
            fx.params[p.key] = next;
            input.value = next;
            numInput.value = next;
            numInput.removeAttribute("aria-invalid");
            if (history) pushHistory("fx-" + fx.id + "-" + p.key);
            if (notify) scheduleRender(140);
            return next;
          };
          const finishTyping = () => {
            const raw = parseFloat(numInput.value);
            commit(Number.isFinite(raw) ? raw : fx.params[p.key], true);
          };

          input.addEventListener("input", () => {
            const next = clampToParam(+input.value, p);
            fx.params[p.key] = next;
            numInput.value = next;
            scheduleRender(140);
          });
          input.addEventListener("change", () => pushHistory("fx-" + fx.id + "-" + p.key));

          numInput.addEventListener("input", () => {
            const text = numInput.value.trim();
            if (text === "" || text === "-" || text === "." || text === "-.") {
              numInput.setAttribute("aria-invalid", "true");
              return;
            }
            const raw = parseFloat(text);
            if (!Number.isFinite(raw)) return;
            if (raw < p.min || raw > p.max) {
              numInput.setAttribute("aria-invalid", "true");
              return;
            }
            // Live preview while typing, but leave the text exactly as typed.
            fx.params[p.key] = raw;
            input.value = raw;
            numInput.removeAttribute("aria-invalid");
            scheduleRender(140);
          });
          numInput.addEventListener("blur", finishTyping);
          numInput.addEventListener("keydown", (e) => {
            const mult = e.shiftKey ? 10 : 1;
            if (e.key === "ArrowUp" || e.key === "ArrowDown") {
              e.preventDefault();
              const base = Number.isFinite(parseFloat(numInput.value)) ? parseFloat(numInput.value) : fx.params[p.key];
              commit(base + (e.key === "ArrowUp" ? p.step * mult : -p.step * mult), true);
            } else if (e.key === "PageUp" || e.key === "PageDown") {
              e.preventDefault();
              const base = Number.isFinite(parseFloat(numInput.value)) ? parseFloat(numInput.value) : fx.params[p.key];
              commit(base + (e.key === "PageUp" ? p.step * 10 : -p.step * 10), true);
            } else if (e.key === "Enter") {
              e.preventDefault();
              finishTyping();
            }
          });
          numInput.addEventListener("wheel", (e) => {
            e.preventDefault();
            const base = Number.isFinite(parseFloat(numInput.value)) ? parseFloat(numInput.value) : fx.params[p.key];
            commit(base + (e.deltaY < 0 ? p.step : -p.step), true);
          }, { passive: false });

          input.addEventListener("dblclick", () => commit(p.def, true));
          numInput.addEventListener("dblclick", () => commit(p.def, true));

          inputWrap.appendChild(input);
          inputWrap.appendChild(numInput);
          attachStepper(
            inputWrap,
            "fx." + fx.id + "." + p.key,
            def.name + " " + p.label,
            (dir, first) => {
              const base = Number.isFinite(parseFloat(numInput.value)) ? parseFloat(numInput.value) : fx.params[p.key];
              commit(base + (dir === "up" ? p.step : -p.step), first, false);
            },
            () => scheduleRender(140)
          );
          wrap.appendChild(inputWrap);
          params.appendChild(wrap);
          return;
        }
        input.addEventListener("input", () => {
          fx.params[p.key] = input.value;
          pushHistory("fx-" + fx.id + "-" + p.key);
          scheduleRender(100);
        });
        wrap.appendChild(input);
        params.appendChild(wrap);
      });
      item.appendChild(params);
    }

    els.effectsList.appendChild(item);
  });
}

function escHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

// Draw the true aspect ratio, scaled into a 16x16 box.
function presetSwatch(w, h) {
  if (!w || !h) {
    return '<svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><rect x="2.5" y="2.5" width="11" height="11" rx="1" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 2"/></svg>';
  }
  const ratio = w / h;
  let rw, rh;
  if (ratio >= 1) { rw = 13; rh = Math.max(2.5, 13 / ratio); }
  else { rh = 13; rw = Math.max(2.5, 13 * ratio); }
  const x = (16 - rw) / 2, y = (16 - rh) / 2;
  return '<svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><rect x="' + x.toFixed(2) +
    '" y="' + y.toFixed(2) + '" width="' + rw.toFixed(2) + '" height="' + rh.toFixed(2) +
    '" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>';
}

function presetLabelParts(preset) {
  const match = String(preset.label).match(/^(.*?)\s*(\d+×\d+)$/);
  if (!match) return { name: preset.label, dim: "" };
  return match[1] ? { name: match[1], dim: match[2] } : { name: match[2], dim: "" };
}

function presetOptionHtml(preset) {
  const selected = preset.id === els.outputPreset.value;
  const parts = presetLabelParts(preset);
  let name = parts.name;
  if (preset.brand === "iPhone") name = name.replace(/^iPhone\s+/, "");
  if (preset.brand === "Galaxy") name = name.replace(/^Galaxy\s+/, "");
  const dim = parts.dim ? '<span class="preset-option-dim">' + escHtml(parts.dim) + "</span>" : "";
  const unverified = preset.unverified
    ? '<span class="preset-unverified" title="Resolution unverified" aria-label="unverified resolution">*</span>'
    : "";
  return '<div class="preset-option" role="option" tabindex="-1" data-preset-id="' + escHtml(preset.id) +
    '" aria-selected="' + selected + '"' + (preset.unverified ? ' title="Resolution unverified"' : "") + ">" +
    '<span class="preset-swatch" aria-hidden="true">' + presetSwatch(preset.w, preset.h) + "</span>" +
    '<span class="preset-option-label"><span class="preset-option-name">' + escHtml(name) + "</span>" +
    dim + "</span>" + unverified + '<span class="preset-check" aria-hidden="true">✓</span></div>';
}

function renderPresetList() {
  const list = els.outputPresetList;
  if (!list) return;
  const query = (els.outputPresetSearch ? els.outputPresetSearch.value : "").trim().toLowerCase();
  const groups = [];
  SIZE_PRESETS.forEach(preset => {
    let group = groups.find(item => item.name === preset.group);
    if (!group) { group = { name: preset.group, items: [] }; groups.push(group); }
    group.items.push(preset);
  });

  let html = "";
  groups.forEach(group => {
    const matches = group.items.filter(preset =>
      !query || preset.label.toLowerCase().includes(query) || group.name.toLowerCase().includes(query)
    );
    if (!matches.length) return;
    html += '<div class="preset-group" role="group" aria-label="' + escHtml(group.name) + '">';
    html += '<div class="preset-group-label">' + escHtml(group.name) + "</div>";

    if (group.name === "Phone wallpaper") {
      const iphone = matches.filter(preset => preset.brand === "iPhone");
      const galaxy = matches.filter(preset => preset.brand === "Galaxy");
      if (query) {
        if (iphone.length) {
          html += '<div class="preset-brand-label">iPhone</div>' + iphone.map(presetOptionHtml).join("");
        }
        if (galaxy.length) {
          html += '<div class="preset-brand-label">Galaxy</div>' + galaxy.map(presetOptionHtml).join("");
        }
      } else {
        const expanded = state.presetExpanded;
        html += '<div class="preset-brand-label">iPhone</div>';
        html += iphone.slice(0, 3).map(presetOptionHtml).join("");
        html += '<div class="preset-phone-extra' + (expanded ? " expanded" : "") + '"' + (expanded ? "" : " inert") + '><div class="preset-phone-inner">';
        html += iphone.slice(3).map(presetOptionHtml).join("");
        if (galaxy.length) {
          html += '<div class="preset-brand-label">Galaxy</div>' + galaxy.map(presetOptionHtml).join("");
        }
        html += "</div></div>";
        html += '<button class="preset-more" type="button" data-preset-more aria-expanded="' + expanded + '">' +
          (expanded ? "View less" : "View more") + "</button>";
        html += '<div class="preset-note">* Resolution unverified — check before export.</div>';
      }
    } else {
      html += matches.map(presetOptionHtml).join("");
    }
    html += "</div>";
  });

  list.innerHTML = html || '<div class="preset-empty">No presets found</div>';
}

function syncPresetPicker() {
  if (!els.outputPreset) return;
  const preset = SIZE_PRESETS.find(item => item.id === els.outputPreset.value) ||
    SIZE_PRESETS.find(item => item.id === "original");
  if (els.outputPresetValue) els.outputPresetValue.textContent = preset ? preset.label : "";
  if (els.outputPresetSwatch) els.outputPresetSwatch.innerHTML = presetSwatch(preset && preset.w, preset && preset.h);
  if (els.outputPresetList) {
    els.outputPresetList.querySelectorAll(".preset-option").forEach(option => {
      option.setAttribute("aria-selected", String(option.dataset.presetId === els.outputPreset.value));
    });
  }
}

function visiblePresetOptions() {
  if (!els.outputPresetList) return [];
  return Array.from(els.outputPresetList.querySelectorAll(".preset-option")).filter(option => {
    if (option.closest("[inert]")) return false;
    const rect = option.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  });
}

function openPresetPicker() {
  if (!els.outputPresetPopup || !els.outputPresetTrigger) return;
  const current = SIZE_PRESETS.find(preset => preset.id === els.outputPreset.value);
  if (current && current.group === "Phone wallpaper") {
    const iphones = SIZE_PRESETS.filter(preset => preset.group === "Phone wallpaper" && preset.brand === "iPhone");
    if (current.brand === "Galaxy" || iphones.indexOf(current) >= 3) state.presetExpanded = true;
  }
  els.outputPresetPopup.hidden = false;
  state.presetOpen = true;
  els.outputPresetTrigger.setAttribute("aria-expanded", "true");
  renderPresetList();
  syncPresetPicker();
  requestAnimationFrame(() => {
    const selected = els.outputPresetList && els.outputPresetList.querySelector('[aria-selected="true"]');
    if (selected) selected.scrollIntoView({ block: "nearest" });
    if (els.outputPresetSearch) els.outputPresetSearch.focus();
  });
}

function closePresetPicker(focusTrigger) {
  if (!els.outputPresetPopup || els.outputPresetPopup.hidden) return;
  els.outputPresetPopup.hidden = true;
  state.presetOpen = false;
  els.outputPresetTrigger.setAttribute("aria-expanded", "false");
  if (els.outputPresetSearch) els.outputPresetSearch.value = "";
  if (focusTrigger !== false) els.outputPresetTrigger.focus();
}

function choosePreset(id) {
  if (!SIZE_PRESETS.some(preset => preset.id === id)) return;
  if (els.outputPreset.value !== id) {
    els.outputPreset.value = id;
    els.outputPreset.dispatchEvent(new Event("change", { bubbles: true }));
  } else {
    updateOutputCustomVisibility();
    syncPresetPicker();
  }
  closePresetPicker();
}

function togglePresetExpanded() {
  const extra = els.outputPresetList && els.outputPresetList.querySelector(".preset-phone-extra");
  const more = els.outputPresetList && els.outputPresetList.querySelector("[data-preset-more]");
  if (!extra || !more) return;
  state.presetExpanded = !state.presetExpanded;
  if (state.presetExpanded) {
    extra.removeAttribute("inert");
    requestAnimationFrame(() => extra.classList.add("expanded"));
    more.textContent = "View less";
    more.setAttribute("aria-expanded", "true");
  } else {
    extra.classList.remove("expanded");
    extra.setAttribute("inert", "");
    more.textContent = "View more";
    more.setAttribute("aria-expanded", "false");
  }
}

function populateOutputPresets() {
  const select = els.outputPreset;
  select.innerHTML = "";
  let currentGroup = null;
  let optgroup = null;
  SIZE_PRESETS.forEach(p => {
    if (p.group !== currentGroup) {
      currentGroup = p.group;
      optgroup = document.createElement("optgroup");
      optgroup.label = currentGroup;
      select.appendChild(optgroup);
    }
    const opt = document.createElement("option");
    opt.value = p.id; opt.textContent = p.label;
    if (p.w && p.h) { opt.dataset.w = p.w; opt.dataset.h = p.h; }
    optgroup.appendChild(opt);
  });
  if (!SIZE_PRESETS.some(p => p.id === state.opts.outputPreset)) state.opts.outputPreset = "original";
  select.value = state.opts.outputPreset;
  renderPresetList();
  syncPresetPicker();
  updateOutputCustomVisibility();
}

function filterControls(q) {
  const query = (q || "").toLowerCase().trim();
  document.querySelectorAll(".panel-section").forEach(sec => {
    const items = sec.querySelectorAll(".control, .dropdown-wrap, .palette-swatches, .presets-bar, .effect-item");
    let visible = 0;
    items.forEach(item => {
      const hit = !query || item.textContent.toLowerCase().includes(query);
      item.classList.toggle("hidden", !hit);
      if (hit) visible++;
    });
    sec.style.display = (!query || visible > 0) ? "" : "none";
  });
}

function updateOutputCustomVisibility() {
  const isCustom = els.outputPreset.value === "custom";
  els.outputCustomRow.hidden = !isCustom;
  if (isCustom) {
    els.outputWidth.value = state.opts.outputWidth;
    els.outputHeight.value = state.opts.outputHeight;
  }
  checkOutputSizeWarning();
  syncPresetPicker();
}

function checkOutputSizeWarning() {
  const w = +els.outputWidth.value;
  const h = +els.outputHeight.value;
  const isLarge = w * h > 4000000 || w > 4096 || h > 4096;
  els.outputWarn.classList.toggle("hidden", !isLarge);
}

function updateOutputSizeFromPreset() {
  const opt = els.outputPreset.options[els.outputPreset.selectedIndex];
  if (opt && opt.dataset.w && opt.dataset.h) {
    const w = +opt.dataset.w;
    const h = +opt.dataset.h;
    state.opts.outputWidth = w;
    state.opts.outputHeight = h;
    els.outputWidth.value = w;
    els.outputHeight.value = h;
    checkOutputSizeWarning();
  }
}

function toggleCompare() {
  state.compare = !state.compare;
  if (state.compare && !state.source) state.compare = false;
  scheduleRender(0);
}

function closeAllMenus(except) {
  if (state.presetOpen) closePresetPicker(false);
  document.querySelectorAll(".menu-dropdown.open, .zoom-menu.open").forEach(dd => {
    if (dd === except) return;
    dd.classList.remove("open");
    const owner = dd.parentElement && dd.parentElement.querySelector('[aria-controls="' + dd.id + '"]');
    if (owner) owner.setAttribute("aria-expanded", "false");
  });
}

function menuItems(dd) {
  return Array.from(dd.querySelectorAll(".menu-item")).filter(item => !item.disabled && item.offsetParent !== null);
}

function focusFirstMenuItem(dd) {
  const items = menuItems(dd);
  if (items.length) items[0].focus();
}

function moveMenuFocus(e, dd) {
  if (!["ArrowDown", "ArrowUp", "Home", "End", "Escape", "Tab"].includes(e.key)) return;
  const items = menuItems(dd);
  if (!items.length) return;
  const index = items.indexOf(document.activeElement);
  if (e.key === "Escape") {
    e.preventDefault();
    closeAllMenus();
    const owner = dd.parentElement && dd.parentElement.querySelector('[aria-controls="' + dd.id + '"]');
    if (owner) owner.focus();
    return;
  }
  if (e.key === "Tab") { closeAllMenus(); return; }
  e.preventDefault();
  if (e.key === "Home") { items[0].focus(); return; }
  if (e.key === "End") { items[items.length - 1].focus(); return; }
  const delta = e.key === "ArrowDown" ? 1 : -1;
  const next = index < 0 ? (delta > 0 ? 0 : items.length - 1) : (index + delta + items.length) % items.length;
  items[next].focus();
}

function togglePanel() {
  if (state.fullPage) { setFullPage(false); return; }
  const isMobile = window.innerWidth <= 768;
  if (isMobile) {
    els.panel.classList.toggle("open");
  } else {
    els.panel.classList.toggle("collapsed");
    els.workspace.classList.toggle("panel-collapsed");
  }
  requestAnimationFrame(() => {
    if (!state.source) return;
    centerCanvas();
    applyTransform();
    updateCompareUI();
  });
}

function zoomToPreset(value) {
  if (value === "fit") fitToWindow();
  else if (value === "fullpage") setFullPage(true);
  else if (value === "small") fitSmall();
  else setZoom(parseFloat(value));
}

function setupEventListeners() {
  on(els.fileInput, "change", e => {
    const file = e.target.files && e.target.files[0];
    if (file) loadFile(file);
    e.target.value = "";
  });
  on(els.openFileBtn, "click", e => { e.stopPropagation(); openFile(); });
  on(els.dropZone, "click", e => { if (e.target.closest("button")) return; openFile(); });

  window.addEventListener("dragover", e => { e.preventDefault(); if (els.dropZone) setDropZoneState("hover"); });
  window.addEventListener("dragleave", e => {
    if (!e.relatedTarget) setDropZoneState("idle");
  });
  window.addEventListener("drop", e => {
    e.preventDefault();
    setDropZoneState("idle");
    if (e.dataTransfer && e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
  });

  on(els.canvasArea, "wheel", handleWheel, { passive: false });
  on(els.canvasArea, "pointerdown", handlePointerDown);
  window.addEventListener("pointermove", handlePointerMove);
  window.addEventListener("pointerup", handlePointerUp);
  window.addEventListener("pointercancel", handlePointerUp);

  function showShortcuts() {
    if (document.querySelector(".modal-backdrop")) return;
    const modal = document.createElement("div");
    modal.className = "modal-backdrop";
    modal.innerHTML = `
      <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="shortcuts-title">
        <h3 class="modal-title" id="shortcuts-title">Keyboard shortcuts</h3>
        <dl class="shortcut-list">
          <dt>Ctrl O</dt><dd>Open a file</dd>
          <dt>E</dt><dd>Export image</dd>
          <dt>R</dt><dd>Reset all (press twice)</dd>
          <dt>Ctrl Z</dt><dd>Undo</dd>
          <dt>Ctrl ⇧ Z</dt><dd>Redo</dd>
          <dt>C</dt><dd>Toggle compare split</dd>
          <dt>O</dt><dd>Hold to show original</dd>
          <dt>+ / −</dt><dd>Zoom in / out</dd>
          <dt>0 / F</dt><dd>Fit window</dd>
          <dt>⇧F</dt><dd>Full page</dd>
          <dt>⇧S</dt><dd>Fit small</dd>
          <dt>1 / 2</dt><dd>100% / 200% zoom</dd>
          <dt>Space</dt><dd>Hold to pan (drag)</dd>
          <dt>\\</dt><dd>Toggle controls panel</dd>
          <dt>T</dt><dd>Toggle theme</dd>
          <dt>Esc</dt><dd>Close menus / compare / full page</dd>
          <dt>?</dt><dd>Show this help</dd>
        </dl>
        <button class="btn btn-primary" type="button" data-close-modal>Got it</button>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (e) => {
      if (e.target === modal || e.target.hasAttribute("data-close-modal")) modal.remove();
    });
    const closeBtn = modal.querySelector("[data-close-modal]");
    if (closeBtn) closeBtn.focus();
  }

  /* ---- Menus: click to open, outside click / Esc to close, arrow keys ---- */
  document.querySelectorAll(".menubar .menu").forEach(menu => {
    const btn = menu.querySelector(".menu-btn");
    const dd = menu.querySelector(".menu-dropdown");
    if (!btn || !dd) return;
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const willOpen = !dd.classList.contains("open");
      closeAllMenus(willOpen ? dd : null);
      dd.classList.toggle("open", willOpen);
      btn.setAttribute("aria-expanded", String(willOpen));
      if (willOpen) requestAnimationFrame(() => focusFirstMenuItem(dd));
    });
    btn.addEventListener("keydown", e => {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        closeAllMenus(dd);
        dd.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
        requestAnimationFrame(() => focusFirstMenuItem(dd));
      }
    });
    dd.addEventListener("keydown", e => moveMenuFocus(e, dd));
  });

  document.addEventListener("click", e => {
    if (!e.target.closest(".menu") && !e.target.closest(".zoom-menu-wrap") && !e.target.closest(".preset-picker")) closeAllMenus();
  });

  /* ---- Menu actions ---- */
  document.querySelectorAll(".menu-item[data-action]").forEach(item => {
    item.addEventListener("click", () => {
      const action = item.dataset.action;
      closeAllMenus();
      if (action === "open") openFile();
      else if (action === "export") exportImage();
      else if (action === "reset") resetAll();
      else if (action === "undo") undo();
      else if (action === "redo") redo();
      else if (action === "compare") toggleCompare();
      else if (action === "fit") fitToWindow();
      else if (action === "fullpage") setFullPage(!state.fullPage);
      else if (action === "fit-small") fitSmall();
      else if (action === "zoom-in") zoomBy(1.25);
      else if (action === "zoom-out") zoomBy(1 / 1.25);
      else if (action === "zoom-100") setZoom(1);
      else if (action === "zoom-200") setZoom(2);
      else if (action === "panel") togglePanel();
    });
    if (item.dataset.action === "original") {
      item.addEventListener("pointerdown", e => { e.preventDefault(); state.showOriginal = true; scheduleRender(0); });
      item.addEventListener("pointerup", () => { state.showOriginal = false; scheduleRender(0); });
      item.addEventListener("pointerleave", () => { if (state.showOriginal) { state.showOriginal = false; scheduleRender(0); } });
    }
  });

  /* ---- Zoom toolbar ---- */
  on(els.zoomIn, "click", () => zoomBy(1.25));
  on(els.zoomOut, "click", () => zoomBy(1 / 1.25));
  on(els.zoomLevel, "click", e => {
    e.stopPropagation();
    const willOpen = !els.zoomMenu.classList.contains("open");
    closeAllMenus(willOpen ? els.zoomMenu : null);
    els.zoomMenu.classList.toggle("open", willOpen);
    els.zoomLevel.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) requestAnimationFrame(() => focusFirstMenuItem(els.zoomMenu));
  });
  els.zoomMenu.querySelectorAll("[data-zoom]").forEach(item => {
    item.addEventListener("click", () => {
      closeAllMenus();
      zoomToPreset(item.dataset.zoom);
    });
  });
  els.zoomMenu.addEventListener("keydown", e => moveMenuFocus(e, els.zoomMenu));

  on(els.themeToggle, "click", toggleTheme);
  on(els.panelToggleBtn, "click", togglePanel);

  on(els.btnExport, "click", exportImage);
  on(els.btnReset, "click", resetAll);
  on(els.panelSearch, "input", () => filterControls(els.panelSearch.value));
  on(els.btnSavePreset, "click", savePreset);
  on(els.btnLoadPreset, "click", loadPreset);

  /* ---- Sections ---- */
  document.querySelectorAll(".section-title").forEach(title => {
    title.addEventListener("click", () => {
      const sec = title.closest(".panel-section");
      if (!sec) return;
      sec.classList.toggle("collapsed");
      title.setAttribute("aria-expanded", String(!sec.classList.contains("collapsed")));
      saveSectionCollapse();
    });
  });
  document.querySelectorAll(".section-reset").forEach(btn => {
    btn.addEventListener("click", e => { e.stopPropagation(); resetSection(btn.dataset.section); });
  });

  /* ---- Keyboard ---- */
  window.addEventListener("keydown", e => {
    const target = e.target;
    const typing = target && target.matches && target.matches("input, select, textarea");
    const textEntry = target && target.matches && target.matches('input[type="text"], input[type="search"], input[type="number"], textarea');

    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.code === "KeyO") {
      e.preventDefault();
      openFile();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.code === "KeyZ" && !textEntry) {
      e.preventDefault();
      if (e.shiftKey) redo(); else undo();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.code === "KeyY" && !textEntry) { e.preventDefault(); redo(); return; }

    if (e.code === "Slash" && !textEntry && !typing) {
      e.preventDefault();
      showShortcuts();
      return;
    }
    if (e.code === "Escape" && !typing) {
      const modal = document.querySelector(".modal-backdrop");
      if (modal) { modal.remove(); return; }
      closeAllMenus();
      if (state.fullPage) { setFullPage(false); return; }
      if (state.compare) { state.compare = false; scheduleRender(0); }
      if (els.panel.classList.contains("open")) els.panel.classList.remove("open");
      return;
    }
    if (typing) return;

    if (e.code === "KeyT") { e.preventDefault(); toggleTheme(); return; }
    if (e.code === "Backslash") { e.preventDefault(); togglePanel(); return; }
    if (e.code === "KeyE") { e.preventDefault(); exportImage(); return; }
    if (e.code === "KeyR") { e.preventDefault(); resetAll(); return; }
    if (e.code === "KeyC") { e.preventDefault(); toggleCompare(); return; }
    if (e.code === "KeyF" && e.shiftKey) { e.preventDefault(); setFullPage(!state.fullPage); return; }
    if (e.code === "KeyS" && e.shiftKey) { e.preventDefault(); fitSmall(); return; }
    if (e.code === "Digit1") { e.preventDefault(); setZoom(1); return; }
    if (e.code === "Digit2") { e.preventDefault(); setZoom(2); return; }
    if (e.code === "KeyF" || e.code === "Digit0" || e.code === "Numpad0") { e.preventDefault(); fitToWindow(); return; }
    if (e.key === "+" || e.key === "=") { e.preventDefault(); zoomBy(1.25); return; }
    if (e.key === "-" || e.key === "_") { e.preventDefault(); zoomBy(1 / 1.25); return; }
    if (e.code === "Space") {
      e.preventDefault();
      state.spaceDown = true;
      els.canvasArea.style.cursor = "grab";
      return;
    }
    if (e.code === "KeyO") { if (!state.showOriginal) { state.showOriginal = true; scheduleRender(0); } }
  });
  window.addEventListener("keyup", e => {
    if (e.code === "Space") { state.spaceDown = false; els.canvasArea.style.cursor = ""; }
    if (e.code === "KeyO" && state.showOriginal) { state.showOriginal = false; scheduleRender(0); }
  });

  on(els.selectMode, "change", () => {
    state.opts.mode = els.selectMode.value;
    toggleModeSections();
    pushHistory("mode");
    scheduleRender(0);
  });

  const textBind = (el, key, after) => on(el, "input", () => {
    state.opts[key] = el.value;
    if (after) after();
    pushHistory(key);
    scheduleRender();
  });
  textBind(els.charInject, "charInject", rebuildRamp);
  on(els.charCategory, "change", () => { state.opts.charCategory = els.charCategory.value; rebuildRamp(); pushHistory("chars"); scheduleRender(); });
  on(els.charSet, "change", () => { state.opts.charSet = els.charSet.value; rebuildRamp(); pushHistory("chars"); scheduleRender(); });
  on(els.textStyle, "change", () => { state.opts.textStyle = els.textStyle.value; rebuildRamp(); pushHistory("chars"); scheduleRender(); });
  on(els.charPreset, "change", () => {
    state.opts.charPreset = els.charPreset.value;
    els.customCharsetRow.hidden = state.opts.charPreset !== "custom";
    applyCharPreset(state.opts.charPreset);
    pushHistory("charPreset"); scheduleRender();
  });
  textBind(els.customCharset, "customCharset", () => { rebuildRamp(); pushHistory("customCharset"); scheduleRender(); });

  // Helper to sync slider and number input
  function syncSliderNumber(slider, numInput, optPath, onChange) {
    const min = +slider.min, max = +slider.max, step = +slider.step;
    let lastValid = slider.value;
    function clamp(v) { return Math.max(min, Math.min(max, v)); }
    function setVal(v, notify = true) {
      // Snap to the control's step grid in the same place every other numeric
      // control does, so repeated stepping cannot accumulate float noise.
      const clamped = clamp(roundToStep(v, step, min));
      slider.value = clamped;
      numInput.value = clamped;
      const parts = optPath.split(".");
      let obj = state.opts;
      for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
      obj[parts[parts.length - 1]] = clamped;
      lastValid = clamped;
      if (onChange && notify) onChange();
    }
    function getCurrentVal() {
      const parts = optPath.split(".");
      let obj = state.opts;
      for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
      return obj[parts[parts.length - 1]];
    }
    slider.addEventListener("input", () => setVal(+slider.value));
    numInput.addEventListener("input", () => {
      const v = parseFloat(numInput.value);
      if (!isNaN(v)) setVal(v);
    });
    numInput.addEventListener("blur", () => {
      if (isNaN(parseFloat(numInput.value))) numInput.value = lastValid;
    });
    numInput.addEventListener("keydown", (e) => {
      const mult = e.shiftKey ? 10 : 1;
      if (e.key === "ArrowUp") { e.preventDefault(); setVal(getCurrentVal() + step * mult); }
      if (e.key === "ArrowDown") { e.preventDefault(); setVal(getCurrentVal() - step * mult); }
      if (e.key === "PageUp") { e.preventDefault(); setVal(getCurrentVal() + step * 10); }
      if (e.key === "PageDown") { e.preventDefault(); setVal(getCurrentVal() - step * 10); }
    });
    // The wheel is a first-class step input on every numeric control, and it
    // must never scroll the panel while stepping.
    numInput.addEventListener("wheel", (e) => {
      e.preventDefault();
      setVal(getCurrentVal() + (e.deltaY < 0 ? step : -step));
    }, { passive: false });
    slider.addEventListener("dblclick", () => setVal(+slider.defaultValue));
    numInput.addEventListener("dblclick", () => { numInput.value = slider.defaultValue; setVal(+slider.defaultValue); });
    attachStepper(
      numInput.parentElement,
      numInput.id || optPath,
      optPath.split(".").pop(),
      (dir) => { setVal(getCurrentVal() + (dir === "up" ? step : -step), false); },
      () => { if (onChange) onChange(); }
    );
  }

  syncSliderNumber(els.cellSize, els.cellSizeNum, "cellSize", () => { pushHistory("cellSize"); scheduleRender(); });
  syncSliderNumber(els.glyphWeight, els.glyphWeightNum, "glyphWeight", () => { pushHistory("glyphWeight"); scheduleRender(); });
  syncSliderNumber(els.depth, els.depthNum, "depth", () => { rebuildRamp(); pushHistory("depth"); scheduleRender(); });
  syncSliderNumber(els.charOffset, els.charOffsetNum, "charOffset", () => { pushHistory("offset"); scheduleRender(); });
  syncSliderNumber(els.ditherDepth, els.ditherDepthNum, "ditherDepth", () => { pushHistory("ditherDepth"); scheduleRender(); });
  syncSliderNumber(els.jpgQuality, els.jpgQualityNum, "jpgQuality", () => { pushHistory("jpgQuality"); scheduleRender(); });

  on(els.glyphInvert, "change", () => { state.opts.glyphInvert = els.glyphInvert.checked; pushHistory("glyphInvert"); scheduleRender(); });
  on(els.glyphColor, "change", () => { state.opts.glyphColor = els.glyphColor.checked; pushHistory("glyphColor"); scheduleRender(); });
  on(els.usePalette, "change", () => { state.opts.usePalette = els.usePalette.checked; pushHistory("usePalette"); scheduleRender(); });
  on(els.transparentBg, "change", () => { state.opts.transparentBg = els.transparentBg.checked; pushHistory("transparent"); scheduleRender(); });
  on(els.autoLevels, "change", () => { state.opts.autoLevels = els.autoLevels.checked; pushHistory("autoLevels"); scheduleRender(); });
  on(els.bgColor, "input", () => { state.opts.bgColor = els.bgColor.value; pushHistory("bg"); scheduleRender(); });
  on(els.colorMode, "change", () => {
    state.opts.colorMode = els.colorMode.value;
    els.controlPalette.hidden = state.opts.colorMode !== "palette";
    pushHistory("colorMode"); scheduleRender();
  });
  on(els.paletteSelect, "change", () => {
    state.opts.palette = els.paletteSelect.value;
    updatePaletteSwatches();
    updateCustomPaletteBuilder();
    pushHistory("palette"); scheduleRender();
  });

  ["Brightness", "Contrast", "Saturation", "Hue", "Highlights", "Shadows", "Sharpen", "Blur"].forEach(name => {
    const key = name.toLowerCase();
    const slider = els["adj" + name], numInput = els["adj" + name + "Num"];
    syncSliderNumber(slider, numInput, "adj." + key, () => { pushHistory("adj-" + key); scheduleRender(70); });
  });
  on(els.adjInvert, "change", () => { state.opts.adj.invert = els.adjInvert.checked; pushHistory("invert"); scheduleRender(); });
  on(els.adjSepia, "change", () => { state.opts.adj.sepia = els.adjSepia.checked; pushHistory("sepia"); scheduleRender(); });

  on(els.outputPreset, "change", () => {
    state.opts.outputPreset = els.outputPreset.value;
    updateOutputCustomVisibility();
    updateOutputSizeFromPreset();
    pushHistory("outputPreset"); scheduleRender();
  });
  on(els.outputPresetSearch, "input", renderPresetList);

  on(els.outputPresetTrigger, "click", () => {
    if (state.presetOpen) closePresetPicker();
    else openPresetPicker();
  });
  on(els.outputPresetTrigger, "keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      openPresetPicker();
    }
  });
  on(els.outputPresetSearch, "keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const options = visiblePresetOptions();
      if (options.length) { options[0].focus(); options[0].scrollIntoView({ block: "nearest" }); }
    } else if (e.key === "Escape") {
      e.preventDefault();
      closePresetPicker();
    } else if (e.key === "Enter") {
      const options = visiblePresetOptions();
      if (options.length === 1) { e.preventDefault(); choosePreset(options[0].dataset.presetId); }
    }
  });
  on(els.outputPresetList, "click", (e) => {
    const more = e.target.closest("[data-preset-more]");
    if (more) { togglePresetExpanded(); return; }
    const option = e.target.closest(".preset-option");
    if (option) choosePreset(option.dataset.presetId);
  });
  on(els.outputPresetList, "keydown", (e) => {
    const options = visiblePresetOptions();
    const index = options.indexOf(document.activeElement);
    if (e.key === "Escape") { e.preventDefault(); closePresetPicker(); return; }
    if (e.key === "Tab") { closePresetPicker(false); return; }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
      if ((e.key === "Enter" || e.key === " ") && index >= 0) {
        e.preventDefault();
        choosePreset(options[index].dataset.presetId);
      }
      return;
    }
    if (!options.length) return;
    e.preventDefault();
    let next = index;
    if (e.key === "Home") next = 0;
    else if (e.key === "End") next = options.length - 1;
    else if (e.key === "ArrowDown") next = index < 0 ? 0 : Math.min(options.length - 1, index + 1);
    else next = index < 0 ? 0 : Math.max(0, index - 1);
    options[next].focus();
    options[next].scrollIntoView({ block: "nearest" });
  });
  on(els.outputLockRatio, "change", () => {
    state.opts.outputLockRatio = els.outputLockRatio.checked;
  });
  on(els.ditherSerpentine, "change", () => {
    state.opts.ditherSerpentine = els.ditherSerpentine.checked;
    pushHistory("ditherSerpentine"); scheduleRender();
  });
  on(els.paletteAddColor, "click", () => {
    if (!state.opts.customPalette) state.opts.customPalette = ["#000", "#fff"];
    state.opts.customPalette.push("#888");
    const paletteName = state.opts.palette === "__custom__" ? "__custom__" : state.opts.palette;
    renderPaletteBuilder(paletteName);
    updatePaletteSwatches();
    pushHistory("custom-palette");
    scheduleRender();
  });
  on(els.paletteSaveCustom, "click", saveCustomPalette);
  on(els.outputWidth, "change", () => {
    state.opts.outputWidth = Math.min(8192, Math.max(1, +els.outputWidth.value));
    if (state.opts.outputLockRatio && els.outputPreset.value !== "custom") {
      const opt = els.outputPreset.options[els.outputPreset.selectedIndex];
      if (opt && opt.dataset.w && opt.dataset.h) {
        const ratio = +opt.dataset.w / +opt.dataset.h;
        state.opts.outputHeight = Math.round(state.opts.outputWidth / ratio);
        els.outputHeight.value = state.opts.outputHeight;
      }
    }
    checkOutputSizeWarning();
    pushHistory("outW"); scheduleRender();
  });
  on(els.outputHeight, "change", () => {
    state.opts.outputHeight = Math.min(8192, Math.max(1, +els.outputHeight.value));
    if (state.opts.outputLockRatio && els.outputPreset.value !== "custom") {
      const opt = els.outputPreset.options[els.outputPreset.selectedIndex];
      if (opt && opt.dataset.w && opt.dataset.h) {
        const ratio = +opt.dataset.w / +opt.dataset.h;
        state.opts.outputWidth = Math.round(state.opts.outputHeight * ratio);
        els.outputWidth.value = state.opts.outputWidth;
      }
    }
    checkOutputSizeWarning();
    pushHistory("outH"); scheduleRender();
  });
  on(els.outputFit, "change", () => { state.opts.outputFit = els.outputFit.value; pushHistory("fit"); scheduleRender(); });
  on(els.exportFormat, "change", () => {
    state.opts.exportFormat = els.exportFormat.value;
    els.jpgQualityControl.hidden = state.opts.exportFormat !== "jpg";
    pushHistory("format");
  });
  on(els.ditherKernel, "change", () => { state.opts.ditherKernel = els.ditherKernel.value; pushHistory("kernel"); scheduleRender(); });

  document.querySelectorAll(".preset-btn[data-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".preset-btn").forEach(b => b.classList.toggle("active", b === btn));
      applyNamedPreset(btn.dataset.preset);
    });
  });

  document.addEventListener("paste", e => {
    const items = (e.clipboardData && e.clipboardData.items) || [];
    for (const item of items) {
      if (item.type.startsWith("image/") || item.type.startsWith("video/")) { loadFile(item.getAsFile()); break; }
    }
  });

  const slider = els.compareSlider;
  on(slider, "pointerdown", e => {
    if (e.button > 0) return;
    e.preventDefault();
    e.stopPropagation();
    // Snapshot the geometry once per gesture: reading it on every move forces
    // a layout flush and lets pan/zoom changes mid-drag skew the split.
    const area = els.canvasArea.getBoundingClientRect();
    const canvasW = els.canvas.width * state.scale;
    const move = ev => {
      state.compareFrac = Math.max(0, Math.min(1, (ev.clientX - area.left - state.pan.x) / (canvasW || 1)));
      scheduleRender(0);
    };
    move(e);
    try { slider.setPointerCapture(e.pointerId); } catch (err) {}
    const end = () => {
      slider.removeEventListener("pointermove", move);
      slider.removeEventListener("pointerup", end);
      slider.removeEventListener("pointercancel", end);
      slider.removeEventListener("lostpointercapture", end);
      try {
        if (slider.hasPointerCapture(e.pointerId)) slider.releasePointerCapture(e.pointerId);
      } catch (err) {}
    };
    slider.addEventListener("pointermove", move);
    slider.addEventListener("pointerup", end);
    slider.addEventListener("pointercancel", end);
    slider.addEventListener("lostpointercapture", end);
  });

  window.addEventListener("resize", () => {
    updateCompareUI();
    applyZoomUI();
  });

  // A hidden tab must be truly idle: no pending render, no video rAF loop.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (state.renderTimer) { clearTimeout(state.renderTimer); state.renderTimer = null; }
      if (state.renderId) { cancelAnimationFrame(state.renderId); state.renderId = null; }
      stopVideoLoop();
      return;
    }
    if (state.renderDirty) requestRenderFrame();
    if (state.video && !state.video.paused && !state.video.ended) startVideoLoop();
  });
}

function initReorder() {
  if (!els.effectsList || typeof createReorderList !== "function") return;
  createReorderList({
    container: els.effectsList,
    itemSelector: ".effect-item",
    handleSelector: ".drag-handle",
    onReorder(from, to) {
      const list = state.opts.effects;
      if (from < 0 || from >= list.length || to < 0 || to >= list.length || from === to) return;
      const [moved] = list.splice(from, 1);
      list.splice(to, 0, moved);
      pushHistory("fx-reorder");
      renderEffectsList();
      scheduleRender(40);
      requestAnimationFrame(() => {
        const nextHandle = els.effectsList.querySelector('[data-id="' + moved.id + '"] .drag-handle');
        if (nextHandle) nextHandle.focus({ preventScroll: true });
      });
      const def = EFFECTS.find(e => e.id === moved.id);
      showToast((def ? def.name : "Effect") + " moved " + (to < from ? "up" : "down"));
    }
  });
}

function init() {
  initEls();
  loadTheme();
  populatePalettes();
  populateOutputPresets();
  rebuildRamp();
  setupEventListeners();
  loadSectionCollapse();
  syncUIFromState();
  initReorder();
  state.history.undo.push(snapshot());
  if (els.outputWidth) els.outputWidth.disabled = true;
  if (els.outputHeight) els.outputHeight.disabled = true;
  applyZoomUI();
  updateStatus();
}

document.addEventListener("pointerdown", (e) => {
  if (state.presetOpen && els.presetPicker && !els.presetPicker.contains(e.target)) closePresetPicker(false);
});

document.addEventListener("DOMContentLoaded", init);
