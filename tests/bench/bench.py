#!/usr/bin/env python3
"""P2-3 Task A2 baseline. Headless Chromium, software raster.

  python tests/bench/bench.py              # every section
  python tests/bench/bench.py render drag  # selected sections

Sections: startup render stacks drag video export idle heap bundle.
Writes docs/evidence/p2-3/baseline.json after every section.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_lib as B  # noqa: E402

OUT = B.ROOT / "docs" / "evidence" / "p2-3" / "baseline.json"
SECTIONS = ["startup", "render", "stacks", "drag", "video", "export", "idle", "heap", "bundle"]
WINDOWS = 5
WARMUP = 2


def meta(browser) -> dict:
    return {
        "task": "P2-3 A2 baseline",
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "chromium": browser.version,
        "cpu": os.cpu_count(),
        "viewport": [1440, 1000],
        "windows": WINDOWS,
        "warmup": WARMUP,
        "seed": B.SEED,
        "raster": "headless software raster (measurement floor, not a GPU claim)",
        "fixtures": {"1080p": str(B.FIXTURE_1080), "4k": str(B.FIXTURE_4K)},
        "video_fixtures": {"1080p": str(B.VIDEO_1080), "4k": str(B.VIDEO_4K),
                           "export": str(B.VIDEO_EXPORT)},
    }


def section_startup(browser, srv, out):
    out["startup"] = B.startup(browser, srv, runs=5)


def section_render(browser, srv, out):
    rows = []
    for label, path in B.expected_sources().items():
        ctx, page, errs = B.new_page(browser, srv)
        try:
            B.load_image(page, path)
            cdp = B.cdp_session(page)
            cat = B.effect_catalog(page)
            for mode in ("script", "dither", "effects"):
                for fx in cat:
                    params = B.mid_params(page, fx["id"])
                    cfg = {"mode": mode, "effects": [fx["id"]],
                           "params": {fx["id"]: params}, "full": False}
                    preview = B.five_windows(page, cdp,
                                            lambda c=cfg: B.render_case(page, cdp, c, warm=WARMUP))
                    full_cfg = dict(cfg, full=True)
                    one = B.render_case_full(page, cdp, full_cfg, warm=1)
                    rows.append({
                        "source": label, "mode": mode, "effect": fx["id"],
                        "preview": preview,
                        "full": {"ms": one["ms"], "w": one["w"], "h": one["h"],
                                 "windows": 1,
                                 "note": "one forced-GC sample at native size; full 5-window cost is in stacks/export"},
                    })
                    print(f"render {label} {mode} {fx['id']:10} preview={preview['median']}ms "
                          f"full={one['ms']}ms {one['w']}x{one['h']}", flush=True)
            if errs:
                out.setdefault("errors", []).extend(f"render {label}: {e}" for e in errs)
        finally:
            ctx.close()
    out["render"] = rows


def section_stacks(browser, srv, out):
    rows = []
    for label, path in B.expected_sources().items():
        ctx, page, errs = B.new_page(browser, srv)
        try:
            B.load_image(page, path)
            cdp = B.cdp_session(page)
            for mode in ("script", "dither", "effects"):
                for n in (1, 3, 6, 12):
                    ids = B.STACK_ORDER[:n]
                    params = {eid: B.mid_params(page, eid) for eid in ids}
                    cfg = {"mode": mode, "effects": ids, "params": params, "full": False}
                    res = B.five_windows(page, cdp,
                                         lambda c=cfg: B.render_case(page, cdp, c, warm=WARMUP))
                    rows.append({"source": label, "mode": mode, "effects": ids,
                                 "count": n, "preview": res})
                    print(f"stack {label} {mode} {n:2} effects median={res['median']}ms p95={res['p95']}", flush=True)
            if errs:
                out.setdefault("errors", []).extend(f"stacks {label}: {e}" for e in errs)
        finally:
            ctx.close()
    out["stacks"] = rows


DRAG_JS = r"""
({frames, warmup}) => new Promise((resolve) => {
  const el = document.getElementById('depth');
  el.scrollIntoView({ block: 'center' });
  const min = +el.min, max = +el.max;
  const intervals = [];
  let last = performance.now(), i = 0, warm = true;
  const renders = [];
  const orig = window.render;
  window.render = function (...a) {
    const t0 = performance.now();
    try { return orig.apply(this, a); }
    finally { renders.push(+(performance.now() - t0).toFixed(1)); }
  };
  const tick = (t) => {
    el.value = String(Math.round(min + (max - min) * (0.5 + 0.42 * Math.sin(i / 9))));
    el.dispatchEvent(new Event('input', { bubbles: true }));
    if (warm) {
      i++;
      if (i > warmup) { warm = false; i = 0; last = t; renders.length = 0; }
      requestAnimationFrame(tick);
      return;
    }
    intervals.push(+(t - last).toFixed(2));
    last = t;
    if (i < frames) { i++; requestAnimationFrame(tick); return; }
    window.render = orig;
    resolve({ intervals, renderMs: renders.slice() });
  };
  requestAnimationFrame(tick);
})
"""


def stats(values):
    vals = sorted(v for v in values if v is not None and v > 0)
    if not vals:
        return {"median": None, "p95": None, "max": None, "n": 0}
    pick = lambda q: vals[min(len(vals) - 1, int(len(vals) * q))]
    return {"median": round(statistics.median(vals), 2),
            "p95": round(pick(0.95), 2), "max": round(vals[-1], 2), "n": len(vals)}


def drag_window(page, frames=180, warmup=60):
    raw = page.evaluate(DRAG_JS, {"frames": frames, "warmup": warmup})
    return {"frames": stats(raw["intervals"]),
            "renderMs": stats(raw["renderMs"]),
            "longtasks": page.evaluate("() => window.__benchLong.slice()")}


def section_drag(browser, srv, out):
    pages = {}
    try:
        for mode, worker in (("worker", True), ("sync", False)):
            ctx, page, errs = B.new_page(browser, srv, worker=worker)
            B.load_image(page, B.FIXTURE_4K)
            page.evaluate("""(ids) => {
              state.opts.effects = state.opts.effects.map(fx => ({
                ...fx, enabled: ids.includes(fx.id),
                params: { ...effectDefaults(fx.id), ...(fx.params || {}) }
              }));
              state.opts.outputPreset = 'original';
              scheduleRender(0);
            }""", B.HEAVY)
            page.wait_for_timeout(1500)
            if worker:
                page.wait_for_function(
                    "() => window.GCWorker && GCWorker.enabled() && GCWorker.stats().sourceReady",
                    timeout=60000)
            pages[mode] = {"ctx": ctx, "page": page, "errors": errs}
        rows = []
        for w in range(WINDOWS):
            pair = {}
            for mode in ("sync", "worker"):
                page = pages[mode]["page"]
                page.evaluate("() => { window.__benchLong.length = 0; }")
                pair[mode] = drag_window(page)
            rows.append(pair)
            print(f"drag window {w + 1}: sync rAF med={pair['sync']['frames']['median']} "
                  f"render med={pair['sync']['renderMs']['median']} | "
                  f"worker rAF med={pair['worker']['frames']['median']} "
                  f"render med={pair['worker']['renderMs']['median']}", flush=True)
        summary = {}
        for mode in ("sync", "worker"):
            summary[mode] = {
                "raf": stats([v for row in rows for v in [row[mode]["frames"]["median"]]]),
                "render": stats([v for row in rows for v in [row[mode]["renderMs"]["median"]]]),
                "longtasks": [t for row in rows for t in row[mode]["longtasks"]],
            }
        out["drag"] = {"effects": B.HEAVY, "source": "4K still", "windows": rows,
                       "summary": summary}
        for mode, info in pages.items():
            if info["errors"]:
                out.setdefault("errors", []).extend(f"drag {mode}: {e}" for e in info["errors"])
    finally:
        for info in pages.values():
            info["ctx"].close()


PLAYBACK_JS = r"""
(seconds) => new Promise((resolve) => {
  const t0 = performance.now();
  const intervals = [];
  let last = t0;
  const tick = (t) => {
    intervals.push(t - last);
    last = t;
    if (t - t0 < seconds * 1000) requestAnimationFrame(tick);
    else resolve({ intervals: intervals.slice(1), seconds: (t - t0) / 1000 });
  };
  requestAnimationFrame(tick);
})
"""


def section_video(browser, srv, out):
    rows = []
    for label, path in (("1080p", B.VIDEO_1080), ("4k", B.VIDEO_4K)):
        for n in (0, 3, 6):
            ctx, page, errs = B.new_page(browser, srv)
            try:
                B.load_video(page, path)
                ids = B.HEAVY[:n]
                page.evaluate("""(ids) => {
                  state.opts.effects = state.opts.effects.map(fx => ({
                    ...fx, enabled: ids.includes(fx.id),
                    params: { ...effectDefaults(fx.id), ...(fx.params || {}) }
                  }));
                  scheduleRender(0);
                }""", ids)
                page.wait_for_timeout(1200)
                page.evaluate("() => { const v = state.video; if (v) { v.currentTime = 0; v.play(); } }")
                page.wait_for_timeout(300)
                windows = []
                for _ in range(WINDOWS):
                    raw = page.evaluate(PLAYBACK_JS, 1.5)
                    windows.append(stats(raw["intervals"]))
                rows.append({"source": label, "effects": ids, "count": n,
                             "windows": windows,
                             "medianOfMedians": round(statistics.median(
                                 [w["median"] for w in windows if w["median"]]), 2)})
                print(f"video {label} {n} effects median={rows[-1]['medianOfMedians']}ms", flush=True)
                if errs:
                    out.setdefault("errors", []).extend(f"video {label} {n}: {e}" for e in errs)
            finally:
                ctx.close()
    out["video"] = rows


def section_export(browser, srv, out):
    B.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for f in B.DOWNLOAD_DIR.iterdir():
        f.unlink()
    ctx, page, errs = B.new_page(browser, srv, downloads=True)
    try:
        B.load_video(page, B.VIDEO_EXPORT)
        cdp = B.cdp_session(page)
        heap_before = B.js_heap(cdp)
        page.evaluate("""() => {
          window.__peak = 0;
          window.__peakTimer = setInterval(() => {
            if (performance.memory) window.__peak = Math.max(window.__peak, performance.memory.usedJSHeapSize);
          }, 40);
        }""")
        t0 = time.perf_counter()
        with page.expect_download(timeout=240000) as dl:
            page.evaluate("""async () => {
              state.opts.effects = state.opts.effects.map(fx => ({
                ...fx, enabled: ['posterize','edges','sketch'].includes(fx.id),
                params: { ...effectDefaults(fx.id), ...(fx.params || {}) }
              }));
              const full = computeOutputSize(state.sourceW, state.sourceH, 'original', 1920, 1080, 'contain');
              await exportVideo(full, renderOpts());
            }""")
        elapsed = time.perf_counter() - t0
        download = dl.value
        saved = B.DOWNLOAD_DIR / download.suggested_filename
        download.save_as(saved)
        peak = page.evaluate("() => { clearInterval(window.__peakTimer); return window.__peak; }")
        heap_after = B.js_heap(cdp)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,duration,nb_frames",
             "-of", "json", str(saved)],
            capture_output=True, text=True, check=True)
        info = json.loads(probe.stdout)
        stream = (info.get("streams") or [{}])[0]
        out["export"] = {
            "source": str(B.VIDEO_EXPORT),
            "source_size": [1280, 720],
            "effects": ["posterize", "edges", "sketch"],
            "seconds_of_video": 1.0,
            "wall_seconds": round(elapsed, 2),
            "seconds_per_exported_second": round(elapsed, 2),
            "peak_js_heap_bytes": peak,
            "heap_before_bytes": heap_before,
            "heap_after_gc_bytes": heap_after,
            "output": {"width": stream.get("width"), "height": stream.get("height"),
                       "duration": stream.get("duration"), "frames": stream.get("nb_frames"),
                       "bytes": saved.stat().st_size},
            "path": str(saved),
        }
        print(f"export {elapsed:.2f}s for 1 s of video, peak heap {peak / 1e6:.1f} MB, "
              f"output {stream.get('width')}x{stream.get('height')}", flush=True)
        if errs:
            out.setdefault("errors", []).extend(f"export: {e}" for e in errs)
    finally:
        ctx.close()


def section_idle(browser, srv, out):
    ctx, page, errs = B.new_page(browser, srv)
    try:
        B.load_image(page, B.FIXTURE_4K)
        page.evaluate("""(ids) => {
          state.opts.effects = state.opts.effects.map(fx => ({
            ...fx, enabled: ids.includes(fx.id),
            params: { ...effectDefaults(fx.id), ...(fx.params || {}) }
          }));
          scheduleRender(0);
        }""", B.HEAVY)
        page.wait_for_timeout(2500)
        cdp = B.cdp_session(page)
        cdp.send("Performance.enable")
        def task_total():
            m = {row["name"]: row["value"] for row in cdp.send("Performance.getMetrics")["metrics"]}
            return m.get("TaskDuration", 0.0)
        page.evaluate("() => { window.__rafCount = 0; window.__rafOn = true; const t=( )=>{ if(!window.__rafOn) return; window.__rafCount++; requestAnimationFrame(t); }; requestAnimationFrame(t); }")
        rows = []
        for _ in range(5):
            a = task_total()
            raf0 = page.evaluate("() => window.__rafCount")
            page.wait_for_timeout(2000)
            b = task_total()
            raf1 = page.evaluate("() => window.__rafCount")
            rows.append({"task_ms": round((b - a) * 1000, 1), "window_ms": 2000,
                         "cpu_percent": round((b - a) * 1000 / 2000 * 100, 2),
                         "raf": raf1 - raf0})
        page.evaluate("() => { window.__rafOn = false; }")
        out["idle"] = {"source": "4K still + 6 effects", "windows": rows,
                       "median_cpu_percent": round(statistics.median(
                           [r["cpu_percent"] for r in rows]), 2)}
        print(f"idle CPU {out['idle']['median_cpu_percent']}% of one core", flush=True)
        if errs:
            out.setdefault("errors", []).extend(f"idle: {e}" for e in errs)
    finally:
        ctx.close()


def section_heap(browser, srv, out):
    ctx, page, errs = B.new_page(browser, srv)
    try:
        B.load_image(page, B.FIXTURE_1080)
        cdp = B.cdp_session(page)
        cfg = {"mode": "script", "effects": B.STACK_ORDER[:3],
               "params": {eid: B.mid_params(page, eid) for eid in B.STACK_ORDER[:3]},
               "full": False}
        for _ in range(10):
            page.evaluate("(c) => window.__benchRender(c)", cfg)
        B.gc(cdp)
        before = B.js_heap(cdp)
        t0 = time.perf_counter()
        for i in range(200):
            page.evaluate("(c) => window.__benchRender(c)", cfg)
            if i % 50 == 0:
                B.gc(cdp)
        elapsed = time.perf_counter() - t0
        B.gc(cdp)
        after = B.js_heap(cdp)
        out["heap"] = {
            "source": "1080p still, preview, 3 effects",
            "renders": 200,
            "wall_seconds": round(elapsed, 2),
            "before_bytes": before,
            "after_gc_bytes": after,
            "growth_bytes": after - before,
            "growth_per_render_bytes": round((after - before) / 200, 1),
        }
        print(f"heap {before / 1e6:.1f} -> {after / 1e6:.1f} MB over 200 renders", flush=True)
        if errs:
            out.setdefault("errors", []).extend(f"heap: {e}" for e in errs)
    finally:
        ctx.close()


def section_bundle(browser, srv, out):
    files = {}
    for path in sorted(B.ROOT.glob("dist/*")):
        if path.is_file():
            files[str(path.relative_to(B.ROOT))] = path.stat().st_size
    source = {}
    for name in ("index.html", "style.css", "engine.js", "effects.js", "reorder.js",
                 "app.js", "render-worker.js"):
        p = B.ROOT / name
        source[name] = p.stat().st_size
    out["bundle"] = {
        "source_bytes": source,
        "source_total_bytes": sum(source.values()),
        "dist_bytes": files,
        "dist_total_bytes": sum(files.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sections", nargs="*")
    args = parser.parse_args()
    unknown = [s for s in args.sections if s not in SECTIONS]
    if unknown:
        parser.error(f"unknown section(s): {', '.join(unknown)}")
    chosen = args.sections or SECTIONS
    need_media = any(s in {"render", "stacks", "drag", "idle", "heap", "startup"} for s in chosen)
    if need_media:
        B.fixtures()
    if any(s in {"video", "export"} for s in chosen):
        B.videos()
    out = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with B.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            out["meta"] = meta(browser)
            B.write_json(OUT, out)
            for name in chosen:
                t0 = time.time()
                print(f"=== {name} ===", flush=True)
                globals()[f"section_{name}"](browser, srv, out)
                out.setdefault("section_seconds", {})[name] = round(time.time() - t0, 1)
                B.write_json(OUT, out)
        finally:
            browser.close()
    print("BASELINE WRITTEN", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
