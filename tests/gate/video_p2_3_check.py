#!/usr/bin/env python3
"""P2-3 Task B acceptance (permanent gate check G21).

Checks, in real Chromium:
  1. The image limit stays 40 MB and the video limit is a separate 850 MB,
     with exact boundaries, a 0-byte rejection, and a clear message.
  2. Loading a video never reads the whole file: FileReader, Blob.arrayBuffer,
     Blob.text, Blob.stream and fetch are instrumented and must stay at 0.
  3. The size controls stay visible but inert for video, with an inline note;
     they are enabled again for an image.
  4. An export ignores the size preset and matches the video's native
     display size (rotation metadata included) for landscape, portrait, odd
     and 4K inputs, measured with ffprobe.
  5. The canvas-limit helper rejects an impossible native size clearly.

usage:
  python tests/gate/video_p2_3_check.py
"""
from __future__ import annotations

import functools
import json
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/tmp/opencode/glyphcraft_p2_3_video")
FIXTURE_IMAGE = Path("/tmp/glyphcraft_gate_fixture.png")
FIXTURES = {
    "1080p": (WORK / "1920x1080.mp4", 1920, 1080),
    "720p": (WORK / "1280x720.mp4", 1280, 720),
    "4k": (WORK / "3840x2160.mp4", 3840, 2160),
    "portrait": (WORK / "1080x1920.mp4", 1080, 1920),
    "odd": (WORK / "1002x562.mp4", 1002, 562),
}
ROTATED = WORK / "rotated-1080x1920.mp4"
READ_PROBE = r"""
(() => {
  window.__fileReads = [];
  const note = (name) => window.__fileReads.push(name);
  for (const m of ["readAsArrayBuffer", "readAsDataURL", "readAsText", "readAsBinaryString"]) {
    const orig = FileReader.prototype[m];
    if (!orig) continue;
    FileReader.prototype[m] = function (...a) { note("FileReader." + m); return orig.apply(this, a); };
  }
  for (const m of ["arrayBuffer", "text", "stream"]) {
    const orig = Blob.prototype[m];
    if (!orig) continue;
    Blob.prototype[m] = function (...a) { note("Blob." + m); return orig.apply(this, a); };
  }
  const fetchOrig = window.fetch;
  if (fetchOrig) window.fetch = function (...a) { note("fetch"); return fetchOrig.apply(this, a); };
})();
"""


class Server:
    def __enter__(self):
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_video(path: Path, width: int, height: int, *, rotation: int | None = None) -> None:
    if path.exists() and path.stat().st_size:
        return
    args = ["ffmpeg", "-y"]
    if rotation is not None:
        args += ["-display_rotation", str(rotation), "-noautorotate"]
    args += ["-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate=24:duration=1",
             "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-an", str(path)]
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_fixtures() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for path, width, height in FIXTURES.values():
        make_video(path, width, height)
    make_video(ROTATED, 1080, 1920, rotation=90)
    if not FIXTURE_IMAGE.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import run_gate  # noqa: E402
        run_gate.make_png(FIXTURE_IMAGE, width=900, height=600, seed=0)


def ffprobe_size(path: Path) -> tuple[int, int]:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    stream = (json.loads(proc.stdout).get("streams") or [{}])[0]
    return int(stream.get("width") or 0), int(stream.get("height") or 0)


def new_page(browser, srv, *, instrument_reads: bool = False):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US")
    ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
    if instrument_reads:
        ctx.add_init_script(READ_PROBE)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(srv.url + "/index.html", wait_until="load")
    page.wait_for_timeout(400)
    return ctx, page, errors


def load_video(page, path: Path) -> None:
    page.set_input_files("#file-input", str(path))
    page.wait_for_function(
        "() => state.sourceType === 'video' && state.source && state.source.readyState >= 2",
        timeout=120000)
    page.wait_for_timeout(500)


def export_video_size(page, path: Path, out: Path) -> tuple[int, int]:
    load_video(page, path)
    page.evaluate("""() => {
      state.opts.effects.forEach(fx => { fx.enabled = false; });
      state.opts.exportFormat = 'webm';
      state.opts.outputPreset = 'custom';
      state.opts.outputWidth = 320;
      state.opts.outputHeight = 180;
      state.opts.outputFit = 'contain';
      state.opts.jpgQuality = 90;
      rebuildRamp();
      syncUIFromState();
      scheduleRender(0);
    }""")
    page.wait_for_timeout(500)
    if out.exists():
        out.unlink()
    with page.expect_download(timeout=240000) as dl:
        page.click("#btn-export")
    dl.value.save_as(out)
    return ffprobe_size(out)


def main() -> int:
    ensure_fixtures()
    rows: list[tuple[str, str, bool]] = []
    problems: list[str] = []

    def record(name: str, detail: str, ok: bool) -> None:
        rows.append((name, detail, ok))
        print(("PASS " if ok else "FAIL ") + name + ": " + detail, flush=True)
        if not ok:
            problems.append(f"{name}: {detail}")

    with Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx, page, errors = new_page(browser, srv, instrument_reads=True)
            try:
                limits = page.evaluate("""() => {
                  const mk = (type, size) => ({ type, size, name: 'probe' });
                  const img = IMAGE_MAX_FILE_BYTES, vid = VIDEO_MAX_FILE_BYTES;
                  return {
                    img, vid,
                    videoExact: fileSizeError(mk('video/webm', vid)),
                    videoPlus1: fileSizeError(mk('video/webm', vid + 1)),
                    imageExact: fileSizeError(mk('image/png', img)),
                    imagePlus1: fileSizeError(mk('image/png', img + 1)),
                    videoZero: fileSizeError(mk('video/webm', 0)),
                    imageZero: fileSizeError(mk('image/png', 0)),
                  };
                }""")
                record("image limit is 40 MB", f"{limits['img']} bytes",
                       limits["img"] == 40 * 1024 * 1024)
                record("video limit is a separate 850 MB", f"{limits['vid']} bytes",
                       limits["vid"] == 850 * 1024 * 1024 and limits["vid"] != limits["img"])
                record("video 850 MB exact accepted", repr(limits["videoExact"]),
                       limits["videoExact"] == "")
                record("video 850 MB + 1 rejected", repr(limits["videoPlus1"]),
                       "850 MB" in limits["videoPlus1"] and "too large" in limits["videoPlus1"])
                record("image 40 MB exact accepted", repr(limits["imageExact"]),
                       limits["imageExact"] == "")
                record("image 40 MB + 1 rejected", repr(limits["imagePlus1"]),
                       "40 MB" in limits["imagePlus1"] and "too large" in limits["imagePlus1"])
                record("0-byte video rejected clearly", repr(limits["videoZero"]),
                       "empty" in limits["videoZero"].lower())
                record("0-byte image rejected clearly", repr(limits["imageZero"]),
                       "empty" in limits["imageZero"].lower())

                helper = page.evaluate("""() => ({
                  small: videoExportSizeError(3840, 2160),
                  hugeSide: videoExportSizeError(70000, 100),
                  hugeArea: videoExportSizeError(20000, 20000),
                  zero: videoExportSizeError(0, 1080),
                })""")
                record("canvas limit accepts 4K", repr(helper["small"]), helper["small"] == "")
                record("canvas limit rejects 70000 px side", repr(helper["hugeSide"]),
                       bool(helper["hugeSide"]))
                record("canvas limit rejects 400 MP area", repr(helper["hugeArea"]),
                       bool(helper["hugeArea"]))
                record("canvas limit rejects zero dimension", repr(helper["zero"]),
                       bool(helper["zero"]))

                load_video(page, FIXTURES["720p"][0])
                reads = page.evaluate("() => window.__fileReads.slice()")
                record("video load does not read the whole file", repr(reads), reads == [])
                page.evaluate("""() => {
                  state.opts.outputPreset = 'custom';
                  els.outputPreset.value = 'custom';
                  updateOutputCustomVisibility();
                  syncPresetPicker();
                }""")
                ui = page.evaluate("""() => {
                  const ids = ['output-preset-trigger', 'output-width', 'output-height',
                               'output-fit', 'output-lock-ratio'];
                  const note = document.getElementById('output-video-note');
                  return {
                    disabled: ids.map(id => !!document.getElementById(id).disabled),
                    visible: ids.map(id => {
                      const el = document.getElementById(id);
                      const r = el.getBoundingClientRect();
                      return !el.hidden && r.width > 0 && r.height > 0;
                    }),
                    noteHidden: note ? note.hidden : null,
                    noteText: note ? note.textContent.trim() : '',
                  };
                }""")
                record("video size controls stay visible", repr(ui["visible"]),
                       all(ui["visible"]))
                record("video size controls are inert", repr(ui["disabled"]),
                       all(ui["disabled"]))
                record("video note is visible and explains native export",
                       f"hidden={ui['noteHidden']} text={ui['noteText']!r}",
                       ui["noteHidden"] is False and "original resolution" in ui["noteText"].lower())

                page.set_input_files("#file-input", str(FIXTURE_IMAGE))
                page.wait_for_function("() => state.sourceType === 'image'", timeout=30000)
                page.wait_for_timeout(400)
                img_ui = page.evaluate("""() => {
                  const ids = ['output-preset-trigger', 'output-width', 'output-height',
                               'output-fit', 'output-lock-ratio'];
                  const note = document.getElementById('output-video-note');
                  return { disabled: ids.map(id => !!document.getElementById(id).disabled),
                           noteHidden: note ? note.hidden : null };
                }""")
                record("image re-enables the size controls", repr(img_ui["disabled"]),
                       not any(img_ui["disabled"]))
                record("image hides the video note", repr(img_ui["noteHidden"]),
                       img_ui["noteHidden"] is True)

                for label, (path, _w, _h) in FIXTURES.items():
                    out = WORK / f"out-{label}.webm"
                    width, height = export_video_size(page, path, out)
                    native = page.evaluate("() => [state.video.videoWidth, state.video.videoHeight]")
                    record(f"export {label} equals native {native[0]}x{native[1]}",
                           f"ffprobe={width}x{height} preset=320x180",
                           (width, height) == (native[0], native[1]))

                out = WORK / "out-rotated.webm"
                width, height = export_video_size(page, ROTATED, out)
                native = page.evaluate("() => [state.video.videoWidth, state.video.videoHeight]")
                has_rotation = native != [1080, 1920]
                record("export rotated video equals displayed native size",
                       f"ffprobe={width}x{height} browser={native[0]}x{native[1]} rotation_seen={has_rotation}",
                       (width, height) == (native[0], native[1]) and has_rotation)

                record("no page or console errors", repr(errors[:6]), not errors)
            finally:
                ctx.close()
        finally:
            browser.close()

    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    if problems:
        print("VIDEO P2-3 FAIL")
        for problem in problems:
            print("FAIL " + problem)
        return 1
    print("VIDEO P2-3 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
