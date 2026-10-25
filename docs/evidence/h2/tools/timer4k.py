#!/usr/bin/env python3
"""Time one effect render at 4000x3000 in a real browser. usage: timer.py <tree> <effect> [json params]"""
import functools, json, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve()
FX = sys.argv[2] if len(sys.argv) > 2 else "sketch"
PARAMS = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {"amount": 70, "cross": 40}

class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"http://127.0.0.1:{httpd.server_port}/index.html", wait_until="load")
    page.wait_for_timeout(400)
    out = page.evaluate("""([fx, params]) => {
      const c = document.createElement('canvas');
      c.width = 4000; c.height = 3000;
      const ctx = c.getContext('2d', {willReadFrequently: true});
      const img = ctx.createImageData(4000, 3000), d = img.data;
      for (let i = 0, px = 0; i < d.length; i += 4, px++) {
        const x = px % 4000, y = (px / 4000) | 0;
        const v = (x * 7 + y * 3) % 256;
        d[i] = v; d[i+1] = (v * 3) % 256; d[i+2] = 255 - v; d[i+3] = 255;
      }
      ctx.putImageData(img, 0, 0);
      const t0 = performance.now();
      const buf = applyEffects(c, [{id: fx, enabled: true, params}]);
      const ms = performance.now() - t0;
      // read back so a lazy canvas cannot hide the cost
      const d2 = buf.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, 8, 8).data;
      return {ms: +ms.toFixed(1), w: buf.width, h: buf.height, px: d2[6]};
    }""", [FX, PARAMS])
    print(f"{ROOT}  {FX} {PARAMS}  {out['ms']}ms  {out['w']}x{out['h']}")
    b.close()
httpd.shutdown()
