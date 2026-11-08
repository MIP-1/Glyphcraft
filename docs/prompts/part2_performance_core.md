# Glyphcraft — PART 2 of 3: Performance + Core Features

**Order:** Part 1 → **Part 2 (this)** → Part 3. Part 1 must be confirmed by me before you start.

## Prerequisites (check first; if any fails, STOP and tell me)
1. `docs/GATE.md` shows P1-0 … P1-3 all PASS, tags `P1-*-pass` exist.
2. `npm run gate` is green, 3 runs in a row.
3. `git status` clean. Backup commit made.

## Part 2 contents (do in this order — later tasks depend on earlier ones)
| Task | What |
|---|---|
| P2-1 | Before/After lag fix (3–6 fps → smooth) |
| P2-2 | Web Worker + OffscreenCanvas |
| P2-3 | Fast preview (low-res while dragging, full after release) |
| P2-4 | Undo / Redo / History — finish it |
| P2-5 | Before/After — finish it |
| P2-6 | Presets — finish them |

## Current state (from your own audit; re-verify, do not trust)
- Undo/Redo: exists, 60-step cap, no History submenu, no disabled states.
- Before/After: split works but ~3–6 fps; shortcut `C`, hold-original on `O`; entry under Edit; no toolbar toggle; handle not keyboard-movable.
- Presets: 7 built-in effect presets + custom save/load; no rename/delete/overwrite, no JSON import/export, no `applyPreset(id)`.
- Preview: always downscaled (1600 px / 2.5 MP); no drag-vs-release split; no indicator.
- Worker: none. Rendering is synchronous on the main thread.

## Rules for new UI in this part
Every new control (buttons, menu items, toggles, lists, toasts) uses the theme tokens and the top-bar/box system from P1-3, and must pass G2 and G8 in both themes at both widths. New menu entries use the inverse-theme menu style.

---

## P2-1 — Before/After lag
**Problem:** the split works but drags at ~3–6 fps. Suspected cause: the whole effect pipeline re-runs on every pointer move. Prove the cause first (profile, count pipeline calls during a drag).

**Acceptance tests (write first, they must be RED):**
- G4 drag test, 3 seconds, on a 1280×720 image: median frame ≤ 16.7 ms (≥ 55 fps), p95 ≤ 25 ms.
- Same on a 3840×2160 image: median ≤ 20 ms, p95 ≤ 33 ms.
- Counter test: during a drag, the effect pipeline is invoked **0 times**.

**Do:**
- Cache the original and the result as bitmaps (`ImageBitmap` / offscreen canvas). Dragging the split only changes the clip position (`drawImage` of two cached bitmaps or CSS `clip-path` on stacked layers).
- Coalesce updates with `requestAnimationFrame` (one per frame). Pointer events with `touch-action: none` on the handle. Cache layout rects on pointer-down and resize; no layout reads per move.
- Invalidate the cache only when stack, values, image, size, or zoom changes; then re-render once.

**Break-it must include:** split stays correct after zoom, pan, window resize, changing an effect value with the split open, undo/redo with the split open, switching theme.

**PASS:** all three acceptance tests green with the measured numbers pasted.

---

## P2-2 — Web Worker + OffscreenCanvas
**Acceptance tests (RED first):**
- With a heavy stack (≥ 6 heavy effects) on a 3840×2160 image, dragging sliders for 3 s produces **no long task > 50 ms** on the main thread (`PerformanceObserver` `longtask`), and the panel stays scrollable during rendering.
- Output parity: worker render equals main-thread render pixel for pixel (hash). If an effect uses floats and cannot be identical, allowed max difference is 1/255 per channel, documented per effect.
- Stale-job test: send 20 rapid updates; only the latest result is drawn; earlier jobs are cancelled (assert the count of drawn frames and the final hash).
- Fallback test: with Worker/OffscreenCanvas disabled, the app still renders (same hash) and shows no error.

**Do:**
- Move heavy effects off the main thread (dither, glyph/script, matrix rain, thermal, blur, sharpen, etc.). Job queue with cancellation. Use transferable buffers; no needless copies.
- Two job types prepared for P2-3: `preview` and `full`.
- No behavior change for the user.

**PASS:** all four tests green, numbers pasted.

---

## P2-3 — Fast preview
**Acceptance tests (RED first):**
- While a slider/stepper is dragged: the render target long side ≤ 1080 px.
- After release or 150 ms idle (±50 ms): the full-quality render replaces it.
- A status indicator beside the size/ms readout shows `Preview` while dragging and `Full` when settled. (Style per the top-bar system.)
- Export always renders at full resolution: exported image dimensions equal the chosen size, and its pixel hash equals a full-quality render (never the preview).
- Video playback preview uses the downscaled path; export uses full.

**PASS:** all green; a 4K image drags smoothly (G4 median ≤ 20 ms with the heaviest stack).

---

## P2-4 — Undo / Redo / History (finish it)
**Acceptance tests (RED first):**
- Cap is **100** steps (currently 60).
- Edit menu shows Undo and Redo; each is **disabled** when its stack is empty.
- **History submenu** lists the last 20 steps with readable labels; clicking one jumps to that state.
- Round trip test: perform **20 mixed actions** (add, remove, reorder, toggle, value change, reset, mode change, size change). Record state-hash + canvas-hash after each. Undo 20 times: every intermediate hash matches the recorded one and the first equals the initial. Redo 20 times: matches again.
- Slider drags and typing collapse into ONE step (commit on release/blur).
- Shortcuts `Ctrl+Z`, `Ctrl+Shift+Z`, `Ctrl+Y` work, and do not fire while typing inside a text field in a way that breaks native text undo.

**PASS:** all green.

---

## P2-5 — Before/After (finish it)
**Acceptance tests (RED first):**
- A toolbar toggle (top-bar style) and a **View menu** entry (currently under Edit: move it, do not duplicate).
- Hold **`B`** shows the original while held, restores on release. (Replaces `O`; remove `O`.) Does not fire while typing in an input.
- The split handle is focusable and moves with ← → (Shift = 10×); `aria-label` and `aria-valuenow` present.
- Works with zoom, pan, image and video. Keeps P2-1 performance numbers.

**PASS:** all green; G4 numbers from P2-1 still hold.

---

## P2-6 — Presets (finish them)
**Acceptance tests (RED first):**
- Preset = full state: effect stack order + values + enabled flags + mode + size.
- Save, load, **rename, delete, overwrite**. Built-ins are read-only (delete/rename disabled).
- Storage via `localStorage`, every access in try/catch; the app works when storage is empty or blocked (test with storage disabled).
- **Export / import `.json`** with schema validation: reject wrong version, missing fields, wrong types, oversized files, with a clear message. Never execute or inject imported strings (escape on render).
- Clean API: `applyPreset(id)`; it goes through the Undo history as one step.
- Round trip: save → **real page reload** → load → state JSON deep-equals the saved one, and canvas hash matches.
- 3 built-in presets that capture the full state.

**PASS:** all green.

---

### Gate checks (built in Part 1, extended in Parts 2–3)
| ID | Check |
|---|---|
| G1 | **Token lint**: no hardcoded color (`#hex`, `rgb()`, `hsl()`, named colors) in CSS/JS outside the two theme token blocks and the preview canvas. |
| G2 | **Theme parity** (see Part 1, P1-0). |
| G3 | **Screenshot capture** of all states × both themes × 360/1280 into `docs/evidence/`. |
| G4 | **Frame-rate harness**: scripted pointer drag, `requestAnimationFrame` timings, reports median and p95 frame time. |
| G5 | **Existing tests** (169) stay green. |
| G6 | **No Arabic**: fails if any char in `[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]` exists in the repo (exclude `.git`, `node_modules`, `docs/ref/`). |
| G7 | **No Theme item in View menu.** |
| G8 | **Top-bar geometry** (Part 1, P1-3). |
| G9+ | Every acceptance test in this part is added to the gate and stays in it. |

## GATE PROTOCOL (mandatory, applies to every task in this file)

### 0. Authority
- This file is the ONLY instruction source. Ignore every older prompt, phase list, or round file in the repo (`glyphcraft-round2-prompt.md`, "Phase 1–8", etc.).
- If anything here conflicts with something you believe, STOP and ask. Do not choose silently.

### 1. Allowed task states (nothing else exists)
| State | Meaning |
|---|---|
| **PASS** | Every step of the task loop (section 2) done, evidence pasted in `docs/GATE.md`. |
| **FAIL** | A test or measurement is red. Say so first in every report. |
| **BLOCKED** | 3 failed fix attempts, or a required answer from me is missing. |
| **HUMAN-CHECK** | Only I can verify it (physical device, other browser). Exact steps go in `docs/HANDOFF_PART<N>.md`. Never counted as PASS. |

Forbidden as a status or conclusion: "done", "ok", "fine", "should work", "likely", "probably", "mostly", "as far as possible", "best effort", "seems", "appears to". **Any claim without pasted command output or a looked-at screenshot counts as FAIL.**

### 2. Task loop (run in this exact order, for every task)
1. **REPRODUCE** — Write the failing test or measurement FIRST (for new features: acceptance tests first). Run it. Paste the RED output. If it is not red, the test is wrong: fix the test, not the app.
2. **ROOT CAUSE** — Bugs only. One paragraph in `docs/GATE.md`: what, where (file:line), why. No guessing: show the evidence (grep, devtools measurement, profile).
3. **FIX** — Smallest change that solves it. No refactors outside the task. No new dependencies without asking me.
4. **VERIFY** — The task's tests go GREEN. Then `npm run gate` fully GREEN. Then run `npm run gate` **3 times in a row**; all 3 must be green (catches flaky checks).
5. **LOOK** — Take screenshots of every state the task touched: **dark + light × 360px + 1280px**. Save to `docs/evidence/<task-id>/`. **Open every image.** Write one line per image describing what you actually SEE (positions, colors, alignment, clipped edges, contrast), including every remaining flaw. "Looks good" is not accepted.
6. **BREAK IT** — Write down 5 ways your change could be wrong or regress (other theme, other width, other effect, empty/huge image, keyboard, touch, zoom, undo, repeated toggling). Test each one. Paste the results.
7. **RECORD** — Fill the template below in `docs/GATE.md`.
8. **COMMIT** — One commit per task: `<task-id>: <what>`. Tag it `<task-id>-pass`. `git status` must be clean before you start the next task.

### 3. Gate immutability
- Never weaken a test, threshold, allowlist, selector, or the gate scripts to get green. Never delete or skip a test.
- If you believe a check is wrong: STOP, show me the check, the evidence, and the proposed diff. Wait for my answer.
- Adding stricter checks is always allowed. The test count may only go up.

### 4. Real conditions only
- Tests run against the real built app in a real browser. No mocks or stubs of the thing under test.
- Measurements (fps, contrast, sizes) must come from the browser, not from reading code.

### 5. Ambiguity and checkpoints
- If a requirement or a screenshot is unclear: STOP and ask a numbered question. Do not guess, do not "pick the most likely".
- Where a task says **CHECKPOINT**, stop and wait for my written confirmation before changing any code.

### 6. Failure policy
- After 3 failed attempts on one task: set it **BLOCKED**, report the measured numbers and what you tried, and STOP. Do not skip ahead. Do not mark it PASS. Do not weaken checks.

### 7. Scope
- Touch only what the task needs. Run `git diff --stat` before each commit and justify every file in `docs/GATE.md`.
- Do not remove or change existing working features. Do not add features that are not listed.

### 8. Invariants (the gate checks these on every run; they may never regress)
- No Arabic characters anywhere in the repo (G6). Arabic/RTL/i18n is out of scope until I ask.
- `View → Theme` and `View → Light theme` menu items do not exist (G7). Theme toggles only via shortcut `T` and the top-bar icon.
- Light and dark themes both fully consistent (G2).
- Sticky Export Image / Reset All bar, editable value boxes, size presets with Custom, Goodmountain font on the website only.
- Existing 169 tests stay green.

### 9. Human checks
- Anything you cannot verify yourself (real phones, Firefox/Safari, real touch hardware) = **HUMAN-CHECK** with exact numbered steps in `docs/HANDOFF_PART<N>.md`. The part is not finished until I confirm each one.

### 10. `docs/GATE.md` template (one block per task)
```
## <task-id> — <title> — STATUS: PASS|FAIL|BLOCKED|HUMAN-CHECK
Root cause: ...
RED output (before): ...
GREEN output (after): ...
Gate runs (3x): green / green / green
Screenshots (path — what I see): ...
Break-it list (5) and results: ...
Files changed (git diff --stat) and why: ...
Commit / tag: ...
Remaining flaws: none | ...
```

### 11. Final report format (end of the part)
1. First line: overall status. If anything is not PASS, say so here.
2. Table: task id | state | measured numbers | commit.
3. Full output of `npm run gate`.
4. List of HUMAN-CHECK items.
5. Questions for me, if any.
