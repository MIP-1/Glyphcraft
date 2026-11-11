# P2-3 Step 5: speed log

Every change is measured with `tests/bench/speed_effect.py`: one page, one
canvas, both variants installed as `EFFECT_RUNNERS[id]` in the same session.
The "old" variant is read from git (`--rev df4365d`), the "new" variant is the
working tree. Five windows; each window runs the pair as A/B/B/A, discards a
warm-up call per variant, forces GC before every timed call, and reports the
window median. Overall median and p95 are computed over all 20 samples per
variant. The rule from `decisions.md`: keep a change only when the paired
median is at least 10% faster in 4 of 5 windows, or it removes a measured long
task over 50 ms — and only with identical golden hashes.

Headless Chromium, software raster, 1600x900 (the app's preview clamp), seed
`0x5EED1234`. These are app-work numbers, not a GPU claim. A single number here
is a floor, not a finish line.

## 1. `fxOil` per-pixel allocations (commit pending)

`effects.js` `fxOil`: the old body allocated `vals = []` and `best = [0,0,0]`
for every quadrant of every pixel (four allocations per pixel, ~5.76 M arrays
at 1600x900) and then used two `Array.reduce` passes. The new body allocates one
`Float64Array` scratch buffer and one result triple per frame, fills them by
index and sums with explicit loops in the same order, so every double is
computed exactly as before.

| Metric | Old | New | Change |
|---|---:|---:|---:|
| Window median, radius 2 | 1616.6 / 1381.8 / 1465.3 / 1470.4 / 1687.5 ms | 1139.1 / 1042.8 / 1227.7 / 1096.2 / 1137.5 ms | — |
| Median of 5 window medians | 1470.4 ms | 1137.5 ms | **−22.6%** |
| All-sample median (n=20) | 1428.7 ms | 1066.6 ms | −25.3% |
| All-sample p95 | 2085.6 ms | 1410.9 ms | −32.4% |
| Windows ≥10% faster | — | 5 / 5 | keep |
| Output hash, radius 2 | 4192098609 | 4192098609 | identical |

Extra parity probe at radii 1, 2 and 3 on both 1600x900 and 3840x2160 (6 pairs,
old vs new in the same page): all six hashes identical.

Verification after the change:

| Check | Result | Log |
|---|---|---|
| G20 golden, 200 cases incl. native 4K `oil` | 200/200 exact, 0 problems | `golden-oil.log` |
| 169-test suite | 169 checks, 0 failures | `test-suite-oil.log` |
| Build + dist smoke | DIST SMOKE PASS, source = dist = `4135467496` | `build-oil.log` |

Raw timing data: `speed-oil.json`; output: `speed-oil.log`.

## 2. Palette parsing once per render

`engine.js`: `nearestPaletteColor` built a `parse` closure and ran a
`rgba?()` regex plus a hex regex for every palette colour on every call — once
per glyph in Script mode and once per pixel in Dither palette mode. The parsed
form is now cached by palette content (`paletteEntries`), and the three call
sites (Script, SVG, Dither) build it once per render. Distance arithmetic,
iteration order, tie-breaking and the returned string are unchanged. The Dither
path also used to re-match the nearest string with `/rgb\((\d+),(\d+),(\d+)\)/`
per pixel to decide whether to substitute; that decision is now precomputed per
palette entry (`hasRgb` + channels), so a hex, `rgba()` or spaced `rgb()`
palette still falls back to the source pixel exactly as before.

This path is not in the G20 golden set (the goldens use the default spectrum
colour mode), so it has its own old-vs-new proof.

### Dither, palette colour mode, 1600x900, `Grayscale 16`

| Metric | Old | New | Change |
|---|---:|---:|---:|
| Window medians | 2376.8 / 2395.4 / 2367.8 / 2423.5 / 2414.6 ms | 405.4 / 352.4 / 352.4 / 368.6 / 349.9 ms | — |
| Median of 5 window medians | 2395.5 ms | 352.4 ms | **−85.3%** |
| All-sample median (n=20) | 2397.0 ms | 358.0 ms | −85.1% |
| All-sample p95 | 2512.3 ms | 457.6 ms | −81.8% |
| Windows ≥10% faster | — | 5 / 5 | keep |
| Output hash | 3491481483 | 3491481483 | identical |

### Script, palette colour mode, 1600x900, `Grayscale 16` (secondary)

Median 104.3 → 98.4 ms (−5.7%), 2/5 windows at or past 10%, identical hash. This
does not meet the keep rule on its own, so no speed claim is made for Script
mode; the precompute stays because it is the same cache and the same code path,
and it is parity-checked.

### Old-vs-new parity matrix (`tests/bench/parity_engine.py`)

Two trees served side by side in one browser; canvas hash plus SVG and TXT
export fingerprints compared. 26 cases, 0 failures: Script and Dither in
palette, mono and spectrum colour modes; hex palettes (`Grayscale 16`, `CGA`,
`1-bit`, `Game Boy`, `Terminal`); a custom palette mixing `rgb()`, `rgba()`,
3-digit and 6-digit hex; all nine dither kernels
(`floyd-steinberg`, `atkinson`, `bayer2/4/8`, `threshold`, `blue-noise`,
`random`, `halftone`); and an Effects Only palette render. Log:
`parity-palette.log`.

Verification: G20 200/200 exact (`golden-palette.log`), 169 tests
(`test-suite-palette.log`), build + dist smoke (`build-palette.log`).

## 3. One adjustment pass instead of three

`engine.js` `applyAdjustments` ran the pixel work in up to three separate
`getImageData`/`putImageData` round trips: highlights/shadows/sharpen, then
invert, then sepia. They now share one read and one write, with the same passes
run back to back on the same `Uint8ClampedArray`. Every write already stores
through `Uint8ClampedArray`, so the merged buffer holds exactly the bytes a
put/get round trip would have returned, and G20's zero-adjustment goldens are
untouched.

The first attempt measured the whole page (`speed_page.py`, Effects Only with
all five pixel adjustments). It was too noisy at ~150 ms per render: one run
passed 4/5 windows at −26%, the next 3/5, and a 4K page run reversed. The
function was therefore isolated: `tests/bench/speed_adjust.py` installs the old
`applyAdjustments` from git and the new one from the working tree in the same
page and alternates them on the same canvas, with an untimed source redraw and
forced GC around every call. That function is short enough that a single canvas
stall moved the old 4-sample median, so each window takes 8 alternating samples
per variant. Two consecutive runs:

| Metric | Old | New | Change |
|---|---:|---:|---:|
| Run A window medians | 184.3 / 180.9 / 182.7 / 193.9 / 181.5 ms | 161.8 / 156.3 / 162.7 / 165.9 / 162.8 ms | **−11.0%** |
| Run A all-sample median (n=40) | 183.9 ms | 161.4 ms | −12.2% |
| Run B window medians | 180.8 / 187.6 / 180.9 / 158.2 / 161.7 ms | 159.1 / 168.3 / 149.1 / 138.1 / 139.5 ms | **−17.5%** |
| Run B all-sample median (n=40) | 179.6 ms | 149.0 ms | −17.1% |
| Windows ≥10% faster | — | A 5/5, B 5/5 | keep |
| Output hash | 1176483911 | 1176483911 | identical |

1600x900, adjustments `highlights 60, shadows 60, sharpen 40, invert, sepia`.
Logs `speed-adjust-fn.log` / `speed-adjust-fn-2.log`, data the matching JSON.

At 3840x2160 the same probe is 815.2 vs 883.5 ms (−7.7%, 2/5 windows at or past
10%, all-sample p95 961.6 vs 1081.3 ms, identical hash 4267617543). The 4K
number is a strict work reduction but does not meet the keep rule on its own, so
no 4K claim is made; the merge is kept on the preview-size result. The page-level
harness remains in the tree (`speed_page.py --adj`, `--full`) for future items.

### Parity

`tests/bench/parity_engine.py` now appends nine adjustment profiles to the
matrix: all pixel passes together, highlights+shadows+sharpen, the canvas
filter group plus sharpen+invert, invert alone, sepia alone, Script with
shadows+sharpen+sepia, Dither palette with invert, Dither mono atkinson with
all passes, and an Effects Only CGA render. 35 cases, 0 failures, canvas hash
identical in every case. Log: `parity-adjust.log`.

Verification: G20 200/200 exact (`golden-adjust.log`), 170 tests
(`test-suite-adjust.log`), build + dist smoke `4135467496` (`build-adjust.log`).
