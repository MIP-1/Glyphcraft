#!/usr/bin/env python3
"""Paired before/after timing for one effect, in one browser session.

  python tests/bench/speed_effect.py oil '{"radius":2}' --rev df4365d

The current tree provides the "new" function. The "old" function is read from a
git revision and installed as `EFFECT_RUNNERS[id]` between windows, so both
variants run on the same page, canvas, browser and machine. Each window runs
both variants (order alternates), discards warm-ups, forces GC, takes the
median of REPS calls and reports the ratio per window.

The rule from docs/evidence/p2-3/decisions.md: keep a change only when it is at
least 10% faster in 4 of 5 windows.
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
REPS = 3
WARM = 1


def extract_function(rev: str, effect_id: str) -> str:
    source = subprocess.run(["git", "show", f"{rev}:effects.js"], cwd=str(ROOT),
                            capture_output=True, text=True, check=True).stdout
    names = re.findall(r"^function (fx\w+)\(c, p\) \{", source, re.M)
    target = None
    for name in names:
        if name.lower() == "fx" + effect_id.lower():
            target = name
            break
    if target is None:
        raise SystemExit(f"no fx function for {effect_id!r} in {rev}: effects.js")
    pattern = re.compile(r"^function " + target + r"\(c, p\) \{.*?^\}\n", re.M | re.S)
    found = pattern.search(source)
    if not found:
        raise SystemExit(f"could not extract {target} from {rev}")
    return found.group(0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect")
    ap.add_argument("params", nargs="?", default="{}")
    ap.add_argument("--rev", default="df4365d")
    ap.add_argument("--mode", default="effects")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    params = json.loads(args.params)
    old = extract_function(args.rev, args.effect)

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
                page.evaluate("""(src) => {
                  window.__altFx = (0, eval)("(" + src.replace(/^function \\w+/, "function") + ")");
                }""", old)
                page.evaluate("""([id, params]) => {
                  window.__fxId = id;
                  window.__fxParams = params;
                  const full = computeOutputSize(state.sourceW, state.sourceH, 'original', 1920, 1080, 'contain');
                  const pv = previewSize(full);
                  const cv = document.createElement('canvas');
                  cv.width = pv.w; cv.height = pv.h;
                  const x = cv.getContext('2d', {willReadFrequently: true});
                  x.drawImage(state.source, 0, 0, pv.w, pv.h);
                  window.__fxCanvas = cv;
                  window.__fxNew = EFFECT_RUNNERS[id];
                  window.__fxRun = (which) => {
                    const fn = which === 'old' ? window.__altFx : window.__fxNew;
                    const t0 = performance.now();
                    fn(window.__fxCanvas, window.__fxParams);
                    return performance.now() - t0;
                  };
                }""", [args.effect, params])

                for window in range(WINDOWS):
                    order = ["new", "old"] if window % 2 == 0 else ["old", "new"]
                    pair = [order[0], order[1], order[1], order[0]]
                    for which in pair:
                        B.gc(cdp)
                        page.wait_for_timeout(30)
                        page.evaluate("(w) => window.__fxRun(w)", which)  # discarded warm-up
                    timings = {"new": [], "old": []}
                    for which in pair:
                        B.gc(cdp)
                        page.wait_for_timeout(30)
                        timings[which].append(page.evaluate("(w) => window.__fxRun(w)", which))
                    value = {k: statistics.median(v) for k, v in timings.items()}
                    rows.append(value)
                    samples["new"].extend(timings["new"])
                    samples["old"].extend(timings["old"])
                    print(f"window {window + 1}: new={value['new']:.2f}ms "
                          f"old={value['old']:.2f}ms "
                          f"ratio={value['new'] / value['old']:.3f}", flush=True)
                hashes = page.evaluate("""() => {
                  const a = window.__fxNew(window.__fxCanvas, window.__fxParams);
                  const b = window.__altFx(window.__fxCanvas, window.__fxParams);
                  const ha = window.__benchHash(a), hb = window.__benchHash(b);
                  a.width = 0; b.width = 0;
                  return {new: ha, old: hb};
                }""")
                errors = list(errors)
            finally:
                ctx.close()
        finally:
            browser.close()

    ratios = sorted(r["new"] / r["old"] for r in rows)
    median_new = statistics.median(r["new"] for r in rows)
    median_old = statistics.median(r["old"] for r in rows)
    faster = sum(1 for r in rows if r["new"] / r["old"] <= 0.90)

    def p95(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]

    all_new = statistics.median(samples["new"])
    all_old = statistics.median(samples["old"])
    print(f"all samples: new median={all_new:.2f}ms p95={p95(samples['new']):.2f}ms "
          f"old median={all_old:.2f}ms p95={p95(samples['old']):.2f}ms")
    print(f"window medians: new={[round(r['new'], 1) for r in rows]} "
          f"old={[round(r['old'], 1) for r in rows]}")
    print(f"median new={median_new:.2f}ms old={median_old:.2f}ms "
          f"ratio={median_new / median_old:.3f} "
          f"faster_windows={faster}/{len(rows)}")
    print(f"hash new={hashes['new']} old={hashes['old']} "
          f"{'IDENTICAL' if hashes['new'] == hashes['old'] else 'DIFFERENT'}")
    if errors:
        print("page errors:", errors[:5])
    verdict = faster >= 4 and hashes["new"] == hashes["old"] and not errors
    print("SPEED PASS" if verdict else "SPEED FAIL")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"effect": args.effect, "params": params, "rev": args.rev,
             "windows": rows, "samples": samples,
             "median_new": median_new, "median_old": median_old,
             "p95_new": p95(samples["new"]), "p95_old": p95(samples["old"]),
             "faster_windows": faster, "hashes": hashes, "errors": errors},
            indent=2) + "\n", encoding="utf-8")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
