#!/usr/bin/env python3
"""L0 measurement harness for the lag and performance round.

Nothing here changes the app. It measures, in real browsers:

  code     file/function sizes, minified/gzip/brotli, script parse+compile
  playback 720p and 1080p x chromium/firefox x 0/2/6 effects, 20 s windows
  stages   one frame split into source copy, effects, readback, compositing
  sharp    backing vs CSS display x DPR at 79/100/112 % zoom
  memory   loads, exports, undo, 5 minutes of uninterrupted playback
  compress static transfer sizes and worker payload shape

usage:
  python tools/l0_measure.py --part code
  python tools/l0_measure.py --part sharp
  python tools/l0_measure.py --part playback --browser chromium
  python tools/l0_measure.py --part stages
  python tools/l0_measure.py --part memory
  python tools/l0_measure.py --part compress
"""
from __future__ import annotations

import argparse
import functools
import gzip
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / os.environ.get("GATE_TASK", "l0")
WORK = Path("/tmp/opencode/glyphcraft_l0")
FIXTURE_IMAGE = Path("/tmp/glyphcraft_gate_fixture.png")
SIZES = {"720p": (1280, 720), "1080p": (1920, 1080)}
LIGHT = ["posterize", "duotone"]
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen", "oil"]

FILES = ["app.js", "engine.js", "effects.js", "reorder.js", "render-worker.js",
         "style.css", "index.html", "vendor/mp4-muxer.js", "vendor/webm-muxer.js"]


# ---------------------------------------------------------------------------
# fixtures and server
# ---------------------------------------------------------------------------

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


def make_fixtures() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for name, (w, h) in SIZES.items():
        path = WORK / f"src-{w}x{h}.webm"
        if path.exists() and path.stat().st_size > 300_000:
            continue
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration=20",
            "-f", "lavfi", "-i", f"mandelbrot=size={w}x{h}:rate=30",
            "-filter_complex", "[0:v][1:v]blend=all_mode=overlay,format=yuv420p",
            "-t", "20", "-c:v", "libvpx-vp9", "-deadline", "realtime",
            "-cpu-used", "8", "-row-mt", "1", "-b:v", "6M", "-an", str(path),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    small = WORK / "src-320x180-2s.webm"
    if not small.exists() or small.stat().st_size < 10_000:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "testsrc2=size=320x180:rate=30:duration=2",
            "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8",
            "-b:v", "400k", "-an", str(small),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not FIXTURE_IMAGE.exists():
        sys.path.insert(0, str(ROOT / "tests" / "gate"))
        import run_gate  # noqa: E402
        run_gate.make_png(FIXTURE_IMAGE, width=900, height=600, seed=0)
    image_1080 = WORK / "image-1920x1080.png"
    if not image_1080.exists():
        from PIL import Image
        Image.open(FIXTURE_IMAGE).convert("RGB").resize((1920, 1080)).save(image_1080)


# ---------------------------------------------------------------------------
# process CPU (Chromium and Firefox): sum utime+stime of new browser pids
# ---------------------------------------------------------------------------

def _browser_pids() -> set[int]:
    pids: set[int] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace").lower()
        except OSError:
            continue
        if ("chrom" in cmd or "firefox" in cmd) and "playwright" in cmd:
            pids.add(int(entry.name))
    return pids


def _cpu_seconds(pids: set[int]) -> float:
    ticks = os.sysconf("SC_CLK_TCK")
    total = 0.0
    for pid in pids:
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().split()
        except OSError:
            continue
        # utime, stime are fields 14 and 15 (1-based)
        total += (int(fields[13]) + int(fields[14])) / ticks
    return total


def _rss_mb(pids: set[int]) -> float:
    total = 0.0
    for pid in pids:
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1]) / 1024
                    break
        except OSError:
            continue
    return total


class CpuWatch:
    def __enter__(self):
        self.pids = _browser_pids()
        self.start = _cpu_seconds(self.pids)
        self.start_rss = _rss_mb(self.pids)
        self.t0 = time.time()
        return self

    def __exit__(self, *a):
        self.pids |= _browser_pids()
        self.wall = time.time() - self.t0
        self.cpu = _cpu_seconds(self.pids) - self.start
        self.rss = _rss_mb(self.pids) - self.start_rss

    def read(self) -> dict:
        return {"wall_s": round(time.time() - self.t0, 3),
                "cpu_s": round(_cpu_seconds(self.pids) - self.start, 3),
                "rss_mb": round(_rss_mb(self.pids) - self.start_rss, 1)}


# ---------------------------------------------------------------------------
# in-page instrumentation
# ---------------------------------------------------------------------------

INIT_JS = r"""
(() => {
  const P = window.__l0 = {
    renders: 0, renderMs: [], renderStarts: [], longtasks: [],
    rvfc: 0, raf: 0, canvases: 0, heap: [],
    urlCreate: 0, urlRevoke: 0, urlLive: 0,
    bitmap: 0, bitmapClose: 0, videoFrame: 0, videoFrameClose: 0,
    getImageData: {n: 0, ms: 0, bytes: 0},
    putImageData: {n: 0, ms: 0},
    drawImage: {n: 0, ms: 0},
    toBlob: {n: 0, ms: 0},
    ltFrom: 0, heapTimer: null,
  };
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (e.startTime >= P.ltFrom) P.longtasks.push(+e.duration.toFixed(1));
      }
    }).observe({entryTypes: ["longtask"]});
  } catch (e) {}
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    return raf((t) => { P.raf++; return cb(t); });
  };
  const rv = HTMLVideoElement.prototype.requestVideoFrameCallback;
  if (rv) {
    HTMLVideoElement.prototype.requestVideoFrameCallback = function (cb) {
      P.rvfc++;
      return rv.call(this, cb);
    };
  }
  const ce = Document.prototype.createElement;
  Document.prototype.createElement = function (tag, ...a) {
    const el = ce.call(this, tag, ...a);
    if (String(tag).toLowerCase() === "canvas") P.canvases++;
    return el;
  };
  const uc = URL.createObjectURL.bind(URL);
  const ur = URL.revokeObjectURL.bind(URL);
  URL.createObjectURL = function (b) { P.urlCreate++; P.urlLive++; return uc(b); };
  URL.revokeObjectURL = function (u) { P.urlRevoke++; P.urlLive--; return ur(u); };
  const cib = window.createImageBitmap;
  if (cib) {
    window.createImageBitmap = function (...a) {
      P.bitmap++;
      return cib.apply(this, a).then((b) => {
        const close = b.close.bind(b);
        b.close = function () { P.bitmapClose++; return close(); };
        return b;
      });
    };
  }
  if (window.VideoFrame) {
    const vf = VideoFrame;
    window.VideoFrame = function (...a) { P.videoFrame++; return new vf(...a); };
    window.VideoFrame.prototype = vf.prototype;
  }
  window.__l0Reset = function () {
    P.renders = 0; P.renderMs = []; P.renderStarts = []; P.longtasks = [];
    P.rvfc = 0; P.raf = 0; P.canvases = 0;
    P.getImageData = {n: 0, ms: 0, bytes: 0};
    P.putImageData = {n: 0, ms: 0}; P.drawImage = {n: 0, ms: 0};
    P.ltFrom = performance.now();
  };
  window.__l0HeapSample = function () {
    if (performance.memory) P.heap.push(Math.round(performance.memory.usedJSHeapSize / 1e3));
  };
  window.__l0HeapStart = function () {
    if (P.heapTimer) clearInterval(P.heapTimer);
    P.heap = []; window.__l0HeapSample();
    P.heapTimer = setInterval(window.__l0HeapSample, 1000);
  };
  window.__l0HeapStop = function () {
    if (P.heapTimer) clearInterval(P.heapTimer);
    P.heapTimer = null; window.__l0HeapSample();
  };
})();
"""

# Counting only. The detailed timing wrappers below add two performance.now()
# calls per canvas operation, which is measurable in blur/oil. Playback windows
# must not carry that cost, so they use this init and only the render timer.
LIGHT_INIT_JS = r"""
(() => {
  const P = window.__l0 = {
    renders: 0, renderMs: [], renderStarts: [], longtasks: [],
    rvfc: 0, raf: 0, canvases: 0, heap: [], ltFrom: 0, heapTimer: null,
    urlCreate: 0, urlRevoke: 0, urlLive: 0,
    bitmap: 0, bitmapClose: 0, videoFrame: 0, videoFrameClose: 0,
    getImageData: {n: 0, ms: 0, bytes: 0},
    putImageData: {n: 0, ms: 0}, drawImage: {n: 0, ms: 0},
  };
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (e.startTime >= P.ltFrom) P.longtasks.push(+e.duration.toFixed(1));
      }
    }).observe({entryTypes: ["longtask"]});
  } catch (e) {}
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    return raf((t) => { P.raf++; return cb(t); });
  };
  const rv = HTMLVideoElement.prototype.requestVideoFrameCallback;
  if (rv) {
    HTMLVideoElement.prototype.requestVideoFrameCallback = function (cb) {
      P.rvfc++;
      return rv.call(this, cb);
    };
  }
  const ce = Document.prototype.createElement;
  Document.prototype.createElement = function (tag, ...a) {
    const el = ce.call(this, tag, ...a);
    if (String(tag).toLowerCase() === "canvas") P.canvases++;
    return el;
  };
  const uc = URL.createObjectURL.bind(URL);
  const ur = URL.revokeObjectURL.bind(URL);
  URL.createObjectURL = function (b) { P.urlCreate++; P.urlLive++; return uc(b); };
  URL.revokeObjectURL = function (u) { P.urlRevoke++; P.urlLive--; return ur(u); };
  const cib = window.createImageBitmap;
  if (cib) {
    window.createImageBitmap = function (...a) {
      P.bitmap++;
      return cib.apply(this, a).then((b) => {
        const close = b.close.bind(b);
        b.close = function () { P.bitmapClose++; return close(); };
        return b;
      });
    };
  }
  window.__l0Reset = function () {
    P.renders = 0; P.renderMs = []; P.renderStarts = []; P.longtasks = [];
    P.rvfc = 0; P.raf = 0; P.canvases = 0;
    P.getImageData = {n: 0, ms: 0, bytes: 0};
    P.putImageData = {n: 0, ms: 0}; P.drawImage = {n: 0, ms: 0};
    P.ltFrom = performance.now();
  };
  window.__l0HeapSample = function () {
    if (performance.memory) P.heap.push(Math.round(performance.memory.usedJSHeapSize / 1e3));
  };
  window.__l0HeapStart = function () {
    if (P.heapTimer) clearInterval(P.heapTimer);
    P.heap = []; window.__l0HeapSample();
    P.heapTimer = setInterval(window.__l0HeapSample, 1000);
  };
  window.__l0HeapStop = function () {
    if (P.heapTimer) clearInterval(P.heapTimer);
    P.heapTimer = null; window.__l0HeapSample();
  };
})();
"""

PATCH_RENDER = r"""
() => {
  const r = window.render;
  window.render = function (...a) {
    const t = performance.now();
    window.__l0.renderStarts.push(+t.toFixed(2));
    try { return r.apply(this, a); }
    finally {
      window.__l0.renders++;
      window.__l0.renderMs.push(+(performance.now() - t).toFixed(2));
    }
  };
}
"""

STAGE_HOOKS = r"""
() => {
  window.__stage = {};
  window.__stageReset = function () { window.__stage = {}; };
  const bump = (key, d) => {
    const s = window.__stage[key] || (window.__stage[key] = {n: 0, ms: 0});
    s.n++; s.ms += d;
  };
  const wrap = (name, key) => {
    const f = window[name];
    if (typeof f !== "function" || f.__l0wrapped) return;
    const w = function (...a) {
      const t = performance.now();
      try { return f.apply(this, a); }
      finally { bump(key, performance.now() - t); }
    };
    w.__l0wrapped = true;
    window[name] = w;
  };
  wrap("prepareBase", "prepareBase");
  wrap("applyEffects", "applyEffects");
  wrap("applyAdjustments", "applyAdjustments");
  wrap("renderToContext", "renderToContext");
  wrap("renderScript", "renderScript");
  wrap("renderDither", "renderDither");
  wrap("autoLevels", "autoLevels");
  wrap("updateStatus", "updateStatus");
  wrap("applyTransform", "applyTransform");
  wrap("applyZoomUI", "applyZoomUI");
  wrap("updateCompareUI", "updateCompareUI");
  // EFFECT_RUNNERS is a top-level const: a lexical global binding, not a
  // window property. Read it by name from this evaluate scope.
  if (typeof EFFECT_RUNNERS !== "undefined" && EFFECT_RUNNERS) {
    for (const id of Object.keys(EFFECT_RUNNERS)) {
      const f = EFFECT_RUNNERS[id];
      if (typeof f !== "function" || f.__l0wrapped) continue;
      const w = function (...a) {
        const t = performance.now();
        try { return f.apply(this, a); }
        finally { bump("fx:" + id, performance.now() - t); }
      };
      w.__l0wrapped = true;
      EFFECT_RUNNERS[id] = w;
    }
  }
  window.__probeRender = function (times) {
    const out = {render: [], stage: {}};
    if (window.__l0StageReset) window.__l0StageReset();
    for (let i = 0; i < times; i++) {
      window.__stageReset();
      const t = performance.now();
      render();
      out.render.push(+(performance.now() - t).toFixed(2));
      for (const [k, v] of Object.entries(window.__stage)) {
        const s = out.stage[k] || (out.stage[k] = {n: 0, ms: 0});
        s.n += v.n; s.ms += v.ms;
      }
    }
    out.canvasOps = {};
    if (window.__l0StageRead) {
      const ops = window.__l0StageRead();
      for (const [k, v] of Object.entries(ops)) {
        out.canvasOps[k] = {n: +(v.n / times).toFixed(1),
                            ms: +(v.ms / times).toFixed(2)};
      }
    }
    for (const [k, v] of Object.entries(out.stage)) {
      v.ms = +(v.ms / times).toFixed(2);
      v.n = +(v.n / times).toFixed(2);
    }
    out.renderAvg = +(out.render.reduce((a, b) => a + b, 0) / times).toFixed(2);
    return out;
  };
}
"""

DETAIL_JS = r"""
() => {
  const proto = CanvasRenderingContext2D.prototype;
  window.__l0Stage = {
    getImageData: {n: 0, ms: 0}, putImageData: {n: 0, ms: 0},
    drawImage: {n: 0, ms: 0}, fillText: {n: 0, ms: 0},
  };
  const gid = proto.getImageData;
  proto.getImageData = function (x, y, w, h, ...r) {
    const t = performance.now();
    try { return gid.call(this, x, y, w, h, ...r); }
    finally {
      window.__l0Stage.getImageData.n++;
      window.__l0Stage.getImageData.ms += performance.now() - t;
    }
  };
  const pid = proto.putImageData;
  proto.putImageData = function (...a) {
    const t = performance.now();
    try { return pid.apply(this, a); }
    finally {
      window.__l0Stage.putImageData.n++;
      window.__l0Stage.putImageData.ms += performance.now() - t;
    }
  };
  const di = proto.drawImage;
  proto.drawImage = function (...a) {
    const t = performance.now();
    try { return di.apply(this, a); }
    finally {
      window.__l0Stage.drawImage.n++;
      window.__l0Stage.drawImage.ms += performance.now() - t;
    }
  };
  const ft = proto.fillText;
  proto.fillText = function (...a) {
    const t = performance.now();
    try { return ft.apply(this, a); }
    finally {
      window.__l0Stage.fillText.n++;
      window.__l0Stage.fillText.ms += performance.now() - t;
    }
  };
  window.__l0StageReset = function () {
    for (const v of Object.values(window.__l0Stage)) { v.n = 0; v.ms = 0; }
  };
  window.__l0StageRead = function () {
    const out = {};
    for (const [k, v] of Object.entries(window.__l0Stage)) {
      out[k] = {n: v.n, ms: +v.ms.toFixed(2)};
    }
    return out;
  };
}
"""

VALUE_JS = r"""() => {
  const P = window.__l0;
  const c = document.getElementById('canvas');
  const status = document.querySelector('.status-bar');
  const full = computeOutputSize(state.sourceW, state.sourceH,
    state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight,
    state.opts.outputFit);
  const pv = previewSize(full);
  return {
    renders: P.renders, renderMs: P.renderMs.slice(),
    renderStarts: P.renderStarts.slice(), longtasks: P.longtasks.slice(),
    rvfc: P.rvfc, raf: P.raf, canvases: P.canvases,
    heap: P.heap.slice(),
    getImageData: {n: P.getImageData.n, ms: +P.getImageData.ms.toFixed(1),
                   bytes: P.getImageData.bytes},
    putImageData: {n: P.putImageData.n, ms: +P.putImageData.ms.toFixed(1)},
    drawImage: {n: P.drawImage.n, ms: +P.drawImage.ms.toFixed(1)},
    urlCreate: P.urlCreate, urlRevoke: P.urlRevoke, urlLive: P.urlLive,
    bitmap: P.bitmap, bitmapClose: P.bitmapClose,
    videoFrame: P.videoFrame, videoFrameClose: P.videoFrameClose,
    videoTime: state.video ? +state.video.currentTime.toFixed(3) : null,
    paused: state.video ? state.video.paused : null,
    backing: c ? {w: c.width, h: c.height} : null,
    preview: {w: pv.w, h: pv.h, scale: +pv.scale.toFixed(4)},
    full, source: {w: state.sourceW, h: state.sourceH, type: state.sourceType},
    status: status ? status.textContent.replace(/\s+/g, ' ').trim() : null,
    playing: videoIsPlaying(),
  };
}
"""


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round((len(xs) - 1) * p)))], 2)


def summarize_window(raw: dict, wall_s: float, cpu: dict | None) -> dict:
    render_ms = raw["renderMs"]
    starts = raw["renderStarts"]
    intervals = [round(b - a, 2) for a, b in zip(starts, starts[1:])]
    lt = raw["longtasks"]
    heap = raw["heap"]
    out = {
        "renders": raw["renders"],
        "renders_per_s": round(raw["renders"] / wall_s, 2),
        "render_p50": pct(render_ms, 0.50),
        "render_p95": pct(render_ms, 0.95),
        "render_max": round(max(render_ms), 2) if render_ms else None,
        "interval_p50": pct(intervals, 0.50),
        "interval_p95": pct(intervals, 0.95),
        "longtasks": len(lt),
        "longtask_ms": round(sum(lt), 1),
        "longest_ms": round(max(lt + [0]), 1),
        "longtasks_over_50": sum(1 for d in lt if d > 50),
        "rvfc": raw["rvfc"],
        "skipped_rvfc": max(0, raw["rvfc"] - raw["renders"]),
        "raf": raw["raf"],
        "canvases": raw["canvases"],
        "canvas_per_render": round(raw["canvases"] / max(1, raw["renders"]), 3),
        "gid_n": raw["getImageData"]["n"],
        "gid_ms": raw["getImageData"]["ms"],
        "gid_mb": round(raw["getImageData"]["bytes"] / 1e6, 1),
        "pid_n": raw["putImageData"]["n"],
        "pid_ms": raw["putImageData"]["ms"],
        "draw_n": raw["drawImage"]["n"],
        "draw_ms": raw["drawImage"]["ms"],
        "video_time": raw["videoTime"],
        "paused": raw["paused"],
        "backing": raw["backing"],
        "preview": raw["preview"],
        "full": raw["full"],
        "source": raw["source"],
        "status": raw["status"],
        "heap_start_mb": round(heap[0] / 1e3, 2) if heap else None,
        "heap_end_mb": round(heap[-1] / 1e3, 2) if heap else None,
        "heap_max_mb": round(max(heap) / 1e3, 2) if heap else None,
        "heap_samples": len(heap),
        "url_live": raw["urlLive"],
        "bitmaps": [raw["bitmap"], raw["bitmapClose"]],
    }
    if cpu:
        out["cpu_s"] = cpu["cpu_s"]
        out["wall_s"] = cpu["wall_s"]
        out["cpu_cores"] = round(cpu["cpu_s"] / max(0.001, cpu["wall_s"]), 2)
        out["cpu_ms_per_render"] = round(1000 * cpu["cpu_s"] / max(1, raw["renders"]), 1)
        out["rss_delta_mb"] = cpu.get("rss_mb")
    return out


# ---------------------------------------------------------------------------
# page helpers
# ---------------------------------------------------------------------------

def new_page(p, browser_name: str, theme="dark", dpr=1.0, viewport=(1440, 1000),
             light=False):
    browser = getattr(p, browser_name).launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        device_scale_factor=dpr, accept_downloads=True, locale="en-US")
    ctx.add_init_script(
        "try{localStorage.setItem('glyphcraft-theme','%s')}catch(e){}" % theme)
    ctx.add_init_script(LIGHT_INIT_JS if light else INIT_JS)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    page.on("console", lambda m: errors.append("console: " + m.text)
            if m.type == "error" else None)
    return browser, ctx, page, errors


def open_app(page, srv):
    page.goto(srv.url + "/index.html", wait_until="load")
    page.wait_for_timeout(400)
    page.evaluate(PATCH_RENDER)


def load_video(page, path: Path):
    before = page.evaluate("() => state.sourceId")
    page.evaluate("() => { document.getElementById('file-input').value = ''; }")
    page.set_input_files("#file-input", str(path))
    page.wait_for_function("(id) => state.sourceId > id", arg=before, timeout=120000)
    page.wait_for_function(
        "() => state.sourceType === 'video' && state.video && state.video.readyState >= 2",
        timeout=120000)
    page.wait_for_timeout(400)
    page.evaluate("""() => { state.video.pause(); stopVideoLoop();
      state.opts.outputPreset = 'original'; state.opts.outputWidth = 0;
      state.opts.outputHeight = 0; scheduleRender(0); }""")
    page.wait_for_timeout(400)


def load_image(page, path: Path):
    before = page.evaluate("() => state.sourceId")
    page.evaluate("() => { document.getElementById('file-input').value = ''; }")
    page.set_input_files("#file-input", str(path))
    page.wait_for_function("(id) => state.sourceId > id", arg=before, timeout=120000)
    page.wait_for_function("() => state.sourceType === 'image'", timeout=120000)
    page.wait_for_timeout(600)


def set_effects(page, ids):
    page.evaluate("""(ids) => {
      state.opts.effects = state.opts.effects.map(fx => ({
        ...fx, enabled: ids.includes(fx.id),
        params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
      }));
      state.opts.mode = 'script';
      scheduleRender(0);
    }""", ids)
    page.wait_for_timeout(300)


def install_pause_latency(page):
    page.evaluate("""() => {
      window.__l0Pause = null;
      const b = document.getElementById('video-toggle');
      b.addEventListener('pointerdown', () => {
        const t0 = performance.now();
        const tick = () => {
          if (state.video && state.video.paused) {
            window.__l0Pause = +(performance.now() - t0).toFixed(1);
          } else { requestAnimationFrame(tick); }
        };
        requestAnimationFrame(tick);
      }, {capture: true, once: true});
    }""")


def measure_pause(page, play_again=True):
    # Wall clock from the driver's click to the paused state. A main thread
    # busy with a 100 ms render delays the event handler, and this includes
    # that delay; the in-page timestamp alone started after the queue drained.
    box = page.locator("#video-toggle").bounding_box()
    t0 = time.time()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    try:
        page.wait_for_function("() => state.video && state.video.paused", timeout=8000)
        value = round((time.time() - t0) * 1000, 1)
    except Exception:  # noqa: BLE001
        value = None
    page.wait_for_timeout(150)
    if play_again:
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(500)
    return value


def install_seek_latency(page):
    page.evaluate("""() => {
      window.__l0Seek = null;
      const s = document.getElementById('video-seek');
      const v = state.video;
      const done = () => { if (window.__l0Seek === null) {
        window.__l0Seek = +(performance.now() - window.__l0SeekT0).toFixed(1); } };
      s.addEventListener('pointerdown', () => {
        window.__l0SeekT0 = performance.now();
        v.addEventListener('seeked', done, {once: true});
      }, {capture: true, once: true});
    }""")


def measure_seek(page, frac=0.72):
    # V3 (the seek bar) is not built yet, so the real control does not exist.
    # Measure the decode+present cost of the seek itself and label it honestly.
    if not page.evaluate("() => !!document.getElementById('video-seek')"):
        return page.evaluate("""async (frac) => {
          const v = state.video;
          const t0 = performance.now();
          const target = Math.max(0, Math.min((v.duration || 20) * frac,
                                              (v.duration || 20) - 0.2));
          await new Promise(r => {
            v.addEventListener('seeked', r, {once: true});
            v.currentTime = target;
            setTimeout(r, 2500);
          });
          return +(performance.now() - t0).toFixed(1);
        }""", frac)
    install_seek_latency(page)
    box = page.locator("#video-seek").bounding_box()
    x = box["x"] + box["width"] * frac
    y = box["y"] + box["height"] / 2
    page.mouse.click(x, y)
    try:
        page.wait_for_function("() => window.__l0Seek !== null", timeout=8000)
        value = page.evaluate("() => window.__l0Seek")
    except Exception:  # noqa: BLE001
        value = None
    page.wait_for_timeout(350)
    return value


def run_window(page, seconds: float, cdp=None) -> dict:
    page.evaluate("() => { window.__l0Reset(); window.__l0HeapStart(); }")
    v0 = page.evaluate("() => (state.video ? state.video.currentTime : null)")
    before = None
    if cdp is not None:
        names = ("TaskDuration", "ScriptDuration", "LayoutDuration",
                 "RecalcStyleDuration")
        m = {r["name"]: r["value"] for r in cdp.send("Performance.getMetrics")["metrics"]}
        before = {n: m.get(n, 0.0) for n in names}
    cpu = CpuWatch().__enter__()
    t0 = time.time()
    time.sleep(seconds)
    wall = time.time() - t0
    cpu.__exit__()
    page.evaluate("() => window.__l0HeapStop()")
    raw = page.evaluate(VALUE_JS)
    out = summarize_window(raw, wall, {"cpu_s": cpu.cpu, "wall_s": wall,
                                       "rss_mb": cpu.rss})
    out["video_start"] = round(v0, 2) if v0 is not None else None
    out["video_advance"] = (round(raw["videoTime"] - v0, 2)
                            if raw["videoTime"] is not None and v0 is not None else None)
    if cdp is not None:
        m = {r["name"]: r["value"] for r in cdp.send("Performance.getMetrics")["metrics"]}
        out["main_thread"] = {
            "task_ms": round((m.get("TaskDuration", 0) - before["TaskDuration"]) * 1000, 1),
            "script_ms": round((m.get("ScriptDuration", 0) - before["ScriptDuration"]) * 1000, 1),
            "layout_ms": round((m.get("LayoutDuration", 0) - before["LayoutDuration"]) * 1000, 1),
            "style_ms": round((m.get("RecalcStyleDuration", 0)
                               - before["RecalcStyleDuration"]) * 1000, 1),
        }
    return out

def seek_paused(page, t):
    page.evaluate("""async (t) => {
      const v = state.video; v.pause(); stopVideoLoop();
      if (Math.abs(v.currentTime - t) > 0.001) {
        await new Promise(r => { v.addEventListener('seeked', r, {once: true});
          v.currentTime = t; setTimeout(r, 2500); });
      }
      scheduleRender(0);
      await new Promise(r => setTimeout(r, 150));
    }""", t)
    page.wait_for_timeout(250)


# ---------------------------------------------------------------------------
# part: code
# ---------------------------------------------------------------------------

def part_code() -> dict:
    sys.path.insert(0, str(ROOT / "tools"))
    import build  # noqa: E402

    rows = []
    for name in FILES:
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        data = text.encode("utf-8")
        row = {
            "file": name,
            "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
            "bytes": len(data),
            "gzip": len(gzip.compress(data, 9)),
        }
        try:
            import brotli
            row["brotli"] = len(brotli.compress(data, quality=11))
        except Exception:  # noqa: BLE001
            row["brotli"] = None
        if name.endswith(".js"):
            row["minified"] = len(build.minify(text).encode("utf-8"))
        elif name.endswith(".css"):
            row["minified"] = len(build.minify_css(text).encode("utf-8"))
        elif name.endswith(".html"):
            row["minified"] = len(re.sub(r">\s+<", "><", text).encode("utf-8"))
        rows.append(row)

    tools = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        tools.append({"file": f"tools/{path.name}", "lines": text.count("\n"),
                      "bytes": len(text.encode("utf-8"))})
    tests = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tests.append({"file": str(path.relative_to(ROOT)), "lines": text.count("\n"),
                      "bytes": len(text.encode("utf-8"))})

    # Largest functions in app.js and effects.js.
    def functions(path: Path) -> list[dict]:
        text = path.read_text(encoding="utf-8")
        out = []
        pattern = re.compile(
            r"(?m)^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
            r"|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
            r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{")
        for m in pattern.finditer(text):
            name = m.group(1) or m.group(2)
            i = text.find("{", m.start())
            depth = 0
            j = i
            while j < len(text):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            body = text[m.start():j]
            out.append({"name": name, "lines": body.count("\n") + 1,
                        "bytes": len(body.encode("utf-8"))})
        return out

    largest = {}
    for name in ("app.js", "effects.js", "engine.js"):
        fns = functions(ROOT / name)
        fns.sort(key=lambda r: r["bytes"], reverse=True)
        largest[name] = {"count": len(fns), "largest": fns[:12]}

    # Parse and compile time in real Chromium.
    parse = {}
    with Server() as srv, sync_playwright() as p:
        browser, ctx, page, errors = new_page(p, "chromium")
        cdp = ctx.new_cdp_session(page)
        chunks: list[dict] = []
        done: list[dict] = []
        cdp.on("Tracing.dataCollected", lambda e: chunks.extend(e.get("value", [])))
        cdp.on("Tracing.tracingComplete", lambda e: done.append(e))
        cdp.send("Performance.enable")
        cdp.send("Tracing.start", {"categories":
                 "v8,devtools.timeline,disabled-by-default-v8.compile,toplevel"})
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(800)
        cdp.send("Tracing.end")
        for _ in range(100):
            if done:
                break
            page.wait_for_timeout(100)
        metrics = {r["name"]: r["value"]
                   for r in cdp.send("Performance.getMetrics")["metrics"]}
        per_url: dict[str, dict] = {}
        for e in chunks:
            if e.get("name") != "v8.compile":
                continue
            url = (e.get("args", {}).get("data", {}) or {}).get("url", "?")
            key = url.rsplit("/", 1)[-1] or url
            row = per_url.setdefault(key, {"ms": 0.0, "events": 0})
            row["ms"] += (e.get("dur", 0) or 0) / 1000
            row["events"] += 1
        bg = sum((e.get("dur", 0) or 0) / 1000 for e in chunks
                 if e.get("name") == "BackgroundCompileTask::Run")
        parse = {
            "main_thread_compile_ms_by_script": {
                k: {"ms": round(v["ms"], 2), "events": v["events"]}
                for k, v in sorted(per_url.items())},
            "main_thread_compile_total_ms": round(
                sum(v["ms"] for v in per_url.values()), 2),
            "background_compile_total_ms": round(bg, 2),
            "script_duration_s": round(metrics.get("ScriptDuration", 0), 3),
            "task_duration_s": round(metrics.get("TaskDuration", 0), 3),
            "errors": errors,
        }
        browser.close()

    # Brotli/gzip totals for what the static host serves (source and dist).
    def total(files: list[Path]) -> dict:
        raw = b"".join(f.read_bytes() for f in files)
        try:
            import brotli
            br = len(brotli.compress(raw, quality=11))
        except Exception:  # noqa: BLE001
            br = None
        return {"bytes": len(raw), "gzip": len(gzip.compress(raw, 9)), "brotli": br}

    app_files = [ROOT / n for n in FILES if (ROOT / n).exists()]
    dist_files = sorted((ROOT / "dist").rglob("*")) if (ROOT / "dist").exists() else []
    dist_files = [f for f in dist_files if f.is_file()]
    result = {
        "files": rows,
        "tools": tools,
        "tests": tests,
        "largest_functions": largest,
        "parse_compile": parse,
        "transfer_source": total(app_files),
        "transfer_dist": total(dist_files) if dist_files else None,
    }
    return result


# ---------------------------------------------------------------------------
# part: playback
# ---------------------------------------------------------------------------

def part_playback(browser_name: str) -> dict:
    make_fixtures()
    result = {"browser": browser_name, "windows": {}, "errors": []}
    with Server() as srv, sync_playwright() as p:
        browser, ctx, page, errors = new_page(p, browser_name, viewport=(1440, 1000),
                                              light=True)
        open_app(page, srv)
        cdp = None
        if browser_name == "chromium":
            cdp = ctx.new_cdp_session(page)
            cdp.send("Performance.enable")
        for size_name, (w, h) in SIZES.items():
            path = WORK / f"src-{w}x{h}.webm"
            load_video(page, path)
            for label, ids in (("none", []), ("light2", LIGHT), ("heavy7", HEAVY)):
                set_effects(page, ids)
                seek_paused(page, 0.2)
                page.evaluate("() => { state.video.play().catch(() => {}); }")
                page.wait_for_timeout(1200)
                pauses = []
                seeks = []
                for i in range(5):
                    if i:
                        page.evaluate("() => { state.video.play().catch(() => {}); }")
                        page.wait_for_timeout(450)
                    val = measure_seek(page, 0.4 + i * 0.1)
                    seeks.append(val)
                for i in range(5):
                    if i:
                        page.evaluate("() => { state.video.currentTime = 0.5; "
                                      "state.video.play().catch(() => {}); }")
                        page.wait_for_timeout(520)
                    pauses.append(measure_pause(page))
                if page.evaluate("() => state.video.paused"):
                    page.evaluate("() => { state.video.play().catch(() => {}); }")
                    page.wait_for_timeout(400)
                seek_paused(page, 0.2)
                page.evaluate("() => { state.video.play().catch(() => {}); }")
                page.wait_for_timeout(1000)
                win = run_window(page, 20.0, cdp)
                valid_p = [v for v in pauses if v is not None]
                valid_s = [v for v in seeks if v is not None]
                win["pause_latency_ms"] = valid_p
                win["pause_latency_med"] = (sorted(valid_p)[len(valid_p) // 2]
                                            if valid_p else None)
                win["seek_latency_ms"] = valid_s
                win["seek_latency_med"] = (sorted(valid_s)[len(valid_s) // 2]
                                           if valid_s else None)
                win["effects"] = ids
                win["size"] = size_name
                result["windows"][f"{size_name}-{label}"] = win
                print(f"[{browser_name}] {size_name} {label}: "
                      f"renders={win['renders']} ({win['renders_per_s']}/s) "
                      f"p50={win['render_p50']}ms p95={win['render_p95']}ms "
                      f"long>{win['longtasks_over_50']} "
                      f"pause={win['pause_latency_med']}ms seek={win['seek_latency_med']}ms "
                      f"cpu={win.get('cpu_s')}s heap={win['heap_end_mb']}MB",
                      flush=True)
                page.evaluate("() => { state.video.pause(); stopVideoLoop(); }")
                page.wait_for_timeout(300)
        result["errors"] = errors[:10]
        result["user_agent"] = page.evaluate("() => navigator.userAgent")
        browser.close()
    return result


# ---------------------------------------------------------------------------
# part: stages
# ---------------------------------------------------------------------------

def part_stages(browser_name: str = "chromium") -> dict:
    make_fixtures()
    result = {"browser": browser_name, "cases": {}, "errors": []}
    with Server() as srv, sync_playwright() as p:
        browser, ctx, page, errors = new_page(p, browser_name, viewport=(1440, 1000))
        open_app(page, srv)
        page.evaluate(DETAIL_JS)
        page.evaluate(STAGE_HOOKS)
        for size_name, (w, h) in SIZES.items():
            load_video(page, WORK / f"src-{w}x{h}.webm")
            seek_paused(page, 2.0)
            for label, ids in (("none", []), ("light2", LIGHT), ("heavy7", HEAVY)):
                set_effects(page, ids)
                seek_paused(page, 2.0)
                page.wait_for_timeout(300)
                probe = page.evaluate("() => window.__probeRender(5)")
                # source copy time is the last drawImage inside prepareBase
                src_ms = page.evaluate("() => +sourceDrawMs().toFixed(2)")
                probe["source_draw_ms"] = src_ms
                probe["effects"] = ids
                probe["size"] = size_name
                result["cases"][f"{size_name}-{label}"] = probe
                print(f"[stages] {size_name} {label}: render={probe['renderAvg']}ms "
                      f"base={probe['stage'].get('prepareBase', {}).get('ms')}ms "
                      f"srcDraw={src_ms}ms "
                      f"glyph={probe['stage'].get('renderScript', {}).get('ms')}ms "
                      f"fillText={probe['canvasOps'].get('fillText')} "
                      f"effects={ {k: v['ms'] for k, v in probe['stage'].items() if k.startswith('fx:')} }",
                      flush=True)
        result["errors"] = errors[:10]
        browser.close()
    return result


# ---------------------------------------------------------------------------
# part: sharpness
# ---------------------------------------------------------------------------

SHARP_JS = r"""
() => {
  const c = document.getElementById('canvas');
  const r = c.getBoundingClientRect();
  const full = computeOutputSize(state.sourceW, state.sourceH,
    state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight,
    state.opts.outputFit);
  const pv = previewSize(full);
  const dpr = window.devicePixelRatio || 1;
  const cssW = r.width, cssH = r.height;
  const needW = Math.min(state.sourceW, cssW * dpr);
  const needH = Math.min(state.sourceH, cssH * dpr);
  return {
    type: state.sourceType, source: [state.sourceW, state.sourceH],
    full: [full.w, full.h], preview: [pv.w, pv.h],
    backing: [c.width, c.height], css: [+cssW.toFixed(1), +cssH.toFixed(1)],
    dpr, zoom: +state.zoom.toFixed(3), scale: +state.scale.toFixed(4),
    need: [+needW.toFixed(1), +needH.toFixed(1)],
    covers: c.width + 0.5 >= needW && c.height + 0.5 >= needH,
    ratio: +(c.width / Math.max(1, needW)).toFixed(3),
    imageRendering: getComputedStyle(c).imageRendering,
  };
}
"""


def part_sharp() -> dict:
    make_fixtures()
    result = {"cases": {}, "errors": []}
    with Server() as srv, sync_playwright() as p:
        browser, ctx, page, errors = new_page(
            p, "chromium", viewport=(1440, 1000), dpr=1.0)
        open_app(page, srv)
        for dpr in (1.0, 2.0):
            if dpr != 1.0:
                page.close()
                ctx.close()
                browser.close()
                browser, ctx, page, errors2 = new_page(
                    p, "chromium", viewport=(1440, 1000), dpr=dpr)
                open_app(page, srv)
                errors += errors2
            for src_name, path, is_video in (
                    ("video-720p", WORK / "src-1280x720.webm", True),
                    ("video-1080p", WORK / "src-1920x1080.webm", True),
                    ("image-1080p", WORK / "image-1920x1080.png", False)):
                if is_video:
                    load_video(page, path)
                    seek_paused(page, 1.0)
                else:
                    load_image(page, path)
                page.evaluate("() => fitToWindow()")
                page.wait_for_timeout(250)
                for zoom in (0.79, 1.0, 1.12, 2.0):
                    page.evaluate("(z) => setZoom(z)", zoom)
                    page.wait_for_timeout(250)
                    data = page.evaluate(SHARP_JS)
                    data["dpr_requested"] = dpr
                    key = f"{src_name}-dpr{dpr}-z{zoom}"
                    result["cases"][key] = data
                    print(f"[sharp] {key}: backing={data['backing']} "
                          f"css={data['css']} need={data['need']} "
                          f"covers={data['covers']} ratio={data['ratio']}",
                          flush=True)
        result["errors"] = errors[:10]
        browser.close()
    return result


# ---------------------------------------------------------------------------
# part: memory
# ---------------------------------------------------------------------------

def heap_now(cdp) -> int:
    cdp.send("HeapProfiler.collectGarbage")
    return cdp.send("Runtime.getHeapUsage")["usedSize"]


def part_memory() -> dict:
    make_fixtures()
    result = {"checkpoints": {}, "idle_playback": [], "errors": []}
    with Server() as srv, sync_playwright() as p:
        browser, ctx, page, errors = new_page(p, "chromium", viewport=(1440, 1000))
        open_app(page, srv)
        cdp = ctx.new_cdp_session(page)
        page.on("download", lambda d: None)
        load_image(page, FIXTURE_IMAGE)
        page.wait_for_timeout(500)
        start = {"heap_mb": round(heap_now(cdp) / 1e6, 2),
                 "urls": page.evaluate("() => ({c: __l0.urlCreate, r: __l0.urlRevoke, live: __l0.urlLive})"),
                 "bitmaps": page.evaluate("() => [__l0.bitmap, __l0.bitmapClose]"),
                 "dom_canvas": page.evaluate("() => document.querySelectorAll('canvas').length")}
        result["checkpoints"]["start"] = start

        # 20 loads, alternating image and video, ending on a video.
        for i in range(20):
            if i % 2 == 0:
                load_video(page, WORK / "src-1280x720.webm")
            else:
                load_image(page, FIXTURE_IMAGE)
            page.wait_for_timeout(180)
        loads = {"heap_mb": round(heap_now(cdp) / 1e6, 2),
                 "urls": page.evaluate("() => ({c: __l0.urlCreate, r: __l0.urlRevoke, live: __l0.urlLive})"),
                 "bitmaps": page.evaluate("() => [__l0.bitmap, __l0.bitmapClose]"),
                 "dom_canvas": page.evaluate("() => document.querySelectorAll('canvas').length"),
                 "dom_video": page.evaluate("() => document.querySelectorAll('video').length"),
                 "source": page.evaluate("() => state.sourceType")}
        result["checkpoints"]["after_20_loads"] = loads
        print("[memory] after 20 loads:", loads, flush=True)

        # 20 exports of a 2 s 320x180 clip.
        load_video(page, WORK / "src-320x180-2s.webm")
        page.evaluate("""() => { state.opts.outputPreset = 'original';
          state.opts.exportFormat = 'webm'; scheduleRender(0); }""")
        page.wait_for_timeout(500)
        export_err = ""
        for i in range(20):
            try:
                page.select_option("#export-format", "webm")
                page.click("#btn-export")
                page.wait_for_function("() => state.videoExporting === true", timeout=15000)
                page.wait_for_function("() => state.videoExporting === false", timeout=120000)
                page.wait_for_timeout(250)
                if i % 5 == 4:
                    print(f"[memory] {i + 1} exports done", flush=True)
            except Exception as exc:  # noqa: BLE001
                export_err = str(exc)
                break
        exports = {"heap_mb": round(heap_now(cdp) / 1e6, 2),
                   "urls": page.evaluate("() => ({c: __l0.urlCreate, r: __l0.urlRevoke, live: __l0.urlLive})"),
                   "bitmaps": page.evaluate("() => [__l0.bitmap, __l0.bitmapClose]"),
                   "video_frames": page.evaluate("() => [__l0.videoFrame, __l0.videoFrameClose]"),
                   "error": export_err}
        result["checkpoints"]["after_20_exports"] = exports
        print("[memory] after 20 exports:", exports, flush=True)

        # 60 undo steps on an image.
        load_image(page, FIXTURE_IMAGE)
        page.wait_for_timeout(500)
        page.evaluate("""async () => {
          for (let i = 0; i < 60; i++) {
            state.opts.adj.brightness = (i % 20) - 10;
            pushHistory('l0-' + i);
            scheduleRender(0);
            await new Promise(r => setTimeout(r, 30));
          }
        }""")
        page.wait_for_timeout(500)
        hist_before = page.evaluate("""() => ({
          undo: state.history.undo.length, redo: state.history.redo.length,
          bytes: state.history.undo.reduce((n, s) => n + s.length, 0),
          heap_bytes: JSON.stringify(state.history.undo).length,
        })""")
        page.evaluate("""async () => {
          for (let i = 0; i < 60; i++) {
            undo();
            scheduleRender(0);
            await new Promise(r => setTimeout(r, 20));
          }
        }""")
        page.wait_for_timeout(500)
        undo = {"heap_mb": round(heap_now(cdp) / 1e6, 2),
                "history_before": hist_before,
                "history_after": page.evaluate("""() => ({
                  undo: state.history.undo.length, redo: state.history.redo.length,
                  bytes: state.history.undo.reduce((n, s) => n + s.length, 0),
                  heap_bytes: JSON.stringify(state.history.undo).length,
                })"""),
                "urls": page.evaluate("() => ({c: __l0.urlCreate, r: __l0.urlRevoke, live: __l0.urlLive})")}
        result["checkpoints"]["after_60_undo"] = undo
        print("[memory] after 60 undo:", undo, flush=True)

        # Five minutes of uninterrupted playback, heap sampled every 5 s.
        load_video(page, WORK / "src-1280x720.webm")
        set_effects(page, LIGHT)
        seek_paused(page, 0)
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(500)
        idle = []
        for i in range(60):
            page.wait_for_timeout(5000)
            sample = page.evaluate("""() => ({
              t: +state.video.currentTime.toFixed(2),
              heap_mb: performance.memory ? +(performance.memory.usedJSHeapSize / 1e6).toFixed(2) : null,
              renders: __l0.renders, longtasks: __l0.longtasks.length,
              backing: document.getElementById('canvas').width,
            })""")
            sample["second"] = (i + 1) * 5
            idle.append(sample)
            if i % 6 == 5:
                print(f"[memory] idle {sample['second']}s heap={sample['heap_mb']}MB "
                      f"renders={sample['renders']}", flush=True)
        result["idle_playback"] = idle
        result["checkpoints"]["after_5min_playback"] = {
            "heap_mb": round(heap_now(cdp) / 1e6, 2),
            "urls": page.evaluate("() => ({c: __l0.urlCreate, r: __l0.urlRevoke, live: __l0.urlLive})"),
        }
        result["errors"] = errors[:10]
        browser.close()
    return result


# ---------------------------------------------------------------------------
# part: compress
# ---------------------------------------------------------------------------

def part_compress() -> dict:
    rows = []
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            continue
        data = path.read_bytes()
        try:
            import brotli
            br = len(brotli.compress(data, quality=11))
        except Exception:  # noqa: BLE001
            br = None
        rows.append({"file": name, "bytes": len(data),
                     "gzip": len(gzip.compress(data, 9)), "brotli": br})
    dist_rows = []
    for path in sorted((ROOT / "dist").rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        try:
            import brotli
            br = len(brotli.compress(data, quality=11))
        except Exception:  # noqa: BLE001
            br = None
        dist_rows.append({"file": str(path.relative_to(ROOT / "dist")),
                          "bytes": len(data), "gzip": len(gzip.compress(data, 9)),
                          "brotli": br})

    worker_summary = page = None
    with Server() as srv, sync_playwright() as p:
        browser, ctx, pg, errors = new_page(p, "chromium")
        open_app(pg, srv)
        load_image(pg, FIXTURE_IMAGE)
        pg.wait_for_timeout(600)
        worker = pg.evaluate("""() => {
          if (!window.GCWorker) return {present: false};
          return {present: true, stats: GCWorker.stats ? GCWorker.stats() : null,
                  minPixels: window.GC_WORKER_MIN_PIXELS,
                  minEffects: window.GC_WORKER_MIN_EFFECTS};
        }""")
        opts_bytes = pg.evaluate("""() => {
          const o = renderOpts();
          return {json: JSON.stringify(o).length,
                  effects: (o.effects || []).length,
                  keys: Object.keys(o).length};
        }""")
        worker_summary = {"worker": worker, "opts_payload": opts_bytes}
        browser.close()

    history = None
    return {"source": rows, "dist": dist_rows,
            "worker_transfer": worker_summary, "history": history}


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True,
                    choices=["code", "playback", "stages", "sharp", "memory",
                             "compress", "all"])
    ap.add_argument("--browser", default="chromium",
                    choices=["chromium", "firefox"])
    args = ap.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    make_fixtures()

    parts = ([args.part] if args.part != "all" else
             ["code", "compress", "sharp", "stages", "memory", "playback"])
    for part in parts:
        started = time.time()
        if part == "code":
            data = part_code()
        elif part == "compress":
            data = part_compress()
        elif part == "sharp":
            data = part_sharp()
        elif part == "stages":
            data = part_stages(args.browser)
        elif part == "memory":
            data = part_memory()
        else:
            data = part_playback(args.browser)
        suffix = args.browser if (part == "playback" or args.browser != "chromium") else "runtime"
        out = EVIDENCE / f"{part}-{suffix}.json"
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)} ({time.time() - started:.1f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
