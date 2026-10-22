# Glyphcraft

Glyphcraft turns images and videos into glyph art in the browser. Drop in a
photo or a clip, tune the ramp, dithering, palette and effects, then export a
still (PNG / JPG / WebP / SVG / TXT) or a WebM clip.

Everything runs locally. There is no build step, no npm install and no server
side: plain HTML, CSS and four classic scripts loaded in order
(`engine.js` → `effects.js` → `reorder.js` → `app.js`).

## Run it

```bash
cd glyphcraft
python -m http.server 8000
# open http://localhost:8000
```

Opening `index.html` directly over `file://` also works in Chromium-based
browsers. A local server is recommended because some browsers restrict
clipboard and font loading on `file://`.

## Modes

| Mode | What it does |
| --- | --- |
| **Script** | Maps brightness to characters from a ramp (18 categories/sets, charset presets from ASCII to Braille, cell size, weight, color/mono). |
| **Dither** | Error-diffusion and ordered dithering (Floyd–Steinberg, Atkinson, Sierra, Stucki, Burkes, JJN, Bayer 2/4/8, halftone, blue noise, random) with serpentine scanning and 2–16 levels. |
| **Effects Only** | Skips the glyph pass and applies the image effects directly to the source. |

Twenty-two stackable effects (CRT, glitch, halftone, VHS, bloom, …) are
available in every mode, plus adjustments (brightness, contrast, saturation,
hue, highlights, shadows, sharpen, blur, invert, sepia). Drag a box by its
six-dot handle (or focus the handle and press `Alt+Up` / `Alt+Down`) to change
the render order.

## Home screen

Drop a file, paste it (`Ctrl+V`) or press **Open file**. Images (PNG, JPG,
WebP, GIF, BMP, AVIF, SVG) and videos (WebM, MP4, …) up to **40 MB** are
accepted. If a file cannot be read, the drop area says why and what to try.
When the browser language starts with `ar`, the home screen switches to Arabic
and the layout becomes right-to-left.

## Keyboard

| Key | Action |
| --- | --- |
| `Ctrl+O` | Open a file |
| `E` | Export |
| `R` | Reset all (press twice) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `C` | Compare split |
| `O` (hold) | Show the original |
| `+` / `−` | Zoom in / out |
| `0` / `F` | Fit window |
| `Space` + drag | Pan |
| `\` | Toggle the controls panel |
| `T` | Toggle theme |
| `Alt+Up` / `Alt+Down` | Move the focused effect up / down |
| `Esc` | Close menu / compare / full page |
| `?` | Shortcut list |

## Themes

Dark and light themes share one semantic token set in `style.css`. The choice
is stored in `localStorage` (`glyphcraft-theme`) and applied before first paint.
The automated contrast audit checks text, placeholders, form fields and control
borders in both themes at 360 px and 1280 px.

## Tests

```bash
python tests/test_suite.py     # 167 checks, headless Chromium via Playwright
python tests/test_contrast.py  # WCAG contrast audit, both themes, 2 widths
```

Reports and screenshots land in `tests/reports/` (gitignored). Tests use
`/tmp/glyphcraft_test.png` and generate a short WebM fixture with `ffmpeg`.
They do not modify the source tree.

## Deploying

The project is a static site. Pushing the folder to GitHub Pages (or any static
host) works as-is; `.nojekyll` is not required because there are no
underscore-prefixed paths. The only network request is the optional Google
Fonts stylesheet — the page falls back to Georgia/serif if it is blocked.

## Browser support

Recent Chromium, Firefox and Safari. The test suite runs headless Chromium.
