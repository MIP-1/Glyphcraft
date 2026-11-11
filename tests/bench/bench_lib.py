#!/usr/bin/env python3
"""Shared harness for the P2-3 baseline and golden checks.

Rules copied from the P2-1 compare harness: real page, one continuous in-page
gesture where a gesture is measured, 60-frame warm-up discarded, forced GC,
settle, median and p95, five windows, paired runs in the same browser session.

The render sampler deliberately calls the app's own `prepareBase` and
`renderToContext` on an offscreen canvas. That is the same code path the
preview uses, without asking the compositor to paint, so the number is app
work rather than headless raster noise.
"""
from __future__ import annotations

import functools
import json
import statistics
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_1080 = Path("/tmp/glyphcraft_p2_3_1920x1080.png")
FIXTURE_4K = Path("/tmp/glyphcraft_p2_3_3840x2160.png")
VIDEO_1080 = Path("/tmp/glyphcraft_p2_3_1920x1080.webm")
VIDEO_4K = Path("/tmp/glyphcraft_p2_3_3840x2160.webm")
VIDEO_EXPORT = Path("/tmp/glyphcraft_p2_3_export_1280x720.webm")
DOWNLOAD_DIR = Path("/tmp/glyphcraft_p2_3_downloads")

SEED = 0x5EED1234
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen"]
STACK_ORDER = ["halftone", "crt", "pixelate", "bloom", "vignette", "posterize",
               "edges", "sketch", "emboss", "blur", "thermal", "retro"]

INIT_JS = r"""
(() => {
  let s = %d;
  const next = () => {
    s |= 0; s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  Math.random = next;
  window.__benchSeedReset = () => { s = %d; };
  window.__benchLong = [];
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__benchLong.push(+e.duration.toFixed(1));
    }).observe({ entryTypes: ["longtask"] });
  } catch (err) {}
})();
""" % (SEED, SEED)

BENCH_JS = r"""
(() => {
  const midParams = (id) => {
    const def = EFFECTS.find(e => e.id === id);
    const out = effectDefaults(id);
    if (!def) return out;
    for (const p of def.params) {
      if (p.type === "color") continue;
      if (p.type === "select") {
        const opts = p.options || [];
        if (opts.length) out[p.key] = opts[Math.floor(opts.length / 2)][0];
        continue;
      }
      const step = p.step > 0 ? p.step : 1;
      out[p.key] = Math.max(p.min, Math.min(p.max,
        p.min + Math.round(((p.max - p.min) / 2) / step) * step));
    }
    return out;
  };
  window.__benchMidParams = midParams;
  window.__benchApply = function (cfg) {
    const base = defaultOpts();
    base.mode = cfg.mode;
    base.outputPreset = "original";
    base.adj = { ...DEFAULT_ADJ };
    if (cfg.adj) Object.assign(base.adj, cfg.adj);
    base.autoLevels = true;
    base.usePalette = true;
    if (cfg.colorMode) base.colorMode = cfg.colorMode;
    if (cfg.ditherKernel) base.ditherKernel = cfg.ditherKernel;
    if (cfg.palette) base.palette = cfg.palette;
    base.effects = base.effects.map((fx) => ({
      id: fx.id,
      enabled: (cfg.effects || []).includes(fx.id),
      params: { ...fx.params, ...(cfg.params && cfg.params[fx.id] ? cfg.params[fx.id]
        : (cfg.effects || []).includes(fx.id) ? midParams(fx.id) : {}) },
    }));
    state.opts = base;
    rebuildRamp();
    if (cfg.palette) {
      state.opts.palette = cfg.palette;
      state.paletteColors = currentPalette();
    }
    state.cacheDisabled = true;
    state.lastRenderKey = "";
    state.renderCache = null;
    state.composite = null;
    clearStageCache();
    if (typeof fxPoolClear === "function") fxPoolClear();
  };
  window.__benchHash = function (canvas) {
    const d = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    let h = 2166136261;
    for (let i = 0; i < d.length; i += 4) {
      h ^= d[i]; h = Math.imul(h, 16777619);
      h ^= d[i + 1]; h = Math.imul(h, 16777619);
      h ^= d[i + 2]; h = Math.imul(h, 16777619);
      h ^= d[i + 3]; h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  };
  window.__benchRender = function (cfg) {
    if (window.__benchSeedReset) window.__benchSeedReset();
    window.__benchApply(cfg);
    const full = computeOutputSize(state.sourceW, state.sourceH, "original", 1920, 1080, "contain");
    const pv = cfg.full ? full : previewSize(full);
    const opts = renderOpts();
    const canvas = document.createElement("canvas");
    canvas.width = pv.w; canvas.height = pv.h;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const t0 = performance.now();
    const base = prepareBase(state.source, pv.w, pv.h, opts, null);
    renderToContext(base, ctx, pv.w, pv.h, opts);
    const ms = performance.now() - t0;
    const hash = window.__benchHash(canvas);
    canvas.width = 0; canvas.height = 0;
    return { ms: +ms.toFixed(2), w: pv.w, h: pv.h, hash };
  };
})();
"""


def fixtures() -> None:
    from PIL import Image
    import numpy as np

    def make(path: Path, w: int, h: int, seed: int) -> None:
        if path.exists() and path.stat().st_size:
            return
        x = np.arange(w, dtype=np.uint32)[None, :]
        y = np.arange(h, dtype=np.uint32)[:, None]
        arr = np.empty((h, w, 3), dtype=np.uint8)
        arr[..., 0] = (x * 255 // max(1, w - 1) + seed * 31) % 256
        arr[..., 1] = (y * 255 // max(1, h - 1) + seed * 17) % 256
        arr[..., 2] = ((x + y) * 255 // max(1, w + h - 2) + seed * 7) % 256
        Image.fromarray(arr, "RGB").save(path)

    make(FIXTURE_1080, 1920, 1080, 3)
    make(FIXTURE_4K, 3840, 2160, 7)


def videos() -> None:
    import subprocess
    if not VIDEO_1080.exists() or not VIDEO_1080.stat().st_size:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=1920x1080:rate=24:duration=2",
                        "-c:v", "libvpx-vp9", "-b:v", "2M", "-an",
                        str(VIDEO_1080)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not VIDEO_4K.exists() or not VIDEO_4K.stat().st_size:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=3840x2160:rate=12:duration=1.5",
                        "-c:v", "libvpx-vp9", "-b:v", "4M", "-an",
                        str(VIDEO_4K)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not VIDEO_EXPORT.exists() or not VIDEO_EXPORT.stat().st_size:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=1280x720:rate=24:duration=1",
                        "-c:v", "libvpx-vp9", "-b:v", "1M", "-an",
                        str(VIDEO_EXPORT)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Server:
    def __enter__(self):
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def new_page(browser, srv, *, worker: bool = True, viewport=(1440, 1000),
             downloads: bool = False):
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                              locale="en-US", reduced_motion="reduce",
                              color_scheme="dark", accept_downloads=downloads)
    ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
    ctx.add_init_script(INIT_JS)
    if not worker:
        ctx.add_init_script("window.__GC_DISABLE_WORKER = true;")
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(srv.url + "/index.html", wait_until="load")
    page.evaluate("() => document.fonts.ready")
    page.add_script_tag(content=BENCH_JS)
    return ctx, page, errors


def load_image(page, path: Path) -> None:
    page.set_input_files("#file-input", str(path))
    page.wait_for_selector(".canvas-area.has-content", timeout=120000)
    page.wait_for_function("() => state.source && state.sourceType === 'image'", timeout=120000)
    page.wait_for_timeout(300)


def load_video(page, path: Path) -> None:
    page.set_input_files("#file-input", str(path))
    page.wait_for_function("() => state.source && state.sourceType === 'video' && state.source.readyState >= 2",
                           timeout=120000)
    page.wait_for_timeout(500)


def cdp_session(page):
    return page.context.new_cdp_session(page)


def gc(cdp) -> None:
    cdp.send("HeapProfiler.collectGarbage")


def js_heap(cdp) -> int:
    cdp.send("HeapProfiler.collectGarbage")
    return cdp.send("Runtime.getHeapUsage")["usedSize"]


def render_case_full(page, cdp, cfg: dict, warm: int = 2) -> dict:
    for _ in range(warm):
        page.evaluate("(c) => window.__benchRender(c)", cfg)
    gc(cdp)
    page.wait_for_timeout(40)
    return page.evaluate("(c) => window.__benchRender(c)", cfg)


def render_case(page, cdp, cfg: dict, warm: int = 2) -> float:
    return render_case_full(page, cdp, cfg, warm=warm)["ms"]


def five_windows(page, cdp, fn, windows: int = 5):
    values = []
    for _ in range(windows):
        values.append(fn())
    values = [v for v in values if v is not None]
    ordered = sorted(values)
    median = statistics.median(ordered) if ordered else None
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else None
    return {"values": [round(v, 2) for v in values],
            "median": round(median, 2) if median is not None else None,
            "p95": round(p95, 2) if p95 is not None else None,
            "windows": len(values)}


def startup(browser, srv, runs: int = 5) -> dict:
    rows = []
    for _ in range(runs):
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  locale="en-US", reduced_motion="reduce",
                                  color_scheme="dark")
        ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
        page = ctx.new_page()
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_function("() => typeof state !== 'undefined' && !!document.getElementById('drop-zone')")
        data = page.evaluate("""() => {
          const nav = performance.getEntriesByType('navigation')[0];
          const paints = Object.fromEntries(performance.getEntriesByType('paint').map(e => [e.name, e.startTime]));
          const resources = performance.getEntriesByType('resource');
          let bytes = 0;
          for (const r of resources) bytes += (r.decodedBodySize || 0);
          return {
            firstPaint: paints['first-paint'] ?? null,
            fcp: paints['first-contentful-paint'] ?? null,
            dcl: nav ? nav.domContentLoadedEventEnd : null,
            load: nav ? nav.loadEventEnd : null,
            appReady: performance.now(),
            bytes,
            requests: resources.length,
          };
        }""")
        rows.append(data)
        ctx.close()
    out = {}
    for key in rows[0]:
        vals = [r[key] for r in rows if r[key] is not None]
        out[key] = round(statistics.median(vals), 2) if vals else None
    out["runs"] = rows
    return out


def effect_catalog(page) -> list[dict]:
    return page.evaluate("() => EFFECTS.map(e => ({id: e.id, name: e.name, params: e.params}))")


def mid_params(page, effect_id: str) -> dict:
    return page.evaluate("(id) => window.__benchMidParams(id)", effect_id)


def golden_cases(page, sources: dict[str, Path]) -> list[dict]:
    catalog = effect_catalog(page)
    cases = []
    for label in ("1080p", "4k"):
        for mode in ("script", "dither", "effects"):
            for fx in catalog:
                params = mid_params(page, fx["id"])
                cases.append({"id": f"{label}-{mode}-{fx['id']}", "source": label,
                              "mode": mode, "effects": [fx["id"]],
                              "params": {fx["id"]: params}})
            for n in (1, 3, 6, 12):
                ids = STACK_ORDER[:n]
                params = {eid: mid_params(page, eid) for eid in ids}
                cases.append({"id": f"{label}-{mode}-stack{n}", "source": label,
                              "mode": mode, "effects": ids, "params": params})
    return cases


def expected_sources() -> dict[str, Path]:
    return {"1080p": FIXTURE_1080, "4k": FIXTURE_4K}


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    with Server() as srv, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx, page, errs = new_page(b, srv)
        fixtures()
        load_image(page, FIXTURE_1080)
        print(page.evaluate("() => window.__benchRender({mode:'script',effects:['halftone']})"))
        print("errors", errs)
        ctx.close()
        b.close()
