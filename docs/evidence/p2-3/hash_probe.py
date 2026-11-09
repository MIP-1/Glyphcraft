#!/usr/bin/env python3
"""Explain the P2-2 G19 hash change: ImageBitmap path vs HTMLImageElement path."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path.cwd() / "tests" / "gate"))
import compare_check as cc

FIXTURE = Path("/tmp/glyphcraft_p2_2_3840x2160.png")
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen", "thermal"]

HASH_JS = r"""
() => {
  const c = document.getElementById('canvas');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let h = 2166136261;
  for (let i = 0; i < d.length; i += 4) {
    h ^= d[i]; h = Math.imul(h, 16777619);
    h ^= d[i+1]; h = Math.imul(h, 16777619);
    h ^= d[i+2]; h = Math.imul(h, 16777619);
    h ^= d[i+3]; h = Math.imul(h, 16777619);
  }
  return {hash: h >>> 0, w: c.width, h: c.height,
          source: state.previewSource ? 'bitmap' : 'element'};
}
"""

def main():
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  locale="en-US", reduced_motion="reduce")
        ctx.add_init_script(cc.INIT_JS)
        ctx.add_init_script("window.__GC_DISABLE_WORKER = true;")
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(500)
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
        cc.settle(page, quiet_ms=400, timeout_ms=120000)
        page.wait_for_timeout(500)
        bitmap = page.evaluate(HASH_JS)

        page.evaluate("""() => {
          state.previewSource = null;
          state.lastRenderKey = '';
          state.renderCache = null;
          state.composite = null;
          if (typeof clearStageCache === 'function') clearStageCache();
          render();
        }""")
        page.wait_for_timeout(300)
        element = page.evaluate(HASH_JS)
        print("bitmap_path", bitmap)
        print("element_path", element)
        print("errors", errs)
        browser.close()

if __name__ == "__main__":
    main()
