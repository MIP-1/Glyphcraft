# V1 — stable full-resolution video frames

Status: **PASS** (parity GREEN in Chromium and Firefox; G13 GREEN; gate runs below)

Base: `b46ca6c` (`V0-pass`). Task: `docs/prompts/p2_3_video_fix.md`, V1.

## Root cause

`render()` chose `previewSize(full, state.playback.scale)` while a video was
playing, and `adaptPlaybackScale()` lowered `state.playback.scale` until the
render cost fit a 26 ms budget. V0 measured the result in the real UI:

| State | Chromium | Firefox |
|---|---|---|
| Paused | 1280×720 | 1280×720 |
| Playing | **755×425** (scale 0.59) | **640×360** (scale 0.5) |
| Playing, 6 heavy effects | 256 px wide (scale 0.2) | 256 px wide (scale 0.2) |

The same decoded frame, same effects and same preview size produced different
pixels because the backing store shrank. It was not a stale source, a
worker/sync switch (`workerEligible` rejects video), a time-seeded effect
(hash parity with `posterize`+`duotone` is deterministic), or a torn canvas.

## Fix

- `render()` always uses `previewSize(full)` (`app.js`), and the playback scale
  is pinned to 1; the governor (`PLAYBACK_SCALES`, `playbackGuessScale`,
  `adaptPlaybackScale`, `playbackRemember`) is removed.
- When the pipeline cannot keep up it now drops frames or lets playback slow
  down. It never changes render resolution.
- `startVideoLoop()` records the rVFC `mediaTime` (`state.videoFrameMediaTime`,
  `state.playbackFrameTime`) so a played frame can be identified.
- A paused `seeked` listener schedules a render after the decoded frame is
  ready, so seeking still renders the frame at the requested time.

## RED evidence

- G13 with the V0 `app.js` and the new assertions
  (`docs/evidence/v1/g13-red.log`):
  - `FAIL playback cost is measured at full output size - full=1280 preview=1280 backing=256 scale=0.2`
  - `FAIL playback keeps the full preview backing, never a reduced one - paused backing=1280 playing backing=256 ... playScale=0.2`
  - 25 checks, 2 failures. The same two assertions that should have caught the
    owner's symptom were the ones locking the old behaviour in.
- G22 parity with the old harness
  (`red-harness-chromium.log`, `red-harness-firefox.log`):
  - Chromium: 4 unmatched play frames from a stale `playbackFrameTime` left
    over from the previous playback phase.
  - Firefox: `t=3.4` unmatched even after scanning ±0.6 s.
  - Firefox paused seeks never fired rVFC, so the old seek helper spent its
    1.5 s timeout on every seek.

## GREEN evidence

- `docs/evidence/v1/g13-green-attempt5.log`: **27 checks, 0 failures** (the
  count went up from 25; two checks were added).
  - paused and playing backing `1280×720`, preview `1280×720`, scale 1, box
    error 0.00%.
  - heavy-six full-resolution playback: 32 renders over the 10 s measurement,
    video advanced 7.205 s, p50 275.8 ms, CPU/frame best 255.5 ms, backing
    1280×720, `scales={'1': 6}`. Across the five attempts: 32–37 renders, p50
    273.3–285.0 ms, CPU/frame best 220.7–255.5 ms, longest task best 276–291 ms.
  - light two-effect playback: p50 72.5 ms against a paired control of
    42.5 ms → delta **30.0 ms**; CPU/frame delta 30.8 ms; all frames 1280×720.
- `docs/evidence/v1/parity-chromium.log`: 20/20 paused-seek timestamps,
  **28 distinct playback frames**, all exact at offset `0.0`, span 4.666 s,
  backing 1280×720, 0/27 backsteps.
- `docs/evidence/v1/parity-firefox.log`: 20/20 paused-seek timestamps,
  **28 distinct playback frames**, offsets `0.0`, `-0.033`, `-0.034` (one
  presentation frame), span 5.2 s, backing 1280×720, 0/27 backsteps.
- `docs/evidence/v1/seek-green-chromium.log` and `seek-green-firefox.log`:
  the new plain-seek check passes 5/5 in both browsers (`8 checks, 0
  failures` for the parity subset).
- Four extra Firefox runs and three extra Chromium runs passed. One Firefox run
  showed a `-0.3 s` presentation lag and a `backstep` after the renderer was
  starved; see the rule change below.
- `npm run build` and `python tools/dist_smoke.py`: **DIST SMOKE PASS**
  (source and dist hashes identical, no page errors).

## Seek-race check and a rejected hypothesis

Hypothesis: Firefox never fires rVFC for a paused seek, so a user seek can
leave a stale frame (the old seek helper timed out on every seek in V0's
harness). Measurement: in Firefox a paused seek to 4.1 s can take 908 ms before
`seeked` fires; the `seeked` handler then arms rVFC, which does fire, and the
preview repaints correctly. An earlier "stale frame" result came from a 700 ms
test window that expired before `seeked`, not from the app.

The handler is still load-bearing, proven by mutation: with the `seeked` render
removed, Firefox repainted 0/5 plain seeks (canvas unchanged, wrong hash) and
even 2/20 paused-seek parity timestamps went stale
(`docs/evidence/v1/seek-red-mutation-firefox.log`). No app change was needed;
the check is now permanent so V3's seek bar cannot regress it.

## Deliberate rule changes (measured)

### G13 playback cost

Old rule assumed the resolution governor:

| Assertion | Before | After | Measured after |
|---|---|---|---|
| Backing while playing | `< full preview` (backing ≥ 150 px) | `== preview` width/height, `scale == 1`, scale log `{"1"}` | 1280×720 = preview |
| Heavy p50 delta | ≤ 8 ms | ≤ 380 ms (absolute full-resolution delta) | best 228.2 ms |
| Heavy CPU/frame | ≤ 40 ms | ≤ 400 ms | best 220.7–255.5 ms |
| Heavy longest task | ≤ 250 ms | ≤ 650 ms | best 276–291 ms |
| Heavy long-task / 2 s | ≤ 400 ms | reported only (inherent to a 230–300 ms frame) | 1602–1767 ms |
| Heavy task_ms | < 8000 ms | reported only | 8572–9759 ms |
| Minimum heavy renders | 50 | 10 | 32–37 |
| New: drops frames, not resolution | — | renders ≥ 10, video advances ≥ 1.5 s, full backing | 32 renders, 7.205 s |
| New: light-two interactive | — | paired p50 delta ≤ 45 ms, CPU delta ≤ 50 ms, absolute p50 ≤ 130 ms | delta 30.0 / 30.8 ms, p50 72.5 ms |

Why: V1 forbids the resolution drop that the 8 ms / 40 ms bounds depended on.
At full 1280×720 the six-effect stack measured p50 273.3–285.0 ms across the
five attempts; the old 40 ms bound was only reachable with a 0.2×
backing store. The light stack is the interactive case and is still gated by a
paired delta (control measured immediately before), so desktop load cancels.
The test count went from 25 to 27 checks.

### G22 playback parity

| Part | Before | After | Why |
|---|---|---|---|
| Paused seek | wait for rVFC `mediaTime`, 1.5 s timeout in Firefox | wait for `seeked` + 120 ms + two rAF, then paint | Firefox fires rVFC only after a paused seek's `seeked`, so the old helper timed out and wasted 1.5 s per seek |
| Playback frame identity | still at `mediaTime ±0.02 s`, then every 1/30 s within ±0.6 s | exact full-canvas hash at the nearest ffprobe PTS frame, nearest ±3 frames first, then ±0.53 s | Exact identity to a real decoded frame; the window is tighter than ±0.6 s |
| Monotonic time | not asserted | reported, not gated | Firefox rVFC reported `mediaTime=1.467` while `currentTime=1.173`, then `1.233`: it runs ahead of a starved clock |
| Pixel-size check | backing width only | backing equals preview width in every sample | same contract as G13 |
| New: plain seek repaints | — | 5 before/after seeks, canvas must equal a fresh still and change, no test render | seek-race contract for the V3 control bar |
| Still match retry | — | one 500 ms retry per sample, reported as `retried=[...]` | a rare stale `drawImage` after a paused seek hashed the old frame for every candidate once |
| Partly decoded frame | — | at most `distinct - 2` exact samples; every other sample must be within mean 4.0 of its nearest frame | Chromium can hand `drawImage` a partly decoded frame under load |

Measured presentation lag: Chromium 0.0 s in all runs; Firefox 0–1 frame
normally, one `-0.3 s` sample in 4 runs when a long render starved the
compositor. The gate allows exact matches within ±0.5 s and requires the
matched frames to span at least 1.5 s, so a stale/half-updated canvas cannot
pass.

The partly-decoded-frame bound comes from measurements, not convenience:
with two CPU burners, 2 of 28 samples hashed no frame anywhere in the
180-frame clip; 1 of 28 differed from its nearest frame by mean 2.66 and
max 191 while the other 27 matched exactly (mean 0, max 0); and the unmatched
sample matched no frame band by band, so it is not a two-frame row split.
Adjacent frames of this clip differ by mean 8–10, so a 4.0 bound cannot accept
a different frame, and a rescaled canvas is rejected before any scan. Four
Chromium parity runs under load measured 0, 0, 0 and 1 glitch (mean 2.01).
Restoring the old 0.59 playback scale still fails the check
(`canvas sizes=[(755, 425)] ... identity not testable`, plus three others,
`docs/evidence/v1/parity-red-resolution-chromium.log`).

## G22 full-run baseline on the V1 tree

`docs/evidence/v1/g22-full-chromium.log`: **20 checks, 10 failures**.
`docs/evidence/v1/g22-full-firefox.log`: 20 checks, 12 failures, captured
before the loop-wrap fix below, so it also failed playback parity at `t=6.167`.
All eight parity checks pass in both browsers; the failures are the V2–V4 work
that this task does not touch:

- seek (3): there is no `video-seek` range input or jump buttons yet — V3.
- output (5): Size controls are still disabled for video, the format list still
  offers PNG/JPG/WebP/SVG/TXT/WebM, the button still says "Export Image", there
  is no "Export Frame" action and no output size line — V4 and V2.
- export (2): there is no MP4 option, and the current MediaRecorder WebM is a
  real 1280×720 VP9 (Chromium) / VP8 (Firefox) file with different frame hashes
  at 0.2 s, 2.9 s and 5.5 s, but WebM carries no `nb_frames` or `duration`, so
  the check's `frames >= 170` and `duration ≈ 6` measurement fails. V2 replaces
  the export path and re-measures decoded frames instead of container tags.
- hitch (1, Firefox only): the 4K six-effect compare drag — V5.

Two harness defects were found and fixed while getting this baseline:

1. `page.select_option("#export-format", "mp4")` waited 30 s and raised before
   the failure could be recorded when the option is missing. The export loop now
   checks the option list first and records "format option 'mp4' is missing".
2. Sampling 28 frames takes ~5 s, so the 6 s clip loops and Firefox reports
   `mediaTime` past the end (measured 6.167). The sample time is now normalised
   modulo the clip length, so a wrapped frame is matched against the frames at
   the start of the clip.

## Gate runs on the V1 tree

`GATE_TASK=v1 npm run gate`, one log per run. G22 is expected to fail in this
task, and only on the V2–V5 checks listed above.

| Run | Log | G1–G21 | G22 chromium | G22 firefox | Verdict |
|---|---|---|---|---|---|
| 1 | `gate-run1.log` (37:32) | PASS | 20 checks, 10 failures | 20 checks, 10 failures | GATE FAIL G22 |
| 2 | `gate-run2.log` (32:17) | PASS | 20 checks, 10 failures | 20 checks, 11 failures | GATE FAIL G22 |
| 3 | `gate-run3.log` (30:18) | **G5 FAIL** | 20 checks, 10 failures | 20 checks, 10 failures | GATE FAIL G5, G22 |
| 4 | `gate-run4.log` (30:00) | PASS | 20 checks, 10 failures | 20 checks, 10 failures | GATE FAIL G22 |
| 5 | `gate-run5.log` (31:37) | PASS | 20 checks, 10 failures | 20 checks, 11 failures | GATE FAIL G22 |
| 6 | `gate-run6.log` (30:55) | PASS | 20 checks, 10 failures | 20 checks, 10 failures | GATE FAIL G22 |

Runs 4, 5 and 6 are the three consecutive runs on the committed tree: G1–G21
all PASS and G22 fails only on the V2–V5 checks. Runs 2 and 5's extra Firefox
failure is the V5 4K six-effect compare-drag hitch, which is intermittent;
runs 1, 3, 4 and 6 pass it. No run failed a parity, seek, output or export
check other than the documented V2–V4 ones.

Run 3 failed G5 with two timing-sensitive existing checks:

```
FAIL video load 100%
FAIL zoom preset 400% is crisp 100%, auto
```

Both are pre-existing in `tests/test_suite.py` (a 1.5 s wait for the video's
`320×240` status text, and a 350 ms wait after clicking the 400% zoom preset).
Neither touches the playback path changed by V1: the suite never plays the
clip, and `render()` used `previewSize(full)` for a paused video before and
after the fix. Run standalone immediately afterwards on the same tree:
`170 checks, 0 failures`, with `PASS video load 100%` and
`PASS zoom preset 400% is crisp 400%, pixelated` (`/tmp/opencode/suite-verify.log`).
Run 4 then passed G5 again. The failure is desktop load (G4 in run 3 measured
p95 frame times of 966–1066 ms), not a V1 regression.

## Status-bar times: 15 ms, 244 ms, 1767 ms

`updateStatus()` (`app.js:1174-1182`) prints `Math.round(state.lastRender)`.
`state.lastRender` is one `render()` call: draw the source into the preview-size
base, apply adjustments, run every enabled effect, then the final script/dither
composite. It is not FPS, decode time or export time. Zoom is display-only:
at 112% the status still showed the same 1600×900 canvas and 1035 ms.

Measured on this machine at 1600×900, `state.cacheDisabled = true`, three fresh
renders each (`/tmp/opencode/status_times.json`):

| Settings | lastRender (ms) |
|---|---|
| 2 effects (`posterize`, `duotone`) | 100, 78, 50 → median **78** |
| 6 heavy effects | 374, 384, 371 → median **374** |
| Oil Paint | 1063, 1078, 1035 → median **1063** |
| Oil Paint at 112% zoom | **1035** (canvas unchanged) |

The three numbers the owner saw have the same meaning and ordering; absolute
values differ with the machine and with the pre-V1 playback backing size. 15 ms
is a cheap/no-effect render, 244 ms a mid stack, and 1767 ms Oil Paint, which
costs roughly 14× the two-effect stack here. The numbers differ because effect
cost scales with the stack and pixel count, not because the status measures
different things.

## Screenshots (same clip, t=2.4 s, two effects)

- `video-light-1280.png`: light theme, 1280 viewport, canvas 1280×720 shown at
  72%, status `72% 1280×720 41ms`, panel with Script mode; the two-effect frame
  is the same at every size.
- `video-dark-1280.png`: identical frame/settings in dark theme, status 36 ms;
  chrome is dark, the clip pixels are unchanged.
- `video-light-360.png`: light theme at 360 px; canvas shown at 26% (320 px
  wide) but still 1280×720 backing, status `26% 1280×720 45ms`; mobile top bar
  and bottom actions.
- `video-dark-360.png`: identical 360 px frame in dark theme, status 35 ms.

## Break-it list (11 checks, all PASS)

`docs/evidence/v1/breakit.json`.

1. First frame (t=0) and last frame (t=5.967) paused parity: equal.
2. Effect switch 2 → 6 → 2 during playback: backing stays 1280×720, scale 1.
3. Theme toggle during playback: backing stays 1280×720, scale 1.
4. Compare/split toggle during playback and back: backing stays full.
5. 20 rapid play/pause cycles, then seek parity: equal, scale 1.
6. Portrait 1080×1920 clip: 900×1600 backing = preview, parity equal.
7. 4K clip: capped only by the 1600 px preview limit (1600×900), parity equal.
8. Viewport resize 1280 → 360 → 1280 during playback: backing unchanged.
9. `?worker=0`: video parity unaffected (video does not use the image worker).
10. Every size preset while playing: backing equals its preview (including
    1080p/2k/4k/8k capped at 1600), scale 1. No resolution change from
    playback.
11. No page or console errors across the run.

## HUMAN-CHECK

- Real GPU/Zen/frame rate is not claimed; all numbers are headless software
  raster on this desktop.
- The owner's exact 15/244/1767 ms machine and settings are not reproducible
  here; the metric and ordering are measured above.

## Files changed

Runtime: `app.js` (render at full preview size, rVFC time capture, paused
`seeked` render, dead governor removed). Checks: `tests/gate/video_check.py`
(G13 contract), `tests/gate/video_real_flow.py` (G22 parity). Docs/evidence:
this report, `docs/GATE.md`, `docs/evidence/v1/*`, `README.md`,
`docs/PROJECT_MEMORY.md`.
