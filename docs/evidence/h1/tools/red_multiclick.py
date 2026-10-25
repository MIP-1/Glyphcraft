#!/usr/bin/env python3
"""RED probe for the user's exact symptom: a burst of fast clicks on a number
control's up arrow "adds 1-3 steps then the value falls back to 0".

The difference from h1_probe.py: this one increments CDP clickCount the way a
real browser does for repeated presses in the same spot, so the browser's own
dblclick gesture fires. Real users click that fast; page.mouse.click() always
sends clickCount=1 and therefore cannot reproduce it.

usage: python red_multiclick.py <repo-dir> [clicks] [spacing_ms] [control-id]
control-id: adj-brightness-num (default) | depth-num | fx.halftone.size
"""
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve()
CLICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
SPACING = int(sys.argv[3]) if len(sys.argv) > 3 else 120
CID = sys.argv[4] if len(sys.argv) > 4 else "adj-brightness-num"
START = float(sys.argv[5]) if len(sys.argv) > 5 else 20
FIXTURE = Path("/tmp/glyphcraft_gate_fixture.png")

INPUT_SEL = """
(cid) => {
  if (cid.startsWith('fx.')) {
    const item = document.querySelector('.effect-item[data-id="' + cid.split('.')[1] + '"]');
    return item ? item.querySelector('input[type=number]') : null;
  }
  return document.getElementById(cid);
}
"""


def main():
    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.goto(url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIXTURE))
        page.wait_for_selector(".canvas-area.has-content", timeout=20000)
        page.wait_for_timeout(700)
        page.evaluate("""() => { document.querySelectorAll('.panel-section.collapsed').forEach(s => {
          if (getComputedStyle(s).display === 'none') return;
          const t = s.querySelector('.section-title'); if (t) t.click(); }); }""")
        page.wait_for_timeout(300)
        page.evaluate("""() => { window.__dbl = []; 
          document.addEventListener('dblclick', e => window.__dbl.push(e.target.id || e.target.tagName), true); }""")

        el = page.evaluate_handle("(cid) => (" + INPUT_SEL + ")(cid)", CID).as_element()
        el.evaluate("e => e.scrollIntoView({block:'center'})")
        page.wait_for_timeout(200)
        # Put the control at a known non-default value, like the owner's 42.
        page.evaluate("(a) => { const e = (" + INPUT_SEL + ")(a.cid); e.value = a.v;"
                      " e.dispatchEvent(new Event('input', {bubbles:true}));"
                      " e.dispatchEvent(new Event('change', {bubbles:true})); }",
                      {"cid": CID, "v": START})
        page.wait_for_timeout(300)
        box = el.evaluate("e => { const b = e.getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width,h:b.height}; }")
        kind = page.evaluate("(cid) => document.querySelector('.stepper[data-control=\"' + cid + '\"]') ? 'stepper' : 'native-spinner'", CID)

        if kind == "stepper":
            pt = page.evaluate("(cid) => { const b = document.querySelector('.stepper[data-control=\"' + cid + '\"] .step-btn[data-step=up]').getBoundingClientRect(); return {x:b.x+b.width/2, y:b.y+b.height/2}; }", CID)
            up = (pt["x"], pt["y"])
        else:
            up = None
            for dy in (14, 17, 12, 20):
                for dx in (-17, -20, -14):
                    x, y = box["x"] + box["w"] + dx, box["y"] + dy
                    before = el.input_value()
                    page.mouse.click(x, y)
                    page.wait_for_timeout(120)
                    after = el.input_value()
                    if float(after) > float(before):
                        up = (x, y)
                        page.evaluate("(a) => { const e = (" + INPUT_SEL + ")(a.cid); e.value = a.v;"
                                      " e.dispatchEvent(new Event('input', {bubbles:true}));"
                                      " e.dispatchEvent(new Event('change', {bubbles:true})); }",
                                      {"cid": CID, "v": START})
                        page.wait_for_timeout(400)
                        break
                if up:
                    break
            if not up:
                print(f"{CID}: no spinner hit point in {box}")
                return

        print(f"=== {CID}  kind={kind}  clicks={CLICKS} spacing={SPACING}ms  hit={up}")
        print(f"start value={el.input_value()}  state={(page.evaluate('() => window.state ? null : null'))}")
        page.mouse.move(*up)
        trace = []
        for i in range(1, CLICKS + 1):
            page.mouse.down(click_count=i)
            page.mouse.up(click_count=i)
            page.wait_for_timeout(SPACING)
            trace.append((i, el.input_value()))
            print(f"  click {i}: value={el.input_value()}")
        page.wait_for_timeout(600)
        print("dblclick targets:", page.evaluate("() => window.__dbl"))
        print("final value:", el.input_value())
        vals = [float(v) for _, v in trace]
        print("VERDICT", "value fell back to the default 0" if 0 in vals and vals[0] > 0 else
              ("monotonic" if all(b >= a for a, b in zip(vals, vals[1:])) else "non-monotonic"))
        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
