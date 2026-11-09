# P2-2 closeout evidence (Step 2)

Branch `p2-3-work`, base `3686017`. All commands run from `/home/mustafa/glyphcraft`.

## 1. Individual screenshot review + run equivalence

- All **68** PNGs in `docs/evidence/p2-2-run-3/` (58 G3 + 10 G14, not 58) were opened in
  six batches of 12/12/12/12/12/8 and described one by one in
  `docs/evidence/p2-2/screenshot-review.md`. No visual defect was found.
- Runs 1 and 2 were not re-opened image by image; equivalence was measured with
  `docs/evidence/p2-3/diff_regions.py` and `pixel_diff.py` (JSON next to them):
  - 68/68 filenames match between runs 1, 2 and 3 (run 3 renames the 740 cell
    `-half` → `-none`, same pixels).
  - 1280×900: right panel (x ≥ 980) **0 px** difference; top bar differs only in
    the render-time digits (`dark`: bbox x 935–954, y 19–27, 118 px > 2/255;
    `light`: x 935–947, 91 px).
  - 360×740: sheet body identical; only the same status digits (y 430–432,
    47–50 px) differ.
  - 740×360: run 2 vs run 3 differs in **192 px**, bbox `[1393,129,1426,144]`,
    i.e. the status digits only; the 740-cell layout is pixel-identical.
  - Canvas differences are confined to the black preview and are caused by the
    intentionally random effects in the “fullest” stack (`effects.js:219-242`,
    `effects.js:619-626`, `engine.js:97,608,778-804`), not by chrome. Worst
    canvas fraction >2/255: 0.332 (dark 1280); median file: no chrome diff.
- Diff images: `diff-dark-1280-fullest.png`, `rawdiff-dark-1280-fullest.png`;
  crops for the focus-ring check: `crop-*.png`.

## 2. Why G19 printed 2243323070 before and 2247827130 after

Not a code change: the G19 drag moves the **Depth** option from its default
**80** to **75**, and the hash is a hash of that state.

`docs/evidence/p2-3/hash_probe2.py` on one tree, one browser context:

```
depth before drag 80 after drag 75
hash fresh/default-depth 2243323070
hash post-drag 2247827130 repeat 2247827130
hash depth restored 2243323070
long tasks [] errors []
```

(`hash_probe2.log`; an earlier run of the same probe reported `[54, 57] ms`
without the gate’s quiet setup. The probe is not the gate, so neither value is
a gate claim; G19 must be re-run in Step 3.) Restoring Depth 80 restores
`2243323070` exactly, so the two published hashes are two states of the same
pipeline.

## 3. Empty `snap=` in G14 light 740×360

Cause: `index.html:125` hardcodes `data-snap="half"` on the panel. At 701–768 px
the panel is not a mobile sheet (`matchMedia('(max-width: 700px)')` false,
`app.js:2562-2567`), and `updateMobileViewport()` only clears the attribute when
a resize or `visualViewport` event fires (`app.js:2695-2698`).

`docs/evidence/p2-3/snap_probe.py` / `snap_probe.json`, three fresh 740×360
contexts, at load + 100/300/700/1500 ms:

```
run 1..3: snap=half, mobile=false, sheetH=267 at every sample
```

So a fresh page keeps the stale attribute; gate run 3 took the screenshot after
a resize/visualViewport event had cleared it. All three runs produce the same
layout and pixels outside the status digits (`192 px`, item 1). No fix is made in
this no-behaviour-change closeout; it is recorded for the Step 3 audit.

## 4. Firefox 157 worker path

`docs/evidence/p2-3/firefox_g19.py` (full G19 copy, `p.firefox.launch`) →
`docs/evidence/p2-3/firefox-g19.log`:

```
worker + OffscreenCanvas enabled       enabled=True ... canvasW=1600  PASS
heavy drag: no long task >50ms         worst=0ms over50=0 posted=131 drawn=1 cancelled=130 depth=80->74 scroll=10/10 maxRt=28.7ms  PASS
worker equals main-thread render       sync=1212541770 worker=1212541770  PASS
preview/full job types agree           preview=1212541770 full=1212541770  PASS
20 rapid updates: latest only          drawn=1 cancelled=18 posted=151 final=3301346089 expected=3301346089  PASS
fallback renders the same pixels       workerEnabled=False hash=1764367753 sync=1764367753 errors=[]  PASS

6 checks, 0 failure(s)
WORKER PASS
```

A second run with the exit code captured
(`firefox-g19-rerun.log`) reproduced the same six PASS rows and identical
hashes, ending `WORKER PASS` / `EXIT=0`; that run's scroll-probe round trip
peaked at `maxRt=103.8ms` (first run 28.7 ms). `maxRt` is the round trip of one
Playwright `page.evaluate` that scrolls the panel (`firefox_g19.py:159-173`),
not a frame interval or a long task, so it is an observation for Step 3, not
proof of a stall.

Honest caveat: Firefox 157 does **not** implement `PerformanceObserver`
`longtask`. `firefox_longtask_support.py` reports
`supportedEntryTypes = ['event','first-input','largest-contentful-paint','mark',
'measure','navigation','paint','resource']` and a 120 ms busy loop produced
`seen: []`. The `worst=0ms` row therefore proves the drag/scroll/cancel
behaviour (131 posts, 1 draw, 130 cancels, 10/10 scroll samples changed,
max rAF interval 28.7 ms) but **cannot** prove the “no main-thread task > 50 ms”
clause. That clause remains Chromium-only evidence. The worker and its fallback
produce identical pixels in Firefox, with no page or console errors; the hash
values differ from Chromium (rasterizer difference), which is expected because
only same-browser sync/async equality is claimed. The four evidence screenshots
in `firefox-shots/` (dark/light × 1280/360, heavy stack) were opened: the
Firefox render matches the Chromium states — one-row mobile top bar and sheet at
360, two-row desktop bar at 1280, depth 74 after the drag, no clipped control.

## 5. Prompt file tracked; build and dist smoke

- `git ls-files docs/prompts/part2_performance_core.md` lists the file
  (tracked).
- `npm run build` → `BUILD_EXIT=0`, `dist/ ready: JS 201899 -> 184506 bytes,
  12 paths` (`build.log`; 12 because the new font licence ships in `dist`).
- `python tools/dist_smoke.py` → `source: hash=4135467496 canvas=900x600`,
  `dist: hash=4135467496 canvas=900x600`, `errors: []`, `DIST SMOKE PASS`,
  `SMOKE_EXIT=0` (`dist-smoke.log`).

## 6. `file://` fallback

`docs/evidence/p2-3/file_probe.py` → `file-probe.log` (exit 0), screenshot
`file-fallback.png`:

```
file url file:///home/mustafa/glyphcraft/index.html
reference(worker disabled over http): 2243323070 workerEnabled False
file:// canvas: 2243323070 workerEnabled False stats {'enabled': False, ... 'errors': 0}
file integrity {'w': 1600, 'h': 900, 'nonBlack': 1440000, 'loading': True, 'sourceType': 'image'}
hash equal True
file pageerrors []
file console errors []
```

Chromium blocks the worker on `file://`; the app boots into the synchronous
fallback, fills all 1,440,000 preview pixels, matches the HTTP reference hash
exactly, and raises no error.

## 7. Font licence + README network sentence

- Added `assets/fonts/JetBrainsMono-OFL.txt` (SIL OFL 1.1, JetBrains Mono
  copyright, note that the shipped `JetBrainsMono-latin.woff2` is a Latin subset
  redistributed under the same licence).
- `network_probe.py` measured the real request set: own-origin HTML/CSS/JS and
  the two self-hosted woff2 files, plus third-party `fonts.googleapis.com` CSS
  and two Crimson Text woff2 files. With Google Fonts blocked: no page error,
  one expected `net::ERR_FAILED` console line, layout still Goodmountain /
  Georgia / serif. README now says “only third-party requests”, names Crimson
  Text, and stops claiming self-hosted fonts never touch the network.
