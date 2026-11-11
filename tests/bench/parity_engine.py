#!/usr/bin/env python3
"""Old-vs-new parity for the palette paths, across two trees.

  python tests/bench/parity_engine.py --rev ad5bb37

Loads the working tree and a git revision in one browser, renders the same
configs on both and compares the canvas hash. Also compares the SVG and TXT
exports, which have their own palette colour lookup. Covers hex palettes (the
3-digit and 6-digit parse paths), `rgb()` palettes (the only form the dither
path substitutes), mono and spectrum, and every dither kernel.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_lib as B  # noqa: E402
import speed_page as S  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CUSTOM_RGB = '["rgb(10,20,30)","rgb(200,100,50)","rgba(1, 2, 3, 0.5)","#0f380f","#08f"]'

CASES = []
for palette in ["Grayscale 16", "CGA", "1-bit", "Game Boy", "Terminal"]:
    for mode in ["script", "dither"]:
        CASES.append({"mode": mode, "colorMode": "palette", "palette": palette,
                      "ditherKernel": "floyd-steinberg", "effects": []})
for kernel in ["floyd-steinberg", "atkinson", "bayer2", "bayer4", "bayer8",
               "threshold", "blue-noise", "random", "halftone"]:
    CASES.append({"mode": "dither", "colorMode": "palette", "palette": "Grayscale 16",
                  "ditherKernel": kernel, "effects": []})
for colorMode in ["mono", "spectrum"]:
    for mode in ["script", "dither"]:
        CASES.append({"mode": mode, "colorMode": colorMode, "palette": "Grayscale 16",
                      "ditherKernel": "floyd-steinberg", "effects": []})
CASES.append({"mode": "script", "colorMode": "palette", "palette": "__custom__",
              "custom": CUSTOM_RGB, "ditherKernel": "floyd-steinberg", "effects": []})
CASES.append({"mode": "dither", "colorMode": "palette", "palette": "__custom__",
              "custom": CUSTOM_RGB, "ditherKernel": "floyd-steinberg", "effects": []})
CASES.append({"mode": "effects", "colorMode": "palette", "palette": "Grayscale 16",
              "ditherKernel": "floyd-steinberg",
              "effects": ["halftone", "posterize", "retro"]})


def cfg_of(case: dict) -> dict:
    return {"mode": case["mode"], "effects": case["effects"],
            "params": {}, "full": False,
            "colorMode": case["colorMode"], "palette": case["palette"],
            "ditherKernel": case["ditherKernel"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--workdir", default="/tmp/opencode/glyphcraft_parity_old")
    args = ap.parse_args()

    B.fixtures()
    old_dir = Path(args.workdir)
    S.unpack(args.rev, old_dir)
    failures = []
    rows = []
    with S.TreeServer(ROOT) as new_srv, S.TreeServer(old_dir) as old_srv, \
            sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            new_ctx, new_page, _, new_errors = S.open_page(browser, new_srv.url)
            old_ctx, old_page, _, old_errors = S.open_page(browser, old_srv.url)
            sides = {"new": new_page, "old": old_page}
            try:
                for case in CASES:
                    cfg = cfg_of(case)
                    result = {}
                    for which, page in sides.items():
                        if "custom" in case:
                            page.evaluate("(src) => { state.opts.customPalette = JSON.parse(src); }",
                                          case["custom"])
                        result[which] = page.evaluate("""(cfg) => {
                          const r = window.__benchRender(cfg);
                          const canvas = document.createElement('canvas');
                          const full = computeOutputSize(state.sourceW, state.sourceH, 'original', 1920, 1080, 'contain');
                          const pv = previewSize(full);
                          canvas.width = pv.w; canvas.height = pv.h;
                          const ctx = canvas.getContext('2d', {willReadFrequently:true});
                          const opts = renderOpts();
                          const base = prepareBase(state.source, pv.w, pv.h, opts, null);
                          renderToContext(base, ctx, pv.w, pv.h, opts);
                          const svg = canvasToSvg(base, { ...opts, preApplied: true });
                          const txt = canvasToTxt(base, { ...opts, preApplied: true });
                          canvas.width = 0;
                          return { hash: r.hash, svg: svg.length, txt: txt.length,
                                   svgSum: [...svg].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7),
                                   txtSum: [...txt].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7) };
                        }""", cfg)
                    same = result["new"] == result["old"]
                    label = f"{case['mode']}/{case['colorMode']}/{case.get('custom', case['palette'])[:24]}/{case['ditherKernel']}"
                    rows.append({"case": case, "new": result["new"], "old": result["old"], "same": same})
                    print(("PASS " if same else "FAIL ") + label, flush=True)
                    if not same:
                        failures.append(f"{label}: new={result['new']} old={result['old']}")
            finally:
                new_ctx.close()
                old_ctx.close()
        finally:
            browser.close()

    errors = new_errors + old_errors
    for error in errors:
        failures.append(f"page error: {error}")
    print(f"{len(rows)} cases, {len(failures)} failure(s)")
    for failure in failures:
        print("FAIL " + failure)
    print("PARITY PASS" if not failures else "PARITY FAIL")
    S.shutil.rmtree(old_dir, ignore_errors=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
