#!/usr/bin/env python3
"""Attribute 4000x3000 prepareBase cost per effect (H2 evidence / H4 input)."""
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("/home/mustafa/glyphcraft")

MEASURE = r"""
(ids) => {
  const out = [];
  for (const id of ids) {
    const eff = [{ id, enabled: true, params: {} }];
    const defs = EFFECTS.find(e => e.id === id).params;
    for (const p of defs) eff[0].params[p.key] = p.key === 'radius' ? 4 : p.def;
    if (id === 'sketch') { eff[0].params.amount = 100; eff[0].params.cross = 100; }
    if (id === 'blur') eff[0].params.radius = 4;
    const t0 = performance.now();
    const c = prepareBase(state.source, 4000, 3000, { ...renderOpts(), effects: eff });
    const ms = performance.now() - t0;
    out.push({ id, ms: +ms.toFixed(0), w: c.width, h: c.height });
  }
  const t0 = performance.now();
  const all = ['posterize','edges','sketch','emboss','blur','sharpen'].map(id => {
    const e = { id, enabled: true, params: {} };
    for (const p of EFFECTS.find(x => x.id === id).params) e.params[p.key] = p.def;
    if (id === 'sketch') { e.params.amount = 100; e.params.cross = 100; }
    if (id === 'blur') e.params.radius = 4;
    return e;
  });
  prepareBase(state.source, 4000, 3000, { ...renderOpts(), effects: all });
  out.push({ id: 'STACK-6', ms: +(performance.now() - t0).toFixed(0) });
  return out;
}
"""


def main():
    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(f"http://127.0.0.1:{httpd.server_port}/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", "/tmp/glyphcraft_gate_4k.png")
        page.wait_for_selector(".canvas-area.has-content", timeout=40000)
        page.wait_for_timeout(1200)
        rows = page.evaluate(MEASURE, ["posterize", "edges", "sketch", "emboss",
                                       "blur", "sharpen"])
        b.close()
    httpd.shutdown()
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
