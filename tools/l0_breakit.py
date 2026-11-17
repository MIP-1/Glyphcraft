#!/usr/bin/env python3
"""Eight ways the L0/G23 measurement could lie, driven in a real browser.

Not a gate check. Each probe prints PASS/FAIL for the measurement contract, not
for app quality; a FAIL means the number G23 reports would be untrustworthy.
Run before L1 (pre-fix) and after L1 (post-fix); the sharpness rows are expected
to be FAIL before the fix and PASS after it.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "gate"))
from perf_check import (INIT_JS, LIGHT, WORK, Server, load_video, make_fixtures,
                        pct, seek_paused, set_effects)
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "l0"
FIXTURE_IMAGE = Path("/tmp/glyphcraft_gate_fixture.png")
rows: list[dict] = []


def check(name: str, detail: str, ok: bool) -> None:
    rows.append({"name": name, "detail": detail, "ok": ok})
    print(("PASS " if ok else "FAIL ") + f"{name}: {detail}", flush=True)


def sharp(page) -> dict:
    return page.evaluate("""() => {
      const c = document.getElementById('canvas');
      const r = c.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      return {backing: [c.width, c.height], css: [+r.width.toFixed(1), +r.height.toFixed(1)],
              dpr, zoom: +state.zoom.toFixed(3),
              need: [+Math.min(state.sourceW, r.width * dpr).toFixed(1),
                     +Math.min(state.sourceH, r.height * dpr).toFixed(1)]};
    }""")


def main() -> int:
    make_fixtures()
    before = {p.name: p.stat().st_mtime for p in WORK.glob("src-*.webm")}
    make_fixtures()
    after = {p.name: p.stat().st_mtime for p in WORK.glob("src-*.webm")}
    check("fixtures are reused, not regenerated", f"{sorted(after)}", before == after)

    with Server() as srv, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(500)
        page.evaluate(INIT_JS)
        load_video(page, WORK / "src-1920x1080.webm")
        page.evaluate("() => fitToWindow()")
        page.wait_for_timeout(250)
        for zoom in (1.12, 2.0):
            page.evaluate("(z) => setZoom(z)", zoom)
            page.wait_for_timeout(250)
            s = sharp(page)
            covers = (s["backing"][0] + 0.5 >= s["need"][0]
                      and s["backing"][1] + 0.5 >= s["need"][1])
            check(f"DPR1 zoom {zoom} sharpness is measured from the real canvas",
                  f"backing={s['backing']} need={s['need']} covers={covers}", covers)

        set_effects(page, LIGHT)
        seek_paused(page, 0.3)
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(1200)
        page.evaluate("() => window.__g23Reset()")
        time.sleep(4.0)
        data = page.evaluate("""() => ({renders: __g23.renders,
          rvfc: __g23.rvfc, ms: __g23.ms.slice(), paused: state.video.paused})""")
        check("the render wrapper counts the video loop",
              f"renders={data['renders']} rvfc={data['rvfc']} p50={pct(data['ms'], 0.5)}",
              data["renders"] > 0 and data["rvfc"] > 0)

        pauses = []
        for _ in range(3):
            box = page.locator("#video-toggle").bounding_box()
            t0 = time.time()
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_function("() => state.video.paused", timeout=8000)
            pauses.append(round((time.time() - t0) * 1000, 1))
            page.evaluate("() => { state.video.play().catch(() => {}); }")
            page.wait_for_timeout(500)
        playing = page.evaluate("() => !state.video.paused")
        check("pause samples resume playback afterwards",
              f"pauses={pauses} playing={playing}", playing)
        page.evaluate("() => { state.video.pause(); stopVideoLoop(); }")
        ctx.close()

        # DPR 2: 1080p must ask for 1920 physical pixels.
        ctx2 = b.new_context(viewport={"width": 1440, "height": 1000},
                             device_scale_factor=2, locale="en-US")
        page2 = ctx2.new_page()
        err2 = []
        page2.on("pageerror", lambda e: err2.append(str(e)))
        page2.goto(srv.url + "/index.html", wait_until="load")
        page2.wait_for_timeout(500)
        load_video(page2, WORK / "src-1920x1080.webm")
        page2.evaluate("() => fitToWindow()")
        page2.wait_for_timeout(250)
        page2.evaluate("() => setZoom(1)")
        page2.wait_for_timeout(250)
        s = sharp(page2)
        covers = (s["backing"][0] + 0.5 >= s["need"][0]
                  and s["backing"][1] + 0.5 >= s["need"][1])
        check("DPR2 zoom 1 uses devicePixelRatio from the context",
              f"dpr={s['dpr']} backing={s['backing']} need={s['need']} covers={covers}",
              s["dpr"] == 2 and covers)
        ctx2.close()

        # 720p has no physical need above its native size.
        ctx3 = b.new_context(viewport={"width": 1440, "height": 1000},
                             device_scale_factor=2, locale="en-US")
        page3 = ctx3.new_page()
        err3 = []
        page3.on("pageerror", lambda e: err3.append(str(e)))
        page3.goto(srv.url + "/index.html", wait_until="load")
        page3.wait_for_timeout(500)
        load_video(page3, WORK / "src-1280x720.webm")
        page3.evaluate("() => { fitToWindow(); setZoom(2); }")
        page3.wait_for_timeout(300)
        s = sharp(page3)
        check("720p backing is never raised above the source",
              f"backing={s['backing']} source need={s['need']}",
              s["backing"][0] <= 1280 and s["backing"][1] <= 720)
        ctx3.close()

        # Light theme must not change the measurement path.
        ctx4 = b.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US",
                             color_scheme="light")
        page4 = ctx4.new_page()
        err4 = []
        page4.on("pageerror", lambda e: err4.append(str(e)))
        page4.add_init_script("try{localStorage.setItem('glyphcraft-theme','light')}catch(e){}")
        page4.goto(srv.url + "/index.html", wait_until="load")
        page4.wait_for_timeout(500)
        page4.evaluate(INIT_JS)
        load_video(page4, WORK / "src-1280x720.webm")
        set_effects(page4, LIGHT)
        seek_paused(page4, 0.3)
        page4.evaluate("() => { state.video.play().catch(() => {}); }")
        page4.wait_for_timeout(900)
        page4.evaluate("() => window.__g23Reset()")
        time.sleep(3.0)
        run = page4.evaluate("() => ({renders: __g23.renders, ms: __g23.ms.slice(),"
                             " theme: document.documentElement.dataset.theme ||"
                             " localStorage.getItem('glyphcraft-theme')})")
        check("light theme renders through the same wrapper",
              f"renders={run['renders']} p50={pct(run['ms'], 0.5)} theme={run['theme']}",
              run["renders"] > 0)
        ctx4.close()

        # Worker-disabled URL must still open and render an image.
        page5 = b.new_page()
        err5 = []
        page5.on("pageerror", lambda e: err5.append(str(e)))
        page5.goto(srv.url + "/index.html?worker=0", wait_until="load")
        page5.wait_for_timeout(500)
        page5.set_input_files("#file-input", str(FIXTURE_IMAGE))
        page5.wait_for_function("() => state.sourceType === 'image'", timeout=30000)
        page5.wait_for_timeout(800)
        hash = page5.evaluate("() => canvasHash(document.getElementById('canvas'))")
        check("worker=0 path still renders", f"hash={hash}", bool(hash) and not err5)
        page5.close()

        check("no page errors in any probe",
              repr((errors + err2 + err3 + err4)[:4]), not (errors or err2 or err3 or err4))
        b.close()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "breakit.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    bad = [r for r in rows if not r["ok"]]
    print(f"{len(rows)} probes, {len(bad)} failure(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
