Load skills: using-rigor-skills, rigor-gate, verify-before-claim, root-cause-debugging, test-first, perf-measure, code-audit, ui-visual-audit, namethatui, performance-optimization, webapp-testing. If a skill is not installed, skip it and say so in one line. Do not install anything.

# Glyphcraft - VIDEO FIX ROUND (tasks V0 to V5)

Repo: ~/glyphcraft. First action: save this file verbatim as docs/prompts/p2_3_video_fix.md.

---

## 1. Summary (read this first)

P2-3 was closed as PASS (tag P2-3-pass, commit 69f4b95, gate G1-G21 green three times). The owner then tested VIDEO by hand in his real browser and it is broken. So the gate did not test the real video flow. This round does two things:

1. Fix the real video behavior.
2. Add a gate check (G22) that drives the REAL UI, so this cannot happen again.

What must work when this round is finished:

| # | Requirement | Task |
|---|-------------|------|
| 1 | Video frames look the same quality every time: no random blocky or striped frames | V1 |
| 2 | Export on a video produces a real, playable video of the WHOLE clip, with effects on every frame. Formats: MP4 and WebM | V2 |
| 3 | Video control bar: play/pause, seek bar, jump back, jump forward | V3 |
| 4 | Default export size = the uploaded video's own size. The Size Preset / Fit / Lock Ratio / Custom controls stay and are usable with video | V4 |
| 5 | Big images with 6+ effects do not freeze when dragging sliders or the compare split | V5 |

Important about the test browser: the owner uses Zen, which is Firefox-based. Chromium headless alone is NOT enough. Every video check in this round must run in BOTH Playwright Chromium and Playwright Firefox. Real GPU and real device results stay HUMAN-CHECK.

---

## 2. What the owner reported (symptoms, not causes)

1. Export on a video gives ONE still image (the current frame), not a video.
2. Preview is unstable. With a few effects, some frames look good and some are pixelated, blocky or striped. It alternates randomly.
3. There is no seek control. He wants a video control bar with a seek bar, jump backward and jump forward.
4. Video export must be at the same resolution as the uploaded video. No new resolution control. The existing Output dimension controls must stay and must work with video. Today they are greyed out when a video is loaded.
5. He wants MP4 export (in addition to WebM).
6. Secondary: on large images with 6+ effects, dragging sliders or the compare split still freezes for a moment.

### Owner screenshots

The owner copies these four files into docs/ref/ before the session. Open all four and describe each one in your report.

- docs/ref/v1-paused-clean.png: video paused (play icon), zoom 79%, status 79% | 1366x768 | 244ms. The frame looks clean.
- docs/ref/v2-playing-chunky.png: the same video playing (pause icon), status 15ms. The frame is low-resolution: big blocky pixels and colored dither-like noise.
- docs/ref/v3-oil-striped-112.png: zoom 112%, status 1767ms, Oil Paint checked (Radius 3). Vertical colored stripes and noise.
- docs/ref/v4-output-disabled.png: Output section with a video loaded. Format shows PNG. Size Preset shows Original but is greyed out. Fit shows Contain but is greyed out. Lock Ratio is checked. A red arrow marks the greyed-out Size Preset and Fit.

Only some effect cards are visible, so the exact enabled effect stack is UNKNOWN. Do not assume it. The three different status times (15 ms, 244 ms, 1767 ms) are also symptoms you must explain.

---

## 3. Locked owner decisions (do not ask again)

- Video export default = the uploaded video's native pixel size. Size Preset default is "Original".
- Size Preset, Fit, Lock Ratio and Custom stay available for video. If the owner picks a preset other than Original, the export uses that size with the chosen Fit mode. If Original is selected, the export is native size.
- This REPLACES the P2-3 rule "video export is always native size, even with a custom preset". The owner asked for the change. Record old rule, new rule and the reason in docs/GATE.md. Keep the G21 native-size assertions for the Original case and add new assertions for the preset case. Show the before and after assertions in GATE.md. This is a deliberate rule change, not a weakened test.
- No new resolution control. Reuse the existing Output controls.
- Export formats for video: MP4 and WebM. MP4 is REQUIRED (details in V2). Do not drop it because it looks hard.
- English only. No Arabic anywhere in the repo (G6). All CSS variables stay namespaced --gc-*. No explanatory comments in app code (short section markers are allowed). Light and dark themes must both pass. Menus keep the inverse theme.
- Do not start P2-4. Do not change the phone layout except to make the new video bar usable at 700 px and below (see V3).

---

## 4. Rules for every task

- Source of truth is git, tags, code, README and docs/GATE.md. If docs/PROJECT_MEMORY.md disagrees, git wins.
- Start: run git status -sb, git log --oneline -10, git tag --list "*-pass", git stash list. Read README.md, the tail of docs/GATE.md and docs/PROJECT_MEMORY.md.
- Test first. For each task: write the check, run it, see it RED, fix, see it GREEN. Keep the RED logs in docs/evidence/<task>/.
- Never weaken a test or threshold. The test count only goes up (G5 is currently 170). A gate rule may change only when a check measures the machine and not the app. Show the numbers first and record it in docs/GATE.md.
- Find the ROOT CAUSE. Do not patch symptoms. Prove each cause with a measurement or a failing test.
- Optimise only by measurement. Keep only changes that measure faster. Record before and after numbers.
- npm run gate takes about 30 minutes. Run it in the background and poll the log. Never interrupt it. After each task that changes runtime code, run it 3 times in a row, one after the other. Every run must end GATE PASS.
- Open and describe every screenshot the gate produces. For each task list at least 8 ways it could still break (break-it list) and run them.
- One commit and one tag per task: V0-pass, V1-pass, V2-pass, V3-pass, V4-pass, V5-pass. Push the branch and the tags after each.
- After three failed attempts on one task, mark it BLOCKED and report. Do not loosen anything.
- Do not ask the owner questions. Find bugs yourself. If you are truly blocked, ask ONE question with numbered options; the last option is "Other: I'll type it".
- Allowed states: PASS, FAIL, BLOCKED, HUMAN-CHECK. Never claim anything you did not run.
- No network downloads at runtime. The site is static and offline-capable. If you need a third-party library (for example an MP4 muxer), vendor one small permissively licensed source file into the repo (for example under assets/vendor/), keep its license text next to it, include it in npm run build, and say exactly what you added and why.
- After each runtime change run npm run build and python tools/dist_smoke.py. Both must pass. The Worker and the new export code must also work from dist.

---

## 5. Tasks

### V0 - Evidence and real-flow reproduction (no app code changes)

1. Audit the whole video path: file load, playback loop, per-frame render, worker eligibility, preview source, export button, format list, Output controls enable/disable logic. List every function and file with line references.
2. Make test videos with ffmpeg (no network): a moving, high-detail clip (testsrc2 plus a moving pattern, 6 s, 30 fps) at 1920x1080, 1280x720, 1080x1920 and 3840x2160, WebM VP9. Generate them in the test fixtures code. Do not commit large binaries.
3. Write tests/gate/video_real_flow.py. It drives the REAL UI in Chromium AND Firefox: load a video, enable effect stacks (a light stack of 2 effects and a heavy stack of 6+ including Oil Paint), in Dither, Script and Effects Only modes; play, pause, seek, zoom, resize the window, click the real Export button, and check the produced file. Record status-bar render times and canvas frame hashes over time.
4. Reproduce each owner symptom with a RED result. Save logs in docs/evidence/v0/. If a symptom does not reproduce, say exactly which browser and settings you tried.
5. Explain why G1-G21 stayed green while these bugs existed: for each symptom, name the check that should have caught it and what that check really asserts.
6. Add the real-flow check to the gate as G22. It is expected to be RED until V5. Write in docs/GATE.md that G22 is intentionally RED until V5. No task may be tagged PASS while its own G22 sub-checks are RED.

Done when: all symptoms are reproduced or honestly explained, and each cause is listed as a hypothesis with the measurement that will confirm or reject it. Commit docs, tests and evidence. Tag V0-pass for the evidence and the RED proof only.

### V1 - Unstable and pixelated frames

Goal: every frame of a playing, paused or seeked video has the SAME quality as a still-image render of that same frame at the same preview size and settings. Quality never changes inside one session unless the owner changes a setting.

Check at least these hypotheses and confirm or reject each with a measurement:
- The P2-2 main-thread preview ImageBitmap (state.previewSource) is stale, taken once, or taken at a reduced size for video.
- Playback switches to a reduced-resolution path depending on render time (adaptive quality, frame skipping that also lowers resolution, a cached stale frame).
- The Worker path and the synchronous path alternate for video, or a frame is drawn from the wrong source.
- The video frame is read before it is decoded (seek race, requestVideoFrameCallback missing or misused).
- Random or time-seeded effects look like instability.
- Oil Paint and other heavy effects cost over 1 second per frame and cause dropped frames and half-updated canvases.

Required behavior:
- Parity test: for at least 20 timestamps spread over the clip, including the first and last frame, seek, let the render settle, then the preview canvas hash must equal the hash of a fresh still render of that same decoded frame with the same settings and size. It must hold while paused, after a seek, and after playback stops. Run in Chromium and Firefox.
- During playback, if the pipeline cannot keep up, the app drops frames or slows playback. It must NOT change render resolution or quality. Every frame it shows must pass the same parity rule.
- Intended effect looks (dither patterns, halftone, glitch) are not bugs. Prove which patterns are intended by rendering the same frame as a still image.
- Use a deterministic effect stack for hash parity (exclude random effects, like P2-2 did). Test random effects only for stable settings.
- Explain the 15 ms, 244 ms and 1767 ms status times with measurements: what each number measures and why they differ.

Done when: parity tests are GREEN in both browsers, three gate runs are green, screenshots of the same moving clip are taken in light and dark at 360 and 1280 widths, and the break-it list is run.

### V2 - Export must produce a real video (MP4 and WebM)

Goal: Export on a video produces a playable video file of the whole clip with all enabled effects applied to every frame.

UI:
- When a video is loaded, the main button says Export Video. The Format list shows video formats: MP4 and WebM. A still-image format must never turn a video into a single frame.
- Exporting the current frame as an image stays available as a separate, clearly named action ("Export Frame"). It is not the default and is not inside the video format list.

Output rules:
- The file covers the full duration from start to end, no matter where the playhead is or whether the video is playing or paused. The preview state is restored afterward.
- The result must not depend on live playback speed. If one frame takes 1.7 seconds to render, the file still contains every frame. Prefer deterministic frame-by-frame rendering (seek, render, encode) over real-time capture. Choose the method by measurement, in Firefox first, and state what you chose and why.
- Frame count must equal duration times frame rate within one frame.
- Size follows section 3. H.264 needs even width and height: round the output size to even numbers and show the real final size in the UI.
- Audio: if the source has an audio track, keep it. If it is truly impossible in the owner's browser, do NOT drop it silently: show a visible note in the UI and list it under Limits in the README.
- Progress and cancel: show progress (frames done of total, elapsed time, estimate) and a Cancel button. Cancel leaves the app clean: no partial download, no stuck busy flag.
- Memory: write the output in a streaming way where possible. Report peak memory for a 1080p clip and for a large clip. Keep the 850 MB source limit (VIDEO_MAX_FILE_BYTES) and the 40 MB image limit unless a measurement proves a problem; report it if so.

MP4 (required):
- Output: MP4 container, H.264 video, yuv420p, moov atom at the start (fast start) so it plays in normal players and editors. Audio, if kept, is AAC.
- Preferred method: WebCodecs VideoEncoder (and AudioEncoder) plus a small vendored MP4 muxer, working offline from the static site and from dist.
- Before encoding, check support with VideoEncoder.isConfigSupported for the exact codec string and size. If the owner's browser cannot encode H.264, the MP4 option stays visible but disabled with a visible reason in the UI. Do not hide it and do not fail silently. In that case also test and report which codecs and sizes Playwright Firefox and Chromium support, and write the result in README under Limits and in HUMAN-CHECK. Do NOT silently write another codec inside an .mp4 file.
- Do not use ffmpeg.wasm unless you prove with numbers that no smaller solution works, because of its size.

WebM:
- VP9 (or VP8 if VP9 is unavailable) in a WebM container, with seekable output (duration and cues set).

Verification (all with ffprobe and ffmpeg):
- For each of 1920x1080, 1280x720, 3840x2160, 1080x1920 and a rotated source, with the preset on Original, and also with a custom 640x360 preset in each Fit mode: check codec, pixel format, width, height, frame count, duration and that the MP4 plays and seeks.
- Frame extraction check: extract frames at the start, middle and end of the exported file. Each must show the effects and must differ from each other when the source frames differ. A file of one repeated frame is a FAIL.
- Run it in Chromium and Firefox through the real UI (G22). Also run it from the dist build.

Done when: G22 export checks are GREEN in Chromium and Firefox (MP4 and WebM, or MP4 disabled with a visible reason only where the browser truly cannot encode H.264), G21 is updated as in section 3, the ffprobe table is in GATE.md, three gate runs are green, and the break-it list is run.

### V3 - Video control bar

Goal: a control bar visible whenever a video is loaded and hidden for images.

Controls:
- Play and pause (keep the current behavior).
- Seek bar (range input) with current position, draggable, with current time and total time as text (m:ss).
- Jump backward and jump forward buttons, fixed step 5 seconds, clamped to start and end.
- Frame step backward and forward ONLY if frame-accurate stepping is verified. Otherwise leave it out. Do not fake it.

Behavior:
- Dragging the seek bar must not cause a render storm: render at most once per animation frame and only for the latest requested time. During the drag the last good frame stays visible. After release, the frame at the final time is rendered and passes the V1 parity rule.
- Seek works while playing and while paused. Playback state is kept or restored predictably.
- The bar never overlaps the canvas or the compare handle. Compare split keeps working with video.
- The seek bar is focusable. Arrow keys move it. Labels and aria values are set. Do not break existing shortcuts (Space plus drag pans, plus/minus zoom, C compare, O original, \ panel, T theme, R reset, E export). If you add shortcuts for jump backward or forward, check conflicts first and list them in the README shortcut table.
- Mobile (700 px and below): usable with touch targets of at least 44x44 CSS px (G16), input font size at least 16 px, no overflow at 320 px, and it does not cover the bottom-sheet handle. Above 700 px the desktop layout stays otherwise unchanged (G17 stays green).
- Contrast at least 4.5 for text and 3 for UI parts, in light and dark, with the host userContent.css fixture injected. Use only --gc-* tokens. No hardcoded colors outside the token blocks (G1). Use the same border, 6px radius, states and transition tokens as the existing groups. Respect reduced motion.

Done when: tests for every behavior are written first (RED then GREEN), screenshots in both themes at 360 and 1280 widths are opened and described, three gate runs are green, and the break-it list is run.

### V4 - Output dimensions work with video

Goal: Size Preset, Fit, Lock Ratio and Custom width and height are enabled and working when a video is loaded.

- Default selection is Original. A line near the Export button shows the real output size the export will use (for example 1920x1080) and updates when preset, Fit, Lock Ratio or custom values change.
- All existing presets and the Custom option work for video, with the existing clamping and stepper logic untouched.
- Fit modes behave exactly as they do for images (read the existing options from the code, do not invent new ones).
- The preview is not forced to the export size. It keeps its own fitting logic.
- If a control is unusable for a real reason, show a visible reason. No silent greyed-out controls.
- Proof: the V2 ffprobe results for each preset and Fit mode.

Done when: tests first (RED then GREEN), screenshots in both themes, three gate runs green, break-it list run.

### V5 - Image hitches, then closeout

1. Reproduce the freeze on a 4K image with 6+ effects (slider drag and compare-split drag) in Chromium AND Firefox, with real numbers: long tasks over 50 ms, worst frame, p95. Find the root cause (for example main-thread work that still runs while the Worker renders, result bitmap handling, layout, status updates, or the synchronous fallback being used in Firefox). Fix only what a measurement proves. If Firefox uses the sync fallback, say so and decide by measurement whether the Worker path should be enabled there.
2. Keep P2-2 parity and G19 green. Keep G11 and G13 green with their paired budgets.
3. Closeout: G22 must be GREEN in both browsers. Run the full gate 3 times in a row, all GATE PASS. Update README (Current status with commit and tag, Done, Next steps with P2-4 first, HUMAN-CHECK, date), docs/GATE.md and docs/PROJECT_MEMORY.md. Run npm run build and python tools/dist_smoke.py. Commit, tag V5-pass, push the branch and the tags. Show git status -sb (must be clean and not ahead) and git tag --list "*-pass".

---

## 6. Final report format

For each task: PASS, FAIL, BLOCKED or HUMAN-CHECK; commit hash; tag; root cause with the measurement that proves it; RED and GREEN numbers; gate run times and results; screenshot list with a one-line description of each; break-it list with results; files changed.

Then one table: owner symptom 1 to 6, fixed or not, and which test proves it.

HUMAN-CHECK (the owner verifies by hand; never claim these as verified): video playback feel and frame rate in his real Zen browser on his own GPU; an exported MP4 and WebM opened in his real player and his real editor; whether his Zen can encode H.264; audio in the export; the largest real-world video on his machine; real phone behavior.

Stop after V5. Do not start P2-4.
