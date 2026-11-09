#!/usr/bin/env python3
"""What the page actually requests over http, and whether blocking Google Fonts is safe."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path.cwd() / "tests" / "gate"))
import compare_check as cc

def collect(browser, srv, block_google):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                              locale="en-US", reduced_motion="reduce")
    page = ctx.new_page()
    reqs, errs, cons = [], [], []
    page.on("request", lambda r: reqs.append(r.url))
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: cons.append(f"{m.type}: {m.text}"))
    if block_google:
        page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
        page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page.goto(srv.url + "/index.html", wait_until="load")
    page.wait_for_timeout(2500)
    page.evaluate("() => document.fonts.ready")
    state = page.evaluate("""() => ({
      logo: getComputedStyle(document.querySelector('.brand, .logo, .brand-name') || document.body).fontFamily,
      ui: getComputedStyle(document.querySelector('.panel') || document.body).fontFamily,
      mono: getComputedStyle(document.querySelector('.control-unit') || document.body).fontFamily,
      canvasW: document.getElementById('canvas').width,
      app: !!window.state
    })""")
    ctx.close()
    own = [u for u in reqs if u.startswith(srv.url)]
    third = [u for u in reqs if not u.startswith(srv.url)]
    return {"blocked": block_google, "own": own, "third_party": third,
            "pageerrors": errs, "console_errors": [c for c in cons if c.startswith("error")],
            "state": state}

def main():
    with cc.Server() as srv, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        print("NORMAL")
        for k, v in collect(b, srv, False).items():
            print(f"  {k}: {v}")
        print("GOOGLE FONTS BLOCKED")
        for k, v in collect(b, srv, True).items():
            print(f"  {k}: {v}")
        b.close()

if __name__ == "__main__":
    main()
