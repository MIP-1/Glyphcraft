#!/usr/bin/env python3
"""P2-2 closeout item 4: worker path and fallback in Firefox."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path.cwd() / "tests" / "gate"))
import compare_check as cc
import p2_2_check as pc

def main():
    pc.ensure_fixture()
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        print("firefox", browser.version)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  locale="en-US", reduced_motion="reduce")
        ctx.add_init_script(cc.INIT_JS)
        ctx.add_init_script(pc.INIT_JS)
        page = ctx.new_page()
        errs, cons = [], []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: cons.append(f"{m.type}: {m.text}"))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(1200)
        page.evaluate(cc.PATCH_JS)
        cc.load(page, pc.FIXTURE_4K)
        pc.set_heavy(page)
        page.evaluate("() => { state.opts.outputPreset = 'original'; scheduleRender(0); }")
        cc.settle(page, quiet_ms=400, timeout_ms=120000)
        pc.wait_idle(page)
        enabled = page.evaluate("() => GCWorker && GCWorker.enabled ? GCWorker.enabled() : false")
        stats = pc.stats(page)
        pc.reset_caches(page)
        sync_hash = page.evaluate("() => GCWorker.syncHash()")
        pc.reset_caches(page)
        worker_hash = page.evaluate("() => GCWorker.asyncHash()")
        pc.wait_idle(page)
        print("worker enabled", enabled)
        print("stats", stats)
        print("sync", sync_hash, "async", worker_hash, "equal", sync_hash == worker_hash)
        print("pageerrors", errs)
        print("console errors", [c for c in cons if c.startswith("error")])
        ctx.close()

        # Forced fallback in Firefox.
        fctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                   locale="en-US", reduced_motion="reduce")
        fctx.add_init_script(cc.INIT_JS)
        fctx.add_init_script(pc.INIT_JS)
        fctx.add_init_script("window.__GC_DISABLE_WORKER = true;")
        fpage = fctx.new_page()
        ferrs = []
        fpage.on("pageerror", lambda e: ferrs.append(str(e)))
        fpage.goto(srv.url + "/index.html", wait_until="load")
        fpage.wait_for_timeout(700)
        fpage.evaluate(cc.PATCH_JS)
        cc.load(fpage, pc.FIXTURE_4K)
        pc.set_heavy(fpage)
        fpage.evaluate("() => { state.opts.outputPreset = 'original'; scheduleRender(0); }")
        cc.settle(fpage, quiet_ms=400, timeout_ms=120000)
        on = fpage.evaluate("() => GCWorker && GCWorker.enabled ? GCWorker.enabled() : false")
        canvas_hash = pc.hash_canvas(fpage)
        sync2 = fpage.evaluate("() => GCWorker.syncHash()")
        print("fallback enabled", on, "canvas", canvas_hash, "sync", sync2,
              "equal", canvas_hash == sync2, "errors", ferrs)
        fctx.close()
        browser.close()

if __name__ == "__main__":
    main()
