#!/usr/bin/env python3
"""Machine canary: is the desktop quiet enough to start a timing run?

A blank page, no application code. Measured floor on this box: Firefox stalls
once for ~150 ms within seconds of launch at ~13 % I/O pressure, Chromium never
stalls, and Firefox is clean after its first 3 s. The canary therefore warms up
8 s and then requires 60 s with no frame gap over 40 ms in either browser.

Exit 0 if the machine is usable, 1 if a run should be postponed.

    python tools/machine_canary.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WAIT = 8000
SPAN = 60000
LIMIT = 40

JS = f"""
async () => {{
  const gaps = [];
  let last = performance.now();
  let stop = false;
  const tick = (now) => {{ gaps.push(now - last); last = now;
                          if (!stop) requestAnimationFrame(tick); }};
  requestAnimationFrame(tick);
  await new Promise(r => setTimeout(r, {SPAN}));
  stop = true;
  return {{frames: gaps.length, worst: Math.round(Math.max(...gaps) * 10) / 10,
           over: gaps.filter(g => g > {LIMIT}).length}};
}}
"""


def main() -> int:
    bad = []
    with sync_playwright() as p:
        for name in ("chromium", "firefox"):
            browser = getattr(p, name).launch(headless=True)
            page = browser.new_page()
            page.goto("data:text/html,<title>canary</title><body>blank</body>",
                      wait_until="load")
            page.wait_for_timeout(WAIT)
            data = page.evaluate(JS)
            browser.close()
            load = Path("/proc/loadavg").read_text().split()[:3]
            print(f"canary {name}: frames={data['frames']} worst={data['worst']}ms "
                  f"over{LIMIT}={data['over']} load={' '.join(load)}", flush=True)
            if data["worst"] > LIMIT:
                bad.append(name)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
