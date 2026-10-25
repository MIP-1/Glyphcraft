#!/usr/bin/env python3
"""H1 evidence probe: rapid up-clicks on a numeric control's arrow affordance,
with a complete value-write log (old -> new, state value, app.js call site).

Works on the pre-fix app (native input[type=number] spinner) and on a
replacement control (.step-btn[data-step="up"]).

usage: python h1_probe.py <repo-dir> [clicks] [spacing_ms] [control-id ...]
control-id: depth-num | adj-brightness-num | fx.<effect>.<param>
"""
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve()
BROWSER = __import__("os").environ.get("H1_BROWSER", "chromium")
CLICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 10
SPACING = int(sys.argv[3]) if len(sys.argv) > 3 else 25
CIDS = sys.argv[4:] or ["fx.halftone.size", "depth-num"]
FIXTURE = Path(__import__("os").environ.get("H1_FIXTURE", "/tmp/glyphcraft_gate_fixture.png"))

INPUT_SEL = """
(cid) => {
  if (cid.startsWith('fx.')) {
    const item = document.querySelector('.effect-item[data-id="' + cid.split('.')[1] + '"]');
    return item ? item.querySelector('input[type=number]') : null;
  }
  return document.getElementById(cid);
}
"""

INSTRUMENT = r"""
(cid) => {
  window.__cid = cid;
  window.__log = [];
  const t0 = performance.now();
  const key = cid.startsWith('fx.') ? cid.split('.')[2] : cid.replace(/-num$/, '');
  window.__readState = () => {
    if (cid.startsWith('fx.')) {
      const e = state.opts.effects.find(e => e.id === cid.split('.')[1]);
      return e ? e.params[key] : null;
    }
    return (state.opts.adj && key in state.opts.adj) ? state.opts.adj[key] : state.opts[key];
  };
  const proto = HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, 'value');
  Object.defineProperty(proto, 'value', {
    configurable: true,
    get() { return desc.get.call(this); },
    set(v) {
      if (this.type === 'number' && this === window.__el) {
        const stack = (new Error().stack || '').split('\n')
          .filter(l => l.includes('app.js')).slice(0, 3)
          .map(l => l.trim().replace(/\(?https?:\/\/[^/]+\//, '')).join(' <- ');
        window.__log.push({
          t: +(performance.now() - t0).toFixed(1),
          old: desc.get.call(this), new: String(v),
          state: window.__readState(),
          stack: stack || 'no app frame'
        });
      }
      desc.set.call(this, v);
    }
  });
}
"""

DETECT = r"""
(box) => {
  const el = window.__el;
  const tryPoint = (x, y) => {
    const before = el.value;
    el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, clientX:x, clientY:y}));
    return before;
  };
  return null;
}
"""


def input_value(page, cid):
    return page.evaluate("(cid) => { const e = (" + INPUT_SEL + ")(cid); return e ? e.value : null; }", cid)


def run(page, cid):
    handle = page.evaluate_handle("(cid) => (" + INPUT_SEL + ")(cid)", cid)
    el = handle.as_element()
    if not el:
        print(f"{cid}: CONTROL MISSING")
        return
    el.scroll_into_view_if_needed(timeout=5000)
    page.wait_for_timeout(150)
    page.evaluate(INSTRUMENT, cid)
    page.evaluate("() => { window.__el = (" + INPUT_SEL + ")(window.__cid); }")
    box = el.evaluate("e => { const b = e.getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width,h:b.height}; }")

    kind = page.evaluate("(cid) => document.querySelector('.stepper[data-control=\"' + cid + '\"] .step-btn[data-step=up]') ? 'step-btn' : 'native-spinner'", cid)
    if kind == "step-btn":
        btn = page.evaluate("(cid) => { const b = document.querySelector('.stepper[data-control=\"' + cid + '\"] .step-btn[data-step=up]').getBoundingClientRect(); return {x:b.x+b.width/2, y:b.y+b.height/2}; }", cid)
        up = (btn["x"], btn["y"])
    else:
        # The native spinner sits inside the input's right edge, vertically
        # centred. Find the up zone empirically by value change.
        up = None
        for dy in (14, 17, 12, 20):
            for dx in (-17, -20, -14):
                x, y = box["x"] + box["w"] + dx, box["y"] + dy
                before = input_value(page, cid)
                page.mouse.click(x, y)
                page.wait_for_timeout(90)
                after = input_value(page, cid)
                if before is not None and after is not None and float(after) > float(before):
                    up = (x, y)
                    # restore
                    page.evaluate("(a) => { const e = (" + INPUT_SEL + ")(a.cid); e.value = a.v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }",
                                  {"cid": cid, "v": before})
                    page.wait_for_timeout(300)
                    break
            if up:
                break
        if not up:
            print(f"{cid}: no native up-arrow hit point found in {box}")
            return

    start_input = input_value(page, cid)
    start_state = page.evaluate("() => window.__readState()")
    page.evaluate("() => { window.__log = []; }")
    page.mouse.move(*up)
    for _ in range(CLICKS):
        page.mouse.click(*up)
        if SPACING:
            page.wait_for_timeout(SPACING)
    page.wait_for_timeout(1500)
    end_input = input_value(page, cid)
    end_state = page.evaluate("() => window.__readState()")
    log = page.evaluate("() => window.__log")
    print(f"\n=== {cid}  kind={kind}  clicks={CLICKS} spacing={SPACING}ms  hit={up}")
    print(f"start input={start_input} state={start_state} | end input={end_input} state={end_state} | writes={len(log)}")
    print(" idx      t(ms)   old -> new    state   app.js call site")
    for i, row in enumerate(log):
        print(f"{i:>4} {row['t']:>10} {str(row['old']):>6} -> {str(row['new']):<6} {str(row['state']):<7} {row['stack'][:160]}")
    delta = float(end_input) - float(start_input)
    lo, hi, st = page.evaluate("(cid) => { const e = (" + INPUT_SEL + ")(cid);"
                               " return [e.min, e.max, e.step]; }", cid)
    hi_v = float(hi) if hi not in (None, "") else float("inf")
    lo_v = float(lo) if lo not in (None, "") else -float("inf")
    want = min(hi_v, max(lo_v, float(start_input) + CLICKS * float(st)))
    writes = len(log)
    print(f"VERDICT expected end {want:g} (clamp {lo_v:g}..{hi_v:g}), got {float(end_input):g} "
          f"| value writes={writes} for {CLICKS} clicks")


def main():
    if not FIXTURE.exists():
        sys.path.insert(0, str(ROOT / "tests" / "gate"))
        from run_gate import make_png
        make_png(FIXTURE, width=900, height=600, seed=0)

    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}"

    with sync_playwright() as p:
        browser = getattr(p, BROWSER).launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIXTURE))
        page.wait_for_selector(".canvas-area.has-content", timeout=20000)
        page.wait_for_timeout(700)
        page.evaluate("""() => { document.querySelectorAll('.panel-section.collapsed').forEach(s => {
          if (getComputedStyle(s).display === 'none') return;
          const t = s.querySelector('.section-title'); if (t) t.click(); }); }""")
        page.wait_for_timeout(300)
        page.evaluate("""() => { window.__dbl = 0;
          document.addEventListener('dblclick', e => { window.__dbl++;
            window.__dblAt = e.target.id || e.target.className || e.target.tagName; }, true); }""")
        for cid in CIDS:
            try:
                run(page, cid)
            except Exception as exc:
                print(f"{cid}: PROBE ERROR {exc}")
        print("dblclick events seen:", page.evaluate("() => [window.__dbl, window.__dblAt]"))
        if errors:
            print("PAGE ERRORS:", errors[:8])
        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
