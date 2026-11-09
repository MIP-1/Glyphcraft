#!/usr/bin/env python3
"""P2-2 closeout item 6: index.html over file:// falls back and renders the same pixels."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path.cwd() / "tests" / "gate"))
import compare_check as cc
import p2_2_check as pc

FIXTURE = pc.FIXTURE_4K
HEAVY = pc.HEAVY
ROOT = Path.cwd()


def configure(page):
    page.evaluate(cc.PATCH_JS)
    cc.load(page, FIXTURE)
    page.evaluate("""(ids) => {
      state.opts.effects = state.opts.effects.map(fx => ({
        ...fx, enabled: ids.includes(fx.id),
        params: { ...effectDefaults(fx.id), ...(fx.params || {}) }
      }));
      state.opts.outputPreset = 'original';
      scheduleRender(0);
    }""", HEAVY)
    cc.settle(page, quiet_ms=400, timeout_ms=180000)


def main():
    pc.ensure_fixture()
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Reference: same tree and settings over http with the worker disabled.
        rctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                   locale="en-US", reduced_motion="reduce")
        rctx.add_init_script(cc.INIT_JS)
        rctx.add_init_script(pc.INIT_JS)
        rctx.add_init_script("window.__GC_DISABLE_WORKER = true;")
        rpage = rctx.new_page()
        rerrs = []
        rpage.on("pageerror", lambda e: rerrs.append(str(e)))
        rpage.goto(srv.url + "/index.html", wait_until="load")
        rpage.wait_for_timeout(500)
        configure(rpage)
        ref_hash = pc.hash_canvas(rpage)
        ref_enabled = rpage.evaluate("() => GCWorker.enabled()")
        rctx.close()

        # file://: no init override, so the app must cope with a blocked worker.
        fctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                   locale="en-US", reduced_motion="reduce")
        fctx.add_init_script(cc.INIT_JS)
        fctx.add_init_script(pc.INIT_JS)
        fpage = fctx.new_page()
        ferrs, fcons = [], []
        fpage.on("pageerror", lambda e: ferrs.append(str(e)))
        fpage.on("console", lambda m: fcons.append(f"{m.type}: {m.text}"))
        url = (ROOT / "index.html").as_uri()
        fpage.goto(url, wait_until="load")
        fpage.wait_for_timeout(800)
        configure(fpage)
        pc.wait_idle(fpage)
        file_hash = pc.hash_canvas(fpage)
        enabled = fpage.evaluate("() => (window.GCWorker && GCWorker.enabled ? GCWorker.enabled() : false)")
        stats = fpage.evaluate("() => (window.GCWorker ? GCWorker.stats() : null)")
        integrity = fpage.evaluate("""() => {
          const c = document.getElementById('canvas');
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let nonBlack = 0;
          for (let i = 0; i < d.length; i += 4) {
            if (d[i] || d[i + 1] || d[i + 2]) nonBlack++;
          }
          return {w: c.width, h: c.height, nonBlack,
                  loading: document.querySelector('.canvas-area').classList.contains('has-content'),
                  sourceType: state.sourceType};
        }""")
        shot = ROOT / "docs" / "evidence" / "p2-3" / "file-fallback.png"
        fpage.screenshot(path=str(shot))
        print("file url", url)
        print("reference(worker disabled over http):", ref_hash, "workerEnabled", ref_enabled)
        print("file:// canvas:", file_hash, "workerEnabled", enabled, "stats", stats)
        print("file integrity", integrity)
        print("hash equal", file_hash == ref_hash)
        print("file pageerrors", ferrs)
        print("file console errors", [c for c in fcons if c.startswith("error")])
        print("screenshot", shot.relative_to(ROOT))
        fctx.close()
        browser.close()

if __name__ == "__main__":
    main()
