
const EFFECTS = [
  { id: "halftone", name: "Halftone", params: [{ key: "size", label: "Dot", min: 2, max: 14, step: 1, def: 5 }] },
  { id: "crt", name: "CRT", params: [
    { key: "scan", label: "Scan", min: 0, max: 100, step: 1, def: 45 },
    { key: "curve", label: "Curve", min: 0, max: 100, step: 1, def: 25 },
    { key: "mask", label: "Mask", min: 0, max: 100, step: 1, def: 35 } ] },
  { id: "glitch", name: "Glitch / RGB Split", params: [
    { key: "shift", label: "Split", min: 0, max: 40, step: 1, def: 8 },
    { key: "slices", label: "Slices", min: 0, max: 40, step: 1, def: 8 } ] },
  { id: "vhs", name: "VHS", params: [
    { key: "bleed", label: "Bleed", min: 0, max: 100, step: 1, def: 40 },
    { key: "noise", label: "Noise", min: 0, max: 100, step: 1, def: 30 } ] },
  { id: "pixelate", name: "Pixelate / Mosaic", params: [{ key: "size", label: "Block", min: 2, max: 40, step: 1, def: 8 }] },
  { id: "pixelsort", name: "Pixel Sort", params: [
    { key: "threshold", label: "Thresh", min: 0, max: 100, step: 1, def: 50 },
    { key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 60 } ] },
  { id: "bloom", name: "Bloom / Glow", params: [
    { key: "radius", label: "Radius", min: 1, max: 30, step: 1, def: 8 },
    { key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 55 } ] },
  { id: "grain", name: "Film Grain", params: [{ key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 35 }] },
  { id: "vignette", name: "Vignette", params: [
    { key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 55 },
    { key: "size", label: "Size", min: 10, max: 100, step: 1, def: 65 } ] },
  { id: "duotone", name: "Duotone / Gradient Map", params: [
    { key: "dark", label: "Dark", type: "color", def: "#0a1a10" },
    { key: "light", label: "Light", type: "color", def: "#8dffa8" } ] },
  { id: "posterize", name: "Posterize", params: [{ key: "levels", label: "Levels", min: 2, max: 16, step: 1, def: 5 }] },
  { id: "edges", name: "Edge Detect (Sobel)", params: [{ key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 80 }] },
  { id: "sketch", name: "Pencil Sketch / Crosshatch", params: [
    { key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 70 },
    { key: "cross", label: "Hatch", min: 0, max: 100, step: 1, def: 40 } ] },
  { id: "oil", name: "Oil Paint (Kuwahara)", params: [{ key: "radius", label: "Radius", min: 1, max: 3, step: 1, def: 2 }] },
  { id: "emboss", name: "Emboss", params: [{ key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 70 }] },
  { id: "blur", name: "Blur", params: [{ key: "radius", label: "Radius", min: 0, max: 20, step: 1, def: 4 }] },
  { id: "sharpen", name: "Sharpen", params: [{ key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 60 }] },
  { id: "invert", name: "Invert", params: [] },
  { id: "sepia", name: "Sepia", params: [{ key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 80 }] },
  { id: "thermal", name: "Thermal", params: [{ key: "amount", label: "Amount", min: 0, max: 100, step: 1, def: 80 }] },
  { id: "matrix", name: "Matrix Rain", params: [
    { key: "density", label: "Density", min: 10, max: 100, step: 1, def: 55 },
    { key: "amount", label: "Glow", min: 0, max: 100, step: 1, def: 70 } ] },
  { id: "retro", name: "Retro Palette", params: [{ key: "palette", label: "Palette", type: "select", def: "gameboy",
    options: [["gameboy", "Game Boy"], ["cga", "CGA"], ["nes", "NES"]] }] }
];

const RETRO_PALETTES = {
  gameboy: ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"],
  cga: ["#000000", "#55ffff", "#ff55ff", "#ffffff"],
  nes: ["#000000", "#fcfcfc", "#f8b800", "#f83800", "#0058f8", "#00a800"]
};

// --- 1C: canvas workspace pool ---------------------------------------------
const FX_POOL_MAX_TOTAL = 10;
const FX_POOL_MAX_PER_SIZE = 4;
let fxPoolArmed = false;
let fxPoolCount = 0;
const fxPool = new Map();

function fxPoolKey(w, h) { return w + "x" + h; }

function fxPoolClear() {
  for (const arr of fxPool.values()) {
    for (const c of arr) { c.width = 0; c.height = 0; }
  }
  fxPool.clear();
  fxPoolCount = 0;
}

function fxPrepareContext(c) {
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  ctx.filter = "none";
  return ctx;
}

function fxCreateCanvas(W, H) {
  if (typeof document === "undefined" && typeof OffscreenCanvas !== "undefined") {
    return new OffscreenCanvas(W, H);
  }
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  return c;
}

function fxCanvas(w, h) {
  const W = Math.max(1, Math.round(w));
  const H = Math.max(1, Math.round(h));
  if (fxPoolArmed) {
    const arr = fxPool.get(fxPoolKey(W, H));
    if (arr && arr.length) {
      const c = arr.pop();
      fxPoolCount--;
      fxPrepareContext(c);
      return c;
    }
  }
  return fxCreateCanvas(W, H);
}

function fxRelease(c) {
  if (!fxPoolArmed || !c) return;
  const key = fxPoolKey(c.width, c.height);
  let arr = fxPool.get(key);
  if (!arr) { arr = []; fxPool.set(key, arr); }
  if (arr.length >= FX_POOL_MAX_PER_SIZE || fxPoolCount >= FX_POOL_MAX_TOTAL) {
    c.width = 0;
    c.height = 0;
    return;
  }
  const ctx = fxPrepareContext(c);
  ctx.clearRect(0, 0, c.width, c.height);
  arr.push(c);
  fxPoolCount++;
}
function fxContext(canvas) {
  return canvas.getContext("2d", { willReadFrequently: true });
}
function fxClone(src) {
  const c = fxCanvas(src.width, src.height);
  fxContext(c).drawImage(src, 0, 0);
  return c;
}
function fxClamp(v) { return v < 0 ? 0 : v > 255 ? 255 : v; }
function fxNum(v, lo, hi, def) {
  if (v === null || v === undefined || v === "" || typeof v === "boolean") return def;
  const n = +v;
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : def;
}
function fxLuma(r, g, b) { return 0.2126 * r + 0.7152 * g + 0.0722 * b; }
let FX_LUMA = null;
function fxLumaPlane(src, n) {
  if (!FX_LUMA || FX_LUMA.length < n) FX_LUMA = new Float64Array(Math.max(n, 4096));
  const lum = FX_LUMA;
  for (let i = 0, j = 0; i < n; i++, j += 4) {
    lum[i] = fxLuma(src[j], src[j + 1], src[j + 2]);
  }
  return lum;
}
function fxHex(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "#000");
  return m ? [+("0x" + m[1]), +("0x" + m[2]), +("0x" + m[3])] : [0, 0, 0];
}
function fxData(canvas) {
  return fxContext(canvas).getImageData(0, 0, canvas.width, canvas.height);
}

function fxHalftone(c, p) {
  const s = Math.round(fxNum(p.size, 2, 14, 5)), w = c.width, h = c.height;
  const d = fxData(c).data;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  ctx.fillStyle = "#f4efe2";
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#171310";
  for (let y = 0; y < h; y += s) {
    for (let x = 0; x < w; x += s) {
      let sum = 0, n = 0;
      for (let yy = y; yy < Math.min(y + s, h); yy++)
        for (let xx = x; xx < Math.min(x + s, w); xx++) {
          const i = (yy * w + xx) * 4;
          sum += fxLuma(d[i], d[i + 1], d[i + 2]); n++;
        }
      if (!n) continue;
      const l = 1 - sum / n / 255;
      ctx.beginPath();
      ctx.arc(x + s / 2, y + s / 2, Math.max(0.4, l * s * 0.62), 0, Math.PI * 2);
      ctx.fill();
    }
  }
  return out;
}

function fxCRT(c, p) {
  const w = c.width, h = c.height;
  const src = fxData(c).data;
  const out = fxCanvas(w, h), octx = fxContext(out);
  const img = octx.createImageData(w, h), o = img.data;
  const curve = (fxNum(p.curve, 0, 100, 25) / 100) * 0.22;
  const scan = fxNum(p.scan, 0, 100, 45) / 100, mask = fxNum(p.mask, 0, 100, 35) / 100;
  const cx = w / 2, cy = h / 2;
  for (let y = 0; y < h; y++) {
    const ny = (y - cy) / cy;
    const shift = curve * ny * ny * w * 0.12;
    const scanLine = y % 2 ? 1 - scan * 0.65 : 1;
    for (let x = 0; x < w; x++) {
      const sx = Math.max(0, Math.min(w - 1, Math.round(x + shift)));
      const si = (y * w + sx) * 4, di = (y * w + x) * 4;
      let r = src[si], g = src[si + 1], b = src[si + 2];
      if (mask > 0) {
        const k = x % 3 === 0 ? 1 - mask * 0.35 : x % 3 === 1 ? 1 : 1 - mask * 0.25;
        r *= k; g *= k; b *= k;
      }
      o[di] = fxClamp(r * scanLine);
      o[di + 1] = fxClamp(g * scanLine);
      o[di + 2] = fxClamp(b * scanLine);
      o[di + 3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);
  return out;
}

function fxGlitch(c, p) {
  const w = c.width, h = c.height;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  const sx = Math.max(1, Math.round(fxNum(p.shift, 0, 40, 8)));
  ctx.drawImage(c, 0, 0);
  ctx.globalCompositeOperation = "screen";
  ctx.globalAlpha = 0.55;
  ctx.drawImage(c, sx, 0);
  ctx.drawImage(c, -sx, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  const slices = Math.round(fxNum(p.slices, 0, 40, 8));
  for (let i = 0; i < slices; i++) {
    const y = Math.floor(Math.random() * h);
    const hh = 1 + Math.floor(Math.random() * Math.max(2, h * 0.04));
    const dx = Math.round((Math.random() - 0.5) * sx * 3);
    ctx.drawImage(out, 0, y, w, hh, dx, y, w, hh);
  }
  return out;
}

function fxVHS(c, p) {
  const w = c.width, h = c.height;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  const bleed = Math.round(fxNum(p.bleed, 0, 100, 40));
  ctx.drawImage(c, 0, 0);
  ctx.globalAlpha = 0.35;
  ctx.drawImage(c, bleed, 0);
  ctx.globalAlpha = 1;
  const d = fxContext(out).getImageData(0, 0, w, h);
  const a = d.data;
  const noise = fxNum(p.noise, 0, 100, 30) / 100;
  for (let y = 0; y < h; y++) {
    const band = Math.random() < 0.06;
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const n = (Math.random() - 0.5) * 60 * noise + (band ? 18 : 0);
      a[i] = fxClamp(a[i] + n);
      a[i + 1] = fxClamp(a[i + 1] + n * 0.8);
      a[i + 2] = fxClamp(a[i + 2] + n * 1.2);
    }
  }
  fxContext(out).putImageData(d, 0, 0);
  return out;
}

function fxPixelate(c, p) {
  const s = Math.round(fxNum(p.size, 2, 40, 8));
  const w = Math.max(1, Math.round(c.width / s)), h = Math.max(1, Math.round(c.height / s));
  const small = fxCanvas(w, h);
  fxContext(small).drawImage(c, 0, 0, w, h);
  const out = fxCanvas(c.width, c.height);
  const ctx = fxContext(out);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(small, 0, 0, out.width, out.height);
  fxRelease(small);
  return out;
}

function fxPixelSort(c, p) {
  const w = c.width, h = c.height;
  const out = fxClone(c);
  const img = fxData(out), d = img.data;
  const thresh = (fxNum(p.threshold, 0, 100, 50) / 100) * 255, amount = fxNum(p.amount, 0, 100, 60) / 100;
  for (let y = 0; y < h; y++) {
    if (Math.random() > amount * 0.6) continue;
    let x = 0;
    while (x < w) {
      if (fxLuma(d[(y * w + x) * 4], d[(y * w + x) * 4 + 1], d[(y * w + x) * 4 + 2]) < thresh) { x++; continue; }
      let end = x;
      while (end < w && fxLuma(d[(y * w + end) * 4], d[(y * w + end) * 4 + 1], d[(y * w + end) * 4 + 2]) >= thresh) end++;
      const run = [];
      for (let i = x; i < end; i++) {
        const k = (y * w + i) * 4;
        run.push([d[k], d[k + 1], d[k + 2]]);
      }
      run.sort((a, b) => fxLuma(a[0], a[1], a[2]) - fxLuma(b[0], b[1], b[2]));
      for (let i = 0; i < run.length; i++) {
        const k = (y * w + x + i) * 4;
        d[k] = run[i][0]; d[k + 1] = run[i][1]; d[k + 2] = run[i][2];
      }
      x = end + 1;
    }
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}

function fxBloom(c, p) {
  const out = fxCanvas(c.width, c.height), ctx = fxContext(out);
  ctx.drawImage(c, 0, 0);
  const bright = fxCanvas(c.width, c.height), bctx = fxContext(bright);
  bctx.drawImage(c, 0, 0);
  bctx.globalCompositeOperation = "source-atop";
  bctx.fillStyle = "rgba(0,0,0,0.45)";
  bctx.fillRect(0, 0, bright.width, bright.height);
  bctx.globalCompositeOperation = "source-over";
  ctx.globalCompositeOperation = "screen";
  ctx.globalAlpha = fxNum(p.amount, 0, 100, 55) / 100;
  ctx.filter = `blur(${Math.round(fxNum(p.radius, 1, 30, 8))}px) brightness(1.35)`;
  ctx.drawImage(bright, 0, 0);
  ctx.filter = "none";
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  fxRelease(bright);
  return out;
}

function fxGrain(c, p) {
  const out = fxClone(c);
  const img = fxData(out), d = img.data, a = (fxNum(p.amount, 0, 100, 35) / 100) * 70;
  for (let i = 0; i < d.length; i += 4) {
    const n = (Math.random() - 0.5) * a;
    d[i] = fxClamp(d[i] + n);
    d[i + 1] = fxClamp(d[i + 1] + n);
    d[i + 2] = fxClamp(d[i + 2] + n);
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}

function fxVignette(c, p) {
  const out = fxClone(c);
  const ctx = fxContext(out), w = out.width, h = out.height;
  const g = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * (fxNum(p.size, 10, 100, 65) / 200), w / 2, h / 2, Math.max(w, h) * 0.72);
  g.addColorStop(0, "rgba(0,0,0,0)");
  g.addColorStop(1, `rgba(0,0,0,${(fxNum(p.amount, 0, 100, 55) / 100) * 0.9})`);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  return out;
}

function fxDuotone(c, p) {
  const out = fxClone(c);
  const img = fxData(out), d = img.data;
  const a = fxHex(p.dark), b = fxHex(p.light);
  for (let i = 0; i < d.length; i += 4) {
    const l = fxLuma(d[i], d[i + 1], d[i + 2]) / 255;
    d[i] = a[0] + (b[0] - a[0]) * l;
    d[i + 1] = a[1] + (b[1] - a[1]) * l;
    d[i + 2] = a[2] + (b[2] - a[2]) * l;
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}

const POSTERIZE_LUTS = new Map();

function fxPosterize(c, p) {
  const out = fxClone(c);
  const img = fxData(out), d = img.data;
  const levels = Math.round(fxNum(p.levels, 2, 16, 5)), step = 255 / (levels - 1);
  let lut = POSTERIZE_LUTS.get(levels);
  if (!lut) {
    lut = new Uint8ClampedArray(256);
    for (let v = 0; v < 256; v++) lut[v] = Math.round(v / step) * step;
    POSTERIZE_LUTS.set(levels, lut);
  }
  for (let i = 0; i < d.length; i += 4) {
    d[i] = lut[d[i]];
    d[i + 1] = lut[d[i + 1]];
    d[i + 2] = lut[d[i + 2]];
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}

function fxEdges(c, p) {
  const w = c.width, h = c.height;
  const amount = fxNum(p.amount, 0, 100, 80) / 100;
  if (amount <= 0) return fxClone(c);
  const src = fxData(c).data;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  const img = ctx.createImageData(w, h), o = img.data;
  for (let x = 0; x < w; x++) {
    o[(x) * 4 + 3] = 255;
    o[((h - 1) * w + x) * 4 + 3] = 255;
  }
  for (let y = 0; y < h; y++) {
    o[(y * w) * 4 + 3] = 255;
    o[(y * w + w - 1) * 4 + 3] = 255;
  }
  const lum = fxLumaPlane(src, w * h);
  for (let y = 1; y < h - 1; y++) {
    let i = y * w + 1, up = i - w, dn = i + w;
    for (let x = 1; x < w - 1; x++, i++, up++, dn++) {
      const ul = lum[up - 1], uc = lum[up], ur = lum[up + 1];
      const lc = lum[i - 1], rc = lum[i + 1];
      const dl = lum[dn - 1], dc = lum[dn], dr = lum[dn + 1];
      const sx = -ul + 0 * uc + ur - 2 * lc + 0 * lum[i] + 2 * rc - dl + 0 * dc + dr;
      const sy = -ul - 2 * uc - ur + 0 * lc + 0 * lum[i] + 0 * rc + dl + 2 * dc + dr;
      const m = fxClamp(Math.sqrt(sx * sx + sy * sy) * amount);
      const di = i * 4;
      o[di] = o[di + 1] = o[di + 2] = m; o[di + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return out;
}

function fxSketch(c, p) {
  const w = c.width, h = c.height;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  const amount = fxNum(p && p.amount, 0, 100, 70) / 100;
  const hatch = fxNum(p && p.cross, 0, 100, 40) / 100;
  if (amount <= 0) { ctx.putImageData(fxData(c), 0, 0); return out; }
  const src = fxData(c).data;
  const img = ctx.createImageData(w, h), o = img.data;
  const sp45 = Math.round(14 - 8 * hatch);
  const sp135 = Math.round(15 - 9 * hatch);
  const spAxis = Math.round(16 - 9 * hatch);
  const spDense = Math.round(11 - 5 * hatch);
  const lat = w + h + 1;  
  const pencil = 0.72;    
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const L = fxLuma(src[i], src[i + 1], src[i + 2]) / 255;
      let paper = 255 * (0.60 + 0.40 * L);
      if (L < 0.75 && (x + y) % sp45 === 0) paper *= pencil;
      if (L < 0.50 && (x - y + lat) % sp135 === 0) paper *= pencil;
      if (L < 0.30 && (x % spAxis === 0 || y % spAxis === 0)) paper *= pencil;
      if (L < 0.15 && ((x + y) % spDense === 0 || (x - y + lat) % spDense === 0)) paper *= pencil;
      const v = Math.max(paper, 60);
      o[i] = src[i] + (v - src[i]) * amount;
      o[i + 1] = src[i + 1] + (v - src[i + 1]) * amount;
      o[i + 2] = src[i + 2] + (v - src[i + 2]) * amount;
      o[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return out;
}

function fxOil(c, p) {
  const w = c.width, h = c.height;
  const src = fxData(c).data;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  const img = ctx.createImageData(w, h), o = img.data;
  const r = Math.round(fxNum(p.radius, 1, 3, 2));
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let bestVar = Infinity, best = [0, 0, 0];
      for (let qy = -1; qy <= 1; qy += 2) {
        for (let qx = -1; qx <= 1; qx += 2) {
          let sr = 0, sg = 0, sb = 0, n = 0, vals = [];
          for (let ky = -r; ky <= r; ky++) {
            for (let kx = -r; kx <= r; kx++) {
              if ((qx < 0 && kx > 0) || (qx > 0 && kx < 0) || (qy < 0 && ky > 0) || (qy > 0 && ky < 0)) continue;
              const px = Math.max(0, Math.min(w - 1, x + kx)), py = Math.max(0, Math.min(h - 1, y + ky));
              const i = (py * w + px) * 4;
              sr += src[i]; sg += src[i + 1]; sb += src[i + 2];
              vals.push(fxLuma(src[i], src[i + 1], src[i + 2])); n++;
            }
          }
          const mean = vals.reduce((a, v) => a + v, 0) / n;
          const varr = vals.reduce((a, v) => a + (v - mean) * (v - mean), 0) / n;
          if (varr < bestVar) { bestVar = varr; best = [sr / n, sg / n, sb / n]; }
        }
      }
      const i = (y * w + x) * 4;
      o[i] = best[0]; o[i + 1] = best[1]; o[i + 2] = best[2]; o[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return out;
}

function fxConvolve(c, kernel, amount) {
  amount = Math.min(1, Math.max(0, Number.isFinite(amount) ? amount : 0));
  const w = c.width, h = c.height;
  if (amount <= 0) {
    const out = fxCanvas(w, h), outCtx = fxContext(out);
    outCtx.drawImage(c, 0, 0);
    const img = outCtx.getImageData(0, 0, w, h), o = img.data;
    let repaint = false;
    for (let i = 3; i < o.length; i += 4) {
      if (o[i] !== 255) { repaint = true; break; }
    }
    if (repaint) {
      for (let i = 3; i < o.length; i += 4) o[i] = 255;
      outCtx.putImageData(img, 0, 0);
    }
    return out;
  }
  const src = fxData(c).data;
  const out = fxCanvas(w, h), ctx = fxContext(out);
  const img = ctx.createImageData(w, h), o = img.data;
  const k0 = kernel[0], k1 = kernel[1], k2 = kernel[2];
  const k3 = kernel[3], k4 = kernel[4], k5 = kernel[5];
  const k6 = kernel[6], k7 = kernel[7], k8 = kernel[8];
  const row = w * 4;
  for (let x = 0; x < w; x++) {
    const t = x * 4, b = ((h - 1) * w + x) * 4;
    o[t] = src[t]; o[t + 1] = src[t + 1]; o[t + 2] = src[t + 2]; o[t + 3] = 255;
    o[b] = src[b]; o[b + 1] = src[b + 1]; o[b + 2] = src[b + 2]; o[b + 3] = 255;
  }
  for (let y = 1; y < h - 1; y++) {
    const rowStart = y * row;
    for (const x of [0, w - 1]) {
      const e = rowStart + x * 4;
      o[e] = src[e]; o[e + 1] = src[e + 1]; o[e + 2] = src[e + 2]; o[e + 3] = 255;
    }
    for (let x = 1; x < w - 1; x++) {
      const di = rowStart + x * 4;
      const u = di - row, d = di + row;
      const r00 = src[u - 4], g00 = src[u - 3], b00 = src[u - 2];
      const r01 = src[u], g01 = src[u + 1], b01 = src[u + 2];
      const r02 = src[u + 4], g02 = src[u + 5], b02 = src[u + 6];
      const r10 = src[di - 4], g10 = src[di - 3], b10 = src[di - 2];
      const r11 = src[di], g11 = src[di + 1], b11 = src[di + 2];
      const r12 = src[di + 4], g12 = src[di + 5], b12 = src[di + 6];
      const r20 = src[d - 4], g20 = src[d - 3], b20 = src[d - 2];
      const r21 = src[d], g21 = src[d + 1], b21 = src[d + 2];
      const r22 = src[d + 4], g22 = src[d + 5], b22 = src[d + 6];
      const vr = r00 * k0 + r01 * k1 + r02 * k2 + r10 * k3 + r11 * k4 + r12 * k5 + r20 * k6 + r21 * k7 + r22 * k8;
      const vg = g00 * k0 + g01 * k1 + g02 * k2 + g10 * k3 + g11 * k4 + g12 * k5 + g20 * k6 + g21 * k7 + g22 * k8;
      const vb = b00 * k0 + b01 * k1 + b02 * k2 + b10 * k3 + b11 * k4 + b12 * k5 + b20 * k6 + b21 * k7 + b22 * k8;
      const nr = r11 + (vr - r11) * amount;
      const ng = g11 + (vg - g11) * amount;
      const nb = b11 + (vb - b11) * amount;
      o[di] = nr < 0 ? 0 : nr > 255 ? 255 : nr;
      o[di + 1] = ng < 0 ? 0 : ng > 255 ? 255 : ng;
      o[di + 2] = nb < 0 ? 0 : nb > 255 ? 255 : nb;
      o[di + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return out;
}

function fxEmboss(c, p) {
  return fxConvolve(c, [-2, -1, 0, -1, 1, 1, 0, 1, 2], fxNum(p.amount, 0, 100, 70) / 100);
}
function fxSharpen(c, p) {
  return fxConvolve(c, [0, -1, 0, -1, 5, -1, 0, -1, 0], fxNum(p.amount, 0, 100, 60) / 100);
}
function fxBlur(c, p) {
  const w = c.width, h = c.height;
  const r = fxNum(p.radius, 0, 20, 4);
  const out = fxCanvas(w, h), ctx = fxContext(out);
  if (r <= 0) { ctx.drawImage(c, 0, 0); return out; }
  const pad = Math.ceil(r * 2) + 1;
  const padded = fxCanvas(w + pad * 2, h + pad * 2);
  const pctx = fxContext(padded);
  pctx.drawImage(c, pad, pad);
  pctx.drawImage(c, 0, 0, w, 1, pad, 0, w, pad);
  pctx.drawImage(c, 0, h - 1, w, 1, pad, pad + h, w, pad);
  pctx.drawImage(c, 0, 0, 1, h, 0, pad, pad, h);
  pctx.drawImage(c, w - 1, 0, 1, h, pad + w, pad, pad, h);
  pctx.drawImage(c, 0, 0, 1, 1, 0, 0, pad, pad);
  pctx.drawImage(c, w - 1, 0, 1, 1, pad + w, 0, pad, pad);
  pctx.drawImage(c, 0, h - 1, 1, 1, 0, pad + h, pad, pad);
  pctx.drawImage(c, w - 1, h - 1, 1, 1, pad + w, pad + h, pad, pad);
  const blurred = fxCanvas(w + pad * 2, h + pad * 2);
  const bctx = fxContext(blurred);
  bctx.filter = `blur(${r}px)`;
  bctx.drawImage(padded, 0, 0);
  bctx.filter = "none";
  ctx.drawImage(blurred, pad, pad, w, h, 0, 0, w, h);
  fxRelease(padded);
  fxRelease(blurred);
  const img = ctx.getImageData(0, 0, w, h), d = img.data;
  let fixed = false;
  for (let i = 3; i < d.length; i += 4) if (d[i] !== 255) { d[i] = 255; fixed = true; }
  if (fixed) ctx.putImageData(img, 0, 0);
  return out;
}
function fxInvert(c) {
  const out = fxClone(c), img = fxData(out), d = img.data;
  for (let i = 0; i < d.length; i += 4) { d[i] = 255 - d[i]; d[i + 1] = 255 - d[i + 1]; d[i + 2] = 255 - d[i + 2]; }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}
function fxSepia(c, p) {
  const out = fxClone(c), img = fxData(out), d = img.data, a = fxNum(p.amount, 0, 100, 80) / 100;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    const sr = 0.393 * r + 0.769 * g + 0.189 * b;
    const sg = 0.349 * r + 0.686 * g + 0.168 * b;
    const sb = 0.272 * r + 0.534 * g + 0.131 * b;
    d[i] = fxClamp(r + (sr - r) * a);
    d[i + 1] = fxClamp(g + (sg - g) * a);
    d[i + 2] = fxClamp(b + (sb - b) * a);
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}
function fxThermal(c, p) {
  const out = fxClone(c), img = fxData(out), d = img.data, a = fxNum(p.amount, 0, 100, 80) / 100;
  for (let i = 0; i < d.length; i += 4) {
    const l = fxLuma(d[i], d[i + 1], d[i + 2]) / 255;
    const r = fxClamp(255 * Math.min(1, l * 2.2));
    const g = fxClamp(255 * Math.max(0, Math.min(1, l * 2 - 0.35)));
    const b = fxClamp(255 * Math.max(0, Math.min(1, l * 2 - 1.05)));
    d[i] = d[i] + (r - d[i]) * a;
    d[i + 1] = d[i + 1] + (g - d[i + 1]) * a;
    d[i + 2] = d[i + 2] + (b - d[i + 2]) * a;
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}
function fxMatrix(c, p) {
  const out = fxCanvas(c.width, c.height), ctx = fxContext(out);
  ctx.drawImage(c, 0, 0);
  ctx.fillStyle = "rgba(0,10,2,0.62)";
  ctx.fillRect(0, 0, out.width, out.height);
  const cell = Math.max(10, Math.round(out.width / 90));
  const cols = Math.ceil(out.width / cell);
  ctx.font = `${cell}px monospace`;
  ctx.textBaseline = "top";
  const density = fxNum(p.density, 10, 100, 55) / 100, glow = fxNum(p.amount, 0, 100, 70) / 100;
  for (let i = 0; i < cols * density; i++) {
    const x = Math.floor(Math.random() * cols) * cell;
    const len = 2 + Math.floor(Math.random() * 10);
    const y0 = Math.random() * out.height;
    for (let j = 0; j < len; j++) {
      const y = y0 + j * cell;
      if (y > out.height) break;
      ctx.fillStyle = `rgba(${Math.round(80 + 175 * glow)},255,${Math.round(120 + 60 * glow)},${j === 0 ? 0.95 : 0.12 + 0.5 * (1 - j / len)})`;
      ctx.fillText(String.fromCharCode(0x30a0 + Math.floor(Math.random() * 96)), x, y);
    }
  }
  return out;
}
function fxRetro(c, p) {
  const pal = (RETRO_PALETTES[p.palette] || RETRO_PALETTES.gameboy).map(fxHex);
  const out = fxClone(c), img = fxData(out), d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    let best = pal[0], bd = Infinity;
    for (const col of pal) {
      const dr = d[i] - col[0], dg = d[i + 1] - col[1], db = d[i + 2] - col[2];
      const dist = dr * dr + dg * dg + db * db;
      if (dist < bd) { bd = dist; best = col; }
    }
    d[i] = best[0]; d[i + 1] = best[1]; d[i + 2] = best[2];
  }
  fxContext(out).putImageData(img, 0, 0);
  return out;
}

const EFFECT_RUNNERS = {
  halftone: fxHalftone, crt: fxCRT, glitch: fxGlitch, vhs: fxVHS,
  pixelate: fxPixelate, pixelsort: fxPixelSort, bloom: fxBloom,
  grain: fxGrain, vignette: fxVignette, duotone: fxDuotone,
  posterize: fxPosterize, edges: fxEdges, sketch: fxSketch, oil: fxOil,
  emboss: fxEmboss, blur: fxBlur, sharpen: fxSharpen,
  invert: fxInvert, sepia: fxSepia, thermal: fxThermal,
  matrix: fxMatrix, retro: fxRetro
};

function effectDefaults(id) {
  const def = EFFECTS.find(e => e.id === id);
  const out = {};
  if (def) def.params.forEach(p => { out[p.key] = p.def; });
  return out;
}

function makeEffect(id, enabled) {
  return { id, enabled: !!enabled, params: effectDefaults(id) };
}

// --- H4: per-stage pipeline cache -------------------------------------------
const STAGE_UNCACHEABLE = new Set(["glitch", "vhs", "pixelsort", "grain", "matrix"]);
const STAGE_CACHE_MAX = 8;
let stageSlots = [];

function clearStageCache() {
  for (const slot of stageSlots) {
    if (slot && slot.canvas) { slot.canvas.width = 0; slot.canvas.height = 0; }
  }
  stageSlots = [];
}

function stageCacheAllowed() {
  return typeof state === "undefined" || !state.cacheDisabled;
}

function stageKey(prevKey, fx) {
  if (!prevKey || STAGE_UNCACHEABLE.has(fx.id)) return null;
  const params = fx.params || {};
  let s = prevKey + ">" + fx.id;
  for (const k of Object.keys(params).sort()) s += "|" + k + "=" + params[k];
  return s;
}

const NEUTRAL_COPY = {
  edges: p => fxNum(p.amount, 0, 100, 80) <= 0,
  sketch: p => fxNum(p.amount, 0, 100, 70) <= 0,
  blur: p => fxNum(p.radius, 0, 20, 4) <= 0,
  sepia: p => fxNum(p.amount, 0, 100, 80) <= 0,
  thermal: p => fxNum(p.amount, 0, 100, 80) <= 0,
};

function isNeutralCopy(id, params) {
  const test = NEUTRAL_COPY[id];
  return !!test && test(params || {});
}

function stageCacheGet(index, key) {
  const slot = stageSlots[index];
  return slot && slot.key === key ? slot.canvas : null;
}

function stageCachePut(index, key, canvas) {
  if (index >= STAGE_CACHE_MAX) return;
  const old = stageSlots[index];
  if (old && old.canvas !== canvas) { old.canvas.width = 0; old.canvas.height = 0; }
  stageSlots[index] = { key, canvas };
}

let lastPooledOutput = null;
let lastPooledSize = "";

function applyEffects(sourceCanvas, effects, baseKey) {
  let current = sourceCanvas;
  const cacheable = !!baseKey && stageCacheAllowed();
  fxPoolArmed = !cacheable;
  if (fxPoolArmed) {
    const size = fxPoolKey(sourceCanvas.width, sourceCanvas.height);
    if (size !== lastPooledSize) {
      if (lastPooledOutput) { lastPooledOutput = null; }
      fxPoolClear();
      lastPooledSize = size;
    }
    if (lastPooledOutput) { fxRelease(lastPooledOutput); lastPooledOutput = null; }
  }
  let chainKey = cacheable ? baseKey : null;
  let owned = null;
  let index = 0;
  for (const fx of effects || []) {
    if (!fx.enabled) continue;
    const run = EFFECT_RUNNERS[fx.id];
    if (!run) continue;
    const key = chainKey ? stageKey(chainKey, fx) : null;
    if (key) {
      const hit = stageCacheGet(index, key);
      if (hit) {
        if (owned) { fxRelease(owned); owned = null; }
        current = hit;
        chainKey = key; index++; continue;
      }
    }
    const params = fx.params || effectDefaults(fx.id);
    if (isNeutralCopy(fx.id, params)) {
      chainKey = key;
      index++;
      continue;
    }
    try {
      const next = run(current, params);
      if (owned && owned !== next) { fxRelease(owned); owned = null; }
      current = next;
      if (fxPoolArmed && current !== sourceCanvas) owned = current;
      if (key) { stageCachePut(index, key, current); chainKey = key; }
      else chainKey = null;
    } catch (e) { console.warn("effect failed:", fx.id, e); chainKey = null; }
    index++;
  }
  if (fxPoolArmed) {
    lastPooledOutput = owned;
  } else {
    lastPooledOutput = null;
    lastPooledSize = "";
  }
  return current;
}

function autoLevels(canvas) {
  const ctx = fxContext(canvas);
  const w = canvas.width, h = canvas.height;
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  const hist = new Uint32Array(256);
  const step = Math.max(1, Math.floor(d.length / 4 / 20000));
  let total = 0;
  for (let i = 0; i < d.length; i += 4 * step) {
    const l = Math.round(fxLuma(d[i], d[i + 1], d[i + 2]));
    hist[l]++; total++;
  }
  if (!total) return canvas;
  let lo = 0, hi = 255, acc = 0;
  for (let i = 0; i < 256; i++) { acc += hist[i]; if (acc > total * 0.01) { lo = i; break; } }
  acc = 0;
  for (let i = 255; i >= 0; i--) { acc += hist[i]; if (acc > total * 0.01) { hi = i; break; } }
  if (hi - lo < 8) return canvas;
  const scale = 255 / (hi - lo);
  for (let i = 0; i < d.length; i += 4) {
    d[i] = fxClamp((d[i] - lo) * scale);
    d[i + 1] = fxClamp((d[i + 1] - lo) * scale);
    d[i + 2] = fxClamp((d[i + 2] - lo) * scale);
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

