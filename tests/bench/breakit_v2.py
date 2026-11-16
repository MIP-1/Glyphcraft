#!/usr/bin/env python3
"""V2 break-it: hostile and edge cases around the real video export.

Runs in Chromium through the real UI. Each case must end with the app usable,
no stuck busy flag, no unhandled page error and the expected download count.

Usage:
  python tests/bench/breakit_v2.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "gate"))
sys.path.insert(0, str(ROOT / "tools"))
import video_real_flow as vrf  # noqa: E402
import v2_export_matrix as matrix  # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence" / "v2"
OUT = Path("/tmp/opencode/v2-breakit")
SHORT = matrix.make_clip("matrix-1280x720.mp4", 1280, 720, 2.0)
SMALL = matrix.make_clip("matrix-1920x1080.mp4", 1920, 1080, 2.0)
BIG = vrf.WORK / "src-3840x2160.webm"


def main() -> int:
    vrf.make_videos()
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    problems: list[str] = []

    def record(name: str, detail: dict, ok: bool) -> None:
        rows.append({"name": name, "detail": detail, "ok": ok})
        print(("PASS " if ok else "FAIL ") + name + ": " + json.dumps(detail)[:400],
              flush=True)
        if not ok:
            problems.append(name)

    def app_state(page) -> dict:
        return page.evaluate("""() => ({
          busy: !!state.videoExporting,
          active: !!state.exportProgress.active,
          frames: state.videoExportFrames || 0,
          button: document.getElementById('btn-export').textContent.trim(),
          enabled: !document.getElementById('btn-export').disabled,
          source: state.sourceType,
          hash: window.__gcHash ? window.__gcHash(document.getElementById('canvas')) : null,
          toast: (document.querySelector('.toast') || {}).textContent || '',
        })""")

    def wait_idle(page, timeout=180000) -> dict:
        page.wait_for_function("() => !state.videoExporting", timeout=timeout)
        page.wait_for_timeout(300)
        return app_state(page)

    with vrf.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  accept_downloads=True, locale="en-US")
        page = ctx.new_page()
        errors: list[str] = []
        expected_errors: list[str] = []
        page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
        page.on("console", lambda m: errors.append("console: " + m.text)
                if m.type == "error" else None)
        downloads: list[str] = []
        page.on("download", lambda d: downloads.append(d.suggested_filename))
        vrf.page_ready(page, srv)
        vrf.set_effects(page, vrf.LIGHT)

        def load(path: Path) -> None:
            vrf.load_video(page, path)

        def preset(kind: str, fit: str = "contain") -> None:
            page.evaluate("""(opts) => {
              Object.assign(state.opts, opts);
              syncOutputControls();
              scheduleRender(0);
            }""", {"outputPreset": kind, "outputFit": fit,
                    "outputWidth": 640, "outputHeight": 360})

        # 1. a blocked muxer module fails with a toast, not a stuck panel.
        load(SHORT)
        page.route("**/vendor/webm-muxer.js*", lambda route: route.abort())
        downloads.clear()
        page.select_option("#export-format", "webm")
        page.click("#btn-export")
        state = wait_idle(page, timeout=30000)
        page.unroute("**/vendor/webm-muxer.js*")
        blocked = [e for e in errors if "ERR_FAILED" in e]
        record("a missing muxer reports a failure and unlocks the app",
               {"downloads": list(downloads), **state,
                "expectedConsoleErrors": blocked},
               not downloads and not state["busy"] and state["enabled"]
               and "failed" in state["toast"].lower())
        expected_errors = list(errors)

        # 1. cancel before the first frame: no download, app clean.
        load(SHORT)
        preset("custom")
        downloads.clear()
        page.evaluate("() => { state.opts.exportFormat = 'webm'; syncUIFromState(); }")
        page.click("#btn-export")
        page.wait_for_timeout(150)
        page.click("#export-cancel")
        state = wait_idle(page)
        record("cancel before the first frame leaves no download",
               {"downloads": list(downloads), **state},
               not downloads and not state["busy"] and state["enabled"])

        # 2. cancel a 4K export, then export again immediately.
        load(BIG)
        downloads.clear()
        page.select_option("#export-format", "webm")
        page.click("#btn-export")
        page.wait_for_function("() => (state.videoExportFrames || 0) >= 2",
                               timeout=120000)
        page.click("#export-cancel")
        wait_idle(page)
        preset("custom")
        page.click("#btn-export")
        state = wait_idle(page, timeout=600000)
        record("export works again right after a cancelled 4K export",
               {"downloads": list(downloads), **state},
               len(downloads) == 1 and downloads[0].endswith(".webm")
               and not state["busy"] and state["enabled"])

        # 3. switching the format mid-export must not change the running file.
        load(SHORT)
        preset("custom")
        downloads.clear()
        page.select_option("#export-format", "webm")
        page.click("#btn-export")
        page.wait_for_function("() => (state.videoExportFrames || 0) >= 1",
                               timeout=60000)
        page.select_option("#export-format", "mp4")
        state = wait_idle(page)
        record("format switch mid-export keeps the started format",
               {"downloads": list(downloads), **state},
               len(downloads) == 1 and downloads[0].endswith(".webm")
               and not state["busy"])

        # 4. page render and export after a theme toggle.
        before = page.evaluate("() => document.documentElement.dataset.theme")
        page.click("#theme-toggle")
        page.wait_for_timeout(300)
        after = page.evaluate("() => document.documentElement.dataset.theme")
        record("theme toggle changes the theme", {"before": before, "after": after},
               before != after)
        downloads.clear()
        page.select_option("#export-format", "webm")
        page.click("#btn-export")
        state = wait_idle(page)
        ui = page.evaluate("""() => {
          const el = document.getElementById('export-progress');
          return {hidden: el.hidden || getComputedStyle(el).display === 'none',
                  text: document.getElementById('btn-export').textContent.trim()};
        }""")
        record("theme toggle leaves the export UI and export working",
               {"downloads": list(downloads), "ui": ui, **state},
               len(downloads) == 1 and ui["hidden"] and not state["busy"])

        # 6. Export Frame is inert while a video export runs.
        load(SHORT)
        downloads.clear()
        page.select_option("#export-format", "webm")
        page.click("#btn-export")
        page.wait_for_function("() => (state.videoExportFrames || 0) >= 1",
                               timeout=60000)
        page.click("#btn-export-frame")
        page.wait_for_timeout(300)
        mid = app_state(page)
        state = wait_idle(page)
        record("Export Frame cannot interrupt a running video export",
               {"downloads": list(downloads), "mid": mid, **state},
               len(downloads) == 1 and downloads[0].endswith(".webm")
               and mid["busy"] and not state["busy"])

        # 7. the progress panel and Cancel are usable at 700 px.
        page.set_viewport_size({"width": 700, "height": 900})
        page.wait_for_timeout(300)
        load(SHORT)
        downloads.clear()
        page.select_option("#export-format", "webm")
        page.click("#btn-export")
        page.wait_for_function("() => (state.videoExportFrames || 0) >= 1",
                               timeout=60000)
        box = page.evaluate("""() => {
          const el = document.getElementById('export-progress');
          const btn = document.getElementById('export-cancel');
          const r = el.getBoundingClientRect();
          const b = btn.getBoundingClientRect();
          return {panel: [r.left, r.top, r.right, r.bottom],
                  cancel: [b.left, b.top, b.right, b.bottom],
                  visible: !el.hidden && getComputedStyle(el).display !== 'none'};
        }""")
        record("progress and Cancel fit the 700 px layout",
               {"box": box, "downloads": list(downloads)},
               box["visible"] and box["panel"][0] >= 0
               and box["panel"][2] <= 700 and box["cancel"][2] <= 700)
        page.click("#export-cancel")
        wait_idle(page)
        page.set_viewport_size({"width": 1440, "height": 1000})

        # 9. loading a new file while an export runs must not wedge the app.
        load(SHORT)
        downloads.clear()
        try:
            page.select_option("#export-format", "webm")
            page.click("#btn-export")
            page.wait_for_function("() => (state.videoExportFrames || 0) >= 1",
                                   timeout=60000)
            page.set_input_files("#file-input", str(SMALL))
            page.wait_for_function(
                "() => state.sourceType === 'video' && state.video.readyState >= 2",
                timeout=120000)
            state = wait_idle(page, timeout=240000)
            page.wait_for_timeout(500)
            after = app_state(page)
            record("loading a new video mid-export leaves a usable app",
                   {"downloads": list(downloads), "state": state, "after": after},
                   not state["busy"] and after["source"] == "video"
                   and after["hash"] is not None)
        except Exception as exc:  # noqa: BLE001
            state = app_state(page)
            record("loading a new video mid-export leaves a usable app",
                   {"error": str(exc), "state": state}, False)

        # 10. no source: the export action is a clean no-op.
        page.evaluate("() => { state.source = null; state.sourceType = null; syncOutputControls(); }")
        downloads.clear()
        page.evaluate("() => exportImage()")
        page.wait_for_timeout(400)
        state = app_state(page)
        record("export with no source is a clean no-op",
               {"downloads": list(downloads), **state},
               not downloads and not state["busy"])

        page.wait_for_timeout(300)
        unexpected = errors[len(expected_errors):]
        record("no page or console errors",
               {"want": 0, "expected": expected_errors[:3],
                "unexpected": unexpected[:8]}, not unexpected)
        browser.close()

    payload = {"rows": rows, "problems": problems,
               "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    (EVIDENCE / "breakit.json").write_text(json.dumps(payload, indent=1),
                                           encoding="utf-8")
    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    for name in problems:
        print("FAIL", name)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
