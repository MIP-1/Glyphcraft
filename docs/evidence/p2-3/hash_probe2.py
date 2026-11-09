#!/usr/bin/env python3
"""Reproduce G19's two hashes on one tree: fresh-state vs post-drag state."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path.cwd() / "tests" / "gate"))
import compare_check as cc
import p2_2_check as pc

FIXTURE = pc.FIXTURE_4K

def main():
    pc.ensure_fixture()
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  locale="en-US", reduced_motion="reduce")
        ctx.add_init_script(cc.INIT_JS)
        ctx.add_init_script(pc.INIT_JS)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(500)
        page.evaluate(cc.PATCH_JS)
        cc.load(page, FIXTURE)
        pc.set_heavy(page)
        page.evaluate("() => { state.opts.outputPreset = 'original'; scheduleRender(0); }")
        cc.settle(page, quiet_ms=300, timeout_ms=120000)
        pc.wait_idle(page)
        depth0 = page.evaluate("() => document.getElementById('depth').value")
        pc.reset_caches(page)
        hash0 = page.evaluate("() => GCWorker.syncHash()")
        # Same drag G19 runs before its parity check.
        longs, scroll = pc.drag_with_measurements(page)
        pc.wait_idle(page)
        depth1 = page.evaluate("() => document.getElementById('depth').value")
        pc.reset_caches(page)
        hash1 = page.evaluate("() => GCWorker.syncHash()")
        pc.reset_caches(page)
        hash1b = page.evaluate("() => GCWorker.syncHash()")
        page.evaluate("(d) => { const el = document.getElementById('depth'); el.value = d; el.dispatchEvent(new Event('input', {bubbles:true})); }", depth0)
        page.wait_for_timeout(400)
        pc.wait_idle(page)
        pc.reset_caches(page)
        hash_restored = page.evaluate("() => GCWorker.syncHash()")
        print("viewport_canvas", page.evaluate("() => [state.sourceW, state.sourceH, document.getElementById('canvas').width, document.getElementById('canvas').height]"))
        print("depth before drag", depth0, "after drag", depth1)
        print("hash fresh/default-depth", hash0)
        print("hash post-drag", hash1, "repeat", hash1b)
        print("hash depth restored", hash_restored)
        print("long tasks", longs, "errors", errs)
        browser.close()

if __name__ == "__main__":
    main()
