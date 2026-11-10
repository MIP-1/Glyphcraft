# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no install and no server side: plain HTML,
CSS and four classic scripts loaded in order (`engine.js` → `effects.js` →
`reorder.js` → `app.js`), plus `render-worker.js`, which `app.js` starts when
the browser supports it. Git keeps the readable sources; `npm run build`
writes an optional minified `dist/` for publishing.

## Status — 2026-11-10

**Current status:** IN PROGRESS — P2-3 Step 3 (audit, baseline, golden outputs,
decision table) is complete and tagged `P2-3-A-pass`; Step 4 (video: 850 MB
limit and native-resolution export) is complete and tagged `P2-3-B-pass`. Both
are on branch `p2-3-work`. Step 5 (speed) is next. Part 1, Part 1B, Part 1C,
P2-1 and its post-PASS cleanup, Part M, and P2-2 remain complete and tagged.
`npm run gate` was green three times in a row on the final P2-2 tree
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
| P2-3 fast preview | IN PROGRESS | Steps 3–4 complete, tags `P2-3-A-pass` and `P2-3-B-pass` |
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

**P2-3 Step 3 (complete, tag `P2-3-A-pass`)**

- Full audit of every source, tool and test file: `docs/evidence/p2-3/audit.md`.
- Measured baseline on the unchanged tree: `docs/evidence/p2-3/baseline.json`
  and `baseline.log`. The preview clamps 1080p and 4K to 1600x900; native
  samples are one-shot. Slowest item is `oil` at 1.7–2.5 s preview and
  8.8–13.1 s native 4K. Worker drag stays at 16.7 ms rAF with 0 long tasks;
  sync drag is 83.3 ms with 1,000 long tasks. Playback is 16.7 ms in all six
  video cells. Headless software raster is a floor, not a GPU claim.
- 200 golden canvas hashes (22 effects × 3 modes × 1080p/4K, 44 native
  Effects Only cases, and 24 stack cases), seed `0x5EED1234`, no excluded
  effects: `tests/gate/golden_p2_3.json`, `docs/evidence/p2-3/golden.md`.
- New permanent G20 runs the golden check. It passed 200/200 exact in 193.5 s.
- Decision table: no module rebuild. `effects.js`, `engine.js`, `app.js` and
  the video path are OPTIMIZE IN PLACE; `reorder.js`, `render-worker.js`,
  `index.html`/`style.css` and the build are KEEP. See
  `docs/evidence/p2-3/decisions.md`.

**P2-3 Step 4 (complete, tag `P2-3-B-pass`)**

- Image and video limits are separate top-level constants:
  `IMAGE_MAX_FILE_BYTES = 40 MB` (unchanged) and
  `VIDEO_MAX_FILE_BYTES = 850 MB`. 850 MB exactly is accepted, +1 byte is
  rejected with a message naming the correct limit, and a 0-byte file is
  rejected as empty.
- Video export always uses `video.videoWidth` × `video.videoHeight`. The size
  preset, width, height, fit and lock controls stay visible but are disabled
  for video, with an inline note; an image re-enables them. Frames, the 20 s
  clamp, 24 fps and no audio are unchanged.
- New permanent G21 (`tests/gate/video_p2_3_check.py`): 25 checks, 0 failures,
  52.6 s standalone. It proves the split boundaries, a 0-byte rejection, zero
  `FileReader`/`Blob`/`fetch` calls on a video load, the disabled-but-visible
  controls, and ffprobe-equal native export for 1920x1080, 1280x720, 3840x2160,
  1080x1920, 1002x562 and a rotated stream — all with the preset deliberately
  set to `custom 320x180`.
- Closeout on a real 838.1 MB 4K VP9 WebM: load 0.70 s, 0 JS heap growth,
  50.3 fps playback with 3 effects, seek exact, native 3840x2160 export in
  107.9 s. See `docs/evidence/p2-3/video-audit.md` and `video-large.log`.
- 169 tests green, G20 golden 200/200 exact, existing video gate green, dist
  smoke hash `4135467496`.

**Next steps**

1. P2-3 Step 5 speed work in the order in `decisions.md`, one change per
   commit, G20 exact and paired before/after numbers: `fxOil` allocations,
   palette parsing, adjustment merge and diffusion reuse, 4K preview base
   cache, render-key serialization and the B4 `filterControls()` fix.
2. Then the three full gate runs, break-it, docs, merge and `P2-3-pass`.
3. After P2-3: P2-4 undo/redo/history, P2-5 before/after finish and P2-6 presets.
4. Mobile landscape refinement (height <500 px): the sheet and controls work
   today, but add a landscape-specific snap once real-device testing is available.

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
WebP, GIF, BMP, AVIF, SVG) up to **40 MB** and videos (WebM, MP4, …) up to
**850 MB** are accepted. If a file cannot be read, the drop area says why and
what to try. Video always exports at the source's original resolution; the
size preset, width, height and fit controls stay visible but are disabled for
video. The interface is English only.

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
python tests/gate/golden_check.py # 200 effect/mode/input canvas hashes (also G20)
python tests/gate/video_p2_3_check.py # 850 MB split, no whole-file read, native export (G21)
python tests/gate/video_large.py  # closeout only: one real 838 MB 4K video load/play/export
python tests/gate/p2_2_breakit.py # six hostile worker cases
python tools/dist_smoke.py        # publish build renders the same canvas
```

Reports and screenshots land in `tests/reports/` (gitignored). Tests use
`/tmp/glyphcraft_test.png` and generate a short WebM fixture with `ffmpeg`.
They do not modify the source tree.

## Deploying

The project is a static site. Pushing the folder to GitHub Pages (or any static
host) works as-is; `.nojekyll` is not required because there are no
underscore-prefixed paths. Apart from the files of the site itself (including
the two self-hosted woff2 fonts), the only third-party requests are the
optional Google Fonts stylesheet and the Crimson Text faces it selects; the
page falls back to Goodmountain/Georgia/serif if they are blocked. JetBrains
Mono is served from this origin; its SIL OFL 1.1 licence sits next to it in
`assets/fonts/JetBrainsMono-OFL.txt`.

## Browser support

Recent Chromium, Firefox and Safari. The test suite runs headless Chromium.
