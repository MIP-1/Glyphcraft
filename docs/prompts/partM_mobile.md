@blackhole @super-nova @rigor-gate @using-rigor-skills @ux-ui-architect @namethatui @chief-of-staff @browser @tailwind-css-patterns @vercel-react-best-practices @code-audit @brainstorming @design-consistency @git-release @kotlin-specialist @performance-optimization @perf-measure @vision-to-code @test-first @tmux @test-driven-development Load skills: using-rigor-skills, rigor-gate, verify-before-claim, root-cause-debugging, test-first, perf-measure, code-audit, ui-visual-audit, design-consistency. (Add namethatui only if installed.)

PART M: MOBILE. Two tasks, in order: M1-1 bottom sheet, M1-2 single-row top bar.
Repo: ~/glyphcraft. English only. No Arabic/i18n anywhere (gate G6). Do not touch P2-2, effects, the pipeline, or stepper behavior. Stop after M1-2 PASS.

## 0. Orient (evidence first, no trusting memory files)
Run: git status -sb, git log --oneline -8, git tag --list "*-pass", read README.md, tail of docs/GATE.md, docs/PROJECT_MEMORY.md sections 2/3/5. Expected: HEAD 3d9e6f2, clean, tags up to P2-1-cleanup-pass. If not, explain and fix before anything else.
First action: save this whole prompt verbatim as docs/prompts/partM_mobile.md (it goes into the M1-1 commit).

## 1. The problem (owner screenshot, real phone, CSS viewport about 360 wide)
- The controls panel is a full-height overlay on the right. It covers about 87% of the width. Only a ~13% strip of the image shows. Editing a value hides the result of the edit.
- The top area uses 3 rows before the image: File/View/Edit; zoom group + theme + panel buttons; status box. With the browser bars this is over a quarter of the screen.
- Preview render is 384 ms at this size (do not fix here; that goes to P2-2).
Goal: on phones the image stays visible while the user edits. The panel never covers the image. Everything still works.

## 2. Hard rules from the owner (do not revisit)
- Mobile means viewport width <= 700 CSS px, any orientation. Above 700 px the desktop layout must stay exactly as it is now (measure, see G17).
- Do NOT drop or hide any feature. Everything reachable on desktop stays reachable on mobile.
- Sticky Export Image / Reset All bar stays. Editable value boxes stay. Size presets with Custom stay. Status readout stays: ONE segmented box with 3 segments (zoom %, WxH, ms), never clipped, never dropped, not clickable.
- No View -> Theme / Light theme item (G7). Theme toggles only by key T and the top-bar icon.
- Menus (File, View, Edit, dropdowns) use the INVERSE theme.
- Both themes fully consistent for every new component. Every CSS variable is namespaced --gc-*; no hardcoded colors outside token blocks (G1). The host userContent.css fixture must stay injected in gate flows.
- App code holds instructions only: no explanatory comments (short section markers are fine). Source stays readable; npm run build and tools/dist_smoke.py must still pass (source hash == dist hash).
- Mobile optimization is the point of this part. Do not do the minimum. Treat each item below as required.

## 3. M1-1: bottom sheet (mobile only)
Layout, not overlay: the page becomes a column. Top bar, then the preview region, then the sheet. The canvas fits inside the preview region only. The sheet never overlaps the canvas (the preview region shrinks when the sheet grows).
Sheet contents = the existing controls panel (same DOM, same logic; do not fork or duplicate controls).
Snap points (heights are fractions of the visual viewport height, from window.visualViewport, never plain vh):
- peek: handle row + status box + sticky Export/Reset bar only (about 112 px, derive from tokens).
- half: 45%.
- full: 88%.
Default: half when no image is loaded; peek when an image or video is loaded and the user has not touched the sheet. Remember the last snap in memory only (no localStorage).
Behavior:
- Drag handle row (grabber bar + status row) with Pointer Events and pointer capture; snap to nearest point by position plus velocity (flick). Tap the grabber cycles peek -> half -> full -> peek. The existing panel-toggle icon switches peek <-> half.
- The drag zone is ONLY the handle row. The controls list scrolls inside the sheet with overscroll-behavior: contain. Scrolling the list never moves the sheet; dragging the handle never scrolls the list; the page itself never scrolls (document scrollTop stays 0, no rubber-band).
- touch-action: none on the handle; touch-action: pan-y on the list. Do not break existing canvas pan/pinch/zoom or the Compare split handle by touch.
- While dragging: do NOT re-run the effect pipeline per frame. Move the sheet with transform; keep the canvas as is (CSS scale only if needed). After settle: one refit, at most one render. Count pipeline calls in the gate: 0 during drag, <= 1 after settle.
- Keyboard accessibility: handle is role="separator" with aria-valuenow and aria-valuemin/max; ArrowUp/ArrowDown change snap; Enter/Space cycles.
- prefers-reduced-motion: no animated snap (instant). Otherwise use the existing transition tokens, not new magic numbers.
- Soft keyboard: size from visualViewport (resize + scroll events) so the sheet sits above the keyboard and the focused input is scrolled into view inside the sheet; image stays visible above. Safe-area insets (env(safe-area-inset-*)) on the bottom; meta viewport with viewport-fit=cover; use dvh where CSS units are needed.
- Status box moves into the sheet handle row on mobile (same component and style, same 3 segments). This resolves the owner rule "never drop a value" because the top bar no longer has room for it.
- Touch targets: every interactive element in the sheet and top bar >= 44 x 44 CSS px on mobile (pointer: coarse OR width <= 700). That includes stepper arrows (CSS size only; do NOT change stepper logic, G9 must stay green), checkboxes, Reset links, section headers (the whole header row is the hit area), select boxes, swatch rows, the 6-dot reorder grip. Reorder stays hold-to-drag (long press) so it does not fight list scrolling.
- Text: value boxes and inputs font-size >= 16 px on mobile (prevents iOS zoom-on-focus). Section titles and Reset links larger and higher contrast than now (contrast gate still >= 4.5 text / >= 3 UI).
- inputmode on numeric value boxes: use "decimal" ONLY where the control's min >= 0. For controls whose min < 0, do not set it (the decimal keyboard has no minus sign). Read each control's range from code; do not guess. Clamping logic untouched.
- Landscape (height < 500): no new layout. It only has to be usable: no overflow, controls reachable, peek keeps >= 120 px for the preview region. A real landscape layout is a later task; write it into README Next steps.

## 4. M1-2: single-row top bar (mobile only)
- One row, height <= 56 px (plus safe-area top). Contents: menu button, zoom group (minus, %, plus; same component as now), theme button, sheet-toggle button.
- File / View / Edit move under the menu button (a menu in the inverse theme listing the three groups with their existing items, same shortcuts text). Every existing command stays reachable; keyboard shortcuts unchanged.
- Order of squeeze at 360 and at 320: reduce padding and gaps first. Never wrap to a second row, never clip, never drop a button.
- Same border, 6 px radius, 1 px dividers, states and transitions as the existing groups.
- Desktop top bar untouched (G8 desktop rules stay).
- G8 at <= 700 px currently expects the old 2-3 row layout. This is an owner-requested app change, not a machine-measuring problem, so: replace the mobile expectations deliberately, record old rule / new rule / why in docs/GATE.md, and prove the new mobile G8 still goes RED on a deliberately broken build (for example one top-bar button pushed off-screen, or one status segment removed). Revert the break afterwards.

## 5. Test first (see RED before any code)
Add permanent checks (Chromium via Playwright; isMobile, hasTouch, deviceScaleFactor 2; swipes via CDP Input.dispatchTouchEvent; Firefox only for layout checks). Viewports (CSS px, browser bars included): 360x680, 390x750, 412x800, 320x568 (small), 740x360 (landscape). Dark + light, host CSS fixture on. Fullest state (all 22 effects stacked) plus the empty state plus a loaded video.
- G14 mobile layout: no horizontal overflow; top bar one row <= 56 px; preview region fraction of viewport height >= 70% at peek and >= 40% at half; canvas rect fully inside the preview region; elementFromPoint at the canvas center is the canvas, never the sheet; sheet bottom = viewport bottom minus safe area.
- G15 sheet gestures: swipe up/down moves peek <-> half <-> full; flick snaps by velocity; tap grabber cycles; list scroll does not move the sheet; handle drag does not scroll the list; document scrollTop stays 0; pipeline calls 0 during drag and <= 1 after; simulated keyboard (visualViewport shrink via CDP device metrics override) keeps the focused input visible above the keyboard.
- G16 touch targets: enumerate every visible interactive element in top bar and sheet (all snaps); each >= 44x44. Zero exceptions unless you list one with a reason in GATE.md and the owner can see it.
- G17 desktop unchanged: record bounding rects of top bar, panel, preview, status, zoom group at 1280x720 and 701x800 BEFORE changing code; after the change they must be identical. This is the guard against regressions above 700.
- G18 menu reachability: list of all File/View/Edit items on desktop equals the list reachable through the mobile menu button; theme parity of the new menu, sheet, handle, status in both themes (extend G2 cells to 360 + the new components; contrast >= 4.5/3).
- Touch Compare: split handle grabbed by touch 20/20 at 360x680 at 100/200/400% zoom. If it fails and the cause is the new sheet, fix it; if it is an old bug, log it in README Next steps and do not widen scope.
- Existing: G1..G13 and the 169 tests must stay green; count may only go up. Never weaken a check. Gate rules may change only when a check measures the machine, not the app; show numbers first.
Capture baseline screenshots + measurements of the CURRENT mobile layout first (proves the problem: image strip ~13% wide, 3 top rows). They go in docs/evidence/m1-0/.

## 6. Process (same as before)
Per task: test first (RED), implement, npm run gate three times in a row (background, poll the log; each run is about 25 min; never interrupt), OPEN and describe every screenshot (contact sheets plus full-res spot checks), list at least 8 break-it cases and run them, record in docs/GATE.md, one commit + tag per task (M1-1-pass, M1-2-pass), push branch and tags. Three failed attempts = BLOCKED with evidence. States: PASS / FAIL / BLOCKED / HUMAN-CHECK only; no "done/ok/probably".
Break-it list (minimum): keyboard open while editing a value; rotate portrait <-> landscape mid-drag; fast flick past full; drag the sheet while a menu is open; theme switch mid-drag; undo/redo while at peek; width 320; browser text zoom 200%; reduced motion; empty state; video loaded; 22 effects stacked and scrolled in full; select dropdown opened at half; Compare on at peek.
Find bugs yourself. Do not ask me which control or value fails.
README rule: before the final reply update README.md (Current status with commit + tag, Done in this step, Next steps with the first item = next action, HUMAN-CHECK list, date) and mirror it in docs/PROJECT_MEMORY.md sections 3/10 (add Part M). Then git status -sb must be clean and not ahead; show git tag --list "*-pass".
HUMAN-CHECK to list (never claim): real Android Firefox/Chrome and iOS Safari, real touch feel, real soft keyboard, URL-bar collapse behavior, real-device frame rate while dragging the sheet.
Stop after M1-2. Do not start P2-2.
