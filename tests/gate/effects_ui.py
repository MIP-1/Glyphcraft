#!/usr/bin/env python3
"""H2 UI-driven effect check: every effect is enabled and driven through the
real controls (drag, stepper clicks, typing, wheel), then the app's own
prepareBase() output is measured. A white/blank base is a failure.

Also exercises the global paths: preset load, undo/redo, theme toggle in the
middle, and replacing the image after an effect was set.

usage: python tests/gate/effects_ui.py [--shots docs/evidence/h2]
"""
import argparse
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = [Path("/tmp/glyphcraft_gate_fixture.png"), Path("/tmp/glyphcraft_gate_4k.png")]

STATS_JS = r"""
() => {
  const w = 320, h = 240;
  const base = prepareBase(state.source, w, h, state.opts);
  const d = base.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, w, h).data;
  let sum = 0, sum2 = 0, n = 0, alphaBad = 0;
  for (let i = 0; i < d.length; i += 4) {
    const l = 0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2];
    sum += l; sum2 += l * l; n++;
    if (d[i+3] !== 255) alphaBad++;
  }
  const mean = sum / n / 255;
  const std = Math.sqrt(Math.max(0, sum2 / n - (sum / n) ** 2)) / 255;
  return {mean: +mean.toFixed(4), std: +std.toFixed(4), alphaBad, w, h};
}
"""

CANVAS_JS = r"""
() => {
  const c = document.getElementById('canvas');
  const d = c.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, c.width, c.height).data;
  let sum = 0, sum2 = 0, n = 0;
  for (let i = 0; i < d.length; i += 4) {
    const l = 0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2];
    sum += l; sum2 += l * l; n++;
  }
  const mean = sum / n / 255;
  return {mean: +mean.toFixed(4), std: +(Math.sqrt(Math.max(0, sum2 / n - (sum / n) ** 2)) / 255).toFixed(4)};
}
"""


def blank(stats):
    return stats["mean"] >= 0.97 and stats["std"] <= 2 / 255


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="")
    args = ap.parse_args()
    shots = Path(args.shots).resolve() if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    problems = []
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{httpd.server_port}/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIXTURES[0]))
        page.wait_for_selector(".canvas-area.has-content", timeout=20000)
        page.wait_for_timeout(600)
        page.evaluate("""() => document.querySelectorAll('.panel-section.collapsed').forEach(s => {
          if (getComputedStyle(s).display === 'none') return;
          const t = s.querySelector('.section-title'); if (t) t.click(); })""")
        page.wait_for_timeout(200)

        effects = page.evaluate("() => EFFECTS.map(e => ({id: e.id, params: e.params}))")

        for effect in effects:
            eid = effect["id"]
            item = page.locator(f'.effect-item[data-id="{eid}"]')
            if item.count() == 0:
                problems.append(f"{eid}: no effect row in the panel")
                continue
            item.scroll_into_view_if_needed()
            check = item.locator('input[type="checkbox"]')
            check.check()
            page.wait_for_timeout(120)

            numeric = [q for q in effect["params"] if q.get("type") not in ("color", "select")]
            steps = []
            if numeric:
                q = numeric[0]
                slider = item.locator('input[type="range"]').first
                box = slider.bounding_box()
                if box:
                    # drag to ~85% of the track
                    x = box["x"] + box["width"] * 0.85
                    y = box["y"] + box["height"] / 2
                    page.mouse.move(box["x"] + box["width"] * 0.5, y)
                    page.mouse.down()
                    page.mouse.move(x, y, steps=6)
                    page.mouse.up()
                    page.wait_for_timeout(220)
                    steps.append("drag")
                stepper = item.locator('.step-btn[data-step="up"]').first
                if stepper.count():
                    sb = stepper.bounding_box()
                    page.mouse.move(sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2)
                    for _ in range(15):
                        page.mouse.click(sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2)
                    page.wait_for_timeout(260)
                    steps.append("stepper x15")
                num = item.locator('input[type="number"]').first
                if num.count():
                    nb = num.bounding_box()
                    page.mouse.click(nb["x"] + nb["width"] / 2, nb["y"] + nb["height"] / 2)
                    page.keyboard.press("Control+A")
                    for ch in str(int(q["min"] if int(q["min"]) else 7)) + "0":
                        page.keyboard.type(ch)
                        page.wait_for_timeout(15)
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(260)
                    steps.append("typed digits")
                    page.mouse.move(nb["x"] + nb["width"] / 2, nb["y"] + nb["height"] / 2)
                    page.mouse.wheel(0, -120)
                    page.wait_for_timeout(120)
                    page.mouse.wheel(0, -120)
                    page.wait_for_timeout(260)
                    steps.append("wheel")
            elif any(q.get("type") == "select" for q in effect["params"]):
                sel = item.locator("select").first
                options = sel.locator("option").evaluate_all("os => os.map(o => o.value)")
                sel.select_option(options[-1])
                page.wait_for_timeout(260)
                steps.append(f"select {options[-1]}")
            elif any(q.get("type") == "color" for q in effect["params"]):
                # Two distinct colours: identical Duotone endpoints are a flat
                # tint by definition, not a render bug.
                inputs = item.locator('input[type="color"]')
                palette = ["#102030", "#f0e0d0"]
                for k in range(min(2, inputs.count())):
                    value = palette[k % len(palette)]
                    inputs.nth(k).evaluate("(e, v) => { e.value = v;"
                                           " e.dispatchEvent(new Event('input', {bubbles:true})); }", value)
                page.wait_for_timeout(260)
                steps.append("colours")

            got = page.evaluate("(id) => { const e = state.opts.effects.find(e => e.id === id);"
                                " return e ? {enabled: e.enabled, params: e.params} : null; }", eid)
            stats = page.evaluate(STATS_JS)
            ok = bool(got and got["enabled"]) and not blank(stats) and stats["alphaBad"] == 0
            rows.append((eid, "+".join(steps) or "enable", f"mean={stats['mean']} std={stats['std']}", ok))
            if not ok:
                problems.append(f"{eid}: state={got} stats={stats}")
            if shots:
                page.locator("#canvas-area").screenshot(path=str(shots / f"ui-{eid}.png"))
            check.uncheck()
            page.wait_for_timeout(80)

        # --- global paths -------------------------------------------------
        page.locator('#presets-bar [data-preset="cyber"]').click()
        page.wait_for_timeout(700)
        st = page.evaluate(CANVAS_JS)
        ok = not blank(st)
        rows.append(("preset cyber", "load preset", f"canvas mean={st['mean']} std={st['std']}", ok))
        problems += [] if ok else [f"preset cyber rendered a blank canvas: {st}"]

        page.keyboard.press("Control+z")
        page.wait_for_timeout(500)
        st_undo = page.evaluate(CANVAS_JS)
        page.keyboard.press("Control+Shift+z")
        page.wait_for_timeout(500)
        st_redo = page.evaluate(CANVAS_JS)
        ok = not blank(st_undo) and not blank(st_redo)
        rows.append(("undo/redo", "after preset", f"undo mean={st_undo['mean']} redo mean={st_redo['mean']}", ok))
        problems += [] if ok else [f"undo/redo blank: undo={st_undo} redo={st_redo}"]

        before_theme = page.evaluate("() => document.documentElement.dataset.theme")
        page.locator("body").click(position={"x": 1200, "y": 60})
        page.keyboard.press("t")
        page.wait_for_timeout(600)
        after_theme = page.evaluate("() => document.documentElement.dataset.theme")
        st_theme = page.evaluate(CANVAS_JS)
        ok = not blank(st_theme) and before_theme != after_theme
        rows.append(("theme toggle", "T mid-stack", f"{before_theme}->{after_theme} mean={st_theme['mean']}", ok))
        problems += [] if ok else [f"theme toggle broke the render: {st_theme}"]

        page.set_input_files("#file-input", str(FIXTURES[1]))
        page.wait_for_selector(".canvas-area.has-content", timeout=30000)
        page.wait_for_timeout(900)
        st_new = page.evaluate(CANVAS_JS)
        ok = not blank(st_new)
        rows.append(("replace image", "4K after effects set", f"mean={st_new['mean']} std={st_new['std']}", ok))
        problems += [] if ok else [f"replaced image rendered blank: {st_new}"]

        page.evaluate("""() => { const d = document.createElement('div'); d.id = 'h2-errors'; }""")
        if errors:
            problems.extend(f"PAGE ERROR {e}" for e in errors[:10])
        browser.close()

    httpd.shutdown()
    httpd.server_close()

    print(f"{'effect':16} {'driven by':24} {'base stats':46} verdict")
    for name, how, detail, ok in rows:
        print(f"{name:16} {how:24} {detail:46} {'PASS' if ok else 'FAIL'}")
    print()
    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    for problem in problems:
        print("  FAIL " + problem)
    print("EFFECTS UI " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
