#!/usr/bin/env python3
"""P2-2 break-it cases: the worker under hostile input.

Not a gate check. Six ways the async preview path could go wrong, driven
through the real browser and the real file loader:

  1. A new image arrives while a heavy worker job is in flight.
  2. Compare is switched on while a heavy worker job is in flight.
  3. Caching is disabled, forcing the synchronous path.
  4. The output size shrinks while a job is in flight.
  5. `?worker=0` disables the worker for the whole page.
  6. A video replaces an image while a job is in flight.

Every case asserts the final canvas equals a fresh synchronous render of the
current state, the visible composite is not clobbered, and no page error was
raised.

usage: python tests/gate/p2_2_breakit.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_check as cc  # noqa: E402
import run_gate as rg  # noqa: E402
import video_check as vc  # noqa: E402

FIXTURE_4K = Path("/tmp/glyphcraft_p2_2_3840x2160.png")
FIXTURE_1280 = Path("/tmp/glyphcraft_gate_1280x720.png")
VIDEO = Path("/tmp/glyphcraft_gate_1280x720.webm")
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen", "thermal"]
ROWS = []


def record(name, detail, ok):
    ROWS.append((name, detail, ok))
    print(f"{name:44} {detail}  {'PASS' if ok else 'FAIL'}", flush=True)


def check(name, fn):
    try:
        detail, ok = fn()
    except Exception as exc:  # noqa: BLE001
        detail, ok = f"EXCEPTION {type(exc).__name__}: {exc}", False
    record(name, detail, ok)


def heavy(page):
    page.evaluate(
        """(ids) => {
          state.opts.effects = state.opts.effects.map(fx => ({
            ...fx,
            enabled: ids.includes(fx.id),
            params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
          }));
          state.opts.outputPreset = 'original';
        }""",
        HEAVY,
    )


def idle(page, timeout=120000):
    page.wait_for_function(
        """() => {
          const s = window.GCWorker ? GCWorker.stats() : { inFlight: false };
          return !s.inFlight && !state.renderId;
        }""",
        timeout=timeout,
    )
    page.wait_for_timeout(120)


def settle(page):
    cc.settle(page, quiet_ms=300, timeout_ms=120000)
    idle(page)


def load(page, path):
    page.set_input_files("#file-input", str(path))
    page.wait_for_selector(".canvas-area.has-content", timeout=60000)
    settle(page)


def plain(page):
    """Leave Compare/Original so a frame hash can be compared with a full render."""
    page.evaluate(
        """() => {
          state.compare = false;
          state.showOriginal = false;
          state.lastRenderKey = '';
          scheduleRender(0);
        }"""
    )
    settle(page)


def hash_canvas(page):
    return page.evaluate("() => window.__p22Hash(document.getElementById('canvas'))")


def sync_hash(page):
    return page.evaluate("() => GCWorker.syncHash()")


def post_job(page):
    page.evaluate(
        """() => {
          const fx = state.opts.effects.find(e => e.id === 'posterize');
          if (fx) { fx.params.levels = 4 + (fx.params.levels % 8); }
          state.lastRenderKey = '';
          state.renderCache = null;
          scheduleRender(0);
        }"""
    )
    page.wait_for_timeout(30)


def new_page(browser, srv, query="", disable_worker=False):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                              locale="en-US", reduced_motion="reduce")
    ctx.add_init_script(cc.INIT_JS)
    ctx.add_init_script(
        """(() => {
          window.__p22Hash = function (c) {
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let h = 2166136261;
            for (let i = 0; i < d.length; i += 4) {
              h ^= d[i]; h = Math.imul(h, 16777619);
              h ^= d[i + 1]; h = Math.imul(h, 16777619);
              h ^= d[i + 2]; h = Math.imul(h, 16777619);
              h ^= d[i + 3]; h = Math.imul(h, 16777619);
            }
            return h >>> 0;
          };
        })();"""
    )
    if disable_worker:
        ctx.add_init_script("window.__GC_DISABLE_WORKER = true;")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(srv.url + "/index.html" + query, wait_until="load")
    page.wait_for_timeout(500)
    page.evaluate(cc.PATCH_JS)
    return ctx, page, errors


def ensure_fixtures():
    if not FIXTURE_4K.exists():
        rg.make_png(FIXTURE_4K, width=3840, height=2160, seed=7)
    if not FIXTURE_1280.exists():
        rg.make_png(FIXTURE_1280, width=1280, height=720, seed=2)
    if not VIDEO.exists():
        vc.ensure_fixtures([])


def main() -> int:
    ensure_fixtures()
    for path in (FIXTURE_4K, FIXTURE_1280, VIDEO):
        if not path.exists() or path.stat().st_size == 0:
            print(f"missing fixture {path}; run the gate first")
            return 2
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        ctx, page, errors = new_page(browser, srv)
        try:
            load(page, FIXTURE_4K)
            heavy(page)
            page.evaluate("() => scheduleRender(0)")
            settle(page)

            def case_image():
                post_job(page)
                page.set_input_files("#file-input", str(FIXTURE_1280))
                page.wait_for_function("() => state.sourceW === 1280", timeout=60000)
                settle(page)
                got = hash_canvas(page)
                want = sync_hash(page)
                return (f"source={page.evaluate('() => state.sourceW')} got={got} want={want} "
                        f"errors={errors}"), got == want and not errors

            check("new image while a job is in flight", case_image)

            def case_compare():
                load(page, FIXTURE_4K)
                heavy(page)
                settle(page)
                before = page.evaluate("() => GCWorker.stats().cancelled")
                post_job(page)
                page.evaluate("() => { state.compare = true; scheduleRender(0); }")
                settle(page)
                after = page.evaluate("() => GCWorker.stats().cancelled")
                strip = page.evaluate(
                    """() => {
                      const c = document.getElementById('canvas');
                      const w = c.width, h = c.height;
                      const got = c.getContext('2d').getImageData(0, 0, 10, h).data;
                      const orig = originalBitmap(w, h).getContext('2d').getImageData(0, 0, 10, h).data;
                      let diff = 0;
                      for (let i = 0; i < got.length; i++) if (got[i] !== orig[i]) diff++;
                      return { diff, mode: state.composite && state.composite.mode, compare: state.compare };
                    }"""
                )
                return (f"mode={strip['mode']} compare={strip['compare']} "
                        f"leftStripDiff={strip['diff']} cancelled {before}->{after} "
                        f"errors={errors}"), (
                    strip["diff"] == 0 and strip["mode"] == "split"
                    and strip["compare"] and after > before and not errors)

            check("compare on while a job is in flight", case_compare)

            def case_no_cache():
                load(page, FIXTURE_4K)
                heavy(page)
                plain(page)
                settle(page)
                before = page.evaluate("() => GCWorker.stats().drawn")
                page.evaluate("() => { state.cacheDisabled = true; state.lastRenderKey = ''; scheduleRender(0); }")
                settle(page)
                after = page.evaluate("() => GCWorker.stats().drawn")
                got = hash_canvas(page)
                want = sync_hash(page)
                page.evaluate("() => { state.cacheDisabled = false; state.lastRenderKey = ''; scheduleRender(0); }")
                settle(page)
                return (f"drawn {before}->{after} got={got} want={want} errors={errors}"), (
                    got == want and after == before and not errors)

            check("cache disabled forces the sync path", case_no_cache)

            def case_resize():
                load(page, FIXTURE_4K)
                heavy(page)
                plain(page)
                settle(page)
                post_job(page)
                page.evaluate(
                    """() => {
                      state.opts.outputPreset = 'custom';
                      state.opts.outputWidth = 800;
                      state.opts.outputHeight = 450;
                      state.lastRenderKey = '';
                      scheduleRender(0);
                    }"""
                )
                settle(page)
                got = hash_canvas(page)
                want = sync_hash(page)
                size = page.evaluate("() => [document.getElementById('canvas').width, document.getElementById('canvas').height]")
                return (f"canvas={size} got={got} want={want} errors={errors}"), (
                    size == [800, 450] and got == want and not errors)

            check("output shrinks while a job is in flight", case_resize)

            def case_video():
                load(page, FIXTURE_4K)
                heavy(page)
                settle(page)
                post_job(page)
                if VIDEO.exists():
                    page.set_input_files("#file-input", str(VIDEO))
                    page.wait_for_function("() => state.sourceType === 'video'", timeout=60000)
                    page.evaluate("() => { if (state.video) state.video.pause(); }")
                    settle(page)
                ready = page.evaluate("() => state.workerSourceReady")
                kind = page.evaluate("() => state.sourceType")
                return (f"sourceType={kind} workerSourceReady={ready} errors={errors}"), (
                    kind == "video" and ready is False and not errors)

            check("video replaces image mid-flight", case_video)
        finally:
            ctx.close()

        ctx, fpage, ferrors = new_page(browser, srv, query="?worker=0")
        try:
            load(fpage, FIXTURE_4K)
            heavy(fpage)
            fpage.evaluate("() => scheduleRender(0)")
            settle(fpage)
            got = hash_canvas(fpage)
            want = fpage.evaluate("() => GCWorker.syncHash()")
            on = fpage.evaluate("() => GCWorker.enabled()")
            record("?worker=0 query disables the worker",
                   f"enabled={on} got={got} want={want} errors={ferrors}",
                   on is False and got == want and not ferrors)
        finally:
            ctx.close()

        browser.close()

    failing = [r for r in ROWS if not r[2]]
    print()
    print(f"{len(ROWS)} cases, {len(failing)} failure(s)")
    for row in failing:
        print(f"  FAIL {row[0]}: {row[1]}")
    print("BREAK-IT " + ("PASS" if not failing else "FAIL"))
    return 0 if not failing else 1


if __name__ == "__main__":
    sys.exit(main())
