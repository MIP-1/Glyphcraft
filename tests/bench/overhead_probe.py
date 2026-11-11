#!/usr/bin/env python3
"""Measured overhead of two candidate costs, on the real preview pipeline.

  python tests/bench/overhead_probe.py

1. Source draw: how much of a 4K-source preview render is `prepareBase`'s
   downscale of the full-size source into the preview canvas (the cost a cached
   preview base could remove). Reported per mode as median of five renders.
2. Render key: how long `JSON.stringify(renderOpts())` takes for a light and a
   twelve-effect configuration, in microseconds per call.

Neither is a candidate by itself; this tool exists so the decision table's
"cache the downscaled preview base" and "build the render key from mutable
fields only" items can be judged on numbers instead of assumed costs.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_lib as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    B.fixtures()
    rows = {"draw": [], "key": []}
    with B.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx, page, errors = B.new_page(browser, srv)
            try:
                B.load_image(page, B.FIXTURE_4K)
                for mode in ("script", "dither", "effects"):
                    cfg = {"mode": mode, "effects": [], "params": {}, "full": False,
                           "colorMode": "spectrum", "palette": "Grayscale 16",
                           "ditherKernel": "floyd-steinberg"}
                    samples = page.evaluate("""(cfg) => {
                      window.__benchApply(cfg);
                      const full = computeOutputSize(state.sourceW, state.sourceH, 'original', 1920, 1080, 'contain');
                      const pv = previewSize(full);
                      const opts = renderOpts();
                      const out = [];
                      for (let i = 0; i < 5; i++) {
                        const canvas = document.createElement('canvas');
                        canvas.width = pv.w; canvas.height = pv.h;
                        const c = canvas.getContext('2d', { willReadFrequently: true });
                        const t0 = performance.now();
                        const base = prepareBase(previewSourceForRender(), pv.w, pv.h, opts, null);
                        renderToContext(base, c, pv.w, pv.h, opts);
                        out.push({total: performance.now() - t0, draw: sourceDrawMs()});
                        canvas.width = 0;
                      }
                      return {pv: [pv.w, pv.h], samples: out};
                    }""", cfg)
                    draw = statistics.median(s["draw"] for s in samples["samples"])
                    total = statistics.median(s["total"] for s in samples["samples"])
                    row = {"mode": mode, "preview": samples["pv"],
                           "draw_ms": round(draw, 3), "total_ms": round(total, 2),
                           "draw_share_pct": round(draw / total * 100, 3)}
                    rows["draw"].append(row)
                    print(json.dumps(row), flush=True)

                for label, effects in (
                        ("light", []),
                        ("twelve", ["halftone", "crt", "pixelate", "bloom", "vignette",
                                    "posterize", "edges", "sketch", "emboss", "blur",
                                    "thermal", "retro"])):
                    cfg = {"mode": "script", "effects": effects, "params": {},
                           "full": False, "colorMode": "palette",
                           "palette": "Grayscale 16", "ditherKernel": "floyd-steinberg"}
                    key = page.evaluate("""(cfg) => {
                      window.__benchApply(cfg);
                      const opts = renderOpts();
                      const t0 = performance.now();
                      for (let i = 0; i < 200; i++) JSON.stringify(opts);
                      const us = (performance.now() - t0) * 1000 / 200;
                      return {us: us, bytes: JSON.stringify(opts).length};
                    }""", cfg)
                    row = {"stack": label, "us_per_call": round(key["us"], 2),
                           "bytes": key["bytes"]}
                    rows["key"].append(row)
                    print(json.dumps(row), flush=True)
                errors = list(errors)
            finally:
                ctx.close()
        finally:
            browser.close()

    print("page errors:", errors[:5])
    if args.out:
        Path(args.out).write_text(json.dumps({**rows, "errors": errors}, indent=2) + "\n",
                                  encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
