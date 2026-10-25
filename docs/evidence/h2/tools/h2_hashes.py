#!/usr/bin/env python3
"""Print a hash of every effect's output at several values, so the fixed tree can
be compared with the pre-fix tree. usage: h2_hashes.py <tree>"""
import functools, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve()
JS = r"""
() => {
  const mulberry32 = (a) => () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  const rnd = mulberry32(42);
  const card = document.createElement('canvas');
  card.width = 256; card.height = 256;
  const ctx = card.getContext('2d', {willReadFrequently: true});
  const img = ctx.createImageData(256, 256), d = img.data;
  for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
    const i = (y * 256 + x) * 4;
    d[i] = Math.round(255 * x / 255);
    d[i+1] = Math.round(255 * y / 255);
    d[i+2] = Math.round(120 + 100 * Math.sin(x / 20) * Math.cos(y / 17) + 20 * (rnd() - 0.5));
    d[i+3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const hash = (cd) => {
    let h = 0x811c9dc5;
    for (let i = 0; i < cd.length; i++) { h ^= cd[i]; h = Math.imul(h, 0x01000193); }
    return (h >>> 0).toString(16).padStart(8, '0');
  };
  // Deterministic Math.random so the random effects (grain, glitch, vhs,
  // pixelsort, matrix) can be compared across trees.
  const realRandom = Math.random;
  const seeded = mulberry32(1234);
  Math.random = seeded;
  const out = {};
  for (const e of EFFECTS) {
    const numeric = e.params.filter(p => p.type !== 'color' && p.type !== 'select');
    const sets = {def: {}};
    e.params.forEach(p => sets.def[p.key] = p.def);
    for (const p of numeric) {
      // Only UI-reachable values: on the step grid, so this compares behaviour
      // a user can actually select.
      const mid = p.min + Math.round((p.max - p.min) / p.step / 2) * p.step;
      sets['min_' + p.key] = {...sets.def, [p.key]: p.min};
      sets['max_' + p.key] = {...sets.def, [p.key]: p.max};
      sets['mid_' + p.key] = {...sets.def, [p.key]: mid};
    }
    for (const [label, params] of Object.entries(sets)) {
      const buf = applyEffects(card, [{id: e.id, enabled: true, params}]);
      out[e.id + '/' + label] = hash(buf.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, 256, 256).data);
    }
  }
  Math.random = realRandom;
  return out;
}
"""
class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context().new_page()
    page.goto(f"http://127.0.0.1:{httpd.server_port}/index.html", wait_until="load")
    page.wait_for_timeout(400)
    data = page.evaluate(JS)
    for key in sorted(data):
        print(key, data[key])
    b.close()
httpd.shutdown()
