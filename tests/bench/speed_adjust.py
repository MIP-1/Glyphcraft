#!/usr/bin/env python3
"""Paired before/after timing for one engine function, in one browser session.

  python tests/bench/speed_adjust.py --rev ec5a726 --size 1600x900

The current tree provides the "new" function. The "old" function is read from a
git revision of `engine.js` and installed as `window.__altAdj`, so both variants
run on the same page, canvas, browser and machine. Each window runs both
variants as A/B/B/A, discards a warm-up call per variant, redraws the source
untimed before every call and forces GC. Reports the per-window ratio, the
median of the five window medians and the p95 over all samples.

The rule from docs/evidence/p2-3/decisions.md: keep a change only when it is at
least 10% faster in 4 of 5 windows with identical output hashes.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_lib as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

WINDOWS = 5


def extract_function(rev: str, name: str) -> str:
    source = subprocess.run(["git", "show", f"{rev}:engine.js"], cwd=str(ROOT),
                            capture_output=True, text=True, check=True).stdout
    pattern = re.compile(r"^function " + name + r"\([^)]*\) \{.*?^\}\n", re.M | re.S)
    found = pattern.search(source)
    if not found:
        raise SystemExit(f"could not extract {name} from {rev}: engine.js")
    return found.group(0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="ec5a726")
    ap.add_argument("--size", default="1600x900")
    ap.add_argument("--adj", default='{"highlights":60,"shadows":60,"sharpen":40,'
                                     '"invert":true,"sepia":true}')
    ap.add_argument("--samples", type=int, default=8,
                    help="timed samples per variant per window (default 8)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    width, height = (int(x) for x in args.size.lower().split("x"))
    adj = json.loads(args.adj)
    old = extract_function(args.rev, "applyAdjustments")

    B.fixtures()
    rows = []
    samples: dict[str, list[float]] = {"new": [], "old": []}
    with B.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx, page, errors = B.new_page(browser, srv)
            try:
                B.load_image(page, B.FIXTURE_1080)
                cdp = B.cdp_session(page)
                page.evaluate("(src) => { window.__altAdj = (0, eval)('(' + src + ')'); }", old)
                page.evaluate("""([w, h, adj]) => {
                  const cv = document.createElement('canvas');
                  cv.width = w; cv.height = h;
                  const c = cv.getContext('2d', { willReadFrequently: true });
                  c.drawImage(state.source, 0, 0, w, h);
                  const src = document.createElement('canvas');
                  src.width = w; src.height = h;
                  src.getContext('2d').drawImage(cv, 0, 0);
                  window.__adjCanvas = cv;
                  window.__adjCtx = c;
                  window.__adjSource = src;
                  window.__adjParams = adj;
                  window.__adjRun = (which) => {
                    const fn = which === 'old' ? window.__altAdj : applyAdjustments;
                    const x = window.__adjCtx;
                    x.setTransform(1, 0, 0, 1, 0, 0);
                    x.filter = 'none';
                    x.drawImage(window.__adjSource, 0, 0, w, h);
                    const t0 = performance.now();
                    fn(x, w, h, window.__adjParams);
                    return performance.now() - t0;
                  };
                }""", [width, height, adj])

                for which in ("new", "old"):
                    B.gc(cdp)
                    page.wait_for_timeout(30)
                    page.evaluate("(w) => window.__adjRun(w)", which)  # warm-up

                # This function is short (~150 ms), so one stray canvas stall can
                # move a 4-sample median. Each window takes more alternating
                # samples and the median over those samples absorbs a stall.
                for window in range(WINDOWS):
                    order = ["new", "old"] if window % 2 == 0 else ["old", "new"]
                    timings = {"new": [], "old": []}
                    for i in range(args.samples):
                        pair = order if i % 2 == 0 else list(reversed(order))
                        for which in pair:
                            B.gc(cdp)
                            page.wait_for_timeout(30)
                            timings[which].append(
                                page.evaluate("(w) => window.__adjRun(w)", which))
                    value = {k: statistics.median(v) for k, v in timings.items()}
                    rows.append(value)
                    samples["new"].extend(timings["new"])
                    samples["old"].extend(timings["old"])
                    print(f"window {window + 1}: new={value['new']:.2f}ms "
                          f"old={value['old']:.2f}ms "
                          f"ratio={value['new'] / value['old']:.3f}", flush=True)

                hashes = page.evaluate("""() => {
                  const cv = window.__adjCanvas;
                  const out = {};
                  for (const which of ['old', 'new']) {
                    window.__adjRun(which);
                    out[which] = window.__benchHash(cv);
                  }
                  return out;
                }""")
                errors = list(errors)
            finally:
                ctx.close()
        finally:
            browser.close()

    median_new = statistics.median(r["new"] for r in rows)
    median_old = statistics.median(r["old"] for r in rows)
    faster = sum(1 for r in rows if r["new"] / r["old"] <= 0.90)

    def p95(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]

    print(f"all samples: new median={statistics.median(samples['new']):.2f}ms "
          f"p95={p95(samples['new']):.2f}ms "
          f"old median={statistics.median(samples['old']):.2f}ms "
          f"p95={p95(samples['old']):.2f}ms")
    print(f"window medians: new={[round(r['new'], 1) for r in rows]} "
          f"old={[round(r['old'], 1) for r in rows]}")
    print(f"median new={median_new:.2f}ms old={median_old:.2f}ms "
          f"ratio={median_new / median_old:.3f} faster_windows={faster}/{len(rows)}")
    print(f"hash new={hashes['new']} old={hashes['old']} "
          f"{'IDENTICAL' if hashes['new'] == hashes['old'] else 'DIFFERENT'}")
    if errors:
        print("page errors:", errors[:5])
    verdict = faster >= 4 and hashes["new"] == hashes["old"] and not errors
    print("SPEED PASS" if verdict else "SPEED FAIL")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"function": "applyAdjustments", "adj": adj, "size": args.size,
             "rev": args.rev, "windows": rows, "samples": samples,
             "median_new": median_new, "median_old": median_old,
             "p95_new": p95(samples["new"]), "p95_old": p95(samples["old"]),
             "faster_windows": faster, "hashes": hashes, "errors": errors},
            indent=2) + "\n", encoding="utf-8")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
