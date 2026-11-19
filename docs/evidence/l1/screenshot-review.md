# L1 gate screenshot review — 68 files

Every PNG that the full gate writes into `docs/evidence/l1/` was opened and
described. They were viewed as six labelled contact sheets (12, 12, 12, 12, 12
and 8 tiles) and each file was additionally opened on its own wherever the
thumbnail was not enough to judge (both `*-edit-menu.png` and
`*-file-menu.png` at 1280, `light-1280-view-menu.png`,
`light-360-mobile-menu.png`, `dark-1280-zoom-menu.png`).

The gate rewrites this whole matrix on every run, so the descriptions below are
the matrix as it stood when the review was written; the final set replaces the
files with identical content per the snapshot check below.

At review time the directory was a **mix of two runs**: the `light-*` files
carried 00:09 mtimes from the green set-4 run, the `dark-*` files 01:01 from
the attempt the load guard aborted at 01:00. The pixel-identity claim is
therefore deferred to closeout: `tools/gate_set.py` snapshots every run's
matrix as `shots-run1..3.sha256`, and the three manifests are diffed file by
file. Files that differ are opened and their differing region is reported; the
expected difference is the live render readout, not the UI.

## How to read the matrix

- `dark-*` / `light-*` are the page theme, not the host theme.
- The menus, the zoom popup, the size picker and the mobile menu are painted in
  the **inverse** of the page surface. That is a token decision, written in
  `style.css` next to the variables: "Menus are the inverse of the page: dark
  page -> light menu." So a cream popup over the dark page and a near-black
  popup over the light page are correct, not a theme leak. The describer below
  notes it once instead of repeating it 30 times.
- Native OS tooltips are not painted in headless Chromium, which is why
  `grep`ping the capture code shows the tooltip itself is a HUMAN-CHECK.
  `dark-1280-hover-theme-tooltip.png` does show a tooltip because Firefox, the
  other capture browser, paints its own; at 360 px no tooltip is expected.
- `m1-g14-*` are the G14 layout cases inherited from P2-3 (short landscape,
  tall phone, half-sheet and peek states), not new L1 features.

## Dark, 1280 x 900 (12)

| File | What it shows |
|---|---|
| `dark-1280-edit-menu.png` | EDIT tab active, cream menu with Undo / Redo / Compare; canvas of glyphs behind it, no clipped text. |
| `dark-1280-file-menu.png` | FILE tab active, cream menu with Open file… / Export Image… / Reset All; menu sits 2 px under the bar, aligned to the tab. |
| `dark-1280-focus-theme.png` | Theme button has the focus ring; ring is visible against the dark bar and not clipped by the header. |
| `dark-1280-fullest-effects.png` | Panel scrolled to the effects list with every effect card open (threshold, halftone, posterize, duotone, CRT, scanlines…); switches read as on, red accent on primary actions. |
| `dark-1280-fullest-top.png` | Panel scrolled to the top: theme, title, Export/Reset, preset search, mode; canvas visible at the chosen fit. |
| `dark-1280-hover-preset.png` | Preset button in its hover state, one step lighter than the idle surface. |
| `dark-1280-hover-primary.png` | Export Image in its hover state; red gradient stays dark enough for white text. |
| `dark-1280-hover-theme-tooltip.png` | Theme button hovered; Firefox paints the native "Switch to light theme" tooltip below it, fully on screen. |
| `dark-1280-select-focus.png` | A select has the keyboard focus ring; the native arrow is legible on the dark input. |
| `dark-1280-size-picker.png` | Size picker open with every group expanded (Original, 1x/2x/3x, 16:9 to 9:16, web sizes); inverse cream surface, scrollable, no cut-off rows. |
| `dark-1280-view-menu.png` | VIEW tab active, cream menu with Zoom in / Zoom out / Fit window / Fit page / Fit small / 100 % / 200 % / Toggle controls panel and their shortcuts. |
| `dark-1280-zoom-menu.png` | Zoom-level popup at the top right, same items plus the checked current zoom; anchored to the button, not the viewport. |

## Dark, 360 x 740 (10)

| File | What it shows |
|---|---|
| `dark-360-focus-theme.png` | Phone layout, theme button focused; focus ring inside the 44 px target. |
| `dark-360-fullest-effects.png` | Phone sheet scrolled to the effects cards; all cards stack without horizontal scroll. |
| `dark-360-fullest-top.png` | Phone sheet at the top: Export/Reset full width, search field, mode row. |
| `dark-360-hover-preset.png` | Preset button hovered at phone width; row wraps to two lines with no clipping. |
| `dark-360-hover-primary.png` | Export Image hovered at phone width. |
| `dark-360-hover-theme-tooltip.png` | Theme button hovered; the hover state is captured and no native tooltip is painted (headless), which the gate records as HUMAN-CHECK. |
| `dark-360-mobile-menu.png` | Hamburger menu open: Open file, Export image, Reset all, Zoom in/out, Fit window/page/small, 50–300 %, Toggle controls panel, Undo, Redo, Compare; inverse cream sheet over the whole width. |
| `dark-360-select-focus.png` | Select focused at phone width; the 44 px row height is kept. |
| `dark-360-size-picker.png` | Size picker open at phone width; inverse surface, every group reachable by scroll, no row under the action bar. |
| `dark-360-zoom-menu.png` | Zoom popup at phone width; opens over the canvas and stays inside the viewport. |

## Light, 1280 x 900 (19)

| File | What it shows |
|---|---|
| `light-1280-edit-menu.png` | EDIT active; near-black inverse menu with Undo / Redo / Compare; separators visible on the light page. |
| `light-1280-file-menu.png` | FILE active; near-black inverse menu with Open file… / Export Image… / Reset All. |
| `light-1280-focus-theme.png` | Light page, theme button focused; ring dark enough on cream, nothing clipped. |
| `light-1280-fullest-effects.png` | Light effects column fully open; every switch, number field and card border reads on cream. |
| `light-1280-fullest-top.png` | Light panel top: Export/Reset, search, mode, header. |
| `light-1280-host-dark-icon.png` | Host dark, page light, icon-style export: warm-toned source, light UI, no dark flash in the chrome. |
| `light-1280-host-dark-reload-light.png` | Empty editor after reload under a dark host: still light, the drop zone and Browse button are the only content. |
| `light-1280-host-dark-T-light.png` | Host dark, page light, T-light case: the same warm source renders on the light page and the preview keeps its sharp backing. |
| `light-1280-host-os-light-os-light.png` | Host light, page light: chrome and canvas agree; the source is the same warm image. |
| `light-1280-hover-preset.png` | Preset button hover on cream; one step darker, text unchanged. |
| `light-1280-hover-primary.png` | Export Image hover on cream; the red gradient and white label keep their contrast. |
| `light-1280-hover-theme-tooltip.png` | Theme button hovered; Firefox paints "Switch to dark theme" under the button, entirely on screen. |
| `light-1280-real-clean-icon.png` | Clean-load icon case: light UI, warm source, no leftover dark surface from the pre-paint state. |
| `light-1280-real-clean-reload-light.png` | Clean load then reload, light theme: empty editor, no dark flash, drop zone centred. |
| `light-1280-real-clean-T-light.png` | Clean-load T-light case: light UI and warm source, preview fills the fitted area. |
| `light-1280-select-focus.png` | Select focused on cream; the ring has 3:1 against the input. |
| `light-1280-size-picker.png` | Size picker open, near-black inverse surface, all groups expanded, bottom rows above the action bar. |
| `light-1280-view-menu.png` | VIEW active; near-black inverse menu, Zoom in/out, all three fits, 100 %, 200 %, Toggle controls panel, shortcuts right-aligned. |
| `light-1280-zoom-menu.png` | Zoom popup on cream; inverse surface, current zoom checked in the accent colour. |

## Light, 360 x 740 (17)

| File | What it shows |
|---|---|
| `light-360-focus-theme.png` | Phone, theme button focused; ring inside the 44 px target. |
| `light-360-fullest-effects.png` | Phone sheet, effects cards stacked, no horizontal scroll, switches legible on cream. |
| `light-360-fullest-top.png` | Phone sheet at the top: wide Export/Reset, search, mode. |
| `light-360-host-dark-icon.png` | Host dark, page light at phone width, icon case: warm source, light chrome, no dark band. |
| `light-360-host-dark-reload-light.png` | Reload under a dark host at phone width: empty light editor, single centred drop zone. |
| `light-360-host-dark-T-light.png` | Host dark, phone, T-light: warm source on the light page, preview fitted. |
| `light-360-host-os-light-os-light.png` | Host light, phone, light page: consistent chrome and canvas. |
| `light-360-hover-preset.png` | Preset hover at phone width; two-line wrap, no clipping. |
| `light-360-hover-primary.png` | Export hover at phone width. |
| `light-360-hover-theme-tooltip.png` | Theme hover at phone width; hover captured, native tooltip not painted (headless), HUMAN-CHECK. |
| `light-360-mobile-menu.png` | Hamburger menu on cream: near-black inverse panel with the full command list, every row at least 44 px. |
| `light-360-real-clean-icon.png` | Clean-load icon case at phone width: light chrome, warm source. |
| `light-360-real-clean-reload-light.png` | Clean load then reload at phone width: empty light editor, no flash. |
| `light-360-real-clean-T-light.png` | Clean-load T-light at phone width: light UI, warm source, fitted preview. |
| `light-360-select-focus.png` | Select focused at phone width; ring visible, 44 px row kept. |
| `light-360-size-picker.png` | Size picker open at phone width; inverse surface, every group scrollable, no row under the action bar. |
| `light-360-zoom-menu.png` | Zoom popup at phone width; stays inside the viewport, current value checked. |

## G14 layout cases (10)

| File | What it shows |
|---|---|
| `m1-g14-dark-360x680-half.png` | Dark 360 x 680, sheet at half height: canvas on top, sheet from the middle down, Export/Reset full width. |
| `m1-g14-dark-360x680-peek.png` | Same viewport in peek: sheet collapses to a strip, the canvas is fully visible, handle and title still reachable. |
| `m1-g14-dark-412x800-half.png` | Dark 412 x 800, half sheet: empty editor behind, sheet content starts with the drop zone, nothing overlaps the top bar. |
| `m1-g14-dark-640x360-half.png` | Dark short landscape 640 x 360, half sheet: top bar compresses to icons, magenta/green source renders at 22 %, status 900x600 104 ms. |
| `m1-g14-dark-640x360-peek.png` | Same in peek: canvas takes the height back, 31 % zoom, sheet reduced to one row. |
| `m1-g14-light-320x568-half.png` | Light 320 x 568, half sheet: warm source above, sheet below, 33 % zoom, 900x600 97 ms. |
| `m1-g14-light-320x568-peek.png` | Same in peek: the whole canvas is visible and the sheet is a single bottom strip. |
| `m1-g14-light-390x750-half.png` | Light 390 x 750, half sheet: 15 % zoom, 900x600 106 ms, sheet starts below the status line. |
| `m1-g14-light-390x750-peek.png` | Same in peek: full preview, sheet as a strip, no clipped buttons. |
| `m1-g14-light-740x360-half.png` | Light 740 x 360 landscape: the desktop FILE/VIEW/EDIT bar appears at this width, canvas at 42 %, sheet shows the effect column, no overlap. |

## What was checked while looking

- No clipped text, no control under another control, no scrollbar inside a
  popup at either width.
- Both themes keep text/background pairs from the same token set; the inverse
  menu is the only intentional inversion.
- Every status readout (`900x600`, zoom, render ms) is inside its box at 320,
  360, 390, 412, 640, 740 and 1280 px.
- The 44 px touch targets hold in the 360 px menus and the size picker.
- No L1-specific visual regression: the preview in `fullest-*` and `T-light`
  files is the sharp-backing render (the same pixels the G23 sharpness cells
  measure), and nothing in the panel moved because layout and golden hashes
  still use `previewSize()`.

## Limits

- This is a human reading of 68 PNGs, not a pixel oracle; the machine oracle is
  G3/G8 (geometry) plus the G19/G20/G21/G22 screenshot hashes.
- The status digits are live, so two runs are never byte-identical; the diff at
  closeout is reported per file with the differing region.
- Native tooltips on the owner's real desktop, and the felt sharpness of the
  HiDPI preview, stay HUMAN-CHECK.
