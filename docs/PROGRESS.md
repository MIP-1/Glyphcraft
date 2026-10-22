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

## Notes
- Single optional Google Font (UnifrakturCook) with serif fallback
- Vanilla JS, plain script tags, no modules, works on file://
- Engraved manuscript aesthetic: oxblood gradient buttons, diamond slider thumbs, chamfered clip-path
- Tests: `python3 test_suite.py` (headless Chromium); report in TEST_REPORT.md, 109 checks
- No Web Worker: effects run synchronously on the reduced preview
