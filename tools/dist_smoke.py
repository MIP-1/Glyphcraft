#!/usr/bin/env python3
"""Publish-build smoke test: dist/ must render the same pixels as the source.

Loads the same fixture through index.html and dist/index.html, enables the
same deterministic effects, waits for the render to settle and compares the
canvas hash plus the backing size. Also fails on any page error.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "gate"))
import run_gate as rg  # noqa: E402

EFFECTS = ["halftone", "posterize", "duotone", "retro"]

SCENARIO = """(ids) => {
  state.opts.effects = state.opts.effects.map(fx => ({
    ...fx, enabled: ids.includes(fx.id)
  }));
  scheduleRender();
  return true;
}"""

HASH = """() => {
  const c = document.getElementById('canvas');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let h = 2166136261;
  for (let i = 0; i < d.length; i++) {
    h ^= d[i];
    h = Math.imul(h, 16777619) >>> 0;
  }
  return { hash: h, w: c.width, h: c.height };
}"""


def measure(page, url: str) -> dict:
    print(f"load {url}", flush=True)
    page.goto(url, wait_until="load", timeout=30000)
    page.evaluate("() => document.fonts.ready")
    page.wait_for_timeout(600)
    before = page.evaluate("() => state.sourceId")
    page.evaluate("() => { document.getElementById('file-input').value = ''; }")
    page.set_input_files("#file-input", str(rg.FIXTURE))
    page.wait_for_function("(id) => state.sourceId > id", arg=before, timeout=60000)
    page.wait_for_selector(".canvas-area.has-content", timeout=60000)
    page.wait_for_timeout(400)
    page.evaluate(SCENARIO, EFFECTS)
    page.wait_for_timeout(2000)
    print("hash", flush=True)
    return page.evaluate(HASH)


def main() -> int:
    rg.ensure_fixtures()
    httpd, url, _thread = rg.start_server()
    rg.BASE_URL = url
    failed = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            def fresh():
                context = browser.new_context(viewport={"width": 1280, "height": 900},
                                              locale="en-US", reduced_motion="reduce")
                context.add_init_script(
                    "try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
                return context, page, errors

            src_ctx, src_page, src_errors = fresh()
            dist_ctx, dist_page, dist_errors = fresh()
            try:
                src = measure(src_page, url + "/index.html")
                dist = measure(dist_page, url + "/dist/index.html")
            finally:
                src_ctx.close()
                dist_ctx.close()
            errors = src_errors + dist_errors
            print(f"source: hash={src['hash']} canvas={src['w']}x{src['h']}")
            print(f"dist:   hash={dist['hash']} canvas={dist['w']}x{dist['h']}")
            print(f"errors: {errors}")
            same = src == dist
            print("DIST SMOKE " + ("PASS" if same and not errors else "FAIL"))
            failed = not (same and not errors)
    finally:
        httpd.shutdown()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
