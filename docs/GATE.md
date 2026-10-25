# Glyphcraft Gate

## P1-0 — Build the gate — STATUS: PASS

The gate now runs the real user flow in a real browser, with an optional host
`userContent.css` fixture that reproduces the user’s Zen/Noctalia environment.
On the pre-fix archive G2 failed with **98 violations**, including dark effect
cards, black preset chips, and invisible effect names in light theme. After the
fix G2 is **green with the host fixture still applied**. G6/G7/G8 remain
deliberately RED for P1-1/P1-3.

### Root cause (not a stale screenshot)

The user’s Zen profile loads a global Noctalia `userContent.css`
(`~/.cache/noctalia/zen-browser/zen-userContent.css`) that declares generic
custom properties on **every element**:

```css
@media (prefers-color-scheme: dark) {
  * {
    --surface: #1f1a1f;
    --text:    #eae0e7;
    --muted:   #988e97;
    /* ... --base, --overlay, --primary, ... */
  }
}
```

The app defined its own `--surface`, `--text`, and `--muted` on `:root` and
inherited them. A direct declaration on a descendant (`*`) beats an inherited
value, regardless of selector specificity. With the app in light theme and the
OS in dark mode, the host’s dark `--surface` replaced the app’s light
`--surface` on every element, while `--surface-panel` (not defined by the host)
stayed light. That is exactly the screenshot pattern: light top bar and panel,
dark canvas, dark effect cards, black preset chips, and dark names on dark
cards. It did not reproduce in a clean browser profile, which is why the
original gate was green.

The fix is to stop using host-generic names for app tokens:

- `--surface` → `--gc-surface`;
- removed the unused generic `--text` and `--muted` aliases;
- the inline empty-state colour now uses `--text-muted`;
- two real-flow contrast issues exposed by the new checks were also fixed:
  active preset border (`--border-focus`) and disabled zoom border
  (`--text-muted`).

`tests/gate/host_usercontent.css` is a permanent regression fixture containing
the host token block. It is injected in G2 for the real-flow cell, so this
collision cannot silently return.

### RED output (before) — real gate run

Command: `npm run gate` in a `git archive HEAD` copy of the pre-fix tree
(`b5c02bd`) with the current `tests/gate/run_gate.py` and host fixture copied
in. This is a genuine full gate run, not a hand-built screenshot assertion.

```text
G1 FAIL token lint: 11 violation(s)
G2 FAIL theme parity: 98 violation(s), 51796 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-0/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=16.700000000000728ms frames=73, dark 360: median=16.69999999999891ms p95=16.700000000000728ms frames=80, light 1280: median=16.69999999999891ms p95=16.799999999999272ms frames=74, light 360: median=16.69999999999891ms p95=16.80000000000109ms frames=84
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (200.3s)
G6 FAIL no Arabic: 28 violation(s)
G7 FAIL no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)

GATE FAIL G1, G2, G6, G7, G8
```

G6 counted 28 in the archived copy because its old `docs/GATE.md` still quoted
the same app strings; the current tree itself has 15 app/test/report hits. G6 is
still RED as required.

G2 red proof — the real host path, at both widths:

```text
[light 1280 host-dark-icon] button.preset-btn:nth-of-type(1) kind=text bg=rgb(31, 26, 31) fg=rgb(33, 27, 20) ratio=1 min=4.5 Terminal Green
[light 1280 host-dark-icon] span.effect-name kind=text bg=rgb(31, 26, 31) fg=rgb(33, 27, 20) ratio=1 min=4.5 Halftone
[light 1280 host-dark-icon] div.effect-item:nth-of-type(1)[data-id="halftone"] kind=luminance bg=rgb(31, 26, 31) ratio=1 min=2 light theme surface luminance 0.011 < 0.35
[light 1280 host-dark-icon] button.drag-handle kind=icon bg=rgb(31, 26, 31) fg=rgb(87, 80, 63) ratio=2.14 min=3 handle dots
[light 1280 host-dark-icon] button.preset-btn:nth-of-type(1) kind=luminance bg=rgb(31, 26, 31) ratio=1 min=2 light theme surface luminance 0.011 < 0.35
[light 360 host-dark-icon] button.preset-btn:nth-of-type(1) kind=text bg=rgb(31, 26, 31) fg=rgb(33, 27, 20) ratio=1 min=4.5 Terminal Green
[light 360 host-dark-icon] span.effect-name kind=text bg=rgb(31, 26, 31) fg=rgb(33, 27, 20) ratio=1 min=4.5 Halftone
[light 360 host-dark-icon] div.effect-item:nth-of-type(1)[data-id="halftone"] kind=luminance bg=rgb(31, 26, 31) ratio=1 min=2 light theme surface luminance 0.011 < 0.35
```

The same run also caught two independent real-flow contrast failures that the
old static/fullest-state checks never reached:

```text
[dark 1280 real-clean-initial] button.preset-btn.active:nth-of-type(6) kind=ui bg=rgb(21, 20, 22) fg=rgb(142, 43, 43) ratio=2.21 min=3 top border
[light 1280 real-clean-reload-light] #zoom-level kind=ui bg=rgb(242, 236, 225) fg=rgb(216, 205, 185) ratio=1.34 min=3 top border
```

G1 red proof (the same collision, caught as a static guard):

```text
style.css:18: host-generic token '--surface' used; namespace the app token
style.css:93: host-generic token '--surface' used; namespace the app token
style.css:109: host-generic token '--surface' used; namespace the app token
style.css:97: host-generic token '--text' used; namespace the app token
style.css:98: host-generic token '--muted' used; namespace the app token
app.js:1188: host-generic token '--muted' used; namespace the app token
```

### Required G6 / G7 / G8 RED (current tree)

G6 is red on the remaining localisation strings. The Arabic payload is omitted
from this record so the record itself does not add more G6 hits; the full lines
are printed by `npm run gate`.

```text
G6 FAIL no Arabic: 15 violation(s)
  app.js:257 [localised home hint]
  app.js:258 [localised hover hint]
  app.js:259 [localised loading hint]
  app.js:260 [localised open-file label]
  app.js:261 [localised no-image status]
  app.js:262 [localised type error]
  app.js:263 [localised size error]
  app.js:264 [localised decode error]
  app.js:265 [localised video error]
  app.js:266 [localised reset confirmation]
  app.js:267 [localised reset completion]
  tests/test_suite.py:1035 [Arabic home assertion]
  tests/test_suite.py:1037 [Arabic error assertion]
  tests/reports/TEST_REPORT.md:174 [generated Arabic report row]
  tests/reports/TEST_REPORT.md:175 [generated Arabic report row]
```

G7 is red in all four cells:

```text
G7 FAIL no Theme item in View menu
  [dark 1280] [{"action": "theme", "text": "ThemeT"}]
  [dark 360] [{"action": "theme", "text": "ThemeT"}]
  [light 1280] [{"action": "theme", "text": "ThemeT"}]
  [light 360] [{"action": "theme", "text": "ThemeT"}]
```

G8 is red on 16 geometry checks. Abridged:

```text
G8 FAIL top-bar geometry: 16 violation(s)
  [dark 1280] icon-center: panel-toggle-btn icon center (1241.0,11.0) vs item center (1246.0,24.0)
  [dark 1280] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
  [dark 1280] top: tops status-bar=15.8, zoom-controls=0.0, theme-toggle=2.0, panel-toggle-btn=2.0
  [dark 1280] radius: zoom-controls=6.0, theme-toggle=4.0
  [dark 360] icon-center: panel-toggle-btn icon center (325.0,55.0) vs item center (330.0,68.0)
  [dark 360] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
  [dark 360] top: tops status-bar=96.0, zoom-controls=44.0, theme-toggle=46.0, panel-toggle-btn=46.0
  [dark 360] radius: zoom-controls=6.0, theme-toggle=4.0
  [light 1280] icon-center: panel-toggle-btn icon center (1241.0,11.0) vs item center (1246.0,24.0)
  [light 1280] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
  [light 1280] top: tops status-bar=15.8, zoom-controls=0.0, theme-toggle=2.0, panel-toggle-btn=2.0
  [light 1280] radius: zoom-controls=6.0, theme-toggle=4.0
  [light 360] icon-center: panel-toggle-btn icon center (325.0,55.0) vs item center (330.0,68.0)
  [light 360] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
  [light 360] top: tops status-bar=96.0, zoom-controls=44.0, theme-toggle=46.0, panel-toggle-btn=46.0
  [light 360] radius: zoom-controls=6.0, theme-toggle=4.0
```

### GREEN output (after)

Focused post-fix browser run (same gate scanner):

```text
g2 pass True violations 0 states 88 cells 10 checked 51796
g3 62
g4 {'pass': True, 'runs': [{'frames': 74, 'median': 16.69999999999891, 'p95': 16.700000000000728, 'theme': 'dark', 'width': 1280}, {'frames': 94, 'median': 16.69999999999891, 'p95': 16.80000000000109, 'theme': 'dark', 'width': 360}, {'frames': 78, 'median': 16.69999999999891, 'p95': 16.799999999999272, 'theme': 'light', 'width': 1280}, {'frames': 92, 'median': 16.69999999999891, 'p95': 16.799999999999272, 'theme': 'light', 'width': 360}]}
g7 pass False
g8 16
errors []
```

With the host fixture still applied, the light card is now
`rgb(250, 247, 241)`, the name is `rgb(33, 27, 20)`, and the chip is
`rgb(250, 247, 241)` on cream `rgb(242, 236, 225)`.

### Firefox (real second browser)

Playwright Firefox 157.0 was installed and used against the pre-fix archive and
the fixed tree, with the host fixture applied to both:

```text
firefox 157.0
prefix-dark        card rgb(31, 26, 31)  name rgb(233, 223, 200)  chip rgb(31, 26, 31)  panel rgb(21, 20, 22)
prefix-light-icon  card rgb(31, 26, 31)  name rgb(33, 27, 20)    chip rgb(31, 26, 31)  panel rgb(242, 236, 225)
prefix-light-T     card rgb(31, 26, 31)  name rgb(33, 27, 20)    chip rgb(31, 26, 31)  panel rgb(242, 236, 225)
prefix-light-reload card rgb(31, 26, 31) name rgb(33, 27, 20)    chip rgb(31, 26, 31)  panel rgb(242, 236, 225)
current-dark       card rgb(11, 11, 12)  name rgb(233, 223, 200)  chip rgb(11, 11, 12)  panel rgb(21, 20, 22)
current-light-icon card rgb(250, 247, 241) name rgb(33, 27, 20)   chip rgb(250, 247, 241) panel rgb(242, 236, 225)
current-light-T    card rgb(250, 247, 241) name rgb(33, 27, 20)   chip rgb(250, 247, 241) panel rgb(242, 236, 225)
current-light-reload card rgb(250, 247, 241) name rgb(33, 27, 20) chip rgb(250, 247, 241) panel rgb(242, 236, 225)
```

Persisted evidence:
`docs/evidence/p1-0/firefox-prefix-light-icon.png` and
`docs/evidence/p1-0/firefox-current-light-icon.png`.

### Full gate runs (3× consecutive, after fix)

Run 1:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51796 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-0/
G4 PASS frame timings: dark 1280: median=16.700000000000728ms p95=16.80000000000291ms frames=90, dark 360: median=16.69999999999891ms p95=16.700000000000728ms frames=71, light 1280: median=16.69999999999891ms p95=16.80000000000109ms frames=79, light 360: median=16.700000000000728ms p95=1116.5999999999985ms frames=94
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (199.0s)
G6 FAIL no Arabic: 15 violation(s)
G7 FAIL no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G6, G7, G8
```

Run 2:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51796 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-0/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=16.799999999999272ms frames=71, dark 360: median=16.69999999999891ms p95=16.799999999999272ms frames=77, light 1280: median=16.700000000000728ms p95=1083.2999999999993ms frames=97, light 360: median=16.69999999999891ms p95=16.700000000000728ms frames=71
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (196.4s)
G6 FAIL no Arabic: 15 violation(s)
G7 FAIL no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G6, G7, G8
```

Run 3:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51796 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-0/
G4 PASS frame timings: dark 1280: median=16.700000000000728ms p95=1083.2999999999993ms frames=89, dark 360: median=16.69999999999709ms p95=16.799999999999272ms frames=76, light 1280: median=16.69999999999709ms p95=16.799999999999272ms frames=96, light 360: median=16.69999999999891ms p95=16.700000000000728ms frames=73
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (200.7s)
G6 FAIL no Arabic: 15 violation(s)
G7 FAIL no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G6, G7, G8
```

Gate runs (3x): **G1-G5 green / green / green**. Each run has `G2 PASS` with
the host fixture active. G6/G7/G8 are the expected P1-1/P1-3 RED outputs.

### Screenshots (path — what I see)

All 62 Chromium shots plus the two Firefox shots are in
`docs/evidence/p1-0/`. I opened the key new states:

- `docs/evidence/p1-0/light-1280-host-dark-icon.png` — real flow, host fixture
  active, light theme: cream panel/top bar, **light effect cards and preset
  chips**, dark readable names, red checkboxes.
- `docs/evidence/p1-0/light-360-host-dark-icon.png` — same at 360 with the panel
  open; cards/chips wrap and stay light; names readable.
- `docs/evidence/p1-0/light-1280-host-dark-reload-light.png` — reload while
  light with the host fixture re-applied; drop zone, top bar and panel are
  light; the (below-fold) effect-card scan is still green.
- `docs/evidence/p1-0/light-360-host-dark-reload-light.png` — same at 360 with
  the panel open; visible cards/chips are light and names readable.
- `docs/evidence/p1-0/light-1280-host-os-light-os-light.png` — first visit with
  OS light and no saved theme; light surfaces, readable text.
- `docs/evidence/p1-0/light-1280-real-clean-icon.png` — clean-browser real flow
  after the icon toggle; light cards/chips, readable names.
- `docs/evidence/p1-0/light-360-real-clean-icon.png` — same at 360.
- `docs/evidence/p1-0/light-1280-real-clean-reload-light.png` — clean reload
  while light; no dark surfaces; disabled zoom border now visible.
- `docs/evidence/p1-0/firefox-prefix-light-icon.png` — Firefox pre-fix: cream
  panel, **dark cards/chips**, invisible names.
- `docs/evidence/p1-0/firefox-current-light-icon.png` — Firefox post-fix: light
  cards/chips, readable names.

The remaining screenshots are the existing dark/light × 360/1280 menu, picker,
focus, hover, and fullest-effect states; G2 audited all 88 scan states in 10
cells (51,796 element/state checks).

### Break-it list (5) and results

1. **Host `userContent.css` defines generic tokens on `*`** — real flow with
   the fixture: pre-fix G2 98 violations, post-fix 0. PASS.
2. **Icon, `T`, and reload while light** — real clicks/keys, no pre-seeded
   localStorage: every post-fix state green at 1280 and 360. PASS.
3. **Active preset border** — pre-fix `ratio=2.21 < 3`; changed to
   `--border-focus`, post-fix green. PASS.
4. **Disabled zoom border after reload** — pre-fix `ratio=1.34 < 3`; changed to
   `--text-muted`, post-fix green. PASS.
5. **Generic host token names in app source** — new G1 guard: 11 pre-fix
   violations, 0 post-fix. PASS.

### Files changed and why

- `style.css` — namespaced `--surface` to `--gc-surface`; removed generic
  `--text`/`--muted` aliases; active preset border uses `--border-focus`;
  disabled zoom border uses `--text-muted`.
- `app.js` — empty-state colour uses `--text-muted` instead of host-generic
  `--muted`.
- `tests/gate/run_gate.py` — adds the host-userContent injection and real-flow
  scenarios (clean dark, host dark, host OS-light), plus the G1 generic-token
  guard. The scanner is stricter, not weaker.
- `tests/gate/host_usercontent.css` — new regression fixture containing the
  Noctalia/Zen generic token block.
- `docs/evidence/p1-0/` — 62 Chromium screenshots and 2 Firefox comparison
  screenshots.
- `docs/GATE.md` — this evidence record.
- **No existing tests were edited in P1-0.** The authorized
  `tests/test_suite.py:717-729` Theme assertion edit is reserved for P1-1 and
  was not applied.

### Commit / tag

Commit: `P1-0: gate and host-token light-theme fix`

Tag: `P1-0-pass`

### Remaining RED (deliberate, next parts)

- **G6** — Arabic/localised strings still present in `app.js`, the existing
  Arabic tests, and the generated report. P1-1.
- **G7** — `View → Theme` item still present in all four cells. P1-1.
- **G8** — top-bar geometry: status/zoom/theme/panel icon alignment and radii
  still differ at 1280/360. P1-3.
- Native `<select>` popups and native tooltips remain a HUMAN-CHECK; headless
  Chromium cannot screenshot OS-rendered widgets. Custom checkbox artwork and
  pseudo-element colours are screenshot-covered but not pixel-sampled.

## P1-1 — Remove localisation and RTL — STATUS: PASS

The app is English-only now. The runtime dictionary, `navigator.language` read,
`documentElement.dir` assignment, RTL stylesheet rules, duplicate View → Theme
row, and the generated-report rows that still held the old language are gone.
G6 and G7 are green, and the existing suite is still exactly **169 checks, 0
failures**.

### Root cause

The home screen was localised at runtime:

- `app.js` held a two-language `STRINGS` map, selected with
  `navigator.language.startsWith("ar")`, and `applyLanguage()` wrote both
  `documentElement.lang` and `documentElement.dir`;
- `t()` substituted strings, including bidi-isolating filename/size values;
- `style.css` carried two `[dir="rtl"]` overrides for selects and the panel;
- `index.html` carried `dir="ltr"` and a duplicate View → Theme row;
- the generated test report still contained the old locale rows.

The product decision is English-only, so this was not a translation-quality
fix: the whole locale seam and the RTL branch were removed. The top-bar theme
button and `T` remain the only theme toggles.

### RED before P1-1 (P1-0 final tree)

P1-0’s three final runs are the starting evidence; they were taken before these
edits and are recorded above.

```text
G6 FAIL no Arabic: 15 violation(s)
  app.js:257-267 [11 localised home strings]
  tests/test_suite.py:1035,1037 [2 locale assertions]
  tests/reports/TEST_REPORT.md:174-175 [2 generated report rows]
G7 FAIL no Theme item in View menu
  [dark 1280] [{"action": "theme", "text": "ThemeT"}]
  [dark 360] [{"action": "theme", "text": "ThemeT"}]
  [light 1280] [{"action": "theme", "text": "ThemeT"}]
  [light 360] [{"action": "theme", "text": "ThemeT"}]
G8 FAIL top-bar geometry: 16 violation(s)
```

G1-G5 were already green in those runs. G8 remains deliberately RED for P1-3.

### Fix

- `app.js` — removed `STRINGS`, `LANG`, `t()`, `applyLanguage()` and its init
  call; home/status/error strings are plain English literals; `showDropError()`
  now takes the final message instead of a dictionary key; removed the dead
  `theme` menu-action branch. `T` and `#theme-toggle` still call `toggleTheme()`.
- `index.html` — removed `dir="ltr"` and the View → Theme menu item.
- `style.css` — removed both `[dir="rtl"]` overrides; the normal panel rule
  remains.
- `README.md` / `docs/PROGRESS.md` — removed the locale/RTL claims and recorded
  the interface as English-only.
- No Arabic font file existed; the Latin Google Fonts and Goodmountain assets
  are unchanged.
- The gate, selectors, thresholds, allowlists and scanner logic were not
  weakened. G2 checks 51,784 element/state values after the menu row removal.

### Authorized Theme test edit (`tests/test_suite.py:717-729`)

Reason: the old test asserted the View → Theme row existed and clicked it. That
is now the opposite of the requirement. The replacement asserts **absence** and
then proves the two supported toggles still work in order: `T` dark→light, `T`
light→dark, then the top-bar icon dark→light.

```diff
-    # Round 2 Phase 4: View > Theme is present and switches the theme.
+    # P1-1: View has no Theme item; T and the top-bar icon own the toggle.
     page.keyboard.press("Escape")
     set_theme(True)
     open_menu("view")
     theme_item = page.locator('#dropdown-view [data-action="theme"]')
-    theme_before = page.evaluate("() => document.documentElement.dataset.theme")
-    theme_label = theme_item.inner_text() if theme_item.count() else ""
-    theme_item.click()
+    theme_count = theme_item.count()
+    page.keyboard.press("Escape")
+    page.wait_for_timeout(150)
+    page.locator("#canvas-area").click(position={"x": 200, "y": 150})
+    page.keyboard.press("t")
+    page.wait_for_timeout(300)
+    after_t = page.evaluate("() => document.documentElement.dataset.theme")
+    page.keyboard.press("t")
+    page.wait_for_timeout(300)
+    after_t2 = page.evaluate("() => document.documentElement.dataset.theme")
+    page.click("#theme-toggle")
     page.wait_for_timeout(300)
-    theme_after = page.evaluate("() => document.documentElement.dataset.theme")
-    record("theme item present in View menu",
-           theme_item.count() == 1 and "Theme" in theme_label and theme_before == "dark" and theme_after == "light",
-           f"count={theme_item.count()}, label={theme_label!r}, {theme_before} -> {theme_after}")
+    after_icon = page.evaluate("() => document.documentElement.dataset.theme")
+    record("no theme item; T and top-bar icon toggle theme",
+           theme_count == 0 and after_t == "light" and after_t2 == "dark" and after_icon == "light",
+           f"count={theme_count}, T={after_t}, T2={after_t2}, icon={after_icon}")
     set_theme(True)
```

The old two locale records in the fresh-context block were also repurposed as
English-only assertions. They now check no `dir` attribute, computed `ltr`,
English hint/open/status copy, and the English size error. **Two records were
replaced, not deleted**, so the total stays 169:

```text
PASS English home screen {"dir": "", "direction": "ltr", "hint": "Drop an image or video here, paste it (Ctrl+V), or open a file.", "open": "Open file", "status": "No image loaded"}
PASS English honest error message This file is too large (50 MB). Try a smaller file (under 40 MB).
REPORT WRITTEN 169 checks, 0 failures
```

A separate `ar-SA` browser check (not added to the suite) proves the interface
does not react to browser locale: `navigatorLanguage="ar-SA"`, `lang="en"`,
no `dir` attribute, computed `direction="ltr"`, English hint/open/status, and
zero page errors. Its screenshot is
`docs/evidence/p1-1/home-english-ar-SA-390.png`.

### GREEN output — 3× consecutive

Each run is `GATE_TASK=p1-1 npm run gate` on the edited tree.

Run 1:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-1/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=16.80000000000109ms frames=78, dark 360: median=16.69999999999709ms p95=16.799999999999272ms frames=100, light 1280: median=16.69999999999891ms p95=16.80000000000291ms frames=93, light 360: median=16.700000000000728ms p95=16.80000000000109ms frames=82
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (202.1s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G8
```

Run 2:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-1/
G4 PASS frame timings: dark 1280: median=16.700000000000728ms p95=1133.199999999997ms frames=89, dark 360: median=16.700000000000728ms p95=1149.9000000000015ms frames=84, light 1280: median=16.69999999999891ms p95=33.39999999999782ms frames=87, light 360: median=16.69999999999891ms p95=16.80000000000291ms frames=92
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (198.2s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G8
```

Run 3:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-1/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=33.30000000000291ms frames=97, dark 360: median=16.69999999999891ms p95=16.799999999999272ms frames=71, light 1280: median=16.69999999999891ms p95=16.799999999999272ms frames=71, light 360: median=16.69999999999891ms p95=16.700000000000728ms frames=79
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (200.6s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G8
```

Run 2’s two G4 p95 spikes (1.13 s/1.15 s) are host load during that run; the
medians stayed 16.7 ms and the gate’s timing threshold passed. Runs 1 and 3 are
clean. G8 is the only remaining gate failure, as scoped for P1-3.

### Screenshots (opened and described)

- `docs/evidence/p1-1/light-1280-view-menu.png` — light page, inverse dark
  View menu; rows are Zoom in/out, Fit window, Full page, Fit small, 100%,
  200%, Toggle controls panel. **No Theme row.**
- `docs/evidence/p1-1/dark-360-view-menu.png` — same at 360, inverse light
  menu, fully inside the viewport. **No Theme row; no horizontal overflow.**
- `docs/evidence/p1-1/home-english-390.png` — 390 px first-visit/error state:
  English LTR copy, English size error, `Open file`, no clipped text.
- `docs/evidence/p1-1/home-english-ar-SA-390.png` — same English/LTR result
  with browser locale `ar-SA`; no locale switch.

### Break-it list (5) and results

1. **Browser locale set to `ar-SA`** — `navigator.language` is `ar-SA`, but
   `lang="en"`, no `dir`, computed `ltr`, English copy, zero page errors.
   PASS.
2. **View menu must not expose Theme** — G7 green in all four
   dark/light × 1280/360 cells; opened both width screenshots. PASS.
3. **Theme must still toggle without the menu row** — the authorized test
   records `count=0, T=light, T2=dark, icon=light`. PASS.
4. **Old locale seam must be completely dead** — repo search finds no
   `STRINGS`, `LANG`, `applyLanguage`, `navigator.language`, `[dir="rtl"]`, or
   `dir=` in app/test/style/docs. G6 0 violations. PASS.
5. **Regenerated report must not reintroduce old rows** — G5 rewrites
   `tests/reports/TEST_REPORT.md`; subsequent G6 runs are 0. PASS.

### Files changed and why

- `app.js` — English literals; locale/dictionary/RTL removed; dead theme action
  removed.
- `index.html` — no `dir`; no View → Theme row.
- `style.css` — no `[dir="rtl"]` rules.
- `tests/test_suite.py` — authorized Theme assertion; two locale records
  replaced with English-only assertions; report screenshot label updated.
- `README.md`, `docs/PROGRESS.md` — English-only documentation.
- `docs/evidence/p1-1/` — 62 gate screenshots plus the two English home shots.
- `docs/GATE.md` — this record.

### Commit / tag

Commit: `P1-1: remove localisation and Theme menu`

Tag: `P1-1-pass`

### Remaining RED (deliberate, next part)

- **G8** — top-bar geometry: status/zoom/theme/panel alignment and radii at
  1280/360. P1-3.

## P1-2 — Light theme parity — STATUS: PASS

G2 is green in both themes at both widths in the fullest state, G1 is green,
and all 22 effect types are present and individually scanned. The root cause
and the app-side fix landed in P1-0 (`ae85c1c`); P1-2 re-ran the full loop on
the current tree and added a stricter per-effect coverage check so the claim
cannot silently regress.

### Root cause (file:line evidence)

The light theme was not missing its own values. The app used the generic token
name `--surface`, and the host’s global `userContent.css` also defines that
name on `*`:

```css
/* b5c02bd:style.css */
:root                    { --surface: #0b0b0c; }   /* line 18 */
:root[data-theme=light]  { --surface: #faf7f1; }   /* line 109 */
.effect-item             { background: var(--surface); } /* line 728 */
.preset-btn              { background: var(--surface); } /* line 833 */

/* tests/gate/host_usercontent.css */
@media (prefers-color-scheme: dark) {
  * { --surface: #1f1a1f; }                         /* line 13 */
}
```

A declaration directly on a descendant (`*`) wins over a value inherited from
`:root`, regardless of selector specificity. With the app in light mode and
the OS in dark mode, every effect card and preset chip inherited the host’s
dark `--surface`, while their text used the app’s light-theme dark
`--text-primary` (`style.css:802`). That produced the reported
`bg=rgb(31,26,31) fg=rgb(33,27,20) ratio=1` cards, invisible names, and black
chips. The 6-dot handle used `--text-muted` on the same dark card and measured
`2.14:1`.

The app-side fix (P1-0) namespaced the token:

- `style.css:18,107` now define `--gc-surface`; the six consumers
  (`style.css:158,369,726,831,1095` and `--bg`) use it;
- the generic `--text` and `--muted` aliases were removed;
- the active preset border now uses `--border-focus` (`style.css:842`), fixing
  the dark real-flow `2.21:1` border;
- the disabled zoom border uses `--text-muted` (`style.css:297`);
- the empty-state inline colour uses `--text-muted` (`app.js:1149`).

The host fixture remains permanently injected in G2’s real-flow cells. There
are now no hardcoded app colours outside the token blocks (G1 0).

### RED output (fresh pre-fix archive)

`GATE_TASK=p1-2-red python tests/gate/run_gate.py` in `/tmp/glyphcraft_prefix`
(a `b5c02bd` archive with the current gate and host fixture). These are the
relevant G1/G2 lines; the archive lacks the generated test fixture, so its G5
line is not the authoritative suite result.

```text
G1 FAIL token lint: 11 violation(s)
G2 FAIL theme parity: 98 violation(s), 51796 element/state checks, 10 cells, 88 scans
  [dark 1280 real-clean-initial] button.preset-btn.active:nth-of-type(6) kind=ui bg=rgb(21, 20, 22) fg=rgb(142, 43, 43) ratio=2.21 min=3 top border
  [light 1280 host-dark-icon] button.preset-btn:nth-of-type(1) kind=text bg=rgb(31, 26, 31) fg=rgb(33, 27, 20) ratio=1 min=4.5 Terminal Green
  [light 1280 host-dark-icon] span.effect-name kind=text bg=rgb(31, 26, 31) fg=rgb(33, 27, 20) ratio=1 min=4.5 Halftone
  [light 1280 host-dark-icon] button.drag-handle kind=icon bg=rgb(31, 26, 31) fg=rgb(87, 80, 63) ratio=2.14 min=3 handle dots
  [light 1280 host-dark-icon] div.effect-item:nth-of-type(1)[data-id="halftone"] kind=luminance bg=rgb(31, 26, 31) fg= ratio=1 min=2 light theme surface luminance 0.011 < 0.35
  ...
  [light 1280 host-dark-reload-light] #drop-zone kind=luminance bg=rgb(34, 29, 33) fg= ratio=1 min=2 light theme surface luminance 0.013 < 0.35
```

The same card/chip/name failures repeat at 360 and in the reload/host cells.
The full 98-line list is in `/tmp/opencode/p1-2-red.log`.

### Fix verification and the stricter effect check

No app CSS/JS change was needed in P1-2; the P1-0 namespacing already removed
every G2 failure. P1-2 adds a G2 completeness guard: the gate now records the
actual `.effect-item[data-id]` list and the expected `EFFECTS` list in every
scan, and the `fullest-top` state fails if it is not exactly all 22 expected
IDs in order. This is stricter than before and is allowed by the gate rules.

```text
expected 22 ['halftone', 'crt', 'glitch', 'vhs', 'pixelate', 'pixelsort', 'bloom', 'grain', 'vignette', 'duotone', 'posterize', 'edges', 'sketch', 'oil', 'emboss', 'blur', 'sharpen', 'invert', 'sepia', 'thermal', 'matrix', 'retro']
actual   22 ['halftone', 'crt', 'glitch', 'vhs', 'pixelate', 'pixelsort', 'bloom', 'grain', 'vignette', 'duotone', 'posterize', 'edges', 'sketch', 'oil', 'emboss', 'blur', 'sharpen', 'invert', 'sepia', 'thermal', 'matrix', 'retro']
unique 22 match True
names 22 ['Halftone', 'CRT', 'Glitch / RGB Split', 'VHS', 'Pixelate / Mosaic', 'Pixel Sort', 'Bloom / Glow', 'Film Grain', 'Vignette', 'Duotone / Gradient Map', 'Posterize', 'Edge Detect (Sobel)', 'Pencil Sketch / Crosshatch', 'Oil Paint (Kuwahara)', 'Emboss', 'Blur', 'Sharpen', 'Invert', 'Sepia', 'Thermal', 'Matrix Rain', 'Retro Palette']
```

### GREEN output — 3× consecutive

Each run is `GATE_TASK=p1-2 npm run gate` on the current tree.

Run 1:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-2/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=16.80000000000109ms frames=80, dark 360: median=16.69999999999891ms p95=16.799999999999272ms frames=84, light 1280: median=16.69999999999891ms p95=16.700000000000728ms frames=71, light 360: median=16.69999999999891ms p95=16.700000000000728ms frames=77
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (201.8s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G8
```

Run 2:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-2/
G4 PASS frame timings: dark 1280: median=16.700000000000728ms p95=16.80000000000291ms frames=79, dark 360: median=16.69999999999891ms p95=16.799999999999272ms frames=71, light 1280: median=16.69999999999891ms p95=16.700000000000728ms frames=78, light 360: median=16.69999999999891ms p95=1033.300000000003ms frames=80
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (198.5s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G8
```

Run 3:

```text
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-2/
G4 PASS frame timings: dark 1280: median=16.69999999999891ms p95=16.700000000000728ms frames=79, dark 360: median=16.700000000000728ms p95=1133.2000000000007ms frames=89, light 1280: median=16.69999999999891ms p95=16.799999999999272ms frames=79, light 360: median=16.700000000000728ms p95=33.39999999999782ms frames=92
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (228.2s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
GATE FAIL G8
```

Run 2/3’s isolated G4 p95 spikes are host scheduling during those runs; all
medians are 16.7 ms and G4 passed. G8 remains the only failure, deliberately
out of scope until P1-3.

### Screenshots (opened and described)

Fullest state:

- `docs/evidence/p1-2/dark-1280-fullest-effects.png` — dark cards on a dark
  page; light effect names, red checked boxes, visible dot handles; preset
  chips are dark bordered rectangles with light labels. No light card leaks
  through.
- `docs/evidence/p1-2/light-1280-fullest-effects.png` — cream cards on the
  cream page; dark effect names/params; preset chips cream with dark borders;
  red checked boxes; handle dots visible; no black card or chip remains.
- `docs/evidence/p1-2/dark-360-fullest-effects.png` — panel open, cards full
  width, chips wrap 3 + 3 + 1; dark surfaces, light names; `Reset`/`Remove`
  readable; no horizontal clipping.
- `docs/evidence/p1-2/light-360-fullest-effects.png` — same layout in light;
  cream cards/chips, dark names, red checks, all labels readable. The narrow
  black strip at the far left is the rendered canvas image (identical in dark),
  not a UI surface.

Host-token and reload states:

- `docs/evidence/p1-2/light-1280-host-dark-icon.png` — host dark fixture
  active, app light: cream panel, cream effect cards, readable names, cream
  preset chips. No `rgb(31,26,31)` block.
- `docs/evidence/p1-2/light-360-host-dark-icon.png` — same at 360 with the
  panel open; chips wrap and stay cream; Halftone card and controls readable.
- `docs/evidence/p1-2/light-1280-host-dark-reload-light.png` — reload while
  light with the host fixture: light drop zone, top bar, fields and panel;
  status says “No image loaded”; no dark drop zone.
- `docs/evidence/p1-2/light-360-host-os-light-os-light.png` — OS light first
  visit, no saved theme: light drop zone/panel; no dark card or field.

Interactive states:

- `docs/evidence/p1-2/light-1280-hover-preset.png` — hovered preset chip has
  the dark-red focus border and cream background; label remains readable.
- `docs/evidence/p1-2/light-1280-hover-primary.png` — primary hover keeps the
  red fill and light label; no dark surface behind it.
- `docs/evidence/p1-2/light-1280-focus-theme.png` — red focus ring around the
  sun icon; icon visible.
- `docs/evidence/p1-2/light-1280-select-focus.png` — red focus border around
  the select; field background stays white/cream, not dark.

Remaining mismatch in these screenshots: **none for theme surfaces or text.**
The known G8 top-bar misalignment is still visible and is intentionally left
for P1-3.

### Break-it list (5) and results

1. **Host `userContent.css` dark block on `*` while the app is light** — G2
   host-dark cells at 1280 and 360: 0 violations; both screenshots opened.
   PASS.
2. **Reload while light with the host block re-applied** — G2
   host-dark-reload-light cell: 0 violations; screenshot shows a light reload
   state. PASS.
3. **OS light first visit with no saved theme** — G2 host-os-light cell: 0
   violations; screenshot light. PASS.
4. **All 22 effect types, not a sample** — every `EFFECTS` ID is added and the
   `fullest-top` scan compares the DOM list to the expected list; 22/22 unique
   and matching; G2 0. PASS.
5. **Dynamic hover/focus/active/disabled states** — gate scans open menus,
   zoom menu, size picker, six theme toggles, hover/focus states, active preset
   border and disabled zoom border; G2 0; light hover/focus screenshots opened.
   PASS.

### Files changed (git diff --stat) and why

- `tests/gate/run_gate.py` — +16 lines: records `effectIds`/expected IDs and
  fails `fullest-top` unless all 22 expected effects are present. Stricter,
  not weaker.
- `docs/evidence/p1-2/` — 62 Chromium screenshots for the current tree.
- `docs/GATE.md` — this record.
- **No app file changed in P1-2.** The token fix was committed in P1-0; this
  task is the required full re-verification plus the coverage guard.
- `git diff --stat` before commit: `tests/gate/run_gate.py | 16 ++++++++++++++++`.

### Commit / tag

Commit: `P1-2: verify light-theme parity across all effects`

Tag: `P1-2-pass`

### Remaining flaws

- **G8** — top-bar geometry/alignment and radii; P1-3.
- Native `<select>` popups and native tooltips are a HUMAN-CHECK; headless
  Chromium cannot capture OS-rendered widgets.

## P1-3 — Top bar matches the purple reference — STATUS: CHECKPOINT

Reference opened: `docs/ref/r3-1-topbar.png` (512×714). I count **5 red
arrows** and **3 purple arrows**. The red arrows land on the three status
tokens, the theme icon, and the panel-toggle icon. The purple arrows all land on
the zoom group. I do **not** see a separate red arrow landing on a vertical
separator/line; the only vertical lines in that area belong to the zoom group
(purple reference), and the bar’s bottom hairline is full-width and unarrowed.

### RED-arrow targets (what is wrong)

1. **Status token `65%`** — plain muted mono text in the bar, no box, border,
   radius, padding, fixed height, hover/active/focus surface, or shared
   component with the zoom group. It is vertically centered as text
   (`height 16.5px`, `top 15.8px` at 1280) while the reference controls are
   boxed at `44px`/`top 0–2px`.
2. **Status token `1280×720`** — same unboxed muted text; same baseline and
   missing states. The second red arrow lands under this token.
3. **Status token `236ms`** — same unboxed muted text; same missing states. The
   third red arrow lands under this token. Together the three arrows read as
   “the whole status readout is the wrong style”, not as three separate
   features to build.
4. **Theme toggle (moon icon)** — bare transparent icon button: no border,
   radius, boxed background, or visible hover/pressed state. It is `44px` high
   but starts at `top 2px` while the zoom group starts at `top 0px`; its radius
   is `4px` versus the zoom group’s `6px`.
5. **Panel-toggle icon (grid)** — bare transparent menu button: no border,
   radius, or boxed background, and it is visibly wrong in the reference’s
   current-state screenshots: the icon center is `(1241,11)` versus item center
   `(1246,24)` at 1280 (and `(325,55)` versus `(330,68)` at 360), so it sits
   high and is clipped. Its height/top/radius also differ (`44px`, `top 2px`,
   `4px`).

**On the lines/separators:** I agree with your list of three controls, but I do
not see a sixth red-arrow target. The three red arrows on the left are all
under the status text, not on a separator. The only nearby separator is the
zoom group’s own border/internal divider, which is the purple reference. The
full-width `.menubar` bottom hairline is present but no arrow points at it. If
you intended the gaps between status/theme/panel to be separate red targets,
say so; otherwise I read “lines/separators next to them” as the missing box
edges around the three unboxed controls.

### PURPLE-arrow targets (reference style)

1. **Zoom-out segment / left side of the zoom group** — boxed by the shared
   rounded group border, `44px` control height, consistent padding, visible
   hover/active states.
2. **Zoom-level `65%` box** — inner bordered/rounded box with centered mono
   label; the strongest reference for a “value readout that is a control”.
3. **Zoom-in segment / right side of the zoom group** — same boxed group,
   internal 1px separators, aligned icon and hit area.

The three purple arrows therefore describe one shared component: the outer
zoom group plus its inner value box and two icon segments. The red targets
should be rebuilt from that system, not copied CSS.

### Checkpoint status

No code changed. `G8` remains RED with 16 violations from P1-2. Waiting for
written confirmation before touching code.

---

## H0 — Top bar: one segmented status box + boxed icon buttons — STATUS: PASS

Root cause: the top bar had two different component systems. `.status` was
plain muted text (`style.css`, old lines 204–213) with no border, radius,
padding, or fixed height, and the theme/panel buttons were bare transparent
`.menu-btn`/`.icon-btn` boxes (44px high, 4px radius, top offset 2px). The zoom
group was the only 48px, 6px-radius, 1px-bordered box. G8 measured exactly those
differences: `heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0,
panel-toggle-btn=44.0`, `tops status-bar=15.8, zoom-controls=0.0,
theme-toggle=2.0`, `radius zoom-controls=6.0, theme-toggle=4.0`, and the
panel-toggle icon center `(1241,11)` vs item center `(1246,24)` (clipped).

RED output (before, `GATE_TASK=p1-0` baseline, `/tmp/opencode/gateline/baseline.log`):
```
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 51784 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-0/
G4 PASS frame timings: dark 1280 ... dark 360 ... light 1280 ... light 360 ...
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 FAIL top-bar geometry: 16 violation(s)
  [dark 1280] icon-center: panel-toggle-btn icon center (1241.0,11.0) vs item center (1246.0,24.0)
  [dark 1280] height: heights status-bar=16.5, zoom-controls=48.0, theme-toggle=44.0, panel-toggle-btn=44.0
  [dark 1280] top: tops status-bar=15.8, zoom-controls=0.0, theme-toggle=2.0, panel-toggle-btn=2.0
  [dark 1280] radius: zoom-controls=6.0, theme-toggle=4.0
  ... repeated identically for [dark 360], [light 1280], [light 360]
GATE FAIL G8
EXIT=1
```
G8 was made row-aware in the same change because decision #2 explicitly permits
the status group to wrap onto its own second row at ≤768px. The stricter checks
now enforce: all four items boxed; one row at >768px; if two rows, the wrapped
row contains only the status group; per-row height/top/gap consistency; status
must be a non-interactive `div[role=status]` with exactly 3 segments, 1px
internal dividers, and no clipped segment text (`scrollWidth <= clientWidth`,
checked at every cell).

GREEN output (after, `GATE_TASK=p1-3`, `/tmp/opencode/gateline/h0-run3.log`):
```
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 52040 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/p1-3/
G4 PASS frame timings: dark 1280: median=16.7ms p95=16.7ms frames=80, dark 360: median=16.7ms p95=16.8ms frames=79, light 1280: median=16.7ms p95=16.7ms frames=80, light 360: median=16.7ms p95=16.8ms frames=79
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures (216.0s)
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 PASS top-bar geometry: 0 violation(s)
GATE PASS
EXIT=0
```
Measured geometry (real browser, 4 cells): `status-bar` 48px high,
`zoom-controls` 48px, `theme-toggle` 48×48, `panel-toggle-btn` 48×48, all
`1px` border, `6px` radius, top `0` at 1280.
At 360 the zoom/theme/panel row is at top 44 and the status group (126px wide,
all 3 segments, `38% | 900×600 | 1160ms`) wraps alone to top 96, right-aligned
(226..352); the bar is 144px tall.

Gate runs (3x): green / green / green (`h0-run1.log`, `h0-run2.log`, `h0-run3.log`; G8 0 violations in each, G5 169/0 each).

Screenshots (path — what I see):
- `docs/evidence/p1-3/dark-1280-fullest-top.png` — dark bar: status is one
  48px box at x=807..980 with `100%`, `900×600`, `1274ms` separated by two 1px
  dividers; zoom group at 988..1156 has the same outer border/radius; moon and
  panel buttons are separate 48px boxes at 1164..1212 and 1220..1268; all four
  boxes share the same top edge (y=0) and height. Icons are centered, nothing
  clipped.
- `docs/evidence/p1-3/light-1280-fullest-top.png` — same geometry on the cream
  theme; status text muted gray is readable, dividers visible, icon buttons use
  the same surface/border. No misalignment.
- `docs/evidence/p1-3/dark-360-fullest-top.png` — first row `File View Edit`;
  second row zoom group + moon + panel (all 48px, right-aligned); third row is
  the status box alone at x=226..352 with all three values (`38%`, `900×600`,
  `1160ms`) fully visible. The 4px inner padding is tighter than desktop but
  no text touches a divider.
- `docs/evidence/p1-3/light-360-fullest-top.png` — same three-row layout in
  light; the status box is complete (all four rounded corners visible) and the
  panel begins below it. No clipping at the right edge (8px margin).
- `docs/evidence/p1-3/dark-1280-focus-theme.png` — the theme button shows a
  2px accent focus ring offset 2px outside its box; the ring is complete on all
  four sides and does not overlap the panel-toggle box.
- `docs/evidence/p1-3/dark-360-focus-theme.png` — focus ring complete at 360,
  not clipped by the viewport or the wrapped status row.
- `docs/evidence/p1-3/light-1280-hover-theme-tooltip.png` — hovered theme
  button has a visibly darker surface and stronger border than its neighbours;
  no tooltip in the screenshot (native tooltip is a HUMAN-CHECK in headless).
- `docs/evidence/p1-3/dark-360-hover-theme-tooltip.png` — same hover change at
  360; box stays 48×48 and the icon stays centered.

Break-it list (5) and results:
1. **Empty state / no image.** Reload with no file at 769, 800, 1024, 320:
   status renders only `No image loaded` in segment 2, segments 1/3 hidden,
   divider widths 0, no page errors. (`/tmp/opencode/h0_breakit.py` → `EMPTY ...`.)
2. **Long values at 360.** 4000×3000 image at 400% (`400% 4000×3000 8742ms`):
   the status box grows 126→144px and every segment has
   `scrollWidth == clientWidth` (0 clipped), still one wrapped row. At 1280 it
   grows to 187px and stays on the single bar row. No errors.
3. **Pressed state at both widths.** Real `pointerdown` on the panel toggle:
   `:active` true, background becomes `rgb(42,39,41)` (`--surface-active`) and
   border `rgb(138,128,112)`, then returns on pointerup. Same at 360 and 1280.
4. **Video-export status (single segment).** `Exporting video: 7/30 frames`
   shows in one visible segment with 0px dividers on both sides; no empty box
   and no dropped text.
5. **Sticky / scroll and width 320 (below target).** Scrolling the panel to the
   end leaves `.menubar` top at 0 at 1280 and 360; at 320 the status still fits
   and wraps alone (`210..312`, 102px, `scrollWidth == clientWidth`).

Files changed (git diff --stat) and why:
```
 app.js                 |  22 +++++++--
 index.html             |   4 +-
 style.css              |  45 ++++++++++++++++---
 tests/gate/run_gate.py | 119 ++++++++++++++++++++++++++++++++++++++-----------
```
- `index.html`: status is now one `.status-group` with three `.status-seg`
  spans; panel toggle joins the `.icon-btn bar-btn` box system.
- `style.css`: `.status-group`/`.status-seg` component (48px, 1px border, 6px
  radius, 1px dividers), `.menubar-right > .icon-btn` box/hover/active/focus
  states, and the 900/768px rules (smaller status font/padding, status wraps
  alone and stays right-aligned).
- `app.js`: `setStatusSegments()` writes the three segments; `updateStatus()`
  and the empty/video-export paths use it.
- `tests/gate/run_gate.py`: row-aware G8 plus the stricter boxed/status/
  divider/no-clip checks described above.

Commit / tag: `H0: box the segmented status group and top-bar icon buttons` / tag `H0-pass`.

Remaining flaws: the native tooltip on the theme button is not capturable in
headless Chromium (HUMAN-CHECK). At 360 the status inner padding is 4px, the
minimum that still fits all three values without clipping; if a future value
string is longer than `400% 4000×3000 8742ms`, the status box grows until it
reaches the bar width, then the 1px-clip check will fail the gate rather than
silently truncate.

---

## H1 — Stepper arrows: rapid clicks, hold speed, exact values — STATUS: PASS

Root cause (measured on `HEAD 7940130` in a real browser, before any change):

The up/down arrows were the browser's own number spinner on
`input[type="number"]` (`index.html:150,184,227,234,277,326-375,425`), not an
application control. Three measured defects:

1. **Hit area.** In a 44px-high field only a ~6×6px strip inside the right
   edge responds. A 4×7 probe grid over the field's right edge stepped only at
   `x = right−17..−14`, `y = top+14..17` (21 of 21 tested points that produced a
   step were inside that 6px strip). Everything else focused the field and did
   nothing → "the arrow does not always grab / does not step reliably".
2. **A burst of rapid presses is a double-click gesture, and the field's
   `dblclick` is a reset.** The value field owns reset-to-default
   (`app.js:1339` on HEAD: `numInput.addEventListener("dblclick", () =>
   commit(p.def, true))`, and `app.js:1957` `setVal(+slider.defaultValue)`),
   and adjustment defaults are 0 (`index.html:326-375`). The browser counts
   repeated presses in one spot as clickCount 1, 2, 3… and dispatches
   `dblclick` on the second one. Measured with real counting (CDP `clickCount`,
   8 presses 120ms apart, `docs/evidence/h1/red-multiclick.txt`):
   - brightness `20 → 21 → **0** → 1 → 2 → 3 → 4 → 5 → 6`
   - halftone Dot `5 → 6 → **5** → 6 → 7 → 8 → 9 → 10 → 11`

   That is the reported symptom word for word: "adds 1–3 steps then the value
   falls back to 0". A plain double-click on the field also does it on its own
   (`42 → 0`).
3. **Slow hold.** The native spinner repeats at ~17/s (measured 17 steps in the
   first second), which is under the required steady rate.

Correction to an earlier draft of this section: "only +9 steps then dead" on
`fx.halftone.size` was that control's clamp (min 2, **max 14**), not a dead
spinner. Re-measured with a clamp-aware probe, the native spinner delivers all
30 presses when `clickCount` is held at 1
(`docs/evidence/h1/red-native-spinner.txt`). The application's own value path
was already exact: 30 rapid presses on `depth-num` produced `80 → 110` with one
write per step. So the defects were the affordance (6px hit strip, a gesture
that lands on a reset handler) and the hold rate — not the state model.

Fix (one component, one value writer):

- `app.js:24` `attachStepper()` — a 44×44 `button.stepper` split into two
  22×21 halves (`[data-step=up|down]`), one `pointerdown` = one **synchronous**
  step, pointer capture, hold repeat after `STEP_INITIAL_DELAY = 300ms`
  (`app.js:21`) at `STEP_REPEAT_MS = 35ms` (`app.js:22`), release ends the
  gesture and schedules **one** coalesced render. No render can run during the
  gesture, so a slow render can never delay, drop or overwrite a step.
- The arrows are a separate element from the value field, so a burst can never
  become a `dblclick` reset on that field.
- Every numeric control now steps through the single clamps used everywhere
  else (`commit()` for effect params, `setVal()`/`roundToStep()` for
  adjustments), and keyboard (`ArrowUp/Down`, `Shift` ×10, `PageUp/Down` ×10),
  wheel, typing and drag keep working.
- The browser's spinner is hidden only where this component replaces it
  (`input[type="number"].has-stepper`, `style.css:740`); the output
  width/height fields, which have no stepper, keep their native arrows.

RED output (before, `docs/evidence/h1/red-multiclick.txt`, real click counting;
the probe scripts are kept in `docs/evidence/h1/tools/`):

```
$ python red_multiclick.py <HEAD-worktree> 8 120 adj-brightness-num 20
=== adj-brightness-num  kind=native-spinner  clicks=8 spacing=120ms  hit=(1251, 466)
  click 1: value=21
  click 2: value=0
  click 3: value=1
  ...
dblclick targets: ['adj-brightness-num']
VERDICT value fell back to the default 0

$ python red_multiclick.py <HEAD-worktree> 8 120 fx.halftone.size 5
  click 1: value=6
  click 2: value=5
  ...
dblclick targets: ['INPUT']
VERDICT non-monotonic
```

Native spinner, clamp-aware probe (`docs/evidence/h1/red-native-spinner.txt`):

```
=== fx.halftone.size  kind=native-spinner  clicks=30 spacing=20ms
start input=5 state=5 | end input=14 state=14 | writes=0
VERDICT expected end 14 (clamp 2..14), got 14 | value writes=0 for 30 clicks
=== depth-num  kind=native-spinner  clicks=30 spacing=20ms
start input=80 state=80 | end input=110 state=110 | writes=60
VERDICT expected end 110 (clamp 20..240), got 110 | value writes=60 for 30 clicks
```

Real double-click on the value text, and the same burst on the fixed tree
(`docs/evidence/h1/green-multiclick.txt` → `dblclick targets: ['BUTTON']`,
`VERDICT monotonic`, 21…28 / 6…13 with no fall-back).

GREEN output (after): G9 in the gate drives the real UI for **every** numeric
control (42 controls: 6 digitiser/export + 8 adjustments + 28 effect params
across all 22 effects) with real mouse events and no artificial waits:

```
G9 PASS numeric steppers: 65 measurements, 15 hold-rate rows
```

Post-fix write log for a 30-click burst at 20ms
(`docs/evidence/h1/green-stepper.txt`):

```
=== fx.halftone.size  kind=step-btn  clicks=30 spacing=20ms
start input=5 state=5 | end input=14 state=14 | writes=30
VERDICT expected end 14 (clamp 2..14), got 14 | value writes=30 for 30 clicks
=== depth-num  kind=step-btn  clicks=30 spacing=20ms
start input=80 state=80 | end input=110 state=110 | writes=60
VERDICT expected end 110 (clamp 20..240), got 110 | value writes=60 for 30 clicks
```

30 writes for 30 clicks on the clamped control (each click still commits and is
clamped), and the 20..240 control moves exactly +30 with no lost step.

Covered per control: 30 up-clicks at 25ms → `start + 30·step` clamped, then 30
down-clicks back to `start`; mixed burst 10↑/5↓/10↑/3↓; 30 × ArrowUp, 10 ×
Shift+ArrowUp, 10 × PageDown; 30 wheel-up + 30 wheel-down ticks; 100 clicks at
0–10ms; double- and triple-click on the arrow with a real increasing
`click_count` (one step per press, the exact gesture that used to trigger the
reset); click-then-hold; and on a 4000×3000 image with a 6-effect stack
(`halftone, posterize, edges, emboss, blur, sharpen`) the same bursts plus
30-up/30-down and mixed bursts. Value **and** `state.opts` are asserted after
every burst. The green burst trace above shows the same 8-click gesture that
resets the pre-fix field stays monotonic on the stepper.

Hold rate, old (native spinner) vs new, 5 controls × 1s/2s/3s, two/three runs
each (`docs/evidence/h1/hold-old.jsonl`, `hold-new.jsonl`):

| control | 1s old → new | 2s old → new | 3s old → new |
|---|---|---|---|
| adj-brightness | 17 → 21 | 37 → 50 | 57 → 78 |
| adj-contrast | 17 → 21 | 37 → 50 | 57 → 78 |
| adj-hue | 17 → 21 | 36 → 50 | 57 → 78 |
| depth | 17 → 21 | 37 → 50 | 57 → 78 |
| char-offset | 17 → 21 | 37 → 50 | 57 → 78 |

New rate 21/s over the first second (300ms delay + 28.6/s steady, sampled at
26/s by rAF) — **≥ the old rate at every duration**, initial delay 300ms
(inside the required 300–500ms window), steady rate inside 15–30/s.

Input latency (`pointerdown` → displayed value): 0.01–2ms on an idle stack and
with a 4K heavy stack pending (budget 16ms).

Gate runs (3x): green / green / green (`/tmp/opencode/h1-gate-1.log`,
`h1-gate-2.log`, `h1-gate-3.log`; G9 65 measurements/15 hold rows each, G5
169/0 each).

Screenshots (path — what I see):
- `docs/evidence/h1/dark-1280-steppers.png` — adjustments section: every row
  has a full-width slider, a 56px value box and a 44×44 stepper flush with the
  panel's right edge; chevrons centered in each half with a 1px divider; all
  eight rows share the same baseline and box height.
- `docs/evidence/h1/light-1280-steppers.png` — same geometry on the light
  theme: white stepper boxes with the warm 1px border, dark chevrons, visible
  divider; no dark panel leaks into the cream sidebar.
- `docs/evidence/h1/dark-360-steppers.png` — 360px: slider ~190px, value box,
  then the 44px stepper; the stepper's right border sits 8px inside the
  viewport, nothing clipped; the top row is under the sticky action bar only
  because the capture scrolled it there.
- `docs/evidence/h1/light-360-h1-row-zoom.png` and
  `light-360-stepper-clip-4x.png` — 3×/4× crops of one row: rounded corners on
  all four sides of the stepper, 1px internal divider, chevrons not touching
  the borders, 4px gap to the value box.
- `docs/evidence/h1/dark-1280-h1-effects.png` / `light-1280-h1-effects.png` —
  effect cards: label, 84px slider, 56px value box, 44px stepper; the stepper
  is inside the card (right edge 1268 = card edge), no overlap with Reset /
  Remove.
- `docs/evidence/h1/dark-360-h1-effects.png` / `dark-360-h1-adjustments.png` —
  the same rows at 360px; nothing overflows the card and the slider stays
  usable.
- `docs/evidence/h1/dark-1280-step-hover.png`, `dark-1280-step-focus.png`,
  `dark-1280-step-pressed.png` (and the `light-360-*` equivalents) — hover
  darkens the pressed half, focus draws the 2px accent ring outside the box,
  pressed shows `--surface-active`; the ring is not clipped by the card.

Break-it list (5) and results
(`python docs/evidence/h1/tools/breakit_h1.py` → `BREAK-IT PASS`):
1. **Touch press steps twice or not at all** — `has_touch` context, `page.tap`
   on the up half: 10 → 11, state 11 (exactly one step).
2. **Keyboard double-fires** — focus the stepper: Space 21, Enter 22, ArrowUp
   23, ArrowDown 22 (one step per press; the button's `click` is prevented).
3. **Wrong button / stray gesture steps** — right-click and middle-click on the
   up half: value stays 5.
4. **Undo history polluted or lost** — three presses 700ms apart: 3 → undo 2 →
   undo 1. A 5-press burst inside the app's 600ms history window is one entry
   (5 → undo 1), identical to the slider's existing coalescing.
5. **Layout breaks at the smallest width / text zoom / with a heavy 4K stack** —
   320px: `scrollWidth == innerWidth`, stepper inside its card, all panel
   controls ≥44×44 (the existing 169-test touch-target check passes); 200% text
   zoom: still visible, no page overflow; 4K + 4 effects + 20 rapid presses:
   value 20, state 20.

Files changed (git diff --stat) and why:
```
 app.js                 | 129 ++++++++++++-
 index.html             |   2 +-
 style.css              |  41 +++-
 tests/gate/run_gate.py | 497 ++++++++++++++++++++++++++++++++++
```
- `app.js`: the shared `attachStepper()` component, its use in the effect
  param rows and in `syncSliderNumber()`, synchronous stepping with deferred
  render, step snapping for the adjustment path, PageUp/PageDown and wheel on
  both groups, and the `has-stepper` marker.
- `index.html`: the cell-size / glyph-weight row becomes
  `.control-row control-row-stack` (two 44px steppers no longer fit side by
  side in a half-width control).
- `style.css`: the `.stepper`/`.step-btn` component (44×44, 1px border, 6px
  radius, hover/active/focus states), spinner removal scoped to
  `.has-stepper`, the stacked row, and a 56px value box in effect cards.
- `tests/gate/run_gate.py`: permanent G9 (real mouse events, all controls,
  heavy 4K stack, hold-rate and latency measurements).
- Also in `app.js`: the deferred render after typing/arrow-key commits moved
  from 40ms to 140ms so a key-repeat burst coalesces into one frame instead of
  one render per key; stepping is unaffected (it is synchronous and commits
  with `notify = false`), and pointer-down latency stays 0.01–2ms.

Commit / tag: `H1: shared stepper replaces the native number spinner` / tag `H1-pass`.

Remaining flaws:
- A held press shows no live preview until release: renders are deliberately
  deferred for the duration of the gesture (that is what makes the hold fast
  and exact). H4's render scheduler replaces this with per-frame coalescing.
- The stepper is one button: a screen-reader user increases with Enter/Space
  and decreases with ArrowDown (stated in its `aria-label`); two separate
  buttons would be finer-grained.
- Real touch hardware is HUMAN-CHECK.
