"""Automated WCAG contrast audit for both themes.

Walks every visible text element (and form fields / placeholders / control
borders), composites the effective background through the ancestor chain and
checks the contrast ratio. Saves a screenshot per theme and viewport.

Usage: python tests/test_contrast.py
Exit code 0 = all checks pass. Report written to tests/reports/contrast.json
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = f"file://{ROOT}/index.html"
REPORTS = os.path.join(ROOT, "tests", "reports")
os.makedirs(REPORTS, exist_ok=True)
TEST_IMG = "/tmp/glyphcraft_test.png"

TEXT_MIN = 4.5
LARGE_MIN = 3.0
UI_MIN = 3.0

AUDIT_JS = r"""
() => {
  function parseColor(str) {
    const m = str && str.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    if (p.length < 3 || p.some(isNaN)) return null;
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function blend(fg, bg) {
    const a = fg[3] + bg[3] * (1 - fg[3]);
    if (a === 0) return [0, 0, 0, 0];
    return [
      (fg[0] * fg[3] + bg[0] * bg[3] * (1 - fg[3])) / a,
      (fg[1] * fg[3] + bg[1] * bg[3] * (1 - fg[3])) / a,
      (fg[2] * fg[3] + bg[2] * bg[3] * (1 - fg[3])) / a,
      a
    ];
  }
  function firstColor(str) {
    const m = str && str.match(/rgba?\([^)]+\)/);
    return m ? m[0] : null;
  }
  function effectiveBg(el) {
    const chain = [];
    let node = el;
    while (node) { chain.push(node); node = node.parentElement; }
    chain.reverse();
    let bg = [255, 255, 255, 1];
    for (const item of chain) {
      const cs = getComputedStyle(item);
      const c = parseColor(cs.backgroundColor);
      if (c && c[3] > 0) bg = blend(c, bg);
      const bi = cs.backgroundImage;
      if (bi && bi !== "none" && bi.indexOf("gradient") !== -1) {
        const fc = firstColor(bi);
        const g = fc && parseColor(fc);
        if (g) bg = blend([g[0], g[1], g[2], 1], bg);
      }
    }
    return bg;
  }
  function lum(rgb) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
  }
  function ratio(a, b) {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function label(el) {
    const cls = (el.className && typeof el.className === "string") ? "." + el.className.trim().split(/\s+/).join(".") : "";
    return el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + cls;
  }

  const out = [];
  const seen = new Set();
  document.querySelectorAll("body *").forEach(el => {
    if (seen.has(el)) return;
    seen.add(el);
    const tag = el.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "LINK" || tag === "META" || tag === "CANVAS") return;
    if (el.closest("[hidden]")) return;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) return;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;

    let text = "";
    el.childNodes.forEach(n => { if (n.nodeType === 3) text += n.textContent; });
    text = text.trim();

    const isField = el.matches('input[type="text"], input[type="number"], input[type="search"], select, textarea');
    if (!text && !isField) return;

    let fg = parseColor(cs.color);
    if (!fg) return;
    let kind = "text";
    if (isField) {
      kind = "field";
      if (tag === "INPUT" && !el.value && el.placeholder) {
        const ph = getComputedStyle(el, "::placeholder");
        fg = parseColor(ph.color) || fg;
        text = el.placeholder;
      } else if (tag === "SELECT") {
        text = el.selectedOptions && el.selectedOptions[0] ? el.selectedOptions[0].textContent : "select";
      } else {
        text = el.value || el.placeholder || "field";
      }
    }
    if (!text) return;

    const size = parseFloat(cs.fontSize) || 14;
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const bg = effectiveBg(el);
    const cr = ratio(fg, bg);
    const min = large ? 3.0 : 4.5;
    out.push({ selector: label(el), text: text.slice(0, 60), kind, size, weight, ratio: +cr.toFixed(2), min, fg: fg.slice(0, 3), bg: bg.slice(0, 3) });

    if (kind === "field" && parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== "none") {
      const bc = parseColor(cs.borderTopColor);
      if (bc && bc[3] > 0) {
        const borderBg = effectiveBg(el);
        const br = ratio([bc[0], bc[1], bc[2]], borderBg);
        out.push({ selector: label(el) + " [border]", text: "control border", kind: "border", ratio: +br.toFixed(2), min: 3.0 });
      }
    }
  });
  return out;
}
"""


def audit(page):
    return page.evaluate(AUDIT_JS)


def run_theme(browser, theme, width, height):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=theme,
        locale="en-US",
        reduced_motion="reduce",
    )
    ctx.add_init_script(
        "try{localStorage.setItem('glyphcraft-theme','%s')}catch(e){}" % theme
    )
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_timeout(500)
    page.set_input_files("#file-input", TEST_IMG)
    page.wait_for_selector(".canvas-area.has-content", timeout=15000)
    page.wait_for_timeout(700)

    results = audit(page)

    # Menus (closed by default, so audit them while open).
    page.click("#menu-file")
    page.wait_for_timeout(250)
    results += audit(page)
    page.keyboard.press("Escape")
    page.click("#menu-view")
    page.wait_for_timeout(250)
    results += audit(page)
    page.keyboard.press("Escape")
    page.click("#zoom-level")
    page.wait_for_timeout(250)
    results += audit(page)
    page.keyboard.press("Escape")

    # Error state on the home screen.
    page.evaluate("""() => {
      document.getElementById('canvas-area').classList.remove('has-content');
      const dz = document.getElementById('drop-zone');
      dz.dataset.state = 'error';
      dz.querySelector('.drop-error').textContent = 'This file is too large (64.0 MB). Try a smaller file (under 40 MB).';
    }""")
    page.wait_for_timeout(200)
    results += audit(page)
    page.reload(wait_until="load")
    page.wait_for_timeout(400)
    page.evaluate("""() => {
      const dz = document.getElementById('drop-zone');
      dz.dataset.state = 'idle';
    }""")

    shot = os.path.join(REPORTS, f"contrast-{theme}-{width}.png")
    page.screenshot(path=shot)
    ctx.close()

    violations = []
    for row in results:
        if row["ratio"] < row["min"] - 0.01:
            violations.append(row)
    return {"theme": theme, "width": width, "checked": len(results), "violations": violations,
            "errors": errors, "screenshot": shot}


def main():
    if not os.path.exists(TEST_IMG):
        sys.exit("Missing test image: " + TEST_IMG)

    all_runs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for theme in ("dark", "light"):
            for width, height in ((1280, 900), (360, 740)):
                all_runs.append(run_theme(browser, theme, width, height))
        browser.close()

    total_violations = sum(len(r["violations"]) for r in all_runs)
    payload = {
        "runs": all_runs,
        "total_checked": sum(r["checked"] for r in all_runs),
        "total_violations": total_violations,
    }
    with open(os.path.join(REPORTS, "contrast.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    for run in all_runs:
        print(f"{run['theme']:5} {run['width']:4}px  checked {run['checked']:3}  "
              f"violations {len(run['violations'])}  errors {len(run['errors'])}")
        for v in run["violations"][:12]:
            print(f"   FAIL {v['ratio']:.2f} < {v['min']:.1f}  {v['selector']}  {v['text']!r}  "
                  f"fg={v.get('fg')} bg={v.get('bg')}")

    print(f"CONTRAST TOTAL: {payload['total_checked']} pairs checked, {total_violations} violations")
    return 1 if total_violations or any(r["errors"] for r in all_runs) else 0


if __name__ == "__main__":
    sys.exit(main())
