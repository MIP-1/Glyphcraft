#!/usr/bin/env python3
"""G23: playback smoothness (paired) and preview sharpness.

Permanent regression check for the owner's two complaints after V2:

  (a) video playback lag with a light effect stack
  (b) a soft preview on a HiDPI screen or above 100 % zoom

L0 baseline (docs/evidence/l0/playback-*.json, 20 s windows, headless software
raster, 1280x720 source, preview 1280x720):

  browser   stack    p50 render   late intervals (>50 ms)
  chromium  none      38.3 ms      0 %
  chromium  light2    67.3 ms    100 %
  firefox   none      52.0 ms    100 %
  firefox   light2   161.0 ms    100 %
  firefox   light2 pause-click latency: median 930 ms, max 1235 ms

Sharpness baseline (docs/evidence/l0/sharp-runtime.json, 1920x1080 source):
  DPR 1, zoom 100 %: backing 1600 covers min(native 1920, CSS 1333) -> PASS
  DPR 1, zoom 200 %: backing 1600 < min(1920, 2666) = 1920 -> FAIL
  DPR 2, zoom 100 %: backing 1600 < min(1920, 2666) = 1920 -> FAIL
  DPR 2, zoom 200 %: backing 1600 < min(1920, 5333) = 1920 -> FAIL

Budgets are the target for "smooth", all paired against the zero-effect control
measured immediately before the light window in the same session: the light
stack may add at most 20 ms (Chromium) / 30 ms (Firefox) to render p50, must
keep at least 60 % of the control's frame rate, and may raise the inter-render
interval p50 by at most 50 ms, with pause input no more than 150 ms above the
paired control p90 and 300 ms above its max. Absolute p50, gap and pause
budgets were falsified as machine measurements by the paired RED runs: the
zero-effect control itself varied from 37.6 ms to 61.5 ms p50 between runs,
headless software raster presents video at 11 to 19 fps with no effects at all,
and after the L1 fixes a zero-effect Firefox click still took a 164.4 ms median
(299.0 ms max) to reach `state.video.paused`, over the original 150 ms absolute
pause budget with no effects enabled at all. The original 150/300 ms numbers
are kept as paired deltas, at p90 and max: the click phase is bimodal (a click
lands either inside or between renders), so the 9-sample median flipped between
modes and a 50 ms mean-delta rule sat inside its own ~35 ms standard error
(Chromium 50.7 and Firefox 56.5 ms in two L1 runs, -0.7 and 40.0 ms in others).
The V2 tree still fails this: L0 measured a 930 ms Firefox pause median and
1235 ms max, i.e. a p90 delta of about 1 s against the same control. They sit
below the L0 measurement on purpose: this check is RED on the V2 tree and goes
GREEN only when the measured cause is removed. A machine that cannot run the
zero-effect control at all is reported as a machine problem, not an app pass.

Estimator fix, same budgets: `median()` averaged the two middle values for an
even sample only after L1 (before it returned the upper of the two windows,
`xs[n // 2]`, which is not a median and biased every two-window aggregate
toward the worse window). With two pairs, a 24/31 ms Firefox delta was reported
as 31; the true median is 27.5. The V2 tree is still RED with the fixed
estimator (Chromium L0 pairs 24.9/34.2 -> 29.6 > 20, Firefox 55/96 -> 75.5 > 30).

Sample count, same budgets (variance, not threshold): the gate runs on a
working desktop, and a blank page with no app code stalled for 149.8 ms in
Firefox (one frame in 20 s) while Chromium was clean, so external stalls are
real. Two consecutive full-gate runs failed on exactly one such stall each:
a single stalled 5 s window of two (the median of two is their mean, so it
could not be discarded) and two 700 ms+ clicks among nine (p90 of nine is the
second-worst value). The harness now takes three control/light pairs, whose
median discards one stalled window, and twenty pause clicks per side, whose p90
is the 18th of 20 and discards two stalls. Every budget is unchanged, and the
V2 tree still fails in every window it was measured in (Chromium 24.9/34.2
against 20, Firefox 55/96 against 30, pause p90 delta about 1 s against 150),
so no median or quantile of its samples can pass.
"""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/tmp/opencode/glyphcraft_perf")
EVIDENCE = ROOT / "docs" / "evidence" / os.environ.get("GATE_TASK", "l0")
LIGHT = ["posterize", "duotone"]

DELTA_P50_BUDGET = {"chromium": 20.0, "firefox": 30.0}
FPS_RATIO_BUDGET = 0.60          # light fps / control fps
INTERVAL_EXTRA_BUDGET = 50.0     # ms above the paired control interval p50
PAUSE_P90_EXTRA_BUDGET = 150.0   # ms above the paired control pause p90
PAUSE_MAX_EXTRA_BUDGET = 300.0   # ms above the paired control pause max
MIN_RENDERS = 15                  # in a 5 s window
MIN_VIDEO_ADVANCE = 4.5          # seconds in a 5 s window
MIN_CONTROL_RENDERS = 20


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
    for name, (w, h) in {"720p": (1280, 720), "1080p": (1920, 1080)}.items():
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


INIT_JS = r"""
(() => {
  const P = window.__g23 = {renders: 0, ms: [], starts: [], longtasks: [],
                            rvfc: 0, ltFrom: 0};
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (e.startTime >= P.ltFrom) P.longtasks.push(e.duration);
      }
    }).observe({entryTypes: ['longtask']});
  } catch (e) {}
  const rv = HTMLVideoElement.prototype.requestVideoFrameCallback;
  if (rv) {
    HTMLVideoElement.prototype.requestVideoFrameCallback = function (cb) {
      P.rvfc++;
      return rv.call(this, cb);
    };
  }
  window.__g23Reset = function () {
    P.renders = 0; P.ms = []; P.starts = []; P.longtasks = [];
    P.rvfc = 0; P.ltFrom = performance.now();
  };
  const r = window.render;
  window.render = function (...a) {
    const t = performance.now();
    P.starts.push(t);
    try { return r.apply(this, a); }
    finally { P.renders++; P.ms.push(performance.now() - t); }
  };
})();
"""


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round((len(xs) - 1) * p)))], 1)


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    mid = n // 2
    # True median: an even sample has no middle element, so average the two
    # middle values. Returning xs[n // 2] (the upper of two windows) used to
    # bias the paired G23 deltas toward the worse window.
    return round(xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2, 1)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def pctr(xs, p):
    return pct([x for x in xs if x is not None], p)


def load_video(page, path: Path) -> None:
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


def set_effects(page, ids) -> None:
    page.evaluate("""(ids) => {
      state.opts.effects = state.opts.effects.map(fx => ({
        ...fx, enabled: ids.includes(fx.id),
        params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
      }));
      state.opts.mode = 'script';
      scheduleRender(0);
    }""", ids)
    page.wait_for_timeout(300)


def seek_paused(page, t: float) -> None:
    page.evaluate("""async (t) => {
      const v = state.video; v.pause(); stopVideoLoop();
      if (Math.abs(v.currentTime - t) > 0.001) {
        await new Promise(r => { v.addEventListener('seeked', r, {once: true});
          v.currentTime = t; setTimeout(r, 2500); });
      }
      scheduleRender(0);
      await new Promise(r => setTimeout(r, 150));
    }""", t)
    page.wait_for_timeout(200)


def window(page, seconds: float) -> dict:
    page.evaluate("() => window.__g23Reset()")
    start = page.evaluate("() => +state.video.currentTime.toFixed(3)")
    t0 = time.time()
    time.sleep(seconds)
    wall = time.time() - t0
    data = page.evaluate("""() => {
      const P = window.__g23;
      const c = document.getElementById('canvas');
      return {renders: P.renders, ms: P.ms.slice(), starts: P.starts.slice(),
              longtasks: P.longtasks.slice(), rvfc: P.rvfc,
              videoTime: +state.video.currentTime.toFixed(3),
              backing: [c.width, c.height], paused: state.video.paused,
              full: computeOutputSize(state.sourceW, state.sourceH,
                state.opts.outputPreset, state.opts.outputWidth,
                state.opts.outputHeight, state.opts.outputFit),
              preview: previewSize(computeOutputSize(state.sourceW, state.sourceH,
                state.opts.outputPreset, state.opts.outputWidth,
                state.opts.outputHeight, state.opts.outputFit))};
    }""")
    intervals = [b - a for a, b in zip(data["starts"], data["starts"][1:])]
    late = sum(1 for v in intervals if v > 50.0)
    data.update({
        "wall": round(wall, 2),
        "fps": round(data["renders"] / max(0.001, wall), 2),
        "p50": pct(data["ms"], 0.5),
        "p95": pct(data["ms"], 0.95),
        "interval_p50": pct(intervals, 0.5),
        "interval_p95": pct(intervals, 0.95),
        "late_share": round(late / max(1, len(intervals)), 3),
        "longest_task": round(max(data["longtasks"] + [0]), 1),
        "longtask_ms": round(sum(data["longtasks"]), 1),
        "advance": round(data["videoTime"] - start, 2),
    })
    return data


def pause_latency(page) -> float | None:
    box = page.locator("#video-toggle").bounding_box()
    t0 = time.time()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    try:
        page.wait_for_function("() => state.video && state.video.paused", timeout=8000)
        value = round((time.time() - t0) * 1000, 1)
    except Exception:  # noqa: BLE001
        return None
    page.evaluate("() => { state.video.play().catch(() => {}); }")
    page.wait_for_timeout(400)
    return value


SHARP_JS = r"""
() => {
  const c = document.getElementById('canvas');
  const r = c.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  return {
    backing: [c.width, c.height],
    css: [+r.width.toFixed(1), +r.height.toFixed(1)],
    source: [state.sourceW, state.sourceH],
    dpr, zoom: +state.zoom.toFixed(3),
    need: [+Math.min(state.sourceW, r.width * dpr).toFixed(1),
           +Math.min(state.sourceH, r.height * dpr).toFixed(1)],
    previewMax: PREVIEW_MAX,
    previewMaxPixels: MAX_PREVIEW_PIXELS,
    needMax: PREVIEW_NEED_MAX,
  };
}
"""


def main() -> int:
    make_fixtures()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    problems: list[str] = []
    window_log: list[dict] = []

    def record(case: str, name: str, detail: str, ok: bool) -> None:
        rows.append({"case": case, "name": name, "detail": detail, "ok": ok})
        print(("PASS " if ok else "FAIL ") + f"[{case}] {name}: {detail}", flush=True)
        if not ok:
            problems.append(f"[{case}] {name}: {detail}")

    with Server() as srv, sync_playwright() as p:
        # ---------------------------------------------------------- (a) smooth
        for browser_name in ("chromium", "firefox"):
            browser = getattr(p, browser_name).launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                      locale="en-US")
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(srv.url + "/index.html", wait_until="load")
            page.wait_for_timeout(3000)
            page.evaluate(INIT_JS)
            load_video(page, WORK / "src-1280x720.webm")

            pairs = []
            for _ in range(3):
                for label, ids in (("control", []), ("light", LIGHT)):
                    set_effects(page, ids)
                    seek_paused(page, 0.3)
                    page.evaluate("() => { state.video.play().catch(() => {}); }")
                    page.wait_for_timeout(900)
                    w = window(page, 5.0)
                    pairs.append((label, w))
                    window_log.append({"browser": browser_name, "label": label,
                                       **{k: v for k, v in w.items()
                                          if k != "ms" and k != "starts"}})
                    page.evaluate("() => { state.video.pause(); stopVideoLoop(); }")
                    page.wait_for_timeout(250)
            controls = [w for label, w in pairs if label == "control"]
            lights = [w for label, w in pairs if label == "light"]
            paired, last_control = [], None
            for label, w in pairs:
                if label == "control":
                    last_control = w
                elif last_control is not None:
                    paired.append({
                        "control": last_control, "light": w,
                        "delta_p50": round(w["p50"] - last_control["p50"], 1),
                        "fps_ratio": round(w["fps"] / max(0.001, last_control["fps"]), 3),
                        "interval_extra": round(
                            w["interval_p50"] - last_control["interval_p50"], 1),
                    })
            ctrl = {k: median([w[k] for w in controls])
                    for k in ("p50", "fps", "advance",
                              "interval_p50", "interval_p95")}
            light = {k: median([w[k] for w in lights])
                     for k in ("p50", "p95", "fps", "advance",
                               "interval_p50", "interval_p95",
                               "longest_task", "longtask_ms")}
            light["delta_p50"] = median([x["delta_p50"] for x in paired])
            light["fps_ratio"] = median([x["fps_ratio"] for x in paired])
            light["interval_extra"] = median([x["interval_extra"] for x in paired])

            # Pause input sampled inside the light window and in the
            # zero-effect control measured just before it (paired).
            def sample_pauses(ids):
                set_effects(page, ids)
                seek_paused(page, 0.3)
                page.evaluate("() => { state.video.play().catch(() => {}); }")
                page.wait_for_timeout(800)
                vals = [pause_latency(page) for _ in range(20)]
                page.evaluate("() => { state.video.pause(); stopVideoLoop(); }")
                page.wait_for_timeout(250)
                return vals

            control_pauses = sample_pauses([])
            pauses = sample_pauses(LIGHT)
            cm = median(control_pauses)
            cmu = mean(control_pauses)
            c90 = pctr(control_pauses, 0.9)
            cmax = max((v for v in control_pauses if v is not None), default=None)
            pm = median(pauses)
            pmu = mean(pauses)
            p90 = pctr(pauses, 0.9)
            pmax = max((v for v in pauses if v is not None), default=None)
            pause_delta_mean = round(pmu - cmu, 1) if pmu is not None and cmu is not None else None
            pause_delta_p90 = round(p90 - c90, 1) if p90 is not None and c90 is not None else None
            pause_delta_max = round(pmax - cmax, 1) if pmax is not None and cmax is not None else None

            record("smooth", f"{browser_name} zero-effect control runs",
                   f"p50={ctrl['p50']}ms fps={ctrl['fps']} "
                   f"interval p50={ctrl['interval_p50']}ms "
                   f"advance={ctrl['advance']}s",
                   ctrl["fps"] is not None and ctrl["fps"] >= 4
                   and ctrl["advance"] >= MIN_VIDEO_ADVANCE)
            record("smooth", f"{browser_name} light stack keeps playback fluid",
                   f"p50={light['p50']}ms(control {ctrl['p50']} "
                   f"delta {light['delta_p50']} budget {DELTA_P50_BUDGET[browser_name]}) "
                   f"p95={light['p95']}ms "
                   f"fps={light['fps']}(control {ctrl['fps']} "
                   f"ratio {light['fps_ratio']} budget {FPS_RATIO_BUDGET}) "
                   f"interval p50={light['interval_p50']}ms(control "
                   f"{ctrl['interval_p50']} extra {light['interval_extra']} "
                   f"budget {INTERVAL_EXTRA_BUDGET}) "
                   f"longest_task={light['longest_task']}ms pairs="
                   f"{[(x['delta_p50'], x['fps_ratio'], x['interval_extra']) for x in paired]}",
                   light["p50"] is not None
                   and light["delta_p50"] <= DELTA_P50_BUDGET[browser_name]
                   and light["fps"] >= max(MIN_RENDERS / 5.0,
                                           FPS_RATIO_BUDGET * ctrl["fps"])
                   and light["interval_extra"] <= INTERVAL_EXTRA_BUDGET
                   and light["advance"] >= MIN_VIDEO_ADVANCE)
            record("smooth", f"{browser_name} light stack keeps input responsive",
                   f"pause p90={p90}ms(control {c90} delta {pause_delta_p90} "
                   f"budget {PAUSE_P90_EXTRA_BUDGET}) "
                   f"max={pmax}ms(control {cmax} delta {pause_delta_max} "
                   f"budget {PAUSE_MAX_EXTRA_BUDGET}) mean={pmu}/{cmu} "
                   f"median={pm}/{cm} samples={pauses} control_samples={control_pauses}",
                   p90 is not None and c90 is not None
                   and pause_delta_p90 <= PAUSE_P90_EXTRA_BUDGET
                   and pmax is not None and cmax is not None
                   and pause_delta_max <= PAUSE_MAX_EXTRA_BUDGET)
            record("smooth", f"{browser_name} playback has no page errors",
                   repr(errors[:4]), not errors)
            browser.close()

        # --------------------------------------------------------- (b) sharpness
        for dpr in (1.0, 2.0):
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                device_scale_factor=dpr, locale="en-US")
            page = ctx.new_page()
            page.goto(srv.url + "/index.html", wait_until="load")
            page.wait_for_timeout(500)
            load_video(page, WORK / "src-1920x1080.webm")
            seek_paused(page, 1.0)
            page.evaluate("() => fitToWindow()")
            page.wait_for_timeout(250)
            for zoom in (0.79, 1.0, 1.12, 2.0):
                page.evaluate("(z) => setZoom(z)", zoom)
                page.wait_for_timeout(200)
                s = page.evaluate(SHARP_JS)
                covers = (s["backing"][0] + 0.5 >= s["need"][0]
                          and s["backing"][1] + 0.5 >= s["need"][1])
                record("sharp", f"DPR {dpr:g} zoom {zoom:g} covers display pixels",
                       f"backing={s['backing']} css={s['css']} need={s['need']} "
                       f"source={s['source']} caps={s['previewMax']}px/"
                       f"{s['previewMaxPixels'] / 1e6:.2f}MP "
                       f"needCap={s['needMax']}px",
                       covers)
            browser.close()

    result = {"rows": rows, "problems": problems,
              "budgets": {"delta_p50": DELTA_P50_BUDGET,
                          "fps_ratio": FPS_RATIO_BUDGET,
                          "interval_extra_ms": INTERVAL_EXTRA_BUDGET,
                          "pause_p90_extra_ms": PAUSE_P90_EXTRA_BUDGET,
                          "pause_max_extra_ms": PAUSE_MAX_EXTRA_BUDGET,
                          "min_renders_5s": MIN_RENDERS},
              "windows": window_log}
    (EVIDENCE / "g23.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{len(rows)} checks, {len(problems)} failure(s) [G23]")
    if problems:
        print("G23 FAIL")
        return 1
    print("G23 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
