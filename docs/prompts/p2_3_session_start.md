Load skills: using-rigor-skills, rigor-gate, verify-before-claim, root-cause-debugging, test-first, perf-measure, code-audit, ui-visual-audit, namethatui, performance-optimization, webapp-testing, improve-codebase-architecture, tmux.

# P2-3 session start: full code review, speed, video limit 850 MB, native video resolution

This file is the full prompt for this session. Read all of it before doing anything, then follow it in order.
Save it as `docs/prompts/p2_3_session_start.md` and include it in your first commit.

## Owner decisions (locked, do not re-ask)

1. **Review everything.** Audit every file of the app. Make it faster. If a module can be rebuilt and is measurably faster, rebuild it. If not, improve what can be improved in place.
2. **No disaster.** The working app must keep working at every commit on `main`. Nothing reaches `main` until the final gates are green. See "Safety net".
3. **Video size limit is 850 MB** (was 40 MB). Use the same MB convention as the existing 40 MB constant. One named constant for video. The image limit stays 40 MB in its own constant; report this split in your final message so the owner can change it.
4. **Video export resolution is always the original video's native resolution.** It never changes. No preset, no fit, no width/height field, no preview clamp may alter the exported video size.
5. Effects output must stay pixel-identical to the pre-P2-3 build unless the owner approves a visual change. Ask ONE question before any intentional visual change.

## Step 0: Skills

- Load by name, no @ mentions. If a skill is missing, skip it and tell me. Install nothing.
- `improve-codebase-architecture` is advice for this task and is allowed to drive the rebuild decisions below.
- `tmux` is not installed on this machine. Use `nohup setsid ... &` and poll with tails. Report that honestly.

## Step 1: Evidence first and safety net

Git and the code are the source of truth, not memory files and not summaries. If this file or any handoff disagrees with git, git wins.

Run and report briefly:

- `git status -sb`, `git log -8 --oneline`, `git tag --list "*-pass"`
- `npm run build`, `python tools/dist_smoke.py`
- `pgrep -af run_gate` (no gate may already be running)
- `df -h .` and `df -h /tmp` (large video fixtures need disk), `ffmpeg -version | head -1`, `ffprobe -version | head -1`

If anything is dirty, ahead, failing or missing, fix it and report it first. Never run `git checkout`, `git reset` or `git stash` on uncommitted work.

Safety net, before any code change:

- Tag `pre-P2-3` on the current HEAD and push it (this is not a `-pass` tag).
- Create the branch `p2-3-work` and work only there. Push the branch to origin regularly as a backup (`git push origin p2-3-work`). Commit WIP often, no `-pass` tags on WIP.
- The live site is served from `main`. Do not push to `main` until Step 7.
- Any module rewrite lives next to the old one behind a switch until it passes parity and gates. Delete the old code only in a separate later commit.
- Never rewrite the whole app in one commit. One module per commit. If a commit breaks parity or a gate, revert that commit, not the checks.

Raw logs rule (learned the hard way): `/tmp` gets wiped by the system. Write every gate log and every benchmark log directly into `docs/evidence/p2-3/` (raw, not summaries). Run gates as `python -u tests/gate/run_gate.py > docs/evidence/p2-3/gate-run-N.log 2>&1` with START and END timestamps and the exit code appended.

Context rule: this session will be long. Print tails only (last 40 lines), never full logs. Write findings to files under `docs/evidence/p2-3/` as you go, so a context compaction loses nothing. Keep `docs/evidence/p2-3/STATE.md` updated after every step (what is done, what is next, last commit hash).

## Step 2: P2-2 closeout (small, read-only first)

P2-2 is tagged `P2-2-pass` (commit `fcbea06`). Check these and fix only what is actually broken, in one commit `P2-2 closeout`, tag `P2-2-closeout-pass`:

1. Open and describe every screenshot of the final P2-2 gate run (58 files in `docs/evidence/p2-2-run-3/`) one by one, in batches of 12. After each batch append your notes to `docs/evidence/p2-2/screenshot-review.md`. For runs 1 and 2, prove equivalence with an automated per-file pixel diff, show the numbers, and open only the files that differ beyond a stated tolerance.
2. The G19 parity hash was `2243323070` before the last fixes and is `2247827130` on the final tree. Explain what changed the output, with evidence.
3. Run 3 printed an empty `snap=` field in the G14 light 740x360 cell. Check whether the other runs and cells print it, and explain.
4. Run G19 and the worker path in Firefox through Playwright (Firefox 157 is installed). The owner's daily browser is Firefox-based. Report the result. If the worker path fails there, the fallback must make the app work identically; prove it. Do not hide a failure.
5. Confirm `docs/prompts/part2_performance_core.md` is tracked in git. Confirm `npm run build` and `tools/dist_smoke.py` pass on the final tree.
6. Opening `index.html` over `file://` must still work (workers can be blocked there). Prove the fallback.
7. Add the font license file for the self-hosted JetBrains Mono next to the font, and fix the README sentence about network requests so it matches reality.

## Step 3: Task A, audit and baseline (no behavior change)

Deliverables in `docs/evidence/p2-3/`: `audit.md`, `baseline.json`, `decisions.md`. Tag `P2-3-A-pass` after review.

### A1. Read everything

Read every source file: `index.html`, `style.css`, `engine.js`, `effects.js`, `reorder.js`, `app.js`, `render-worker.js`, `tools/`, `tests/`. For each file record size, responsibility, hot paths, dead code, duplicated work and risks. Use `code-audit`. Find bugs yourself, do not ask the owner to find them.

Look at least for: per-frame allocations, buffers that can be reused, full-frame passes that can be merged or skipped, `getImageData`/`putImageData` round trips, missing `willReadFrequently`, repeated work on unchanged stages (per-stage cache), neutral stages that can be skipped, work done at full size that only needs preview size, layout thrash and forced reflow, listener cost during drag and scroll, CSS cost (large blur, filters, shadows, always-on animations), the DOM size of the 22 effect cards, startup cost (script order, font loading, work before first paint), idle CPU when nothing changes, memory growth over time, and the size of `dist/`.

### A2. Baseline measurements (before any change)

Build a benchmark harness (`tests/bench/`) with the same rules as the P2-1 compare harness: one continuous in-page gesture, 60-frame warm-up discarded, forced GC, settle time, median and p95, 5 windows, paired old/new runs in the same session. Measure on the current build, headless Chromium:

- Startup: time to first paint and to interactive, bytes loaded.
- Render time per effect (all 22) in each mode (Script, Dither, Effects Only), on 1080p and 4K stills, effect amount at a fixed mid value.
- Stacked cases: 1, 3, 6 and 12 effects. Slider drag with the worker path on and off.
- Video: playback frame time with 0, 3 and 6 effects on a 1080p fixture and a 4K fixture.
- Video export: time per exported second and peak memory for a short clip.
- Idle CPU with an image loaded and nothing happening. JS heap before and after 200 renders.
- Bundle size (source and `dist/`).

Headless software raster is a measurement floor. Real GPU numbers are HUMAN-CHECK, never claimed.

### A3. Golden outputs (parity safety net)

Before any code change, write `tests/gate/golden_p2_3.json`: a canvas hash for each of the 22 effects and each of the 3 modes on fixed 1080p and 4K inputs, plus a set of stacked cases. Seed or exclude random effects and list the excluded ones. This becomes a permanent gate check (next free G number). After every optimization or rewrite, all hashes must match exactly (0/255 difference), or the change is reverted.

### A4. Decision table

In `decisions.md`, list every module with: measured cost, root cause, and a decision: KEEP, OPTIMIZE IN PLACE, or REBUILD BEHIND A SWITCH, with the expected gain and the risk. A module is only a rebuild candidate if the audit measured a real bottleneck in it. If a rebuild candidate exists, ask the owner ONE question before building it (numbered options, last option "Other: I'll type it") listing the candidates and the measured gain. Optimize-in-place items proceed without asking.

## Step 4: Task B, video (limit 850 MB, native resolution)

Test first: write the checks and see them RED, then implement.

### B1. Understand the current video flow

Trace and document in `docs/evidence/p2-3/video-audit.md`: where the 40 MB constant and its strings live (code, drop area text, error text, README, tests, gate); how the file is read (it must not be read whole into memory; no `FileReader` full read, no `arrayBuffer()` of the whole file, no base64 data URL; use an object URL); how frames are pumped (`requestVideoFrameCallback` or rAF); how seeking works; how export works (WebM through `MediaRecorder` and canvas capture) and where recorded chunks are kept; what happens to audio; what the export size is today and which control or clamp decides it (the preview is clamped to 1600 px / 2.5 MP; the export must not be); frame rate handling; progress, cancel, and what happens when a new file is loaded during export.

### B2. Implement

- Video limit 850 MB in a single named constant, separate from the image limit. Update the drop area text, error messages, README and every test that asserts the old limit. Tests are updated to the new rule and extended, never deleted or loosened.
- Files above the limit are rejected with a clear message that states the real limit. The boundary is exact: a file of exactly the limit is accepted, one byte more is rejected.
- Loading an 850 MB video must not freeze the page or read the file into memory. Report peak memory.
- Export resolution equals the source video's native pixel size (`videoWidth` x `videoHeight`, after rotation metadata). For video sources the size preset, width, height and fit controls stay visible but inert with a short inline note that video exports at original resolution. Nothing is hidden or dropped. Image export behavior is unchanged.
- If the native size exceeds what the browser canvas can handle, fail with a clear message. Never silently downscale or change the size.
- Do not change frame rate or audio behavior silently. Report what they are today. If you find a defect, fix it only if it is a bug, and say so.

### B3. Checks (permanent, in the gate where the cost allows)

- Boundary check for the limits with a mocked file size object: exactly 850 MB accepted, 850 MB + 1 byte rejected, image 40 MB boundary unchanged, 0 byte file rejected with a clear message.
- Whole-file-read check: instrument `FileReader`, `Blob.arrayBuffer`, `Blob.text` and `fetch` on the video path. Calls on the video file must be 0.
- Export size check with `ffprobe` on the exported file: it must equal the source for landscape 1920x1080, 1280x720, 3840x2160, portrait 1080x1920, and an odd size such as 1002x562. Include a phone-style rotated video if you can generate one.
- One real large file test (separate script `tests/gate/video_large.py`, run at closeout with raw evidence): generate a WebM of about 840 MB with `ffmpeg` into a git-ignored folder, load it, apply 3 effects, play, seek, export a short range, check the exported size, then delete the fixture. If it is too slow for the gate, it stays a required closeout run, not an optional one.
- Check first whether this Chromium plays H.264. If it does not, use VP8 or VP9 WebM fixtures, and mark MP4/H.264 as HUMAN-CHECK on the owner's real browser.

Commit, run the full gate 3 times in a row (Step 6 rules), tag `P2-3-B-pass`.

## Step 5: Task C, speed (module by module)

Follow `decisions.md`. Also read the P2-3 section of `docs/prompts/part2_performance_core.md` (fast preview; the README says the preview is always downscaled today). That spec still applies. If it conflicts with the owner decisions above, ask ONE question.

Rules for every change:

- One change per commit. Before and after numbers go into `docs/evidence/p2-3/perf-log.md` (paired runs, 5 windows, median and p95).
- Keep a change only if the paired median is at least 10% faster and it wins in at least 4 of 5 windows, or if it removes a measured long task (over 50 ms). Anything else is reverted. Removing comments or renaming does not count as speed.
- After every change: golden hashes identical, `python tests/test_suite.py` green (169 checks, the count only goes up), G1 to G19 not broken. Run the targeted checks after every commit and one full gate after every few commits.
- Keep the Worker path (G19), the compare split (G11), playback (G13), mobile layout (G14 to G18, G17 desktop baseline unchanged) and theme parity (G2) green. Effects output stays pixel-identical.
- A rebuild of a module is allowed only if approved in Step 3 A4, lives behind a switch, passes the golden hashes and the targeted benchmark, and then replaces the old code in a separate commit.
- Update `tools/build.py` and `tools/dist_smoke.py` if files change. `dist/` must render the same canvas as the source.

## Step 6: Gates

- Full gate 3 times in a row, sequentially, in the background, unbuffered, raw logs in `docs/evidence/p2-3/`. About 25 minutes each, longer if checks were added. Never interrupt a run.
- Before each launch, check `pgrep -af run_gate`. Never start a gate while one is running, and do no browser work and no heavy work while a gate runs (timing checks are sensitive to load).
- If a launch dies before G2 passes its first `page.goto` (a 30 s Google Fonts timeout happened in P2-2), keep that log, document it, and relaunch. It does not count. If it happens twice in a row, ask ONE question.
- Never weaken a test or threshold. A gate rule may change only when the check measures the machine and not the app: show the numbers first, prefer relative metrics, record it in `docs/GATE.md`.
- Open every screenshot of the final run one by one, in batches of 12, and append notes to `docs/evidence/p2-3/screenshot-review.md` after each batch. Prove runs 1 and 2 equivalent by automated pixel diff with numbers, and open any file that differs. If something cannot be reviewed, record it under HUMAN-CHECK, do not claim it.

## Step 7: Break-it, docs, merge, tag

Test at least these 12 cases and record each result:

1. Video of exactly 850 MB accepted, one byte more rejected.
2. Corrupt, truncated and 0-byte video; unsupported codec; renamed non-video file.
3. Portrait and rotated phone video, odd dimensions, 4K video with 6 effects.
4. Export cancelled midway; a new file loaded during export; export started with the tab hidden.
5. Undo/redo, compare split, theme switch and window resize during video playback.
6. 360 px mobile layout with a video loaded (sheet at peek, half, full).
7. `?worker=0`, `file://`, and Firefox.
8. Slider drag on a 4K still with 12 effects.
9. Loading 20 files in a row (memory growth).
10. Empty state, then drop a video, then drop an image.
11. Every effect amount at 0, at max, and typed out of range.
12. Reload in light theme with the fullest state.

Then:

- Record everything in `docs/GATE.md`: RED and GREEN evidence, baseline and after numbers, decisions table result, gate runs, break-it results, screenshot review.
- Update `README.md` (limits, status, next steps, HUMAN-CHECK, date) and `docs/PROJECT_MEMORY.md`.
- Merge `p2-3-work` into `main` only now, fast-forward if possible. One closeout commit and the tag `P2-3-pass`. Push `main`, the tags and the branch. Show `git status -sb` (clean, not ahead) and `git tag --list "*-pass"`.

## Rules

- English only. No Arabic anywhere in the repo (G6). All CSS variables stay `--gc-*`.
- No explanatory comments in app code (short section markers are allowed).
- Never weaken a test or threshold. The 169 tests: the count may only go up. New permanent checks are added to the gate.
- Optimise only by measuring. Keep only measurably faster changes.
- Three failed attempts on one task means BLOCKED, not a loosened check.
- Do not touch effect output, the mobile layout, the theme tokens or the stepper logic except where a measured change requires it and parity proves no change.
- Do not start P2-4.

## Questions

If you need information from the owner, ask ONE question at a time with numbered options. The last option is always "Other: I'll type it". Never ask what you can find out from the repo or by measuring.

## Final report format

- Per gate run: start, end, duration, result, every non-PASS line.
- Per task: commit hash, tag, RED and GREEN evidence.
- Speed: before/after table per kept change; list of reverted changes with the reason.
- The two owner-visible limits: video 850 MB, image 40 MB, and confirmation that video export size equals the source.
- Honest HUMAN-CHECK list: real-device frame rate, real GPU playback, real Safari, real Firefox/Zen feel, MP4/H.264 on a real browser, the largest real-world video on the owner's machine.
