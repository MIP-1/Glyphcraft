# Part 1C — Audit, video play/pause control, multi-effect performance

Source brief: `~/Downloads/part_1c_prompt.md` (kept outside the repo). This file is
the English task record for the repo and is the only brief the gate reads.

## Goal

1. Audit Part 1B: find and remove real console errors, runtime bugs and
   edge-case exceptions (RED first, one commit per audit fix).
2. Add a robust, accessible video Play/Pause control that stays in sync with
   the `<video>` element, its DOM events, and the UI, with no leaks or races.
3. Find and fix the root cause of the multi-effect cost that makes Zen/Brave
   warn about the tab, structurally rather than by lowering quality silently.

## Non-negotiable rules

- No Arabic characters anywhere in the repo (G6). The Arabic brief stays in
  `~/Downloads/`.
- Never weaken an existing test, threshold or allowlist. New checks are added
  as G13+.
- Tests first: every fix has a failing check before the change and the same
  check green after it. 3 failed attempts = BLOCKED.
- Every performance claim has before/after numbers from the same harness.
- Full gate 3× in a row on the committed tree, every screenshot opened and
  described, then one commit per task and tag `<task>-pass`.
- States are PASS / FAIL / BLOCKED / HUMAN-CHECK only.

## Acceptance criteria

### A. Audit (C1)

- A1: a hidden tab during video playback resumes the render loop when the tab
  becomes visible again (currently the loop dies while the tab is hidden and
  the preview freezes on return).
- A2: exporting a video preserves the user's prior play/pause state; a paused
  video is not left playing after export.
- A3: no uncaught page errors, no unhandled promise rejections, and no console
  errors during load → play → pause → effect change → theme change → export →
  replace source, at 1280 and 360.
- A4: replacing / clearing a video removes its event listeners and revokes its
  object URL exactly once; the reused `V` video element does not accumulate
  listeners.
- A5: all single-key shortcuts are ignored while focus is on a button, so
  Space/Enter activates the focused control instead of panning.

### B. Video Play/Pause control (C2)

- B1: a real `<button>` in the canvas area, 44×44 minimum, visible only when a
  video is loaded (hidden for images and for the empty state).
- B2: label and icon reflect the real element state after `play`, `pause`,
  `ended`, programmatic changes and rapid double clicks; state is read from
  `video.paused`, never from a shadow variable.
- B3: `play()` rejection (AbortError / NotAllowedError) is caught and leaves
  the control in the true state; no unhandled rejection.
- B4: keyboard operable (Tab, Enter, Space when focused), visible focus ring,
  `aria-label` updated, no duplicate/!second rAF loop.
- B5: unrelated app actions that pause or resume the video (export, undo of
  the source, replacing the source, tab visibility) keep the control in sync.
- B6: no listener, timer, rAF or heap growth across 50 play/pause cycles.

### C. Multi-effect performance (C3)

- C1a: with six stacked effects on a playing 1280×720 video, measured over 5 s:
  p95 render ≤ 33 ms, long-task total ≤ 300 ms, no unthrottled frame storm,
  and rendered frames ≥ 20 (visible motion).
- C1b: 5 s of image idle with the same six effects stays at 0 rAF / 0 timers
  (H4 behaviour must not regress).
- C1c: a `glitch`/`grain` random-effect stack does not allocate a new canvas per
  effect per frame: canvas creations per rendered frame ≤ 1 after warm-up.
- C1d: paused video + six effects stays at 0 rAF / 0 timers (H4 regression).
- C1e: the same six-effect stack on the same source produces the same pixels
  as before the optimisation when paused (pixel identity on non-random effects).
- Root cause must be named in `docs/GATE.md` with file:line evidence and a
  before/after table; rejected ideas are listed with the reason.

## Gate additions (G13+)

- G13 `video_check.py`: playback cost, allocation rate, play/pause control
  contract, hidden-tab resume, export state, listener/heap stability, image
  idle regression.
- G14 (if needed): any additional audit regression found during C1.

## Execution order

1. C0: `video_check.py` baseline mode on the current HEAD; record numbers.
2. C1: the audit fixes above, each with a RED check first.
3. C2: play/pause control with its G13 checks.
4. C3: structural performance changes, one commit each, keeping only measured
   gains.
5. Full gate 3×, screenshots, `docs/GATE.md`, commits, tags.
