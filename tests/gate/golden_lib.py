#!/usr/bin/env python3
"""Shared golden-output measurement for P2-3 Task A3.

The golden hash is the app's own preview pipeline on a fixed input, plus a
native-size hash for every effect in Effects Only mode. Cases are built from the
live EFFECTS catalog so the gate notices a changed catalog and forces a
deliberate regeneration. Random effects are seeded, not excluded: `bench_lib`
replaces Math.random and resets the seed before every render.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "bench"))

import bench_lib as B  # noqa: E402

SEEDED_RANDOM_EFFECTS = ["glitch", "vhs", "pixelsort", "grain", "matrix"]
EXCLUDED: list[str] = []


def build_cases(page) -> list[dict]:
    all_cases = B.golden_cases(page, B.expected_sources())
    for label in ("1080p", "4k"):
        for fx in B.effect_catalog(page):
            params = B.mid_params(page, fx["id"])
            all_cases.append({"id": f"{label}-native-effects-{fx['id']}",
                              "source": label, "mode": "effects",
                              "effects": [fx["id"]],
                              "params": {fx["id"]: params}, "full": True})
    seen = set()
    out = []
    for case in all_cases:
        if case["id"] in seen:
            raise SystemExit(f"duplicate golden case id: {case['id']}")
        seen.add(case["id"])
        out.append(case)
    return out


def _cfg(case: dict) -> dict:
    return {"mode": case["mode"], "effects": case["effects"],
            "params": case["params"], "full": bool(case.get("full"))}


def hash_cases(browser, srv, cases: list[dict]) -> tuple[list[dict], list[str]]:
    by_source: dict[str, list[dict]] = {}
    for case in cases:
        by_source.setdefault(case["source"], []).append(case)
    results: list[dict] = []
    errors: list[str] = []
    for label, path in B.expected_sources().items():
        group = by_source.get(label)
        if not group:
            continue
        ctx, page, page_errors = B.new_page(browser, srv)
        try:
            B.load_image(page, path)
            cdp = B.cdp_session(page)
            for case in group:
                res = B.render_case_full(page, cdp, _cfg(case), warm=1)
                results.append({**case, "hash": res["hash"],
                                "w": res["w"], "h": res["h"]})
        finally:
            ctx.close()
        errors.extend(f"{label}: {e}" for e in page_errors)
    return results, errors
