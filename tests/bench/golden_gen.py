#!/usr/bin/env python3
"""Generate tests/gate/golden_p2_3.json.

  python tests/bench/golden_gen.py

Every case is the app preview pipeline on a fixed 1080p or 4K input, with the
Math.random seed reset before each render. Random effects are seeded and are
listed in the file; none are excluded.
"""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "bench"))
sys.path.insert(0, str(ROOT / "tests" / "gate"))

import bench_lib as B  # noqa: E402
import golden_lib as G  # noqa: E402

OUT = ROOT / "tests" / "gate" / "golden_p2_3.json"


def main() -> int:
    B.fixtures()
    with B.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            version = browser.version
            ctx, page, errors = B.new_page(browser, srv)
            try:
                B.load_image(page, B.FIXTURE_1080)
                cases = G.build_cases(page)
            finally:
                ctx.close()
            rows, render_errors = G.hash_cases(browser, srv, cases)
        finally:
            browser.close()
    all_errors = errors + render_errors
    if all_errors:
        print("generation saw page errors:")
        for error in all_errors:
            print("  " + error)
        return 1
    if len(rows) != len(cases):
        print(f"GOLDEN GEN FAIL {len(rows)}/{len(cases)} cases rendered")
        return 1
    doc = {
        "meta": {
            "task": "P2-3 A3 golden outputs",
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "platform": platform.platform(),
            "chromium": version,
            "seed": B.SEED,
            "viewport": [1440, 1000],
            "canvas": "preview (1600x900 clamp) for every mode, plus native-size Effects Only for all 22 effects; same prepareBase/renderToContext path as export",
            "seeded_random_effects": G.SEEDED_RANDOM_EFFECTS,
            "excluded": G.EXCLUDED,
            "case_count": len(rows),
        },
        "cases": rows,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"GOLDEN GEN PASS {len(rows)} cases, seed {B.SEED}, wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
