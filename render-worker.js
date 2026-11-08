const WORKER_MIN = /\.min\.js(\?.*)?$/.test(self.location.pathname + self.location.search);
const WORKER_ENGINE = WORKER_MIN ? "./engine.min.js" : "./engine.js";
const WORKER_EFFECTS = WORKER_MIN ? "./effects.min.js" : "./effects.js";

importScripts(WORKER_ENGINE, WORKER_EFFECTS);

let workerSource = null;
let workerSourceId = 0;
let workerReady = false;

const WORKER_FONT_URL = new URL("./assets/fonts/JetBrainsMono-latin.woff2", self.location.href).href;

function workerLoadFonts() {
  if (typeof FontFace === "undefined" || !self.fonts || !self.fonts.add) {
    return Promise.reject(new Error("worker fonts unavailable"));
  }
  const faces = ["400", "700"].map(weight => {
    const face = new FontFace("JetBrains Mono", `url(${WORKER_FONT_URL})`, { weight });
    return face.load().then(loaded => { self.fonts.add(loaded); return loaded; });
  });
  return Promise.all(faces).then(() => undefined);
}

function workerRender(d) {
  const source = workerSource;
  if (!source || d.sourceId !== workerSourceId) {
    return { error: "no source" };
  }
  const opts = d.opts || {};
  const w = Math.max(1, Math.round(d.w));
  const h = Math.max(1, Math.round(d.h));
  const base = prepareBase(source, w, h, opts, null);
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (opts.mode === "script") renderScript(base, ctx, w, h, { ...opts, preApplied: true });
  else if (opts.mode === "dither") renderDither(base, ctx, w, h, { ...opts, preApplied: true });
  else ctx.drawImage(base, 0, 0, w, h);
  return { bitmap: canvas.transferToImageBitmap() };
}

self.addEventListener("message", event => {
  const d = event.data || {};
  if (d.type === "source") {
    if (workerSource && typeof workerSource.close === "function") workerSource.close();
    workerSource = d.bitmap || null;
    workerSourceId = d.id;
    return;
  }
  if (d.type !== "render" || !workerReady) return;
  const started = performance.now();
  try {
    const result = workerRender(d);
    if (result.error) {
      self.postMessage({ type: "error", job: d.job, message: result.error });
      return;
    }
    const ms = +(performance.now() - started).toFixed(1);
    self.postMessage({ type: "result", job: d.job, kind: d.kind, ms, bitmap: result.bitmap }, [result.bitmap]);
  } catch (err) {
    self.postMessage({ type: "error", job: d.job, message: String((err && err.stack) || err) });
  }
});

workerLoadFonts()
  .then(() => {
    workerReady = true;
    self.postMessage({ type: "ready" });
  })
  .catch(err => {
    self.postMessage({ type: "boot-error", message: String((err && err.stack) || err) });
  });
