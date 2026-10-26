# Glyphcraft — Part 1B (H0–H4) human checks

Everything below can only be confirmed by you, in your own browser/hardware. The
gate runs in headless Chromium on this machine, so it cannot see your GPU,
your compositor, your touch screen, or your OS memory accounting. Each item has
exact steps and the result I expect; if you see something different, say which
number you saw.

Part 1B status: H0 PASS, H1 PASS, H2 PASS, H3 PASS, H4 PASS (tag `H4-pass`).

## 1. Load: paused video must be idle (H4)

1. Open the app (`npm run serve` or your usual local server), hard reload with
   `Ctrl+Shift+R`.
2. Load a real `.webm` or `.mp4` (not the gate's test clip): drop it on the
   canvas or use Open.
3. Let it play for 2 s. The app has no pause button today (the video autoplays
   and loops); pause it from the devtools console (`F12`, Console), where
   `state` is reachable by name:
   `state.video.pause()`.
4. Close the devtools console, then open the browser's own task manager
   (Chrome: `Shift+Esc`; Firefox: `about:performance`) and watch the tab for
   10 s.
5. **Expected:** CPU for the tab falls to roughly 0% (headless measured 0 rAF
   and 1.4 ms of task time per 5 s). It must not sit at 20-60% like before.
   Note: with devtools open, Chrome adds its own overhead; step 4 deliberately
   measures with the console closed.

## 2. Load: hidden tab must stop rendering (H4)

1. Load a video and leave it **playing**.
2. Switch to another tab or another window for 10 s.
3. **Expected:** the Glyphcraft tab's CPU goes to ~0% (headless measured 0 rAF
   and 5 ms of task time over 3 s hidden).
4. Switch back: the video must resume playing and the preview must update
   again, with no frozen black canvas and no doubled speed.

## 3. Load: a slider drag on a 4K image (H4)

1. Load a 4000×3000 image (or the largest photo you have).
2. Enable six heavy effects: Posterize, Edge Detect, Pencil Sketch, Emboss,
   Blur, Sharpen.
3. Drag the Script **depth** slider slowly left and right for 3 s.
4. **Expected:** the preview keeps up with the pointer (measured 57-90 ms per
   render, i.e. 11-17 fps at 4K, 151 updates in 3 s). It must not freeze for a
   second and then jump once.
5. Note: this is *more* total CPU than before by design — the preview now
   updates continuously instead of once on release. Per update it is 10-12x
   cheaper (721.9/909.4 ms -> 57.35/89.97 ms).

## 4. Load: memory over a long session (H4)

1. Load the 4K image with the six effects from item 3.
2. Move 5-10 different sliders around for a minute (about 100 changes).
3. Watch the tab's memory in the browser task manager before and after.
4. **Expected:** a small rise only (headless measured +4.05% heap after forced
   GC, canvas count constant at 1). It must not grow without bound, and must
   not keep climbing if you keep dragging.

## 5. Compare: real touch / pen hardware (H3)

1. On a touch device or a pen display, enable Compare (`C` or Edit -> Compare).
2. Touch and drag the split line 10 times, starting each drag exactly on the
   line, and 10 times 1-2 cm away from it.
3. **Expected:** the line follows your finger/pen every time; the image does
   not pan instead. Headless measured 50/50 grabs at 100/200/400% zoom with a
   28x44 px hit area; real hardware is unverified.

## 6. Frame pacing on your machine (H4)

1. With the six-effect 4K stack, drag the depth slider and watch for stutter
   that is not explained by render time.
2. **Expected:** no periodic multi-hundred-ms freeze. The gate's G4 reported a
   16.7 ms median in every cell, but its p95 varied 800-1483 ms on this
   headless machine (also before H4). If you see the same spikes on real
   hardware, report the machine and the stack; it is a known open item.

## 7. Both themes and both widths, by hand (H0-H4)

1. `Ctrl+Shift+R`, then `T` to switch theme.
2. At 1280 px and at 360 px wide, check: top bar (status box segments, theme
   and panel buttons), stepper arrows, compare split, and the sticky
   Export/Reset bar.
3. **Expected:** nothing clipped, nothing overlapping, both themes consistent.
4. Repeat at 200% browser zoom.

## 8. Native widgets (headless cannot see them)

1. Open a native `<select>` popup (e.g. an output preset) and hover a control
   with a native `title` tooltip.
2. **Expected:** the popup opens at normal speed and the tooltip text is
   correct and readable in both themes.

Report format: item number, what you did, what you saw, and the number if the
step asks for one.
