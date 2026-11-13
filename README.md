# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no install and no server side: plain HTML,
CSS and four classic scripts loaded in order (`engine.js` → `effects.js` →
`reorder.js` → `app.js`), plus `render-worker.js`, which `app.js` starts when
the browser supports it. Git keeps the readable sources; `npm run build`
writes an optional minified `dist/` for publishing.

## Status — 2026-11-13

**Current status:** the owner's video-fix round is **in progress** on `main`.
V0 (`V0-pass`) reproduced the real video defects and registered G22; V1
(`V1-pass`) fixes the unstable/pixelated frames so every played, paused or
seeked frame renders at the full preview size, with parity in Chromium and
Firefox. V2–V5 (real MP4/WebM export, video control bar, output dimensions,
image hitches) are **NOT DONE** yet. P2-3 remains complete and tagged
`P2-3-pass`; P2-4 is still **NOT STARTED** and is not part of this pass.

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
| P2-3 fast preview + video limits | PASS | tag `P2-3-pass`, gate runs 1–3, `docs/GATE.md` P2-3 |
| Video fix V0 | PASS | tag `V0-pass`, `docs/evidence/v0/report.md` |
| Video fix V1 full-resolution frames | PASS | tag `V1-pass`, `docs/evidence/v1/report.md` |
| Video fix V2–V5 | IN PROGRESS | MP4/WebM export, control bar, output sizes, hitches |
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
- 169 tests green at the time (the suite is 170 after Step 5 C3), G20 golden
  200/200 exact, existing video gate green, dist smoke hash `4135467496`.

**P2-3 Step 5 (complete)**

Every candidate was measured old-vs-new in one browser session with a paired
A/B/B/A window design, and kept only when it was at least 10% faster in 4 of 5
windows (or removed a measured long task) with identical output hashes. Logs
and raw data are in `docs/evidence/p2-3/perf-log.md`.

- C1 (`ad5bb37`): `fxOil` no longer allocates a `vals` array and a `best`
  array per quadrant of every pixel. Radius 2 at 1600×900: median 1470.4 →
  1137.5 ms (−22.6%), p95 −32.4%, 5/5 windows. Hashes identical at radius
  1/2/3 on 1600×900 and 3840×2160.
- C2 (`2443ee0`): palette parsing is cached by content and built once per
  render instead of per glyph or per pixel. Dither + palette: median 2395.5 →
  352.4 ms (−85.3%), p95 −81.8%, 5/5 windows. Script + palette only −5.7%, so
  no claim there. Old-vs-new parity matrix 26/26 across five built-in palettes,
  a custom `rgb()`/`rgba()`/hex palette, all nine dither kernels, mono,
  spectrum, Effects Only and the SVG/TXT exports.
- C3 (`ec5a726`): B4 — `filterControls()` now re-applies the mode-visibility
  rules last, so a panel search cannot reveal Dither-only controls in Script
  mode, and empty sections are hidden while a query is active. New regression
  check raises the suite to 170 (`tests/gate/run_gate.py` G5 requires 170).

- C4 (`4ab2169`): the adjustment pixel passes (highlights/shadows/sharpen,
  invert, sepia) share one `getImageData`/`putImageData` instead of up to
  three. Function-level paired probe: 5/5 windows and −11.0% / −17.5% in two
  runs, identical hash; the parity matrix gained nine adjustment profiles
  (35/35).
- C5 (reverted): diffusion-buffer pooling measured slower for both layouts
  (+3.5% planar, +2.5% interleaved, 0/5 windows), so `engine.js` stayed as C4.
  The negative result and the probe are kept in `perf-log.md`.
- The last two `decisions.md` items were measured and rejected: a cached 4K
  preview base could save <0.1% (the source draw is below timer resolution on
  the 1600×900 preview), and the render key costs 14–20 µs per call against a
  65–245 ms render. No code changed; both are recorded in `perf-log.md`.

**P2-3 Step 6–7 (complete)**

- Three consecutive full gate runs passed on the final tree: 06:16–06:45,
  13:56–14:24 and 14:24–14:54 on 2026-11-11 (`docs/evidence/p2-3/gate-run-1/2/3.log`).
  Every run: G1–G21 PASS, G5 `170 checks, 0 failures`, G20 `200 cases, 0 problems`,
  G21 `25 checks`, `GATE PASS`, exit 0. An early aborted launch and one run
  interrupted by a server restart are kept in the evidence folder and do not
  count.
- Break-it: 31/31 PASS in 87.7 s (`tests/bench/breakit_p2_3.py`,
  `docs/evidence/p2-3/breakit.log`), covering all 12 required cases — the two
  limits, corrupt/truncated/renamed video, portrait/rotated/odd/4K video,
  export cancel/new file/background page, playback interactions, 360 px sheet,
  worker fallback / `file://` / Firefox, 4K 12-effect drag, 20 loads, source
  switches, out-of-range amounts, and light-theme reload.
- All 68 screenshots of the final run were opened in batches of 12
  (`docs/evidence/p2-3/screenshot-review.md`). Runs 1 and 2 are pixel-identical
  outside the preview canvas and the status digits (0 differing pixels in every
  file); runs 2 and 3 differ only by a 2,124 px one-capture slider reflow, which
  is listed under HUMAN-CHECK.
- Limits: video 850 MB, image 40 MB, both named constants. Video export is
  always the source's native pixel size, proven with ffprobe on six sources.
- Full evidence and decisions: `docs/GATE.md` P2-3.

**Next steps**

1. P2-3 is PASS. Owner hand-check (fresh reload in both themes, one real video
   over 100 MB, one phone).
2. After the owner confirms P2-3: P2-4 undo/redo/history, then P2-5
   before/after finish and P2-6 presets. Do not start P2-4 in this pass.
3. Mobile landscape refinement (height <500 px): the sheet and controls work
   today, but add a landscape-specific snap once real-device testing is available.

**HUMAN-CHECK**

- Real-device frame rate, real GPU playback and real Safari: the worker's
  long-task numbers come from headless Chromium and are not a real-device
  claim.
- Worker `FontFace` support in a real Safari/Firefox: if a browser cannot
  register the self-hosted font in the worker, the code falls back to the
  synchronous path. Firefox break-it used that fallback with correct output and
  no errors; real-device feel is unverified.
- MP4/H.264 on a real browser: this Chromium build does not guarantee H.264, so
  the gate fixtures and the 838.1 MB closeout file are VP8/VP9 WebM. The largest
  real-world video on the owner's machine is not tested.
- Hidden-tab export: headless Chromium reports `document.hidden=false`, so the
  hidden-tab export branch was not exercised (export cancel, new file and a
  second page in front are covered).
- P2-3 screenshots: all 68 files of the final run were opened in batches of 12.
  Runs 1 and 2 are pixel-identical outside the preview canvas and status digits.
  Runs 2 and 3 differ in one file by a 2,124 px slider thumb shift (15 px
  narrower track in that capture); 60 consecutive reloads did not reproduce it.
- P2-3 inherited landscape limit at 740×360 (height <500): CSS uses the narrow
  desktop layout while the mobile sheet starts at ≤700 px, so the sidebar is
  off-screen. The P2-2 capture of the same cell is pixel-identical except the
  status digits; it is not a P2-3 regression and remains a later landscape step.
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
python tests/test_suite.py        # 170 checks, headless Chromium via Playwright
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
