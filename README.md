# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no build step, no npm install and no server
side: plain HTML, CSS and four classic scripts loaded in order
(`engine.js` → `effects.js` → `reorder.js` → `app.js`).

## Status — 2026-11-02

**Current status:** Part 1, Part 1B and Part 1C are PASS. Part 2 is in progress
at P2-1 and is **not** PASS yet. The full `npm run gate` is **not** green.

| Work | State | Evidence |
| --- | --- | --- |
| P1-0 gate foundation | PASS | commit `ae85c1c`, tag `P1-0-pass` |
| P1-1 remove localisation / RTL | PASS | commit `2446db4`, tag `P1-1-pass` |
| P1-2 light theme parity | PASS | commit `961ede5`, tag `P1-2-pass` |
| P1-3 top bar | CHECKPOINT, no tag | `docs/GATE.md` line 770. The work landed in H0 and G8 is green, but the id was never re-stated as PASS |
| H0 top bar | PASS | `7940130`, tag `H0-pass` |
| H1 steppers | PASS | tag `H1-pass` |
| H2 white effects | PASS | tag `H2-pass` |
| H3 compare freeze + grab | PASS | tag `H3-pass` |
| H4 reduce load | PASS | tag `H4-pass` |
| C1 / C2 / C3 audit, video control, multi-effect cost | PASS | one commit, tags `C1-audit-pass`, `C2-video-control-pass`, `C3-perf-pass` |
| P2-1 before/after lag | IN PROGRESS | fix is written but uncommitted; `compare_check.py` 20/20 PASS |
| P2-2 Worker + OffscreenCanvas | NOT STARTED | no `Worker` or `OffscreenCanvas` in the repo |
| P2-3 fast preview | NOT STARTED | preview is always downscaled |
| P2-4 undo / redo / history | NOT STARTED | history exists but is unfinished |
| P2-5 before/after finish | NOT STARTED | |
| P2-6 presets finish | NOT STARTED | |
| P3-1 … P3-5 | NOT STARTED | |

**Done in this step**

- P2-1 root cause found and fixed: `drawOriginal` redrew the 4K source into a
  clipped context on every pointer move (9.9 ms/frame in software raster). The
  original is now downscaled once per preview size into `originalBitmap`
  (0.07 ms/frame); 4K `render()` median fell 10.2 ms → 0.6 ms.
- The compare drag harness now drives one continuous in-page pointer gesture
  from a rAF loop with a discarded 60-frame warm-up and a forced GC + 150 ms
  settle before measuring. Thresholds and check count are unchanged.
- `python tests/gate/compare_check.py`: **20/20 PASS**, drag p95 16.8 ms at both
  1280×720 and 4K, pipeline invoked 0 times, 50/50 handle grabs at 100/200/400%.
- `python tests/gate/video_check.py`: 25 checks, **1 FAIL** — 6-effect playback
  p50 26.2 ms against a 26.0 ms limit, while the zero-effect control measured in
  the same session is p50 19.5 ms. The miss is 0.2 ms.

**Next steps**

1. Settle P1-3: either record it as PASS with a `P1-3-pass` tag (the H0 work
   satisfies it and G8 is green) or keep the checkpoint and say so. Part 2's
   prerequisite list asks for `P1-0 … P1-3` PASS.
2. Get `npm run gate` green three times in a row for P2-1. G11 flaked once
   under full-gate load (1280 p95 33.3 ms) and G13 is 0.2 ms over budget.
3. Open and describe every P2-1 screenshot, run the five break-it cases, write
   the `docs/GATE.md` block, then commit and tag `P2-1-pass`.
4. Only then start P2-2 (Worker + OffscreenCanvas).

**HUMAN-CHECK**

- Drag the split on a 4K image in a real browser; the split must stay under the
  pointer and stay correct after zoom, pan, resize, a value change, undo/redo
  and a theme switch.
- G13 playback is measured in headless software raster. Confirm six-effect
  video playback on the real GPU before treating that 0.2 ms as a product bug.

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
