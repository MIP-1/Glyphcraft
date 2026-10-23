# Glyphcraft — PART 1B: Hotfix (bugs found by hand-testing)

**Order inside this file:** H0 → H1 → H2 → H3 → H4. One session, one file. Do not stop between tasks to ask me anything unless this file says CHECKPOINT (it has none). Part 2 and Part 3 come later, only after I confirm this part.

## Prerequisites (check first; if any fails, STOP and tell me)
1. `docs/GATE.md`: P1-0, P1-1, P1-2 are PASS; tags exist. (P1-3 is done inside this file as H0.)
2. `npm run gate` is green EXCEPT G8 (top-bar geometry), which H0 fixes.
3. `git status` clean. Backup commit made.
4. Arabic/RTL/i18n is **forbidden** until I explicitly ask (G6 stays green). Do not touch it, do not mention it.

## Why this exists
I found these by using the app myself. The gate did not catch any of them, so each one first needs a test that reproduces it (RED), exactly like P1-0.

| ID | Bug (as I observe it) |
|---|---|
| H0 | Top bar still unboxed (finish old P1-3 with my answers below). |
| H1 | Number steppers: **fast repeated clicks** on the arrows raise the value 1–3 steps then it **jumps back to 0**. Slow clicks (1 per second), **hold**, and **mouse wheel/drag** work fine. |
| H2 | Some effects output **plain white** even when I change their values. **Known case: `Pencil Sketch / Crosshatch`** (checked, Amount 0 → all white; Amount 70 + Hatch 40 → white page with a few sparse dots/lines on a dark galaxy image). Others may exist; find them. |
| H3 | **Compare / before-after** (Edit → Compare, key `C`): activating it **freezes my computer** for a while, and the split handle **does not always grab** when I hover and press with the mouse. |
| H4 | The site is **too heavy on resources** (CPU/RAM). Reduce the load without changing output. |

## Rules specific to this part
- **Do NOT ask me which effect is white, which values break, or how to reproduce.** You find it yourself: read the code, run the sweep, fuzz the values, drive the real UI. This overrides the generic "ask when ambiguous" rule for H1–H4. You may only stop with BLOCKED after the exhaustive search in H2 step 5 found nothing, and then you report exactly what you tried.
- You may read and review ALL source files. Reading code is required, not optional.
- Output (pixels) of every effect must stay identical to before unless a bug is being fixed; H4 optimizations must be pixel-identical (hash) to the unoptimized render.
- Every acceptance test below becomes a permanent gate check (G9, G10, …).
- Note: P2-1 (Before/After performance) overlaps with H3. After H3 PASS, P2-1 only needs re-verification of its numbers.

---

## H0 — Top bar (finish old P1-3, my answers are final, no checkpoint)
My screenshot shows the status text (`42% 1280×720 254ms`), the moon button and the panel-toggle button still unboxed and the panel-toggle still high/clipped. Make G8 go RED → GREEN.
Confirmed inventory: red targets = status tokens (3), theme button, panel-toggle button. Purple reference = the zoom group (outer border, 6px radius, inner value box, internal 1px dividers, 44px height).
Decisions (final):
1. Status = **ONE segmented box with 3 segments** (`65%` | `1280×720` | `236ms`), same component as the zoom group: outer border, same radius, internal 1px dividers, same height and top offset. Status is NOT clickable: no hover/pressed state.
2. At 360px: reduce padding/font first; if it still does not fit, wrap the status group onto a second row of the bar. Never clip, never drop a value.
3. Theme and panel buttons: same box, border, radius, height, top offset, hover / active / focus-visible / pressed states and transitions as the zoom group. Icons centered, nothing clipped, same gap rhythm.
4. Keep the bar sticky; do not change the zoom group's look.
If G8 is already green when you start, show the output and skip H0.
**PASS:** G8 green, all other gate checks green, screenshots (dark/light × 360/1280, plus hover/focus states) opened and described honestly.

---

## H1 — Stepper arrows: rapid clicks fail, hold got slower  (TOP PRIORITY)
**H1 is the top priority. Spend all effort here until it is PASS. Do not start H2 before H1 is PASS. Order: H1 → H2 → H3 → H4.** The slow single click (≈1/s) works; rapid clicks add only 1–3 steps then the value falls back to 0; holding is slower than before; the arrows beside each effect box still do not step reliably.
**Hypothesis to test, not assume:** state is overwritten by a stale async/debounced render or handler (a re-render re-reads the default/old value), or events get queued behind a long synchronous render and the last handler writes a stale value.

**Evidence first (required before any fix):** instrument one stepper and log the exact sequence of value writes (source, old, new, timestamp) during 10 rapid clicks. Paste the log. Show which write sets it back to 0/old and from where (file:line).

**Acceptance tests (RED first), using real mouse events in the real browser, no artificial waits between clicks:**
1. For **every** numeric control (all 28+ params): 30 up-clicks at 20–40 ms spacing → value = start + 30·step (clamped to max). Then 30 down-clicks → back to start exactly.
2. Mixed bursts: 10 up, 5 down, 10 up, 3 down → exact expected value.
3. Keyboard: ArrowUp/ArrowDown 30 rapid presses, Shift/PageUp variants if supported.
4. Wheel bursts: 30 wheel ticks → exact expected value.
5. Same tests with a **heavy effect stack on a 4K image** (render is slow) — values must still be exact and the final render must match the final value.
6. Existing slow-click, hold, drag, typing tests stay green.
7. **Hold speed (regression, reported by me):** holding the arrow now steps slower than before. Find the last commit before the stepper rework (use `git log -S` / `git log --oneline -- <stepper file>`), check it out into a temp worktree, and measure values-per-second while holding an arrow for 1 s, 2 s, 3 s on 5 different controls, including with a heavy effect stack on a 4K image. The fixed version must be **≥ the old rate (within 10%)** at every duration, with a sensible initial delay (≈ 300–500 ms) then a steady repeat (≈ 15–30 steps/s, same as the old version if it was faster). Paste the old-vs-new table.
8. **Input latency:** with a heavy stack on 4K, the time from `pointerdown` on an arrow to the displayed number changing must be ≤ 16 ms. The value display updates **immediately**; the render happens afterwards and never blocks the value. If a render is still running when the next step arrives, steps are still applied (never dropped, never reset).
9. Extreme speed: 100 clicks with 0–10 ms spacing, double-click and triple-click on an arrow, and click-then-immediately-hold: exact expected values every time.
10. Test the arrows **beside every effect box** (the per-effect number inputs in the effect cards) and the arrows in the adjustments section: both groups, all 22 effects' parameters.

**Fix rules:** one source of truth for each value; every input event updates state **synchronously**; rendering only READS the latest state and never writes control values back; coalesce renders, never coalesce value writes; clamp/round in one function.

**PASS:** tests 1–6 green on all controls; write-log of the fixed flow pasted.

---

## H2 — Effects that output white (find and fix them yourself)
Do these steps in order. Paste the output of each.

**0. KNOWN FAILING CASE — `Pencil Sketch / Crosshatch` (fix this first).**
Observed: with the effect checked, **Amount 0 → the whole canvas is white** (Hatch 100). With Amount 70 / Hatch 40 on a dark galaxy picture the result is a white page with a few faint dots/lines; I expected a **crosshatched/pencil look**, with dark areas of the picture drawn with denser hatching. With the effect unchecked the picture is normal.
Required behavior (spec you must implement and test, adjust only if you can justify it with evidence):
- **Amount 0 = identity**: output equals the input exactly (hash). Amount scales the effect: `out = mix(src, sketch, amount/100)`.
- **Tonal crosshatch:** compute luminance L (0–1). Paper is light; add hatch layers by darkness: L<0.75 → 45° lines, L<0.50 → −45° lines, L<0.30 → 0°/90° lines, L<0.15 → dense cross layer. **Hatch** controls line spacing/density (higher = denser, never blank at either end). Line darkness uses a pencil gray, not pure black.
- Dark regions of the source must come out visibly **darker (denser hatching) than light regions**. A dark image must NOT become a white page.
- No `NaN`, no divide-by-zero at Hatch min/max, correct on any image size, deterministic.
Acceptance tests (RED first): (a) Amount 0 → pixel-identical to input; (b) on a test card with a black→white gradient, mean darkness of the output in the dark third > mean darkness in the light third by at least 25 percentage points at Amount 100; (c) output is not uniformly white for any Amount ≥ 10 and any Hatch in [min, max] on the test card AND on a dark photo-like image; (d) Hatch low vs high changes line density measurably (edge/stroke count differs by ≥ 2×); (e) full-size 4000×3000 render completes without freezing the page (no long task > 200 ms when run off the interaction path, or document the cost). Add screenshots of Amount 0 / 30 / 70 / 100 × Hatch min / 40 / max on a dark photo and a bright photo and describe each honestly.
After this, run steps 1–6 below for ALL other effects (the same kind of bug can hide in others, e.g. wrong neutral value, blank output when a parameter is at an end of its range).

**1. Code review of every effect (before running anything).** Open the source of EVERY effect and the code that connects UI controls to effect parameters. For each effect write one row in `docs/GATE.md`: effect | params (type, min, max, step, default, neutral) | math hazards found (division by zero, missing clamp, uint8 overflow/wraparound, `NaN`/`Infinity` paths, string-vs-number math like `"50"+1`, undefined param at some steps, wrong alpha/blend, gamma/color-space errors, reused or uninitialized buffers, order dependence, canvas-filter/shader fallback returning white) | suspected failing value ranges. No row may say "looks fine"; if no hazard is found, list the lines you checked.

**2. Parameter-path audit.** Trace how a value travels: slider/stepper/typed text → state → effect parameter → render. The white output may come from this path (value arrives as a string, empty string, `NaN`, or `undefined` while typing; wrong units; stale value). Check what the effect receives for: empty input, `-`, `.`, `0`, negative, above max, very large, `1e3`, trailing spaces.

**3. Sweep test (RED first).** Build generated test cards (gradient + color bars + gray ramp + photo-like patch) at 512×512 and 4000×3000. For **every effect**:
- Render at: min, min+1 step, default, midpoint, max−1 step, max; with `enabled` on/off; and **in pairs** with every other effect (A→B and B→A) at default and at max.
- Assert each render: no `NaN`/`Infinity` in intermediate buffers; output **not uniformly white** (mean luminance < 0.97 and std dev > 2/255 when the input has variation); not uniformly black unless defined so; alpha 255 where expected; correct dimensions; at the neutral value output equals input exactly (hash) where that is the definition.
- Print a table: effect | value | white? | NaN? | identity at neutral? | verdict.

**4. Drive the real UI.** With Playwright, for each effect set values through the real controls (drag slider, click arrows, type digits one by one, paste, wheel), screenshot, and compute the output stats from the canvas. Include: load preset, undo/redo, theme toggle in the middle, image replaced after the effect was set. White output reachable only through the UI path counts as a failure.

**5. Exhaustive fuzz if nothing failed yet.** Do NOT ask me. Widen the search: 2,000 random values per parameter (including edge values and non-integers), random stacks of 2–8 effects with random order, small (1×1, 2×2, 17×13) and huge images, grayscale/transparent/CMYK-like/16-bit inputs, animated or video frames, portrait/landscape. Log every white or NaN result with the exact repro. Only if this finds nothing, write BLOCKED with the full list of what you tried and the evidence, and wait.

**6. Fix.** For each failing effect: root cause with file:line, fix, a permanent regression case in the sweep. Output of working effects must stay pixel-identical (hash) to before.

**PASS:** code-review rows for all effects; sweep + UI-driven + fuzz green; table pasted; every failure has a root-cause line and a regression case.

---

## H3 — Compare freeze + unreliable handle
**Evidence first:** record, for toggling Compare on a 1280×720 and a 4K image: longest main-thread task (`longtask`), total blocked ms, number of pipeline invocations, number of canvas/ImageBitmap allocations, number of event listeners added/removed (leak check: toggle 20×), whether a `requestAnimationFrame` loop stays running, and any `getImageData`/`toDataURL`/CSS filter on a huge canvas during drag. Paste numbers and the culprit with file:line.

**Acceptance tests (RED first):**
1. Toggling Compare on/off: no long task > 100 ms; no more than 2 pipeline invocations per toggle; 20 toggles leave listener count, canvas count, and JS heap (after forced GC) unchanged (±5%).
2. **Grab reliability:** with real mouse events, move the pointer to the handle and press, 50 times at random vertical positions and at 3 zoom levels: **50/50** must start a drag. Hit area ≥ 24 px wide (≥ 44 px on touch), `pointer-events` and `z-index` correct, pointer capture on `pointerdown`, `touch-action: none`, no overlay intercepting events (assert with `document.elementFromPoint`).
3. Drag performance: median frame ≤ 16.7 ms, p95 ≤ 25 ms on 1280×720; median ≤ 20 ms, p95 ≤ 33 ms on 4K; **0** pipeline invocations during the drag.
4. Split stays correct after zoom, pan, resize, changing an effect value, undo/redo.

**Fix rules:** cache original and result once; dragging only moves the clip; invalidate cache only on real changes; one coalesced `rAF` per frame; cache layout rects at pointer-down; clean up listeners on toggle off.

**PASS:** tests 1–4 green with measured numbers pasted. (Then mark P2-1 as "re-verify only".)

---

## H4 — Reduce load (measure → optimize one thing at a time → re-measure)
**Baseline first (paste into `docs/GATE.md`):** for a 1920×1080 and a 4K image with 6 effects on: (a) **idle** for 5 s with nothing happening: count `rAF` callbacks, timers, observers firing, main-thread busy ms; (b) one slider drag of 3 s: renders executed, ms per render, total main-thread ms; (c) 30 rapid stepper clicks: renders executed; (d) 100 random value changes: JS heap before/after (forced GC) and canvas count; (e) video loaded and **paused**: CPU activity.

**Optimizations — apply in this order, one per commit, keep only those that show a measured gain:**
1. **Render scheduler:** a dirty flag and a single `rAF` per frame; many state changes in one frame produce one render of the latest state; skip a render if the state hash is unchanged.
2. **True idle:** when nothing changed, **zero** `rAF` callbacks, no polling timers/intervals; stop everything when `document.hidden`; do not process video frames while paused or hidden.
3. **Pipeline stage cache:** cache each effect stage's output keyed by (input hash, params). Changing effect k recomputes only k…n, never 0…k−1.
4. **Neutral bypass:** disabled effects or effects at their neutral value are skipped.
5. **Memory hygiene:** decode the image once into an `ImageBitmap` and reuse; reuse `ImageData`/buffers instead of allocating per frame; revoke object URLs; release temporary canvases (`width = 0`).
6. Do NOT add a Worker here (that is P2-2). Do NOT change output.

**Acceptance tests (RED where a baseline exists, then GREEN):**
- **Idle:** 0 `rAF` callbacks and 0 timer firings in 5 s with nothing changing, and 0 when the tab is hidden.
- **Coalescing:** 30 rapid stepper clicks → renders ≤ number of animation frames elapsed; final render equals the final value (hash).
- **Stage cache:** changing the last effect's value re-runs exactly 1 stage (counter test); changing the first re-runs all.
- **Identical output:** for 20 random stacks, optimized render hash equals the unoptimized (cache disabled) render hash.
- **Memory:** after 100 random value changes and forced GC, JS heap ≤ +20% of the start and canvas count constant.
- **Gain:** per-render ms with the heaviest stack reduced by ≥ 30% vs baseline, or write a measured explanation of why not.

**PASS:** all green; before/after table of every baseline number pasted.

---

## Hotfix final report
Use the standard final-report format. Add a table: bug | root cause (file:line) | test id | before → after numbers.

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
