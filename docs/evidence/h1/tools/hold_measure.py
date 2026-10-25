#!/usr/bin/env python3
"""Measure observed step rate while holding a numeric control's up arrow.

Counts distinct values visible on the control, sampled once per animation
frame, so a blocked main thread counts as "the user sees nothing".

usage: python hold_measure.py <repo-dir> <fixture> <seconds...> [control ...]
"""
import functools
import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve()
FIXTURE = Path(sys.argv[2])
SECONDS = [float(x) for x in sys.argv[3].split(",")]
CIDS = sys.argv[4:] or ["adj-brightness-num", "adj-contrast-num", "adj-hue-num", "depth-num", "cell-size-num"]

INPUT_SEL = """
(cid) => {
  if (cid.startsWith('fx.')) {
    const item = document.querySelector('.effect-item[data-id="' + cid.split('.')[1] + '"]');
    return item ? item.querySelector('input[type=number]') : null;
  }
  return document.getElementById(cid);
}
"""

SAMPLE = r"""
() => {
  const el = window.__el;
  window.__samples = [];
  window.__stop = false;
  const tick = () => {
    if (window.__stop) return;
    window.__samples.push([performance.now(), el.value]);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
"""


def find_up(page, cid):
    kind = page.evaluate("(cid) => document.querySelector('.stepper[data-control=\"' + cid + '\"] .step-btn[data-step=up]') ? 'stepper' : 'native'", cid)
    if kind == "stepper":
        page.locator('.stepper[data-control="' + cid + '"] .step-btn[data-step=up]').scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        pt = page.evaluate("(cid) => { const b = document.querySelector('.stepper[data-control=\"' + cid + '\"] .step-btn[data-step=up]').getBoundingClientRect(); return {x:b.x+b.width/2, y:b.y+b.height/2}; }", cid)
        return kind, pt
    el = page.evaluate_handle("(cid) => (" + INPUT_SEL + ")(cid)", cid).as_element()
    el.scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    box = el.evaluate("e => { const b = e.getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width,h:b.height}; }")
    for dy in (14, 17, 12, 20):
        for dx in (-17, -20, -14):
            x, y = box["x"] + box["w"] + dx, box["y"] + dy
            before = el.input_value()
            page.mouse.click(x, y)
            page.wait_for_timeout(80)
            after = el.input_value()
            if float(after) > float(before):
                page.evaluate("(a) => { const e = (" + INPUT_SEL + ")(a.cid); e.value = a.v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }",
                              {"cid": cid, "v": before})
                page.wait_for_timeout(300)
                return kind, {"x": x, "y": y}
    return None, None


def main():
    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}"
    rows = []
    with sync_playwright() as p:
        browser = getattr(p, os.environ.get("H1_BROWSER", "chromium")).launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.goto(url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIXTURE))
        page.wait_for_selector(".canvas-area.has-content", timeout=30000)
        page.wait_for_timeout(1200)
        page.evaluate("""() => { document.querySelectorAll('.panel-section.collapsed').forEach(s => {
          if (getComputedStyle(s).display === 'none') return;
          const t = s.querySelector('.section-title'); if (t) t.click(); }); }""")
        page.wait_for_timeout(400)
        for cid in CIDS:
            el = page.evaluate_handle("(cid) => (" + INPUT_SEL + ")(cid)", cid).as_element()
            if not el:
                rows.append({"control": cid, "error": "missing"})
                continue
            kind, pt = find_up(page, cid)
            if not pt:
                rows.append({"control": cid, "error": "no arrow"})
                continue
            for secs in SECONDS:
                # reset to min so clamping cannot end the hold early
                mn = el.get_attribute("min") or "0"
                el.fill(str(mn))
                el.press("Enter")
                page.evaluate("() => document.activeElement && document.activeElement.blur()")
                page.wait_for_timeout(400)
                if kind == "stepper":
                    page.locator('.stepper[data-control="' + cid + '"] .step-btn[data-step=up]').scroll_into_view_if_needed()
                    page.wait_for_timeout(150)
                    pt = page.evaluate("(cid) => { const b = document.querySelector('.stepper[data-control=\"' + cid + '\"] .step-btn[data-step=up]').getBoundingClientRect(); return {x:b.x+b.width/2, y:b.y+b.height/2}; }", cid)
                page.evaluate("(cid) => { window.__el = (" + INPUT_SEL + ")(cid); window.__cid = cid; }", cid)
                page.evaluate(SAMPLE)
                page.mouse.move(pt["x"], pt["y"])
                t0 = time.time()
                page.mouse.down()
                page.wait_for_timeout(int(secs * 1000))
                page.mouse.up()
                page.wait_for_timeout(200)
                samples = page.evaluate("() => { window.__stop = true; return window.__samples; }")
                start = float(mn)
                changes = 0
                prev = samples[0][1] if samples else str(start)
                for _t, v in samples:
                    if v != prev:
                        changes += 1
                        prev = v
                end_val = samples[-1][1] if samples else "?"
                rows.append({"control": cid, "kind": kind, "seconds": secs,
                             "steps": changes, "rate": round(changes / secs, 1),
                             "from": str(int(start)), "to": end_val,
                             "wall": round(time.time() - t0, 1)})
                print(json.dumps(rows[-1]))
        browser.close()
    httpd.shutdown()
    print(json.dumps({"rows": rows}))


if __name__ == "__main__":
    main()
