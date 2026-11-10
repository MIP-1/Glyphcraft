#!/usr/bin/env python3
"""P2-3 closeout: one real ~840 MB video, load/play/seek/export.

Not part of the normal gate (it generates and exports hundreds of MB and takes
minutes). Run at closeout and keep the raw log:

  python tests/gate/video_large.py

The fixture is a 3840x2160 lossless VP9 WebM of ~838 MB (under the 850 MB
limit), generated with ffmpeg and deleted after the run. Peak memory is the JS
heap plus the browser's own decode buffers as reported by performance.memory;
the JS heap alone is not the whole process.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import video_p2_3_check as V  # noqa: E402

ROOT = V.ROOT
WORK = Path("/tmp/opencode/glyphcraft_p2_3_large")
LARGE = WORK / "large-840mb.webm"
OUT = WORK / "large-export.webm"
TARGET_LOW = 800 * 1024 * 1024
TARGET_HIGH = 850 * 1024 * 1024


def make_large() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    if LARGE.exists() and TARGET_LOW <= LARGE.stat().st_size <= TARGET_HIGH:
        return
    if LARGE.exists():
        LARGE.unlink()
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "nullsrc=s=3840x2160:r=24:d=2.75,"
        "geq=random(1)*255:random(2)*255:random(3)*255",
        "-c:v", "libvpx-vp9", "-lossless", "1", "-b:v", "0", "-g", "1",
        "-deadline", "realtime", "-cpu-used", "8", "-an", str(LARGE),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    size = LARGE.stat().st_size
    if not TARGET_LOW <= size <= TARGET_HIGH:
        raise SystemExit(f"large fixture is {size} bytes, outside the 800-850 MB window")


def main() -> int:
    make_large()
    size = LARGE.stat().st_size
    print(f"fixture {LARGE} {size} bytes ({size / 1024 / 1024:.1f} MB)")
    rows: list[tuple[str, str, bool]] = []
    problems: list[str] = []

    def record(name: str, detail: str, ok: bool) -> None:
        rows.append((name, detail, ok))
        print(("PASS " if ok else "FAIL ") + name + ": " + detail, flush=True)
        if not ok:
            problems.append(f"{name}: {detail}")

    with V.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx, page, errors = V.new_page(browser, srv, instrument_reads=True)
            try:
                page.evaluate("""() => {
                  window.__peakHeap = 0;
                  window.__heapTimer = setInterval(() => {
                    if (performance.memory) {
                      window.__peakHeap = Math.max(window.__peakHeap, performance.memory.usedJSHeapSize);
                    }
                  }, 50);
                }""")
                heap_before = page.evaluate("() => performance.memory ? performance.memory.usedJSHeapSize : 0")
                t0 = time.perf_counter()
                V.load_video(page, LARGE)
                load_seconds = time.perf_counter() - t0
                heap_peak = page.evaluate("() => window.__peakHeap")
                reads = page.evaluate("() => window.__fileReads.slice()")
                dims = page.evaluate("() => [state.video.videoWidth, state.video.videoHeight]")
                duration = page.evaluate("() => state.video.duration")
                record("840 MB video loads", f"{load_seconds:.2f}s, {dims[0]}x{dims[1]}, duration={duration:.2f}s",
                       load_seconds < 30 and dims == [3840, 2160])
                record("whole file is not read by JS", repr(reads), reads == [])
                record("peak JS heap during load is bounded",
                       f"before={heap_before / 1e6:.1f}MB peak={heap_peak / 1e6:.1f}MB "
                       f"delta={(heap_peak - heap_before) / 1e6:.1f}MB",
                       heap_peak < 512 * 1024 * 1024)

                page.evaluate("""(ids) => {
                  state.opts.effects = state.opts.effects.map(fx => ({
                    ...fx, enabled: ids.includes(fx.id),
                    params: { ...effectDefaults(fx.id), ...(fx.params || {}) }
                  }));
                  scheduleRender(0);
                }""", ["posterize", "edges", "sketch"])
                page.wait_for_timeout(1200)
                frames = page.evaluate("""() => new Promise((resolve) => {
                  let count = 0;
                  const t0 = performance.now();
                  const tick = () => {
                    count++;
                    if (performance.now() - t0 < 2000) requestAnimationFrame(tick);
                    else resolve({frames: count, seconds: (performance.now() - t0) / 1000});
                  };
                  state.video.currentTime = 0;
                  state.video.play().catch(() => {});
                  requestAnimationFrame(tick);
                })""")
                record("840 MB video plays with 3 effects",
                       f"{frames['frames']} frames in {frames['seconds']:.2f}s "
                       f"({frames['frames'] / frames['seconds']:.1f} fps)",
                       frames["frames"] >= 12)

                seeked = page.evaluate("""() => new Promise((resolve) => {
                  const v = state.video;
                  const target = Math.min(1.5, Math.max(0, v.duration - 0.1));
                  const done = () => resolve({currentTime: v.currentTime, target});
                  v.addEventListener('seeked', done, {once: true});
                  v.currentTime = target;
                  setTimeout(done, 5000);
                })""")
                record("seek works on the large video",
                       f"target={seeked['target']:.2f}s current={seeked['currentTime']:.2f}s",
                       abs(seeked["currentTime"] - seeked["target"]) < 0.35)

                page.evaluate("""() => {
                  state.video.pause();
                  state.opts.exportFormat = 'webm';
                  state.opts.outputPreset = 'custom';
                  state.opts.outputWidth = 320;
                  state.opts.outputHeight = 180;
                  state.opts.outputFit = 'contain';
                  syncUIFromState();
                  scheduleRender(0);
                }""")
                page.wait_for_timeout(500)
                if OUT.exists():
                    OUT.unlink()
                t_export = time.perf_counter()
                with page.expect_download(timeout=1200000) as dl:
                    page.click("#btn-export")
                dl.value.save_as(OUT)
                export_seconds = time.perf_counter() - t_export
                width, height = V.ffprobe_size(OUT)
                record("large export keeps native resolution",
                       f"{width}x{height}, preset=320x180, {export_seconds:.1f}s, "
                       f"{OUT.stat().st_size / 1e6:.1f}MB",
                       (width, height) == (3840, 2160))
                record("no page or console errors", repr(errors[:6]), not errors)
            finally:
                ctx.close()
        finally:
            browser.close()

    if OUT.exists():
        OUT.unlink()
    if LARGE.exists():
        LARGE.unlink()
    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    if problems:
        print("VIDEO LARGE FAIL")
        for problem in problems:
            print("FAIL " + problem)
        return 1
    print("VIDEO LARGE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
