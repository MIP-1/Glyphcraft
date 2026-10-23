# Glyphcraft — PART 1 of 3: Gate + Foundation

**Order:** Part 1 (this) → Part 2 (performance + core features) → Part 3 (remaining features). Do not start a later part until I confirm the earlier one.

## Why this exists
Earlier reports said "169/169 passed, 9,628 contrast pairs, 0 violations" while the light theme was visibly broken (dark effect cards, invisible effect names, black preset chips). The checks did not cover what is on screen. A green report is worthless until the checks are proven to catch the real bugs.

## Part 1 contents
| Task | What |
|---|---|
| P1-0 | Build the gate and prove it fails on the current broken build |
| P1-1 | Remove Arabic completely |
| P1-2 | Light theme parity |
| P1-3 | Top bar matches the purple reference |

## Before you start
1. `git status` clean; commit or copy the project to a backup folder.
2. Put my 5 screenshots in `docs/ref/` (names below) and OPEN each one:
   - `r3-1-topbar.png` — dark theme top bar. **Purple arrows = correct reference. Red arrows = must be fixed to match purple.**
   - `r3-2-compare.png` — before/after split.
   - `r3-3-light-top.png`, `r3-4-light-effects.png`, `r3-5-light-cards.png` — light theme bugs.
   If any file is missing, STOP and ask me.

---

## P1-0 — Build the gate

Create `npm run gate`. It runs G1–G8 (table below), prints every violation with a selector or file:line, and exits non-zero on any failure. Put scripts in `tests/gate/`. Do not touch the existing 169 tests.

### G2 — Theme parity (the critical check)
Using a real browser, for BOTH themes at BOTH 360px and 1280px:
1. Put the app in its **fullest state**: image loaded, **every available effect added to the stack**, all preset chips visible, Save/Load preset visible, Output + Size sections expanded, a value typed into at least one input.
2. Also capture, separately: each menu open (File, View, Edit, zoom menu), the size picker open (every group expanded), each `<select>` open where possible, tooltips, focus rings, hover states of buttons.
3. Walk **every visible element** (including pseudo-element backgrounds you can reach, SVG icons, checkboxes, sliders, scrollbars). For each element compute effective background (walk up ancestors until opaque) and effective text/icon color, then contrast ratio:
   - text: ≥ 4.5
   - UI borders, icons, handle dots, slider thumbs: ≥ 3
4. **Luminance rule** (this catches "dark card on a light page"):
   - Light theme: any panel / card / chip / input / button background with relative luminance < 0.35 FAILS.
   - Dark theme: any such background with relative luminance > 0.35 FAILS.
   - Allowlist (explicit, in one file, reviewed by me): preview canvas, inverse-theme menus and pickers, primary red buttons. Nothing else.
5. Toggle theme 5 times with the panel full; run the whole check after each toggle (no leftover styles from JS-set inline colors or cached classes).
6. Print every violation: selector, computed bg, computed fg, ratio, theme, width.

### G8 — Top-bar geometry (needed for P1-3)
In both themes and both widths, for every direct item in the top bar (status readout, zoom group, theme button, panel-toggle button):
- bounding box fully inside the bar (not clipped, 0 px overflow),
- same height (±1 px) and same top offset (±1 px),
- same border width and radius (±1 px) for all boxed items,
- same gap between neighbors (±1 px).

### Proof the gate works (REQUIRED before P1-1)
Run `npm run gate` on the CURRENT, unmodified code and paste the output into `docs/GATE.md`:
- **G2 MUST fail** and list the dark effect cards, black preset chips, and invisible effect names in light mode.
- **G6 MUST fail** (Arabic exists now).
- **G8 MUST fail** (panel-toggle icon is higher than the others and clipped).
- **G7**: record whether it passes or fails today.
If G2, G6 or G8 pass on the current build, the gate is broken: fix the gate until each fails for the right reason, show me the output, and only then continue.

**PASS for P1-0:** the three required RED outputs pasted; gate scripts committed; `docs/GATE.md` created with the template.

---

## P1-1 — Remove Arabic completely
- Delete all Arabic strings, language switch, RTL / `dir` logic, Arabic fonts, Arabic test cases, Arabic text in README and docs.
- English only, plain strings. Do not leave an i18n framework or dead language files behind.
- Verify `G6` goes from RED to GREEN. Verify G7 stays/becomes GREEN (no Theme item in View).
- Break-it examples to test: first load with an Arabic browser locale, `dir` attribute on `<html>`, error messages, tooltips, file-open messages.

**PASS:** G6 and G7 green, 169 old tests green (update only the tests that asserted Arabic behavior, and list each one in `docs/GATE.md` with the reason — this is the only allowed test edit in this task).

---

## P1-2 — Light theme parity

**Seen in my screenshots 3, 4, 5:** in light theme the effect cards stay dark; effect names are invisible (dark text on dark); preset chips are black rectangles with no readable text; the 6-dot handle is barely visible; light buttons sit on dark card backgrounds.

**Do:**
1. Find the root cause (hardcoded colors, wrong token, JS inline styles, a class that only sets the dark value, missing `color-scheme`). Write it with file:line evidence.
2. Fix **everything G2 reports**, not only what the screenshots show. Dynamically added effects, chips, presets, empty/disabled/hover/focus/active states all use tokens.
3. Both themes must look intentionally designed: same layout, same spacing, same component shapes; only token values differ.
4. Every effect type must be added and checked individually (not just 3 of them).

**PASS:** G2 green in both themes at both widths in the fullest state; G1 green; screenshots of the fullest state (dark + light × 360 + 1280) each described honestly with zero remaining mismatch listed.

---

## P1-3 — Top bar matches the purple reference

**In `r3-1-topbar.png`:** purple arrows point at elements that already look right (bordered boxes, consistent height, aligned, hover/active states). Red arrows point at elements that don't.

### CHECKPOINT (stop here, change no code)
Write in `docs/GATE.md`, and print in the chat, two numbered lists:
- every RED-arrow target you identified (name + what is wrong),
- every PURPLE-arrow target you identified (this is the reference style).
My reading: red = status readout (`65% 1280×720 236ms`), theme icon, panel-toggle icon, and the lines/separators next to them. Say whether you agree or see more. **Wait for my confirmation before touching code.**

### After my confirmation
- Make every red target use the same system as the purple ones: same box style (border, radius, height, padding, background token), same hover / active / focus / pressed states, same transitions. One shared class/component, not copied CSS.
- Everything on one row and one baseline. The panel-toggle icon currently sits higher than the others and is clipped (screenshots 3, 4, 5): fix it.
- Same spacing rhythm at 360px and 1280px, both themes.
- Keep the bar sticky. Do not change the zoom group's look (it is the reference).

**PASS:** G8 goes RED → GREEN; G2 stays green; the 4 screenshots (dark/light × 360/1280) described honestly; hover and focus states captured and described.

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
