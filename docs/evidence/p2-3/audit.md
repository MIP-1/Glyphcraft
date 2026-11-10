# P2-3 Task A1 audit

Branch `p2-3-work` at `2547d1f` (before any P2-3 code change). Every source file
was read in full: `index.html`, `style.css`, `engine.js`, `effects.js`,
`reorder.js`, `app.js`, `render-worker.js`, `tools/build.py`,
`tools/dist_smoke.py`, `tests/test_suite.py`, `tests/test_contrast.py` and all
files under `tests/gate/`.

Measured numbers in this file are either static (bytes, line counts, counts of
calls) or come from the A2 harness in `tests/bench/`; see `baseline.json`.
Headless software raster is a measurement floor, not a GPU claim.

## 1. Size and shape

| File | Lines | Bytes | Responsibility |
|---|---:|---:|---|
| `index.html` | 503 | 31,750 | Static shell, 22 effect cards container, menus, sheet, 4 script tags at the end |
| `style.css` | 1,463 | 46,878 | Tokens, desktop panel, mobile sheet, menus, picker, 4 keyframes |
| `engine.js` | 812 | 35,896 | Render pipeline: base draw, adjustments, script glyphs, dither kernels, palettes, output size, export encoders |
| `effects.js` | 801 | 30,376 | 22 effects, canvas pool, per-stage cache, neutral-stage skip, auto levels |
| `reorder.js` | 289 | 9,972 | Pointer/touch/keyboard effect reorder, ghost/placeholder, auto-scroll |
| `app.js` | 3,296 | 123,814 | State, DOM wiring, render scheduling, worker client, video loop/export, presets, history, mobile sheet |
| `render-worker.js` | 71 | 2,662 | Worker job, source bitmap, font registration, `OffscreenCanvas` result |
| `tools/build.py` | 437 | 13,243 | Comment strip + minifier for `dist/`, `node --check` gate |
| `tools/dist_smoke.py` | 97 | 3,531 | Source vs `dist/` canvas hash smoke |
| `tests/` | 8,786 | 347,445 | 169-check suite plus G1–G19 gate helpers |

`dist/` after `npm run build`: 340 KB total, of which JS 184,506 bytes,
CSS 42,844 bytes, plus two woff2 fonts and the OFL text. The build log reports
12 output paths. Source JS+CSS+HTML is 270,686 bytes.

## 2. Render pipeline (the only hot path that matters)

`app.js:render()` (`app.js:748-845`) is the single entry point:

1. `computeOutputSize()` maps the source to the export size.
2. `previewSize()` (`app.js:595-602`) clamps the preview to 1600 px longest side
   and 2.56 MP (`app.js:186-187`). A 1080p and a 4K still therefore both render
   at **1600×900**; the 4K source only costs more in `drawImage` decode/sample.
3. `renderOpts()` (`app.js:587-597`) builds a fresh object, including
   `ramp.chars` and `palette`.
4. `JSON.stringify(opts)` (`app.js:761`) runs on every interactive frame.
5. `prepareBase()` (`engine.js:332-340`): base draw, `applyAdjustments()`, then
   `applyEffects()`.
6. `renderToContext()` (`app.js:705-709`): script glyph pass or dither pass, or
   a plain copy in Effects Only mode.
7. Frame cache `state.renderCache`, stage cache in `effects.js`, and the worker
   path (`postWorkerRender`, `app.js:935+`) can skip work.

The worker path is only entered for rAF-driven still previews with ≥6 enabled
effects, ≥900,000 preview pixels, fonts ready, no compare/original/cache-off/
video-export (`app.js:930-945`). Everything else is synchronous.

## 3. Per-file findings

### index.html

- Four local scripts at lines 498–501, no `defer`; they are at the end of
  `<body>`, so parsing is not blocked, but `app.js` runs `init()` on
  `DOMContentLoaded` (`app.js:3292-3296`).
- `index.html:19-21` adds two preconnects and a **render-blocking** Google Fonts
  stylesheet before `style.css`. FCP is gated by that cross-origin CSS; the
  measured startup section records first paint at 464–720 ms with no synthetic
  delay. The local fallback stack is complete, so this is startup cost, not a
  correctness risk.
- `index.html:125` hard-codes `data-snap="half"` on the panel. It is cleared
  only by `updateMobileViewport()` on a resize/`visualViewport` event
  (`app.js:2562-2570`), which is the race documented in the P2-2 closeout.
- The 22 effect cards are **not** in the HTML; `renderEffectsList()` builds them
  at runtime (`app.js:1913-2128`). Static DOM is ~295 elements, so the initial
  DOM is small; the cards are the growth point (roughly 22 × 6–20 nodes).
- The output size controls stay in the DOM and are made inert for video in Step
  4; nothing here needs a structural change.

### style.css

- Token discipline is good: colours come from `--gc-*` variables and the gate's
  G1 lint enforces it.
- Four keyframes only: `spin` (loading spinner, line 514), `toast-in/out`
  (line 1219–1223), `fade-in` (line 1249). No always-on animation; idle CPU is
  therefore mostly zero.
- Mobile sheet uses `transition: height 0.2s ease` (`style.css:1388`). The drag
  handler sets `transition: none` on pointerdown (`app.js:2603`) and restores it
  on pointerup (`app.js:2629`), so the transition is not on the drag path.
- `.preset-phone-extra` animates `grid-template-rows` (`style.css:1195`);
  expanding 44 phone presets forces a layout once, not per frame.
- `backdrop-filter`, large `filter: blur`, and shadows exist only on a few
  overlays; none is on the canvas or effect path. 19 declarations mention
  fixed/filter/shadow; none is a full-page blur.

### engine.js

- `nearestPaletteColor()` (`engine.js:135-153`) rebuilds the palette parser on
  **every call** and calls it per glyph (`engine.js:318`) or per pixel
  (`engine.js:633`). The regex parse of `rgb(...)`/hex strings is in the inner
  loop: for a 1600×900 dither that is up to 1.44M calls × palette length.
- `applyAdjustments()` (`engine.js:155-237`) can perform three separate
  full-frame `getImageData`/`putImageData` passes (highlights/shadows/sharpen,
  invert, sepia) after an optional `ctx.filter` self-draw. Each pass copies the
  full preview. The passes are independent and can be merged into one loop.
- `renderScript()` (`engine.js:303-326`) draws one glyph per cell with a
  per-glyph `fillStyle` string; spectrum mode allocates `rgb(...)` strings.
- `renderDither()` (`engine.js:584-650`) allocates a new `ImageData` for output
  and the kernel functions allocate their own work buffers.
- `errorDiffusionDither()` (`engine.js:655-657`) allocates
  `new Float32Array(data.length)` per call. At 1600×900 that is 5.76 MB per
  render; at 4K export it is 33 MB.
- `gcScratch()` / `gcScratchContext()` (`engine.js:93-118`) correctly reuse
  scratch canvases keyed `base`/`stage`, and `willReadFrequently` is set on
  every read-heavy context (`engine.js:54,252,268,350,403,589`).
- `prepareBase()` only returns the processed canvas; it does not expose timing
  per stage, which is why A2 samples the whole call.
- Export helpers (`canvasToBlob`, `canvasToSvg`, `canvasToTxt`,
  `computeOutputSize`) are single-purpose and not in the interactive path.

### effects.js

- 22 effects; ids and parameters (`effects.js:2-45`) match `EFFECTS` in the
  tests. Five are random and uncacheable: `glitch`, `vhs`, `pixelsort`, `grain`,
  `matrix` (`effects.js:669`).
- Stage cache: `stageKey()` (`effects.js:684-690`) builds a string from the
  previous key plus every sorted parameter, and `applyEffects()`
  (`effects.js:717-772`) reuses a cached canvas when the key hits. This is the
  main reason a slider edit only re-runs the changed suffix.
- Neutral-stage skip (`effects.js:698-705`) avoids copying for amount 0 on five
  effects.
- Canvas pool: capped at 10 canvases / 4 per size (`effects.js:51-53`), armed
  only when the stage cache is not used (`effects.js:723`). Good reuse, but
  `fxPoolClear()` sets `width=0` and drops all canvases when the preview size
  changes.
- Hot effects:
  - `fxHalftone` (`effects.js:151-177`): per-cell `arc`/`fill`; output is
    vector-ish drawing, not a pixel loop.
  - `fxVHS` (`effects.js:233-249`): `getImageData` + `Math.random()` per pixel
    and a full `putImageData`.
  - `fxGlitch` (`effects.js:218-222`) and `fxMatrix` (`effects.js:619-626`)
    call `Math.random()` per slice/character.
  - `fxOil` (Kuwahara) and `fxPixelsort` sort pixel runs; both are expected to
    dominate the per-effect table.
  - `fxLumaPlane` (`effects.js:134-141`) keeps a module-global
    `Float64Array` sized to the pixel count. At 1600×900 that is 11.5 MB; at 4K
    it is 66 MB, retained for the page lifetime. `Float32Array` would halve it.
  - `fxData()` (`effects.js:147-149`) always allocates a fresh `ImageData`;
    most effects then allocate a second canvas through `fxClone`.
- `autoLevels()` (`effects.js:774-800`) does a histogram pass with a stride
  sample and a full pixel remap; it is enabled by default and runs inside
  `prepareBase` for both preview and export.
- Output is pixel-identical for deterministic effects; the stage cache and pool
  must not change that (golden hashes prove it after every change).

### reorder.js

- `items()` (`reorder.js:22-24`) calls `querySelectorAll` and copies the list.
  It is called from `indexOf`, `activate`, `movePlaceholder`, `targetIndex` and
  cleanup.
- `activate()` (`reorder.js:114-155`) reads `getBoundingClientRect()` for the
  item plus every other item once, and `movePlaceholder()` (`reorder.js:173-193`)
  reads every item's `top`, mutates the placeholder, then reads every item's
  `top` again to compute transforms. That is a forced layout read/write/read
  sequence on every placeholder move (not every pointermove — `updateDrag`
  only calls `movePlaceholder` when the target slot changes).
- `updateDrag()` (`reorder.js:157-170`) writes ghost `left/top` and reads the
  scroller rect per pointermove.
- Auto-scroll (`reorder.js:235-255`) writes `scrollTop` and immediately calls
  `updateDrag()`, which reads layout again.
- Verdict: measurable only on a long reorder with 22 cards; it is not a render
  cost. Candidate for OPTIMIZE IN PLACE, not a rebuild.

### app.js

- `state` is a large mutable object (`app.js:120-185`). `pushHistory()` takes a
  full `JSON.stringify(state.opts)` on **every** input/change (`app.js:535-548`).
  History keeps 60 snapshots; at ~5–15 KB per snapshot this is bounded but is
  repeated allocation during a slider drag every 600 ms grouping window.
- `render()` re-serializes `renderOpts()` every frame (`app.js:761`), including
  `ramp.chars` (up to hundreds of characters) and the full effect array. The
  state key only needs the mutable fields.
- `outputMeta()` / `displayScale()` / `applyZoomUI()` each call
  `computeOutputSize()` again (`app.js:1159-1203`). `render()` calls
  `finishRenderUI()` which calls `applyZoomUI()`; that is 2–4 recomputations of
  the same preset math per frame. Cheap compared with pixels, but repeated.
- `finishRenderUI()` (`app.js:1063-1070`) writes `applyTransform`,
  `applyZoomUI`, `updateCompareUI` and `updateStatus` on every completed
  render. `updateStatus()` rewrites three `textContent` values and a class even
  when the size/zoom did not change (`app.js:1205-1224`). During a worker drag
  this runs once per drawn frame, not per input.
- `renderEffectsList()` (`app.js:1913-2128`) rebuilds **all** cards with
  `innerHTML=""` and re-creates every listener. It is called by
  `syncUIFromState()`, which is called by preset load, reset, undo/redo and
  restore. Not on the slider path, but it is the largest DOM allocation in the
  app (22 cards × params).
- `filterControls()` (`app.js:2330-2342`) walks every section and every
  control, reads `textContent`, and toggles `hidden`/`style.display` on each
  keystroke. It also sets `sec.style.display=""` for matching sections, which
  can **unhide a section that the current mode hides** (see bug B4).
- `syncUIFromState()` (`app.js:1856-1903`) writes ~30 controls and rebuilds the
  effect list; it is called on every preset/reset/undo, not per frame.
- `loadFile()` (`app.js:1399-1491`) uses an object URL, never a full-file read.
  The 40 MB `MAX_FILE_BYTES` (`app.js:1381`) is applied to video as well as
  images (`app.js:1410`); Step 4 must split it.
- Video playback: `startVideoLoop()` (`app.js:1554-1582`) uses
  `requestVideoFrameCallback` when available and renders on the adaptive
  preview scale; `PLAYBACK_MIN_INTERVAL` and `adaptPlaybackScale()` guard frame
  cost. No idle rAF when paused.
- `exportVideo()` (`app.js:1706-1765`): 24 fps fixed (`app.js:1715`), duration
  clamped to 20 s (`app.js:1716`), output canvas uses `full` from
  `computeOutputSize()` (`app.js:1665`, `app.js:1710`), so it preview-clamps
  rather than exporting native video dimensions. It seeks the video to
  `i / fps` and waits for `seeked` or 120 ms, then renders one frame. Chunks are
  kept in an in-memory array until `MediaRecorder` stops (`app.js:1727-1740`).
- Mobile sheet: `onSheetPointerMove()` (`app.js:2608-2621`) computes snap
  heights (several `getBoundingClientRect` calls) on every pointermove and
  writes `panel.style.height`; layout is forced by the rect reads before the
  write. `onSheetPointerUp()` settles to a snap.
- `syncSheetStatus()` (`app.js:2474-2485`) moves the status bar between the
  sheet slot and the menubar on every call; it early-returns if already in the
  right parent.
- Listeners: `window` pointermove/up are always attached (`app.js:2760-2762`)
  but handlers early-return when not dragging. `filterControls` is attached to
  the search input only. No listener leak was found: menus/popovers add
  listeners once at init; the compare drag adds/removes its own listeners per
  gesture (`app.js:3203-3229`).

### render-worker.js

- One source bitmap kept in the worker; one job in flight with latest-wins
  pending on the main thread. Fonts are registered once (`render-worker.js:13-22`).
- `workerRender()` allocates a new `OffscreenCanvas` and context for **every
  job** (`render-worker.js:33-35`) and transfers the bitmap out. Reuse is
  possible (a scratch canvas per size), but the worker job rate is at most one
  in flight, so the allocation is once per completed frame, not per input.
- `prepareBase(..., null)` disables the stage cache in the worker; the worker
  therefore always runs the full effect chain. It shares `effects.js`, so the
  canvas pool is per-worker and capped.
- Errors are posted back with stack text; `onWorkerError()` falls back to the
  sync path (`app.js:875-903`).

### tools/build.py

- Python-only comment stripper and whitespace minifier. It preserves ASI
  newlines, literals and regexes; `node --check` runs on stripped sources.
- `dist/` is generated from the same sources; `render-worker.js` chooses
  `*.min.js` by its own URL (`render-worker.js:1-5`), so the worker loads the
  minified engine/effects in `dist/`.
- Risk: the minifier's regex/ASI heuristics are the only thing protecting
  semantics. `dist_smoke.py` compares a canvas hash on one effect stack; the new
  golden check (G20) will make that safety net much wider.

### tools/dist_smoke.py

- Loads source and `dist/`, waits for load/fonts, applies four deterministic
  effects, and compares a 32-bit FNV hash plus canvas size. It fails on page or
  console errors.
- It does not cover script/dither modes, random effects, video or export. G20
  covers the first two; video/export are covered by Step 4 checks.

### tests

- `tests/test_suite.py` (1,153 lines) is the 169-check suite. It covers empty
  state, load, all 22 effects in 3 modes, parameter sync/clamp/step, reorder,
  compare, history, presets, exports, video load, zoom, menus, mobile 360,
  contrast and error-free reload. It asserts `22 effects listed` and the 40 MB
  message (`tests/test_suite.py:159`, `tests/test_suite.py:1039-1046`).
- `tests/test_contrast.py` audits both themes at 360 and 1280 with WCAG ratios.
- `tests/gate/run_gate.py` (2,762 lines) defines G1–G19: token lint, theme
  parity, screenshots, frame timings, existing tests, no Arabic, View menu,
  top-bar geometry, steppers, effects, compare, load, video, mobile layout,
  gestures, touch targets, desktop baseline, menu reachability, worker.
  Next free number is **G20**.
- `compare_check.py` is the model for A2: in-page gesture, 60-frame warm-up,
  forced GC through CDP, settle, five paired windows, median/p95, and a
  control gesture with nothing listening.
- `load_check.py`, `video_check.py`, `effects_sweep.py`, `effects_ui.py`,
  `p2_1_breakit.py`, `p2_2_breakit.py`, `p2_2_check.py` are targeted harnesses.
  `compare_check.py:126-128` defines `blank_page()` but never calls it — the
  only dead helper found in `tests/`.
- Gate fixtures are generated deterministically into `/tmp`; the 4K fixture is
  reused by several checks.

## 4. Duplicated work and allocation inventory

| Where | What is repeated / allocated | Frequency |
|---|---|---|
| `engine.js:135-153,318,633` | Palette string parsing per glyph/pixel | Every palette/dither render |
| `engine.js:155-237` | 1–3 full-frame `getImageData`/`putImageData` passes | Every adjusted render |
| `engine.js:656` | `Float32Array(data.length)` | Every error-diffusion render |
| `effects.js:147-149` | Fresh `ImageData` per `fxData` call | Most effects |
| `effects.js:134-141` | Global `Float64Array` luma plane sized to pixels | Retained across renders |
| `effects.js:723-772` | `fxPoolClear()` on size change | Every preview-size change |
| `app.js:761` | `JSON.stringify(renderOpts())` | Every interactive frame |
| `app.js:535-548` | `JSON.stringify(state.opts)` | Every input/change |
| `app.js:1913-2128` | Full 22-card DOM rebuild | Preset/reset/undo, not drag |
| `app.js:2330-2342` | Full DOM text scan | Every search keystroke |
| `app.js:1159-1203` | `computeOutputSize()` repeated | 2–4× per completed frame |
| `render-worker.js:33` | New `OffscreenCanvas` per result | Once per worker frame |
| `reorder.js:173-193` | Layout read/write/read per slot change | During reorder only |
| `reorder.js:22-24` | `querySelectorAll` per list access | Reorder only |
| `app.js:2608-2621` | Multiple rect reads per sheet pointermove | Mobile sheet drag only |

## 5. Bugs found by this audit

| # | File:line | Bug | Severity / effect |
|---|---|---|---|
| B1 | `app.js:440` | `renderPaletteBuilder()` assigns to undeclared `builtin` inside a ternary. In non-strict script this creates a global; if the palette is not found it also assigns `undefined`. | Low, but real leak/pollution; fix when touching the palette builder |
| B2 | `app.js:1381,1410` | One `MAX_FILE_BYTES = 40 MB` is used for images **and video**, and the message says “under 40 MB” for both. | Blocks the P2-3 850 MB video rule; Step 4 |
| B3 | `app.js:1715-1716,1665,1710` | Video export is fixed at 24 fps, clamped to 20 s, and rendered at `computeOutputSize()`, i.e. the preview/export size controls, not native `videoWidth × videoHeight`. | Blocks the native-resolution export rule; Step 4 |
| B4 | `app.js:2330-2342` vs `app.js:1905-1911` | `filterControls()` sets `sec.style.display = ""` on matching/all sections. Clearing the search after filtering in Dither mode makes the hidden Script/Color sections visible until the mode is toggled or the UI is synced. | Medium UI correctness; cheap fix after baseline |
| B5 | `index.html:125`, `app.js:2562-2570` | Stale hard-coded `data-snap="half"` is only cleared by a resize/`visualViewport` event. | Cosmetic/attribute race; already documented in P2-2 |
| B6 | `app.js:1749-1751` | `video.onseeked = r; setTimeout(r, 120);` leaves a stray timer after every exported frame; `r` can resolve twice (promise ignores it) and the handler is only cleared after the loop. | Low; no wrong output observed, but it keeps timers alive during export |
| B7 | `reorder.js:177-193` | `movePlaceholder()` reads every item's `top`, mutates the DOM, then reads every item's `top` again; this is a forced synchronous layout in the middle of a pointer gesture. | Performance only; A2 measures reorder separately if needed |
| B8 | `app.js:1856-1903,1913-2128` | `syncUIFromState()` always rebuilds the full effect list, even when only one value changed (undo/redo, reset section). | Performance only; not on the render path |

B2/B3 are the only bugs that block an explicit P2-3 requirement. B4 is a
user-visible correctness defect that the 169 tests do not cover; it should be
fixed with a regression check, not silently.

## 6. Risks and non-goals

- **Effect pixels are the contract.** `glitch`, `vhs`, `pixelsort`, `grain`,
  `matrix` use `Math.random()`. Golden hashes will seed `Math.random` in the
  gate and list the seeded effects; production behaviour is unchanged.
- **The preview is already capped** at 1600 px / 2.56 MP. “Work done at full
  size” is real only in export/worker-full jobs; A2 records a one-shot native
  sample per effect and five-window preview numbers.
- **Headless Chromium is software raster.** GPU numbers and real-device feel
  stay HUMAN-CHECK.
- **Firefox 157 lacks `longtask`.** Frame-time claims from Firefox cannot use
  the long-task clause; only Chromium can.
- **No idle rAF loop** exists when an image is loaded and nothing is playing.
  Idle CPU is CSS/compositor noise plus any pending toast/settle timers.
- **Memory is bounded by design**: 60 history snapshots, 10 pooled canvases,
  8 stage slots, one worker bitmap. The luma plane is the largest retained
  buffer; export creates full-size canvases transiently.
- **Do not rebuild** `engine.js`/`effects.js` merely because they are large.
  A rebuild is only allowed if A2 measures a real bottleneck and the owner
  approves it in A4.

## 7. What A2 must still measure

`tests/bench/bench.py` records: startup (first paint, FCP, DCL, load,
app-ready, bytes, requests), all 22 effects × 3 modes × 1080p/4K (five preview
windows plus one native sample), stacks 1/3/6/12, slider drag with worker
on/off, video playback at 0/3/6 effects on 1080p/4K, one video export with
native dimensions and peak heap, idle CPU, heap before/after 200 renders, and
bundle size. Results land in `baseline.json`; `decisions.md` uses them.
