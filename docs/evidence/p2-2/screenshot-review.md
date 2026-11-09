# P2-2 screenshot review — individual pass

Source: `docs/evidence/p2-2-run-3/` (68 PNG files: 58 G3 chrome states + 10 G14 mobile cells).
Reviewed on 2026-11-09 in filename order, batches of 12. Every file opened at full size.

Common to every dark 1280x900 shot: dark surface tokens, File/View/Edit menubar at
top-left, zoom group and theme/panel buttons top-right, status `100% · 900×600 · 2236ms`,
black preview area with red monospace glyph art on the left, cream right panel.
No horizontal scrollbar, no clipped labels, no mixed light surfaces.

## Batch 1 — dark 1280 (12 files)

1. `dark-1280-edit-menu.png` — Edit menu open below EDIT (x≈112–328), light inverse panel, items Undo / Redo / Compare with Ctrl+Z / Ctrl+Shift+Z / C. Rows aligned, shortcut column right-aligned, no clipping.
2. `dark-1280-file-menu.png` — File menu open below FILE (x≈10–231), Open file… / Export Image… / Reset All with Ctrl+O / E / R. Light inverse panel; no clipped shadow or text.
3. `dark-1280-focus-theme.png` — no menu; theme button (moon, top-right) carries a visible 2 px focus ring. Rest of the chrome unchanged; preview and panel normal.
4. `dark-1280-fullest-effects.png` — panel scrolled to Effects: preset grid (Terminal Green, Newspaper, Cyber Glitch, Game Boy, Blueprint, Old Photo, Neon Thermal), Save/Load preset, then Halftone, CRT and Glitch / RGB Split cards. Export/Reset action bar stays at the top of the panel. No overlap or clipped values.
5. `dark-1280-fullest-top.png` — panel at scroll 0: brand, Export Image / Reset All, search field, MODE = Script, Script Options (Depth 91, Category All, Set All, empty Inject Characters, Offset 0, Text Style Regular, Use Palette checked). Geometry consistent; no clipping.
6. `dark-1280-hover-preset.png` — Effects view; "Terminal Green" preset has the hover border/background, theme button also shows its focus ring. Neighbouring presets unhighlighted.
7. `dark-1280-hover-primary.png` — Effects view; Export Image has the lighter hover gradient, Reset All remains outlined. Theme focus ring visible.
8. `dark-1280-hover-theme-tooltip.png` — Effects view with the theme button hovered. No native tooltip is painted (expected in headless Chromium); hover state itself is present. Same clean layout.
9. `dark-1280-select-focus.png` — Output section scrolled into view; Format = PNG has a visible focus ring, Size Preset = Original, Fit = Contain with Lock Ratio checked. No clipped border.
10. `dark-1280-size-picker.png` — Output section with the size picker open: search field, IPHONE group, iPhone 18/17/16 rows; "17 Pro Max 1320×2868" has the hover highlight. Light inverse popover, right-aligned inside the panel, bottom item cut by the viewport edge but the list is scrollable. No horizontal overflow.
11. `dark-1280-view-menu.png` — View menu open below VIEW: Zoom in/out, Fit window, Full page, Fit small, 100%, 200%, divider, Toggle controls panel, with shortcut column. Light inverse panel; no clipping.
12. `dark-1280-zoom-menu.png` — zoom percent dropdown open from the top bar (x≈923–1107), items Fit window / Full page / Fit small / 25–400%, 100% in accent red. Covers the brand area by design; no clipping at the panel edge.

Findings: none. The select-focus state is correct (earlier suspicion was a mis-ordered glance).

## Batch 2 — dark 360 (10 files) + light 1280 menus (2 files)

Dark 360x740 shots share: one-row top bar (hamburger, zoom −/38%/+ , moon, panel), black preview with small green glyph art, bottom sheet at peek showing the dot swatch and `38% · 900×600 · 1374ms` status inside the sheet handle, then brand, Export Image / Reset All, search and Mode. No horizontal overflow, no overlap between preview and sheet.

13. `dark-360-focus-theme.png` — theme button in the top bar; the focus ring is present but thin at this scale (the 1280 dark shot shows it clearly). Peek sheet intact.
14. `dark-360-fullest-effects.png` — sheet scrolled to Effects: preset grid, Save/Load preset, Halftone card begins at the bottom edge. Action bar (Export/Reset) stays visible; no clipped button text.
15. `dark-360-fullest-top.png` — sheet at top: brand, Export/Reset, search, MODE = Script with Reset. Consistent 16 px padding, no overflow.
16. `dark-360-hover-preset.png` — "Terminal Green" carries the hover outline; other presets plain. Layout unchanged.
17. `dark-360-hover-primary.png` — Export Image has the hover gradient; Reset All stays outlined. No layout shift.
18. `dark-360-hover-theme-tooltip.png` — theme hover state only; no native tooltip painted (headless). No other change.
19. `dark-360-mobile-menu.png` — full mobile menu opened from the hamburger: File group (Open/Export/Reset), View group (zoom/fit/100/200/panel), Edit group (Undo/Redo/Compare) in a light inverse sheet covering the preview. Shortcut column aligned; bottom of the menu ends just above the sheet search field. No text clipped.
20. `dark-360-select-focus.png` — Output controls: Format PNG has the focus ring, Size Preset Original, Fit Contain, Lock Ratio. Controls fit the 360 px sheet width.
21. `dark-360-size-picker.png` — size popover open over the sheet; searchable iPhone list shows 17 / 16 Pro Max / 16 Pro, last row cut at the popover's scroll edge. Fit/Contain remain visible below. No horizontal overflow.
22. `dark-360-zoom-menu.png` — zoom dropdown under the percentage box; Fit window / Full page / Fit small / 25–100–400%, ends above the sheet brand. Light inverse surface, no clipped edge.

23. `light-1280-edit-menu.png` — light theme at 1280x900: cream top bar and panel, dark Edit menu open with Undo/Redo/Compare. Preview is the intended black canvas with dark-red glyph art; light-theme text and borders are coherent, status `1509ms`.
24. `light-1280-file-menu.png` — dark File menu under FILE, same three commands and shortcuts; no mixed-theme control, no clipped shadow.

Findings: none. The 360 focus ring is visually thinner than at 1280 but G2 measured it at >=3:1; not recorded as a defect.

## Batch 3 — light 1280 (12 files)

25. `light-1280-focus-theme.png` — light chrome, theme button focus ring visible in dark red against cream; canvas black with dark-red art; panel and status `1509ms` normal. No mixed-theme field.
26. `light-1280-fullest-effects.png` — Effects panel in light theme: presets, Save/Load, Halftone / CRT / Glitch cards on cream cards with dark text, red accent sliders. No clipped values.
27. `light-1280-fullest-top.png` — top of the light panel; the Depth number field has the focus ring. Brand, action bar, search and Script Options all light; no leftover dark surface.
28. `light-1280-host-dark-icon.png` — host-dark fixture + app light theme: light panel and fields throughout, dark preview canvas, Effects section with Blur controls and unchecked Halftone/CRT cards. The host CSS did not override any app token.
29. `light-1280-host-dark-reload-light.png` — empty state after reload under the host-dark fixture: light top bar with "No image loaded", cream dashed drop zone, Open file button, light panel. No dark flash survived, no dark card.
30. `light-1280-host-dark-T-light.png` — same host-dark state after `T`; theme toggle shows its focus ring, the page stays light. Identical panel geometry to the icon state.
31. `light-1280-host-os-light-os-light.png` — host OS light + app light: Effects view, light surfaces, preview art, status `113ms`; no dark field or dark card.
32. `light-1280-hover-preset.png` — light Effects view, "Terminal Green" hover outline in accent red, theme focus ring. No layout shift.
33. `light-1280-hover-primary.png` — Export Image hover gradient in light theme; Reset All outline unchanged.
34. `light-1280-hover-theme-tooltip.png` — theme hover only, no native tooltip painted (headless). Panel light and consistent.
35. `light-1280-real-clean-icon.png` — no host CSS, light theme: Effects view with Blur controls and unchecked effect cards, black preview. Structure matches the host-dark shot; no host-only leak.
36. `light-1280-real-clean-reload-light.png` — no host CSS, reloaded empty light state: "No image loaded", dashed drop zone, Open file, light panel. Clean.

Findings: none. Host-CSS states show no dark panel, dark field or unreadable text.

## Batch 4 — light 1280 tail (5) + light 360 (7)

37. `light-1280-real-clean-T-light.png` — light theme after `T`; theme button ring visible, Blur controls and unchecked Halftone/CRT cards light, black preview. Consistent.
38. `light-1280-select-focus.png` — Output section, Format PNG focus ring, Size Preset Original, Fit Contain + Lock Ratio. No clipped ring.
39. `light-1280-size-picker.png` — dark inverse size popover over the light panel: search, IPHONE, rows 18 Pro Max … 16 Pro, `17 Pro Max` hovered. Fits the panel width; only the list end is cut (scrollable).
40. `light-1280-view-menu.png` — dark inverse View menu under VIEW: zoom/fit commands, 100/200%, Toggle controls panel. No mixed surface.
41. `light-1280-zoom-menu.png` — dark inverse zoom dropdown under the percentage box; Fit / 25–400%, 100% accent. Contained; no clipped edge.

Light 360x740 shots share: single-row top bar (hamburger, zoom, sun, panel), cream surfaces, black preview with light glyph art, sheet peek with dot swatch and `38% · 900×600 · 1421ms` (or later 136/148 ms) status, brand, actions, search and Mode.

42. `light-360-focus-theme.png` — theme focus was set programmatically after touch input in this cell, so Chromium paints no `:focus-visible` ring here; the layout and light tokens are correct. (The ring itself is proven by the T-key cell below and by the 1280 shot.)
43. `light-360-fullest-effects.png` — Effects sheet: presets, Save/Load, Halftone card starts at the bottom; no clipped text.
44. `light-360-fullest-top.png` — sheet top: brand, Export/Reset, search, MODE. Cream fields, dark text, no dark remnant.
45. `light-360-host-dark-icon.png` — host-dark fixture + light app: cream sheet, light fields, black preview, Effects with Blur 0 and unchecked cards; status `148ms`. No dark panel.
46. `light-360-host-dark-reload-light.png` — empty state under host-dark after reload: cream dashed drop zone, "No image loaded" in the sheet handle, Open file. No dark flash/leak.
47. `light-360-host-dark-T-light.png` — same host-dark state after `T`: the theme button has the 2 px dark-red focus ring, page stays light, geometry unchanged.
48. `light-360-host-os-light-os-light.png` — host OS light + app light: Effects sheet, cream surfaces, status `136ms`; no mixed theme.

Findings: one recorded nuance, not an app defect: the light-360 `focus-theme` capture has no visible focus ring because programmatic focus after touch does not trigger `:focus-visible` in Chromium; the keyboard-triggered state (47) shows the ring. No pixel or token defect.

## Batch 5 — light 360 tail (10) + G14 dark 360x680 (2)

49. `light-360-hover-preset.png` — light Effects sheet; Terminal Green carries the hover border; card grid and Save/Load unchanged.
50. `light-360-hover-primary.png` — Export Image hover gradient in the light sheet; Reset All unchanged.
51. `light-360-hover-theme-tooltip.png` — theme hover only; no native tooltip in headless. Sheet top is light and aligned.
52. `light-360-mobile-menu.png` — dark inverse mobile menu over the light page: File, View (zoom/fit), Edit (undo/redo/compare) groups with shortcut column, ends just above the sheet search field. No clipped row.
53. `light-360-real-clean-icon.png` — no host CSS; light Effects sheet with Blur 0 and unchecked Halftone/CRT cards, black preview. Same geometry as the host-dark cells.
54. `light-360-real-clean-reload-light.png` — empty light state: dashed drop zone, "No image loaded" in the handle, Open file. No dark leak.
55. `light-360-real-clean-T-light.png` — same state after `T`; theme ring visible; all light.
56. `light-360-select-focus.png` — Format PNG focus ring, Size Preset Original, Fit Contain, Lock Ratio. No clipped border at 360.
57. `light-360-size-picker.png` — dark size popover over the light sheet, iPhone rows with the last row cut at the scroll edge; Fit row remains visible. No horizontal overflow.
58. `light-360-zoom-menu.png` — dark zoom dropdown under the percentage, Fit/25–400%. It covers the status row while open by design; no clipped item.

59. `m1-g14-dark-360x680-half.png` (720x1360 @2x) — dark 360x680, sheet at half: one-row top bar, preview above, status `38% · 900×600 · 1867ms` inside the handle, brand/actions/search, one column, no overlap or horizontal scroll.
60. `m1-g14-dark-360x680-peek.png` — same cell at peek: preview taller, 105 px sheet, status still inside the handle. No gap at the bottom, no clipped action bar.

Findings: none in this batch.

## Batch 6 — G14 remaining cells (8)

61. `m1-g14-dark-412x800-half.png` (824x1600 @2x) — empty state, 412x800 dark, sheet at half: one-row top bar, dashed drop zone, "No image loaded" status row, brand, actions, search, Mode. No overlap; the empty-state half snap is the expected one.
62. `m1-g14-dark-640x360-half.png` (1280x720 @2x) — landscape 640x360, dark, image loaded, sheet at half: preview ~267 px, status `22% · 900×600 · 200ms`, brand and Export/Reset partially below the fold but scrollable. No horizontal overflow, preview keeps >120 px.
63. `m1-g14-dark-640x360-peek.png` — the same landscape cell at peek: preview taller (~199 px per the G14 log), 105 px sheet with status and the action bar. No overlap.
64. `m1-g14-light-320x568-half.png` (640x1136 @2x) — light 320x568 at half: preview, status `33% · 900×600 · 130ms`, brand, actions, search. One column, no overflow.
65. `m1-g14-light-320x568-peek.png` — the same cell at peek: taller preview, sheet only 105 px high; the status and the top of the action bar are visible at the bottom edge (the rest is reachable by scrolling the sheet). Intended peek behaviour, no clipping inside a control.
66. `m1-g14-light-390x750-half.png` (780x1500 @2x) — light 390x750 at half: preview, status `41% · 900×600 · 1803ms`, brand, actions, search, Mode. Geometry consistent with 360.
67. `m1-g14-light-390x750-peek.png` — same cell at peek: preview larger, 105 px sheet with status, action bar at the bottom edge. No overlap or overflow.
68. `m1-g14-light-740x360-none.png` (1480x720 @2x) — 740x360 crosses above the 700 px sheet breakpoint, so the desktop branch is shown: two-row top bar (menu row + toolbar row), centred preview, no sheet. `dataset.snap` is empty (filename `-none`). Runs 1 and 2 named this cell `-half` because the attribute was stale, but their pixels are the same layout; this is analysed in closeout item 3.

Findings: none visual. Note: the directory holds 68 PNGs (58 G3 + 10 G14), not 58; all 68 were opened here.

## Pixel-diff equivalence for runs 1 and 2

Automated per-file diff (`docs/evidence/p2-3/pixel_diff.py`, raw JSON in the same folder), tolerance >2/255 on any channel:

- 68/68 filenames match between runs 1 and 2.
- Every 1280x900 pair: the right panel (x >= 980) differs by 0 pixels. The only top-bar difference is the status render-time text (bbox x 935–954, y 19–27 for dark; x 935–947 for light; 91–118 pixels over 2). The preview canvas differs because the "fullest" stack includes random-based effects (grain/random dither/glitch/matrix), which are intentionally non-deterministic; canvas differences are confined to the black preview region.
- 360x740 pairs: the sheet body (y >= 460) is identical; the only differences are the same render-time digits at the bottom edge of the status row (y 430–432, 47–50 pixels) plus the random-effect canvas.
- G14 files: identical except the landscape status digits and the 740 cell's internal snap name (pixels outside the ms text match).
- Worst canvas fraction over2: 0.332 (dark 1280); median file: no chrome difference at all.

Files that differ *outside* the preview canvas and the render-time digits: none. The four host-CSS 1280 files have a larger canvas diff because their effect cards are unchecked but the preview still carries the same random stack; their chrome is 0-diff. No file needed a second inspection beyond the batches above, and the two run-1/run-2 740 cells were opened explicitly.
