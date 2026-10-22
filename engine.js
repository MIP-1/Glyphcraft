const CHAR_CATEGORIES = {
  all: " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
  letters: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
  numbers: "0123456789",
  symbols: "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
  "letters-numbers": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
};

const CHAR_SETS = {
  all: null,
  consonants: /[BCDFGHJKLMNPQRSTVWXYZbcdfghjklmnpqrstvwxyz]/,
  vowels: /[AEIOUaeiou]/,
  uppercase: /[A-Z]/,
  lowercase: /[a-z]/,
  binary: /[01]/
};

const BUILTIN_PALETTES = [
  { name: "1-bit", colors: ["#000", "#fff"] },
  { name: "2-color", colors: ["#000", "#fff"], editable: true },
  { name: "Game Boy", colors: ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"] },
  { name: "CGA", colors: ["#000", "#555", "#aaa", "#fff", "#f00", "#0f0", "#ff0", "#0ff"] },
  { name: "Grayscale 4", colors: ["#000", "#555", "#aaa", "#fff"] },
  { name: "Grayscale 8", colors: ["#000", "#222", "#444", "#666", "#888", "#aaa", "#ccc", "#fff"] },
  { name: "Grayscale 16", colors: ["#000", "#111", "#222", "#333", "#444", "#555", "#666", "#777", "#888", "#999", "#aaa", "#bbb", "#ccc", "#ddd", "#eee", "#fff"] },
  { name: "Terminal", colors: ["#000", "#003300", "#006600", "#00aa00", "#00ff00", "#ccffcc"] },
  { name: "Amber", colors: ["#000", "#331a00", "#663300", "#cc6600", "#ffaa00", "#ffe0aa"] },
  { name: "Sunset", colors: ["#1a0a2e", "#3e1a4a", "#6b2d5e", "#a84866", "#e87a6e", "#ffb88c"] },
  { name: "Ocean", colors: ["#001219", "#005f73", "#0a9396", "#94d2bd", "#e9d8a6", "#ee9b00"] },
  { name: "Matrix", colors: ["#000", "#001100", "#003300", "#005500", "#00aa00", "#00ff00", "#88ff88", "#cceecc"] },
  { name: "Monochrome", colors: ["#000", "#222", "#444", "#666", "#888", "#aaa", "#ccc", "#fff"] }
];

function measureGlyphDensities(font, chars) {
  const cacheKey = font + "|" + chars;
  if (measureGlyphDensities.cache && measureGlyphDensities.cache.key === cacheKey) {
    return measureGlyphDensities.cache.densities;
  }
  const size = 16;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.font = font;
  ctx.textBaseline = "top";
  ctx.fillStyle = "#fff";

  const densities = [];
  for (const ch of chars) {
    ctx.clearRect(0, 0, size, size);
    ctx.fillText(ch, 0, 0);
    const data = ctx.getImageData(0, 0, size, size).data;
    let count = 0;
    for (let i = 3; i < data.length; i += 4) if (data[i] > 16) count++;
    densities.push(count / (size * size));
  }
  measureGlyphDensities.cache = { key: cacheKey, densities };
  return densities;
}

function buildRamp(category, set, inject, textStyle) {
  let base = CHAR_CATEGORIES[category] || CHAR_CATEGORIES.all;
  const filter = CHAR_SETS[set];
  if (filter) base = base.split("").filter(c => filter.test(c)).join("");
  if (inject) base = inject + base;
  base = [...new Set(base.split(""))].join("");
  if (!base.length) base = "@";

  const weight = textStyle === "bold" ? "700" : "400";
  const style = textStyle === "italic" ? "italic" : "normal";
  const font = `${style} ${weight} 14px "JetBrains Mono", monospace`;

  const densities = measureGlyphDensities(font, base);
  const paired = base.split("").map((ch, i) => ({ ch, d: densities[i] }));
  paired.sort((a, b) => a.d - b.d);
  return { chars: paired.map(p => p.ch), font };
}

function extractPalette(imageData, colorCount = 6) {
  const pixels = imageData.data;
  const sampleStep = Math.max(1, Math.floor(pixels.length / 4 / 5000));
  const samples = [];
  for (let i = 0; i < pixels.length; i += 4 * sampleStep) {
    samples.push([pixels[i], pixels[i+1], pixels[i+2]]);
  }
  let centroids = samples[Math.floor(Math.random() * samples.length)].slice();
  for (let c = 1; c < colorCount; c++) {
    let maxDist = -1, farthest = samples[0];
    for (const s of samples) {
      let minDist = Infinity;
      for (const cent of centroids) {
        const dr = s[0]-cent[0], dg = s[1]-cent[1], db = s[2]-cent[2];
        minDist = Math.min(minDist, dr*dr + dg*dg + db*db);
      }
      if (minDist > maxDist) { maxDist = minDist; farthest = s; }
    }
    centroids.push(farthest);
  }
  for (let iter = 0; iter < 10; iter++) {
    const clusters = centroids.map(() => []);
    for (const s of samples) {
      let best = 0, bestDist = Infinity;
      centroids.forEach((cent, ci) => {
        const dr = s[0]-cent[0], dg = s[1]-cent[1], db = s[2]-cent[2];
        const dist = dr*dr + dg*dg + db*db;
        if (dist < bestDist) { bestDist = dist; best = ci; }
      });
      clusters[best].push(s);
    }
    let moved = false;
    centroids.forEach((cent, ci) => {
      const cl = clusters[ci];
      if (!cl.length) return;
      const sum = cl.reduce((a, v) => [a[0]+v[0], a[1]+v[1], a[2]+v[2]], [0,0,0]);
      const newCent = sum.map(v => Math.round(v / cl.length));
      if (newCent[0] !== cent[0] || newCent[1] !== cent[1] || newCent[2] !== cent[2]) moved = true;
      centroids[ci] = newCent;
    });
    if (!moved) break;
  }
  return centroids.map(([r,g,b]) => `rgb(${r},${g},${b})`);
}

function nearestPaletteColor(r, g, b, palette) {
  if (!palette || !palette.length) return `rgb(${r},${g},${b})`;
  const parse = c => {
    let m = c.match(/rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/);
    if (m) return [+m[1], +m[2], +m[3]];
    m = c.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
    if (m) return [+("0x" + m[1]), +("0x" + m[2]), +("0x" + m[3])];
    return [0, 0, 0];
  };
  let best = palette[0], bestDist = Infinity;
  for (const c of palette) {
    const [pr, pg, pb] = parse(c);
    const dr = r - pr, dg = g - pg, db = b - pb;
    const dist = dr * dr + dg * dg + db * db;
    if (dist < bestDist) { bestDist = dist; best = c; }
  }
  return best;
}

function applyAdjustments(ctx, w, h, adj) {
  const filters = [];
  if (adj.brightness !== 0) filters.push(`brightness(${1 + adj.brightness/100})`);
  if (adj.contrast !== 0) filters.push(`contrast(${1 + adj.contrast/100})`);
  if (adj.saturation !== 0) filters.push(`saturate(${1 + adj.saturation/100})`);
  if (adj.hue !== 0) filters.push(`hue-rotate(${adj.hue}deg)`);
  if (adj.blur > 0) filters.push(`blur(${adj.blur}px)`);
  if (filters.length) {
    ctx.filter = filters.join(" ");
    ctx.drawImage(ctx.canvas, 0, 0, w, h);
    ctx.filter = "none";
  }
  if (adj.highlights !== 0 || adj.shadows !== 0 || adj.sharpen > 0) {
    const imgData = ctx.getImageData(0, 0, w, h);
    const data = imgData.data;
    const hl = adj.highlights / 100;
    const sh = adj.shadows / 100;
    const sharp = adj.sharpen / 100;
    if (hl !== 0 || sh !== 0) {
      for (let i = 0; i < data.length; i += 4) {
        const l = 0.2126*data[i] + 0.7152*data[i+1] + 0.0722*data[i+2];
        if (l > 180 && hl !== 0) {
          const f = 1 + hl * (l - 180) / 75;
          data[i] = Math.min(255, data[i] * f);
          data[i+1] = Math.min(255, data[i+1] * f);
          data[i+2] = Math.min(255, data[i+2] * f);
        } else if (l < 76 && sh !== 0) {
          const f = 1 + sh * (76 - l) / 76;
          data[i] = Math.min(255, data[i] * f);
          data[i+1] = Math.min(255, data[i+1] * f);
          data[i+2] = Math.min(255, data[i+2] * f);
        }
      }
    }
    if (sharp > 0) {
      const src = new Uint8ClampedArray(data);
      const kernel = [[0,-1,0],[-1,5,-1],[0,-1,0]];
      for (let y = 1; y < h-1; y++) {
        for (let x = 1; x < w-1; x++) {
          let r = 0, g = 0, b = 0;
          for (let ky = -1; ky <= 1; ky++) {
            for (let kx = -1; kx <= 1; kx++) {
              const idx = ((y+ky)*w + (x+kx))*4;
              const k = kernel[ky+1][kx+1];
              r += src[idx] * k;
              g += src[idx+1] * k;
              b += src[idx+2] * k;
            }
          }
          const idx = (y*w + x)*4;
          data[idx] = Math.max(0, Math.min(255, r));
          data[idx+1] = Math.max(0, Math.min(255, g));
          data[idx+2] = Math.max(0, Math.min(255, b));
        }
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }
  if (adj.invert) {
    const imgData = ctx.getImageData(0, 0, w, h);
    const data = imgData.data;
    for (let i = 0; i < data.length; i += 4) {
      data[i] = 255 - data[i];
      data[i+1] = 255 - data[i+1];
      data[i+2] = 255 - data[i+2];
    }
    ctx.putImageData(imgData, 0, 0);
  }
  if (adj.sepia) {
    const imgData = ctx.getImageData(0, 0, w, h);
    const data = imgData.data;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i+1], b = data[i+2];
      data[i] = Math.min(255, 0.393*r + 0.769*g + 0.189*b);
      data[i+1] = Math.min(255, 0.349*r + 0.686*g + 0.168*b);
      data[i+2] = Math.min(255, 0.272*r + 0.534*g + 0.131*b);
    }
    ctx.putImageData(imgData, 0, 0);
  }
}

function scriptMetrics(destW, destH, depth) {
  const cols = depth;
  const cellW = destW / cols;
  const fontPx = Math.max(7, Math.round(cellW * 1.5));
  const cellH = fontPx * 1.1;
  return { cols, cellW, cellH, fontPx, rows: Math.ceil(destH / cellH) };
}

function renderScript(sourceCanvas, destCtx, destW, destH, opts) {
  const { offset, ramp, transparentBg, bgColor, colorMode, palette } = opts;
  const { cols, cellW, cellH, fontPx, rows } = scriptMetrics(destW, destH, opts.depth);

  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width = destW;
  tmpCanvas.height = destH;
  const tmpCtx = tmpCanvas.getContext("2d", { willReadFrequently: true });
  tmpCtx.drawImage(sourceCanvas, 0, 0, destW, destH);
  if (!opts.preApplied) applyAdjustments(tmpCtx, destW, destH, opts.adj);
  if (opts.autoLevels) autoLevels(tmpCanvas);

  const imgData = tmpCtx.getImageData(0, 0, destW, destH);
  const data = imgData.data;

  destCtx.clearRect(0, 0, destW, destH);
  if (!transparentBg) {
    destCtx.fillStyle = bgColor;
    destCtx.fillRect(0, 0, destW, destH);
  }

  destCtx.font = ramp.font.replace(/14px/, fontPx + "px");
  destCtx.textBaseline = "top";
  const rampLen = ramp.chars.length;
  const threshold = 0.02;

  for (let row = 0; row < rows; row++) {
    const y = row * cellH;
    for (let col = 0; col < cols; col++) {
      const x = col * cellW;
      let r = 0, g = 0, b = 0, luma = 0, count = 0;
      const sx = Math.floor(x), sy = Math.floor(y);
      const sw = Math.ceil(cellW), sh = Math.ceil(cellH);
      for (let py = sy; py < Math.min(sy+sh, destH); py++) {
        for (let px = sx; px < Math.min(sx+sw, destW); px++) {
          const idx = (py * destW + px) * 4;
          r += data[idx]; g += data[idx+1]; b += data[idx+2];
          luma += 0.2126*data[idx] + 0.7152*data[idx+1] + 0.0722*data[idx+2];
          count++;
        }
      }
      if (!count) continue;
      r = Math.round(r / count); g = Math.round(g / count); b = Math.round(b / count);
      luma = luma / count / 255;

      if (luma < threshold) continue;

      let idx = Math.floor(luma * (rampLen - 1)) + offset;
      idx = ((idx % rampLen) + rampLen) % rampLen;
      const ch = ramp.chars[idx];

      if (colorMode === "spectrum") destCtx.fillStyle = `rgb(${r},${g},${b})`;
      else if (colorMode === "palette") destCtx.fillStyle = nearestPaletteColor(r, g, b, palette);
      else destCtx.fillStyle = opts.monoColor || "#e9dfc8";

      destCtx.fillText(ch, x, y);
    }
  }
}

function prepareBase(source, destW, destH, opts) {
  const canvas = document.createElement("canvas");
  canvas.width = destW;
  canvas.height = destH;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(source, 0, 0, destW, destH);
  if (opts.adj) applyAdjustments(ctx, destW, destH, opts.adj);
  const processed = applyEffects(canvas, opts.effects || []);
  return processed;
}

function renderToCanvas(source, opts, destW, destH) {
  const base = prepareBase(source, destW, destH, opts);
  const canvas = document.createElement("canvas");
  canvas.width = destW; canvas.height = destH;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (opts.mode === "script") {
    renderScript(base, ctx, destW, destH, { ...opts, preApplied: true });
  } else if (opts.mode === "dither") {
    renderDither(base, ctx, destW, destH, { ...opts, preApplied: true });
  } else {
    ctx.drawImage(base, 0, 0);
  }
  return canvas;
}

function canvasToBlob(canvas, type, quality) {
  return new Promise(res => canvas.toBlob(res, type, quality));
}

function canvasToSvg(canvas, opts) {
  const { offset, ramp, transparentBg, bgColor, colorMode, palette, monoColor } = opts;
  const { cols, cellW, cellH, fontPx, rows } = scriptMetrics(canvas.width, canvas.height, opts.depth);

  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width = canvas.width;
  tmpCanvas.height = canvas.height;
  const tmpCtx = tmpCanvas.getContext("2d", { willReadFrequently: true });
  tmpCtx.drawImage(canvas, 0, 0);
  if (!opts.preApplied) applyAdjustments(tmpCtx, canvas.width, canvas.height, opts.adj);
  if (opts.autoLevels) autoLevels(tmpCanvas);
  const imgData = tmpCtx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imgData.data;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}">`;
  if (!transparentBg) svg += `<rect width="100%" height="100%" fill="${bgColor}"/>`;
  svg += `<style>text{font-family:"JetBrains Mono",monospace;font-size:${fontPx}px;dominant-baseline:hanging}</style>`;
  const rampLen = ramp.chars.length;
  const threshold = 0.02;

  for (let row = 0; row < rows; row++) {
    const y = row * cellH;
    for (let col = 0; col < cols; col++) {
      const x = col * cellW;
      let r = 0, g = 0, b = 0, luma = 0, count = 0;
      const sx = Math.floor(x), sy = Math.floor(y);
      const sw = Math.ceil(cellW), sh = Math.ceil(cellH);
      for (let py = sy; py < Math.min(sy+sh, canvas.height); py++) {
        for (let px = sx; px < Math.min(sx+sw, canvas.width); px++) {
          const idx = (py * canvas.width + px) * 4;
          r += data[idx]; g += data[idx+1]; b += data[idx+2];
          luma += 0.2126*data[idx] + 0.7152*data[idx+1] + 0.0722*data[idx+2];
          count++;
        }
      }
      if (!count) continue;
      r = Math.round(r / count); g = Math.round(g / count); b = Math.round(b / count);
      luma = luma / count / 255;
      if (luma < threshold) continue;
      let idx = Math.floor(luma * (rampLen - 1)) + offset;
      idx = ((idx % rampLen) + rampLen) % rampLen;
      const ch = ramp.chars[idx].replace(/[&<>"']/g, c => ({'&':'&','<':'<','>':'>','"':'"',"'":'&apos;'}[c]));
      let fill;
      if (colorMode === "spectrum") fill = `rgb(${r},${g},${b})`;
      else if (colorMode === "palette") fill = nearestPaletteColor(r, g, b, palette);
      else fill = monoColor || "#e9dfc8";
      svg += `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" fill="${fill}">${ch}</text>`;
    }
  }
  svg += "</svg>";
  return svg;
}

function canvasToTxt(canvas, opts) {
  const { offset, ramp } = opts;
  const { cols, cellW, cellH, rows } = scriptMetrics(canvas.width, canvas.height, opts.depth);

  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width = canvas.width;
  tmpCanvas.height = canvas.height;
  const tmpCtx = tmpCanvas.getContext("2d", { willReadFrequently: true });
  tmpCtx.drawImage(canvas, 0, 0);
  if (!opts.preApplied) applyAdjustments(tmpCtx, canvas.width, canvas.height, opts.adj);
  if (opts.autoLevels) autoLevels(tmpCanvas);
  const imgData = tmpCtx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imgData.data;

  let txt = "";
  const rampLen = ramp.chars.length;
  const threshold = 0.02;
  for (let row = 0; row < rows; row++) {
    const y = row * cellH;
    let line = "";
    for (let col = 0; col < cols; col++) {
      const x = col * cellW;
      let luma = 0, count = 0;
      const sx = Math.floor(x), sy = Math.floor(y);
      const sw = Math.ceil(cellW), sh = Math.ceil(cellH);
      for (let py = sy; py < Math.min(sy+sh, canvas.height); py++) {
        for (let px = sx; px < Math.min(sx+sw, canvas.width); px++) {
          const idx = (py * canvas.width + px) * 4;
          luma += 0.2126*data[idx] + 0.7152*data[idx+1] + 0.0722*data[idx+2];
          count++;
        }
      }
      if (!count) { line += " "; continue; }
      luma = luma / count / 255;
      if (luma < threshold) { line += " "; continue; }
      let idx = Math.floor(luma * (rampLen - 1)) + offset;
      idx = ((idx % rampLen) + rampLen) % rampLen;
      line += ramp.chars[idx];
    }
    txt += line + "\n";
  }
  return txt;
}

const SIZE_PRESETS = [
  // Video
  { group: "Video", id: "720p", label: "720p 1280×720", w: 1280, h: 720 },
  { group: "Video", id: "1080p", label: "1080p 1920×1080", w: 1920, h: 1080 },
  { group: "Video", id: "2k", label: "2K 2560×1440", w: 2560, h: 1440 },
  { group: "Video", id: "4k", label: "4K 3840×2160", w: 3840, h: 2160 },
  { group: "Video", id: "8k", label: "8K 7680×4320", w: 7680, h: 4320 },
  { group: "Video", id: "vertical-1080", label: "Vertical 1080×1920", w: 1080, h: 1920 },
  // Desktop wallpaper
  { group: "Desktop wallpaper", id: "hd", label: "1366×768", w: 1366, h: 768 },
  { group: "Desktop wallpaper", id: "wxga", label: "1920×1200", w: 1920, h: 1200 },
  { group: "Desktop wallpaper", id: "1440p", label: "2560×1600", w: 2560, h: 1600 },
  { group: "Desktop wallpaper", id: "ultrawide", label: "3440×1440", w: 3440, h: 1440 },
  { group: "Desktop wallpaper", id: "5k", label: "5120×1440", w: 5120, h: 1440 },
  // Phone wallpaper
  { group: "Phone wallpaper", id: "fhd-plus", label: "FHD+ 1080×2400", w: 1080, h: 2400 },
  { group: "Phone wallpaper", id: "qhd-plus", label: "QHD+ 1440×3200", w: 1440, h: 3200 },
  { group: "Phone wallpaper", id: "iphone-pro", label: "iPhone Pro 1179×2556", w: 1179, h: 2556 },
  { group: "Phone wallpaper", id: "iphone-pro-max", label: "iPhone Pro Max 1290×2796", w: 1290, h: 2796 },
  { group: "Phone wallpaper", id: "samsung-s", label: "Samsung S 1080×2340", w: 1080, h: 2340 },
  // Instagram
  { group: "Instagram", id: "ig-portrait", label: "Portrait 1080×1350", w: 1080, h: 1350 },
  { group: "Instagram", id: "ig-square", label: "Square 1080×1080", w: 1080, h: 1080 },
  { group: "Instagram", id: "ig-story", label: "Story/Reel 1080×1920", w: 1080, h: 1920 },
  // YouTube
  { group: "YouTube", id: "yt-thumb", label: "Thumbnail 1280×720", w: 1280, h: 720 },
  { group: "YouTube", id: "yt-thumb-4k", label: "Thumbnail 4K 3840×2160", w: 3840, h: 2160 },
  { group: "YouTube", id: "yt-banner", label: "Banner 2048×1152", w: 2048, h: 1152 },
  { group: "YouTube", id: "yt-icon", label: "Icon 800×800", w: 800, h: 800 },
  // Link preview
  { group: "Link preview", id: "og", label: "OG 1200×630", w: 1200, h: 630 },
  { group: "Link preview", id: "linkedin", label: "LinkedIn 1200×627", w: 1200, h: 627 },
  // Avatar
  { group: "Avatar", id: "avatar-400", label: "400×400", w: 400, h: 400 },
  { group: "Avatar", id: "avatar-800", label: "800×800", w: 800, h: 800 },
  // Logo / icon
  { group: "Logo / icon", id: "favicon-32", label: "Favicon 32", w: 32, h: 32 },
  { group: "Logo / icon", id: "favicon-64", label: "Favicon 64", w: 64, h: 64 },
  { group: "Logo / icon", id: "apple-touch", label: "Apple Touch 180", w: 180, h: 180 },
  { group: "Logo / icon", id: "pwa-192", label: "PWA 192", w: 192, h: 192 },
  { group: "Logo / icon", id: "pwa-512", label: "PWA 512", w: 512, h: 512 },
  { group: "Logo / icon", id: "app-icon", label: "App Icon 1024", w: 1024, h: 1024 },
  { group: "Logo / icon", id: "logo-1000", label: "Logo 1000×1000", w: 1000, h: 1000 },
  // Print
  { group: "Print", id: "a4-150", label: "A4 @150dpi 1240×1754", w: 1240, h: 1754 },
  { group: "Print", id: "a4-300", label: "A4 @300dpi 2480×3508", w: 2480, h: 3508 },
  // Original
  { group: "Original", id: "original", label: "Original", w: null, h: null },
  // Custom
  { group: "Custom", id: "custom", label: "Custom…", w: null, h: null }
];

function computeOutputSize(sourceW, sourceH, preset, customW, customH, fit) {
  if (preset === "original") return { w: sourceW, h: sourceH };
  const p = SIZE_PRESETS.find(p => p.id === preset);
  if (!p || (p.w === null && preset !== "custom")) return { w: sourceW, h: sourceH };
  let w = preset === "custom" ? customW : p.w;
  let h = preset === "custom" ? customH : p.h;
  w = Math.min(w, 8192); h = Math.min(h, 8192);
  return { w, h };
}

const DITHER_KERNELS = {
  "floyd-steinberg": [
    [0, 0, 7/16],
    [3/16, 5/16, 1/16]
  ],
  "atkinson": [
    [0, 0, 1/8, 1/8],
    [1/8, 1/8, 1/8, 0],
    [0, 1/8, 0, 0]
  ],
  "bayer2": [
    [0, 2],
    [3, 1]
  ].map(row => row.map(v => v / 4)),
  "bayer4": [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5]
  ].map(row => row.map(v => v / 16)),
  "bayer8": [
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21]
  ].map(row => row.map(v => v / 64)),
  "sierra": [
    [0, 0, 0, 5/32, 3/32],
    [2/32, 4/32, 5/32, 4/32, 2/32],
    [0, 2/32, 3/32, 2/32, 0]
  ],
  "stucki": [
    [0, 0, 0, 8/42, 4/42],
    [2/42, 4/42, 8/42, 4/42, 2/42],
    [1/42, 2/42, 4/42, 2/42, 1/42]
  ],
  "burkes": [
    [0, 0, 0, 8/32, 4/32],
    [2/32, 4/32, 8/32, 4/32, 2/32]
  ],
  "jarvis-judice-ninke": [
    [0, 0, 0, 7/48, 5/48],
    [3/48, 5/48, 7/48, 5/48, 3/48],
    [1/48, 3/48, 5/48, 3/48, 1/48]
  ]
};

function renderDither(sourceCanvas, destCtx, destW, destH, opts) {
  const { ditherKernel, colorDepth, usePalette, transparentBg, bgColor, colorMode, palette } = opts;
  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width = destW;
  tmpCanvas.height = destH;
  const tmpCtx = tmpCanvas.getContext("2d", { willReadFrequently: true });
  tmpCtx.drawImage(sourceCanvas, 0, 0, destW, destH);
  if (!opts.preApplied) applyAdjustments(tmpCtx, destW, destH, opts.adj);
  const imgData = tmpCtx.getImageData(0, 0, destW, destH);
  const data = imgData.data;

  let workData;
  if (ditherKernel === "halftone") {
    workData = halftoneDither(data, destW, destH, colorDepth, opts);
  } else if (ditherKernel === "threshold") {
    workData = thresholdDither(data, destW, destH, colorDepth, opts);
  } else if (ditherKernel === "blue-noise") {
    workData = blueNoiseDither(data, destW, destH, colorDepth, opts);
  } else if (ditherKernel === "random") {
    workData = randomDither(data, destW, destH, colorDepth, opts);
  } else if (ditherKernel.startsWith("bayer")) {
    workData = orderedDither(data, destW, destH, DITHER_KERNELS[ditherKernel], colorDepth, opts);
  } else {
    workData = errorDiffusionDither(data, destW, destH, DITHER_KERNELS[ditherKernel], colorDepth, opts);
  }

  destCtx.clearRect(0, 0, destW, destH);
  if (!transparentBg) {
    destCtx.fillStyle = bgColor;
    destCtx.fillRect(0, 0, destW, destH);
  }

  const outData = destCtx.createImageData(destW, destH);
  const out = outData.data;

  if (colorMode === "mono") {
    for (let i = 0, j = 0; i < workData.length; i++, j += 4) {
      const v = workData[i];
      out[j] = out[j+1] = out[j+2] = v;
      out[j+3] = 255;
    }
  } else if (colorMode === "palette" && usePalette && palette.length) {
    for (let i = 0, j = 0; i < workData.length; i += 3, j += 4) {
      const r = workData[i], g = workData[i+1], b = workData[i+2];
      const nearest = nearestPaletteColor(r, g, b, palette);
      const m = nearest.match(/rgb\((\d+),(\d+),(\d+)\)/);
      if (m) {
        out[j] = +m[1]; out[j+1] = +m[2]; out[j+2] = +m[3];
      } else {
        out[j] = r; out[j+1] = g; out[j+2] = b;
      }
      out[j+3] = 255;
    }
  } else {
    for (let i = 0, j = 0; i < workData.length; i += 3, j += 4) {
      out[j] = workData[i];
      out[j+1] = workData[i+1];
      out[j+2] = workData[i+2];
      out[j+3] = 255;
    }
  }
  destCtx.putImageData(outData, 0, 0);
}

function errorDiffusionDither(data, w, h, kernel, colorDepth, opts) {
  const levels = colorDepth;
  const step = 255 / (levels - 1);
  const work = new Float32Array(data.length);
  for (let i = 0; i < data.length; i += 4) {
    work[i] = data[i];
    work[i+1] = data[i+1];
    work[i+2] = data[i+2];
  }
  const kh = kernel.length;
  const kw = kernel[0].length;
  const kcy = Math.floor(kh / 2);
  const kcx = Math.floor(kw / 2);
  const serpentine = opts.ditherSerpentine !== false;
  for (let y = 0; y < h; y++) {
    const leftToRight = !serpentine || y % 2 === 0;
    const xStart = leftToRight ? 0 : w - 1;
    const xEnd = leftToRight ? w : -1;
    const xStep = leftToRight ? 1 : -1;
    for (let x = xStart; x !== xEnd; x += xStep) {
      const idx = (y * w + x) * 4;
      for (let c = 0; c < 3; c++) {
        const oldVal = work[idx + c];
        const newVal = Math.round(oldVal / step) * step;
        const err = oldVal - newVal;
        work[idx + c] = newVal;
        for (let ky = 0; ky < kh; ky++) {
          for (let kx = 0; kx < kw; kx++) {
            const weight = kernel[ky][kx];
            if (!weight) continue;
            const nx = x + kx - kcx;
            const ny = y + ky - kcy;
            if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
              const nidx = (ny * w + nx) * 4 + c;
              work[nidx] += err * weight;
            }
          }
        }
      }
    }
  }
  const result = new Uint8ClampedArray(w * h * 3);
  for (let i = 0, j = 0; i < work.length; i += 4, j += 3) {
    result[j] = Math.max(0, Math.min(255, work[i]));
    result[j+1] = Math.max(0, Math.min(255, work[i+1]));
    result[j+2] = Math.max(0, Math.min(255, work[i+2]));
  }
  return result;
}

function orderedDither(data, w, h, matrix, colorDepth, opts) {
  const levels = colorDepth;
  const step = 255 / (levels - 1);
  const ms = matrix.length;
  const result = new Uint8ClampedArray(w * h * 3);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const idx = (y * w + x) * 4;
      const threshold = matrix[y % ms][x % ms];
      for (let c = 0; c < 3; c++) {
        const val = data[idx + c];
        const quantized = Math.round(val / step) * step;
        const adjusted = val + (threshold - 0.5) * step;
        const final = Math.round(adjusted / step) * step;
        result[(y * w + x) * 3 + c] = Math.max(0, Math.min(255, final));
      }
    }
  }
  return result;
}

function halftoneDither(data, w, h, colorDepth, opts) {
  const levels = colorDepth;
  const step = 255 / (levels - 1);
  const dotSize = Math.max(2, Math.floor(8 / levels * 4));
  const result = new Uint8ClampedArray(w * h * 3);
  for (let y = 0; y < h; y += dotSize) {
    for (let x = 0; x < w; x += dotSize) {
      let r = 0, g = 0, b = 0, count = 0;
      for (let dy = 0; dy < dotSize && y + dy < h; dy++) {
        for (let dx = 0; dx < dotSize && x + dx < w; dx++) {
          const idx = ((y + dy) * w + (x + dx)) * 4;
          r += data[idx]; g += data[idx+1]; b += data[idx+2];
          count++;
        }
      }
      if (!count) continue;
      r = Math.round(r / count); g = Math.round(g / count); b = Math.round(b / count);
      const luma = 0.2126*r + 0.7152*g + 0.0722*b;
      const quantized = Math.round(luma / step) * step;
      const nr = Math.round(r * quantized / (luma || 1));
      const ng = Math.round(g * quantized / (luma || 1));
      const nb = Math.round(b * quantized / (luma || 1));
      for (let dy = 0; dy < dotSize && y + dy < h; dy++) {
        for (let dx = 0; dx < dotSize && x + dx < w; dx++) {
          const idx = ((y + dy) * w + (x + dx)) * 3;
          result[idx] = Math.max(0, Math.min(255, nr));
          result[idx+1] = Math.max(0, Math.min(255, ng));
          result[idx+2] = Math.max(0, Math.min(255, nb));
        }
      }
    }
  }
  return result;
}

function thresholdDither(data, w, h, colorDepth, opts) {
  const levels = colorDepth;
  const step = 255 / (levels - 1);
  const result = new Uint8ClampedArray(w * h * 3);
  for (let i = 0, j = 0; i < data.length; i += 4, j += 3) {
    for (let c = 0; c < 3; c++) {
      const val = data[i + c];
      result[j + c] = Math.round(val / step) * step;
    }
  }
  return result;
}

function blueNoiseDither(data, w, h, colorDepth, opts) {
  const levels = colorDepth;
  const step = 255 / (levels - 1);
  const result = new Uint8ClampedArray(w * h * 3);
  const patternSize = 64;
  const pattern = new Uint8Array(patternSize * patternSize);
  for (let i = 0; i < pattern.length; i++) pattern[i] = Math.random() * 255;
  
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const idx = (y * w + x) * 4;
      const px = x % patternSize, py = y % patternSize;
      const threshold = pattern[py * patternSize + px] / 255;
      for (let c = 0; c < 3; c++) {
        const val = data[idx + c];
        const quantized = Math.round(val / step) * step;
        const adjusted = val + (threshold - 0.5) * step;
        const final = Math.round(adjusted / step) * step;
        result[(y * w + x) * 3 + c] = Math.max(0, Math.min(255, final));
      }
    }
  }
  return result;
}

function randomDither(data, w, h, colorDepth, opts) {
  const levels = colorDepth;
  const step = 255 / (levels - 1);
  const result = new Uint8ClampedArray(w * h * 3);
  for (let i = 0, j = 0; i < data.length; i += 4, j += 3) {
    for (let c = 0; c < 3; c++) {
      const val = data[i + c];
      const threshold = Math.random();
      const quantized = Math.round(val / step) * step;
      const adjusted = val + (threshold - 0.5) * step;
      const final = Math.round(adjusted / step) * step;
      result[j + c] = Math.max(0, Math.min(255, final));
    }
  }
  return result;
}

function renderToCanvasLegacy(source, opts, destW, destH) {
  const canvas = document.createElement("canvas");
  canvas.width = destW; canvas.height = destH;
  const ctx = canvas.getContext("2d");
  if (opts.mode === "script") {
    renderScript(source, ctx, destW, destH, opts);
  } else if (opts.mode === "dither") {
    renderDither(source, ctx, destW, destH, opts);
  }
  return canvas;
}