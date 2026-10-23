# Glyphcraft Gate

## P1-0 — Build the gate — STATUS: BLOCKED

**Blocker:** The repository at `HEAD 7f17aff` is **not** the broken light-theme build described in the task file. G2 is GREEN on the unmodified app. The reference images in `docs/ref/` show the old failure, but the app no longer reproduces it: `.effect-item` and `.preset-btn` compute to light surfaces with dark text in light theme at both widths. The gate is not broken; a live negative control proves it catches the exact screenshot failure when it exists.

### Root cause of the blocker

- `style.css:105-152` defines a complete `:root[data-theme="light"]` token block; the light values are already used by the effect cards, preset chips, and effect-name text (`--surface`, `--surface-panel`, `--text-primary`).
- `git log` shows the light-theme repair in earlier committed work (`b89b5e2 Round 2 — light theme...`, `a6936d0 Round 1 fixes: theme tokens...`). The `docs/ref/` screenshots predate that repair.
- This means P1-0's required RED condition (`G2 MUST fail` with dark light-theme cards/chips/invisible names) cannot be produced honestly on this tree.

### RED output (before) — required check status

The full run on `HEAD 7f17aff`, with `tests/gate/run_gate.py` and `tests/gate/allowlist.json`, produced:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 38372 element/state checks, 4 cells, 64 scans
G3 PASS screenshots: 48 captured in docs/evidence/p1-0/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=16.799999999999272ms frames=71, dark 360: median=16.69999999999891ms p95=16.799999999999272ms frames=71, light 1280: median=16.69999999999891ms p95=16.799999999999272ms frames=74, light 360: median=16.700000000000728ms p95=16.80000000000109ms frames=83
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (198.8s)
G6 FAIL no Arabic: 15 violation(s)
G7 FAIL no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)

GATE FAIL G6, G7, G8
```

Required G6 RED, as expected (abridged; full list is printed by `npm run gate`):

```text
app.js:257: idle: "أفلت صورة أو فيديو هنا، أو الصقه (Ctrl+V)، أو افتح ملفًا.",
app.js:258: hover: "أفلت الملف لتحميله.",
app.js:259: loading: "جارٍ تحميل {name}…",
app.js:260: open: "فتح ملف",
app.js:261: noImage: "لم يتم تحميل صورة",
app.js:262: errType: "نوع الملف غير مدعوم. جرّب صورة PNG أو JPG أو WebP، أو فيديو WebM أو MP4.",
app.js:263: errSize: "الملف كبير جدًا ({size}). جرّب ملفًا أصغر (أقل من {max}).",
app.js:264: errDecode: "تعذّر فك ترميز هذا الملف. جرّب حفظه بصيغة PNG أو MP4 ثم افتحه مجددًا.",
app.js:265: errVideo: "تعذّر تشغيل هذا الفيديو. جرّب MP4 (H.264) أو WebM (VP9).",
app.js:266: resetConfirm: "اضغط على «إعادة تعيين الكل» مرة أخرى للتأكيد",
app.js:267: resetDone: "تمت إعادة تعيين كل الإعدادات"
tests/test_suite.py:1035: arabic_ok["dir"] == "rtl" and "أفلت" in arabic_ok["hint"] and arabic_ok["open"] == "فتح ملف",
tests/test_suite.py:1037: record("Arabic honest error message", "كبير" in arabic_err and "40 MB" in arabic_err, arabic_err)
tests/reports/TEST_REPORT.md:174: | Arabic home screen | PASS | {"dir": "rtl", "hint": "أفلت صورة أو فيديو هنا، أو الصقه (Ctrl+V)، أو افتح ملفًا.", "op...
tests/reports/TEST_REPORT.md:175: | Arabic honest error message | PASS | الملف كبير جدًا (⁦50 MB⁩). جرّب ملفًا أصغر (أقل من ⁦40 MB⁩). |
```

Required G7 RED:

```text
[dark 1280]  [{"action": "theme", "text": "ThemeT"}]
[dark 360]   [{"action": "theme", "text": "ThemeT"}]
[light 1280] [{"action": "theme", "text": "ThemeT"}]
[light 360]  [{"action": "theme", "text": "ThemeT"}]
```

Required G8 RED (16 violations; abridged):

```text
[dark 1280] icon-center: panel-toggle-btn icon center (1241.0,11.0) vs item center (1246.0,24.0)
[dark 1280] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
[dark 1280] top: tops status-bar=15.8, zoom-controls=0.0, theme-toggle=2.0, panel-toggle-btn=2.0
[dark 1280] radius: zoom-controls=6.0, theme-toggle=4.0
...
[light 360] icon-center: panel-toggle-btn icon center (325.0,55.0) vs item center (330.0,68.0)
[light 360] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
[light 360] top: tops status-bar=96.0, zoom-controls=44.0, theme-toggle=46.0, panel-toggle-btn=46.0
[light 360] radius: zoom-controls=6.0, theme-toggle=4.0
```

### Gate negative control (proves G2 is not broken)

The failing state from the screenshots was injected into the live light-theme page only, without changing any repository file:

```css
.effect-item { background:#000000 !important; border-color:#1a1a1a !important }
.effect-name { color:#141414 !important }
.preset-btn { background:#000000 !important; color:#141414 !important; border-color:#1a1a1a !important }
.drag-handle { color:#222222 !important }
```

G2 result: **before 0 violations; after 40 violations.** The exact requested failures were reported:

```text
[light 1280 after-negative-control] button.preset-btn:nth-of-type(1) kind=text bg=rgb(0, 0, 0) fg=rgb(20, 20, 20) ratio=1.14 min=4.5 "Terminal Green"
[light 1280 after-negative-control] span.effect-name kind=text bg=rgb(0, 0, 0) fg=rgb(20, 20, 20) ratio=1.14 min=4.5 "Halftone"
[light 1280 after-negative-control] button.drag-handle kind=icon bg=rgb(0, 0, 0) fg=rgb(34, 34, 34) ratio=1.32 min=3 "handle dots"
[light 1280 after-negative-control] div.effect-item[data-id="halftone"] kind=luminance bg=rgb(0, 0, 0) detail="light theme surface luminance 0.000 < 0.35"
```

This confirms the light-theme failure would be caught in a real browser. It is absent from HEAD.

### GREEN output (after)

Not applicable while BLOCKED. G1-G5 are already green; G6/G7/G8 are deliberately red and are the P1-1/P1-3 targets.

### Gate runs (3x)

Not run as a PASS sequence because P1-0 is BLOCKED. The full gate was run twice after scanner fixes; the final run is pasted above. Repeating it would not turn G2 red on this tree.

### Screenshots (path — what I see)

All 48 are in `docs/evidence/p1-0/`. I opened the fullest and menu/picker states:

- `docs/evidence/p1-0/dark-1280-fullest-top.png` — dark page; status text at right; zoom group taller than theme/panel buttons; panel icon sits high inside its 44px box; red Export button.
- `docs/evidence/p1-0/light-1280-fullest-top.png` — light page; all top-bar text readable; same geometry issue; no dark surfaces.
- `docs/evidence/p1-0/dark-1280-fullest-effects.png` — dark effect cards, light preset chips and readable names; red checkboxes; no clipped controls.
- `docs/evidence/p1-0/light-1280-fullest-effects.png` — **light effect cards, dark readable names, cream preset chips, red checkboxes**; the screenshot bug is not present.
- `docs/evidence/p1-0/dark-360-fullest-effects.png` — panel open at 360; chips wrap; cards are dark with readable names; panel icon high.
- `docs/evidence/p1-0/light-360-fullest-effects.png` — panel open at 360; chips and cards are light/cream; names readable; panel icon high.
- `docs/evidence/p1-0/dark-1280-file-menu.png` / `light-1280-file-menu.png` — inverse menus: light menu on dark page, dark menu on light page; text readable; no clipping.
- `docs/evidence/p1-0/dark-1280-view-menu.png` / `light-1280-view-menu.png` — readable inverse menu; **Theme item visible**, confirming G7 red.
- `docs/evidence/p1-0/dark-1280-zoom-menu.png` / `light-1280-zoom-menu.png` — inverse zoom menu; readable; current zoom row highlighted.
- `docs/evidence/p1-0/dark-1280-size-picker.png` / `light-1280-size-picker.png` — inverse picker; searchable list; readable labels/swatches; no overflow at 1280.

The remaining 36 state images are in the same directory; the G2 scanner audited them in 64 real-browser scans.

### Break-it list (5) and results

1. **Inject dark cards/chips/names in light theme** — G2 RED with 40 exact violations (negative control above). PASS for gate sensitivity.
2. **Arabic text present in app and tests** — G6 RED with 15 file:line locations. PASS for gate sensitivity.
3. **Theme item present in View** — G7 RED in all four cells. PASS for gate sensitivity.
4. **Top-bar icon not vertically centered** — G8 RED: panel-toggle icon center y=11 vs item center y=24 at 1280. PASS for gate sensitivity.
5. **Theme toggle stress** — five real toggles per cell, full DOM scan after each; 64 scans total, no leaked inline styles reported by G2. PASS for no-flake sensitivity.

### Files changed (`git diff --stat`) and why

- `package.json` — adds `npm run gate` with no new dependencies.
- `tests/gate/run_gate.py` — G1-G8 implementation; real Chromium for G2/G3/G4/G7/G8, static lint for G1/G6, existing suite for G5.
- `tests/gate/allowlist.json` — explicit G2 luminance allowlist: preview canvas, inverse menus/pickers, primary red buttons, toast; contrast exceptions only for primary red hairlines.
- `docs/GATE.md` — this evidence record.
- `docs/evidence/p1-0/` — 48 screenshots (dark/light × 360/1280 × 12 states).
- No app files and no existing test files were edited by this task.

### Commit / tag

Not tagged. A BLOCKED task must not be tagged `P1-0-pass`.

### Remaining flaws

- **G2 is green, contrary to P1-0.** The current tree already has the light-theme repair; the reference images are stale.
- **P1-1 has a second conflict:** `tests/test_suite.py:717-729` asserts that `View → Theme` exists, while P1-1 requires it removed and G7 green. P1-1 says only Arabic tests may be edited, so the 169-test green requirement cannot be met without also changing that test (or replacing it with a no-Theme assertion).
- Native `<select>` popup and native title tooltips cannot be captured by headless Chromium; their focus/hover states are captured, the OS-rendered popup/tooltip itself is a HUMAN-CHECK.
- Custom checkbox artwork and pseudo-element backgrounds are screenshot-covered; the DOM scanner checks reachable pseudo colors but cannot sample data-URI checkbox pixels.
