# L0 — measure first (lag, softness, CPU, RAM, code size)

Status: **PASS** (measurement complete; G23 written and **RED** for the measured
causes). No app code changed in L0.

Base: `1e6f84d` (`L0` task file). Task: `docs/prompts/lag_performance_round.md`.
Evidence is in this folder: `code-runtime.json`, `playback-chromium.json`,
`playback-firefox.json`, `stages-runtime.json`, `sharp-runtime.json`,
`memory-runtime.json`, `compress-runtime.json`, `g23.json`, `g23-red.log`,
`g23-red-raw.log`, `breakit.json`, `breakit.log`.

Machine: Linux, 4 cores, 7.8 GB RAM, no display, headless software raster.
Chromium (Playwright) and Firefox 1555. Node 26.13.1, Python 3.14.9, ffmpeg
9.0.2. Every number below is a real browser run on this machine, not an
estimate. The owner's real GPU is **HUMAN-CHECK**.

Fixtures: 1280×720 and 1920×1080, 20 s, 30 fps VP9 (`testsrc2` + `mandelbrot`
overlay), 1920×1080 PNG still. All frames shown during playback are rendered at
the full preview size (`previewSize(full)`); nothing lowers resolution.

## 1. Code map — is "the code is long" the cause?

Source (unminified), measured with `tools/l0_measure.py --part code`:

| File | Lines | Bytes | gzip | brotli | minified |
|---|---:|---:|---:|---:|---:|
| app.js | 3796 | 142,500 | 35,726 | 29,294 | 130,207 |
| engine.js | 835 | 36,884 | 8,298 | 7,276 | 33,790 |
| effects.js | 814 | 30,677 | 8,020 | 7,156 | 28,076 |
| reorder.js | 289 | 9,972 | 2,515 | 2,182 | 8,376 |
| render-worker.js | 71 | 2,662 | 1,093 | 930 | 2,514 |
| style.css | 1480 | 47,715 | 9,200 | 8,012 | 43,668 |
| index.html | 525 | 33,132 | 5,564 | 4,637 | 26,353 |
| vendor/mp4-muxer.js | 1883 | 69,375 | 14,597 | 12,564 | 58,280 |
| vendor/webm-muxer.js | 1453 | 65,311 | 11,995 | 10,324 | 58,244 |
| **total** | **11,146** | **438,228** | **94,774** | **75,491** | **—** |

Largest functions: `setupEventListeners` 514 lines / 23,635 B (runs once),
`renderEffectsList` 216 / 8,517 (runs on a panel change), `initEls` 138 /
5,837 (once), `exportVideo` 152 / 5,756 (export only), `loadFile` 123 / 4,605
(load only), `render` 100 / 3,739 and `renderScript` 67 / 2,583 (per frame).
`effects.js` has 47 functions, the largest `fxConvolve` 62 lines; the per-frame
hot ones are tiny (`autoLevels` 27 lines, `fxDuotone` 13, `fxPosterize` 20,
`fxOil` 46).

Parse/compile at load (CDP, Chromium):

| Script | Main-thread compile |
|---|---:|
| app.js | 0.08 ms |
| engine.js | 1.33 ms |
| effects.js | 1.29 ms |
| reorder.js | 0.04 ms |
| render-worker.js | 0.38 ms |
| index.html inline | 0.26 ms |
| **total** | **3.38 ms** |

Background compile 20.18 ms; `ScriptDuration` 0.054 s and `TaskDuration`
0.59 s for the whole load.

**Conclusion:** code length is not the lag cause. 142 KB of app.js compiles in
0.08 ms on the main thread; the largest function runs once. The per-frame cost
is pixel work (section 3), not parsing, not source size. Shrinking code helps
transfer and maintenance (L2), not playback smoothness.

## 2. Playback profile (20 s windows, real rVFC loop)

Chromium (`playback-chromium.json`, rerun with CDP main-thread metrics):

| Case | renders/s | p50 | p95 | interval p50 | long tasks >50 ms | pause med | seek med | CPU s / 20 s | task / script ms | layout / style ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 720p none | 14.55 | 38.4 | 51.1 | 66.8 | 29 | 10.5 | 372 | 21.5 | 14,099 / 11,805 | 19.4 / 5.4 |
| 720p light2 | 10.65 | 66.1 | 91.6 | 84.2 | 213 | 8.8 | 420 | 24.1 | 16,721 / 14,979 | 19.4 / 5.8 |
| 720p heavy7 | 1.05 | 943.1 | 970.5 | 968.1 | 21 | 12.8 | 1,307 | 24.6 | 19,976 / 19,754 | 5.5 / 1.7 |
| 1080p none | 10.90 | 65.0 | 75.9 | 83.6 | 218 | 8.2 | 718 | 28.8 | 16,644 / 14,712 | 18.4 / 5.3 |
| 1080p light2 | 7.25 | 112.3 | 124.0 | 133.4 | 145 | 116.0 | 731 | 29.3 | 17,889 / 16,437 | 24.8 / 6.7 |
| 1080p heavy7 | 0.65 | 1,551.4 | 1,579.2 | 1,565.9 | 13 | 1,415.9 | 1,962 | 29.4 | 20,431 / 20,171 | 4.7 / 3.4 |

Firefox (`playback-firefox.json`; no `performance.memory`, no long-task API):

| Case | renders/s | p50 | p95 | interval p50 | pause med | seek med | CPU s / 20 s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 720p none | 18.91 | 52 | 61 | 53 | 141 | 218 | 25.7 |
| 720p light2 | 1.26* | 161 | 278 | 164 | 930 | 791 | 23.7 |
| 720p heavy7 | 0.45 | 2,420 | 3,346 | 2,425 | 5,547 | 2,313 | 20.1 |
| 1080p none | 8.81 | 107 | 151 | 108 | 285 | 434 | 25.6 |
| 1080p light2 | 5.43 | 162 | 361 | 166 | 472 | 363 | 24.7 |
| 1080p heavy7 | 0.40 | 3,182 | 3,422 | 3,193 | 8,893 | 3,942 | 24.7 |

\* One Firefox 720p-light2 window hit a 63.3 s wall clock with the page
starved (80 renders, CPU only 0.37 core): the driver stopped presenting
frames. It is reported raw, not hidden; the other Firefox windows ran 20 s.
Firefox runs have no long-task observer, so CPU time and render intervals are
the evidence there.

Facts that matter:

- The video element presents about 11–19 fps in this headless software raster
  even with **zero effects**, so an absolute "no interval above 50 ms" rule
  measures the machine, not the app. This is why G23's pacing bounds are paired
  (section 6).
- The light stack adds 28–47 ms of render time (Chromium 720p 38.4 → 66.1;
  Firefox 720p 52 → 161) and drops Chromium from 14.6 to 10.7 fps and Firefox
  from 18.9 to ~7–12 fps. Pause latency follows the same trend in Firefox
  (141 → 930 ms in the starved window; 400–548 ms in G23).
- Heavy stacks are decode-independent: `fxOil` alone is 627 ms at 720p and
  959 ms at 1080p; the page still advances video, it just shows few frames.
- CPU sits at 1.0–1.5 cores while playing. Layout and style work is 19–25 ms
  per 20 s (≈1 ms/s) — CSS is **not** a cause. Long tasks in Chromium are one
  per render (the whole synchronous `render()`), not separate work.

## 3. Per-frame breakdown (`stages-runtime.json`)

One frame, Chromium, paused at 2 s, probe of 5 renders (ms per frame):

| Case | render | prepareBase | effects | renderScript | autoLevels (inside script) | getImageData total (n) | putImageData | drawImage | fillText |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 720p none | 81.4 | 1.9 | 0.0 | 79.3 | 50.8* | 19.4 (2) | 1.4 | 1.9 | 6.5 (2240) |
| 720p light2 | 88.7 | 51.3 | 58.1 | 37.1 | 18.3 | 30.2 (4) | 4.0 | 2.2 | 4.6 (2240) |
| 720p heavy7 | 914.3 | 878.2 | 855.7 | 35.8 | 15.9 | 51.3 (9) | 14.2 | 24.0 | 4.8 (2240) |
| 1080p none | 59.7 | 11.0 | 0.0 | 48.5 | 24.4 | 13.3 (2) | 1.4 | 10.8 | 5.2 (2240) |
| 1080p light2 | 97.3 | 51.9 | 57.4 | 45.1 | 22.9 | 29.5 (4) | 5.8 | 8.7 | 4.0 (2240) |
| 1080p heavy7 | 1,334.5 | 1,282.1 | 1,255.1 | 52.1 | 23.1 | 60.8 (9) | 15.3 | 40.8 | 5.8 (2240) |

\* First probe includes JIT warm-up; the same stage measures 18–24 ms on later
cases. Effect timings at 720p light: `fxPosterize` 14.7, `fxDuotone` 34.4;
1080p: 16.7 and 25.9. Heavy: `fxOil` 640/959, `fxSketch` 59/68, `fxEmboss`
45/70, `fxSharpen` 46/69, `fxBlur` 32/43, `fxEdges` 35/42.

What the split proves:

- `autoLevels` does one full-canvas `getImageData`, a 20 k-sample histogram and
  a full-canvas `putImageData` **inside** `renderScript`, which then reads the
  same canvas again. That is two readbacks and a write of the same frame.
- Every CPU effect clones the canvas, reads it, writes it back. The light
  two-effect stack therefore performs **4 full reads and 3 full writes** per
  frame; the no-effect control already performs 2 reads and 1 write.
- `fillText` (2,240 calls) is only 4–6.5 ms, and status/DOM work is ≤0.1 ms.
  Glyph drawing is not the bottleneck; pixel transport and per-pixel math are.

## 4. Sharpness (`sharp-runtime.json`, `g23-red.log`)

The canvas CSS size is derived from the capped backing:
`scale = zoom × pv.w / full.w`, so `cssWidth = pv.w² × zoom / full.w`.
The backing is capped at `PREVIEW_MAX = 1600` px and
`MAX_PREVIEW_PIXELS = 1600×1600 = 2.56 MP` (`app.js`).

| Source, DPR, zoom | Backing | CSS | Need = min(source, CSS×DPR) | Covers |
|---|---|---|---|---:|
| 1080p, DPR1, 0.79 | 1600×900 | 1053×593 | 1053×593 | yes |
| 1080p, DPR1, 1.00 | 1600×900 | 1333×750 | 1333×750 | yes |
| 1080p, DPR1, 1.12 | 1600×900 | 1493×840 | 1493×840 | yes |
| 1080p, DPR1, 2.00 | 1600×900 | 2667×1500 | **1920×1080** | **no** (0.833×) |
| 1080p, DPR2, 0.79 | 1600×900 | 1053×593 | **1920×1080** | **no** |
| 1080p, DPR2, 1.00 | 1600×900 | 1333×750 | **1920×1080** | **no** |
| 1080p, DPR2, 1.12 | 1600×900 | 1493×840 | **1920×1080** | **no** |
| 1080p, DPR2, 2.00 | 1600×900 | 2667×1500 | **1920×1080** | **no** |
| 720p, DPR2, 2.00 | 1280×720 | 2560×1440 | 1280×720 (native) | yes |
| 4K, DPR2, 1.00* | 1600×900 | 667×375 | 1333×750 | yes |

\* 4K is not in the G23 matrix; its CSS size is small because the cap shrinks
the displayed canvas (`1600²/3840 = 667`), so at default zoom the backing
covers the device pixels. At 4K zoom 2 the need is 2667 and the 1600 backing
would be soft again. This limit is reported for L1 as **HUMAN-CHECK / cap
limit**, not silently "fixed".

Cause: the backing is chosen only from the source size; it ignores the physical
display size (`CSS × devicePixelRatio`). A 1080p source at DPR2 always needs
1920 device pixels, but 1600 is the hard cap. CSS smoothing (`imageRendering:
auto` below 112 %, `pixelated` above) cannot add detail that was never
rendered — the softness is upstream of CSS.

## 5. Memory and leaks (`memory-runtime.json`)

| Checkpoint | JS heap | Object URLs (created/revoked/live) | ImageBitmaps (created/closed) | Notes |
|---|---:|---|---:|---|
| Start (image loaded) | 2.50 MB | 1 / 0 / 1 | 2 / 0 | 1 DOM canvas |
| After 20 load/clear cycles (image/video) | 2.74 MB | 21 / 20 / 1 | 22 / 10 | 0 DOM videos, 1 canvas |
| After 20 WebM exports (2 s, 320×180) | 3.11 MB | 42 / 40 / 2 | 22 / 11 | 1,200 `VideoFrame`s made, all closed by source |
| After 60 undo steps | 3.28 MB | 43 / 42 / 1 | — | 60 snapshots = 124,293 JSON bytes / 146,074 heap bytes |
| After undo | 3.28 MB | — | — | 1 undo / 59 redo = 2,073 bytes |
| 5 min idle playback (sample every 5 s) | **35.1 MB constant** | 44 / 43 / 1 | — | 3,151 renders, 60/60 samples identical |

- No heap growth in 5 minutes: 35.1 MB at 5 s and at 300 s (Chrome reports
  0.1 MB granularity). Video time cycles because the 20 s clip loops.
- Every load revokes the previous object URL; one live URL is the current
  source. The transient `live=2` after exports is the download blob, revoked on
  the next load. ImageBitmap 22 created / 10 closed is ownership transfer to
  the worker plus the current preview, not a leak (the worker owns transferred
  bitmaps).
- The harness counted `VideoFrame` creation only; `app.js` calls `frame.close()`
  immediately after every `encoder.encode(...)` in both video export paths, so
  1,200 created = 1,200 closed. This is a harness gap, not an app leak.
- History is capped in practice (60 pushes stayed 124 KB). Nothing here
  explains "heavy on RAM": the resident cost is the video decoder and canvas
  buffers, not the JS heap.

## 6. G23 — permanent RED check for the two owner complaints

`tests/gate/perf_check.py`, wired into `tests/gate/run_gate.py` after G22 and
documented in `docs/GATE.md`. Budgets were written before any fix.

Smoothness is paired: each light window is compared with the zero-effect
control measured immediately before it in the same session. Sharpness: backing
must be ≥ `min(source native, CSS display × devicePixelRatio)` in 8 cells
(DPR 1/2 × zoom 79/100/112/200 %).

Final RED (`g23-red.log`):

```
FAIL [smooth] chromium light stack keeps playback fluid: p50=69.3ms(control 41.4 delta 27.9 budget 20.0) ... fps=10.2(control 15.0 ratio 0.7 budget 0.6) interval p50=102.9ms(control 66.8 extra 36.1 budget 50.0)
FAIL [smooth] firefox light stack keeps input responsive: pause median=181.3ms(budget 150.0) max=270.1ms(budget 300.0)
FAIL [sharp] DPR 1 zoom 2 covers display pixels: backing=[1600, 900] ... need=[1920, 1080]
FAIL [sharp] DPR 2 zoom 0.79 / 1 / 1.12 / 2 covers display pixels: backing=[1600, 900] ... need=[1920, 1080]
16 checks, 7 failure(s) [G23]
```

Chromium input latency passes today (median 11.9 ms, max 83.4 ms) because its
event loop drains between 60 ms renders; Firefox fails (181 / 270 ms). The
Firefox fluid row passes today's paired delta (28 ms against a 30 ms budget)
but that is marginal and its pause row is red; the budget is unchanged.

Two budgets were corrected **before any fix**, using the measured-machine rule
(recorded in `docs/GATE.md`): (1) an absolute "intervals >50 ms ≤ 25 %" rule
failed on the zero-effect control itself (Chromium 15.0 fps, interval p50 66.8
ms; Firefox 16.2 fps, 53.0 ms); (2) an absolute light p50 budget moved with
machine load (control 37.6 ms in one run, 61.5 ms in the next). The final
bounds are per-pair deltas. No existing gate threshold was changed.

## 7. Compression candidates (not implemented)

| Candidate | Measurement | Verdict |
|---|---|---|
| Worker frame transfer | `ImageBitmap` is posted with a transfer list (`postMessage({source, bitmap}, [bitmap])`), already zero-copy; opts payload is 2,552 B JSON, 22 effects, 36 keys | **REJECTED** — compression adds CPU for a 2.5 KB message |
| Worker → main result | one `ImageBitmap` or `ImageData` transfer; no repeated bulk payload measured | **REJECTED** for L0; revisit if L1 moves video into the worker |
| Shipped JS/CSS | source 438 KB → 94.8 KB gzip / 75.5 KB brotli; dist 619 KB → 185.2 KB gzip / 138.1 KB brotli (dist also carries both `.js` and `.mjs` muxer copies plus fonts) | candidate for L2: drop duplicate muxer format, verify build |
| Fonts | WOFF2 already compressed (31.3 KB + 31.4 KB); gzip/brotli add ~0 | **REJECTED** |
| Undo history | 60 snapshots = 124 KB; compression would save <0.1 % of a 35 MB heap | **REJECTED** |
| Cached frames | canvas backing stores are not serialisable without a CPU round trip; lossless codecs would cost more than they save | **REJECTED** |

The prompt's expected result — same-process transfers are faster uncompressed
— matches the measurements: the worker payload is already zero-copy and tiny.

## 8. Ranked causes (measurement behind each)

1. **Per-frame full-canvas readback/write pattern** — light stack does 4
   `getImageData` (30.2 ms) + 3 `putImageData` (4.0 ms) and 4 `drawImage`
   copies per 720p frame. Root cause: each effect clones/reads/writes, and
   `autoLevels` reads and writes the frame inside `renderScript` before
   `renderScript` reads it again.
2. **`autoLevels` on every frame** — 18–50 ms per frame inside the 37–79 ms
   `renderScript`, doing a histogram sample, a full 3-channel scale loop and a
   `putImageData` that the next line reads back.
3. **CPU effect passes** — `fxPosterize` 14.7–16.8 ms, `fxDuotone` 25.9–34.4
   ms at 720p/1080p (clone + read + per-pixel loop + write each).
4. **Synchronous main-thread render blocks input** — Firefox pause 181–930 ms,
   seek 363–791 ms while a 112–161 ms render runs; layout/style are only 1 ms/s,
   so the block is the render itself, not CSS.
5. **Preview cap ignores physical display size** — 1600 px / 2.56 MP gives
   0.833× of the needed 1920 device pixels for a 1080p source at DPR2 or at
   DPR1 zoom 200 %.
6. **Worker cannot take video** — `workerEligible()` requires
   `sourceType === "image"`, so the one available offload path is unused during
   playback (not a cause by itself, but it bounds the options; evaluate in L1).
7. **Heavy effects are inherently long** — `fxOil` 627–959 ms; no scheduling
   change can make a 1 s frame smooth. Playback degrades by dropping frames
   (current behaviour, allowed by the V1 quality rule).
8. **Not causes (measured and rejected):** code length/parse (3.38 ms at load),
   layout/style per frame (1 ms/s), status/DOM updates (≤0.1 ms), mouse/pointer
   listeners (Pause click is 8–12 ms in Chromium), and memory (heap flat at
   35.1 MB for 5 min).

## 9. Break-it list (10 probes, `breakit.log` / `breakit.json`)

| # | Way the measurement could lie | Result (pre-fix) |
|---|---|---|
| 1 | Fixture is silently regenerated between runs | PASS — mtimes unchanged on the second call |
| 2 | Sharpness computed from CSS, not the real backing | PASS — DPR1 zoom 1.12 measured covers (1600 ≥ 1493) |
| 3 | Sharpness at DPR1 zoom 2 is claimed sharp | FAIL (expected RED) — 1600 < 1920 |
| 4 | Render wrapper is overwritten by the app's function declaration | PASS after fix — 20 renders / 20 rVFC counted; the original init-script version was falsified and replaced (see below) |
| 5 | Pause probe leaves the video paused | PASS — 3 samples, playback resumed each time |
| 6 | DPR is read as 1 under a DPR2 context | PASS — `dpr=2`; sharpness FAIL is real (1600 < 1920) |
| 7 | Upscaling is applied to a 720p source above native | PASS — backing stays 1280×720 |
| 8 | Light theme changes the measurement path | PASS — 24 renders counted, theme `light`, no errors |
| 9 | Worker-disabled URL breaks rendering | PASS — image hash non-zero, no page errors |
| 10 | Any probe leaks a page error | PASS — none in Chromium/DPR2/Firefox-free probes |

The first G23 version installed the wrapper with `add_init_script`; the app's
global `function render` declaration then replaced it, so `renders` stayed 0.
That was found by probe 4 before the final RED, fixed by instrumenting after
load, and the raw log is kept as `g23-red-raw.log`. The absolute pacing budget
was falsified by the control the same way (section 6).

## 10. Conclusions for L1

- Fix order by measured impact: (1) fuse `autoLevels` into the read that
  `renderScript` already performs; (2) fuse consecutive pixel effects into one
  read/modify/write; (3) make the backing follow `CSS × DPR` up to a 1920 px
  physical cap while keeping the existing 1600 px preview size for layout,
  golden hashes and default DPR1 (only currently-soft cells grow); (4) then
  re-measure scheduling and input latency, and only keep worker/offload work if
  it measures better in both browsers.
- The pixel-parity safety net is exact: G19/G20 (200 cases), G21, and G22
  parity must keep identical hashes. The golden cases render through
  `prepareBase` + `renderToContext` with `previewSize(full)`, so the L1 backing
  change must not alter that path.
- Expected L1 target from these numbers: remove ~10 ms of redundant readback
  from every frame and ~10–13 ms from the light effect chain, taking the
  paired light delta from 28–29 ms to ≤20 ms (Chromium) and Firefox input
  under 150 ms; the sharpness cells need 1920 backing only at DPR2 and at
  zoom 200 % DPR1.
