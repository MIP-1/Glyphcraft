#!/usr/bin/env python3
"""H1 break-it checks: 5 ways the shared stepper could be wrong."""
import functools
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("/home/mustafa/glyphcraft")
FIX = Path("/tmp/opencode/small.png")
FIX4K = Path("/tmp/glyphcraft_gate_4k.png")

STEP = '.stepper[data-control="adj-brightness-num"]'
UP = STEP + ' .step-btn[data-step="up"]'
DOWN = STEP + ' .step-btn[data-step="down"]'


def val(page):
    return page.evaluate("() => +document.getElementById('adj-brightness-num').value")


def state_val(page):
    return page.evaluate("() => state.opts.adj.brightness")


class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}"
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIX))
        page.wait_for_selector(".canvas-area.has-content")
        page.wait_for_timeout(600)
        page.evaluate("""() => { document.querySelectorAll('.panel-section.collapsed').forEach(s => {
          if (getComputedStyle(s).display === 'none') return;
          const t = s.querySelector('.section-title'); if (t) t.click(); }); }""")
        page.wait_for_timeout(300)
        page.locator("#adj-brightness-num").scroll_into_view_if_needed()
        page.wait_for_timeout(200)

        def reset(v=0):
            page.fill("#adj-brightness-num", str(v))
            page.press("#adj-brightness-num", "Enter")
            page.evaluate("() => document.activeElement && document.activeElement.blur()")
            page.wait_for_timeout(300)

        # 1. Touch press steps exactly once (pointerType=touch, real tap).
        reset(10)
        page.tap(UP)
        page.wait_for_timeout(250)
        results["touch_tap_once"] = {"value": val(page), "state": state_val(page), "pass": val(page) == 11 and state_val(page) == 11}

        # 2. Keyboard on the stepper: one step per press, no double-fire.
        reset(20)
        page.locator(STEP).focus()
        page.keyboard.press("Space")
        page.wait_for_timeout(150)
        after_space = val(page)
        page.keyboard.press("Enter")
        page.wait_for_timeout(150)
        after_enter = val(page)
        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(150)
        after_up = val(page)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(150)
        after_down = val(page)
        results["keyboard"] = {"space": after_space, "enter": after_enter, "up": after_up, "down": after_down,
                               "pass": (after_space, after_enter, after_up, after_down) == (21, 22, 23, 22)}

        # 3. Right/middle click must not step.
        reset(5)
        box = page.evaluate("(sel) => { const b = document.querySelector(sel).getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }", UP)
        page.mouse.click(box["x"], box["y"], button="right")
        page.mouse.click(box["x"], box["y"], button="middle")
        page.wait_for_timeout(300)
        results["non_primary_click"] = {"value": val(page), "pass": val(page) == 5}

        # 4. Undo: one history entry per discrete press, and a hold is one entry.
        reset(0)
        for _ in range(3):
            page.locator(UP).click()
            page.wait_for_timeout(700)   # > the app's 600ms history coalescing window
        page.wait_for_timeout(400)
        three = val(page)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(500)
        undo1 = val(page)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(500)
        undo2 = val(page)
        results["undo_per_press"] = {"after3": three, "undo1": undo1, "undo2": undo2,
                                     "pass": three == 3 and undo1 == 2 and undo2 == 1}
        # A burst inside the coalescing window is one history entry (unchanged
        # app behaviour, same as dragging the slider).
        reset(0)
        for _ in range(5):
            page.locator(UP).click()
            page.wait_for_timeout(60)
        page.wait_for_timeout(400)
        burst = val(page)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(600)
        results["undo_burst_is_one_entry"] = {"after5": burst, "after_undo": val(page),
                                              "pass": burst == 5 and val(page) < burst}

        # 5. Layout at 320px and at 200% text zoom: stepper inside its card, no page overflow.
        page.set_viewport_size({"width": 320, "height": 800})
        page.wait_for_timeout(400)
        g320 = page.evaluate("""() => {
          const s = document.querySelector('.stepper[data-control="adj-brightness-num"]');
          const card = s.closest('.control-input-wrap') || s.parentElement;
          const sb = s.getBoundingClientRect(), cb = card.getBoundingClientRect();
          return {docW: document.documentElement.scrollWidth, winW: window.innerWidth,
                  stepRight: +sb.right.toFixed(1), cardRight: +cb.right.toFixed(1),
                  w: +sb.width.toFixed(1), h: +sb.height.toFixed(1)};
        }""")
        page.evaluate("() => { document.documentElement.style.fontSize = '32px'; }")
        page.wait_for_timeout(400)
        zoom = page.evaluate("""() => {
          const s = document.querySelector('.stepper[data-control="adj-brightness-num"]');
          const sb = s.getBoundingClientRect();
          return {docW: document.documentElement.scrollWidth, winW: window.innerWidth,
                  stepRight: +sb.right.toFixed(1), visible: !!(sb.width && sb.height)};
        }""")
        page.evaluate("() => { document.documentElement.style.fontSize = ''; }")
        page.set_viewport_size({"width": 1280, "height": 900})
        results["layout"] = {"at320": g320, "text200": zoom,
                             "pass": g320["docW"] <= g320["winW"] and g320["stepRight"] <= g320["cardRight"] + 0.5
                                     and zoom["docW"] <= zoom["winW"] and zoom["visible"]}

        # 6. Heavy 4K stack: 20 rapid presses are exact while renders are pending.
        if FIX4K.exists():
            page.set_input_files("#file-input", str(FIX4K))
            page.wait_for_selector(".canvas-area.has-content")
            page.wait_for_timeout(2500)
            names = page.evaluate("() => Object.fromEntries(EFFECTS.map(e => [e.id, e.name]))")
            for eid in ("halftone", "posterize", "edges", "emboss"):
                page.locator(f'.effect-item input[type="checkbox"][aria-label="Enable {names[eid]}"]').check()
            page.wait_for_timeout(4000)
            reset(0)
            page.evaluate("(sel) => document.querySelector(sel).scrollIntoView({block: 'center'})", UP)
            page.wait_for_timeout(400)
            b = page.evaluate("(sel) => { const b = document.querySelector(sel).getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }", UP)
            page.mouse.move(b["x"], b["y"])
            for _ in range(20):
                page.mouse.click(b["x"], b["y"])
                page.wait_for_timeout(25)
            page.wait_for_timeout(5000)
            results["heavy_4k_20_clicks"] = {"value": val(page), "state": state_val(page),
                                             "pass": val(page) == 20 and state_val(page) == 20}

        results["page_errors"] = errs[:5]
        browser.close()
    httpd.shutdown()
    print(json.dumps(results, indent=1))
    ok = all(v.get("pass", True) for k, v in results.items() if isinstance(v, dict))
    print("BREAK-IT", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
