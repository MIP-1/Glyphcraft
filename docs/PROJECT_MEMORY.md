# Glyphcraft — Project Memory (handoff)

Snapshot date: 2026-10-24. Put this file at `docs/PROJECT_MEMORY.md`. Read it at the start of every new session, then read `docs/GATE.md`.
English only. Do not add Arabic anywhere in the repo (gate check G6).

## 1. What Glyphcraft is
Web app (HTML/CSS/JS, built with opencode) that loads an image or video and applies glyph/script, dither, and stackable effects, with output format, size presets, width/height, fit, zoom, before/after compare, undo/redo, presets, export. Website font: Goodmountain (website only). Repo: `~/glyphcraft`. Dev machine: CachyOS + Hyprland, browser Zen with a custom `userContent.css`.

## 2. Owner decisions (final, do not revisit unless the owner says so)
- **Arabic / RTL / i18n: removed and forbidden** until the owner asks for it. No Arabic characters in the repo (gate G6). It is the LAST thing, if ever.
- `View → Theme` and `View → Light theme` do NOT exist (gate G7). Theme toggles only via key `T` and the top-bar icon.
- Sticky Export Image / Reset All bar stays. Editable value boxes stay. Size presets with Custom stay.
- Light and dark themes must both be fully consistent: effect cards, chips, menus, inputs.
- Menus (File, View, Edit, dropdowns) use the INVERSE theme (dark theme → light panel, light theme → dark panel).
- Top bar: status readout becomes ONE segmented box with 3 segments (`65%` | `1280×720` | `236ms`), same component style as the zoom group (border, 6px radius, 1px inner dividers, 44px height); status is not clickable (no hover). Theme and panel-toggle buttons get the same box, states, transitions. At 360px reduce padding first, then wrap to a second row; never clip or drop a value.
- Phone presets: real models only, newest first (iPhone 18 Pro Max … iPhone 12 base; Samsung S26 Ultra … same-year-as-iPhone-12 and later), three iPhone 18 entries visible by default, then animated "View more / View less". Aspect swatch left of every size name.
- The agent must find bugs by itself (read code, sweep values, drive the UI). It must not ask the owner which effect or value fails.
- Quality bar: no "done/ok/probably". Evidence only (see section 5).

## 3. Work plan and status

| Part | File (in `docs/prompts/`) | Content | Status |
|---|---|---|---|
| 1 | `part1_gate_foundation.md` | P1-0 gate, P1-1 remove Arabic, P1-2 light theme, P1-3 top bar | P1-0 PASS (commit ae85c1c, tag P1-0-pass); P1-1 PASS (2446db4); P1-2 PASS (961ede5); P1-3 NOT done (inventory recorded, code unchanged). G8 still RED (16 violations), moved into Part 1B as H0 |
| 1B | `part1b_hotfix.md` | H0 top bar; H1 stepper arrows; H2 white effects (Pencil Sketch first); H3 Compare freeze + grab; H4 reduce load | H0 PASS (7940130, tag H0-pass); H1 PASS (tag H1-pass); H2 PASS (tag H2-pass); H3 PASS (tag H3-pass); H4 NEXT |
| 2 | `part2_performance_core.md` | P2-1 before/after fps, P2-2 Worker + OffscreenCanvas, P2-3 fast preview, P2-4 undo/redo/history, P2-5 before/after finish, P2-6 presets | after the owner verifies Part 1B by hand |
| 3 | `part3_remaining_features.md` | Command Palette, drag to add effects, advanced export, batch ZIP, final regression | last |

Order: Part 1B → Part 2 → Part 3. Do not start a later part before the owner confirms the earlier one.

### Already audited feature state (verify, do not trust)
- Undo/redo exists (60-step cap, no History submenu, no disabled states). Compare exists under Edit (key `C`, hold-original on `O`; should move to View and use `B`). Presets: 7 built-ins + custom save/load, no rename/delete/import/export. Preview always downscaled (max 1600 px / 2.5 MP). No Worker. No command palette, no drag-to-add, no batch.

## 4. Known bugs (reported by the owner by hand-testing)
1. ~~**Steppers:** fast repeated clicks add 1–3 steps then the value falls back to 0; holding an arrow is slower than before; also affects the arrows beside each effect box.~~ **Fixed in H1** (shared 44×44 stepper; rapid-press reset and 6px hit strip gone; hold 21/50/78 vs 17/37/57 at 1/2/3s).
2. ~~**White output:** `Pencil Sketch / Crosshatch` — Amount 0 gives an all-white canvas (should be identity); Amount 70 / Hatch 40 on a dark galaxy image gives a white page with sparse dots (expected: tonal crosshatch, denser in dark areas). Other effects may have similar bugs.~~ **Fixed in H2** (tonal crosshatch with Amount-0 identity; Edge Detect neutral + opaque frame; Blur padded/opaque; all 22 effects swept, 1848 pairs, 115,553 fuzz renders green).
3. ~~**Compare / before-after:** activating it freezes the machine; drag runs at about 3–6 fps; the split handle does not always grab with the mouse.~~ **Fixed in H3** (post-pipeline frame cache: 36-37 pipelines per drag → 0, p95 133-183 ms → 16.8 ms; 4 px handle that lost the gesture to canvas pan → 28/44 px hit area with pointer capture; 0/50 → 50/50 grabs at 100/200/400%). P2-1 re-verifies.
4. **Load:** site too heavy on CPU/RAM; plan = render scheduler, true idle, per-stage cache, neutral bypass, memory hygiene (no Worker until P2-2). (H4)
5. **Top bar:** status text, theme icon, panel icon unboxed; panel icon sits high and is clipped. (H0)

## 5. Gate system (how work is verified)
`npm run gate` runs real-browser checks (Playwright; Firefox 157 also installed):
- G1 token lint (no hardcoded colors outside theme token blocks)
- G2 theme parity (contrast ≥ 4.5 text / ≥ 3 UI; luminance rule; fullest state with all 22 effects; toggles; reload in light; real flows; host-CSS fixture)
- G3 screenshots into `docs/evidence/<task>/`
- G4 frame timings harness (idle median 16.7 ms is just the display refresh; the Before/After drag test comes in Part 1B/2)
- G5 the 169 existing tests (`tests/test_suite.py`), count may only go up
- G6 no Arabic characters; G7 no Theme item in View; G8 top-bar geometry
- New acceptance tests from every task are added permanently (G9+).
Rules: states are PASS / FAIL / BLOCKED / HUMAN-CHECK only; test first (see it RED), fix, run gate 3× in a row, OPEN every screenshot and describe it, list 5 ways it could break, record in `docs/GATE.md`, one commit per task with tag `<task>-pass`. Never weaken a test or threshold; if a check looks wrong, show evidence and ask. After 3 failed attempts: BLOCKED. Real-device checks are HUMAN-CHECK.

## 6. Important findings
- **Light-theme bug root cause:** the owner's Zen/Noctalia `userContent.css` declares `--surface`, `--text`, `--muted` on `*` in dark OS mode, which overrode the app's inherited tokens (app showed dark cards + invisible names on a light panel). Fix: app tokens renamed `--gc-surface`, unused generic aliases removed; the gate now injects `tests/gate/host_usercontent.css` during its real flow. Keep every app CSS variable namespaced `--gc-*`.
- 22 effects: halftone, crt, glitch, vhs, pixelate, pixelsort, bloom, grain, vignette, duotone, posterize, edges, sketch, oil, emboss, blur, sharpen, invert, sepia, thermal, matrix, retro.
- The earlier "all green" reports were misleading because the tests did not cover the owner's real browser conditions. Always test the fullest state in both themes with the host CSS fixture.

## 7. Unverified / HUMAN-CHECK list
- Phone resolutions not confirmed from official specs: iPhone 18 Pro Max 1320×2868; iPhone 18 Pro and 18 1206×2622; Galaxy S26 Ultra and S26+ 1440×3120; S26 1080×2340.
- Physical Safari, real touch hardware, full moving-video WebM/MP4 export and playback.
- Owner checks by hand after each part (Ctrl+Shift+R, both themes, narrow and wide window).

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
1. Run Part 1B in one session: H0 → H1 → H2 → H3 → H4.
2. Owner verifies by hand: top bar boxed, steppers exact on rapid clicks and fast hold, Pencil Sketch Amount 0 = original and denser hatching in dark areas, Compare does not freeze and always grabs.
3. Then Part 2, then Part 3.
