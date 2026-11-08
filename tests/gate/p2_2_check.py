#!/usr/bin/env python3
"""P2-2 acceptance (permanent gate check G19): Worker + OffscreenCanvas.

Four acceptance checks from docs/prompts/part2_performance_core.md:

  1. A 3 s real slider drag with >= 6 heavy effects on a 3840x2160 image
     produces no long task > 50 ms on the main thread; the panel still
     scrolls while the worker renders.
  2. Worker output equals a main-thread render pixel for pixel (hash).
  3. 20 rapid updates: only the latest result is drawn, earlier jobs are
     cancelled, and the final canvas hash matches the latest state.
  4. With Worker/OffscreenCanvas disabled the app still renders the same
     pixels and raises no page error.

The two job types reserved for P2-3 (preview and full) are also driven.

usage: python tests/gate/p2_2_check.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_check as cc  # noqa: E402
import run_gate as rg  # noqa: E402

FIXTURE_4K = Path("/tmp/glyphcraft_p2_2_3840x2160.png")
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen", "thermal"]
SHOTS = rg.ROOT / "docs" / "evidence" / "p2-2"

ROWS = []
PROBLEMS = []


def record(name, detail, ok):
    ROWS.append((name, detail, ok))
    print(f"{name:38} {detail}  {'PASS' if ok else 'FAIL'}", flush=True)
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def check(name, fn):
    """Run one acceptance check; a missing feature is a FAIL row, not a crash."""
    try:
        detail, ok = fn()
    except Exception as exc:  # noqa: BLE001 - the exception text is the evidence
        detail, ok = f"EXCEPTION {type(exc).__name__}: {exc}", False
    record(name, detail, ok)
    return ok


def ensure_fixture():
    if FIXTURE_4K.exists() and FIXTURE_4K.stat().st_size > 0:
        return
    t0 = time.time()
    rg.make_png(FIXTURE_4K, width=3840, height=2160, seed=7)
    print(f"fixture 3840x2160 in {time.time() - t0:.1f}s", flush=True)


INIT_JS = r"""
(() => {
  window.__p22 = { lt: [], from: 0 };
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        window.__p22.lt.push({ d: +e.duration.toFixed(1), t: e.startTime });
      }
    }).observe({ entryTypes: ["longtask"] });
  } catch (e) {}
  window.__p22Reset = function () {
    window.__p22.lt = [];
    window.__p22.from = performance.now();
  };
  window.__p22Long = function () {
    return window.__p22.lt
      .filter((e) => e.t >= window.__p22.from)
      .map((e) => e.d);
  };
  window.__p22Hash = function (c) {
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
})();
"""


def hash_canvas(page):
    return page.evaluate("() => window.__p22Hash(document.getElementById('canvas'))")


def set_heavy(page):
    page.evaluate(
        """(ids) => {
          state.opts.effects = state.opts.effects.map(fx => ({
            ...fx,
            enabled: ids.includes(fx.id),
            params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
          }));
        }""",
        HEAVY,
    )


def reset_caches(page):
    page.evaluate(
        """() => {
          if (typeof clearStageCache === 'function') clearStageCache();
          state.renderCache = null;
          state.lastRenderKey = '';
          state.composite = null;
        }"""
    )


def wait_idle(page, timeout=120000):
    page.wait_for_function(
        """() => {
          const s = window.GCWorker ? GCWorker.stats() : { inFlight: false };
          return !s.inFlight && !state.renderId;
        }""",
        timeout=timeout,
    )
    page.wait_for_timeout(120)


def drag_with_measurements(page):
    """Real 3 s pointer drag of the Script depth slider, with scroll probes."""
    slider = page.locator("#depth")
    slider.scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    before = page.evaluate("() => Number(document.getElementById('depth').value)")
    box = slider.bounding_box()
    y = box["y"] + box["height"] / 2
    x0 = box["x"] + 8
    x1 = box["x"] + box["width"] - 8
    scroll = {"changed": 0, "samples": 0, "max_rt_ms": 0.0}
    page.evaluate("() => window.__p22Reset()")
    page.mouse.move(x0, y)
    page.mouse.down()
    steps = 140
    for i in range(1, steps + 1):
        x = x0 + (x1 - x0) * (0.5 + 0.45 * math.sin(i / 14.0))
        page.mouse.move(x, y)
        page.wait_for_timeout(18)
        if i % 14 == 0:
            t0 = time.perf_counter()
            moved = page.evaluate(
                """() => {
                  const el = document.querySelector('.panel-content');
                  const before = el.scrollTop;
                  el.scrollTop = before + 24;
                  return el.scrollTop !== before;
                }"""
            )
            rt = (time.perf_counter() - t0) * 1000
            scroll["samples"] += 1
            scroll["max_rt_ms"] = max(scroll["max_rt_ms"], round(rt, 1))
            if moved:
                scroll["changed"] += 1
    page.mouse.up()
    longs = page.evaluate("() => window.__p22Long()")
    after = page.evaluate("() => Number(document.getElementById('depth').value)")
    scroll["from"] = before
    scroll["to"] = after
    return longs, scroll


def stats(page):
    return page.evaluate("() => (window.GCWorker ? GCWorker.stats() : null)")


def enabled(page):
    return page.evaluate(
        "() => (window.GCWorker && typeof GCWorker.enabled === 'function' ? GCWorker.enabled() : false)"
    )


def main() -> int:
    ensure_fixture()
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  locale="en-US", reduced_motion="reduce")
        ctx.add_init_script(cc.INIT_JS)
        ctx.add_init_script(INIT_JS)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(500)
        page.evaluate(cc.PATCH_JS)

        cc.load(page, FIXTURE_4K)
        set_heavy(page)
        page.evaluate("() => { state.opts.outputPreset = 'original'; scheduleRender(0); }")
        cc.settle(page, quiet_ms=300, timeout_ms=120000)
        wait_idle(page)

        def check_enabled():
            on = enabled(page)
            s = stats(page)
            same = page.evaluate("() => document.getElementById('canvas').width")
            return f"enabled={on} stats={s} canvasW={same}", bool(on)

        check("worker + OffscreenCanvas enabled", check_enabled)

        def check_drag():
            before = stats(page) or {}
            longs, scroll = drag_with_measurements(page)
            wait_idle(page)
            s = stats(page) or {}
            worst = max(longs + [0])
            over = [v for v in longs if v > 50]
            posted = s.get("posted", 0) - before.get("posted", 0)
            drawn = s.get("drawn", 0) - before.get("drawn", 0)
            cancelled = s.get("cancelled", 0) - before.get("cancelled", 0)
            ok = (bool(s.get("enabled")) and worst <= 50 and len(over) == 0
                  and posted >= 1 and drawn >= 1
                  and scroll["to"] != scroll["from"]
                  and scroll["samples"] > 0 and scroll["changed"] == scroll["samples"])
            return (f"worst={worst}ms over50={len(over)} posted={posted} "
                    f"drawn={drawn} cancelled={cancelled} depth={scroll['from']}->{scroll['to']} "
                    f"scroll={scroll['changed']}/{scroll['samples']} "
                    f"maxRt={scroll['max_rt_ms']}ms"), ok

        check("heavy drag: no long task >50ms", check_drag)

        def check_parity():
            reset_caches(page)
            sync_hash = page.evaluate("() => GCWorker.syncHash()")
            reset_caches(page)
            worker_hash = page.evaluate("() => GCWorker.asyncHash()")
            wait_idle(page)
            return f"sync={sync_hash} worker={worker_hash}", (
                sync_hash == worker_hash and sync_hash not in (0, None))

        check("worker equals main-thread render", check_parity)

        def check_kinds():
            reset_caches(page)
            preview_hash = page.evaluate("() => GCWorker.renderKind('preview')")
            wait_idle(page)
            reset_caches(page)
            full_hash = page.evaluate("() => GCWorker.renderKind('full')")
            wait_idle(page)
            return f"preview={preview_hash} full={full_hash}", (
                preview_hash == full_hash and preview_hash not in (0, None))

        check("preview/full job types agree", check_kinds)

        def check_stale():
            reset_caches(page)
            page.evaluate(
                "() => { if (state.workerStats) { state.workerStats.drawn = 0; state.workerStats.cancelled = 0; } }")
            page.evaluate(
                """() => new Promise((resolve) => {
                  let i = 0;
                  const tick = () => {
                    const fx = state.opts.effects.find(e => e.id === 'posterize');
                    if (fx) { fx.params.levels = 3 + (i % 10); state.opts.effects = state.opts.effects.map(x => ({...x})); }
                    scheduleRender(0);
                    i++;
                    if (i < 20) requestAnimationFrame(tick);
                    else setTimeout(resolve, 60);
                  };
                  requestAnimationFrame(tick);
                })"""
            )
            wait_idle(page)
            final_hash = hash_canvas(page)
            stale = page.evaluate("() => ({ ...(state.workerStats || {}) })")
            expected = page.evaluate("() => GCWorker.syncHash()")
            ok = (stale.get("drawn", 99) <= 2 and stale.get("cancelled", 0) >= 1
                  and final_hash == expected)
            return (f"drawn={stale.get('drawn')} cancelled={stale.get('cancelled')} "
                    f"posted={stale.get('posted')} final={final_hash} expected={expected}"), ok

        check("20 rapid updates: latest only", check_stale)

        def check_fallback():
            fctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                       locale="en-US", reduced_motion="reduce")
            fctx.add_init_script(cc.INIT_JS)
            fctx.add_init_script(INIT_JS)
            fctx.add_init_script("window.__GC_DISABLE_WORKER = true;")
            fpage = fctx.new_page()
            ferrors = []
            fpage.on("pageerror", lambda e: ferrors.append(str(e)))
            try:
                fpage.goto(srv.url + "/index.html", wait_until="load")
                fpage.wait_for_timeout(500)
                fpage.evaluate(cc.PATCH_JS)
                cc.load(fpage, FIXTURE_4K)
                set_heavy(fpage)
                fpage.evaluate("() => { state.opts.outputPreset = 'original'; scheduleRender(0); }")
                cc.settle(fpage, quiet_ms=300, timeout_ms=120000)
                fallback_hash = hash_canvas(fpage)
                on = enabled(fpage)
                same = fpage.evaluate("() => GCWorker.syncHash()")
            finally:
                fctx.close()
            ok = (on is False and fallback_hash == same and not ferrors)
            return (f"workerEnabled={on} hash={fallback_hash} sync={same} "
                    f"errors={ferrors}"), ok

        check("fallback renders the same pixels", check_fallback)

        # Evidence screenshots: heavy stack settled, both themes at 1280/360.
        SHOTS.mkdir(parents=True, exist_ok=True)
        for theme in ("dark", "light"):
            page.evaluate("(t) => setTheme(t)", theme)
            for width in (1280, 360):
                page.set_viewport_size({"width": width, "height": 900 if width > 700 else 740})
                page.wait_for_timeout(500)
                if width <= 700:
                    page.evaluate("() => { if (window.__gcSetSnap) window.__gcSetSnap('half', false); }")
                page.wait_for_timeout(200)
                schedule_js = "() => { if (state.compare) { state.compare = false; state.showOriginal = false; } scheduleRender(0); }"
                page.evaluate(schedule_js)
                wait_idle(page)
                page.screenshot(path=str(SHOTS / f"{theme}-{width}-heavy.png"))

        ctx.close()
        browser.close()

    if errors:
        PROBLEMS.extend(f"PAGE ERROR {e}" for e in errors)
    failing = [r for r in ROWS if not r[2]]
    print()
    print(f"{len(ROWS)} checks, {len(failing)} failure(s)")
    for row in failing:
        print(f"  FAIL {row[0]}: {row[1]}")
    print("WORKER " + ("PASS" if not failing and not PROBLEMS else "FAIL"))
    return 0 if not failing and not PROBLEMS else 1


if __name__ == "__main__":
    sys.exit(main())
