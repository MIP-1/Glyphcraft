# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no install and no server side: plain HTML,
CSS and four classic scripts loaded in order (`engine.js` → `effects.js` →
`reorder.js` → `app.js`). Git keeps the readable sources; `npm run build`
writes an optional minified `dist/` for publishing.

## Status — 2026-11-08

**Current status:** PASS — Part 1, Part 1B, Part 1C, P2-1 and its post-PASS
cleanup, and Part M are complete. P2-2 is next and not started. Tag `P2-1-pass`
marks the P2-1 closeout; tag `P2-1-cleanup-pass` marks the cleanup commit;
tags `M1-1-pass` and `M1-2-pass` mark the single Part M commit on `main`
(both tasks share one commit because M1-2 reuses the M1-1 mobile branch;
`docs/GATE.md` records the combined evidence honestly; the tag resolves to the
exact commit with `git rev-parse M1-2-pass`).
`npm run gate` is green three times in a row on the final tree
(`docs/evidence/m1-2/gate-run-1/2/3.log`).

| Work | State | Evidence |
| --- | --- | --- |
| P1-0 gate foundation | PASS | commit `ae85c1c`, tag `P1-0-pass` |
| P1-1 remove localisation / RTL | PASS | commit `2446db4`, tag `P1-1-pass` |
| P1-2 light theme parity | PASS | commit `961ede5`, tag `P1-2-pass` |
| P1-3 top bar | PASS | commit `855a5b4`, tag `P1-3-pass` |
| H0 top bar | PASS | `7940130`, tag `H0-pass` |
| H1 steppers | PASS | tag `H1-pass` |
| H2 white effects | PASS | tag `H2-pass` |
| H3 compare freeze + grab | PASS | tag `H3-pass` |
| H4 reduce load | PASS | tag `H4-pass` |
| C1 / C2 / C3 audit, video control, multi-effect cost | PASS | one commit, tags `C1-audit-pass`, `C2-video-control-pass`, `C3-perf-pass` |
| P2-1 before/after lag | PASS | tag `P2-1-pass`, gate runs 5–7, `docs/GATE.md` P2-1 |
| P2-1 post-PASS cleanup + publish build | PASS | tag `P2-1-cleanup-pass`, gate runs 8–10, `docs/GATE.md` cleanup |
| M1-1 mobile bottom sheet | PASS | Part M commit, tag `M1-1-pass` |
| M1-2 single-row mobile top bar | PASS | same commit, tag `M1-2-pass` |
| P2-2 Worker + OffscreenCanvas | NOT STARTED | no `Worker` or `OffscreenCanvas` in the repo |
| P2-3 fast preview | NOT STARTED | preview is always downscaled |
| P2-4 undo / redo / history | NOT STARTED | history exists but is unfinished |
| P2-5 before/after finish | NOT STARTED | |
| P2-6 presets finish | NOT STARTED | |
| P3-1 … P3-5 | NOT STARTED | |

**Done in this step**

- Mobile now means viewport width ≤700 px in any orientation. The layout is
  one column: one-row top bar, preview, bottom sheet. The panel keeps its DOM,
  controls and logic, and never covers the preview: the preview shrinks as the
  sheet grows. Snaps come from `window.visualViewport.height` (peek = handle +
  sticky action bar + safe area, measured 105 px at 360; half = 45%; full =
  88%). Dragging the handle uses Pointer Events with capture and
  position/velocity snapping; the grabber tap cycles peek → half → full. The
  handle is an ARIA separator with ArrowUp/Down and Enter/Space. The status box
  moved into the handle row as the same three-segment component.
- Soft keyboard handling uses `visualViewport` resize/scroll, `viewport-fit=cover`
  and safe-area padding, and scrolls the focused field into view. Mobile touch
  targets are ≥44×44, inputs are ≥16 px, numeric fields get
  `inputmode="decimal"`, and effect reordering is long-press only.
- The top bar is a single 56 px row (plus safe-area top): menu, zoom group,
  theme button and sheet toggle. File/View/Edit live in the mobile menu with
  the inverse palette, all 14 commands and shortcut labels, and unchanged
  keyboard shortcuts. At 320 px the padding and gaps shrink first; nothing
  wraps, clips or disappears. Widths 701+ keep the previous layout, including
  the 701–768 overlay branch.
- New permanent checks G14–G18: mobile layout, gestures (CDP touch), touch
  targets, desktop-unchanged guard and menu reachability/contrast. G8's mobile
  rule changed deliberately from "two rows allowed if status-only" to "exactly
  one row at ≤700 px", with a RED proof on a broken build.
- 169 existing tests, G1–G13, contrast (9068 pairs, 0 violations), the publish
  build and `tools/dist_smoke.py` (same canvas hash `651948841`) are green.
  Baseline evidence is in `docs/evidence/m1-0/`; RED/green logs, screenshots
  and 14/14 break-it cases are in `docs/evidence/m1-1/` and `m1-2/`.

**Next steps**

1. Start P2-2: move the effect pipeline to a Worker with OffscreenCanvas, add
   its acceptance check first, and keep G11/G13 green.
2. Then P2-3 fast preview, followed by P2-4 to P2-6 in order.
3. Mobile landscape refinement (height <500 px): the sheet and all controls
   work today (640×360 peek preview is 199 px), but add a landscape-specific
   snap once real-device testing is available.
4. Re-run the full gate three times after each task and open every screenshot.

**HUMAN-CHECK**

- Real Android Firefox/Chrome and iOS Safari: sheet drag feel, grabber tap
  cycle, soft keyboard and URL-bar collapse, and real-device frame rate are not
  claimed by the headless Chromium gate.
- Real touch hardware: Compare split grab at 100/200/400% and the sheet handle
  gesture. Headless CDP touch reports 20/20 grabs and 0 pipeline calls during a
  drag.
- Desktop: confirm 701–768 px still shows the old overlay and 1280 px is
  unchanged (G17 compares 15 rects, tolerance 1 px).
- Drag the split on a 4K image in a real browser: it must stay under the
  pointer and stay correct after zoom, pan, resize, a value change, undo/redo
  and a theme switch.

## Run it

```bash
cd glyphcraft
python -m http.server 8000
# open http://localhost:8000
```

Opening `index.html` directly over `file://` also works in Chromium-based
browsers. A local server is recommended because some browsers restrict
clipboard and font loading on `file://`.

## Modes

| Mode | What it does |
| --- | --- |
| **Script** | Maps brightness to characters from a ramp (18 categories/sets, charset presets from ASCII to Braille, cell size, weight, color/mono). |
| **Dither** | Error-diffusion and ordered dithering (Floyd–Steinberg, Atkinson, Sierra, Stucki, Burkes, JJN, Bayer 2/4/8, halftone, blue noise, random) with serpentine scanning and 2–16 levels. |
| **Effects Only** | Skips the glyph pass and applies the image effects directly to the source. |

Twenty-two stackable effects (CRT, glitch, halftone, VHS, bloom, …) are
available in every mode, plus adjustments (brightness, contrast, saturation,
hue, highlights, shadows, sharpen, blur, invert, sepia). Drag a box by its
six-dot handle (or focus the handle and press `Alt+Up` / `Alt+Down`) to change
the render order.

## Home screen

Drop a file, paste it (`Ctrl+V`) or press **Open file**. Images (PNG, JPG,
WebP, GIF, BMP, AVIF, SVG) and videos (WebM, MP4, …) up to **40 MB** are
accepted. If a file cannot be read, the drop area says why and what to try.
The interface is English only.

## Keyboard

| Key | Action |
| --- | --- |
| `Ctrl+O` | Open a file |
| `E` | Export |
| `R` | Reset all (press twice) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `C` | Compare split |
| `O` (hold) | Show the original |
| `+` / `−` | Zoom in / out |
| `0` / `F` | Fit window |
| `Space` + drag | Pan |
| `\` | Toggle the controls panel |
| `T` | Toggle theme |
| `Alt+Up` / `Alt+Down` | Move the focused effect up / down |
| `Esc` | Close menu / compare / full page |
| `?` | Shortcut list |

## Themes

Dark and light themes share one semantic token set in `style.css`. The choice
is stored in `localStorage` (`glyphcraft-theme`) and applied before first paint.
The automated contrast audit checks text, placeholders, form fields and control
borders in both themes at 360 px and 1280 px.

## Tests

```bash
python tests/test_suite.py     # 169 checks, headless Chromium via Playwright
python tests/test_contrast.py  # WCAG contrast audit, both themes, 2 widths
python tools/dist_smoke.py     # publish build renders the same canvas
```

Reports and screenshots land in `tests/reports/` (gitignored). Tests use
`/tmp/glyphcraft_test.png` and generate a short WebM fixture with `ffmpeg`.
They do not modify the source tree.

## Deploying

The project is a static site. Pushing the folder to GitHub Pages (or any static
host) works as-is; `.nojekyll` is not required because there are no
underscore-prefixed paths. The only network request is the optional Google
Fonts stylesheet — the page falls back to Georgia/serif if it is blocked.

## Browser support

Recent Chromium, Firefox and Safari. The test suite runs headless Chromium.
