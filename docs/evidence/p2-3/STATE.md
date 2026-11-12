# P2-3 STATE

- Branch: `p2-3-work` (from `main` @ 3686017)
- Safety tag: `pre-P2-3` pushed
- Step 1: build exit 0, dist_smoke PASS hash 4135467496, no gate running, tmux absent
- Step 2: P2-2 closeout complete — see `closeout.md`
  - 68/68 run-3 screenshots reviewed; run 1/2 equivalence measured
  - hash difference explained (Depth 80 vs 75)
  - 740 px `data-snap` race explained (index.html:125, app.js:2562-2567)
  - Firefox 157 worker 6/6 checks; long-task API unsupported there (reported)
  - `file://` fallback hash-equal, no errors
  - font OFL licence added; README network sentence corrected
  - build + dist smoke re-run green
- Tag: `P2-2-closeout-pass`
- Step 3 (Task A):
  - A1 audit complete: `docs/evidence/p2-3/audit.md`
  - A2 baseline complete: `baseline.json` + `baseline.log`, all 9 sections,
    no page errors, 132 render rows, 24 stack rows
  - A3 golden complete: 200 cases, seed `0x5EED1234`, no exclusions;
    `tests/gate/golden_p2_3.json`, generator `tests/bench/golden_gen.py`,
    checker `tests/gate/golden_check.py`; two exact check runs
  - G20 wired into `tests/gate/run_gate.py`; standalone G20 PASS 200/200
    exact in 193.5 s (`g20-run.log`)
  - A4 decisions complete: `docs/evidence/p2-3/decisions.md`; no rebuild
    candidate, no owner question needed
- Tag: `P2-3-A-pass`
- Step 4 (Task B):
  - split limits: `IMAGE_MAX_FILE_BYTES` 40 MB, `VIDEO_MAX_FILE_BYTES` 850 MB
  - `fileSizeError()` with 850 MB exact accepted, +1 rejected, 0-byte rejected
  - `videoExportSizeError()` canvas guard; native export via
    `video.videoWidth` × `video.videoHeight`
  - size controls visible but disabled for video, `#output-video-note` inline
  - new `tests/gate/video_p2_3_check.py` (G21), 25 checks, RED then GREEN
    (`video-p2-3-red.log` → `video-p2-3-green-3.log`)
  - standalone G21 PASS 25 checks in 52.6 s (`g21-run.log`)
  - 169 tests green (`test-suite-step4.log`); test suite now reloads an image
    before the output picker because video disables those controls
  - G20 200/200 exact after the app change (`golden-check-step4.log`)
  - existing video gate 25/25 (`video-check-step4.log`)
  - build + dist smoke PASS hash 4135467496 (`build-step4.log`)
  - real 838.1 MB 4K VP9 closeout: 7/7 checks (`video-large.log`), fixture and
    export deleted; 0.70 s load, 0 JS heap growth, 50.3 fps, native 3840x2160
    export in 107.9 s
  - `docs/evidence/p2-3/video-audit.md` records B1 flow, RED → GREEN and the
    large-file results
- Tag: `P2-3-B-pass`
- Step 5 (Task C), complete:
  - C1 `ad5bb37`: `fxOil` per-pixel allocations removed; 5/5 windows,
    median −22.6%, p95 −32.4%; hashes identical at radius 1/2/3 on
    1600x900 and 3840x2160; G20 200/200, 169 tests, dist smoke
  - C2 `2443ee0`: palette parsed once per render and reused by Script, SVG
    and Dither; precomputed per-entry `rgb()` substitution; dither+palette
    median −85.3% (5/5), p95 −81.8%; script+palette −5.7% (no claim);
    old-vs-new parity 26/26 (`parity-palette.log`); G20 200/200, 169 tests
  - C3 `ec5a726`: B4 fix — `filterControls()` re-applies
    `toggleModeSections()` last and hides empty sections during a query;
    new regression check, suite now 170 (G5 updated); G20 200/200, dist smoke
  - evidence: `perf-log.md`, `b4-search.md`
  - C4 `4ab2169`: adjustment pixel passes share one get/put (up to three
    before); function probe 5/5, −11.0% and −17.5% in two runs; parity
    35/35 including nine adjustment profiles; G20 200/200, 170 tests
  - C5: diffusion-buffer pooling measured slower (+3.5% planar, +2.5%
    interleaved, 0/5), engine.js unchanged; negative result in `perf-log.md`
  - items 4/5 rejected on measurement: 4K preview-base draw <0.1% of the
    render; render key 14–20 µs (see `perf-log.md`, `overhead.log`)
- Step 6, complete: three consecutive full gate runs PASS on `28b22dc`
  - run 1 06:16–06:45, run 2 13:56–14:24, run 3 14:24–14:54 (2026-11-11)
  - every run G1–G21 PASS, G5 170 checks, G20 200 cases, G21 25 checks,
    `GATE PASS`, EXIT=0; logs `gate-run-1/2/3.log`
  - `gate-run-1-aborted.log` (G1 only, killed after a tree change) and
    `gate-run-2-interrupted.log` (G1–G12, server restart) do not count
  - screenshots: 68 per run in `p2-3-run-1/2/3/`, 58 in
    `p2-3-run-2-interrupted/`; all 68 final-run files opened in six batches,
    notes in `screenshot-review.md`
  - pixel diff: runs 1/2 = 0 px outside canvas/status in all 68 files;
    runs 2/3 same except one 2,124 px slider reflow (HUMAN-CHECK);
    `pixel-diff-run1-run2.json`, `pixel-diff-run2-run3.json`,
    `pixel-diff-regions.txt`
- Step 7, complete: break-it 31/31 PASS in 87.7 s
  (`tests/bench/breakit_p2_3.py`, `breakit.log`); all 12 required cases;
  `docs/GATE.md` P2-3 section, README and PROJECT_MEMORY updated
- Next: merge `p2-3-work` to `main`, closeout commit, tag `P2-3-pass`, push.
  P2-4 is not started.
