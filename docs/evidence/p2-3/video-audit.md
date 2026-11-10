# P2-3 Task B1: current video flow

Read on the pre-change tree (`df4365d`, Step 3 tagged). This records what the
code does today, before the 850 MB and native-resolution changes.

## Where the 40 MB rule lives

| Location | Text / value |
|---|---|
| `app.js:1381` | `const MAX_FILE_BYTES = 40 * 1024 * 1024;` |
| `app.js:1410-1411` | one size check for both images and video; message `This file is too large (X). Try a smaller file (under 40 MB).` |
| `app.js:1407` | unsupported-type message mentions PNG/JPG/WebP and WebM/MP4 |
| `app.js:1456` | video decode failure message mentions MP4 (H.264) / WebM (VP9) |
| `index.html` drop area | says `Drop an image or video here…`; no size text |
| `README.md:148` | `Images … and videos … up to **40 MB** are accepted` |
| `tests/test_suite.py:1039-1046` | calls `showDropError` with the 40 MB sentence and asserts `40 MB` |
| `tests/test_suite.py:619` | exports a still image as WebM among the six formats |

There is no separate video constant and no 850 MB string anywhere yet.

## How the file is read

`loadFile()` (`app.js:1399-1491`) does **not** read the file. It validates
`file.type` and `file.size`, creates `URL.createObjectURL(file)`, and assigns
that URL to a new `<video>` or `<img>`. There is no `FileReader`, no
`Blob.arrayBuffer()`, no `Blob.text()`, no base64 data URL and no `fetch` on the
file. The object URL is revoked when a replacement source is installed or on a
decode error. An 850 MB object URL therefore costs metadata plus the browser's
own demux/decode buffers, not an 850 MB JS buffer.

## Playback

- `<video>` is `muted`, `playsInline`, `loop` (`app.js:1428`).
- `loadedmetadata` installs `state.video`, reads `videoWidth`/`videoHeight`,
  clears the stage cache, invalidates the worker, and starts the loop
  (`app.js:1431-1452`).
- `startVideoLoop()` (`app.js:1554-1582`) prefers
  `requestVideoFrameCallback`; otherwise it uses rAF. It renders only when the
  video is playing, not exporting and the document is visible.
- `PLAYBACK_MIN_INTERVAL` and `adaptPlaybackScale()` bound frame cost by
  lowering the preview scale after slow frames. The baseline measured 16.7 ms
  per frame at 0, 3 and 6 effects on both 1080p and 4K fixtures.
- `stopVideoLoop()` cancels the rAF and `cancelVideoFrameCallback` handles.
- When paused, the app schedules one still render; there is no idle rAF loop.

## Export today

`exportVideo(full, opts)` (`app.js:1707-1763`):

1. Requires `window.MediaRecorder`; otherwise `alert()`.
2. Sets `state.videoExporting` and `state.exportProgress`.
3. Creates a canvas at the **passed `full` size** and a 2D context.
4. Reads `video.duration`, clamps it to **20 s**, and uses a fixed **24 fps**;
   `total = ceil(duration * 24)`.
5. Pauses the video, rewinds to 0, creates `canvas.captureStream(24)` and a
   `MediaRecorder` (`video/webm;codecs=vp9` when supported).
6. For each frame: seeks to `i / 24`, waits for `seeked` or 120 ms, calls
   `prepareBase` + `renderToContext` at `full.w`/`full.h`, and waits
   `1000 / 24` ms.
7. Stops the recorder, saves the blob as `glyphcraft.webm`, restores the
   previous play state, and resolves.
8. Recorded chunks are kept in an in-memory `chunks` array until `onstop`.
   Nothing is written to disk or streamed during the export.
9. `exportImage()` passes `full` from `computeOutputSize(...)`
   (`app.js:1665`), i.e. the **preview/export size controls**, not
   `video.videoWidth` × `video.videoHeight`. With the default `original`
   preset that happens to equal the source; any size preset, fit or custom
   width/height changes the exported video. This is bug B3 and the reason for
   Task B.
10. Audio: the captured stream comes from the canvas only, so exported WebM has
    no audio track. The source video is muted during playback. This is current
    behavior and is not changed silently.
11. Cancel: there is no cancel control. `state.videoExporting` only gates a new
    export and some UI; loading a new file during an export is not blocked
    (`loadFile()` does not check it), so the running loop would keep reading
    `state.video` while the source changed. Recorded as a break-it case; not
    silently changed in Task B.
12. Tab hidden: the export loop uses timers and seeking, not rAF, so it
    continues while hidden; `videoIsPlaying()` is suppressed by
    `state.videoExporting`.

## What Task B changes

- Split `MAX_FILE_BYTES` into one image constant (40 MB, unchanged) and one
  named video constant (850 MB).
- Reject 0-byte files with a clear message before decode.
- Keep the size preset, width, height, fit and lock controls visible for video
  but disabled, with an inline note that video exports at the source
  resolution.
- Use `video.videoWidth` × `video.videoHeight` for the export canvas regardless
  of the size controls, and fail clearly if that exceeds the browser canvas
  limit.
- Keep 24 fps, the 20 s clamp, no audio and the existing progress behavior
  unchanged, and report them.

## Test plan for B3

- Boundary: 850 MB exactly accepted, +1 byte rejected, 40 MB image boundary
  unchanged, 0 byte rejected, with mocked size objects (no huge real file).
- Whole-file read: instrument `FileReader`, `Blob.prototype.arrayBuffer`,
  `Blob.prototype.text` and `window.fetch`; a video load must make 0 calls.
- ffprobe export sizes: 1920x1080, 1280x720, 3840x2160, portrait 1080x1920 and
  odd 1002x562, with a non-original size preset selected so the old clamp would
  fail. Rotated phone video if the container/browser supports it; otherwise
  HUMAN-CHECK.
- One ~840 MB real file at closeout: `tests/gate/video_large.py`, load, 3
  effects, play, seek, short export, ffprobe, delete the fixture.
- H.264: check whether this Chromium decodes it; if not, use VP8/VP9 WebM
  fixtures and mark MP4/H.264 as HUMAN-CHECK.

## After Task B (implemented)

- `IMAGE_MAX_FILE_BYTES = 40 * 1024 * 1024` and
  `VIDEO_MAX_FILE_BYTES = 850 * 1024 * 1024` are separate top-level constants.
  `fileSizeError(file)` picks the limit from `file.type` and also rejects
  `size === 0` with `This file is empty. Choose a file with content.`
- Messages use the exact limit (`under 40 MB`, `under 850 MB`) rather than
  `formatBytes` decimals.
- `syncOutputControls()` disables the preset trigger, width, height, fit and
  lock-ratio controls for a video source, keeps them enabled for an image, and
  shows `#output-video-note` with
  `Video exports at the original resolution. Size controls are disabled for video.`
- `exportVideo()` overrides the passed size with
  `video.videoWidth` × `video.videoHeight`, so no preset, fit or custom size can
  change the exported video. The browser applies rotation metadata to those
  values; the rotated fixture exports at the displayed size.
- `videoExportSizeError(w, h)` rejects a zero side, a side over 65,535 px, an
  area over 268,435,456 px, or a canvas the browser cannot give a 2D context.
  `exportVideo()` shows the message as a toast and leaves the export state
  clean instead of silently downscaling.
- Frame rate (24), the 20 s clamp, no audio, in-memory chunks and the lack of a
  cancel control are unchanged.
- H.264/MP4 does decode in the Playwright Chromium when served over HTTP, so
  the export fixtures are H.264 MP4. Rotation metadata was generated with
  `ffmpeg -display_rotation 90 -noautorotate` and Chromium reports the rotated
  display size (1920x1080 for a coded 1080x1920 stream).

### RED → GREEN

- RED: `video-p2-3-red.log` — `ReferenceError: IMAGE_MAX_FILE_BYTES is not
  defined` before the split.
- GREEN: `video-p2-3-green-3.log` — 25 checks, 0 failures, every check line
  printed with its evidence. The final gate run is G21 (`g21-run.log`, 52.6 s
  standalone). `video-p2-3-green-2.log` is the earlier run of the same 25
  checks before the per-line PASS output was added.
- Covered sizes (ffprobe = browser native): 1920x1080, 1280x720, 3840x2160,
  1080x1920, 1002x562 and the rotated 1080x1920 stream. All five plain cases
  were exported with the preset deliberately set to `custom 320x180`, proving
  the controls no longer decide the video size.
- Whole-file read instrumentation: `FileReader` (all four read methods),
  `Blob.arrayBuffer`, `Blob.text`, `Blob.stream` and `fetch` recorded 0 calls on
  the video load.
- 169-test suite green; G20 golden 200/200 exact; dist smoke hash 4135467496.
  Logs: `test-suite-step4.log`, `golden-check-step4.log`, `build-step4.log`,
  `video-check-step4.log` (existing 25-check video gate still green).

### Closeout: one real 838 MB video

`tests/gate/video_large.py` (not in the normal gate; it generates and exports
hundreds of MB) ran once on a real 3840x2160 lossless VP9 WebM:
`video-large.log`, 7 checks, 0 failures.

| Check | Result |
|---|---|
| File under the limit | 878,759,144 bytes (838.1 MB) of the 891,289,600 (850 MB) limit |
| Load | 0.70 s, browser reports 3840x2160, duration 2.75 s |
| Whole-file JS read | 0 calls (`FileReader`, `Blob.arrayBuffer/text/stream`, `fetch`) |
| Peak JS heap during load | 10.0 MB before, 10.0 MB peak, +0.0 MB |
| Playback with 3 effects | 101 frames in 2.01 s (50.3 fps) |
| Seek to 1.50 s | landed at 1.50 s |
| Export with preset `custom 320x180` | ffprobe 3840x2160, 107.9 s, 2.2 MB |
| Page/console errors | none |

The fixture and the exported file are deleted at the end of the run. The 0.0 MB
JS-heap delta is the point: the app never holds the file. The browser's own
demux/decode memory is outside `performance.memory` and is not measured here.

