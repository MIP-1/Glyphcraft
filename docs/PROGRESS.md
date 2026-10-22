# Glyphcraft Progress

## Phase 1 - DONE
- Layout: menubar, left toolbar, canvas, right panel (290px, collapsible)
- Theme toggle (dark/light) with localStorage persistence, prefers-color-scheme initial
- File open: drag-drop, paste, file picker (images)
- Script engine: Depth, Category, Set, Inject, Offset, Text Style, Use Palette, Transparent BG, BG Color
- Color: Mode (Spectrum/Palette/Mono), built-in palettes (8), auto-extract via k-means
- Adjustments sliders: Brightness, Contrast, Saturation, Hue, Highlights, Shadows, Sharpen, Blur, Invert
- Output: Size presets (14), Custom WxH (max 4096), Fit (Contain/Cover/Stretch)
- PNG export
- Pan (Space + drag) / wheel zoom / Fit (F) / status bar (zoom%, size, fps)

## Phase 2 - DONE
- All image formats (jpg, webp, gif, bmp, avif, svg) via browser native support
- SVG/TXT/JPG/WebP export
- Export format dropdown (PNG, JPG, WebP, SVG, TXT, WebM)
- Pan/zoom refinements

## Phase 3 - DONE
- Video input (mp4, webm, mov, m4v, ogv) with codec error handling
- Video playback loop with frame-accurate seeking
- WebM export via MediaRecorder (VP9 when supported)
- Export progress in status bar

## Phase 4 - DONE
- Dither engine: Floyd-Steinberg, Atkinson, Bayer 4×4, Bayer 8×8, Halftone Dot Grid, Threshold
- Color Depth slider (2-16 levels)
- Dither kernel dropdown
- Same Adjustments panel works for both Script and Dither modes
- Palette swatches for mono/palette color modes

## Phase 5 - DONE (2026-10-21)
- Empty state: centered drop zone (click to open), whole-window drag-drop, Ctrl+V paste
- Removed duplicate Pan/Fit toolbars and the unlabeled red button; pan = Space/middle-drag, F = fit
- Right panel: collapsible sections, control search, per-section reset, panel collapse
- Undo/redo (Ctrl+Z / Ctrl+Shift+Z) with slider coalescing
- Named presets (7) + save/load custom presets (localStorage)
- Split compare slider + hold-to-show-original (O key or View menu item)
- Effects pipeline (22 effects) with enable toggles, params, drag reorder; runs before Script/Dither and standalone in "Effects Only" mode
- Auto-levels before glyph mapping, tighter cell metrics, scaled glyph font
- Preview capped at 1100px; exports render at full output resolution
- Light theme rebuilt as parchment with dark ink (AA contrast audited)
- SVG/TXT export now derives from the prepared source (not the rendered glyph canvas), so effects are included

## Phase 1 (Overhaul) - DONE (2026-10-22)
- Sticky action bar: Export Image / Reset All stay visible at top of panel while scrolling
- Export shows progress for video, success toast on completion
- Reset All requires confirmation (inline confirm with 3s timeout) or undo toast

## Phase 2 (Overhaul) - DONE (2026-10-22)
- Unified spacing scale (4/8/12/16/24/32) as CSS variables
- Consistent control heights (36px), label sizes, gaps, padding across all sections
- Collapsible sections (Mode, Script, Dither, Color, Adjustments, Effects, Output) with localStorage persistence
- Unified form control styles: selects, sliders, toggles, buttons with same radius, border, hover, focus-visible ring, disabled state
- Tab order top→bottom, left→right; everything keyboard-reachable; Esc closes menus
- Effect stack: reorder (drag handle), per-effect enable toggle, remove, reset-to-default, empty state message
- Tested widths 360, 768, 1280, 1920 — no horizontal scroll, no clipped text, no misaligned columns
- Dark/light themes working; colors as tokens on :root
- Logical CSS properties (margin-inline, padding-inline) for RTL support

## Phase 3 (Overhaul) - DONE (2026-10-22)
- Every slider gets a number input next to it — two-way live sync
- Each effect keeps its own min, max, step, default in effects.js config
- Clamp on input, blur, paste; NaN → revert to last valid
- Arrow keys step; Shift+arrow = 10× step; Double-click slider = default
- Units shown (px, %, deg) where applicable

## Phase 4 (Overhaul) - DONE (2026-10-22)
- Replaced dimension buttons with searchable grouped dropdown (Custom as last item)
- Groups: Video, Desktop wallpaper, Phone wallpaper, Instagram, YouTube, Link preview, Avatar, Logo/icon, Print, Original
- Custom reveals width + height inputs; preset fills width/height, switches to Custom if edited
- Aspect-ratio lock checkbox
- Max 8192 per side with warning on heavy sizes
- Presets kept as data in engine.js

## Phase 5 (Overhaul) - DONE (2026-10-22)
- Goodmountain font (from /home/mustafa/Goodmountain-main) copied to ./assets/fonts/
- @font-face in style.css with relative URL, font-display: swap, readable fallback stack
- Used for brand, headings, buttons; clearer font for dense controls/numbers
- Arabic glyph coverage checked; fallback handles Arabic
- Google Fonts CDN kept as-is (UnifrakturCook, Crimson Text, JetBrains Mono)

## Phase 6 (Overhaul) - DONE (2026-10-22)
- Dither kernels added: Sierra, Stucki, Burkes, Jarvis-Judice-Ninke, Bayer 2×2, Blue Noise, Random
- Serpentine (boustrophedon) toggle for error diffusion
- Palette system enhanced: 1-bit, 2-color editable, Game Boy 4-green, CGA, N-level grayscale (4/8/16), custom palette builder with add/remove/save
- Effects: 22 existing effects verified; params have min/max/step/default, tooltips, live preview, work on video
- Script mode: charset presets (ASCII, blocks, braille, binary, minimal, dense), cell size, weight, invert, color/mono, background
- Presets: save/load/delete named effect stacks in localStorage (try/catch), JSON export/import

## Phase 7 (Overhaul) - DONE (2026-10-22)
- Drop zone states (idle/hover/error/loading), paste from clipboard, clear error for bad files
- Before/after compare (hold key) — already implemented (O key)
- Zoom and pan — already implemented (wheel zoom, Space+pan, F fit)
- Debounce heavy effects, render in requestAnimationFrame, show render time
- Large input: downscale for preview (max 1600px / 2.5MP), full quality only on export
- Undo/redo for all parameter changes — already implemented
- Shortcuts (E export, R reset with confirm, Z undo, Shift+Z redo, C compare, O hold original, F fit, Space pan, ? help) with ? popover
- Export: PNG, JPEG (quality slider), WebP, plus existing formats (SVG, TXT, WebM)
- Accessibility: labels, aria-live status, contrast ≥ 4.5:1, prefers-reduced-motion, focus-visible rings
- Remove dead code, zero console errors/warnings on load

## Notes
- Single optional Google Font (UnifrakturCook) with serif fallback
- Vanilla JS, plain script tags, no modules, works on file://
- Engraved manuscript aesthetic: oxblood gradient buttons, diamond slider thumbs, chamfered clip-path
- Tests: `python3 test_suite.py` (headless Chromium); report in TEST_REPORT.md, 114 checks (all pass)
- No Web Worker: effects run synchronously on the reduced preview
## Round 2 (2026-10-22) - DONE
- **Light theme rebuilt** with a semantic token system (`--surface*`, `--text*`, `--border-*`, `--accent*`); every colour in `style.css` now comes from a token (including select arrows, checkbox SVGs, shadows and hover gradients). Legacy aliases (`--bg`, `--panel`, `--line`, …) kept for inline styles.
- **Contrast**: 44×44 custom tokenised checkboxes, 44px controls, ≥3:1 control borders. New automated audit `tests/test_contrast.py` checks every visible text node, field, placeholder and control border in both themes at 360 and 1280 → **5960 pairs, 0 violations**.
- **Sticky action bar**: solid `--surface-panel`, full panel width including padding/gap, `z-index: 40`, divider, content scrolls underneath (verified by hit-testing the gap).
- **Unified controls**: duplicate value labels removed (`<input type=number>` is the only value display); one style per theme; no UA-white fields in dark or UA-dark fields in light; section headers are real buttons with `aria-expanded`.
- **Menus**: File (Open/Export/Reset), View (zoom, fit, full page, fit small, 100/200%, panel, theme), Edit (undo/redo/compare). Click/tap open, Esc + outside click close, ArrowUp/Down/Home/End navigation, `<kbd>` shortcuts, `aria-haspopup/expanded`. Preset save/load moved to the Effects section.
- **Zoom toolbar**: − / percent / + in the top bar, menu with Fit window, Full page, Fit small, 25–400%; live percent, clamp 10–800%, disabled limits, Ctrl+wheel and wheel zoom at the pointer, pinch, drag-pan when the image is larger than the view, `+ − 0` keys, pixelated above 100%, Full page + Esc restore.
- **Theme toggle**: single top-bar button, inline sun/moon SVGs, pre-paint theme script, localStorage persistence, action-specific aria-label.
- **Home screen**: real `Open file` button, drag/drop/paste, honest idle/hover/loading/error copy, 40 MB limit, format/decode/video errors, `aria-live` status, Arabic (`ar`) strings + RTL layout.
- **Cleanup**: test reports moved to `tests/reports/` (gitignored), no `.bak` files added, README added.

## Testing
- `python tests/test_suite.py` → 131 checks, 0 failures.
- `python tests/test_contrast.py` → 5960 pairs, 0 violations; screenshots in `tests/reports/`.
