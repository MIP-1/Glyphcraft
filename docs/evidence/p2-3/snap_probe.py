#!/usr/bin/env python3
"""Why run 3 printed snap='' for the G14 light 740x360 cell."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path.cwd() / "tests" / "gate"))
import compare_check as cc

FIXTURE = Path("/tmp/glyphcraft_gate_fixture.png")

def sample(page):
    return page.evaluate("""() => ({
      snap: document.getElementById('panel').dataset.snap || '',
      mobile: window.matchMedia('(max-width: 700px)').matches,
      width: innerWidth,
      mobileBtn: !!document.getElementById('mobile-menu-btn'),
      sheetH: document.getElementById('panel').getBoundingClientRect().height
    })""")

def run(browser, i):
    ctx = browser.new_context(viewport={"width": 740, "height": 360},
                              color_scheme="light", locale="en-US",
                              reduced_motion="reduce", is_mobile=True,
                              has_touch=True, device_scale_factor=2)
    ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','light')}catch(e){}")
    page = ctx.new_page()
    page.goto(cc.Server and "", wait_until="load") if False else None
    ctx.close()

def main():
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        out = []
        for i in range(3):
            ctx = browser.new_context(viewport={"width": 740, "height": 360},
                                      color_scheme="light", locale="en-US",
                                      reduced_motion="reduce", is_mobile=True,
                                      has_touch=True, device_scale_factor=2)
            ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','light')}catch(e){}")
            page = ctx.new_page()
            page.goto(srv.url + "/index.html", wait_until="load")
            rows = [("after-load", sample(page))]
            page.wait_for_timeout(100)
            before = page.evaluate("() => state.sourceId")
            page.set_input_files("#file-input", str(FIXTURE))
            page.wait_for_selector(".canvas-area.has-content", timeout=30000)
            page.wait_for_function("(id) => state.sourceId > id", arg=before, timeout=30000)
            for wait in (100, 300, 700, 1500):
                page.wait_for_timeout(wait)
                rows.append((f"after+{wait}", sample(page)))
            out.append(rows)
            ctx.close()
        print(json.dumps(out, indent=1))
        browser.close()

if __name__ == "__main__":
    main()
