#!/usr/bin/env python3
"""L1 parity probe: fused video pixel path vs the unfused path.

`applyEffects` fuses posterize/duotone and hands the ImageData to
`renderScript` only when `state.sourceType === "video"`. Golden (G20) only
renders images, so this probe drives the same paused video frame through both
paths and requires identical canvas hashes:

  fuse on  : state.sourceType = "video"  (batch + autoLevels in one buffer)
  fuse off : state.sourceType = "image"  (one pass per effect, re-read, the
             pre-L1 code path; no other code depends on the flag here)

Writes docs/evidence/<GATE_TASK>/parity-video.json and exits 1 on any mismatch.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "gate"))

import perf_check as pc  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence" / os.environ.get("GATE_TASK", "l1")
STACKS = {
    "light2": ["posterize", "duotone"],
    "posterize": ["posterize"],
    "duotone": ["duotone"],
    "light2+autoLevels-off": ["posterize", "duotone"],
}
TIMES = (0.5, 2.0, 5.0)

PROBE_JS = r"""
(t) => {
  const v = state.video;
  v.pause(); stopVideoLoop();
  return new Promise(res => {
    const go = () => res();
    if (Math.abs(v.currentTime - t) > 0.001) {
      v.addEventListener("seeked", go, {once: true});
      v.currentTime = t;
      setTimeout(go, 2500);
    } else go();
  });
}
"""

HASH_JS = r"""
(ids) => {
  const opts = renderOpts();
  opts.mode = "script";
  opts.effects = state.opts.effects.map(fx => ({
    ...fx, enabled: ids.includes(fx.id),
    params: {...effectDefaults(fx.id), ...(fx.params || {})},
  }));
  const full = computeOutputSize(state.sourceW, state.sourceH,
    state.opts.outputPreset, state.opts.outputWidth,
    state.opts.outputHeight, state.opts.outputFit);
  const pv = previewSize(full);
  const run = (type) => {
    const prev = state.sourceType;
    state.sourceType = type;
    const c = document.createElement("canvas");
    c.width = pv.w; c.height = pv.h;
    const ctx = c.getContext("2d", {willReadFrequently: true});
    const base = prepareBase(state.video, pv.w, pv.h, opts, null);
    renderToContext(base, ctx, pv.w, pv.h, opts);
    state.sourceType = prev;
    return canvasHash(c);
  };
  return {size: [pv.w, pv.h], fused: run("video"), plain: run("image")};
}
"""


def main() -> int:
    pc.make_fixtures()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = []
    with pc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US")
        page = ctx.new_page()
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(500)
        pc.load_video(page, pc.WORK / "src-1280x720.webm")
        for name, ids in STACKS.items():
            if name.endswith("autoLevels-off"):
                page.evaluate("() => { state.opts.autoLevels = false; }")
            for t in TIMES:
                page.evaluate(PROBE_JS, t)
                page.wait_for_timeout(250)
                r = page.evaluate(HASH_JS, ids)
                ok = r["fused"] == r["plain"]
                rows.append({"stack": name, "time": t, "size": r["size"],
                             "fused": r["fused"], "plain": r["plain"], "ok": ok})
                print(("PASS " if ok else "FAIL ") + f"{name} t={t}s "
                      f"size={r['size']} fused={r['fused']} plain={r['plain']}",
                      flush=True)
            page.evaluate("() => { state.opts.autoLevels = true; }")
        browser.close()
    out = {"cases": rows, "failures": [r for r in rows if not r["ok"]]}
    (EVIDENCE / "parity-video.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{len(rows)} cases, {len(out['failures'])} mismatch(es)")
    return 1 if out["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
