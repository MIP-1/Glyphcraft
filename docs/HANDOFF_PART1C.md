# Glyphcraft — Part 1C human checks

Everything below can only be confirmed by you, in your own browser/hardware. The
gate runs in headless Chromium on this machine, so it cannot see your GPU,
your compositor, your audio device, or your OS memory accounting. Each item has
exact steps and the result I expect; if you see something different, say which
number you saw.

Part 1C status: C1 audit PASS, C2 play/pause control PASS, C3 multi-effect cost
PASS (one commit, tags `C1-audit-pass`, `C2-video-control-pass`,
`C3-perf-pass`).

## 1. The pause button actually pauses (C2)

1. Open the app (`npm run serve` or your usual local server), hard reload with
   `Ctrl+Shift+R`.
2. Load a real `.webm` or `.mp4` (not the gate's test clip). It autoplays.
3. Click the button in the bottom-left corner of the preview.
4. **Expected:** the video stops on its current frame, the icon becomes ▶, and
   the tooltip/accessible name is `Play video`. Click again: it resumes and the
   icon becomes ⏸ with the name `Pause video`.
5. Pause it, then click on empty canvas next to the video and drag: the video
   must stay paused and the click must not be swallowed by the drag.

## 2. Keyboard and screen-reader path (C2)

1. Press `Tab` until the corner button has a visible focus ring.
2. Press `Space` twice.
3. **Expected:** play, then pause. The canvas must not start panning and the
   cursor must not change to a grab hand. With a screen reader, the button reads
   `Play video` / `Pause video` and never a stale label.

## 3. Playback smoothness with the six-effect stack (C3)

1. Load a 720p or 1080p video and enable exactly: Posterize, Edge Detect,
   Pencil Sketch, Emboss, Blur, Sharpen.
2. Let it play for 5 s and watch the status readout (`ms`) and the motion.
3. **Expected:** the readout sits around 20-35 ms, the motion is continuous, and
   the browser does **not** show its "this tab is using significant resources"
   or "slow page" warning. The preview is softer than paused **by design** — the
   internal render size drops to 218 px wide on this machine and comes back to
   full resolution the moment you pause.
4. Pause: the frame must become sharp again within one frame, and the status
   readout should return to the full-resolution value (tens of ms).
5. If your machine is faster than mine, the governor will settle at a higher
   scale (sharper); if it is slower, it goes no lower than 0.17. Tell me the
   scale you see (`state.playback.scale` in the console) and the ms readout.

## 4. The preview must not shrink while playing (C2/C3)

1. Any video, any stack. Note the width of the preview box.
2. Press play, wait 3 s, compare the box again.
3. **Expected:** the box keeps exactly the same size and position; only the
   sharpness changes. A shrinking or jumping preview is the bug this part
   fixed (headless: 76 % shrink before, 0.5 % after).

## 5. Tab switch while playing (C3)

1. Load a video, press play.
2. Switch to another tab for 10 s, then come back.
3. **Expected:** while hidden, the tab uses ~0 % CPU; on return, playback and
   the preview continue at the same position, with no black frame and no
   doubled speed.

## 6. Export while paused (C2)

1. Load a short video, pause it, then Export as WebM.
2. **Expected:** the exported file starts from the paused frame, the app is still
   paused afterwards, and the button still says `Play video`.

## 7. Real hardware / other browsers (C1)

1. Repeat items 1 and 3 in Brave and, if you have one, on a phone or a
   touchscreen laptop.
2. **Expected:** same behaviour. Playwright here runs Chromium with the software
   rasteriser; your GPU path and real touch input are unverified by the gate.

## 8. Both themes and both widths, by hand (C1)

1. `Ctrl+Shift+R`, then `T` to switch theme.
2. At 1280 px and at 360 px wide, with a video loaded: check the corner button
   (icon, hover, focus ring, contrast), the status row and the sticky
   Export/Reset bar.
3. **Expected:** nothing clipped, the button never overlaps the status row, both
   themes consistent.
4. Repeat at 200 % browser zoom.

Report format: item number, what you did, what you saw, and the number if the
step asks for one.
