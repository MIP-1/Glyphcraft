# Glyphcraft — Project Memory (handoff)

Snapshot date: 2026-11-08. Put this file at `docs/PROJECT_MEMORY.md`. Read it at the start of every new session, then read `docs/GATE.md`.
English only. Do not add Arabic anywhere in the repo (gate check G6).

## 1. What Glyphcraft is
Web app (HTML/CSS/JS, built with opencode) that loads an image or video and applies glyph/script, dither, and stackable effects, with output format, size presets, width/height, fit, zoom, before/after compare, undo/redo, presets, export. Website font: Goodmountain (website only). Repo: `~/glyphcraft`. Dev machine: CachyOS + Hyprland, browser Zen with a custom `userContent.css`.

## 2. Owner decisions (final, do not revisit unless the owner says so)
- **Arabic / RTL / i18n: removed and forbidden** until the owner asks for it. No Arabic characters in the repo (gate G6). It is the LAST thing, if ever.
- `View → Theme` and `View → Light theme` do NOT exist (gate G7). Theme toggles only via key `T` and the top-bar icon.
- Sticky Export Image / Reset All bar stays. Editable value boxes stay. Size presets with Custom stay.
- Light and dark themes must both be fully consistent: effect cards, chips, menus, inputs.
- Menus (File, View, Edit, dropdowns) use the INVERSE theme (dark theme → light panel, light theme → dark panel).
- Top bar: status readout becomes ONE segmented box with 3 segments (`65%` | `1280×720` | `236ms`), same component style as the zoom group (border, 6px radius, 1px inner dividers, 44px height); status is not clickable (no hover). Theme and panel-toggle buttons get the same box, states, transitions.
- **Mobile = viewport width ≤700 CSS px, any orientation.** The layout is one column: a single top-bar row (≤56 px + safe-area top) with menu, zoom, theme and sheet toggle; the preview; and a bottom sheet that never overlaps the preview. The status box lives in the sheet handle row on mobile. File/View/Edit are inside the mobile menu with the inverse palette; every command and shortcut stays reachable. At 320/360 px reduce padding and gaps first; never wrap, clip or drop a control. Widths 701–768 keep the old overlay layout; widths >700 must stay layout-identical to before Part M (G17). At height <500 px there is no separate layout; the next step is a landscape-specific snap after real-device testing.
- Phone presets: real models only, newest first (iPhone 18 Pro Max … iPhone 12 base; Samsung S26 Ultra … same-year-as-iPhone-12 and later), three iPhone 18 entries visible by default, then animated "View more / View less". Aspect swatch left of every size name.
- The agent must find bugs by itself (read code, sweep values, drive the UI). It must not ask the owner which effect or value fails.
- Quality bar: no "done/ok/probably". Evidence only (see section 5).

## 3. Work plan and status

| Part | File (in `docs/prompts/`) | Content | Status |
|---|---|---|---|
| 1 | `part1_gate_foundation.md` | P1-0 gate, P1-1 remove Arabic, P1-2 light theme, P1-3 top bar | P1-0 PASS (commit ae85c1c, tag P1-0-pass); P1-1 PASS (2446db4); P1-2 PASS (961ede5); P1-3 PASS (commit 855a5b4, tag `P1-3-pass`; fresh G8 evidence and 62 screenshots in `docs/evidence/p1-3/`) |
| 1B | `part1b_hotfix.md` | H0 top bar; H1 stepper arrows; H2 white effects (Pencil Sketch first); H3 Compare freeze + grab; H4 reduce load | H0 PASS (7940130, tag H0-pass); H1 PASS (tag H1-pass); H2 PASS (tag H2-pass); H3 PASS (tag H3-pass); H4 PASS (commits da8e572, 81f6e00, 6c3031e, 9cdc711, a6909ee; tag H4-pass) |
| 1C | `part1c.md` | C1 audit Part 1B, C2 video play/pause control, C3 multi-effect cost | C1/C2/C3 PASS (one commit, tags `C1-audit-pass`, `C2-video-control-pass`, `C3-perf-pass`; see `docs/GATE.md` Part 1C and `docs/HANDOFF_PART1C.md`). One commit for three tasks because the control exposed the pointer-capture bug and the perf work exposed the preview-collapse bug; the commit body records the departure from one-commit-per-task |
| 2 | `part2_performance_core.md` | P2-1 before/after fps, P2-2 Worker + OffscreenCanvas, P2-3 fast preview, P2-4 undo/redo/history, P2-5 before/after finish, P2-6 presets | **P2-1 PASS (tag `P2-1-pass`, gate runs 5–7).** `originalBitmap` cache (drawOriginal 9.9 → 0.07 ms/frame; 4K render median 10.2 → 0.6 ms), band-only split repaint, paired G11/G13 budgets, 7/7 break-it cases, 62 screenshots. Post-PASS cleanup PASS (tag `P2-1-cleanup-pass`, gate runs 8–10). P2-2 … P2-6 NOT STARTED |
| M | `partM_mobile.md` | M1-1 mobile bottom sheet; M1-2 single-row mobile top bar | **M1-1 PASS and M1-2 PASS**, one commit on `main`, tags `M1-1-pass` / `M1-2-pass`; permanent G14–G18, G8 mobile rule changed with RED proof, 14/14 break-it; gates 1–3 in `docs/evidence/m1-2/`. Two tasks share one commit because M1-2 builds directly on the M1-1 mobile branch; `docs/GATE.md` records that M1-1 was proven RED→green in isolation but not separately full-gated 3× |
| 3 | `part3_remaining_features.md` | Command Palette, drag to add effects, advanced export, batch ZIP, final regression | NOT STARTED |

Order: Part 1B → Part 2 (P2-1) → Part M (mobile) → Part 2 (P2-2 … P2-6) → Part 3. Do not start a later part before the owner confirms the earlier one.

Post-PASS cleanup (2026-11-04, tag `P2-1-cleanup-pass`): explanatory comments and three dead functions removed; `npm run build` writes a minified `dist/` (gitignored) and `tools/dist_smoke.py` proves source and dist render the same canvas; Sepia/Thermal amount 0 now skip the per-pixel pass byte-identically (13.0/17.6 → 0.0 ms); a Retro rewrite measured 1.0× and was reverted. Gates 8–10 PASS.

Part M (2026-11-08, tags `M1-1-pass` / `M1-2-pass`, one commit): mobile ≤700 px is a column with a single 56 px top-bar row and a bottom sheet. Snaps derive from `visualViewport` (peek 105 px at 360 = handle + sticky bar + safe area, half 45%, full 88%); the sheet never overlaps the preview. Drag uses Pointer Events; grabber tap cycles; handle is an ARIA separator with Arrow keys and Enter/Space. Status moved into the handle row as the same component. Soft keyboard/safe-area handled via `--gc-vvh` + `viewport-fit=cover`. All mobile touch targets ≥44×44, inputs ≥16 px, numeric `inputmode="decimal"`, reorder long-press only. Mobile menu holds all 14 File/View/Edit commands in the inverse palette. 701–768 keeps the old overlay; G17 proves 1280×720 and 701×800 unchanged. G14–G18 are permanent. 14/14 break-it; 169 tests, G1–G13 and contrast green; gates 1–3 PASS.

### Already audited feature state (verify, do not trust)
- Undo/redo exists (60-step cap, no History submenu, no disabled states). Compare exists under Edit (key `C`, hold-original on `O`; should move to View and use `B`). Presets: 7 built-ins + custom save/load, no rename/delete/import/export. Preview always downscaled (max 1600 px / 2.5 MP). No Worker. No command palette, no drag-to-add, no batch.

## 4. Known bugs (reported by the owner by hand-testing)
1. ~~**Steppers:** fast repeated clicks add 1–3 steps then the value falls back to 0; holding an arrow is slower than before; also affects the arrows beside each effect box.~~ **Fixed in H1** (shared 44×44 stepper; rapid-press reset and 6px hit strip gone; hold 21/50/78 vs 17/37/57 at 1/2/3s).
2. ~~**White output:** `Pencil Sketch / Crosshatch` — Amount 0 gives an all-white canvas (should be identity); Amount 70 / Hatch 40 on a dark galaxy image gives a white page with sparse dots (expected: tonal crosshatch, denser in dark areas). Other effects may have similar bugs.~~ **Fixed in H2** (tonal crosshatch with Amount-0 identity; Edge Detect neutral + opaque frame; Blur padded/opaque; all 22 effects swept, 1848 pairs, 115,553 fuzz renders green).
3. ~~**Compare / before-after:** activating it freezes the machine; drag runs at about 3–6 fps; the split handle does not always grab with the mouse.~~ **Fixed in H3** (post-pipeline frame cache: 36-37 pipelines per drag → 0, p95 133-183 ms → 16.8 ms; 4 px handle that lost the gesture to canvas pan → 28/44 px hit area with pointer capture; 0/50 → 50/50 grabs at 100/200/400%). P2-1 re-verifies.
4. ~~**Load:** site too heavy on CPU/RAM.~~ **Fixed in H4** (dirty-flag scheduler with one rAF per frame and an unchanged-state skip; true idle — paused video 301 → 0 rAF/5 s, hidden tab 84 → 0 rAF and 2999 → 5 ms; per-stage chain cache so changing the last effect runs 1 stage instead of 6, warm render 843 → 291 ms; neutral bypass 543.8 → 128.5 ms at 4K, output byte-identical; +4.05% heap, constant canvas count. No Worker, no output change).
5. **Top bar:** status text, theme icon, panel icon unboxed; panel icon sits high and is clipped. (H0)

## 5. Gate system (how work is verified)
`npm run gate` runs real-browser checks (Playwright; Firefox 157 also installed):
- G1 token lint (no hardcoded colors outside theme token blocks)
- G2 theme parity (contrast ≥ 4.5 text / ≥ 3 UI; luminance rule; fullest state with all 22 effects; toggles; reload in light; real flows; host-CSS fixture)
- G3 screenshots into `docs/evidence/<task>/`
- G4 frame timings harness (idle median 16.7 ms is just the display refresh; the Before/After drag test comes in Part 1B/2)
- G5 the 169 existing tests (`tests/test_suite.py`), count may only go up
- G6 no Arabic characters; G7 no Theme item in View; G8 top-bar geometry
- G9 numeric steppers; G10 effect sweep; G11 compare split; G12 load/idle; G13 video control + multi-effect playback
- G14 mobile layout (≤700 px: one column, no overlap, one-row bar, snaps, status in handle); G15 mobile gestures (CDP touch, pipeline idle during drag, touch Compare); G16 touch targets ≥44×44 with zero exceptions; G17 desktop unchanged (1280×720 and 701×800 rects); G18 mobile menu reachability + contrast parity
- New acceptance tests from every task are added permanently (G9+).
Rules: states are PASS / FAIL / BLOCKED / HUMAN-CHECK only; test first (see it RED), fix, run gate 3× in a row, OPEN every screenshot and describe it, list 5 ways it could break, record in `docs/GATE.md`, one commit per task with tag `<task>-pass`. Never weaken a test or threshold; if a check looks wrong, show numbers from 3+ runs, prove the replacement still fails a deliberately slowed build, and record the old rule, new rule and reason in `docs/GATE.md`. After 3 failed attempts: BLOCKED. Real-device checks are HUMAN-CHECK.

## 6. Important findings
- **Light-theme bug root cause:** the owner's Zen/Noctalia `userContent.css` declares `--surface`, `--text`, `--muted` on `*` in dark OS mode, which overrode the app's inherited tokens (app showed dark cards + invisible names on a light panel). Fix: app tokens renamed `--gc-surface`, unused generic aliases removed; the gate now injects `tests/gate/host_usercontent.css` during its real flow. Keep every app CSS variable namespaced `--gc-*`.
- 22 effects: halftone, crt, glitch, vhs, pixelate, pixelsort, bloom, grain, vignette, duotone, posterize, edges, sketch, oil, emboss, blur, sharpen, invert, sepia, thermal, matrix, retro.
- The earlier "all green" reports were misleading because the tests did not cover the owner's real browser conditions. Always test the fullest state in both themes with the host CSS fixture.

## 7. Unverified / HUMAN-CHECK list
- Phone resolutions not confirmed from official specs: iPhone 18 Pro Max 1320×2868; iPhone 18 Pro and 18 1206×2622; Galaxy S26 Ultra and S26+ 1440×3120; S26 1080×2340.
- Real mobile browsers: Android Firefox/Chrome and iOS Safari sheet drag feel, grabber tap cycle, soft keyboard and URL-bar collapse, and real-device frame rate are NOT claimed. The gate runs headless Chromium with CDP touch.
- Real touch hardware: Compare split grab at 100/200/400% and the sheet handle gesture (headless reports 20/20 grabs, 0 pipeline calls during drag).
- Mobile landscape (height <500 px) has no separate layout yet; 640×360 is usable with a 199 px peek preview. A landscape-specific snap is a next step after real-device testing.
- Physical Safari, full moving-video WebM/MP4 export and playback.
- Owner checks by hand after each part (Ctrl+Shift+R, both themes, narrow and wide window, one real phone).

## 8. Tools and environment
- Agent: opencode (DeepSeek, about 200k token context). When the context fills, work degrades and rules get forgotten → **open a new session after every PASS task** and resume from this file + `docs/GATE.md`.
- Rigor skills installed globally in `~/.config/opencode/skills/`: `using-rigor-skills`, `rigor-gate`, `verify-before-claim`, `root-cause-debugging`, `test-first`, `code-audit`, `ui-visual-audit`, `design-consistency`, `perf-measure`. A merged master skill `exactitude` was designed but NOT built yet. Source pack: `~/rigor-skills-build/` (has `validate.sh`, `tests/run-pressure.sh`, `AGENTS.snippet.md`). Pressure tests are HUMAN-CHECK (nested `opencode run` fails on the free tier).
- Reference screenshots in `docs/ref/`: `r3-1-topbar.png` (purple = reference style, red = fix), `r3-2-compare.png`, `r3-3-light-top.png`, `r3-4-light-effects.png`, `r3-5-light-cards.png`. The owner's light-theme screenshots are NOT stale: they came from his browser CSS.
- Older prompts in the repo (`glyphcraft-round2-prompt.md`, "Phase 1–8") are obsolete: ignore them.

## 9. Resume message (paste at the start of a new session)
```
Load skills: using-rigor-skills, rigor-gate, verify-before-claim, root-cause-debugging, test-first, perf-measure, code-audit, ui-visual-audit.
Read docs/PROJECT_MEMORY.md, then docs/GATE.md, then the current part file in docs/prompts/. Use ONLY that part file. Ignore older prompts.
Continue from the first task that is not PASS. Do not ask me which effect or value fails; find it yourself. Do not touch Arabic/i18n.
```

## 10. Next actions
1. Part 1, Part 1B, Part 1C, P2-1 and Part M are PASS, each tagged `<task>-pass`; Part M's three green gates are `docs/evidence/m1-2/gate-run-1/2/3.log`; P2-1's are `docs/evidence/p2-1/gate-run-5/6/7.log`; the cleanup's are `docs/evidence/cleanup/gate-run-8/9/10.log`.
2. **Next action: start P2-2** (Worker + OffscreenCanvas) from `docs/prompts/part2_performance_core.md`. Write its acceptance check first, see it RED, then implement.
3. Then P2-3 fast preview, followed by P2-4 to P2-6 in order. Do not start P3 before the owner confirms Part 2.
4. Mobile landscape refinement (height <500 px): keep the current working layout, then add a landscape-specific snap after real-device testing.
5. After each task: open every screenshot, list 5 ways it could break, run the full gate 3× in a row, record the block in `docs/GATE.md`, commit and tag `<task>-pass`.
6. Then Part 3 (P3-1 … P3-5).
7. Owner verifies by hand after each part.
