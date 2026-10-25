#!/usr/bin/env python3
"""Render the Pencil Sketch matrix (Amount x Hatch) on a dark and a bright
photo-like card and save one contact sheet per card. usage: sketch_shots.py <tree> <outdir>"""
import functools, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

JS = r"""
([kind, amounts, hatches, tileW, tileH]) => {
  const mulberry32 = (a) => () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  const src = document.createElement('canvas');
  src.width = tileW; src.height = tileH;
  const sctx = src.getContext('2d', {willReadFrequently: true});
  const img = sctx.createImageData(tileW, tileH), d = img.data;
  const rnd = mulberry32(kind === 'dark' ? 7 : 99);
  for (let y = 0; y < tileH; y++) {
    for (let x = 0; x < tileW; x++) {
      const i = (y * tileW + x) * 4;
      const t = y / (tileH - 1);
      let r, g, b;
      if (kind === 'dark') {
        const band = Math.exp(-Math.pow((t - 0.42 - 0.1 * Math.sin(x / 30)) / 0.16, 2));
        const stars = rnd() > 0.995 ? 170 * rnd() : 0;
        const base = 10 + 22 * t + 150 * band + stars;
        r = Math.min(255, base * 0.55 + 8);
        g = Math.min(255, base * 0.82 + 6);
        b = Math.min(255, base * 1.0 + 14);
      } else {
        const cloud = 0.5 + 0.5 * Math.sin(x / 37) * Math.cos(y / 29);
        const base = 120 + 110 * cloud + 30 * (rnd() - 0.5);
        r = Math.min(255, base); g = Math.min(255, base * 0.94); b = Math.min(255, base * 0.86);
      }
      d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = 255;
    }
  }
  sctx.putImageData(img, 0, 0);

  const pad = 8, labelH = 22;
  const sheet = document.createElement('canvas');
  sheet.width = amounts.length * (tileW + pad) + pad;
  sheet.height = hatches.length * (tileH + pad + labelH) + pad;
  const ctx = sheet.getContext('2d');
  ctx.fillStyle = '#1b1b1b'; ctx.fillRect(0, 0, sheet.width, sheet.height);
  ctx.font = '13px sans-serif'; ctx.textBaseline = 'top';
  amounts.forEach((amount, ci) => {
    hatches.forEach((hatch, ri) => {
      const out = applyEffects(src, [{id: 'sketch', enabled: true, params: {amount, cross: hatch}}]);
      const x = pad + ci * (tileW + pad);
      const y = pad + ri * (tileH + pad + labelH);
      ctx.fillStyle = '#ddd';
      ctx.fillText('Amount ' + amount + '  Hatch ' + hatch, x + 2, y);
      ctx.drawImage(out, x, y + labelH);
    });
  });
  return sheet.toDataURL('image/png');
}
"""

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
    for kind in ("dark", "bright"):
        data = page.evaluate(JS, [kind, [0, 30, 70, 100], [0, 40, 100], 360, 260])
        raw = data.split(",", 1)[1]
        import base64
        path = OUT / f"sketch-{kind}-matrix.png"
        path.write_bytes(base64.b64decode(raw))
        print(path)
    b.close()
httpd.shutdown()
