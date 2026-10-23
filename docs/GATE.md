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
