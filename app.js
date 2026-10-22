const DEFAULT_ADJ = { brightness: 0, contrast: 0, saturation: 0, hue: 0, highlights: 0, shadows: 0, sharpen: 0, blur: 0, invert: false, sepia: false };

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
  pan: { x: 0, y: 0 },
  scale: 1,
  spaceDown: false,
  opts: defaultOpts(),
  ramp: null,
  paletteColors: null,
  lastRender: 0,
  compare: false,
  compareFrac: 0.5,
  showOriginal: false,
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
  els.panelToggle = $("panel-toggle");
  els.panelToggleBtn = $("panel-toggle-btn");
  els.panelSearch = $("panel-search");
  els.btnExport = $("btn-export");
  els.btnReset = $("btn-reset");
  els.selectMode = $("select-mode");
  els.depth = $("depth"); els.valDepth = $("val-depth");
  els.depthNum = $("depth-num");
  els.charCategory = $("char-category");
  els.charSet = $("char-set");
  els.charInject = $("char-inject");
  els.charOffset = $("char-offset"); els.valOffset = $("val-offset");
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
  els.adjBrightness = $("adj-brightness"); els.valBrightness = $("val-brightness");
  els.adjBrightnessNum = $("adj-brightness-num");
  els.adjContrast = $("adj-contrast"); els.valContrast = $("val-contrast");
  els.adjContrastNum = $("adj-contrast-num");
  els.adjSaturation = $("adj-saturation"); els.valSaturation = $("val-saturation");
  els.adjSaturationNum = $("adj-saturation-num");
  els.adjHue = $("adj-hue"); els.valHue = $("val-hue");
  els.adjHueNum = $("adj-hue-num");
  els.adjHighlights = $("adj-highlights"); els.valHighlights = $("val-highlights");
  els.adjHighlightsNum = $("adj-highlights-num");
  els.adjShadows = $("adj-shadows"); els.valShadows = $("val-shadows");
  els.adjShadowsNum = $("adj-shadows-num");
  els.adjSharpen = $("adj-sharpen"); els.valSharpen = $("val-sharpen");
  els.adjSharpenNum = $("adj-sharpen-num");
  els.adjBlur = $("adj-blur"); els.valBlur = $("val-blur");
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
  els.valColorDepth = $("val-color-depth");
  els.statusBar = $("status-bar");
  els.menuFile = $("menu-file"); els.dropdownFile = $("dropdown-file");
  els.menuView = $("menu-view"); els.dropdownView = $("dropdown-view");
  els.menuEdit = $("menu-edit"); els.dropdownEdit = $("dropdown-edit");
  els.toggleTheme = $("toggle-theme");
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
  els.valCellSize = $("val-cell-size");
  els.glyphWeight = $("glyph-weight");
  els.glyphWeightNum = $("glyph-weight-num");
  els.valWeight = $("val-weight");
  els.glyphInvert = $("glyph-invert");
  els.glyphColor = $("glyph-color");
  els.jpgQuality = $("jpg-quality");
  els.jpgQualityNum = $("jpg-quality-num");
  els.valJpgQuality = $("val-jpg-quality");
  els.jpgQualityControl = $("jpg-quality-control");
}

function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  if (els.toggleTheme) els.toggleTheme.checked = dark;
  try { localStorage.setItem("glyphcraft-theme", dark ? "dark" : "light"); } catch (e) {}
}

function loadTheme() {
  try {
    const saved = localStorage.getItem("glyphcraft-theme");
    if (saved) { setTheme(saved === "dark"); return; }
  } catch (e) {}
  setTheme(!window.matchMedia || window.matchMedia("(prefers-color-scheme: dark)").matches);
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
    els.customPaletteBuilder.style.display = "";
    renderPaletteBuilder(paletteName);
  } else {
    els.customPaletteBuilder.style.display = "none";
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
  clearTimeout(state.renderTimer);
  state.renderTimer = setTimeout(() => {
    if (state.renderId) return;
    state.renderId = requestAnimationFrame(() => {
      state.renderId = null;
      render();
    });
  }, delay == null ? 60 : delay);
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
    if (els.statusBar) els.statusBar.textContent = "No image loaded";
    return;
  }
  const start = performance.now();
  const full = computeOutputSize(state.sourceW, state.sourceH, state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight, state.opts.outputFit);
  const pv = previewSize(full);
  const opts = renderOpts();

  els.canvas.width = pv.w;
  els.canvas.height = pv.h;
  const base = prepareBase(state.source, pv.w, pv.h, opts);
  renderToContext(base, els.ctx, pv.w, pv.h, opts);

  if (state.showOriginal) {
    drawOriginal(els.ctx, pv.w, pv.h, null);
  } else if (state.compare) {
    drawOriginal(els.ctx, pv.w, pv.h, Math.round(pv.w * state.compareFrac));
  }

  state.lastRender = performance.now() - start;
  updateCompareUI();
  updateStatus(full);
}

function updateStatus(full) {
  if (!els.statusBar) return;
  if (state.videoExporting) {
    els.statusBar.textContent = `Exporting video: ${state.videoExportFrames}/${state.videoExportTotal} frames`;
    return;
  }
  if (!state.source) { els.statusBar.textContent = "No image loaded"; return; }
  const zoom = Math.round(state.scale * 100);
  els.statusBar.textContent = `${zoom}%  ${state.sourceW}×${state.sourceH}  ${Math.round(state.lastRender)}ms`;
}

function updateCompareUI() {
  if (!els.compareOverlay || !els.compareSlider) return;
  const active = state.compare && state.source && !state.showOriginal;
  els.compareOverlay.style.display = active ? "flex" : "none";
  if (!active) return;
  const area = els.canvasArea.getBoundingClientRect();
  const left = state.pan.x + els.canvas.width * state.scale * state.compareFrac;
  els.compareSlider.style.left = `${left}px`;
  els.compareSlider.style.top = `${state.pan.y}px`;
  els.compareSlider.style.height = `${els.canvas.height * state.scale}px`;
  els.compareSlider.style.bottom = "auto";
}

function fitToWindow() {
  if (!state.source) return;
  const area = els.canvasArea.getBoundingClientRect();
  const w = els.canvas.width || 1, h = els.canvas.height || 1;
  state.scale = Math.min(area.width / w, area.height / h, 1) * 0.94;
  state.pan.x = (area.width - w * state.scale) / 2;
  state.pan.y = (area.height - h * state.scale) / 2;
  applyTransform();
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
  const factor = e.deltaY > 0 ? 0.9 : 1.1;
  const newScale = Math.max(0.05, Math.min(20, state.scale * factor));
  const dx = mx - state.pan.x, dy = my - state.pan.y;
  state.pan.x = mx - dx * (newScale / state.scale);
  state.pan.y = my - dy * (newScale / state.scale);
  state.scale = newScale;
  applyTransform();
}

let isPanning = false, panStart = { x: 0, y: 0 };
function handlePointerDown(e) {
  if (!state.source || e.button === 2) return;
  if (!(state.spaceDown || e.button === 1)) return;
  e.preventDefault();
  isPanning = true;
  panStart = { x: e.clientX - state.pan.x, y: e.clientY - state.pan.y };
  els.canvasArea.style.cursor = "grabbing";
}
function handlePointerMove(e) {
  if (!isPanning) return;
  state.pan.x = e.clientX - panStart.x;
  state.pan.y = e.clientY - panStart.y;
  applyTransform();
}
function handlePointerUp() {
  if (isPanning) { isPanning = false; els.canvasArea.style.cursor = state.spaceDown ? "grab" : ""; }
}

function setDropZoneState(state) {
  if (els.dropZone) els.dropZone.dataset.state = state;
}

function showDropError(message) {
  if (els.dropZone) {
    const errorEl = els.dropZone.querySelector(".drop-error");
    if (errorEl) errorEl.textContent = message;
    setDropZoneState("error");
  }
  setTimeout(() => setDropZoneState("idle"), 3000);
}

function loadFile(file) {
  if (!file) return;
  setDropZoneState("loading");
  const url = URL.createObjectURL(file);
  const isVideo = file.type.startsWith("video/");
  if (isVideo) {
    const vid = document.createElement("video");
    vid.src = url; vid.muted = true; vid.playsInline = true; vid.loop = true;
    vid.addEventListener("loadedmetadata", () => {
      state.video = vid;
      state.source = vid;
      state.sourceType = "video";
      state.sourceW = vid.videoWidth;
      state.sourceH = vid.videoHeight;
      els.canvasArea.classList.add("has-content");
      vid.play().catch(() => {});
      startVideoLoop();
      if (state.opts.palette === "__auto__") extractAutoPalette(vid);
      scheduleRender(0);
      setTimeout(fitToWindow, 30);
      setDropZoneState("idle");
    }, { once: true });
    vid.addEventListener("error", () => { URL.revokeObjectURL(url); showDropError("Unsupported video codec"); }, { once: true });
  } else {
    const img = new Image();
    img.onload = () => {
      state.source = img;
      state.sourceType = "image";
      state.video = null;
      state.sourceW = img.naturalWidth;
      state.sourceH = img.naturalHeight;
      els.canvasArea.classList.add("has-content");
      if (state.opts.palette === "__auto__") extractAutoPalette(img);
      scheduleRender(0);
      requestAnimationFrame(() => { render(); fitToWindow(); pushHistory("load"); });
      setDropZoneState("idle");
    };
    img.onerror = () => { URL.revokeObjectURL(url); showDropError("Unsupported image format"); };
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
  if (state.rafId) cancelAnimationFrame(state.rafId);
  function loop() {
    if (state.video && !state.video.paused && !state.video.ended && !state.videoExporting) {
      render();
    }
    state.rafId = requestAnimationFrame(loop);
  }
  loop();
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
  toast.style.cssText = `
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: var(--panel2); color: var(--text);
    padding: 10px 16px; border-radius: 8px; border: 1px solid var(--line);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3); z-index: 1000;
    font-family: var(--font-ui); font-size: 13px;
    animation: toast-in 0.2s ease-out;
  `;
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
  els.depth.value = o.depth; els.valDepth.textContent = o.depth; els.depthNum.value = o.depth;
  els.charCategory.value = o.charCategory;
  els.charSet.value = o.charSet;
  els.charInject.value = o.charInject;
  els.charOffset.value = o.charOffset; els.valOffset.textContent = o.charOffset; els.charOffsetNum.value = o.charOffset;
  els.textStyle.value = o.textStyle;
  els.charPreset.value = o.charPreset;
  els.customCharset.value = o.customCharset;
  els.customCharsetRow.style.display = o.charPreset === "custom" ? "" : "none";
  els.cellSize.value = o.cellSize; els.valCellSize.textContent = o.cellSize; els.cellSizeNum.value = o.cellSize;
  els.glyphWeight.value = o.glyphWeight; els.valWeight.textContent = o.glyphWeight; els.glyphWeightNum.value = o.glyphWeight;
  els.glyphInvert.checked = o.glyphInvert;
  els.glyphColor.checked = o.glyphColor;
  els.usePalette.checked = o.usePalette;
  els.transparentBg.checked = o.transparentBg;
  els.autoLevels.checked = o.autoLevels;
  els.bgColor.value = o.bgColor;
  els.colorMode.value = o.colorMode;
  els.paletteSelect.value = o.palette;
  els.ditherKernel.value = o.ditherKernel;
  els.ditherDepth.value = o.ditherDepth; els.valColorDepth.textContent = o.ditherDepth; els.ditherDepthNum.value = o.ditherDepth;
  els.ditherSerpentine.checked = o.ditherSerpentine;
  const names = ["Brightness", "Contrast", "Saturation", "Hue", "Highlights", "Shadows", "Sharpen", "Blur"];
  names.forEach(n => {
    const key = n.toLowerCase();
    els["adj" + n].value = o.adj[key];
    els["val" + n].textContent = o.adj[key];
    els["adj" + n + "Num"].value = o.adj[key];
  });
  els.adjInvert.checked = o.adj.invert;
  els.adjSepia.checked = o.adj.sepia;
  els.outputPreset.value = o.outputPreset;
  els.outputWidth.value = o.outputWidth;
  els.outputHeight.value = o.outputHeight;
  els.outputFit.value = o.outputFit;
  els.outputLockRatio.checked = o.outputLockRatio;
  els.exportFormat.value = o.exportFormat;
  els.jpgQuality.value = o.jpgQuality; els.valJpgQuality.textContent = o.jpgQuality; els.jpgQualityNum.value = o.jpgQuality;
  els.jpgQualityControl.style.display = o.exportFormat === "jpg" ? "" : "none";
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
  els.controlPalette.style.display = state.opts.colorMode === "palette" ? "" : "none";
}

function renderEffectsList() {
  if (!els.effectsList) return;
  els.effectsList.innerHTML = "";
  if (state.opts.effects.length === 0) {
    const empty = document.createElement("div");
    empty.className = "effect-empty";
    empty.style.cssText = "padding: var(--space-4); text-align: center; color: var(--muted); font-size: 13px;";
    empty.textContent = "No effects added. Enable effects from the presets or add them manually.";
    els.effectsList.appendChild(empty);
    return;
  }
  state.opts.effects.forEach((fx, index) => {
    const def = EFFECTS.find(e => e.id === fx.id);
    if (!def) return;
    const item = document.createElement("div");
    item.className = "effect-item";
    item.draggable = true;
    item.dataset.index = index;
    item.dataset.id = fx.id;

    const handle = document.createElement("span");
    handle.className = "drag-handle";
    handle.textContent = "⠿";
    handle.title = "Drag to reorder";

    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = fx.enabled;
    check.title = "Enable " + def.name;
    check.addEventListener("change", () => {
      fx.enabled = check.checked;
      pushHistory("fx-toggle-" + fx.id);
      scheduleRender(80);
    });

    const name = document.createElement("span");
    name.className = "effect-name";
    name.textContent = def.name;

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "4px";
    actions.style.marginInlineStart = "auto";

    const resetBtn = document.createElement("button");
    resetBtn.className = "btn btn-small";
    resetBtn.textContent = "Reset";
    resetBtn.title = "Reset to defaults";
    resetBtn.style.padding = "4px 8px";
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
    removeBtn.style.padding = "4px 8px";
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
    head.style.display = "flex";
    head.style.alignItems = "center";
    head.style.gap = "8px";
    head.style.flex = "1";
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
          input.style.width = "34px"; input.style.height = "24px"; input.style.padding = "1px";
        } else if (p.type === "select") {
          input = document.createElement("select");
          (p.options || []).forEach(([val, text]) => {
            const opt = document.createElement("option");
            opt.value = val; opt.textContent = text;
            input.appendChild(opt);
          });
          input.value = fx.params[p.key];
          input.style.width = "90px"; input.style.padding = "3px 20px 3px 6px";
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
          numInput.style.width = "60px";
          numInput.style.height = "28px";
          numInput.style.padding = "4px 8px";
          numInput.style.fontSize = "11px";
          numInput.style.fontFamily = "var(--font-ui)";
          numInput.style.color = "var(--text)";
          numInput.style.background = "var(--bg)";
          numInput.style.border = "1px solid var(--line)";
          numInput.style.borderRadius = "var(--radius-sm)";

          const out = document.createElement("span");
          out.className = "param-value";
          out.textContent = fx.params[p.key];
          out.style.fontFamily = "var(--font-mono)";
          out.style.fontSize = "10px";
          out.style.minWidth = "30px";
          out.style.color = "var(--muted)";

          const sync = (val) => {
            const clamped = Math.max(p.min, Math.min(p.max, val));
            input.value = clamped;
            numInput.value = clamped;
            out.textContent = clamped;
            fx.params[p.key] = clamped;
          };

          input.addEventListener("input", () => sync(+input.value));
          numInput.addEventListener("input", () => {
            const v = parseFloat(numInput.value);
            if (!isNaN(v)) sync(v);
          });
          numInput.addEventListener("blur", () => {
            if (isNaN(parseFloat(numInput.value))) numInput.value = fx.params[p.key];
          });
          numInput.addEventListener("keydown", (e) => {
            if (e.key === "ArrowUp") { e.preventDefault(); sync(fx.params[p.key] + p.step * (e.shiftKey ? 10 : 1)); }
            if (e.key === "ArrowDown") { e.preventDefault(); sync(fx.params[p.key] - p.step * (e.shiftKey ? 10 : 1)); }
          });
          input.addEventListener("dblclick", () => sync(p.def));

          inputWrap.appendChild(input);
          inputWrap.appendChild(numInput);
          inputWrap.appendChild(out);
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

    item.addEventListener("dragstart", e => {
      state.dragIndex = index;
      item.classList.add("dragging");
      if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
    });
    item.addEventListener("dragend", () => { item.classList.remove("dragging"); state.dragIndex = null; });
    item.addEventListener("dragover", e => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "move"; });
    item.addEventListener("drop", e => {
      e.preventDefault();
      const from = state.dragIndex;
      if (from == null || from === index) return;
      const list = state.opts.effects;
      const [moved] = list.splice(from, 1);
      list.splice(index, 0, moved);
      state.dragIndex = null;
      renderEffectsList();
      pushHistory("fx-reorder");
      scheduleRender(60);
    });
    els.effectsList.appendChild(item);
  });
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
    if (p.w && p.h) opt.dataset.w = p.w; opt.dataset.h = p.h;
    optgroup.appendChild(opt);
  });
  select.value = state.opts.outputPreset;
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
  els.outputCustomRow.style.display = isCustom ? "flex" : "none";
  if (isCustom) {
    els.outputWidth.value = state.opts.outputWidth;
    els.outputHeight.value = state.opts.outputHeight;
  }
  checkOutputSizeWarning();
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

function setupEventListeners() {
  on(els.fileInput, "change", e => {
    const file = e.target.files && e.target.files[0];
    if (file) loadFile(file);
    e.target.value = "";
  });
  on(els.dropZone, "click", openFile);

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

  function showShortcuts() {
    const modal = document.createElement("div");
    modal.className = "shortcuts-modal";
    modal.style.cssText = `
      position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000;
      display: flex; align-items: center; justify-content: center;
      animation: fade-in 0.2s ease-out;
    `;
    modal.innerHTML = `
      <div style="background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: var(--space-6); max-width: 400px; width: 90%; max-height: 80vh; overflow: auto;">
        <h3 style="font-family: var(--font-heading); font-size: 18px; margin-bottom: var(--space-4); color: var(--text);">Keyboard Shortcuts</h3>
        <dl style="display: grid; grid-template-columns: auto 1fr; gap: var(--space-2) var(--space-4); font-family: var(--font-ui); font-size: 13px; color: var(--text);">
          <dt style="color: var(--muted); font-family: var(--font-mono);">E</dt><dd>Export image</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">R</dt><dd>Reset all (with confirmation)</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">Z</dt><dd>Undo</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">Shift+Z</dt><dd>Redo</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">C</dt><dd>Toggle compare split</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">O</dt><dd>Hold to show original</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">F</dt><dd>Fit to window</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">Space</dt><dd>Hold to pan (drag)</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">Esc</dt><dd>Close menus / compare / mobile panel</dd>
          <dt style="color: var(--muted); font-family: var(--font-mono);">?</dt><dd>Show this help</dd>
        </dl>
        <button class="btn btn-primary" style="margin-top: var(--space-5); width: 100%;" onclick="this.closest('.shortcuts-modal').remove()">Got it</button>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
  }

  window.addEventListener("keydown", e => {
    const target = e.target;
    const typing = target && target.matches && target.matches("input, select, textarea");
    const textEntry = target && target.matches && target.matches('input[type="text"], input[type="search"], input[type="number"], textarea');
    if ((e.ctrlKey || e.metaKey) && e.code === "KeyZ" && !textEntry) {
      e.preventDefault();
      if (e.shiftKey) redo(); else undo();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.code === "KeyY" && !textEntry) { e.preventDefault(); redo(); return; }
    if (e.code === "Space" && !typing) {
      e.preventDefault();
      state.spaceDown = true;
      els.canvasArea.style.cursor = "grab";
    }
    if (e.code === "Slash" && !textEntry && !typing) {
      e.preventDefault();
      showShortcuts();
      return;
    }
    if (e.code === "KeyE" && !textEntry && !typing) { e.preventDefault(); exportImage(); return; }
    if (e.code === "KeyR" && !textEntry && !typing) { e.preventDefault(); resetAll(); return; }
    if (e.code === "KeyC" && !textEntry && !typing) { e.preventDefault(); toggleCompare(); return; }
    if (typing) return;
    if (e.code === "KeyF") { e.preventDefault(); fitToWindow(); }
    if (e.code === "KeyO") { if (!state.showOriginal) { state.showOriginal = true; scheduleRender(0); } }
    if (e.code === "Escape") {
      if (state.compare) { state.compare = false; scheduleRender(0); }
      document.querySelectorAll(".menu-dropdown.open").forEach(d => d.classList.remove("open"));
      if (els.panel.classList.contains("open")) { els.panel.classList.remove("open"); }
    }
  });
  window.addEventListener("keyup", e => {
    if (e.code === "Space") { state.spaceDown = false; if (!isPanning) els.canvasArea.style.cursor = ""; }
    if (e.code === "KeyO" && state.showOriginal) { state.showOriginal = false; scheduleRender(0); }
  });

  function togglePanel() {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      els.panel.classList.toggle("open");
    } else {
      els.panel.classList.toggle("collapsed");
      els.workspace.classList.toggle("panel-collapsed");
    }
  }

  on(els.panelToggle, "click", togglePanel);
  on(els.panelToggleBtn, "click", togglePanel);

  document.querySelectorAll(".menu-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const dd = $("dropdown-" + btn.id.replace("menu-", ""));
      document.querySelectorAll(".menu-dropdown").forEach(d => { if (d !== dd) d.classList.remove("open"); });
      if (dd) dd.classList.toggle("open");
    });
  });
  document.addEventListener("click", e => {
    if (!e.target.closest(".menu")) document.querySelectorAll(".menu-dropdown").forEach(d => d.classList.remove("open"));
  });

  document.querySelectorAll(".menu-item[data-action]").forEach(item => {
    const action = item.dataset.action;
    item.addEventListener("click", () => {
      if (action === "open") openFile();
      else if (action === "export") exportImage();
      else if (action === "reset") resetAll();
      else if (action === "fit") fitToWindow();
      else if (action === "compare") toggleCompare();
      else if (action === "undo") undo();
      else if (action === "redo") redo();
      else if (action === "save-preset") savePreset();
      else if (action === "load-preset") loadPreset();
      document.querySelectorAll(".menu-dropdown").forEach(d => d.classList.remove("open"));
    });
    if (action === "original") {
      item.addEventListener("pointerdown", e => { e.preventDefault(); state.showOriginal = true; scheduleRender(0); });
      item.addEventListener("pointerup", () => { state.showOriginal = false; scheduleRender(0); });
      item.addEventListener("pointerleave", () => { if (state.showOriginal) { state.showOriginal = false; scheduleRender(0); } });
    }
  });

  on(els.toggleTheme, "change", () => setTheme(els.toggleTheme.checked));
  on(els.btnExport, "click", exportImage);
  on(els.btnReset, "click", resetAll);
  on(els.panelSearch, "input", () => filterControls(els.panelSearch.value));

  document.querySelectorAll(".section-title").forEach(title => {
    title.addEventListener("click", () => {
      const sec = title.closest(".panel-section");
      if (sec) {
        sec.classList.toggle("collapsed");
        saveSectionCollapse();
      }
    });
  });
  document.querySelectorAll(".section-reset").forEach(btn => {
    btn.addEventListener("click", e => { e.stopPropagation(); resetSection(btn.dataset.section); });
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
    els.customCharsetRow.style.display = state.opts.charPreset === "custom" ? "" : "none";
    applyCharPreset(state.opts.charPreset);
    pushHistory("charPreset"); scheduleRender();
  });
  textBind(els.customCharset, "customCharset", () => { rebuildRamp(); pushHistory("customCharset"); scheduleRender(); });

  syncSliderNumber(els.cellSize, els.cellSizeNum, els.valCellSize, "cellSize", () => { pushHistory("cellSize"); scheduleRender(); });
  syncSliderNumber(els.glyphWeight, els.glyphWeightNum, els.valWeight, "glyphWeight", () => { pushHistory("glyphWeight"); scheduleRender(); });

  on(els.glyphInvert, "change", () => { state.opts.glyphInvert = els.glyphInvert.checked; pushHistory("glyphInvert"); scheduleRender(); });
  on(els.glyphColor, "change", () => { state.opts.glyphColor = els.glyphColor.checked; pushHistory("glyphColor"); scheduleRender(); });

  // Helper to sync slider and number input
  function syncSliderNumber(slider, numInput, valueEl, optPath, onChange) {
    const min = +slider.min, max = +slider.max, step = +slider.step;
    let lastValid = slider.value;
    function clamp(v) { return Math.max(min, Math.min(max, v)); }
    function setVal(v) {
      const clamped = clamp(v);
      slider.value = clamped;
      numInput.value = clamped;
      if (valueEl) valueEl.textContent = clamped;
      // Set nested property (e.g., "adj.brightness" -> state.opts.adj.brightness)
      const parts = optPath.split(".");
      let obj = state.opts;
      for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
      obj[parts[parts.length - 1]] = clamped;
      lastValid = clamped;
      if (onChange) onChange();
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
      if (e.key === "ArrowUp") { e.preventDefault(); setVal(getCurrentVal() + step * (e.shiftKey ? 10 : 1)); }
      if (e.key === "ArrowDown") { e.preventDefault(); setVal(getCurrentVal() - step * (e.shiftKey ? 10 : 1)); }
    });
    slider.addEventListener("dblclick", () => setVal(+slider.defaultValue));
    numInput.addEventListener("dblclick", () => { numInput.value = slider.defaultValue; setVal(+slider.defaultValue); });
  }

  syncSliderNumber(els.depth, els.depthNum, els.valDepth, "depth", () => { rebuildRamp(); pushHistory("depth"); scheduleRender(); });
  syncSliderNumber(els.charOffset, els.charOffsetNum, els.valOffset, "charOffset", () => { pushHistory("offset"); scheduleRender(); });
  syncSliderNumber(els.ditherDepth, els.ditherDepthNum, els.valColorDepth, "ditherDepth", () => { pushHistory("ditherDepth"); scheduleRender(); });
  on(els.usePalette, "change", () => { state.opts.usePalette = els.usePalette.checked; pushHistory("usePalette"); scheduleRender(); });
  on(els.transparentBg, "change", () => { state.opts.transparentBg = els.transparentBg.checked; pushHistory("transparent"); scheduleRender(); });
  on(els.autoLevels, "change", () => { state.opts.autoLevels = els.autoLevels.checked; pushHistory("autoLevels"); scheduleRender(); });
  on(els.bgColor, "input", () => { state.opts.bgColor = els.bgColor.value; pushHistory("bg"); scheduleRender(); });
  on(els.colorMode, "change", () => {
    state.opts.colorMode = els.colorMode.value;
    els.controlPalette.style.display = state.opts.colorMode === "palette" ? "" : "none";
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
    const slider = els["adj" + name], val = els["val" + name], numInput = els["adj" + name + "Num"];
    syncSliderNumber(slider, numInput, val, "adj." + key, () => { pushHistory("adj-" + key); scheduleRender(70); });
  });
  on(els.adjInvert, "change", () => { state.opts.adj.invert = els.adjInvert.checked; pushHistory("invert"); scheduleRender(); });
  on(els.adjSepia, "change", () => { state.opts.adj.sepia = els.adjSepia.checked; pushHistory("sepia"); scheduleRender(); });

  on(els.outputPreset, "change", () => {
    state.opts.outputPreset = els.outputPreset.value;
    updateOutputCustomVisibility();
    updateOutputSizeFromPreset();
    pushHistory("outputPreset"); scheduleRender();
  });
  on(els.outputPresetSearch, "input", () => {
    const query = els.outputPresetSearch.value.toLowerCase();
    Array.from(els.outputPreset.options).forEach(opt => {
      const match = !query || opt.textContent.toLowerCase().includes(query);
      opt.style.display = match ? "" : "none";
    });
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
    els.jpgQualityControl.style.display = state.opts.exportFormat === "jpg" ? "" : "none";
    pushHistory("format");
  });
  syncSliderNumber(els.jpgQuality, els.jpgQualityNum, els.valJpgQuality, "jpgQuality", () => { pushHistory("jpgQuality"); scheduleRender(); });
  on(els.ditherKernel, "change", () => { state.opts.ditherKernel = els.ditherKernel.value; pushHistory("kernel"); scheduleRender(); });
  on(els.ditherDepth, "input", () => { state.opts.ditherDepth = +els.ditherDepth.value; els.valColorDepth.textContent = state.opts.ditherDepth; els.ditherDepthNum.value = state.opts.ditherDepth; pushHistory("ditherDepth"); scheduleRender(); });

  document.querySelectorAll(".preset-btn").forEach(btn => {
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
    e.preventDefault();
    const area = els.canvasArea.getBoundingClientRect();
    const update = ev => {
      const canvasW = els.canvas.width * state.scale;
      state.compareFrac = Math.max(0, Math.min(1, (ev.clientX - area.left - state.pan.x) / (canvasW || 1)));
      scheduleRender(0);
    };
    update(e);
    const move = ev => update(ev);
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });

  window.addEventListener("resize", updateCompareUI);
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
  state.history.undo.push(snapshot());
  updateStatus();
  els.outputWidth.disabled = true;
  els.outputHeight.disabled = true;
}

document.addEventListener("DOMContentLoaded", init);
