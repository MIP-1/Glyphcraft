#!/usr/bin/env python3
"""H4 load baseline and acceptance (permanent gate check G12).

Measures, in real Chromium with real pointer input:
  (a) idle 5 s with an image and with a paused video: rAF callbacks, timers,
      observers, long tasks, renderer task ms;
  (b) a 3 s slider drag: renders, ms/render, task ms;
  (c) 30 rapid stepper clicks: renders vs animation frames, final value;
  (d) 100 random value changes: heap after forced GC, DOM canvas count;
  (e) paused video CPU activity;
  plus stage-cache counters, 20-stack output identity, and the cached-drag gain.

usage:
  python tests/gate/load_check.py            # acceptance (gate)
  python tests/gate/load_check.py --baseline # numbers only, writes JSON
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_check as C  # noqa: E402

ROOT = C.ROOT
OUT = ROOT / "docs" / "evidence" / "h4"
FIXTURE_1080 = Path("/tmp/glyphcraft_gate_1920x1080.png")
VIDEO = Path("/tmp/glyphcraft_test.webm")
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen"]
# These runners use Math.random(), so two renders of the same stack are not
# byte-identical even without a cache. Identity is asserted on the other 17.
RANDOM_EFFECTS = {"glitch", "vhs", "pixelsort", "grain", "matrix"}

LOAD_JS = r"""
() => {
  window.__load = { raf: 0, timeouts: 0, intervals: 0, frames: 0 };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    window.__load.raf++;
    return raf((t) => { window.__load.frames++; return cb(t); });
  };
  const st = window.setTimeout.bind(window);
  window.setTimeout = function (fn, d, ...a) {
    window.__load.timeouts++;
    return st(fn, d, ...a);
  };
  const si = window.setInterval.bind(window);
  window.setInterval = function (fn, d, ...a) {
    window.__load.intervals++;
    return si(fn, d, ...a);
  };
  window.__hashCanvas = function (c) {
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    let h = 2166136261;
    for (let i = 0; i < d.length; i += 4) {
      h ^= d[i]; h = Math.imul(h, 16777619);
      h ^= d[i + 1]; h = Math.imul(h, 16777619);
      h ^= d[i + 2]; h = Math.imul(h, 16777619);
      h ^= d[i + 3]; h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  };
  window.__resetLoad = function () {
    __load.raf = 0; __load.timeouts = 0; __load.intervals = 0; __load.frames = 0;
    __perf.longtasks = []; __perf.renders = 0; __perf.renderMs = [];
    window.__ltFrom = performance.now();
    __perf.pipeline = 0; __perf.canvasCreated = 0;
  };
  // Works on both the pre-H4 tree (frame cache only) and the H4 tree.
  window.__resetCaches = function () {
    if (typeof window.clearStageCache === 'function') window.clearStageCache();
    try { state.renderCache = null; state.lastRenderKey = ''; } catch (e) {}
  };
  window.__lt = [];
  window.__ltFrom = 0;
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__lt.push({ d: e.duration, t: e.startTime });
    }).observe({ entryTypes: ['longtask'] });
  } catch (e) {}
  window.__stageCounts = {};
  for (const id of Object.keys(EFFECT_RUNNERS)) {
    const run = EFFECT_RUNNERS[id];
    EFFECT_RUNNERS[id] = function (...a) {
      window.__stageCounts[id] = (window.__stageCounts[id] || 0) + 1;
      return run.apply(this, a);
    };
  }
}
"""


def perf_metrics(cdp):
    names = ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration")
    m = {row["name"]: row["value"] for row in cdp.send("Performance.getMetrics")["metrics"]}
    return {n: round(m.get(n, 0.0), 4) for n in names}


def snapshot(page, cdp, seconds=5, label=""):
    page.evaluate("() => window.__resetLoad()")
    before = perf_metrics(cdp)
    page.wait_for_timeout(seconds * 1000)
    after = perf_metrics(cdp)
    load = page.evaluate("() => ({...__load, longtasks: window.__lt.filter(e => e.t >= window.__ltFrom).map(e => +e.d.toFixed(1))})")
    load["longtask_ms"] = round(sum(load["longtasks"]), 1)
    load["longest_ms"] = round(max(load["longtasks"] + [0]), 1)
    load["task_ms"] = round((after["TaskDuration"] - before["TaskDuration"]) * 1000, 1)
    load["script_ms"] = round((after["ScriptDuration"] - before["ScriptDuration"]) * 1000, 1)
    load["label"] = label
    return load


def load_image(page, size):
    # Clear first so re-selecting the same file still fires change.
    page.evaluate("() => { document.getElementById('file-input').value = ''; }")
    page.set_input_files("#file-input", str(size))
    page.wait_for_selector(".canvas-area.has-content", timeout=60000)
    C.settle(page)


def load_video(page):
    page.evaluate("() => { document.getElementById('file-input').value = ''; }")
    page.set_input_files("#file-input", str(VIDEO))
    page.wait_for_selector(".canvas-area.has-content", timeout=60000)
    page.wait_for_timeout(800)


def set_heavy(page, ids=None):
    page.evaluate(
        """(ids) => {
          state.opts.effects = state.opts.effects.map(fx => ({
            ...fx,
            enabled: ids.includes(fx.id),
            params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
          }));
          renderEffectsList();
          window.__resetCaches();
          scheduleRender(0);
        }""",
        ids or HEAVY,
    )
    C.settle(page, quiet_ms=250, timeout_ms=60000)


def drag_slider(page, selector, cdp, duration_ms=3000):
    # Park the control at its maximum first, render that state, then drag from
    # 15% to 85%: the final value is guaranteed to differ, so the measurement
    # cannot collapse into a cached frame.
    page.evaluate("""(sel) => {
      const el = document.querySelector(sel);
      el.value = el.max;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }""", selector)
    page.wait_for_timeout(250)
    C.settle(page, quiet_ms=250, timeout_ms=60000)
    page.evaluate("() => window.__resetLoad()")
    before = perf_metrics(cdp)
    # The control may be below the panel fold; a drag must land on it.
    page.locator(selector).scroll_into_view_if_needed()
    page.wait_for_timeout(120)
    box = page.locator(selector).bounding_box()
    y = box["y"] + box["height"] / 2
    x0 = box["x"] + box["width"] * 0.15
    x1 = box["x"] + box["width"] * 0.85
    page.mouse.move(x0, y)
    page.mouse.down()
    steps = max(10, duration_ms // 20)
    for i in range(1, steps + 1):
        x = x0 + (x1 - x0) * i / steps
        page.mouse.move(x, y)
        page.wait_for_timeout(max(0, duration_ms // steps - 4))
    page.mouse.up()
    page.wait_for_timeout(400)
    after = perf_metrics(cdp)
    p = C.perf(page)
    ms = p["renderMs"] or [0]
    return {
        "renders": p["renders"],
        "avg_ms": round(sum(ms) / len(ms), 2),
        "max_ms": round(max(ms), 2),
        "pipeline": p["pipeline"],
        "longtask_ms": round(sum(p["longtasks"]), 1),
        "longest_ms": round(max(p["longtasks"] + [0]), 1),
        "task_ms": round((after["TaskDuration"] - before["TaskDuration"]) * 1000, 1),
        "frames": page.evaluate("() => window.__load.frames"),
    }


def stepper_burst(page, selector, clicks=30, gap_ms=25):
    page.evaluate("() => window.__resetLoad()")
    start = page.evaluate(
        "(s) => { const el = document.querySelector(s); return Number(el.value); }", "#depth"
    )
    page.locator(selector).scroll_into_view_if_needed()
    page.wait_for_timeout(120)
    box = page.locator(selector).bounding_box()
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] * 0.25
    for _ in range(clicks):
        page.mouse.click(x, y)
        page.wait_for_timeout(gap_ms)
    page.wait_for_timeout(400)
    end = page.evaluate("() => Number(document.querySelector('#depth').value)")
    frames = page.evaluate("() => window.__load.frames")
    renders = page.evaluate("() => __perf.renders")
    return {"start": start, "end": end, "frames": frames, "renders": renders,
            "expected": min(240, start + clicks)}


def random_changes(page, count=100):
    page.evaluate(
        """(count) => {
          const ids = ['#depth', '#char-offset', '#cell-size', '#glyph-weight'];
          for (let i = 0; i < count; i++) {
            const el = document.querySelector(ids[i % ids.length]);
            if (!el) continue;
            const min = Number(el.min), max = Number(el.max);
            el.value = String(Math.round(min + Math.random() * (max - min)));
            el.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }""",
        count,
    )
    page.wait_for_timeout(600)
    C.settle(page, quiet_ms=250, timeout_ms=30000)


def random_stack(page, rng):
    page.evaluate("(ids) => { window.__randomEffects = ids; }", sorted(RANDOM_EFFECTS))
    page.evaluate(
        """(rngState) => {
          let s = rngState;
          const rand = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
          const all = EFFECTS.map(e => e.id).filter(id => !window.__randomEffects.includes(id));
          const picked = [];
          const want = 3 + Math.floor(rand() * 4);
          while (picked.length < want) {
            const id = all[Math.floor(rand() * all.length)];
            if (!picked.includes(id)) picked.push(id);
          }
          state.opts.effects = state.opts.effects.map(fx => {
            if (!picked.includes(fx.id)) return { ...fx, enabled: false };
            const params = {};
            const def = EFFECTS.find(e => e.id === fx.id);
            for (const p of (def.params || [])) {
              if (p.type === 'color') params[p.key] = p.def || '#000000';
              else if (p.type === 'select') params[p.key] = p.def || (p.options && p.options[0] && p.options[0][0]);
              else {
                const min = Number(p.min), max = Number(p.max), step = Number(p.step) || 1;
                const raw = min + rand() * (max - min);
                params[p.key] = Math.round(raw / step) * step;
              }
            }
            return { ...fx, enabled: true, params };
          });
          window.__resetCaches();
        }""",
        rng,
    )
    C.settle(page, quiet_ms=250, timeout_ms=60000)


def hash_frame(page):
    return page.evaluate("() => window.__hashCanvas(document.getElementById('canvas'))")


def stage_counts(page):
    return page.evaluate("() => ({...window.__stageCounts})")


def reset_stage_counts(page):
    page.evaluate("() => { window.__stageCounts = {}; }")


def visibility(page, hidden):
    page.evaluate(
        """(hidden) => {
          try {
            Object.defineProperty(document, 'visibilityState', {
              configurable: true, get: () => hidden ? 'hidden' : 'visible',
            });
            Object.defineProperty(document, 'hidden', {
              configurable: true, get: () => hidden,
            });
          } catch (e) {}
          document.dispatchEvent(new Event('visibilitychange'));
        }""",
        hidden,
    )
    page.wait_for_timeout(300)


def main() -> int:
    baseline = "--baseline" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    problems = []

    if not FIXTURE_1080.exists():
        from PIL import Image
        Image.open(C.FIXTURE).convert("RGB").resize((1920, 1080)).save(FIXTURE_1080)

    def record(name, detail, ok):
        rows.append((name, detail, ok))
        print(("PASS " if ok else "FAIL ") + name + " — " + detail)
        if not ok and not baseline:
            problems.append(f"{name}: {detail}")

    with C.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_init_script(C.INIT_JS)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.evaluate(C.PATCH_JS)
        page.evaluate(LOAD_JS)
        cdp = ctx.new_cdp_session(page)
        cdp.send("Performance.enable")

        data = {"fixtures": {}, "idle": {}, "drags": {}, "stepper": {}, "memory": {},
                "video": {}, "stages": {}, "identity": {}, "gain": {}}

        # (a) idle on 1920x1080 and 4K, six effects
        for label, path in (("1920x1080", FIXTURE_1080), ("4K", C.FIXTURE_4K)):
            load_image(page, path)
            set_heavy(page)
            shot = snapshot(page, cdp, 5, "idle " + label)
            data["idle"][label] = shot
            record(f"idle {label}", f"rAF={shot['raf']} frames={shot['frames']} "
                   f"timeouts={shot['timeouts']} intervals={shot['intervals']} "
                   f"longtask={shot['longtask_ms']}ms task={shot['task_ms']}ms",
                   shot["raf"] == 0 and shot["timeouts"] == 0 and shot["intervals"] == 0
                   if not baseline else True)

        # (b) a real 3 s drag of the Script depth slider on both sizes. Every
        # frame changes the Script stage but no effect, so this is the drag the
        # stage cache is meant to make cheap. (Effect-parameter sliders are
        # debounced by 100 ms in the UI, so they cannot produce per-frame cost.)
        for label, path in (("1920x1080", FIXTURE_1080), ("4K", C.FIXTURE_4K)):
            load_image(page, path)
            set_heavy(page)
            data["drags"][label] = drag_slider(page, "#depth", cdp)
            record("drag depth " + label, json.dumps(data["drags"][label]), True)

        # Per-render gain: the full pipeline (cold) against a render that
        # changes only the last effect while every earlier stage is warm.
        cold_runs = page.evaluate("""() => {
          const out = [];
          for (let i = 0; i < 3; i++) {
            state.cacheDisabled = true;
            window.__resetCaches();
            const t0 = performance.now();
            render();
            out.push(+(performance.now() - t0).toFixed(2));
          }
          state.cacheDisabled = false;
          window.__resetCaches();
          return out;
        }""")
        warm_runs = page.evaluate("""() => {
          const out = [];
          const fx = state.opts.effects.find(e => e.id === 'sharpen');
          for (let i = 0; i < 3; i++) {
            state.cacheDisabled = false;
            window.__resetCaches();
            render();
            fx.params.amount = 40 + i * 7;
            const t0 = performance.now();
            render();
            out.push(+(performance.now() - t0).toFixed(2));
          }
          return out;
        }""")
        cold = sorted(cold_runs)[1]
        warm_last = sorted(warm_runs)[1]
        drag_avg = data["drags"]["4K"]["avg_ms"]
        data["gain"] = {"cold_render_ms": cold, "cold_runs": cold_runs,
                        "warm_last_effect_ms": warm_last, "warm_runs": warm_runs,
                        "drag_avg_4k_ms": drag_avg,
                        "warm_ratio": round(warm_last / cold, 3) if cold else None,
                        "drag_ratio": round(drag_avg / cold, 3) if cold else None}
        record("last-effect render gain",
               f"cold={cold}ms warm_last_effect={warm_last}ms "
               f"({round((1 - warm_last / cold) * 100, 1) if cold else 0}% lower)",
               warm_last <= cold * 0.7 if not baseline else True)
        record("drag render gain",
               f"cold={cold}ms drag_avg_4k={drag_avg}ms "
               f"({round((1 - drag_avg / cold) * 100, 1) if cold else 0}% lower)",
               drag_avg <= cold * 0.7 if not baseline else True)

        # (c) 30 rapid stepper clicks
        page.evaluate("() => { const el = document.querySelector('#depth'); el.value = 80; el.dispatchEvent(new Event('input', {bubbles:true})); }")
        C.settle(page, quiet_ms=150, timeout_ms=20000)
        data["stepper"] = stepper_burst(page, 'button.stepper[data-control="depth-num"]')
        st = data["stepper"]
        record("30 stepper clicks", f"start={st['start']} end={st['end']} expected={st['expected']} "
               f"renders={st['renders']} frames={st['frames']}",
               st["end"] == st["expected"] and st["renders"] <= max(1, st["frames"])
               if not baseline else True)

        # coalescing: 50 changes in one frame -> one render of the latest value
        page.evaluate("() => window.__resetLoad()")
        page.evaluate("""() => {
          const el = document.querySelector('#depth');
          for (let i = 0; i < 50; i++) {
            el.value = String(60 + i);
            el.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }""")
        page.wait_for_timeout(500)
        coalesce_renders = page.evaluate("() => __perf.renders")
        coalesce_value = page.evaluate("() => Number(document.querySelector('#depth').value)")
        data["coalesce"] = {"renders": coalesce_renders, "value": coalesce_value}
        record("50 changes in one frame", f"renders={coalesce_renders} value={coalesce_value}",
               coalesce_renders == 1 and coalesce_value == 109 if not baseline else True)

        # item 1: a render whose state key is unchanged is skipped entirely
        hash_before = page.evaluate("() => window.__hashCanvas(document.getElementById('canvas'))")
        page.evaluate("() => window.__resetLoad()")
        page.evaluate("() => { render(); render(); }")
        skip = page.evaluate("() => ({renders: __perf.renders, pipeline: __perf.pipeline})")
        hash_after = page.evaluate("() => window.__hashCanvas(document.getElementById('canvas'))")
        data["unchanged"] = {"renders": skip["renders"], "pipeline": skip["pipeline"],
                             "same": hash_before == hash_after}
        record("unchanged state skips the render",
               f"pipeline={skip['pipeline']} render calls={skip['renders']} "
               f"canvas same={hash_before == hash_after}",
               skip["pipeline"] == 0 and hash_before == hash_after if not baseline else True)

        # (d) 100 changes then forced GC
        cdp.send("HeapProfiler.collectGarbage")
        heap0 = cdp.send("Runtime.getHeapUsage")["usedSize"]
        canvas0 = page.evaluate("() => document.querySelectorAll('canvas').length")
        random_changes(page, 100)
        cdp.send("HeapProfiler.collectGarbage")
        heap1 = cdp.send("Runtime.getHeapUsage")["usedSize"]
        canvas1 = page.evaluate("() => document.querySelectorAll('canvas').length")
        pct = (heap1 - heap0) / max(1, heap0) * 100
        data["memory"] = {"heap0": heap0, "heap1": heap1, "pct": round(pct, 2),
                          "canvas0": canvas0, "canvas1": canvas1}
        record("100 changes memory", f"heap {heap0/1e6:.1f}->{heap1/1e6:.1f}MB "
               f"({pct:+.1f}%), DOM canvases {canvas0}->{canvas1}",
               pct <= 20 and canvas0 == canvas1 if not baseline else True)

        # (e) video loaded and paused
        load_video(page)
        page.evaluate("() => { if (state.video) state.video.pause(); }")
        page.wait_for_timeout(400)
        shot = snapshot(page, cdp, 5, "video paused")
        data["video"] = shot
        record("paused video idle", f"rAF={shot['raf']} frames={shot['frames']} "
               f"timeouts={shot['timeouts']} intervals={shot['intervals']} "
               f"longtask={shot['longtask_ms']}ms task={shot['task_ms']}ms",
               shot["raf"] == 0 and shot["timeouts"] == 0 and shot["intervals"] == 0
               if not baseline else True)

        # hidden tab with a playing video: 0 rAF / timers (simulated visibility)
        load_video(page)
        page.evaluate("() => { if (state.video) state.video.play().catch(() => {}); }")
        page.wait_for_timeout(400)
        visibility(page, True)
        shot = snapshot(page, cdp, 3, "hidden")
        visibility(page, False)
        data["idle"]["hidden"] = shot
        record("hidden tab idle", f"rAF={shot['raf']} timeouts={shot['timeouts']} "
               f"intervals={shot['intervals']} task={shot['task_ms']}ms",
               shot["raf"] == 0 and shot["timeouts"] == 0 and shot["intervals"] == 0
               if not baseline else True)

        # stage cache: last effect 1 stage, first effect all 6
        load_image(page, FIXTURE_1080)
        set_heavy(page)
        page.evaluate("""() => {
          state.cacheDisabled = false; window.__resetCaches(); render();
        }""")
        reset_stage_counts(page)
        page.evaluate("""() => {
          const fx = state.opts.effects.find(e => e.id === 'sharpen');
          fx.params.amount = (Number(fx.params.amount) || 50) + 1;
          render();
        }""")
        last = stage_counts(page)
        reset_stage_counts(page)
        page.evaluate("""() => {
          const fx = state.opts.effects.find(e => e.id === 'posterize');
          fx.params.levels = Math.max(3, (Number(fx.params.levels) || 8) - 1);
          render();
        }""")
        first = stage_counts(page)
        data["stages"] = {"last": last, "first": first}
        record("stage cache last effect", json.dumps(last),
               sum(last.values()) == 1 if not baseline else True)
        record("stage cache first effect", json.dumps(first),
               sum(first.values()) == len(HEAVY) if not baseline else True)

        # identity: 20 random stacks, cache on vs cache off
        rng = 20261026
        mismatches = []
        for i in range(20):
            random_stack(page, rng + i * 7919)
            # warm the stage cache, then measure a render that reuses it
            page.evaluate("""() => {
              state.cacheDisabled = false; window.__resetCaches(); render();
            }""")
            h1 = page.evaluate("""() => {
              window.__resetCaches();
              render();
              return window.__hashCanvas(document.getElementById('canvas'));
            }""")
            # the same stack with every cache bypassed
            h2 = page.evaluate("""() => {
              state.cacheDisabled = true; window.__resetCaches();
              render();
              return window.__hashCanvas(document.getElementById('canvas'));
            }""")
            page.evaluate("() => { state.cacheDisabled = false; }")
            if h1 != h2:
                mismatches.append((i, h1, h2))
        page.evaluate("() => { state.cacheDisabled = false; }")
        data["identity"] = {"mismatches": mismatches, "stacks": 20}
        record("20 stacks identical output", f"{20 - len(mismatches)}/20 match",
               not mismatches if not baseline else True)

        if errors:
            problems.extend("PAGE ERROR " + e for e in errors)
        browser.close()

    data["baseline"] = baseline
    data["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    name = "baseline.json" if baseline else "acceptance.json"
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n")

    print("")
    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    print("LOAD " + ("BASELINE" if baseline else ("PASS" if not problems else "FAIL")))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
