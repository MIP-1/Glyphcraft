#!/usr/bin/env python3
"""P2-1 break-it cases: the compare split under hostile input.

Not a gate check. These are the five (six) ways the cached-band split could be
wrong, driven through the real browser and the real pointer handlers:

  1. 4K source with the heavy stack, long drag.
  2. zoom + pan, then drag.
  3. viewport resize while the pointer is down.
  4. undo/redo while the pointer is down.
  5. theme switch while the pointer is down.
  6. 360 px viewport, drag and no horizontal overflow.

Every case asserts the overlay's left edge equals the canvas-space split, no
page error was raised, and (case 1) the per-move render stays under 4 ms with
zero pipeline runs.

usage: python tests/gate/p2_1_breakit.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_check as cc  # noqa: E402
from run_gate import make_png  # noqa: E402

ROWS = []


def record(name, detail, ok):
    ROWS.append((name, detail, ok))
    print(f"{name:34} {detail}  {'PASS' if ok else 'FAIL'}")


def ensure_fixtures():
    if not cc.FIXTURE.exists():
        make_png(cc.FIXTURE, width=900, height=600, seed=0)
    if not cc.FIXTURE_4K.exists():
        make_png(cc.FIXTURE_4K, width=4000, height=3000, seed=5)
    from PIL import Image
    Image.open(cc.FIXTURE).convert("RGB").resize((1280, 720)).save(cc.FIXTURE_1280)


def split_state(page):
    return page.evaluate("""() => {
      const c = document.getElementById('canvas');
      const expected = state.pan.x + c.width * state.scale * state.compareFrac;
      const left = parseFloat(document.getElementById('compare-slider').style.left);
      return {
        frac: state.compareFrac, expected, left,
        hidden: document.getElementById('compare-overlay').hidden,
        compare: state.compare,
        theme: document.documentElement.dataset.theme,
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        w: c.width, h: c.height,
      };
    }""")


def split_ok(data, changed_from=None):
    ok = (not data["hidden"] and data["compare"]
          and abs(data["left"] - data["expected"]) <= 1
          and 0 <= data["frac"] <= 1)
    if changed_from is not None:
        ok = ok and abs(data["frac"] - changed_from) > 0.01
    return ok


LAST = {"span": 260}


def prepare(page, frac=0.35):
    """Put the split at `frac` in the middle of the canvas area."""
    page.evaluate(
        """(f) => {
          state.compareFrac = f;
          const a = els.canvasArea.getBoundingClientRect();
          state.pan.x = a.width / 2 - els.canvas.width * state.scale * f;
          state.pan.y = a.height / 2 - els.canvas.height * state.scale / 2;
          applyTransform();
          updateCompareUI();
          scheduleRender(0);
        }""",
        frac,
    )
    cc.settle(page, quiet_ms=120)


def handle_x(page):
    return page.evaluate(
        "() => document.getElementById('canvas-area').getBoundingClientRect().left"
        " + state.pan.x + document.getElementById('canvas').width * state.scale * state.compareFrac"
    )


def drag(page, steps=80, span=260):
    """Continuous Python-driven drag from the current handle position."""
    box = page.locator("#compare-slider").bounding_box()
    start = handle_x(page)
    y = box["y"] + box["height"] / 2
    room = page.viewport_size["width"] - 2 - start
    used = max(40, min(span, room))
    LAST["span"] = used
    page.mouse.move(start, y)
    page.mouse.down()
    for i in range(1, steps + 1):
        page.mouse.move(start + used * i / steps, y)
    return y


def finish(page, y=None, span=None):
    box = page.locator("#compare-slider").bounding_box()
    if y is None:
        y = box["y"] + box["height"] / 2
    if span is None:
        span = LAST["span"]
    start = handle_x(page)
    page.mouse.move(start + span, y)
    page.mouse.up()
    cc.settle(page)


def main():
    ensure_fixtures()
    problems = []
    with cc.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_init_script(cc.INIT_JS)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.evaluate(cc.PATCH_JS)

        # 1. 4K heavy, long drag
        cc.load(page, cc.FIXTURE_4K)
        cc.enable_effects(page, cc.HEAVY)
        cc.ensure_compare(page, True)
        cc.set_frac(page, 0.35)
        before_frac = page.evaluate("() => state.compareFrac")
        cc.reset(page)
        fr = cc.drag_frames(page, frames=120, span=260, warmup=40)
        dr = cc.perf(page)
        data = split_state(page)
        ms = sorted(dr["renderMs"])
        p90 = ms[min(len(ms) - 1, int(len(ms) * 0.9))] if ms else None
        ok = (split_ok(data, before_frac) and dr["pipeline"] == 0
              and p90 is not None and p90 <= 4.0)
        record("4K heavy drag", f"{data['w']}x{data['h']} frames={fr['frames']} "
                                f"render p90={p90}ms pipeline={dr['pipeline']} "
                                f"left={data['left']:.1f} expected={data['expected']:.1f}", ok)

        # 2. zoom + pan, then drag
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.keyboard.press("2")
        cc.settle(page, quiet_ms=120)
        page.mouse.move(700, 500)
        page.mouse.down(button="middle")
        page.mouse.move(760, 540, steps=4)
        page.mouse.up(button="middle")
        cc.settle(page, quiet_ms=120)
        before_frac = page.evaluate("() => state.compareFrac")
        y = drag(page, steps=40)
        finish(page)
        data = split_state(page)
        record("zoom+pan drag", f"zoom={page.evaluate('() => state.zoom')} "
                                f"pan={page.evaluate('() => [state.pan.x, state.pan.y]')} "
                                f"left={data['left']:.1f} expected={data['expected']:.1f}", split_ok(data, before_frac))

        # 3. resize while the pointer is down
        page.set_viewport_size({"width": 1440, "height": 1000})
        prepare(page)
        before_frac = page.evaluate("() => state.compareFrac")
        y = drag(page, steps=20)
        page.set_viewport_size({"width": 1100, "height": 800})
        finish(page)
        data = split_state(page)
        record("resize mid-drag", f"viewport=1100x800 w={data['w']} "
                                  f"left={data['left']:.1f} expected={data['expected']:.1f}",
               split_ok(data, before_frac))

        # 4. undo/redo while the pointer is down
        page.set_viewport_size({"width": 1440, "height": 1000})
        prepare(page)
        before_frac = page.evaluate("() => state.compareFrac")
        before_opts = page.evaluate("() => JSON.stringify(state.opts)")
        y = drag(page, steps=20)
        page.keyboard.press("Control+z")
        finish(page)
        data = split_state(page)
        after_opts = page.evaluate("() => JSON.stringify(state.opts)")
        undo_changed = before_opts != after_opts
        record("undo mid-drag", f"optsChanged={undo_changed} "
                                f"left={data['left']:.1f} expected={data['expected']:.1f}",
               split_ok(data, before_frac) and undo_changed)
        page.keyboard.press("Control+Shift+z")
        cc.settle(page)
        data = split_state(page)
        redone_opts = page.evaluate("() => JSON.stringify(state.opts)")
        record("redo after drag", f"optsRestored={redone_opts == before_opts} "
                                  f"left={data['left']:.1f} expected={data['expected']:.1f}",
               split_ok(data, before_frac) and redone_opts == before_opts)

        # 5. theme switch while the pointer is down
        before = page.evaluate("() => document.documentElement.dataset.theme")
        prepare(page)
        before_frac = page.evaluate("() => state.compareFrac")
        y = drag(page, steps=20)
        page.evaluate("() => document.getElementById('theme-toggle').click()")
        page.wait_for_timeout(250)
        finish(page)
        data = split_state(page)
        after = data["theme"]
        record("theme switch mid-drag", f"{before}->{after} left={data['left']:.1f} "
                                        f"expected={data['expected']:.1f}",
               split_ok(data, before_frac) and after != before)

        # 6. 360 px viewport
        page.set_viewport_size({"width": 360, "height": 720})
        page.wait_for_timeout(400)
        prepare(page)
        before_frac = page.evaluate("() => state.compareFrac")
        y = drag(page, steps=30, span=80)
        finish(page, y, span=80)
        data = split_state(page)
        record("360px drag", f"w={data['w']} left={data['left']:.1f} "
                              f"expected={data['expected']:.1f} overflow={data['overflow']}px",
               split_ok(data, before_frac) and data["overflow"] <= 0)

        if errors:
            problems.extend(errors)
        browser.close()

    print()
    bad = [r for r in ROWS if not r[2]] + problems
    print(f"{len(ROWS)} cases, {len(bad)} failure(s)")
    for row in ROWS:
        if not row[2]:
            print(f"  FAIL {row[0]}: {row[1]}")
    for e in problems:
        print(f"  PAGE ERROR {e}")
    print("BREAKIT " + ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
