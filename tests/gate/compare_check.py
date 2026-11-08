#!/usr/bin/env python3
"""H3 Compare / before-after acceptance (permanent gate check G11).

Measures, in a real browser with real mouse/keyboard events:
 1. Toggle cost and leaks (long tasks, pipeline invocations, listeners,
    canvases, heap, idle rAF) on 1280x720 and 4000x3000, plain and with a
    six-effect stack.
 2. Handle grab reliability: 50 presses at random heights x 3 zoom levels,
    hit-area width, pointer capture, touch-action, z-index/pointer-events,
    44px hit area under touch emulation.
 3. Drag frame times (median, and the paired delta against the same pointer
    storm with nothing listening) and zero pipeline invocations during the drag.
 4. Split position correctness after zoom, pan, resize, a value change and
    undo/redo.

usage: python tests/gate/compare_check.py
"""
import functools
import random
import statistics
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path("/tmp/glyphcraft_gate_fixture.png")
FIXTURE_4K = Path("/tmp/glyphcraft_gate_4k.png")
FIXTURE_1280 = Path("/tmp/glyphcraft_gate_1280x720.png")

HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen"]

# What a drag is allowed to cost over the same pointer storm with nothing
# listening. Measured as the median of five paired (control, drag) windows, so
# a background stall that also delays a plain rAF loop cancels out. The drag
# repaints the split band, not the frame, so the honest budget is a fraction of
# a refresh.
DRAG_DELTA_MEDIAN_MS = 2.0
# Wall-clock p95 on a 60 Hz loop is bimodal (16.7 or 33.3) and a single missed
# vsync moves it by a whole refresh; at load 7 on 4 cores the control window
# still reports 16.8 while the drag window reports 33.3 with the app spending
# 0.5 ms per move. The drag's own cost is therefore measured inside render():
# 0.5 ms median and ~2 ms p90 for a 1600x1200 split. A build that re-runs the
# frame pipeline per pointer move spends 100+ ms per render here.
DRAG_RENDER_P90_MS = 4.0

INIT_JS = r"""
(() => {
  const P = window.__perf = {
    pipeline: 0, renders: 0, renderMs: [], longtasks: [], raf: 0,
    ltFrom: 0,
    canvasCreated: 0, getImageData: 0, gidBytes: 0, toDataURL: 0,
    listeners: [],
  };
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        // Chromium can deliver an entry well after the task ended. Attribute
        // it to the window it started in, not the window it arrived in.
        if (e.startTime >= P.ltFrom) P.longtasks.push(+e.duration.toFixed(1));
      }
    }).observe({ entryTypes: ["longtask"] });
  } catch (err) {}
  const create = Document.prototype.createElement;
  Document.prototype.createElement = function (tag, ...a) {
    const el = create.call(this, tag, ...a);
    if (String(tag).toLowerCase() === "canvas") P.canvasCreated++;
    return el;
  };
  const gid = CanvasRenderingContext2D.prototype.getImageData;
  CanvasRenderingContext2D.prototype.getImageData = function (x, y, w, h, ...r) {
    P.getImageData++;
    P.gidBytes += (w | 0) * (h | 0) * 4;
    return gid.call(this, x, y, w, h, ...r);
  };
  const tdu = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function (...a) {
    P.toDataURL++;
    return tdu.apply(this, a);
  };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    return raf((t) => { P.raf++; return cb(t); });
  };
  const add = EventTarget.prototype.addEventListener;
  const rem = EventTarget.prototype.removeEventListener;
  const tracked = (t) => t === window || (t && t.nodeType === 9);
  EventTarget.prototype.addEventListener = function (type, fn, opt) {
    if (tracked(this)) {
      const cap = !!(opt === true || (opt && opt.capture));
      if (!P.listeners.some((l) => l.t === this && l.type === type && l.fn === fn && l.cap === cap))
        P.listeners.push({ t: this, type, fn, cap });
    }
    return add.call(this, type, fn, opt);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, opt) {
    if (tracked(this)) {
      const cap = !!(opt === true || (opt && opt.capture));
      P.listeners = P.listeners.filter((l) => !(l.t === this && l.type === type && l.fn === fn && l.cap === cap));
    }
    return rem.call(this, type, fn, opt);
  };
})();
"""

PATCH_JS = r"""
() => {
  const orig = window.prepareBase;
  window.prepareBase = function (...a) {
    window.__perf.pipeline++;
    return orig.apply(this, a);
  };
  const r = window.render;
  window.render = function (...a) {
    const t0 = performance.now();
    try { return r.apply(this, a); }
    finally { window.__perf.renders++; window.__perf.renderMs.push(+(performance.now() - t0).toFixed(1)); }
  };
}
"""


def blank_page(problems, label):
    problems.append(f"{label}: blank/black canvas")
    return True


class Server:
    def __enter__(self):
        class Q(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def wait_worker(page, timeout_ms=30000):
    """Wait for the P2-2 async render queue to drain (no-op without a worker).

    Measurements that follow a state change must describe the settled frame.
    The worker path is asynchronous, so the render counter alone is not enough.
    """
    page.wait_for_function(
        """() => {
          if (!window.GCWorker || typeof GCWorker.stats !== 'function') return true;
          const s = GCWorker.stats();
          return !s.inFlight && !s.pending;
        }""",
        timeout=timeout_ms,
    )


def settle(page, quiet_ms=220, timeout_ms=15000):
    """Wait until the render counter has been stable for quiet_ms."""
    # `__settleStart` was never assigned, so the timeout clause was always true
    # once the page was older than `timeout`: settle returned immediately and
    # callers measured renders that were still in flight.
    page.evaluate(
        """() => {
          window.__settleN = window.__perf ? window.__perf.renders : 0;
          window.__settleAt = performance.now();
          window.__settleStart = performance.now();
        }"""
    )
    page.wait_for_function(
        """([quiet, timeout]) => {
          const now = performance.now();
          const n = window.__perf ? window.__perf.renders : 0;
          if (window.__settleN !== n) { window.__settleN = n; window.__settleAt = now; return false; }
          return now - window.__settleAt >= quiet || now - window.__settleStart > timeout;
        }""",
        arg=[quiet_ms, timeout_ms],
        timeout=timeout_ms + 5000,
    )
    wait_worker(page, timeout_ms=timeout_ms + 5000)


def reset(page):
    page.evaluate("""() => {
      const P = __perf;
      P.pipeline = 0; P.renders = 0; P.renderMs = []; P.longtasks = [];
      P.raf = 0; P.canvasCreated = 0; P.getImageData = 0; P.gidBytes = 0; P.toDataURL = 0;
      P.ltFrom = performance.now();
      window.__settleN = -1; window.__settleStart = performance.now();
    }""")


def perf(page):
    return page.evaluate("""() => ({
      pipeline: __perf.pipeline, renders: __perf.renders,
      renderMs: __perf.renderMs.slice(), longtasks: __perf.longtasks.slice(),
      raf: __perf.raf, canvasCreated: __perf.canvasCreated,
      getImageData: __perf.getImageData, gidBytes: __perf.gidBytes,
      toDataURL: __perf.toDataURL, listeners: __perf.listeners.length
    })""")


def toggle(page):
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    page.keyboard.press("c")


def ensure_compare(page, on=True):
    if page.evaluate("() => state.compare") != on:
        toggle(page)
        settle(page)


def load(page, path):
    page.set_input_files("#file-input", str(path))
    page.wait_for_selector(".canvas-area.has-content", timeout=40000)
    settle(page)


def enable_effects(page, ids):
    for eid in ids:
        item = page.locator(f'.effect-item[data-id="{eid}"]')
        item.scroll_into_view_if_needed()
        box = item.locator('input[type="checkbox"]')
        if not box.is_checked():
            box.check()
            page.wait_for_timeout(80)
    settle(page)


def set_frac(page, frac):
    """Drag the handle to a fraction using real mouse events."""
    box = page.locator("#compare-slider").bounding_box()
    area = page.locator("#canvas-area").bounding_box()
    cx = area["x"] + box["x"] - area["x"]  # box is already viewport-relative
    x = area["x"] + (box["x"] - area["x"])
    # start from the current handle position and drag to the target fraction
    start = page.evaluate("() => state.compareFrac")
    x0 = area["x"] + page.evaluate("() => state.pan.x + document.getElementById('canvas').width * state.scale * state.compareFrac")
    target = page.evaluate(
        "(f) => { const a = document.getElementById('canvas-area').getBoundingClientRect();"
        " return a.left + state.pan.x + document.getElementById('canvas').width * state.scale * f; }",
        frac,
    )
    y = box["y"] + box["height"] / 2
    page.mouse.move(x0, y)
    page.mouse.down()
    page.mouse.move(target, y, steps=4)
    page.mouse.up()
    settle(page)
    return start


def drag_frames(page, frames=180, span=260, warmup=60):
    """Drive a real 3 s pointer drag through the slider's own handlers.

    The moves are dispatched from a requestAnimationFrame loop inside the
    page. Pacing them from Python over CDP added transport jitter: a drag with
    *zero* effects on the same machine produced 33 ms rAF intervals and
    55-59 ms long tasks, so the old check measured the driver, not the app.

    The gesture opens with an out-and-back warm-up inside the *same* pointer
    down, and only the following 3 s window is recorded. A separate pointer
    down restarted the compositor transient (two 33 ms frames) every time.
    The thresholds are unchanged and the events still travel through the real
    pointerdown/pointermove/pointerup handlers.
    """
    return page.evaluate(
        """({frames, span, warmup}) => new Promise((resolve) => {
          const slider = document.getElementById('compare-slider');
          const box = slider.getBoundingClientRect();
          const y = box.top + box.height / 2;
          const x0 = box.left + box.width / 2;
          const samples = [];
          let last = performance.now();
          let i = 0;
          let warm = true;
          const send = (type, x, buttons) => slider.dispatchEvent(new PointerEvent(type, {
            bubbles: true, cancelable: true, clientX: x, clientY: y,
            pointerId: 1, pointerType: 'mouse', buttons,
          }));
          const tick = (t) => {
            if (warm) {
              send('pointermove', x0 + 80 * Math.sin(Math.PI * i / warmup), 1);
              i++;
              if (i > warmup) { warm = false; i = 0; last = t; }
              requestAnimationFrame(tick);
              return;
            }
            samples.push(t - last);
            last = t;
            if (i <= frames) {
              send('pointermove', x0 + (i / frames) * span, 1);
              i++;
              requestAnimationFrame(tick);
              return;
            }
            send('pointerup', x0 + span, 0);
            const f = samples.filter((v) => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
            const pick = (p) => f.length ? f[Math.min(f.length - 1, Math.floor(f.length * p))] : null;
            resolve({ frames: f.length, median: pick(0.5), p95: pick(0.95) });
          };
          send('pointerdown', x0, 1);
          requestAnimationFrame(tick);
        })""",
        {"frames": frames, "span": span, "warmup": warmup},
    )


def gesture_frames(page, frames=180, span=260, warmup=60):
    """The same pointermove storm as drag_frames, aimed at the canvas area.

    Nothing listens for these moves (no pointerdown, no compare handle), so the
    cost is the harness + compositor only: the floor for the drag tail. A drag
    that runs the pipeline or drops frames sits above this floor; a desktop
    hiccup that misses a frame shows up in both.
    """
    return page.evaluate(
        """({frames, span, warmup}) => new Promise((resolve) => {
          const el = document.getElementById('canvas-area');
          const box = el.getBoundingClientRect();
          const y = box.top + box.height / 2;
          const x0 = box.left + box.width / 2;
          const samples = [];
          let last = performance.now();
          let i = 0;
          let warm = true;
          const send = (x) => el.dispatchEvent(new PointerEvent('pointermove', {
            bubbles: true, cancelable: true, clientX: x, clientY: y,
            pointerId: 2, pointerType: 'mouse', buttons: 0,
          }));
          const tick = (t) => {
            if (warm) {
              send(x0 + 80 * Math.sin(Math.PI * i / warmup));
              i++;
              if (i > warmup) { warm = false; i = 0; last = t; }
              requestAnimationFrame(tick);
              return;
            }
            samples.push(t - last);
            last = t;
            if (i <= frames) { send(x0 + (i / frames) * span); i++; requestAnimationFrame(tick); return; }
            const f = samples.filter((v) => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
            const pick = (p) => f.length ? f[Math.min(f.length - 1, Math.floor(f.length * p))] : null;
            resolve({ frames: f.length, median: pick(0.5), p95: pick(0.95) });
          };
          requestAnimationFrame(tick);
        })""",
        {"frames": frames, "span": span, "warmup": warmup},
    )


def main() -> int:
    problems = []
    rows = []

    # The gate creates the shared fixture; standalone runs must too.
    if not FIXTURE.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import run_gate  # noqa: E402
        run_gate.make_png(FIXTURE, width=900, height=600, seed=0)
    if not FIXTURE_4K.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import run_gate  # noqa: E402
        run_gate.make_png(FIXTURE_4K, width=4000, height=3000, seed=5)
    FIXTURE_1280.parent.mkdir(parents=True, exist_ok=True)
    Image.open(FIXTURE).convert("RGB").resize((1280, 720)).save(FIXTURE_1280)

    with Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_init_script(INIT_JS)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.evaluate(PATCH_JS)
        ready = page.evaluate("() => typeof window.prepareBase === 'function' && !!window.__perf")
        if not ready:
            print("FAIL instrumentation did not attach")
            return 1

        def record(name, detail, ok):
            rows.append((name, detail, ok))
            if not ok:
                problems.append(f"{name}: {detail}")

        # ------------------------------------------------------------------
        # 1. Toggle cost, on 1280x720 and 4K, plain and with a heavy stack
        # ------------------------------------------------------------------
        cases = []
        for path, label in ((FIXTURE_1280, "1280x720"), (FIXTURE_4K, "4K")):
            load(page, path)
            cases.append((label + " default", path, []))
        # measure plain first, then heavy on the already loaded 4K image
        for label, path, effects in cases:
            reset(page)
            toggle(page)
            settle(page)
            on = perf(page)
            reset(page)
            toggle(page)
            settle(page)
            off = perf(page)
            worst = max(on["longtasks"] + off["longtasks"] + [0])
            ok = worst < 100 and on["pipeline"] <= 2 and off["pipeline"] <= 2
            record(
                f"toggle {label}",
                f"on pipeline={on['pipeline']} longest={max(on['longtasks'] + [0])}ms "
                f"allocs={on['canvasCreated']} | "
                f"off pipeline={off['pipeline']} longest={max(off['longtasks'] + [0])}ms "
                f"allocs={off['canvasCreated']}",
                ok,
            )

        load(page, FIXTURE_4K)
        enable_effects(page, HEAVY)
        reset(page)
        toggle(page)
        settle(page)
        on = perf(page)
        reset(page)
        toggle(page)
        settle(page)
        off = perf(page)
        worst = max(on["longtasks"] + off["longtasks"] + [0])
        record(
            "toggle 4K heavy",
            f"on pipeline={on['pipeline']} longest={max(on['longtasks'] + [0])}ms "
            f"allocs={on['canvasCreated']} | "
            f"off pipeline={off['pipeline']} longest={max(off['longtasks'] + [0])}ms "
            f"allocs={off['canvasCreated']}",
            worst < 100 and on["pipeline"] <= 2 and off["pipeline"] <= 2,
        )

        # ------------------------------------------------------------------
        # 1b. 20 toggles: listeners / canvases / heap / cumulative allocations
        # ------------------------------------------------------------------
        cdp = ctx.new_cdp_session(page)
        ensure_compare(page, False)
        cdp.send("HeapProfiler.collectGarbage")
        heap0 = cdp.send("Runtime.getHeapUsage")["usedSize"]
        before = perf(page)
        dom0 = page.evaluate("() => document.querySelectorAll('canvas').length")
        page.evaluate("() => { __perf.canvasCreated = 0; }")
        for _ in range(20):
            toggle(page)
            settle(page, quiet_ms=90, timeout_ms=8000)
        settle(page)
        after = perf(page)
        dom1 = page.evaluate("() => document.querySelectorAll('canvas').length")
        cdp.send("HeapProfiler.collectGarbage")
        heap1 = cdp.send("Runtime.getHeapUsage")["usedSize"]
        listeners_delta = after["listeners"] - before["listeners"]
        heap_delta = (heap1 - heap0) / max(1, heap0) * 100
        ok = (abs(listeners_delta) <= max(1, before["listeners"] * 0.05)
              and dom1 == dom0 and abs(heap_delta) <= 5
              and after["canvasCreated"] <= 2)
        record(
            "20 toggles leak",
            f"listeners {before['listeners']}->{after['listeners']} (delta {listeners_delta}), "
            f"DOM canvases {dom0}->{dom1}, heap {heap0/1e6:.1f}->{heap1/1e6:.1f}MB "
            f"({heap_delta:+.1f}%), canvas allocations {after['canvasCreated']}",
            ok,
        )

        # idle rAF
        page.wait_for_timeout(400)
        page.evaluate("() => { __perf.raf = 0; }")
        page.wait_for_timeout(1000)
        idle_raf = page.evaluate("() => __perf.raf")
        record("idle rAF after toggles", f"{idle_raf} callbacks/s", idle_raf == 0)

        # ------------------------------------------------------------------
        # 2. Handle: hit area, capture, touch-action, z-index, grab 50x x 3 zooms
        # ------------------------------------------------------------------
        load(page, FIXTURE_1280)
        page.evaluate("() => { state.opts.effects = []; scheduleRender(0); }")
        settle(page)
        reset(page); ensure_compare(page, True)
        box = page.locator("#compare-slider").bounding_box()
        mid_y = box["y"] + box["height"] / 2
        mid_x = box["x"] + box["width"] / 2
        # Probe the width away from the 20px knob at mid-height, which would
        # otherwise let a 4px line pass the +-10px assertion.
        edge_y = box["y"] + box["height"] * 0.25
        probe = page.evaluate(
            """([x, y]) => {
              const el = document.elementFromPoint(x, y);
              const s = document.getElementById('compare-slider');
              return { id: el && el.id, inside: !!(el && (el === s || s.contains(el))) };
            }""",
            [mid_x, edge_y],
        )
        half = 10
        edge = page.evaluate(
            """([x, y, dx]) => {
              const s = document.getElementById('compare-slider');
              const el = document.elementFromPoint(x + dx, y);
              return !!(el && (el === s || s.contains(el)));
            }""",
            [mid_x, edge_y, half],
        )
        style = page.evaluate(
            """() => {
              const s = getComputedStyle(document.getElementById('compare-slider'));
              const o = getComputedStyle(document.getElementById('compare-overlay'));
              return { width: parseFloat(s.width), touch: s.touchAction,
                       pointer: s.pointerEvents, z: parseInt(s.zIndex, 10),
                       overlayPointer: o.pointerEvents, overlayZ: parseInt(o.zIndex, 10) };
            }"""
        )
        record(
            "hit area + styles",
            f"width={style['width']}px, center hit={probe['inside']}, +-{half}px hit={edge}, "
            f"touch-action={style['touch']}, pointer-events={style['pointer']}, "
            f"z={style['z']} overlay z={style['overlayZ']} pointer={style['overlayPointer']}",
            style["width"] >= 24 and probe["inside"] and edge and style["touch"] == "none"
            and style["pointer"] == "auto" and style["z"] > style["overlayZ"]
            and style["overlayPointer"] == "none",
        )

        # pointer capture on pointerdown
        page.evaluate("""() => {
          window.__pid = null;
          const s = document.getElementById('compare-slider');
          s.addEventListener('pointerdown', (e) => { window.__pid = e.pointerId; }, { capture: true, once: true });
        }""")
        page.mouse.move(mid_x, mid_y)
        page.mouse.down()
        captured = page.evaluate("""() => {
          const s = document.getElementById('compare-slider');
          return window.__pid != null && s.hasPointerCapture(window.__pid);
        }""")
        page.mouse.up()
        record("pointer capture", f"hasPointerCapture={captured}", captured)

        rng = random.Random(20261025)
        zoom_sel = {"1": None, "2": None, "4": '[data-zoom="4"]'}
        for zlabel, menu in zoom_sel.items():
            page.evaluate("() => document.activeElement && document.activeElement.blur()")
            if menu:
                page.click("#zoom-level")
                page.click(".zoom-menu " + menu)
            else:
                page.keyboard.press(zlabel)
            settle(page, quiet_ms=120)
            # A zoomed canvas can push the split outside the visible area; the
            # grab test is about a handle the user can see, so pan it to the
            # middle of the canvas area first.
            page.evaluate("""() => {
              const a = els.canvasArea.getBoundingClientRect();
              state.pan.x = a.width / 2 - els.canvas.width * state.scale * state.compareFrac;
              applyTransform();
            }""")
            settle(page, quiet_ms=120)
            area = page.locator("#canvas-area").bounding_box()
            box = page.locator("#compare-slider").bounding_box()
            ok_count = 0
            misses = []
            for idx in range(50):
                box = page.locator("#compare-slider").bounding_box()
                # Press only where the handle is actually on screen: the box
                # is unclipped, but the canvas area clips it at every zoom.
                top = max(box["y"], area["y"], 0) + 1
                bottom = min(box["y"] + box["height"], area["y"] + area["height"], 1000) - 1
                y = top + rng.random() * max(1.0, bottom - top)
                x = box["x"] + box["width"] / 2
                before_frac = page.evaluate("() => state.compareFrac")
                page.mouse.move(x, y)
                page.mouse.down()
                direction = 40 if idx % 2 == 0 else -40
                page.mouse.move(x + direction, y)
                page.mouse.up()
                page.wait_for_timeout(25)
                after_frac = page.evaluate("() => state.compareFrac")
                if abs(after_frac - before_frac) > 0.005:
                    ok_count += 1
                else:
                    misses.append((round(y, 1), before_frac, after_frac))
            record(
                f"grab zoom {zlabel}00%",
                f"{ok_count}/50 drags started (misses {misses[:3]})",
                ok_count == 50,
            )
            # restore a middle split for the next zoom without relying on a
            # handle that may now be scrolled out of view
            page.evaluate("() => { state.compareFrac = 0.5; updateCompareUI(); }")

        # touch width (44px requirement)
        tctx = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        tctx.add_init_script(INIT_JS)
        tpage = tctx.new_page()
        tpage.goto(srv.url + "/index.html", wait_until="load")
        tpage.wait_for_timeout(300)
        tpage.evaluate(PATCH_JS)
        load(tpage, FIXTURE_1280)
        reset(tpage); ensure_compare(tpage, True)
        tw = tpage.locator("#compare-slider").bounding_box()["width"]
        tstyle = tpage.evaluate("() => getComputedStyle(document.getElementById('compare-slider')).touchAction")
        record("touch hit area", f"width={tw}px touch-action={tstyle}", tw >= 44 and tstyle == "none")
        tctx.close()

        # ------------------------------------------------------------------
        # 3. Drag performance, 0 pipeline invocations
        # ------------------------------------------------------------------
        for label, path, effects in (("1280x720", FIXTURE_1280, []),
                                     ("4K heavy", FIXTURE_4K, HEAVY)):
            load(page, path)
            if effects:
                enable_effects(page, effects)
            else:
                page.evaluate("() => { state.opts.effects = []; scheduleRender(0); }")
                settle(page)
            reset(page); ensure_compare(page, True)
            set_frac(page, 0.2)
            # The 20-toggle and handle-grab checks leave garbage behind; a GC
            # during the drag shows up as a dropped frame. Settle it before the
            # measured windows rather than attributing it to the app.
            cdp.send("HeapProfiler.collectGarbage")
            page.wait_for_timeout(150)
            # Five paired windows. The same pointer volume with nothing
            # listening (no pointerdown, no compare handle) is the floor: a
            # desktop stall that delays a plain rAF loop shows up in both
            # windows and cancels in the paired delta, while work the drag does
            # per move does not. A single absolute p95 bound was measuring the
            # desktop: one 3 s window with a background stall failed at 33.3 ms
            # while the control window in the same session sat at 16.8 ms.
            pairs = []
            for _ in range(5):
                ctrl = gesture_frames(page)
                page.evaluate(
                    "() => { state.compareFrac = 0.2; updateCompareUI(); scheduleRender(0); }"
                )
                settle(page, quiet_ms=80)
                reset(page)
                fr = drag_frames(page)
                settle(page, quiet_ms=80)
                dr = perf(page)
                pairs.append((fr, ctrl, dr))

            def median_of(vals):
                vals = sorted(v for v in vals if v is not None)
                return vals[len(vals) // 2] if vals else None

            def pct(vals, q):
                return vals[min(len(vals) - 1, int(len(vals) * q))] if vals else None

            drags = [fr for fr, _, _ in pairs]
            ctrls = [ctrl for _, ctrl, _ in pairs]
            med = median_of([d["median"] for d in drags])
            p95 = median_of([d["p95"] for d in drags])
            ctl_med = median_of([c["median"] for c in ctrls])
            ctl_p95 = median_of([c["p95"] for c in ctrls])
            d_med = median_of([d["median"] - c["median"] for d, c in zip(drags, ctrls)])
            d_p95 = median_of([d["p95"] - c["p95"] for d, c in zip(drags, ctrls)])
            pipeline = sum(dr["pipeline"] for _, _, dr in pairs)
            gid = sum(dr["getImageData"] for _, _, dr in pairs)
            tdu = sum(dr["toDataURL"] for _, _, dr in pairs)
            longest = max((max(dr["longtasks"] + [0]) for _, _, dr in pairs), default=0)
            render_ms = sorted(m for _, _, dr in pairs for m in dr["renderMs"])
            r_p50 = pct(render_ms, 0.5)
            r_p90 = pct(render_ms, 0.9)
            r_max = render_ms[-1] if render_ms else None
            pair_p95 = [(round(d["p95"], 1), round(c["p95"], 1)) for d, c in zip(drags, ctrls)]
            # The frame interval is reported as 16.700000000000728 on some
            # runs; 0.1 ms is float tolerance for "one refresh", not a
            # relaxation (two frames is 33.4 ms).
            med_limit = 16.8 if label == "1280x720" else 20
            ok = (med is not None and med <= med_limit
                  and d_med is not None and d_med <= DRAG_DELTA_MEDIAN_MS
                  and r_p90 is not None and r_p90 <= DRAG_RENDER_P90_MS
                  and pipeline == 0 and gid == 0)
            record(
                f"drag {label}",
                f"frames={sum(d['frames'] for d in drags)} "
                f"median={None if med is None else round(med, 1)}ms(limit {med_limit}) "
                f"delta_median={None if d_med is None else round(d_med, 1)}ms(limit {DRAG_DELTA_MEDIAN_MS}) "
                f"p95={None if p95 is None else round(p95, 1)}ms delta_p95={None if d_p95 is None else round(d_p95, 1)}ms "
                f"gesture_control p50={None if ctl_med is None else round(ctl_med, 1)}ms "
                f"p95={None if ctl_p95 is None else round(ctl_p95, 1)}ms "
                f"pairs={pair_p95} "
                f"render p50={r_p50}ms p90={r_p90}ms(limit {DRAG_RENDER_P90_MS}) max={r_max}ms "
                f"pipeline={pipeline} getImageData={gid} "
                f"toDataURL={tdu} longest={longest}ms",
                ok,
            )

        # ------------------------------------------------------------------
        # 3b. A split drag repaints only the moved band, and the result is
        #     pixel-identical to compositing both full frames.
        # ------------------------------------------------------------------
        page.evaluate("""() => {
          if (!CanvasRenderingContext2D.prototype.__diCounted) {
            const d = CanvasRenderingContext2D.prototype.drawImage;
            CanvasRenderingContext2D.prototype.drawImage = function (...a) {
              window.__di = (window.__di || 0) + 1;
              return d.apply(this, a);
            };
            CanvasRenderingContext2D.prototype.__diCounted = true;
          }
          window.__di = 0;
        }""")
        walk = page.evaluate(
            """(frac) => new Promise((resolve) => {
              const slider = document.getElementById('compare-slider');
              const area = document.getElementById('canvas-area').getBoundingClientRect();
              const box = slider.getBoundingClientRect();
              const y = box.top + box.height / 2;
              const cw = document.getElementById('canvas').width * state.scale;
              const start = area.left + state.pan.x + cw * state.compareFrac;
              const target = area.left + state.pan.x + cw * frac;
              const steps = 10;
              let i = 0;
              const send = (type, x, buttons) => slider.dispatchEvent(new PointerEvent(type, {
                bubbles: true, cancelable: true, clientX: x, clientY: y,
                pointerId: 9, pointerType: 'mouse', buttons,
              }));
              send('pointerdown', start, 1);
              const tick = () => {
                if (i <= steps) {
                  send('pointermove', start + (target - start) * (i / steps), 1);
                  i++;
                  requestAnimationFrame(tick);
                  return;
                }
                send('pointerup', target, 0);
                requestAnimationFrame(() => requestAnimationFrame(() => resolve({
                  frac: state.compareFrac,
                  mode: state.composite && state.composite.mode,
                  draws: window.__di,
                })));
              };
              requestAnimationFrame(tick);
            })""",
            0.72,
        )
        # Rebuild the same frame the slow way: full frame, then the original
        # over the left side. Any difference means the band repaint is wrong.
        pixels = page.evaluate("""() => {
          const c = document.getElementById('canvas');
          const w = c.width, h = c.height;
          const x = Math.round(w * state.compareFrac);
          const got = c.getContext('2d').getImageData(0, 0, w, h).data;
          const off = document.createElement('canvas');
          off.width = w; off.height = h;
          const o = off.getContext('2d');
          o.drawImage(state.renderCache.canvas, 0, 0);
          const orig = originalBitmap(w, h);
          if (orig) {
            o.save(); o.beginPath(); o.rect(0, 0, x, h); o.clip();
            o.drawImage(orig, 0, 0, w, h); o.restore();
          }
          const want = o.getImageData(0, 0, w, h).data;
          let diff = 0, maxd = 0;
          for (let i = 0; i < got.length; i += 4) {
            const d = Math.abs(got[i] - want[i]) + Math.abs(got[i + 1] - want[i + 1])
                    + Math.abs(got[i + 2] - want[i + 2]);
            if (d) { diff++; if (d > maxd) maxd = d; }
          }
          return { w, h, x, diff, maxd, shared: c === state.renderCache.canvas };
        }""")
        record(
            "split strip redraw",
            f"{pixels['w']}x{pixels['h']} split x={pixels['x']} "
            f"drawImage per 10 moves={walk['draws']} mode={walk['mode']} "
            f"pixels differing={pixels['diff']} (max {pixels['maxd']})",
            pixels["diff"] == 0 and walk["mode"] == "split" and walk["draws"] <= 12,
        )

        # ------------------------------------------------------------------
        # 4. Split correctness after zoom / pan / resize / value / undo
        # ------------------------------------------------------------------
        load(page, FIXTURE_1280)
        page.evaluate("() => { state.opts.effects = []; scheduleRender(0); }")
        settle(page)
        reset(page); ensure_compare(page, True)
        set_frac(page, 0.35)

        def check_split(tag):
            data = page.evaluate("""() => {
              const c = document.getElementById('canvas');
              const expected = state.pan.x + c.width * state.scale * state.compareFrac;
              const left = parseFloat(document.getElementById('compare-slider').style.left);
              const hidden = document.getElementById('compare-overlay').hidden;
              return { frac: state.compareFrac, expected, left, hidden, compare: state.compare };
            }""")
            ok = (not data["hidden"] and data["compare"]
                  and abs(data["left"] - data["expected"]) <= 1
                  and abs(data["frac"] - 0.35) <= 0.01)
            record(f"split {tag}", f"frac={data['frac']:.3f} left={data['left']:.1f} "
                                    f"expected={data['expected']:.1f} hidden={data['hidden']}", ok)
            return ok

        check_split("initial")
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.keyboard.press("2")
        settle(page, quiet_ms=120)
        check_split("zoom 200%")
        # pan with the middle button (image no longer fits)
        page.mouse.move(700, 500)
        page.mouse.down(button="middle")
        page.mouse.move(760, 540, steps=4)
        page.mouse.up(button="middle")
        settle(page, quiet_ms=120)
        check_split("pan")
        page.set_viewport_size({"width": 1100, "height": 800})
        page.wait_for_timeout(350)
        check_split("resize")
        page.evaluate("""() => {
          state.opts.adj.brightness = 25;
          scheduleRender(0);
        }""")
        settle(page)
        check_split("value change")
        page.keyboard.press("Control+z")
        settle(page)
        check_split("undo")
        page.keyboard.press("Control+Shift+z")
        settle(page)
        check_split("redo")

        if errors:
            problems.extend(f"PAGE ERROR {e}" for e in errors[:10])
        browser.close()

    width = max(len(r[0]) for r in rows) + 2
    for name, detail, ok in rows:
        print(f"{name:{width}} {detail:112} {'PASS' if ok else 'FAIL'}")
    print()
    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    for problem in problems:
        print("  FAIL " + problem)
    print("COMPARE " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
