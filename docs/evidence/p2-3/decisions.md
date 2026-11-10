# P2-3 Task A4: decision table

Measured on the pre-change tree (`2547d1f`) with `tests/bench/bench.py`.
Raw data: `baseline.json`; method and hot-path inventory: `audit.md`.
Headless Chromium, software raster, viewport 1440x1000, seed `0x5EED1234`.
These are app-work numbers and a measurement floor, not a GPU or real-device
claim. Every preview number is the app's own preview pipeline at 1600x900 (the
1080p and 4K stills both clamp there); native samples are one forced-GC render
at 1920x1080 or 3840x2160.

## Baseline summary

| Measure | 1080p | 4K |
|---|---:|---:|
| Preview render median, Script (22 effects) | 197.7 ms | 163.1 ms |
| Preview render median, Dither (22 effects) | 335.6 ms | 386.4 ms |
| Preview render median, Effects Only (22 effects) | 63.9 ms | 90.0 ms |
| Slowest single effect, preview | 1727.1 ms (`oil`, Script) | 2469.4 ms (`oil`, Effects) |
| Slowest single effect, native sample | 3659.2 ms (`oil`, Script) | 13136.3 ms (`oil`, Effects) |
| Stack 1 / 3 / 6 / 12, Script preview | 162.8 / 226 / 319 / 763.9 ms | 167.3 / 222.8 / 302.8 / 646.9 ms |
| Stack 1 / 3 / 6 / 12, Dither preview | 324.1 / 384.3 / 436.3 / 950.4 ms | 329.9 / 383.9 / 454.3 / 859.3 ms |

| Other measure | Value |
|---|---:|
| First paint / FCP | 520 / 520 ms |
| DOMContentLoaded / load / app ready | 536.7 / 800.4 / 887.3 ms |
| Startup bytes / requests | 316,608 / 9 |
| Slider drag, worker on (rAF median / main-thread render) | 16.7 ms / 0.3 ms, 0 long tasks |
| Slider drag, worker off (rAF median / main-thread render) | 83.3 ms / 64.6 ms, 1000 long tasks in 5 windows |
| Video playback, 0 / 3 / 6 effects, 1080p and 4K | 16.7 ms per frame in all six cells |
| Video export, 1280x720, 1 s, 3 effects | 4.95 s per exported second, peak JS heap 33.1 MB |
| Idle CPU, 4K still + 6 effects, own rAF counter running | 3.02% of one core |
| JS heap growth over 200 preview renders | +53,352 bytes total (+266.8 B/render) |
| Source bytes / `dist/` bytes | 281,348 / 259,941 |

The 1000 sync long tasks and zero worker long tasks are the clearest signal in
the baseline: the worker path already moves the render off the main thread.
It must stay.

## Module decisions

| Module | Measured cost / evidence | Root cause | Decision | Expected gain | Risk |
|---|---|---|---|---|---|
| `effects.js` | `oil` 1658–2469 ms preview, 8788–13136 ms native; next slowest effect 639 ms preview | `fxOil` allocates a `vals` array and a `best` array for every quadrant of every pixel, then reduces with two array passes; `fxPixelSort` allocates a run array per run; `fxData`/`fxClone` allocate a full frame per effect | **OPTIMIZE IN PLACE** | Remove the per-pixel allocations in `fxOil` for a 2–4× win; reuse buffers in sort/VHS/glitch | Pixel parity is the contract; every change must match G20 exactly and keep the 4-in-5-window rule |
| `engine.js` | Dither median 335.6 / 386.4 ms vs Effects Only 63.9 / 90.0 ms | `nearestPaletteColor` re-parses the palette strings and allocates a regex match per glyph or per pixel; `applyAdjustments` can do three full-frame `getImageData`/`putImageData` round trips; `errorDiffusionDither` allocates a 5.76 MB (preview) to 33 MB (4K) `Float32Array` per render | **OPTIMIZE IN PLACE** | Parse the palette once per render; merge independent adjustment passes; reuse the diffusion buffer | Adjustment merges and float buffer reuse can change arithmetic order, so G20 is the hard stop |
| `app.js` | 4K preview render median is 163–386 ms while the same effects at 1080p are similar or slower; `__benchRender` shows a 4K source draw before every frame. Sync drag render 64.6 ms; every input serializes `renderOpts()`; full DOM rebuild on reset/undo | Full-size source is redrawn/downscaled to 1600x900 on every render; `JSON.stringify(renderOpts())` and `pushHistory()` serialize on the input path; `finishRenderUI()` recomputes output size 2–4×; `filterControls()` can unhide mode-hidden sections (B4) | **OPTIMIZE IN PLACE** | Cache the downscaled preview base; build the render key from mutable fields only; fix B4 with a regression test | Cache invalidation is the main risk; B4 is a correctness fix that needs its own test |
| `reorder.js` | Not on the render path; audit found a forced layout read/write/read per placeholder move, no baseline number | `movePlaceholder()` reads every card's `top`, mutates the placeholder, then reads every card again | **KEEP** | None claimed until a gesture benchmark shows a real cost; a speculative change would violate the measure-first rule | Touching the drag gesture risks G15/G17 parity for no measured user gain |
| `render-worker.js` | Worker drag: 16.7 ms rAF, 0.3 ms main-thread render, 0 long tasks; sync: 83.3 ms and 1000 long tasks | One job in flight, latest-wins; only per-job `OffscreenCanvas` allocation | **KEEP** | Reusing the canvas would save one allocation per completed frame, which the baseline does not show as a cost | A worker rewrite would put G19 and the fallback at risk for an unmeasured gain |
| `index.html` / `style.css` | FCP 520 ms, app ready 887.3 ms, 316,608 bytes, 9 requests; idle 3.02% with a measuring rAF loop; four keyframes, no always-on animation | Render-blocking Google Fonts stylesheet on a cross-origin host; local fonts are self-hosted; scripts are at the end of `<body>` | **KEEP** | Deferring the remote stylesheet is a network/product choice, not a proven app-work win | Removing the remote font changes typography fallback; not a parity-safe optimization |
| Video path | Playback 16.7 ms at 0/3/6 effects on 1080p and 4K; export 4.95 s per second at 1280x720 | Playback is already `requestVideoFrameCallback`/adaptive; export is fixed 24 fps, 20 s clamp and rendered at `computeOutputSize()` (B3), not native video size; one 40 MB constant covers video (B2) | **OPTIMIZE IN PLACE (Step 4)** | Native-size export removes the preview clamp; no playback change expected | Step 4 is a behavior change by owner decision; it needs its own RED/GREEN tests and ffprobe evidence |
| `tools/build.py` / `dist/` | `dist/` 259,941 bytes across 7 top-level files; build + dist smoke green | Comment strip and whitespace minifier; no measured runtime cost | **KEEP** | None claimed | Build heuristics must keep passing `node --check` and dist smoke |

## Rebuild verdict

**No module is a rebuild candidate.** The measured bottlenecks are localized
functions inside `effects.js`, `engine.js` and `app.js`; each can be changed in
place behind the golden hashes. The sizes of the files are not evidence of a
bottleneck, and a rewrite of `effects.js` or `engine.js` would add risk without a
measured module-level win. No owner question is needed because no rebuild is
proposed.

## Order of work for Step 5

1. `fxOil` allocation removal (largest single win, 8.8–13.1 s native today).
2. Palette parsing once per render (dither and Script palette mode).
3. Adjustment-pass merge and diffusion-buffer reuse.
4. Cached downscaled preview base for 4K sources.
5. Render-key serialization and B4 `filterControls()` correctness fix.

Every item is kept only with a paired median at least 10% faster in 4 of 5
windows (or a removed >50 ms long task), identical G20 hashes, 169+ tests green
and G1–G20 green. Anything else is reverted.
