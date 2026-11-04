# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no build step, no npm install and no server
side: plain HTML, CSS and four classic scripts loaded in order
(`engine.js` → `effects.js` → `reorder.js` → `app.js`).

## Status — 2026-11-04

**Current status:** Part 1, Part 1B, Part 1C and P2-1 are PASS. P2-2 is next and
not started. `npm run gate` is green three times in a row on the P2-1 tree
(`docs/evidence/p2-1/gate-run-5/6/7.log`), with paired performance budgets.

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
| P2-2 Worker + OffscreenCanvas | NOT STARTED | no `Worker` or `OffscreenCanvas` in the repo |
| P2-3 fast preview | NOT STARTED | preview is always downscaled |
| P2-4 undo / redo / history | NOT STARTED | history exists but is unfinished |
| P2-5 before/after finish | NOT STARTED | |
| P2-6 presets finish | NOT STARTED | |
| P3-1 … P3-5 | NOT STARTED | |

**Done in this step**

- P2-1 closed as PASS. `drawOriginal` redrew the 4K source into a clipped
  context on every pointer move (9.9 ms/frame in software raster). It is now
  downscaled once per preview size into `originalBitmap` (0.07 ms/frame); the
  4K `render()` median fell 10.2 ms → 0.6 ms. The split drag repaints only the
  changed band and G11 proves it pixel-identical to the full composite.
- Gate rules audited: G11 drag and G13 playback now compare paired windows,
  G13 gates the best of five windows, and both still fail a deliberately
  slowed build (logs in `docs/evidence/rule-red/`).
- 62 screenshots opened and described, 7/7 break-it cases (4K, zoom+pan,
  resize mid-drag, undo/redo mid-drag, theme mid-drag, 360 px), 169 existing
  tests, G1–G13 green in runs 5, 6 and 7.

**Next steps**

1. Start P2-2: move the effect pipeline to a Worker with OffscreenCanvas, add
   its acceptance check first, and keep G11/G13 green.
2. Then P2-3 fast preview, followed by P2-4 to P2-6 in order.
3. Re-run the full gate three times after each task and open every screenshot.

**HUMAN-CHECK**

- Drag the split on a 4K image in a real browser: it must stay under the
  pointer and stay correct after zoom, pan, resize, a value change, undo/redo
  and a theme switch.
- Confirm six-effect video playback on the real GPU; G13 runs in headless
  software raster with a paired zero-effect control.

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
