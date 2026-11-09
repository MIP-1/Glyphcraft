# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no install and no server side: plain HTML,
CSS and four classic scripts loaded in order (`engine.js` → `effects.js` →
`reorder.js` → `app.js`), plus `render-worker.js`, which `app.js` starts when
the browser supports it. Git keeps the readable sources; `npm run build`
writes an optional minified `dist/` for publishing.

## Status — 2026-11-09

**Current status:** PASS — Part 1, Part 1B, Part 1C, P2-1 and its post-PASS
cleanup, Part M, and P2-2 are complete. P2-3 is next and not started. Tag
`P2-2-pass` marks the P2-2 closeout. Earlier tags: `P2-1-cleanup-pass` (cleanup
commit), `P2-1-pass`, and `M1-1-pass` / `M1-2-pass` on the single Part M
commit. `npm run gate` is green three times in a row on the final P2-2 tree
(`docs/evidence/p2-2/gate-run-1/2/3.log`).

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
| P2-2 Worker + OffscreenCanvas | PASS | tag `P2-2-pass`, gate runs 1–3, `docs/GATE.md` P2-2 |
| P2-3 fast preview | NOT STARTED | preview is always downscaled |
| P2-4 undo / redo / history | NOT STARTED | history exists but is unfinished |
| P2-5 before/after finish | NOT STARTED | |
| P2-6 presets finish | NOT STARTED | |
| P3-1 … P3-5 | NOT STARTED | |

**Done in this step**

- The preview effect pipeline can run in a classic Web Worker drawing into
  `OffscreenCanvas`. Only rAF-driven renders are eligible: image source, worker
  ready, fonts ready, ≥6 enabled effects, preview ≥900,000 px, and no compare /
  original / cache-off / video-export. Everything else stays synchronous, so
  tests, video playback and export behave exactly as before.
- One job in flight, one latest-wins pending job; transferred `ImageBitmap`
  results, an epoch that drops stale jobs across image/video changes, and a
  persistent worker-side source bitmap.
- Pixel parity is exact (0/255, so the 1/255 allowance was not used). The
  preview starts from a persistent `ImageBitmap`, never the `HTMLImageElement`,
  because Chromium resamples the two differently when downscaling. The frame,
  composite and stage caches are cleared when that bitmap is installed.
- The worker registers the same self-hosted JetBrains Mono 400/700 bytes
  (`assets/fonts/JetBrainsMono-latin.woff2`) with `FontFace`. Font readiness
  also clears the cached glyph densities and rebuilds the ramp, so a page never
  keeps a fallback-font ramp.
- Fallback: `?worker=0`, `window.__GC_DISABLE_WORKER`, or any boot/runtime error
  permanently returns to the synchronous path with the same pixels and no page
  error.
- New permanent G19: the acceptance check proves no long task >50 ms over a 3 s
  seven-effect drag on 3840×2160, exact sync/worker parity, latest-only under 20
  rapid updates, `preview`/`full` job parity, and the disabled-worker fallback.
  6/6 break-it cases pass. 169 tests, G1–G19, the publish build and a
  deterministic `tools/dist_smoke.py` (`4135467496`) are green; the full gate
  passed three times in a row.

**Next steps**

1. Start P2-3: fast preview on top of the existing `preview` / `full` worker
   job kinds, acceptance check first.
2. Then P2-4 undo/redo/history, P2-5 before/after finish and P2-6 presets.
3. Mobile landscape refinement (height <500 px): the sheet and all controls
   work today (640×360 peek preview is 199 px), but add a landscape-specific
   snap once real-device testing is available.
4. Re-run the full gate three times after each task and open every screenshot.

**HUMAN-CHECK**

- Real-device frame rate, real GPU playback and real Safari: the worker's
  long-task numbers come from headless Chromium and are not a real-device
  claim.
- Worker `FontFace` support in a real Safari/Firefox: if a browser cannot
  register the self-hosted font in the worker, the code falls back to the
  synchronous path, but that fallback is unverified there.
- G3 wrote 174 screenshots across the three gate runs; they were reviewed as
  contact sheets and spot checks in this pass, not individually. An individual
  pass over all 58 per run remains.
- Real Android Firefox/Chrome and iOS Safari: sheet drag feel, grabber tap
  cycle, soft keyboard and URL-bar collapse.
- Desktop: confirm 701–768 px still shows the old overlay and 1280 px is
  unchanged (G17 compares 15 rects, tolerance 1 px).

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
python tests/test_suite.py        # 169 checks, headless Chromium via Playwright
python tests/test_contrast.py     # WCAG contrast audit, both themes, 2 widths
python tests/gate/p2_2_check.py   # worker acceptance (also permanent G19)
python tests/gate/p2_2_breakit.py # six hostile worker cases
python tools/dist_smoke.py        # publish build renders the same canvas
```

Reports and screenshots land in `tests/reports/` (gitignored). Tests use
`/tmp/glyphcraft_test.png` and generate a short WebM fixture with `ffmpeg`.
They do not modify the source tree.

## Deploying

The project is a static site. Pushing the folder to GitHub Pages (or any static
host) works as-is; `.nojekyll` is not required because there are no
underscore-prefixed paths. The only network request is the optional Google
Fonts stylesheet (and its font files); the page falls back to Georgia/serif if
it is blocked. JetBrains Mono is self-hosted and never touches the network.

## Browser support

Recent Chromium, Firefox and Safari. The test suite runs headless Chromium.
