# P2-3 screenshot review

Final tree: `28b22dc` (P2-3 branch, Step 5 complete). Gate runs are in
`docs/evidence/p2-3-run-1/`, `-run-2/`, `-run-3/`; each contains the 68 PNGs
written by G3 and G14. The interrupted run is kept separately in
`docs/evidence/p2-3-run-2-interrupted/` (58 PNGs, stopped after G12).
All 68 files of the final run were opened in six labelled batches
(12/12/12/12/12/8) at half scale, and the files listed below were opened again
at full size.

## Batch notes (final run, 68 files)

1. Dark 1280: edit/file/view/zoom menus, focus-theme, fullest-effects,
   fullest-top, hover preset/primary/theme-tooltip, select-focus, size-picker.
   Menu popovers are the paper-coloured (light) style in dark theme, which is
   the existing design and matches the P2-2 reference. No clipped labels, no
   overlap between the menu and the panel, status box shows 100% / 900×600 /
   render ms.
2. Dark 360: focus-theme, fullest-effects, fullest-top, hover preset/primary/
   theme-tooltip, mobile-menu, select-focus, size-picker, zoom-menu; plus the
   light 1280 edit and file menus. Single-row top bar, sheet at peek, mobile
   menu is a three-group list with separators, nothing overflows 360 px.
3. Light 1280: file menu, fullest-effects, fullest-top, host-dark icon and
   T-light, host-dark reload-light (empty state, correct: a reload does not
   persist a source), hover preset/primary, hover-theme-tooltip, real-clean
   icon/reload-light, select-focus, size-picker. Light theme is consistent;
   popovers are the dark paper style, matching P2-2.
4. Light 1280 real-clean reload-light, select-focus, size-picker, view menu,
   zoom menu; light 360 focus-theme, fullest-effects, fullest-top, host-dark
   icon/reload-light/os-light. Empty state after reload is intended; the light
   sheet is at peek, no overflow.
5. Light 360 hover preset/primary/theme-tooltip, mobile menu, real-clean
   T-light/icon/reload-light, select-focus, size-picker, zoom-menu; first
   G14 cells (dark 412×800 half, dark 640×360 half/peek). Sheet snaps grow in
   the expected order, status row stays above the sheet content.
6. Remaining G14 cells: light 320×568 peek/half, light 390×750 peek/half,
   light 740×360 half, dark 360×680 peek/half, dark 412×800 half,
   dark 640×360 peek/half. All mobile cells keep the preview above the sheet
   and the sheet content scrolls; 320/360/390/412/640 widths have no
   horizontal overflow.

One inherited landscape limitation was seen and is not a P2-3 regression:
`m1-g14-light-740x360-half.png` shows only the preview. At 740×360 the CSS is
in the narrow/2-row desktop mode while `isMobileSheet()` is `(max-width:
700px)`, so the 300 px sidebar starts at x=740 and is off-screen. The P2-2
capture of the same cell (`m1-g14-light-740x360-none.png`) is pixel-identical
except for the render-time digits (2,531 px, all inside the status box), and
the README already lists mobile landscape (height < 500) as a later step. It is
recorded under HUMAN-CHECK instead of being claimed as covered.

## Pixel-diff equivalence

Tool: `docs/evidence/p2-3/pixel_diff.py`, tolerance >2/255 on any channel.
Raw JSON: `pixel-diff-run1-run2.json`, `pixel-diff-run2-run3.json`, region
classification `pixel-diff-regions.txt`.

- Both comparisons cover all 68 filenames; no file is missing on either side.
- Runs 1 and 2: the only differing pixels are inside the preview canvas or the
  status render-time digits. With those two regions excluded, **every file has
  0 differing pixels** (worst canvas fraction 0.144). The canvas differences
  come from the deliberately random effects in the fullest stack
  (`matrix`, `grain`, `glitch`, `pixelsort`); a crop comparison of the mobile
  sheet showed the only sheet difference is the millisecond value
  (`1047ms` vs `1085ms`, 268 px inside the 260 px status crop).
- Runs 2 and 3: same result except one file,
  `light-1280-host-dark-reload-light.png`, where 2,124 px sit on the Depth and
  Offset slider rows of the panel. Measured thumb centres: runs 1/2
  x=1039.5 and 1071.5, run 3 x=1035.5 and 1064.2. That is exactly the shift a
  15 px narrower range track produces at value 80 (27% of 15 px ≈ 4 px) and
  value 0 (50% of 15 px ≈ 7 px); the number/stepper boxes and every label are
  unchanged. A fresh replay of 60 consecutive 650 ms reloads always produced
  the normal 158 px slider and thumb x=1039.5, so this was a one-capture
  transient layout reflow, not a repeated render difference. It is the only
  non-canvas/non-status difference in the three runs and is listed under
  HUMAN-CHECK.
- Menus, top bar, panel cards, labels, buttons, sheet chrome and focus rings
  are otherwise identical in all 68 pairs.

## Break-it screenshots

- `breakit-360-video-peek/half/full.png`: 360 px layout with a video loaded;
  sheet heights 105 / 333 / 651 px, no horizontal overflow.
- `breakit-light-fullest-reload.png`: light theme after reload with the
  fullest stack set before the reload (theme persists; effect settings are
  session state and intentionally reset).
