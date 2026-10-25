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

## H2 — Effects that output white — STATUS: PASS

### Root cause (three effects, measured on `HEAD 7940130` in `/tmp/opencode/gc-h0`)

**1. Pencil Sketch / Crosshatch was white by construction** (`effects.js:317-338`
on `7940130`):

- `effects.js:319` draws the source through `grayscale(1) invert(1) blur(3px)`
  and then `effects.js:322-323` composites the original over it with
  `color-dodge`. Colour-dodge divides the inverted base by `1 - source`: dark
  source pixels (source ≈ 0) leave the bright inverted base unchanged, and
  bright source pixels saturate to 255. A dark image therefore becomes a white
  page with a few surviving dots — the reported symptom exactly.
- `effects.js:326-328`: `const amt = p.amount / 100;` then
  `v = 255 - (255 - d[i]) * amt`. At `amt = 0`, `v = 255` for every pixel: the
  declared neutral value was a **pure white page**, so the required
  "Amount 0 = identity" could never hold. Nothing validated the parameter, so
  `undefined`, `""`, `0` and negative strings all took the same white path.
- `effects.js:329-333`: only two hatch layers (`% 9` and `% 11`); the second
  needs `cross > 0.05`. `cross` only scaled their darkness (`- 40 * cross`,
  `- 30 * cross`) and never their spacing, so **Hatch could not change line
  density** and at Hatch <= 5 it drew no hatch at all. Maximum darkening was
  70 levels over a near-white dodge result, which is why Amount 70 / Hatch 40
  stayed "a white page with a few faint dots".

**2. Edge Detect at Amount 0 was a black page with a transparent frame**
(`effects.js:290-315` on `7940130`). The Sobel result was multiplied by
`amount`; at 0 every interior pixel became 0 (black), and the 1px frame was
never written, so it stayed alpha 0. Amount 0 is this effect's neutral value,
so it must be identity, and the effect must not punch transparency into an
export.

**3. Blur sampled outside the canvas** (`effects.js:407-413` on `7940130`).
`ctx.filter = blur(r)` was applied directly to the unpadded canvas, so every
sample outside the image was transparent: 12,240-272,244 non-opaque pixels per
render and a dark fringe at all four edges, which then leaked into the Script
stage and the exported PNG.

Also found while reading every effect: no effect validated its numeric
parameters. `p.amount / 100` on `""` is 0 (white), on `undefined` is `NaN`
(`fxClamp(NaN)` passes `NaN` through and `ImageData` turns it into 0), and
`blur radius 1e9` from a pasted preset queued a canvas allocation that hung a
fuzz worker for 30 minutes. That is a parameter-path bug shared by all 22
effects, fixed with one reader.

### RED output (before any change)

The permanent sweep run against the pre-fix worktree
(`docs/evidence/h2/red-all-effects-old.log`):

```
$ cd /tmp/opencode/gc-h0 && python tests/gate/effects_sweep.py --only all --quick
249 checks, 94 failure(s)
  FAIL sketch amount 0 hatch 0: output is not the input
  FAIL sketch amount 0 at 1x1: not the input or wrong size
  FAIL sketch tonal hatch 0: dark third 252.0 vs light 249.1 (gap -0.01 < 0.25)
  FAIL sketch gradient amount 10 hatch 0: {'mean': 0.9988, 'std': 0.0058, 'whiteFrac': 0.9811, ...}
  FAIL sketch dark photo amount 10 hatch 0: {'mean': 0.9913, 'std': 0.0092, 'whiteFrac': 0.8528, ...}
  FAIL sketch param path '': {'mean': 1, 'std': 0, 'whiteFrac': 1, ...}
  FAIL sketch param path '0': {'mean': 1, 'std': 0, 'whiteFrac': 1, ...}
  FAIL sketch param path '-5': {'mean': 1, 'std': 0, 'whiteFrac': 1, ...}
  FAIL sketch param path None: {'mean': 1, 'std': 0, 'whiteFrac': 1, ...}
  FAIL edges [amount=0]: 6132 non-255 alpha pixels, not identity at neutral
  FAIL blur [radius=4]: 60240 non-255 alpha pixels
  FAIL blur [radius=20]: 272244 non-255 alpha pixels
  FAIL pair halftone->edges [default]: mean=0.727 std=0.388 alpha_bad=1020
  FAIL pair halftone->blur [max]: mean=0.638 std=0.209 alpha_bad=40572
```

Sketch-only RED (`docs/evidence/h2/red-sketch-old.log`): `45 checks,
29 failure(s)`. The tonal gap is **negative** on the pre-fix effect (dark third
252.0 vs light 249.1), i.e. the dark part of a gradient came out *lighter*
than the light part. At Amount 10 more than 98% of the gradient was pure
white. This is the reported bug reproduced without asking which values fail.

### Fix

- `effects.js:73-77` `fxNum(v, lo, hi, def)`: one reader for every numeric
  parameter (26 call sites). Empty, `null`, `undefined`, booleans and
  non-finite input fall back to the declared default; everything else is
  clamped to the range the UI exposes. `effects.js:1379-1395` already rejected
  empty/`-`/`.`/out-of-range text while typing and clamped on blur
  (`clampToParam`, `app.js:12-14`); the two paths now agree.
- `effects.js:345-382` rewrites `fxSketch` as tonal crosshatch:
  `paper = 255 * (0.60 + 0.40 * L)`, four layers at 45 degrees, -45 degrees,
  both axes, and a dense cross layer for `L < .75 / .50 / .30 / .15`, line
  spacing `14-8h / 15-9h / 16-9h / 11-5h` (every range is > 2x and never below
  6px), pencil gray `0.72`, floor 60 so a black source still shows hatching,
  and a final `mix(src, sketch, amount/100)`. `amount <= 0` returns a
  pixel-identical copy before any math.
- `effects.js:299-343` `fxEdges`: `amount <= 0` returns a clone; the 1px frame
  is written with alpha 255 before the Sobel loop.
- `effects.js:452-485` `fxBlur`: extend the edge pixels into a padded canvas
  (9 strips including corners), blur the padded copy, crop it back, then force
  alpha 255 after the crop (premultiplied blending leaves a sub-255 ring).
- No other effect's maths changed: every other numeric read is the same
  expression through `fxNum` with the same defaults, and the regression hashes
  below prove the pixels did not move.

### Code review of every effect (before running the sweep)

Ranges cite the fixed `effects.js`. "Hazard checked" lists the lines/paths
examined, not a claim that the effect is perfect. No row says "looks fine".

| # | effect | params (type, min..max, step, def) | math hazards checked | suspected failing ranges |
|---|---|---|---|---|
| 1 | halftone | size int 2..14, 1, 5 | `s` clamped >=2 (87); inner block always has `n>=1` (97-100); dot radius `>=0.4` (105); luma finite; opaque paper fill | none found; min size on 1x1 gives one dot, not white |
| 2 | crt | scan/curve/mask 0..100, 1, 45/25/35 | `cy = h/2 >= .5` so no /0 (118-121); sampled `sx` clamped to `w-1` (126); `scanLine >= .35`, mask factor `>= .6`; every channel clamped | none found; curve=100 + 1px width still bounded by clamp |
| 3 | glitch | shift/slices 0..40, 1, 8/8 | `shift 0` becomes `max(1,..)` so it is a 1px split, not identity (declared neutral is not identity); slice `y/hh` guarded (153-157); out-of-bounds drawImage is a no-op | shift=0: 1px RGB split by definition; slices=0: no slices |
| 4 | vhs | bleed/noise 0..100, 1, 40/30 | bleed up to 100 can exceed a narrow width (draws nothing, source kept); noise clamped; random band ~6% of rows | noise=0 still adds +18 on ~6% rows (not identity); no white path |
| 5 | pixelate | size int 2..40, 1, 8 | source `w/h = max(1,..)` for 1x1 at size 40 (190); smoothing explicitly off; exact upscale | none found; 1x1 block is a flat colour, never white unless input is |
| 6 | pixelsort | threshold/amount 0..100, 1, 50/60 | random row gate; `while` bounded by `x++` / `x=end+1` (206-221); `run.sort` on finite luma; amount 0 skips nearly all rows | threshold 0 sorts whole rows; amount 0 is random-but-identity, by design |
| 7 | bloom | radius 1..30, amount 0..100, 1, 8/55 | CSS `blur()` on the gate browser; radius rounded/clamped; `globalAlpha 0` = identity; `source-atop` keeps canvas size | amount 0 identity; a browser without canvas filter would draw unblurred, still not white |
| 8 | grain | amount 0..100, 1, 35 | `a = 0` at amount 0 so `n = 0` = identity (250); clamp per channel | none found |
| 9 | vignette | amount 0..100, size 10..100, 1, 55/65 | inner radius `<` outer at every size incl. 1x1 (264); alpha 0 = identity; finite stops | none found; size 10 and 100 only change falloff |
| 10 | duotone | dark/light colour, defaults #0a1a10 / #8dffa8 | `fxHex` falls back to #000 on malformed input (79-82); equal endpoints produce a flat tint by definition | equal/malformed colours: flat by definition, not a white bug; sweep exempts equal endpoints |
| 11 | posterize | levels int 2..16, 1, 5 | `step = 255/(levels-1) >= 17` so no /0 (289); product rounded into Uint8Clamped | none found; levels=2 gives two tones |
| 12 | edges | amount 0..100, 1, 80 | fixed: `amount<=0` clone (302); 1px frame alpha 255 (307-314); w/h <3 has no interior (kept black) | fixed: amount 0 identity + transparent frame; a 1x2 image has no edges by definition |
| 13 | sketch | amount 0..100, 1, 70; cross 0..100, 1, 40 | fixed: `amount<=0` clone (351); spacings 6..16 so `% spacing` never /0; `lat = w+h+1` keeps `x-y` positive (357); alpha 255; floor 60 | fixed: amount 0 white, dark image white, Hatch no density; all Hatch 0..100 tested |
| 14 | oil | radius int 1..3, 1, 2 | every quadrant has `n>=6` at r=1 so `mean`/`varr` never /0 (392-406); `px/py` clamped; opaque | none found; cost is O(w*h*r^4) — 4K attribution below |
| 15 | emboss | amount 0..100, 1, 70 | `fxConvolve` clamps amount (419), copies the 1px frame (424-427), kernel sums to 1, clamps each channel | none found; amount 0 is identity for opaque input |
| 16 | blur | radius 0..20, 1, 4 | fixed: `r<=0` clone (457); `pad = ceil(2r)+1`; 9 edge strips incl. corners (461-474); crop; alpha forced 255 (478-484) | fixed: 12k-272k transparent pixels + dark fringe; 4K cost noted below |
| 17 | sharpen | amount 0..100, 1, 60 | same `fxConvolve`; kernel sums to 1; frame copied; clamp | none found; amount 0 identity |
| 18 | invert | none | `255-v` on Uint8Clamped; alpha preserved | none found; not identity by definition |
| 19 | sepia | amount 0..100, 1, 80 | `a` in 0..1; matrix coefficients finite; clamp per channel | none found; amount 0 identity |
| 20 | thermal | amount 0..100, 1, 80 | `l/255` in 0..1; each channel clamped before mix; `a` in 0..1 | none found; amount 0 identity |
| 21 | matrix | density 10..100, 1, 55; amount 0..100, 1, 70 | `cell >= 10`, `cols >= 1` (527-529); random `y0/len` bounded; glyph alpha computed; glow clamped | amount 0 still draws dim glyphs (not identity by definition), never white |
| 22 | retro | palette select gameboy/cga/nes | unknown palette falls back to gameboy (545); palette hex literals valid; distances finite | 4-6 colour output has low std by design (mean stays between palette colours) |

Cross-cutting hazard found in the review: `applyEffects`
(`effects.js:589-599`) catches every effect error and keeps the previous
canvas. That means a broken effect cannot paint a white page, but it can also
hide a throw. The fuzz run reports page errors separately; none occurred.

### Parameter-path audit (value -> state -> effect -> render)

The UI path is `app.js:1379-1401`: while typing, empty / `-` / `.` / `-.`
mark the box `aria-invalid` and leave state alone; a finite in-range value is
written live; out-of-range text is marked invalid and only clamped on blur.
`app.js:12-14` `clampToParam` snaps to the step grid and clamps to min/max.
The effect side now repeats that clamp through `fxNum`, so a value that never
went through the controls cannot differ. Measured through the real UI
(`docs/evidence/h2/breakit-h2.txt`, paste via `Control+V` into Amount, starting
at 70):

| input | state after blur | aria-invalid while editing | render |
|---|---|---|---|
| `` (empty) | 70 (kept) | true | mean 0.6831, std 0.1584, finite |
| `-` | 70 (kept) | true | mean 0.6831, std 0.1584 |
| `abc` | 70 (kept) | true | mean 0.6831, std 0.1584 |
| `1e3` | 100 (clamped on blur) | true | mean 0.7633, std 0.1389 |
| ` 50 ` | 50 (trimmed) | false | mean 0.6295, std 0.1756 |

The sweep's own parameter-path run (`docs/evidence/h2/sweep-param-path.log`,
34 checks) additionally feeds `None`, `""`, `"0"`, `"-5"`, `"abc"`, `" 40 "`,
`0`, `-5`, `1e3`, `1e9` and non-integers straight into `fxSketch` and the other
effects: all are finite, within range after clamping, and non-blank.

### Sweep results (GREEN, after the fix)

```
$ python tests/gate/effects_sweep.py --only sketch
34 checks, 0 failure(s)               (docs/evidence/h2/sweep-param-path.log)

$ python tests/gate/effects_sweep.py --only all --quick
204 checks, 0 failure(s)             (docs/evidence/h2/sweep-all-effects.log)
1848 ordered pairs, 0 white/blank    (docs/evidence/h2/sweep-pairs.log)

$ python tests/gate/effects_sweep.py --only fuzz
115553 renders, 0 failures           (docs/evidence/h2/sweep-fuzz.log)

$ python tests/gate/effects_ui.py --shots docs/evidence/h2
26 checks, 0 failure(s)              (docs/evidence/h2/ui-driven.log)
```

The all-effects table covers every effect at min / min+1 step / default /
midpoint / max-1 step / max / disabled, and the sketch acceptance suite covers
(a)-(e). The pair matrix runs every ordered pair at default and all-max in
both orders (1848 renders). The fuzz run generates 2,000 random values per
parameter (including edge values and non-integers), random stacks of 2-8
effects in random order, 1x1 / 2x2 / 17x13 / 4000x3000 inputs, grayscale,
transparent, 16-bit-like and portrait/landscape cards, and logs every white or
NaN result with its exact repro. It found none.

Test definitions, stated so they cannot be mistaken for weakened thresholds:
uniform white = `mean >= 0.97 and std <= 2/255`; a flat non-white card
(`std < 2/255` with `mean >= 0.5`) is not white; black is only a failure when
*all* tested cards are flat black, and is allowed for `invert` and `edges`
below 5% (defined outputs); identity is asserted only at declared neutral
configs (`sketch/edges/emboss/sharpen/thermal/sepia/grain/vignette/pixelsort`
at their neutral, `crt(0,0,0)`, `blur radius 0`, `bloom amount 0`); `duotone`
with equal endpoints and stacks containing `invert`/`duotone` are exempt from
the white check because colour is the parameter; fuzz stacks use
`mean >= 0.985 && std <= 1.5/255` for a blank page. These definitions are in
`tests/gate/effects_sweep.py` and apply unchanged to the pre-fix tree (that is
how the RED run above failed).

Sketch acceptance, measured (`sweep-param-path.log`):

| check | result |
|---|---|
| (a) Amount 0 identity, hash, Hatch 0/40/100 + 1x1/2x2/17x13/31x7 | equal, correct size |
| (b) dark third vs light third, Amount 100 | gap 0.32 / 0.34 / 0.38 (Hatch 0/40/100), required >= 0.25 |
| (c) not white, Amount >= 10, all Hatch, gradient + dark photo + colour bars | dark photo mean 0.2634-0.5131, none blank |
| (d) Hatch min vs max line density | ink pixels 18,576 -> 43,350 = 2.33x, required >= 2x |
| (e) 4000x3000 Sketch render | 639-747 ms across runs, documented (budget was 200 ms or document the cost) |

Regression hashes, old vs new, at every UI-reachable value
(`docs/evidence/h2/h2-hash-old.txt`, `h2-hash-new.txt`, 106 renders each,
`Math.random` stubbed by `tools/h2_hashes.py`): the two files differ **only**
for `blur`, `edges` and `sketch` — the three fixed effects. The other 19
effects are pixel-identical. Within the changed effects, `blur radius 0`,
`edges amount 0` and `sketch amount 0` are now identity by definition; every
other difference is the fixed edge/alpha or the fixed sketch maths.

### Cost at 4000x3000 (`docs/evidence/h2/timer4k-breakdown.txt`)

| render | ms |
|---|---|
| posterize | 550 |
| edges | 1866 |
| sketch (Amount 100, Hatch 100) | 747 |
| emboss | 2110 |
| blur (radius 4) | 777 |
| sharpen | 1790 |
| six-effect stack (posterize, edges, sketch, emboss, blur, sharpen) | 9869 |

These are full-size export-path numbers. The interactive preview is capped at
1600px (`app.js:165-166`, `PREVIEW_MAX`), so the editor does not run this cost
on every interaction; reducing it is H4's task, not hidden here.

### Screenshots (opened and described)

- `docs/evidence/h2/sketch-dark-matrix.png` — 3 rows (Hatch 0 / 40 / 100) x
  4 columns (Amount 0 / 30 / 70 / 100) on the dark galaxy photo. Amount 0 is
  the untouched photo (navy sky, blue wave, white stars) in all three rows.
  Amount 30 shows a light graphite weave over the wave; Amount 70 a clear
  diagonal crosshatch with the dark sky visibly denser than the bright wave;
  Amount 100 is a light paper field whose wave is drawn by hatching, not by
  white pixels. Hatch 0 lines are coarse (~14px), Hatch 100 fine (~6px);
  no cell is blank and none is a solid black fill.
- `docs/evidence/h2/sketch-bright-matrix.png` — same grid on the bright
  cream/dark-blob photo. Amount 0 is the original; Amount 30 adds a faint
  weave; Amount 70 a readable 45-degree hatch; Amount 100 keeps the cream
  highlights as paper while the dark blobs carry visible crosshatch. Hatch
  100 is measurably finer; the paper never disappears.
- `docs/evidence/h2/ui-sketch.png` — the real editor canvas with Sketch
  enabled and driven by drag + 15 stepper clicks + typed digits + wheel: the
  Script stage turns the hatched base into dense glyph rows, light at the top
  and darker toward the bottom-left; nothing is a white page.
- `docs/evidence/h2/ui-blur.png` — soft glyph rows with no white border and no
  dark vignette at the canvas edge (the old transparent fringe would show as a
  clean rectangular band of missing glyphs; it is gone).
- `docs/evidence/h2/ui-edges.png` — black canvas. This fixture is a smooth
  colour gradient with no edges, so the Sobel base is legitimately near-black
  (`mean 0.0182`, `std 0.0059`); the old failure here was the alpha-0 frame,
  not the darkness, and the sweep's edge cards with real edges are not blank.
- `docs/evidence/h2/ui-halftone.png` — regular dot-screen glyph texture over
  the green/magenta gradient, visible dot pitch, no clipping.
- `docs/evidence/h2/ui-crt.png` — horizontal scanline rows, slightly curved
  verticals, magenta top / green bottom preserved.
- `docs/evidence/h2/ui-glitch.png` — RGB-split glyph rows with horizontal
  slice offsets; no white bands.
- `docs/evidence/h2/ui-vhs.png` — noisy, smeared rows and colour bleed, still
  full-frame content.
- `docs/evidence/h2/ui-pixelate.png` — blocky glyph clusters with 8px-ish
  blocks, no empty areas.
- `docs/evidence/h2/ui-pixelsort.png` — vertical streaks where bright runs
  were sorted; the frame stays filled.
- `docs/evidence/h2/ui-bloom.png` — bright rows bloom into their neighbours,
  dark background retained.
- `docs/evidence/h2/ui-grain.png` — uniform grain over the whole glyph field,
  no clear rectangle.
- `docs/evidence/h2/ui-vignette.png` — corners darker than the centre, centre
  unclipped.
- `docs/evidence/h2/ui-duotone.png` — green/black two-colour map, gradients
  preserved as tone steps.
- `docs/evidence/h2/ui-posterize.png` — banded glyph rows at the 5-level
  default, no flat white.
- `docs/evidence/h2/ui-oil.png` — painterly blobs with smoothed cluster edges.
- `docs/evidence/h2/ui-emboss.png` — grey relief with a consistent diagonal
  light direction, no clipped highlights.
- `docs/evidence/h2/ui-sharpen.png` — crisp glyph boundaries, no halos at the
  canvas edge.
- `docs/evidence/h2/ui-invert.png` — inverted photo: light magenta left,
  dark right; full frame, no transparency.
- `docs/evidence/h2/ui-sepia.png` — warm brown/olive cast with tonality kept.
- `docs/evidence/h2/ui-thermal.png` — black -> red -> yellow -> white heat
  ramp with the hot band in the lower middle.
- `docs/evidence/h2/ui-matrix.png` — sparse green glyph rain on near-black;
  the low mean (0.2176) is the effect, not a bug.
- `docs/evidence/h2/ui-retro.png` — NES palette blocks: red/orange top-right,
  green/blue/white lower field; flat colours by design, no white page.

These 22 UI shots and the two matrices are the states the task touched. The
gate's own G3 run also captured the 62 full chrome screenshots
(dark/light x 360/1280, menus, hover/focus, fullest panel) into
`docs/evidence/h2/`; they are visually unchanged from H1 because H2 touches
only effect maths, and G2 checked all 10 theme cells / 88 scans green.

### Break-it list (5) and results

`python docs/evidence/h2/tools/breakit_h2.py` ->
`docs/evidence/h2/breakit-h2.txt`:

1. **Amount 0 is not identity through the UI, or only alone.** Set Amount to 0
   by typing, then compare the prepared base hash with the same stack minus
   Sketch (alone, and with Posterize): both hashes equal, amount reads 0. PASS.
2. **Hatch extremes crash or go non-deterministic on tiny images.** 1x1, 2x2
   and 17x13 sources at Hatch 0/50/100: 9 runs, no exception, no non-finite or
   non-opaque pixel, two runs byte-identical. PASS.
3. **Pasted junk corrupts the parameter.** Paste `""`, `-`, `abc`, `1e3`,
   ` 50 ` into Amount and blur: state stays finite and in range (70 kept,
   100 clamped, 50 trimmed), the box flags `aria-invalid` while the text is
   invalid, and every render stays non-blank. PASS.
4. **Undo/redo restores the value but not the pixels.** Change Hatch 40 -> 90,
   undo, redo: 40 -> 90 -> 40 -> 90 and the hashes return exactly to the
   base/changed hashes (3611139 / 3979507346). PASS.
5. **4K plus a six-effect stack hangs or blanks.** Replace the image after the
   stack is set: 4000x3000, 6 effects, finite, alpha 255, not blank; stack
   7468 ms, Sketch alone 639 ms, no page errors. PASS (cost documented above;
   H4 owns reducing it).

### Gate runs (3x consecutive)

Green / green / green (`docs/evidence/h2/h2-gate-1.log`, `h2-gate-2.log`,
`h2-gate-3.log`). Each run:

```
G1 PASS token lint: 0 violation(s)
G2 PASS theme parity: 0 violation(s), 76680 element/state checks, 10 cells, 88 scans
G3 PASS screenshots: 62 captured in docs/evidence/h2/
G5 PASS existing tests: REPORT WRITTEN 169 checks, 0 failures
G6 PASS no Arabic: 0 violation(s)
G7 PASS no Theme item in View menu
G8 PASS top-bar geometry: 0 violation(s)
G9 PASS numeric steppers: 65 measurements, 15 hold-rate rows
G10 PASS effects: 239 checks, 0 failure(s)
GATE PASS
```

G10 is the new permanent check (sketch acceptance + all-effects + 1848 pairs)
and fails on any white/NaN/alpha/identity result. G4 passed in all three runs;
its light-360 p95 was 16.7 ms in run 1 but spiked to 1200/1283 ms in runs 2/3
(dark and 1280 cells stayed at 16.7 ms). G4 currently fails only on a missing
or errored sample with fewer than 10 frames and reports p95 without a
threshold (`tests/gate/run_gate.py:1128-1130`), so this spike did not make the
run red. It is pre-existing frame variance on the smallest light cell, not an
effect-maths change; H4's scheduler work is where frame-time stability is
addressed, and G4 must not be weakened meanwhile.

### Files changed and why

```
 effects.js             | 159 ++++++++++++++++++++++++++++++++++-------------
 tests/gate/run_gate.py |  39 +++++++++++-
 2 files changed, 154 insertions(+), 44 deletions(-)
```

- `effects.js`: `fxNum` and its 26 call sites, the `fxSketch` rewrite,
  `fxEdges` neutral + opaque frame, `fxBlur` padding + alpha fix.
- `tests/gate/run_gate.py`: G10 runs the permanent sweep
  (`effects_sweep.py --only all --quick`; 239 checks, ~50 s) and fails on any
  white/NaN/alpha/identity result.
- New permanent tests: `tests/gate/effects_sweep.py` (662 lines: sketch
  acceptance, all effects, 1848 pairs, fuzz) and `tests/gate/effects_ui.py`
  (231 lines: every effect through the real controls, preset, undo/redo,
  theme toggle, 4K replace).
- Evidence tooling: `docs/evidence/h2/tools/` (`h2_hashes.py`,
  `sketch_shots.py`, `timer4k.py`, `timer4k_breakdown.py`, `breakit_h2.py`).

### Commit / tag

`H2: tonal crosshatch identity + effect sweep` / tag `H2-pass`.

### Remaining flaws

- `applyEffects` silently keeps the previous canvas on a thrown effect
  (`effects.js:589-599`). No effect throws in 115,553 fuzz renders, but a
  future one would fail quietly; surfacing a console error badge is a UI
  decision, not part of H2.
- Sketch at 4000x3000 costs 639-747 ms on the export path. The UI preview is
  capped at 1600px, so this is not felt while editing; H4 must not change the
  pixels while reducing it.
- The 4K six-effect export stack is 9.9 s. That is the measured cost, not a
  claim that it is fast.
- Edge Detect on an image with no edges is legitimately black
  (`ui-edges.png`); a user may read that as "broken". It is the effect's
  defined output, not a white page.
