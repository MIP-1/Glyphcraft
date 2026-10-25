#!/usr/bin/env python3
"""H2 break-it checks: 5 ways the effect fix could be wrong or regress.

1. Amount 0 is identity through the real UI, alone and inside a stack.
2. Hatch extremes on 1x1 / 2x2 sources: finite pixels, opaque, deterministic.
3. Junk pasted into Amount (empty, "-", "abc", "1e3", " 50 "): clamped or
   rejected, state stays finite and in range, render stays non-blank.
4. Undo / redo around a Crosshatch parameter change restores both value and
   pixels (hash).
5. 4000x3000 + six-effect stack including Crosshatch: renders, finite, opaque,
   bounded time, no page errors.

usage: python docs/evidence/h2/tools/breakit_h2.py
"""
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("/home/mustafa/glyphcraft")
FIX = Path("/tmp/glyphcraft_gate_fixture.png")
FIX4K = Path("/tmp/glyphcraft_gate_4k.png")

SKETCH = '.effect-item[data-id="sketch"]'
AMOUNT = '#fx\\.sketch\\.amount-num'  # fallback below if ids differ
POSTERIZE = '.effect-item[data-id="posterize"]'


def card_num(item, index):
    return item.locator('input[type="number"]').nth(index)


STATS_JS = r"""
(effects) => {
  const opts = { ...renderOpts(), effects };
  const t0 = performance.now();
  const base = prepareBase(state.source, 320, 240, opts);
  const ms = performance.now() - t0;
  const a = base.getContext('2d', { willReadFrequently: true })
                  .getImageData(0, 0, 320, 240).data;
  let sum = 0, sum2 = 0, n = 0, alphaBad = 0, nonFinite = 0, hash = 2166136261;
  for (let i = 0; i < a.length; i += 4) {
    const l = 0.2126 * a[i] + 0.7152 * a[i + 1] + 0.0722 * a[i + 2];
    if (![a[i], a[i+1], a[i+2], a[i+3]].every(Number.isFinite)) nonFinite++;
    sum += l; sum2 += l * l; n++;
    if (a[i + 3] !== 255) alphaBad++;
    for (let k = 0; k < 4; k++) { hash ^= a[i + k]; hash = Math.imul(hash, 16777619) >>> 0; }
  }
  const mean = sum / n / 255;
  return {
    mean: +mean.toFixed(4),
    std: +(Math.sqrt(Math.max(0, sum2 / n - (sum / n) ** 2)) / 255).toFixed(4),
    alphaBad, nonFinite, hash, ms: +ms.toFixed(1),
    w: base.width, h: base.height
  };
}
"""

BIG_JS = r"""
() => {
  const t0 = performance.now();
  const base = prepareBase(state.source, 4000, 3000, renderOpts());
  const ms = performance.now() - t0;
  const a = base.getContext('2d', { willReadFrequently: true })
                  .getImageData(0, 0, 4000, 3000).data;
  let sum = 0, sum2 = 0, n = 0, alphaBad = 0, nonFinite = 0;
  for (let i = 0; i < a.length; i += 4) {
    const l = 0.2126 * a[i] + 0.7152 * a[i + 1] + 0.0722 * a[i + 2];
    if (![a[i], a[i+1], a[i+2], a[i+3]].every(Number.isFinite)) nonFinite++;
    sum += l; sum2 += l * l; n++;
    if (a[i + 3] !== 255) alphaBad++;
  }
  const mean = sum / n / 255;
  return {
    mean: +mean.toFixed(4),
    std: +(Math.sqrt(Math.max(0, sum2 / n - (sum / n) ** 2)) / 255).toFixed(4),
    alphaBad, nonFinite, ms: +ms.toFixed(1), w: base.width, h: base.height,
    sourceW: state.sourceW, sourceH: state.sourceH
  };
}
"""

SKETCH_4K_JS = r"""
() => {
  const params = { amount: 100, cross: 100 };
  const t0 = performance.now();
  const c = prepareBase(state.source, 4000, 3000,
                        { ...renderOpts(), effects: [{ id: 'sketch', enabled: true, params }] });
  return { ms: +(performance.now() - t0).toFixed(0), w: c.width, h: c.height };
}
"""

TINY_JS = r"""
() => {
  const out = [];
  for (const [w, h] of [[1, 1], [2, 2], [17, 13]]) {
    for (const cross of [0, 50, 100]) {
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      const cx = c.getContext('2d', { willReadFrequently: true });
      if (w > 1) {
        const g = cx.createLinearGradient(0, 0, w, 0);
        g.addColorStop(0, '#000'); g.addColorStop(1, '#fff');
        cx.fillStyle = g;
      } else cx.fillStyle = '#000';
      cx.fillRect(0, 0, w, h);
      const run = () => {
        const o = fxSketch(c, { amount: 100, cross });
        return o.getContext('2d', { willReadFrequently: true })
                .getImageData(0, 0, w, h).data;
      };
      let d1, d2, err = null;
      try { d1 = run(); d2 = run(); } catch (e) { err = String(e); }
      let bad = 0;
      if (d1) for (let i = 0; i < d1.length; i++) {
        if (!Number.isFinite(d1[i])) bad++;
        if (i % 4 === 3 && d1[i] !== 255) bad++;
      }
      const deterministic = d1 && d2 && d1.every((v, i) => v === d2[i]);
      out.push({ w, h, cross, err, bad, deterministic: !!deterministic });
    }
  }
  return out;
}
"""


def blank(stats):
    return stats["mean"] >= 0.97 and stats["std"] <= 2 / 255


def main() -> int:
    problems = []
    results = []

    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIX))
        page.wait_for_selector(".canvas-area.has-content", timeout=20000)
        page.wait_for_timeout(600)
        page.evaluate("""() => document.querySelectorAll('.panel-section.collapsed').forEach(s => {
          if (getComputedStyle(s).display === 'none') return;
          const t = s.querySelector('.section-title'); if (t) t.click(); })""")
        page.wait_for_timeout(250)

        def effects():
            return page.evaluate(
                "() => state.opts.effects.map(e => ({id: e.id, enabled: e.enabled,"
                " params: {...e.params}}))")

        def hash_of(eff):
            return page.evaluate(STATS_JS, eff)

        def enable(eid):
            item = page.locator(f'.effect-item[data-id="{eid}"]')
            item.scroll_into_view_if_needed()
            item.locator('input[type="checkbox"]').check()
            page.wait_for_timeout(150)
            return item

        def type_value(item, index, text):
            num = card_num(item, index)
            num.click()
            page.keyboard.press("Control+A")
            page.keyboard.type(str(text))
            page.keyboard.press("Tab")
            page.wait_for_timeout(320)

        # --- 1. Amount 0 identity through the UI ---------------------------
        item = enable("sketch")
        type_value(item, 0, 0)
        st = page.evaluate("() => ({...state.opts.effects.find(e => e.id === 'sketch').params})")
        eff = effects()
        with_zero = hash_of(eff)
        without = hash_of([e for e in eff if e["id"] != "sketch"])
        ok = st["amount"] == 0 and with_zero["hash"] == without["hash"]
        results.append(("1a amount=0 identity (UI)", f"amount={st['amount']} "
                        f"hash all={with_zero['hash']} without={without['hash']}", ok))
        if not ok:
            problems.append(f"1a amount=0 is not identity: state={st} {with_zero} {without}")

        enable("posterize")
        page.wait_for_timeout(200)
        eff = effects()
        with_zero = hash_of(eff)
        without = hash_of([e for e in eff if e["id"] != "sketch"])
        ok = with_zero["hash"] == without["hash"] and not blank(with_zero)
        results.append(("1b amount=0 identity in stack", f"stack=posterize+sketch "
                        f"hash all={with_zero['hash']} without={without['hash']}", ok))
        if not ok:
            problems.append(f"1b amount=0 in stack is not identity: {with_zero} {without}")
        page.locator('.effect-item[data-id="posterize"] input[type="checkbox"]').uncheck()
        page.wait_for_timeout(150)

        # --- 2. Hatch extremes on tiny sources ------------------------------
        tiny = page.evaluate(TINY_JS)
        bad = [r for r in tiny if r["err"] or r["bad"] or not r["deterministic"]]
        results.append(("2 hatch extremes 1x1/2x2/17x13", f"{len(tiny)} runs, "
                        f"{len(bad)} bad", not bad))
        if bad:
            problems.append(f"2 tiny-source failures: {bad}")

        # --- 3. Pasted junk into Amount -------------------------------------
        item = page.locator(SKETCH)
        item.scroll_into_view_if_needed()
        num = card_num(item, 0)
        junk = ["", "-", "abc", "1e3", " 50 "]
        for text in junk:
            # start from a known good value each time
            type_value(item, 0, 70)
            page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
            num.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Control+V")
            page.wait_for_timeout(120)
            invalid = page.evaluate(
                "() => document.activeElement && document.activeElement.getAttribute"
                "('aria-invalid')")
            page.keyboard.press("Tab")
            page.wait_for_timeout(360)
            st = page.evaluate("() => ({...state.opts.effects.find(e => e.id === 'sketch').params})")
            stats = hash_of(effects())
            ok = (isinstance(st["amount"], (int, float)) and 0 <= st["amount"] <= 100
                  and stats["nonFinite"] == 0 and not blank(stats))
            results.append((f"3 paste {text!r}", f"amount={st['amount']} "
                            f"invalid_during={invalid!r} mean={stats['mean']} "
                            f"std={stats['std']}", ok))
            if not ok:
                problems.append(f"3 paste {text!r} broke the state/render: {st} {stats}")
        type_value(item, 0, 70)

        # --- 4. Undo / redo around a Crosshatch change ----------------------
        base_state = page.evaluate(
            "() => ({...state.opts.effects.find(e => e.id === 'sketch').params})")
        base_hash = hash_of(effects())["hash"]
        type_value(page.locator(SKETCH), 1, 90)
        page.wait_for_timeout(400)
        changed = page.evaluate(
            "() => ({...state.opts.effects.find(e => e.id === 'sketch').params})")
        changed_hash = hash_of(effects())["hash"]
        page.keyboard.press("Control+z")
        page.wait_for_timeout(500)
        undone = page.evaluate(
            "() => ({...state.opts.effects.find(e => e.id === 'sketch').params})")
        undone_hash = hash_of(effects())["hash"]
        page.keyboard.press("Control+Shift+z")
        page.wait_for_timeout(500)
        redone = page.evaluate(
            "() => ({...state.opts.effects.find(e => e.id === 'sketch').params})")
        redone_hash = hash_of(effects())["hash"]
        ok = (changed["cross"] == 90 and changed_hash != base_hash
              and undone["cross"] == base_state["cross"]
              and redone["cross"] == 90
              and undone_hash == base_hash and redone_hash == changed_hash)
        results.append(("4 undo/redo", f"base={base_state['cross']}/{base_hash} "
                        f"changed={changed['cross']}/{changed_hash} "
                        f"undo={undone['cross']}/{undone_hash} "
                        f"redo={redone['cross']}/{redone_hash}", ok))
        if not ok:
            problems.append("4 undo/redo did not restore value+pixels: "
                            f"{base_state} {changed} {undone} {redone}")

        # --- 5. 4K + six-effect stack ---------------------------------------
        enable("posterize")
        for eid in ["edges", "emboss", "blur", "sharpen"]:
            enable(eid)
        page.wait_for_timeout(200)
        type_value(page.locator(SKETCH), 0, 100)
        type_value(page.locator(SKETCH), 1, 100)
        ids = [e["id"] for e in effects() if e["enabled"]]
        page.set_input_files("#file-input", str(FIX4K))
        page.wait_for_selector(".canvas-area.has-content", timeout=40000)
        page.wait_for_timeout(1200)
        sketch4k = page.evaluate(SKETCH_4K_JS)
        big = page.evaluate(BIG_JS)
        # The UI itself previews at <=1600px (PREVIEW_MAX); this is the
        # full-size export path. The assertion is "completes without hanging",
        # and the sketch cost is reported against the documented 426ms.
        ok = (big["w"] == 4000 and big["h"] == 3000 and big["nonFinite"] == 0
              and big["alphaBad"] == 0 and not blank(big) and big["ms"] < 30000)
        results.append(("5 4K six-effect stack", f"ids={ids} source="
                        f"{big['sourceW']}x{big['sourceH']} stack={big['ms']}ms "
                        f"sketch-alone={sketch4k['ms']}ms mean={big['mean']} "
                        f"std={big['std']} alphaBad={big['alphaBad']}", ok))
        if not ok:
            problems.append(f"5 4K stack failed: {big} sketch={sketch4k}")

        if errors:
            problems.extend(f"PAGE ERROR {e}" for e in errors[:10])
        browser.close()

    httpd.shutdown()
    httpd.server_close()

    for name, detail, ok in results:
        print(f"{name:30} {detail:78} {'PASS' if ok else 'FAIL'}")
    print()
    print(f"{len(results)} checks, {len(problems)} failure(s)")
    for problem in problems:
        print("  FAIL " + problem)
    print("BREAK-IT " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
