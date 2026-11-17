Load skills: first run ls ~/.config/opencode/skills and load EVERY skill found there, by name, with no exceptions and no @ mentions. Known names: using-rigor-skills, rigor-gate, verify-before-claim, root-cause-debugging, test-first, code-audit, ui-visual-audit, design-consistency, perf-measure, namethatui, performance-optimization, webapp-testing, caveman, extremesv1. If a known skill is missing, skip it and say so in one line. Do not install anything. Style-only skills (caveman, extremesv1) shape your chat replies only; they never apply to code, commit messages, docs or this prompt file.

# Glyphcraft - LAG AND PERFORMANCE ROUND (tasks L0 to L3)

Repo: ~/glyphcraft. First action: save this file verbatim as docs/prompts/lag_performance_round.md.

---

## 1. Summary (read this first)

The owner tested the app after V2 and still sees:

1. LAG when a video plays.
2. Video preview sharper than before, but still too soft (low detail).
3. A feeling that the app is heavy on CPU and RAM. The owner suspects the code is too long and that this is part of the problem. Treat that as a hypothesis, not a fact: measure it.

Goals of this round:

| # | Goal | Task |
|---|------|------|
| 1 | Measure where the time and memory really go, before changing anything | L0 |
| 2 | Remove the video playback lag and make the preview sharper, without lowering quality during playback | L1 |
| 3 | Lower CPU and RAM use, and make the code shorter, cleaner and faster WITHOUT breaking any function or changing any output pixel | L2 |
| 4 | Test everything, find holes (bugs, leaks, security problems), fix them, then close out | L3 |

Hard promise to the owner: you may not say a problem is solved until you have run the real app and measured it. "Looks fixed" is not a result. Numbers are.

Where this round sits: V0, V1 and V2 are done (tags V0-pass, V1-pass, V2-pass; V2 commit a83ddac). V3 (control bar), V4 (size controls) and V5 (image hitches, closeout) are NOT done and NOT part of this round. Do not build V3, V4 or V5 features. Do not start P2-4. When this round ends, the README next steps must still say V3 first.

---

## 2. Known facts from earlier work (verify each one, do not trust it)

- V1 removed the adaptive playback resolution. Playback now always renders at previewSize(full), for example 1280x720 for a 1280x720 source. If the pipeline is slow, frames are dropped instead of quality. This rule stays (see section 3).
- Earlier measurements on the dev machine, headless software raster: 2-effect stack about 37 ms per frame when calm and about 73 ms under load; 6 heavy effects about 237 to 280 ms per frame; Oil Paint about 1063 ms per frame at 1600x900. The status bar prints state.lastRender only.
- The preview is capped at 1600 px and 2.5 MP (verify the current constants).
- Worker rendering (P2-2) is used only for still images with 6 or more enabled effects and a large preview. Video frames go through the synchronous main-thread path. Verify this.
- Effects read and write pixels with getImageData and putImageData on the CPU. That is a known cost. A GPU (WebGL) rewrite is OUT OF SCOPE for this round, because the 200-case golden set (G20) requires exact identical pixels. You may describe it as a recommendation with an honest estimate in the final report.
- A full gate run now takes about 45 minutes (V2 runs took 45 to 48 minutes each).
- All gate runs are headless software raster. They do not show the owner's real GPU. Real GPU feel is HUMAN-CHECK.

---

## 3. Locked rules

- Source of truth is git, tags, code, README and docs/GATE.md. If docs/PROJECT_MEMORY.md disagrees, git wins.
- Start: git status -sb, git log --oneline -10, git tag --list "*-pass", git stash list. Read README.md, the tail of docs/GATE.md, docs/PROJECT_MEMORY.md and docs/evidence/v1/report.md and v2/report.md.
- NO behavior change. The app must keep every feature: all modes, 22 effects, presets, undo/redo, compare, export MP4/WebM/Frame, themes, mobile sheet, reorder, shortcuts. If a refactor changes any visible behavior, it is wrong.
- NO pixel change. G20 (200 golden cases, exact), G19 parity, G21 and the G22 parity checks must keep identical hashes. A faster path that changes even one pixel is a bug.
- Playback quality rule from V1 stays: during playback, if the pipeline cannot keep up, drop frames or slow down. NEVER lower render resolution or quality, and never switch quality mid-session. Every shown frame must match a still render of the same frame (G22 parity).
- Never weaken a test or threshold. The test count only goes up (G5 is currently 170). A gate rule may change only when a check measures the machine and not the app: show numbers first, prefer relative or paired metrics, record old rule, new rule and reason in docs/GATE.md.
- Test first. For each task: write the check, see it RED, fix, see it GREEN. Keep RED and GREEN logs in docs/evidence/<task>/.
- Find the ROOT CAUSE. Prove each cause with a measurement. Keep only changes that measure faster or lighter. Record before and after numbers. Reject and revert anything that does not measure better, and write it down as REJECTED with the numbers.
- Small steps. Change one thing, run the targeted checks (G5, G13, G19, G20, G21 and the G22 checks that currently pass), then commit. Never stack several unmeasured changes.
- English only, no Arabic anywhere in the repo (G6). All CSS variables stay --gc-*. No explanatory comments in app code (short section markers allowed). Both themes must pass. Menus keep the inverse theme.
- No runtime network downloads. The site stays static and offline-capable.
- npm run gate takes about 45 minutes. Run it in the background, poll the log, never interrupt it. Full gate 3 times in a row, one after the other, once at the end of each task that changes runtime code. Required result: G1-G21 PASS in all three runs. G22 may fail ONLY on the known not-yet-built V3, V4 and V5 sub-checks; every G22 sub-check that passes today must still pass, and no new failure is allowed. List the exact G22 lines before and after.
- After every runtime change: npm run build and python tools/dist_smoke.py must pass. The Worker and the export code must work from dist.
- Open and describe every screenshot the gate produces. For each task list at least 8 ways it could still break (break-it list) and run them.
- One tag per task: L0-pass, L1-pass, L2-pass, L3-pass. Several small commits per task are fine. Push the branch and the tags after each task.
- After three failed attempts on one task, mark it BLOCKED and report. Do not loosen anything.
- Do not ask the owner questions. Find problems yourself. If truly blocked, ask ONE question with numbered options; the last option is "Other: I'll type it".
- Allowed states: PASS, FAIL, BLOCKED, HUMAN-CHECK, REJECTED (for an experiment that measured no gain). Never claim anything you did not run.

---

## 4. Tasks

### L0 - Measure first (no app code changes)

1. Code map: for every file (app.js, engine.js, effects.js, reorder.js, render-worker.js, style.css, index.html, tools, tests) report line count, byte size and minified size. For app.js and effects.js list the largest functions and the hottest functions per frame during video playback. Say honestly whether "the code is long" has any measurable link to the lag. Parse and compile time of the scripts at load must be measured, not assumed.
2. Playback profile: for a 1280x720 and a 1920x1080 clip, in Chromium AND Firefox, with (a) no effects, (b) a 2-effect light stack, (c) a 6-effect heavy stack, record during 20 s of playback: frames rendered per second, time per frame (p50 and p95), main-thread long tasks over 50 ms, input latency of a click on Pause and of a seek, dropped or skipped frames, status-bar value, JS heap over time, and CPU time. Use CDP Performance metrics and tracing in Chromium and the closest available tools in Firefox.
3. Per-frame breakdown: split one frame into stages (video to canvas copy, getImageData, each effect, putImageData, compositing, status update, any layout or style work) and show which stage dominates. Check also for per-frame allocations, layout thrash, forced style recalculation, expensive CSS during playback (backdrop-filter, filters, shadows, transitions on elements that update every frame), timers and listeners that run every frame.
4. Sharpness analysis: for a video and for the same frame as a still, measure source size, preview backing size, CSS display size, devicePixelRatio and the zoom value. Explain exactly why the preview looks soft: for example backing size smaller than display size times devicePixelRatio, the 1600 px or 2.5 MP cap, smoothing during CSS scaling, or a downscale from the source. Give the numbers for 79%, 100% and 112% zoom.
5. Memory and leaks: measure memory after loading and clearing a video and an image 20 times, after 20 exports, after 60 undo steps, and during 5 minutes of idle playback. Check blob URL revocation, ImageBitmap and VideoFrame close calls, event listener and timer cleanup, history storage size.
6. Write RED checks for the owner's two complaints as permanent tests (new G23): (a) playback smoothness for a light stack measured relative to a no-effect control in the same session (paired, so machine speed cancels out); (b) preview sharpness: the backing size must be at least min(source native size, CSS display size times devicePixelRatio), subject to the existing preview caps, which you must list. Set the numeric budgets from the L0 baseline, write them down BEFORE any fix, and never change them afterward without the measured-machine rule.
7. Compression candidates: list every place where compression could help and what it would cost: (a) data sent between the main thread and the Worker (check whether transferable ImageBitmap or ArrayBuffer transfer is already zero-copy; compressing it adds CPU, so measure honestly); (b) the shipped JS, CSS and font files (minify, and gzip or brotli as served by the static host, measured with real compressed sizes); (c) the undo history and any cached frames (only lossless compression is allowed). Do not implement anything yet.

Done when: docs/evidence/l0/report.md holds all numbers, tables and conclusions, G23 exists and is RED for the right reasons, and a ranked list of causes exists with the measurement behind each. Commit and tag L0-pass for evidence and RED proof only.

### L1 - Video playback lag and preview sharpness

Goal: video playback is smooth for the light stack and degrades gracefully (dropped frames, never a frozen page or lower quality) for the heavy stack; the preview is as sharp as the rules in L0 item 6b allow.

- Fix the causes found in L0, in the order of measured impact. Likely candidates to CHECK, not to assume: render work running on the main thread for video, redundant renders per frame, rendering faster than the screen can show, rendering frames that will be skipped, extra full-size copies, status bar or DOM updates every frame, expensive CSS during playback, getImageData readback pattern, decoding and rVFC scheduling, rendering while the tab or the canvas is not visible.
- Evaluate moving video frame rendering into the existing Worker (transfer the frame as ImageBitmap or VideoFrame). Keep it only if it measures better in both browsers and every parity check stays identical. If Firefox cannot do it, keep a correct synchronous fallback and say so.
- Frame scheduling: render at most once per displayed frame, use the newest decoded frame, skip stale work, and keep the UI responsive (play, pause, seek and slider input must stay responsive while playing, with the input latency budget from L0).
- Sharpness: fix the cause found in L0 so the backing size follows the rule in L0 item 6b. Check that this does not make playback slower than the L0 baseline for the same stack. If sharpness and speed conflict, report both numbers and keep the quality rule: sharp frames with dropped frames are allowed, soft frames are not.
- G23 goes GREEN. G13, G19, G20, G21 and the G22 parity and export checks stay green with identical hashes.
- Try the app in a headed browser with the real GPU if a display is available (Playwright headed), and report those numbers separately and clearly marked as not part of the gate. If it is not possible, write HUMAN-CHECK.

Done when: before and after tables (fps, p50 and p95 frame time, long tasks, input latency, CPU, heap) for each stack and both browsers are in docs/evidence/l1/report.md, G23 is GREEN, 3 gate runs are green, screenshots in light and dark at 360 and 1280 are opened and described, and the break-it list is run. Tag L1-pass.

### L2 - Lighter and faster code, without breaking anything

Goal: lower CPU and RAM use and reduce code size and complexity, with zero behavior change and zero pixel change.

Work in small measured steps. Each step has: reason (from L0 numbers), change, targeted checks, before and after numbers, KEEP or REJECTED.

1. Dead and duplicate code: find unused functions, unused CSS, unused assets, duplicated helpers, leftover debug code. Remove only what tests and a repo-wide search prove is unused. Add a test that fails if removed behavior is used.
2. Allocation and memory: reuse buffers, avoid per-frame and per-render allocations, close ImageBitmap and VideoFrame objects, revoke blob URLs, remove listeners and timers on teardown, cap caches, fix every leak found in L0.
3. Idle and background cost: no timers, animation frames or renders while nothing changes, while the tab is hidden or the video is paused.
4. Structure: if app.js is too large to maintain, you may split it into several classic scripts loaded in order (for example state, ui, video, export, history), without a bundler, with names that describe their job, and update index.html, tools/build.py, tools/dist_smoke.py and tests so that dist keeps working. Do this only if all characterisation checks stay identical. A smaller number of lines is not a goal by itself; clarity and measured speed are.
5. Load cost: measure script parse and compile time, first paint and total transferred size (gzip and brotli) of source and dist before and after. Keep the minified dist build and fix anything that makes it larger than needed.
6. Compression experiments, each one measured and each one lossless: (a) Worker messages: compare plain transfer, structured clone and compressed payloads (for example CompressionStream), with real timings including decompression; (b) history or cache storage in memory: compress only if the measured memory saving is larger than the measured CPU cost and the round trip is byte-identical. Expected result for same-process transfers: compression is usually slower than zero-copy transfer. If your numbers show that, mark it REJECTED with the numbers and do not ship it. Ship a compression only if it measures better and round-trips identically.
7. Do not remove or rename any user-visible control, shortcut, effect, preset or export format. Do not touch effect math, dither math or glyph math unless a measured change keeps every golden hash identical.

Done when: before and after table for code size (lines, bytes, minified, gzip, brotli), memory over time, idle CPU, parse time and per-frame cost is in docs/evidence/l2/report.md; every step is marked KEEP or REJECTED with numbers; G5 count is not lower than 170 (it must go up, because every removal and every fix adds a test); G20 is 200/200 exact; 3 gate runs are green; screenshots opened and described; break-it list run. Tag L2-pass.

### L3 - Audit for holes, fix them, closeout

1. Run the code-audit and ui-visual-audit skills on the whole repo. Look for: bugs, race conditions (load, seek, export, cancel, undo during render), unhandled errors and promise rejections, unreachable states (stuck busy flags, disabled buttons that never re-enable), memory leaks, event listeners never removed, focus and keyboard problems, layout overflow at 320 px, touch targets, contrast in both themes, console errors and warnings.
2. Security and robustness review for a static client-side app: untrusted file input (very large, corrupt, wrong type, huge dimensions, animated or malformed images and videos, SVG with scripts), filenames and text inserted into the DOM (no innerHTML with untrusted data), Blob and object URL handling, localStorage data that is corrupt or oversized, Worker message validation, third-party or vendored code (the MP4 and WebM muxers: license present, version recorded, nothing loaded from the network), Content Security Policy options for a static host and what they would break, dependency and supply-chain check of npm packages used by the build.
3. For every hole found: write a failing test first, fix the root cause, show GREEN. Rank findings as high, medium or low. Report the ones you did not fix and why.
4. Run the real-flow checks again in Chromium AND Firefox: load image, load video, play, pause, seek, apply effects, change presets, export Video MP4, export WebM, export Frame, undo and redo, theme switch, mobile width. Report every console error.
5. Closeout: full gate 3 times in a row, all G1-G21 PASS, G22 failing only on the known V3, V4 and V5 sub-checks (list them). Update README (Current status with commit and tag, Done, Next steps with V3 first, then V4, V5, P2-4, HUMAN-CHECK, date), docs/GATE.md and docs/PROJECT_MEMORY.md. Run npm run build and python tools/dist_smoke.py. Commit, tag L3-pass, push the branch and the tags. Show git status -sb (clean and not ahead) and git tag --list "*-pass".

---

## 5. Final report format

For each task: PASS, FAIL, BLOCKED, HUMAN-CHECK or REJECTED; commit hashes; tag; root cause with the measurement that proves it; RED and GREEN numbers; gate run times and results; screenshot list with a one-line description of each; break-it list with results; files changed.

Then these tables:
1. Owner complaints (video lag, soft preview, heavy CPU and RAM, long code): fixed or not, with the before and after numbers and the test that proves it.
2. Every experiment (including every compression idea): KEEP or REJECTED, with numbers.
3. Findings from the L3 audit: severity, fixed or open.

HUMAN-CHECK (the owner verifies by hand; never claim these as verified): how smooth the playback feels on his real Zen browser and his real GPU, real CPU and RAM use on his machine, exported files opened in his real player and editor, real phone behavior, MP4 H.264 support in his Zen, the largest real-world video on his machine.

Recommendation section (not implemented): give an honest, measured estimate of what a GPU (WebGL or WebGPU) pipeline would gain and what it would cost, including the pixel-exactness problem with the golden set.

Stop after L3. Do not start V3, V4, V5 or P2-4.
