# V2 — Export produces a real video (MP4 and WebM)

Status: **PASS** (G22 export subset 16/16 in Chromium and Firefox; 36-cell
ffprobe matrix green in both browsers and from `dist`; G21 31/31; gate runs
below).

Base: `4112a32` (`V1-pass`). Task: `docs/prompts/p2_3_video_fix.md`, V2.

## What was broken (RED)

The V1 tree exported a video through `canvas.captureStream()` plus
`MediaRecorder`, with no MP4 option. `docs/evidence/v2/red-g22-chromium-before-export.json`
(10 checks, 7 failures) measured:

| Check | Result |
|---|---|
| `export produces a real WEBM video` | 2,088,652-byte Matroska that ffprobe reads as **0 frames, 0.0 s**, no duration element |
| `WEBM covers the clip from the playhead` | export duration 0.0, frames 0 |
| `WEBM export shows progress and cancel` | no progress element, no Cancel, `busy=false` |
| `MP4 format is in the video list` | `mp4` absent from `#export-format` |
| `Export Frame writes one full-size still` | button did not exist (click timed out) |
| `progress panel hides when the export finishes` | no panel |
| `cancel stops the export and leaves the app clean` | nothing to cancel |

The cause is the capture method: `MediaRecorder` records wall-clock time, so a
render that costs more than 1/30 s drops frames, and the produced WebM had no
final duration/cues. The method was replaced, not patched.

## Full G22 on the V2 tree

The full G22 runs inside the final gate runs (`gate-run1.log` /
`gate-run2.log` / `gate-run3.log`; `g22-chromium-163333.json`,
`g22-firefox-164007.json`): Chromium **32 checks, 4 failures**, Firefox **32
checks, 4–5 failures**. Every export, parity and error check passes. The reds are the three
V3 control-bar checks, V4's "size controls are enabled for video", and — in
Firefox only — the V5 4K six-effect compare-drag hitch (60 fps median, p95
32.9–33.6 ms against a 25 ms limit, i.e. two or three 33 ms frames). V1 recorded
that same intermittent V5 red. No V2 sub-check is red.

## Method choice (measured, Firefox first)

| Candidate | Measurement | Verdict |
|---|---|---|
| `canvas.captureStream()` + `MediaRecorder` | 2 s clip → 0 decodable frames, 0.0 s duration; tied to wall clock | rejected |
| WebCodecs `VideoEncoder`, seek → render → encode, vendored muxer | exact 60/60 and 180/180 decoded frames, exact duration, cues/fast start | chosen |

The decisive number is the per-frame cost of the real pipeline. A 2 s 720p clip
needs 39.6 s in Chromium (0.66 s/frame) and 54.3 s in Firefox (0.91 s/frame)
for WebM; the P2-3 baseline measured Oil Paint at 1.7–2.5 s per preview frame.
A real-time capture has a 0.033 s budget per frame, so it cannot contain every
frame at those costs. Frame-by-frame encoding can, and its output does not
depend on playback speed.

Measured in Firefox first because it is the harder encoder: H.264 High is
supported, but its encoder emits B-frames in decode order (output timestamps
`0, 100, 33, 67, 133, … ms`). Chromium emits no B-frames (`0, 33, 66, …`).

### Vendored codecs

`vendor/mp4-muxer.mjs` 5.2.2 and `vendor/webm-muxer.mjs` 5.1.4 (both MIT,
Vanilagy), byte-identical to the published npm builds; SHA-256 in
`vendor/README.md`. `tools/vendor_muxers.py` generates the classic-script
`vendor/mp4-muxer.js` / `webm-muxer.js` from them; the only change is the final
ESM export block, replaced by a window global. They are loaded on demand with a
`<script>` tag when an export starts, because a dynamic `import()` of a file URL
is blocked on `file://` (this broke the existing file:// suite, see below);
`npm run build` copies `vendor/` into `dist/vendor/`. No network at runtime or
build time; no ffmpeg.wasm.

## Codec support (measured, `docs/evidence/v2/codec-support.json`)

`VideoEncoder.isConfigSupported` / `AudioEncoder.isConfigSupported`, exact
codec string and size:

| Browser | H.264 1280×720 | H.264 1920×1080 | H.264 3840×2160 | VP9 | VP8 | AAC encode | Opus encode |
|---|---|---|---|---|---|---|---|
| Firefox 1555 | yes | yes | yes | yes | yes | **no** | yes |
| Chromium 1248 | yes | yes | **no** | yes | yes | **no** | yes |

Consequences, all visible in the app:

- Chromium 4K video: the MP4 option stays in the list, is disabled, and
  `#export-format-note` shows "This browser cannot encode H.264 at
  3840×2160. Choose WebM instead." No codec substitution inside `.mp4`.
- AAC cannot be encoded by either browser. A source with audio shows
  `#export-audio-note` ("Audio is not included in exported videos: …") and the
  exported file has no audio stream. It is not dropped silently.

## Implementation

- `exportVideo()` renders frames deterministically: for each of
  `round(duration × 30)` frames it seeks the source, draws it through
  `prepareBase` + `renderToContext` at the output size (all enabled effects),
  wraps the canvas in a `VideoFrame`, and feeds `VideoEncoder`.
- The output size is `computeOutputSize(...)` with even width/height for H.264
  (`evenSize`); the default preset is Original (native, rotation-aware).
  Bitrate scales with output area, capped at 40 Mbit/s.
- MP4 uses `fastStart: "in-memory"`, so the box order is `ftyp, moov, mdat`
  (verified in every MP4 cell). WebM sets duration and cues (seekable; verified
  by extracting `\x1c\x53\xbb\x6b`).
- Progress shows format, frames done of total, elapsed, estimate and a Cancel
  button; Cancel sets a flag, the loop stops after the current frame, no
  download is produced, and the busy flag clears.
- The preview is paused, loop and playhead are restored afterwards; loading a
  new file while an export runs cancels it instead of wedging the app.
- `Export Frame (PNG)` is a separate action that writes one full-size still.
- Starting an export expands a peeked mobile sheet to half and scrolls the
  progress panel into view, and the panel/Cancel carry
  `scroll-margin-top` 76 px (68 px on the sheet). Without that, at 700 px the
  61 px peek viewport is filled by the sticky action bar and Cancel cannot be
  reached (break-it evidence below).
- The existing still-image **WebM Video** export (used by G5) was rebuilt on the
  same pipeline: 30 deterministic frames at 30 fps, VP9, 0.966 s, 418,616 bytes
  for the 900×600 fixture, clean decode.

### Firefox MP4: decode order and the 67 ms shift

Firefox's H.264 encoder emits chunks in decode order with presentation
timestamps out of order. Sorting them before muxing corrupted the stream
(`sps_id 1 out of range`, `illegal short term buffer state`; see
`g22-firefox-050102.json`). Two measured fixes:

1. Mux in arrival order. DTS = frame index × frame duration; PTS =
   `chunk.timestamp + delay`, where `delay` is the largest reorder distance
   (67 ms for the 180-frame clip), written as `ctts`. `mp4-muxer` rejects
   negative DTS, so the timeline is shifted instead of using an edit list.
2. Firefox duplicates the first byte of each parameter set in
   `decoderConfig.description`; the `avcC` is rebuilt from the in-band SPS/PPS
   (`avcCFromChunk`) instead (50-byte box, one SPS + one PPS, verified).

After the fix a full `ffmpeg -i file -f null -` decode of the final Firefox MP4
has zero stderr lines, `nb_frames=180`, duration 6.0. Chromium's MP4 has
`has_b_frames=0` and `start_time=0`; Firefox reports `has_b_frames=2` and
`start_time=0.0667` (see Limits).

Chromium tags an sRGB canvas as full range, so ffprobe reports `yuvj420p`.
The gate accepts `yuv420p`/`yuvj420p`: same 4:2:0 layout, different range tag
from the canvas input. Firefox reports `yuv420p`.

## Evidence: G22 export subset (real UI, both browsers)

`docs/evidence/v2/export-final-chromium.log`,
`export-final-firefox.log`: **16 checks, 0 failures** each, including the two
audio checks and the two 700 px Cancel checks. Covered: real MP4 and WebM from the playhead (playhead
2.8 s, file still 6.0 s), decoded frame count, duration, seek at 2.5 s and
5.6 s, MP4 fast start, progress + Cancel, Export Frame, audio note, cancel
cleanup, restore.

## Evidence: size / preset matrix

Tool: `tools/v2_export_matrix.py` (drives the real UI, saves the download,
probes it). Sources: 2 s clips for 720p/1080p/portrait/rotated, 1 s for 4K.
`docs/evidence/v2/matrix-chromium-164828.json`,
`matrix-firefox-170230.json` (re-run on the final loader); decoded frame counts
re-probed from the saved
files in `matrix-decoded.json`; the Chromium memory re-run and current `dist`
build are in `matrix-chromium-061834.json`.

Every cell: seek at 35 % and 80 %, three extracted frames with effects
(effects diff vs the source 27–44 greyscale levels), and distinct frames.

### chromium

| Cell | Size | Codec | pix_fmt | Frames | Duration | Seek | Fast start / cues | Effects diff | Export s |
|---|---|---|---|---|---|---|---|---|---|
| custom-640x360-contain-mp4 | 640x360 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 27.54 | 37.1 |
| custom-640x360-contain-webm | 640x360 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 27.59 | 37.3 |
| custom-640x360-cover-mp4 | 640x360 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 27.54 | 38.4 |
| custom-640x360-cover-webm | 640x360 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 27.59 | 37.7 |
| custom-640x360-stretch-mp4 | 640x360 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 27.54 | 37.0 |
| custom-640x360-stretch-webm | 640x360 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 27.59 | 36.5 |
| dist-1280x720-mp4 | 1280x720 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 29.03 | 40.2 |
| dist-1280x720-webm | 1280x720 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 29.05 | 40.1 |
| orig-1080x1920-original-mp4 | 1080x1920 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 29.87 | 52.2 |
| orig-1080x1920-original-webm | 1080x1920 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 29.91 | 53.3 |
| orig-1280x720-original-mp4 | 1280x720 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 29.02 | 38.8 |
| orig-1280x720-original-webm | 1280x720 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 29.05 | 39.6 |
| orig-1920x1080-original-mp4 | 1920x1080 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 30.91 | 50.9 |
| orig-1920x1080-original-webm | 1920x1080 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 30.94 | 51.8 |
| orig-3840x2160-original-mp4 | 3840x2160 | — | — | — | — | — | — | — | skipped: no H.264 at 4K |
| orig-3840x2160-original-webm | 3840x2160 | vp9 | yuv420p | 30 | 0.966 | yes | yes | 30.89 | 38.7 |
| orig-rotated-original-mp4 | 1080x1920 | h264 | yuvj420p | 60 | 2.0 | yes | yes | 37.18 | 53.2 |
| orig-rotated-original-webm | 1080x1920 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 37.18 | 53.6 |

### firefox

| Cell | Size | Codec | pix_fmt | Frames | Duration | Seek | Fast start / cues | Effects diff | Export s |
|---|---|---|---|---|---|---|---|---|---|
| custom-640x360-contain-mp4 | 640x360 | h264 | yuv420p | 60 | 2.0 | yes | yes | 32.59 | 39.5 |
| custom-640x360-contain-webm | 640x360 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 32.61 | 43.1 |
| custom-640x360-cover-mp4 | 640x360 | h264 | yuv420p | 60 | 2.0 | yes | yes | 32.59 | 39.4 |
| custom-640x360-cover-webm | 640x360 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 32.61 | 43.1 |
| custom-640x360-stretch-mp4 | 640x360 | h264 | yuv420p | 60 | 2.0 | yes | yes | 32.59 | 38.9 |
| custom-640x360-stretch-webm | 640x360 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 32.61 | 43.7 |
| dist-1280x720-mp4 | 1280x720 | h264 | yuv420p | 60 | 2.0 | yes | yes | 34.98 | 42.0 |
| dist-1280x720-webm | 1280x720 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 35.01 | 53.3 |
| orig-1080x1920-original-mp4 | 1080x1920 | h264 | yuv420p | 60 | 2.0 | yes | yes | 37.01 | 58.3 |
| orig-1080x1920-original-webm | 1080x1920 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 37.06 | 80.8 |
| orig-1280x720-original-mp4 | 1280x720 | h264 | yuv420p | 60 | 2.0 | yes | yes | 34.98 | 41.3 |
| orig-1280x720-original-webm | 1280x720 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 35.01 | 54.3 |
| orig-1920x1080-original-mp4 | 1920x1080 | h264 | yuv420p | 60 | 2.0 | yes | yes | 38.03 | 55.4 |
| orig-1920x1080-original-webm | 1920x1080 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 38.03 | 77.2 |
| orig-3840x2160-original-mp4 | 3840x2160 | h264 | yuv420p | 30 | 1.0 | yes | yes | 36.61 | 45.7 |
| orig-3840x2160-original-webm | 3840x2160 | vp9 | yuv420p | 30 | 0.966 | yes | yes | 36.61 | 91.0 |
| orig-rotated-original-mp4 | 1080x1920 | h264 | yuv420p | 60 | 2.0 | yes | yes | 43.8 | 56.6 |
| orig-rotated-original-webm | 1080x1920 | vp9 | yuv420p | 60 | 1.966 | yes | yes | 43.81 | 78.2 |

The rotated source is a 1920×1080 stream with a 90° display matrix; both
browsers report it as 1080×1920 and both export a 1080×1920 file.

The three Fit cells use a 16:9 source into 16:9 640×360, so their pictures are
identical by construction; they prove each Fit option exports at the requested
size. Fit itself is the existing image behavior (`computeOutputSize` ignores
`fit`; the image base is stretched), which V4 audits for images and video.

## Peak memory (Chromium, `matrix-chromium-061834.json`)

| Clip | Output | Frames | JS heap peak | Browser RSS base → peak |
|---|---|---|---|---|
| 1920×1080, 2 s | WebM 2.6 MB | 60 | 32 MB | 727 MB → **1,432 MB** (Δ 705 MB) |
| 3840×2160, 1 s | WebM 3.8 MB | 30 | 32 MB | 1,336 MB → **2,437 MB** (Δ 1,101 MB) |

RSS is the sum of VmRSS over the six Playwright browser processes; it includes
the decoded source, canvases, effect scratch and the encoder. The output file
itself is small, so `ArrayBufferTarget` is not the driver. Both exports
succeeded, so the 850 MB source limit is not changed by this measurement.
Firefox has no `performance.memory`; its memory is not claimed (HUMAN-CHECK).

## Export cost (the seek is the floor)

A 6 s 4K source exported at 640×360 took **281 s** for 180 frames, because
every frame seeks a 4K VP9 source (~1.5 s) even though the output is small.
The progress estimate stayed within ~2× of the real time. This is cost, not a
correctness defect, and is reported for V5 planning.

## G21 rule change (size, measured before/after)

Section 3 replaces "video export is always native" with "default Original;
presets, Custom and Fit apply when chosen".

| Assertion (per fixture) | Before (V1) | After (V2) |
|---|---|---|
| landscape, portrait, 4K, odd | `export <label> equals native`, preset deliberately 320×180 and must be **ignored** | `export <label> keeps native <w>x<h> with Original` |
| new | — | `export <label> uses the custom preset 320x180` |
| rotated | `equals displayed native size` | `keeps displayed native size` + `uses the custom preset 320x180` |

The native assertion is kept, not weakened; six preset assertions are added.
G21 went from 25 to **31 checks, 0 failures** (`g21-31-checks.log`).

## Gate findings fixed in V2

The first three full gate runs exposed two regressions in the new export path.
Both are fixed and re-measured.

### 1. `file://` could not load the muxers (G5)

The first runs failed G5 with `export webm Timeout 90000ms` and

```
Access to script at 'file:///…/vendor/webm-muxer.mjs' from origin 'null' has
been blocked by CORS policy
```

A dynamic `import()` of a file URL is blocked under `file://`, and the existing
suite runs the app from `file://` (it is a static site with no server). The
image → WebM action failed the same way. Fix: `tools/vendor_muxers.py`
generates classic-script `vendor/mp4-muxer.js` / `webm-muxer.js` from the
upstream `.mjs` files (only the final export block changes, into a window
global), and `loadMuxer()` injects the needed one on demand. Classic scripts
are not blocked by the file origin.

After: `docs/evidence/v2/g5-file-fix.log`, **170 checks, 0 failures**
(`export webm 416111 bytes, magic=ok`, `zero console errors []`).

The first classic build was still wrong: both files declared their top-level
names with `var` (`Target`, `ArrayBufferTarget`, `Muxer`, …), so loading
`mp4-muxer.js` after `webm-muxer.js` rebound `Target`, and the WebM muxer
rejected its own target with *"The target must be provided and an instance of
Target."* The G22 export subset caught it: 16 checks, 4 failures, because the
audio export runs after MP4. A probe confirmed both globals existed and
`instanceof` was false. Fix: `tools/vendor_muxers.py` wraps each generated file
in an IIFE, so its names stay local and only `window.Mp4Muxer` /
`window.WebmMuxer` escape. Probe after the fix: both muxers construct in the
same page; G22 export subset **16 checks, 0 failures** in Chromium and
Firefox.

### 2. Per-frame seek listeners looked like a leak (G13)

G13's `replacing the source keeps one listener set` failed on all three runs:
`first=67 last=7`. The export seeks once per frame and added a
`{once: true}` `seeked` listener each time. The browser removes those
listeners itself, but the test's tracker only observes
`removeEventListener`, so 60 finished seeks still counted as live. They were
not a real leak, but the bookkeeping was unclear and the test could not tell.

Fix: `seekVideoFrame()` now removes the listener and clears its 3 s timeout
explicitly in `finish()`.

After: `docs/evidence/v2/g13-listener-fix.log`, **27 checks, 0 failures**,
`first=7 last=7 ids=[1, 2, 3] totalTracked=42`.

## Gate runs

`GATE_TASK=v2 npm run gate` three times in a row on the final tree
(2026-11-16): 14:09–14:54, 14:54–15:42, 16:02–16:48. Every run: G1–G21 PASS,
G5 `170 checks, 0 failures`, G13 `27 checks, 0 failures`, G20 `200 cases, 0
problems`, G21 `31 checks, 0 failures`. G22: Chromium `32 checks, 4 failures`
each run; Firefox `32 checks, 4/5/4 failures`, the extra one in run 2 being the
V5 4K compare-drag hitch. The reds are V3 (three seek checks), V4 (size
controls enabled) and that V5 hitch; no V2 sub-check is red.

Logs: `gate-run1.log`, `gate-run2.log`, `gate-run3.log`. Three earlier attempts
are kept as `gate-attempt{1,2,3}.log`; attempt 1 had the known flaky G13
two-effect timing failure and does not count.

## Limits / HUMAN-CHECK

- **Audio** is not in the exported file: neither browser can encode AAC
  (measured). The UI note and the README Limits entry are the visible record.
  Opus encoding is available but the container/player requirement is AAC, and
  an `.mp4` must not silently contain another codec.
- **Chromium 4K H.264** is unsupported in this build; MP4 is offered and
  disabled with a visible reason at that size. Firefox encodes 4K H.264.
- **Firefox MP4 start offset**: the encoder's B-frame reordering plus the
  muxer's non-negative DTS rule shift the presentation timeline by 67 ms
  (`start_time=0.0667`, 180 frames, duration 6.0). All frames decode cleanly;
  the first two frame slots are empty and the last two presentation times sit
  at 6.0/6.033 s. Chromium MP4 starts at 0. This is a container-metadata
  limitation of the vendored muxer (it writes no edit list), not a lost frame.
- Real GPU/Zen encode speed, real Safari, and player-specific start behavior
  are not claimed; all numbers are headless.
- Firefox memory is not measured (no `performance.memory`).
- The owner's real 4K camera files are not available here; the matrix uses
  generated VP9/H.264 clips.

## Files changed

Runtime: `app.js`, `index.html`, `style.css`. Build: `tools/build.py` copies
`vendor/`. Tests: `tests/gate/video_real_flow.py` (G22 export subset + audio
fixture), `tests/gate/video_p2_3_check.py` (G21). Tools:
`tools/v2_export_matrix.py`, `tools/v2_decoded_frames.py`,
`tools/codec_probe.py`, `tools/vendor_muxers.py`,
`tests/bench/breakit_v2.py`. Vendored: `vendor/mp4-muxer.mjs`,
`vendor/webm-muxer.mjs` (upstream), the generated `vendor/*-muxer.js`
classic scripts, licences, README.
Evidence: this directory.

## Break-it (11 cases, Chromium)

Tool: `tests/bench/breakit_v2.py`; final run 2026-11-15,
**11 checks, 0 failures** (`docs/evidence/v2/breakit.log`,
`breakit.json`). Every case must leave the app usable, no stuck busy flag, no
unhandled page error, and the expected number of downloads.

| Check | Result | What it proves |
|---|---|---|
| a missing muxer reports a failure and unlocks the app | PASS | a blocked muxer script shows a toast, clears the busy flag and re-enables Export |
| cancel before the first frame leaves no download | PASS | no download, no stuck panel |
| export works again right after a cancelled 4K export | PASS | the second export downloads a 180-frame file |
| format switch mid-export keeps the started format | PASS | the started format is the one written |
| theme toggle changes the theme | PASS | dark → light |
| theme toggle leaves the export UI and export working | PASS | the export UI and a later export still work |
| Export Frame cannot interrupt a running video export | PASS | the still action cannot interrupt or produce a second file |
| progress and Cancel fit the 700 px layout | PASS | panel and Cancel are inside the viewport (see below) |
| loading a new video mid-export leaves a usable app | PASS | the running export is cancelled and the new video is usable |
| export with no source is a clean no-op | PASS | no download |
| no page or console errors | PASS | only the deliberate muxer abort was logged, recorded as that case's expected error |

The blocked-muxer case deliberately aborts the `vendor/webm-muxer.js` request,
so the browser logs one `Failed to load resource: net::ERR_FAILED` console
error. The scan records it as the expected error of that case and checks every
later case separately, rather than ignoring console errors in general.

### The 700 px defect this found

At 700 px the sheet's peek is 105 px: the handle plus the sticky action bar
fills the whole 61 px scroll viewport. `page.click("#export-cancel")` timed out
on "Reset All intercepts pointer events", then "element is outside of the
viewport" — the progress panel sat at y=7,762. Keyboard focus to Cancel was
hidden under the same bar.

Fix (`revealExportProgress`): starting an export expands a peeked sheet to half
and scrolls the progress panel into view; the panel and Cancel carry
`scroll-margin-top` 76 px (68 px on the sheet). After: panel 774–847, Cancel
774–818, hit test returns `export-cancel`, keyboard focus `cancelTop 732 >
barBottom 601`. Two permanent G22 checks now guard it (visible/clickable at
700 px, and the tap stops the export).
