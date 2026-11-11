#!/usr/bin/env python3
"""Paired whole-page render timing: working tree vs a git revision.

  python tests/bench/speed_page.py --mode dither --colorMode palette \
      --palette "Grayscale 16" --rev ad5bb37

Both trees are served side by side from one browser, one fixture and one
viewport. The old tree is unpacked with `git archive` into /tmp (no repo
change). Every window runs the pair as A/B/B/A with a discarded warm-up call
per side and forced GC before each timed render, so machine drift hits both
sides. Reports the per-window ratio, the median of the five window medians and
the p95 over all samples.

Keep a change only when it is at least 10% faster in 4 of 5 windows.
"""
from __future__ import annotations

import argparse
import functools
import io
import json
import shutil
import statistics
import subprocess
import sys
import tarfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_lib as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

WINDOWS = 5


class TreeServer:
    def __init__(self, directory: Path):
        self.directory = directory

    def __enter__(self):
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.directory)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def unpack(rev: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = subprocess.run(["git", "archive", rev], cwd=str(ROOT),
                             check=True, stdout=subprocess.PIPE).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest)


def open_page(browser, url: str):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                              locale="en-US", reduced_motion="reduce",
                              color_scheme="dark")
    ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
    ctx.add_init_script(B.INIT_JS)
    ctx.add_init_script(B.BENCH_JS)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(url + "/index.html", wait_until="load")
    page.wait_for_timeout(400)
    B.load_image(page, B.FIXTURE_1080)
    return ctx, page, B.cdp_session(page), errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="dither")
    ap.add_argument("--colorMode", default="palette")
    ap.add_argument("--palette", default="Grayscale 16")
    ap.add_argument("--ditherKernel", default="floyd-steinberg")
    ap.add_argument("--effects", default="")
    ap.add_argument("--adj", default="")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--label", default="")
    ap.add_argument("--workdir", default="/tmp/opencode/glyphcraft_speed_old")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cfg = {"mode": args.mode, "effects": [e for e in args.effects.split(",") if e],
           "params": {}, "full": False,
           "colorMode": args.colorMode, "palette": args.palette,
           "ditherKernel": args.ditherKernel}
    if args.adj:
        cfg["adj"] = json.loads(args.adj)
    if args.full:
        cfg["full"] = True

    B.fixtures()
    old_dir = Path(args.workdir)
    unpack(args.rev, old_dir)
    rows: list[dict] = []
    samples = {"new": [], "old": []}

    with TreeServer(ROOT) as new_srv, TreeServer(old_dir) as old_srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            new_ctx, new_page, new_cdp, new_errors = open_page(browser, new_srv.url)
            old_ctx, old_page, old_cdp, old_errors = open_page(browser, old_srv.url)
            sides = {"new": (new_page, new_cdp), "old": (old_page, old_cdp)}
            hashes = {}
            try:
                for window in range(WINDOWS):
                    order = ["new", "old"] if window % 2 == 0 else ["old", "new"]
                    pair = [order[0], order[1], order[1], order[0]]
                    for which in pair:
                        page, cdp = sides[which]
                        B.gc(cdp)
                        page.wait_for_timeout(30)
                        page.evaluate("(c) => window.__benchRender(c)", cfg)  # warm-up
                    timings = {"new": [], "old": []}
                    for which in pair:
                        page, cdp = sides[which]
                        B.gc(cdp)
                        page.wait_for_timeout(30)
                        timings[which].append(page.evaluate("(c) => window.__benchRender(c).ms", cfg))
                    value = {k: statistics.median(v) for k, v in timings.items()}
                    rows.append(value)
                    samples["new"].extend(timings["new"])
                    samples["old"].extend(timings["old"])
                    print(f"window {window + 1}: new={value['new']:.2f}ms "
                          f"old={value['old']:.2f}ms "
                          f"ratio={value['new'] / value['old']:.3f}", flush=True)
                for which, (page, cdp) in sides.items():
                    hashes[which] = page.evaluate(
                        "(c) => window.__benchRender(c).hash", cfg)
            finally:
                new_ctx.close()
                old_ctx.close()
        finally:
            browser.close()

    def p95(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]

    median_new = statistics.median(r["new"] for r in rows)
    median_old = statistics.median(r["old"] for r in rows)
    faster = sum(1 for r in rows if r["new"] / r["old"] <= 0.90)
    print(f"all samples: new median={statistics.median(samples['new']):.2f}ms "
          f"p95={p95(samples['new']):.2f}ms | old median={statistics.median(samples['old']):.2f}ms "
          f"p95={p95(samples['old']):.2f}ms")
    print(f"window medians: new={[round(r['new'], 1) for r in rows]} "
          f"old={[round(r['old'], 1) for r in rows]}")
    print(f"median new={median_new:.2f}ms old={median_old:.2f}ms "
          f"ratio={median_new / median_old:.3f} faster_windows={faster}/{len(rows)}")
    print(f"hash new={hashes.get('new')} old={hashes.get('old')} "
          f"{'IDENTICAL' if hashes.get('new') == hashes.get('old') else 'DIFFERENT'}")
    errors = new_errors + old_errors
    if errors:
        print("page errors:", errors[:5])
    verdict = faster >= 4 and hashes.get("new") == hashes.get("old") and not errors
    print("SPEED PASS" if verdict else "SPEED FAIL")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"label": args.label or args.mode, "cfg": cfg, "rev": args.rev,
             "windows": rows, "samples": samples,
             "median_new": median_new, "median_old": median_old,
             "p95_new": p95(samples["new"]), "p95_old": p95(samples["old"]),
             "faster_windows": faster, "hashes": hashes, "errors": errors},
            indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(old_dir, ignore_errors=True)
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
