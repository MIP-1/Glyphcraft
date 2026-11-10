#!/usr/bin/env python3
"""Permanent P2-3 parity gate: compare canvas hashes with golden_p2_3.json.

  python tests/gate/golden_check.py

The live EFFECTS catalog builds the case list, so adding, removing or renaming
an effect fails the check and forces a deliberate golden regeneration.
Every case must match exactly (0/255 difference); the random effects are seeded
and listed in the golden file, not excluded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "bench"))
sys.path.insert(0, str(ROOT / "tests" / "gate"))

import bench_lib as B  # noqa: E402
import golden_lib as G  # noqa: E402

GOLDEN = ROOT / "tests" / "gate" / "golden_p2_3.json"


def main() -> int:
    if not GOLDEN.exists():
        print(f"FAIL missing {GOLDEN.relative_to(ROOT)}")
        print("GOLDEN FAIL no golden file")
        return 1
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    expected = {case["id"]: case for case in doc["cases"]}
    seed = doc.get("meta", {}).get("seed")
    if seed != B.SEED:
        print(f"FAIL golden seed {seed!r} != harness seed {B.SEED}")
        print("GOLDEN FAIL seed mismatch")
        return 1

    B.fixtures()
    problems: list[str] = []
    with B.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx, page, errors = B.new_page(browser, srv)
            try:
                B.load_image(page, B.FIXTURE_1080)
                cases = G.build_cases(page)
            finally:
                ctx.close()
            live_ids = [case["id"] for case in cases]
            for missing in sorted(set(live_ids) - set(expected)):
                problems.append(f"no golden hash for live case {missing}")
            for stale in sorted(set(expected) - set(live_ids)):
                problems.append(f"stale golden case not in the live catalog: {stale}")
            rows, render_errors = G.hash_cases(browser, srv, cases)
        finally:
            browser.close()

    problems.extend(f"page error: {error}" for error in errors + render_errors)
    by_id = {row["id"]: row for row in rows}
    for case_id in live_ids:
        got = by_id.get(case_id)
        want = expected.get(case_id)
        if got is None:
            problems.append(f"{case_id}: case did not render")
            continue
        if want is None:
            continue
        if (got["w"], got["h"]) != (want["w"], want["h"]):
            problems.append(f"{case_id}: size {got['w']}x{got['h']} != golden "
                            f"{want['w']}x{want['h']}")
        if got["hash"] != want["hash"]:
            problems.append(f"{case_id}: hash {got['hash']} != golden {want['hash']}")

    checked = len(rows)
    print(f"GOLDEN CHECK {checked} cases, seed {seed}, {len(problems)} problem(s)")
    for problem in problems:
        print("FAIL " + problem)
    if problems:
        print(f"GOLDEN FAIL {len(problems)} problem(s) across {checked} cases")
        return 1
    print(f"GOLDEN PASS {checked}/{len(expected)} cases exact (0/255)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
