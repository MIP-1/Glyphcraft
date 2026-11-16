#!/usr/bin/env python3
"""G22: real video flow, driven through the real UI in Chromium and Firefox.

This check exists because P2-3's G1-G21 stayed green while hand testing found
the video path broken. It loads real generated clips, uses the real controls,
plays, pauses, seeks, exports and inspects the produced files.

usage:
  python tests/gate/video_real_flow.py --browser chromium
  python tests/gate/video_real_flow.py --browser firefox
  python tests/gate/video_real_flow.py --browser chromium --only parity,export
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/tmp/opencode/glyphcraft_video")
EVIDENCE = ROOT / "docs" / "evidence" / os.environ.get("GATE_TASK", "v0")
FIXTURE_IMAGE = Path("/tmp/glyphcraft_gate_fixture.png")
VIDEO_SIZES = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "portrait": (1080, 1920),
    "4k": (3840, 2160),
}
LIGHT = ["posterize", "duotone"]
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen", "oil"]


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


def make_videos() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for name, (w, h) in VIDEO_SIZES.items():
        path = WORK / f"src-{w}x{h}.webm"
        if path.exists() and path.stat().st_size > 200_000:
            continue
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration=6",
            "-f", "lavfi", "-i", f"mandelbrot=size={w}x{h}:rate=30",
            "-filter_complex", "[0:v][1:v]blend=all_mode=overlay,format=yuv420p",
            "-t", "6", "-c:v", "libvpx-vp9", "-deadline", "realtime",
            "-cpu-used", "8", "-b:v", "8M", "-an", str(path),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    audio = WORK / "src-audio-320x180.webm"
    if not (audio.exists() and audio.stat().st_size > 20_000):
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8",
            "-b:v", "1M", "-c:a", "libopus", "-shortest", str(audio),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not FIXTURE_IMAGE.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import run_gate  # noqa: E402
        run_gate.make_png(FIXTURE_IMAGE, width=900, height=600, seed=0)
    huge = WORK / "fixture-3840x2160.png"
    if not huge.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import run_gate  # noqa: E402
        run_gate.make_png(huge, width=3840, height=2160, seed=2)


def ffprobe(path: Path) -> dict:
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_name,codec_type,width,height,pix_fmt,nb_frames,nb_read_frames,"
        "r_frame_rate,avg_frame_rate,duration"
        ":format=format_name,duration,size",
        "-count_frames", "-of", "json", str(path),
    ], capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"stream": stream, "format": data.get("format", {})}


def frame_hashes(path: Path, times: list[float]) -> list[str]:
    out = []
    for t in times:
        proc = subprocess.run([
            "ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
            "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
        ], capture_output=True, check=True)
        out.append(hashlib.sha256(proc.stdout).hexdigest()[:16])
    return out


def video_summary(path: Path) -> dict:
    """Decoded frame count, fps and duration, not just container tags."""
    probe = ffprobe(path)
    stream = probe["stream"]
    fps_txt = stream.get("r_frame_rate") or "0/1"
    num, _, den = fps_txt.partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return {
        "codec": stream.get("codec_name"),
        "pix_fmt": stream.get("pix_fmt"),
        "w": stream.get("width"),
        "h": stream.get("height"),
        "frames": int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0),
        "fps": round(fps, 3),
        "duration": round(float(probe["format"].get("duration") or 0), 3),
        "format": probe["format"].get("format_name"),
    }


def top_level_boxes(path: Path) -> list[str]:
    data = path.read_bytes()
    out: list[str] = []
    i = 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i:i + 4], "big")
        kind = data[i + 4:i + 8].decode("latin1", "replace")
        if size == 1 and i + 16 <= len(data):
            size = int.from_bytes(data[i + 8:i + 16], "big")
        if size < 8:
            break
        out.append(kind)
        i += size
    return out


def decodes_at(path: Path, t: float) -> bool:
    proc = subprocess.run([
        "ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
        "-frames:v", "1", "-f", "null", "-",
    ], capture_output=True, text=True)
    return proc.returncode == 0 and not proc.stderr.strip()


def video_pts(path: Path) -> list[float]:
    """Every decoded frame's presentation time, used as the identity grid."""
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path),
    ], capture_output=True, text=True, check=True)
    return [float(x) for x in proc.stdout.split() if x.strip()]


def page_ready(page, srv, theme="dark"):
    ctx = page.context
    ctx.add_init_script(
        "try{localStorage.setItem('glyphcraft-theme','%s')}catch(e){}" % theme)
    page.goto(srv.url + "/index.html", wait_until="load")
    page.wait_for_timeout(500)
    page.evaluate("""() => {
      window.__gcHash = function (c) {
        const d = c.getContext('2d', {willReadFrequently: true})
          .getImageData(0, 0, c.width, c.height).data;
        let h = 2166136261;
        for (let i = 0; i < d.length; i += 4) {
          h ^= d[i]; h = Math.imul(h, 16777619);
          h ^= d[i + 1]; h = Math.imul(h, 16777619);
          h ^= d[i + 2]; h = Math.imul(h, 16777619);
          h ^= d[i + 3]; h = Math.imul(h, 16777619);
        }
        return h >>> 0;
      };
      window.__gcState = function () {
        const c = document.getElementById('canvas');
        const full = computeOutputSize(state.sourceW, state.sourceH,
          state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight,
          state.opts.outputFit);
        const pv = previewSize(full);
        return {
          type: state.sourceType, w: c.width, h: c.height,
          previewW: pv.w, previewH: pv.h, hash: window.__gcHash(c),
          playing: !!state.video && !state.video.paused && !state.video.ended,
          t: state.video ? +state.video.currentTime.toFixed(3) : null,
          renderMs: Math.round(state.lastRender),
          zoom: state.zoom, effects: (state.opts.effects || [])
            .filter(f => f.enabled).map(f => f.id),
        };
      };
    }""")


def load_video(page, path: Path, autoplay_src: bool = True):
    page.set_input_files("#file-input", str(path))
    page.wait_for_function(
        "() => state.sourceType === 'video' && state.video && state.video.readyState >= 2",
        timeout=120000)
    page.wait_for_function("() => state.exportSupport && state.exportSupport.key",
                           timeout=60000)
    page.wait_for_timeout(300)
    page.evaluate("() => { state.video.pause(); stopVideoLoop(); scheduleRender(0); }")
    page.wait_for_timeout(250)


def set_effects(page, ids):
    page.evaluate("""(ids) => {
      state.opts.effects = state.opts.effects.map(fx => ({
        ...fx, enabled: ids.includes(fx.id),
        params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
      }));
      state.opts.mode = 'effects';
      scheduleRender(0);
    }""", ids)
    page.wait_for_timeout(300)


def seek(page, t: float):
    """Pause and seek, then wait for the painted frame to settle.

    Firefox does not fire requestVideoFrameCallback for a paused seek, so the
    old rVFC wait always ran into its 1.5 s timeout. A paused seek is settled
    once `seeked` has fired and two canvas reads 60 ms apart are identical.
    """
    page.evaluate("""async (t) => {
      const v = state.video;
      v.pause();
      if (Math.abs(v.currentTime - t) > 0.0005) {
        await new Promise(r => {
          let done = false;
          const finish = () => { if (!done) { done = true; r(); } };
          v.addEventListener('seeked', finish, {once: true});
          v.currentTime = t;
          setTimeout(finish, 2500);
        });
      }
      scheduleRender(0);
      await new Promise(r => setTimeout(r, 120));
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      await new Promise(r => setTimeout(r, 80));
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    }""", t)


def still_hash(page, t: float) -> int:
    return page.evaluate("""async (t) => {
      const v = state.video;
      if (Math.abs(v.currentTime - t) > 0.0005) {
        await new Promise(r => {
          let done = false;
          const finish = () => { if (!done) { done = true; r(); } };
          v.addEventListener('seeked', finish, {once: true});
          v.currentTime = t;
          setTimeout(finish, 2000);
        });
      }
      await new Promise(r => setTimeout(r, 120));
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const full = computeOutputSize(state.sourceW, state.sourceH,
        state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight,
        state.opts.outputFit);
      const pv = previewSize(full);
      const opts = renderOpts();
      const base = prepareBase(v, pv.w, pv.h, opts);
      const c = document.createElement('canvas');
      c.width = pv.w; c.height = pv.h;
      renderToContext(base, c.getContext('2d', {willReadFrequently: true}),
        pv.w, pv.h, opts);
      return window.__gcHash(c);
    }""", t)


def click_export(page, out: Path, timeout=240000) -> dict:
    if out.exists():
        out.unlink()
    with page.expect_download(timeout=timeout) as dl:
        page.click("#btn-export")
    download = dl.value
    download.save_as(out)
    return {"suggested": download.suggested_filename, "size": out.stat().st_size}


def hash_video_frame(page) -> int:
    return page.evaluate("() => window.__gcHash(document.getElementById('canvas'))")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", choices=["chromium", "firefox"], default="chromium")
    ap.add_argument("--only", default="")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}
    make_videos()
    pts = video_pts(WORK / "src-1280x720.webm")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    tag = f"{args.browser}-{time.strftime('%H%M%S')}"
    rows: list[dict] = []
    problems: list[str] = []

    def record(case: str, name: str, detail: str, ok: bool) -> None:
        rows.append({"case": case, "name": name, "detail": detail, "ok": ok})
        print(("PASS " if ok else "FAIL ") + f"[{case}] {name}: {detail}", flush=True)
        if not ok:
            problems.append(f"[{case}] {name}: {detail}")

    def wanted(case: str) -> bool:
        return not only or case in only

    with Server() as srv, sync_playwright() as p:
        browser_type = getattr(p, args.browser)
        browser = browser_type.launch(headless=not args.headful)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  accept_downloads=True, locale="en-US")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
        page.on("console", lambda m: errors.append("console: " + m.text)
                if m.type == "error" else None)
        page_ready(page, srv)

        video = WORK / "src-1280x720.webm"
        load_video(page, video)
        set_effects(page, LIGHT)

        # ------------------------------------------------------------ seek UI
        if wanted("seek"):
            ui = page.evaluate("""() => {
              const ids = ['video-toggle', 'video-seek', 'video-back', 'video-forward'];
              return Object.fromEntries(ids.map(id => {
                const el = document.getElementById(id);
                if (!el) return [id, null];
                const r = el.getBoundingClientRect();
                return [id, {w: Math.round(r.width), h: Math.round(r.height),
                             hidden: el.hidden || getComputedStyle(el).display === 'none',
                             type: el.type || el.tagName}];
              }));
            }""")
            record("seek", "video control bar exists", json.dumps(ui),
                   all(ui.get(i) and not ui[i]["hidden"] for i in
                       ("video-toggle", "video-seek", "video-back", "video-forward")))
            record("seek", "seek bar is a range input",
                   json.dumps(ui.get("video-seek")),
                   bool(ui.get("video-seek") and ui["video-seek"]["type"] == "range"))
            record("seek", "jump buttons meet 44px touch target",
                   json.dumps({k: ui.get(k) for k in ("video-back", "video-forward")}),
                   all(ui.get(k) and ui[k]["w"] >= 44 and ui[k]["h"] >= 44
                       for k in ("video-back", "video-forward")))
            if ui.get("video-seek"):
                page.evaluate("""() => {
                  const s = document.getElementById('video-seek');
                  s.value = 3;
                  s.dispatchEvent(new Event('input', {bubbles: true}));
                  s.dispatchEvent(new Event('change', {bubbles: true}));
                }""")
                page.wait_for_timeout(500)
                t = page.evaluate("() => +state.video.currentTime.toFixed(2)")
                record("seek", "seek bar moves the video", f"currentTime={t}",
                       abs(t - 3) < 0.35)
                page.click("#video-back")
                page.wait_for_timeout(300)
                back = page.evaluate("() => +state.video.currentTime.toFixed(2)")
                page.click("#video-forward")
                page.wait_for_timeout(300)
                forward = page.evaluate("() => +state.video.currentTime.toFixed(2)")
                record("seek", "jump buttons step 5 s and clamp",
                       f"back={back} forward={forward}",
                       abs(back - max(0, t - 5)) < 0.4 and abs(forward - min(6, t)) < 0.4)

        # -------------------------------------------------------- quality parity
        if wanted("parity"):
            times = [0, 0.1, 0.4, 0.7, 1.0, 1.3, 1.6, 2.0, 2.4, 2.8, 3.2, 3.6,
                     4.0, 4.4, 4.8, 5.2, 5.5, 5.7, 5.9, 5.99]
            page.evaluate("() => { state.video.pause(); stopVideoLoop(); }")
            page.wait_for_timeout(300)
            bad = []
            backing = set()
            for t in times:
                seek(page, t)
                st = page.evaluate("() => window.__gcState()")
                backing.add((st["w"], st["h"]))
                expected = still_hash(page, t)
                if st["hash"] != expected:
                    bad.append({"t": t, "preview": st["hash"], "still": expected,
                                "w": st["w"], "h": st["h"]})
            record("parity", "paused and seeked frames equal a fresh still render",
                   f"{len(times) - len(bad)}/{len(times)} timestamps, backing={sorted(backing)}, "
                   f"mismatches={bad[:4]}", not bad)

            # A plain seek must repaint by itself: the browser's own `seeked`
            # event and a settle pause, with no test-driven render. This is the
            # seek-race contract the control bar will expose in V3.
            pairs = [(0.5, 1.7), (2.6, 4.1), (4.9, 0.3), (1.2, 5.5), (5.9, 0.8)]
            stale = []
            for before_t, after_t in pairs:
                seek(page, before_t)
                old = page.evaluate("() => window.__gcState()")
                page.evaluate("""async (t) => {
                  const v = state.video;
                  await new Promise(r => {
                    let done = false;
                    const fin = () => { if (!done) { done = true; r(); } };
                    v.addEventListener('seeked', fin, {once: true});
                    v.currentTime = t;
                    setTimeout(fin, 4000);
                  });
                  await new Promise(r => setTimeout(r, 300));
                }""", after_t)
                now = page.evaluate("() => window.__gcState()")
                want = still_hash(page, after_t)
                if now["hash"] != want or now["hash"] == old["hash"]:
                    stale.append({"from": before_t, "to": after_t,
                                  "canvas_equals_still": now["hash"] == want,
                                  "unchanged": now["hash"] == old["hash"],
                                  "t": now["t"]})
            record("parity", "a seek repaints the preview without a test render",
                   f"{len(pairs) - len(stale)}/{len(pairs)} seeks, stale={stale[:3]}",
                   not stale)

            rec = page.evaluate("() => window.__gcState()")
            record("parity", "paused preview uses the full preview size",
                   f"canvas={rec['w']}x{rec['h']} preview={rec['previewW']}x{rec['previewH']}",
                   rec["w"] == rec["previewW"] and rec["h"] == rec["previewH"])

            paused = page.evaluate("() => window.__gcState()")
            page.evaluate("() => { state.video.currentTime = 1.0; state.video.play(); startVideoLoop(); }")
            page.wait_for_timeout(2500)
            playing = page.evaluate("() => window.__gcState()")
            page.evaluate("() => { state.video.pause(); stopVideoLoop(); scheduleRender(0); }")
            page.wait_for_timeout(300)
            record("parity", "playback never lowers render resolution",
                   f"paused={paused['w']}x{paused['h']} playing={playing['w']}x{playing['h']} "
                   f"preview={paused['previewW']}x{paused['previewH']}",
                   playing["w"] == paused["previewW"] and playing["h"] == paused["previewH"])
            record("parity", "playing frame keeps full preview backing",
                   f"playing={playing['w']}x{playing['h']} preview={playing['previewW']}x{playing['previewH']}",
                   playing["w"] == playing["previewW"] and playing["h"] == playing["previewH"])

            # Sample the canvas that is actually on screen while the clip plays,
            # then prove each distinct sample is the app's own paused render of a
            # real source frame. Firefox reports the presentation time of frame k
            # but drawImage during that callback can still return frame k-1, so a
            # sample must match PTS k or its immediate predecessor. This is
            # stricter than the old +/-0.6 s scan: every shown frame must be
            # pixel-identical to a specific decoded frame, and no resolution
            # change is accepted. A browser-level partially decoded frame
            # (localized, mean <= 4 against its nearest frame) is reported as a
            # glitch, at most two per run, never a different or rescaled frame.
            page.evaluate("""() => {
              window.__gcProbe = function (c, withPixels) {
                const t = document.createElement('canvas');
                t.width = 64; t.height = 36;
                const x = t.getContext('2d', {willReadFrequently: true});
                x.drawImage(c, 0, 0, 64, 36);
                const d = x.getImageData(0, 0, 64, 36).data;
                let h = 2166136261;
                for (let i = 0; i < d.length; i++) {
                  h ^= d[i]; h = Math.imul(h, 16777619);
                }
                let px = null;
                if (withPixels) {
                  px = new Array(64 * 36 * 3);
                  for (let i = 0, j = 0; i < d.length; i += 4) {
                    px[j++] = d[i]; px[j++] = d[i + 1]; px[j++] = d[i + 2];
                  }
                }
                return {hash: h >>> 0, px};
              };
            }""")
            page.evaluate("""() => {
              state.playbackFrameTime = null;
              state.video.currentTime = 0.2;
              state.video.play();
              startVideoLoop();
            }""")
            page.wait_for_function("() => state.playbackFrameTime !== null", timeout=8000)
            samples = []
            for _ in range(28):
                page.wait_for_timeout(90)
                samples.append(page.evaluate("""() => {
                  const c = document.getElementById('canvas');
                  const p = window.__gcProbe(c, true);
                  return {t: state.playbackFrameTime, hash: p.hash, px: p.px,
                          w: c.width, h: c.height};
                }"""))
            page.evaluate("() => { state.video.pause(); stopVideoLoop(); scheduleRender(0); }")
            page.wait_for_timeout(300)
            distinct = {}
            for s in samples:
                if s["t"] is not None:
                    distinct.setdefault(s["hash"], s["t"])
            times = [s["t"] for s in samples if s["t"] is not None]
            backsteps = sum(1 for i in range(len(times) - 1) if times[i + 1] < times[i])

            clip_len = pts[-1] + (pts[1] - pts[0])

            def nearest_frame(t):
                return min(range(len(pts)), key=lambda i: abs(pts[i] - t))

            sizes = sorted({(s["w"], s["h"]) for s in samples})
            size_ok = sizes == [(rec["previewW"], rec["previewH"])]
            if not size_ok:
                # A rescaled canvas cannot equal a still at the preview size;
                # report it instead of scanning every frame at the wrong size.
                record("parity", "frames shown during playback match a fresh still render",
                       f"canvas sizes={sizes} preview="
                       f"{rec['previewW']}x{rec['previewH']}, identity not testable",
                       False)

            def mean_diff(a, b):
                total = 0
                for k in range(len(a)):
                    total += abs(a[k] - b[k])
                return total / len(a)

            samples_by_hash = {}
            for s in samples:
                if s["t"] is not None:
                    samples_by_hash.setdefault(s["hash"], s)
            missing = []
            glitches = []
            retries = []
            matched_offsets = []
            matched_times = []
            for h, first in (samples_by_hash.items() if size_ok else []):
                # The clip loops while sampling, so a reported mediaTime can be
                # past the end; normalise it to the frame actually on screen.
                t = first["t"] % clip_len
                i = nearest_frame(t)
                # Try the reported frame and its immediate neighbours first.
                order = sorted(range(max(0, i - 3), min(len(pts), i + 4)),
                               key=lambda j: abs(j - i))
                # Starved playback lets rVFC report a frame the compositor has
                # not painted yet, so drawImage can lag by many frames; widen to
                # +/-0.53 s, which is still tighter than the old +/-0.6 s scan.
                order += [j for j in range(max(0, i - 16), min(len(pts), i + 17))
                          if j not in order]
                matched = False
                for attempt in range(2):
                    for j in order:
                        seek(page, pts[j])
                        got = page.evaluate("""() => window.__gcProbe(
                          document.getElementById('canvas'), false).hash""")
                        if got == h:
                            matched = True
                            matched_offsets.append(round(pts[j] - t, 4))
                            matched_times.append(pts[j])
                            break
                    if matched:
                        break
                    # A rare stale drawImage after a paused seek can hash the
                    # previous frame for every candidate; settle and retry once.
                    page.wait_for_timeout(500)
                if matched:
                    continue
                retries.append(round(t, 3))
                # Chromium can hand drawImage a video frame that is only partly
                # decoded (measured: one 64x36 sample differing from every
                # decoded frame with mean 2.7 but max 191, and no two-frame row
                # split). Classify that localized artifact separately from a
                # different or rescaled frame, which differs across the image.
                best = None
                for j in range(max(0, i - 4), min(len(pts), i + 5)):
                    seek(page, pts[j])
                    px = page.evaluate("""() => window.__gcProbe(
                      document.getElementById('canvas'), true).px""")
                    md = mean_diff(first["px"], px)
                    if best is None or md < best[0]:
                        best = (md, round(pts[j] - t, 4))
                if best and best[0] <= 4.0:
                    glitches.append({"t": round(t, 3), "frame_offset": best[1],
                                     "mean_diff": round(best[0], 2)})
                else:
                    missing.append({"t": round(t, 3), "hash": h,
                                    "best": None if not best
                                    else [round(best[0], 2), best[1]],
                                    "frames": [round(pts[i], 3),
                                               round(pts[i - 1], 3) if i else None]})
            span = round(max(matched_times) - min(matched_times), 3) if matched_times else 0
            exact = len(samples_by_hash) - len(glitches) - len(missing)
            if size_ok:
                record("parity",
                       "frames shown during playback match a fresh still render",
                       f"{len(distinct)} distinct on-screen frames, exact={exact}, "
                       f"unmatched={missing[:3]}, glitches={glitches[:3]}, "
                       f"offsets={sorted(set(matched_offsets))[:12]}, span={span}s, "
                       f"retried={retries[:4]}, "
                       f"backsteps={backsteps}/{max(0, len(times) - 1)} "
                       f"(rVFC runs ahead of the starved clock; measured, not gated), "
                       f"times={[round(t, 3) for t in times][:30]}",
                       not missing and exact >= len(samples_by_hash) - 2
                       and len(distinct) >= 3
                       and all(abs(off) <= 0.5 for off in matched_offsets)
                       and span >= 1.5)
            record("parity", "playback never shrinks the backing store",
                   f"widths={sorted(set(s['w'] for s in samples))}",
                   all(s["w"] == rec["previewW"] for s in samples))

        # ------------------------------------------------------------ output UI
        if wanted("output"):
            out_ui = page.evaluate("""() => {
              const ids = ['output-preset-trigger', 'output-width', 'output-height',
                           'output-fit', 'output-lock-ratio'];
              const note = document.getElementById('output-video-note');
              return {
                disabled: Object.fromEntries(ids.map(id => [id,
                  !!document.getElementById(id).disabled])),
                formats: Array.from(document.getElementById('export-format').options)
                  .map(o => o.value),
                noteHidden: note ? note.hidden : null,
                note: note ? note.textContent.trim() : '',
                button: document.getElementById('btn-export').textContent.trim(),
                frameButton: !!document.getElementById('btn-export-frame'),
              };
            }""")
            record("output", "size controls are enabled for video",
                   json.dumps(out_ui["disabled"]), not any(out_ui["disabled"].values()))
            record("output", "video format list offers MP4 and WebM",
                   json.dumps(out_ui["formats"]),
                   "mp4" in out_ui["formats"] and "webm" in out_ui["formats"]
                   and "png" not in out_ui["formats"])
            record("output", "main button says Export Video",
                   repr(out_ui["button"]), "video" in out_ui["button"].lower())
            record("output", "Export Frame is a separate action",
                   f"present={out_ui['frameButton']}", out_ui["frameButton"])
            size_line = page.evaluate("""() => {
              const el = document.getElementById('output-size-line');
              return el ? el.textContent.trim() : null;
            }""")
            record("output", "default output size line shows the native size",
                   repr(size_line), bool(size_line and "1280" in size_line and "720" in size_line))

        # --------------------------------------------------------------- export
        if wanted("export"):
            def option_state(fmt: str) -> dict:
                return page.evaluate("""(f) => {
                  const sel = document.getElementById('export-format');
                  const o = Array.from(sel.options).find(x => x.value === f);
                  return {present: !!o, disabled: !!(o && o.disabled),
                          text: o ? o.textContent.trim() : null,
                          note: (document.getElementById('export-format-note') || {})
                            .textContent || '',
                          hidden: !!(document.getElementById('export-format-note') || {})
                            .hidden};
                }""", fmt)

            def progress_ui() -> dict:
                return page.evaluate(r"""() => {
                  const el = document.getElementById('export-progress');
                  const bar = document.getElementById('export-progress-bar');
                  const cancel = document.getElementById('export-cancel');
                  return {
                    present: !!el,
                    hidden: !el || el.hidden || getComputedStyle(el).display === 'none',
                    text: el ? el.textContent.replace(/[ \n\t]+/g, ' ').trim() : '',
                    barValue: bar ? Number(bar.value) : null,
                    cancel: !!cancel && !cancel.hidden,
                    busy: !!state.videoExporting,
                  };
                }""")

            # Start playback away from the start, so a real-time capture would
            # produce a short or offset file. The export must still be whole.
            seek(page, 2.4)
            page.evaluate("() => state.video.play()")
            page.wait_for_timeout(400)
            playhead = page.evaluate("() => +state.video.currentTime.toFixed(3)")

            for fmt, ext, codecs in (("webm", "webm", ("vp9", "vp8")),
                                     ("mp4", "mp4", ("h264",))):
                state = option_state(fmt)
                if not state["present"]:
                    record("export", f"{fmt.upper()} format is in the video list",
                           f"format option {fmt!r} is missing from the list", False)
                    continue
                if state["disabled"]:
                    reason = page.evaluate("""() => {
                      const el = document.getElementById('export-format-note');
                      return el && !el.hidden ? el.textContent.trim() : '';
                    }""")
                    record("export", f"{fmt.upper()} disabled with a visible reason",
                           f"option={state} visible_reason={reason!r}", bool(reason))
                    continue
                page.select_option("#export-format", fmt)
                out = WORK / f"v2-export-{tag}.{ext}"
                try:
                    with page.expect_download(timeout=900000) as dl:
                        page.click("#btn-export")
                        ui = {}
                        for _ in range(300):
                            ui = progress_ui()
                            if ui["present"] and not ui["hidden"]:
                                break
                            page.wait_for_timeout(100)
                        progress_seen = ui
                    download = dl.value
                    download.save_as(out)
                    meta = {"suggested": download.suggested_filename,
                            "size": out.stat().st_size}
                    info = video_summary(out)
                    want_frames = round(info["duration"] * info["fps"])
                    boxes = top_level_boxes(out)
                    seek_ok = decodes_at(out, 2.5) and decodes_at(out, 5.6)
                    hashes = frame_hashes(out, [0.2, 2.9, 5.5])
                    fast = (fmt != "mp4" or
                            ("moov" in boxes and "mdat" in boxes
                             and boxes.index("moov") < boxes.index("mdat")))
                    ok = (meta["size"] > 2000
                          and info["codec"] in codecs
                          and info["pix_fmt"] in ("yuv420p", "yuvj420p")
                          and (info["w"], info["h"]) == (1280, 720)
                          and abs(info["frames"] - want_frames) <= 1
                          and abs(info["duration"] - 6.0) <= 0.2
                          and seek_ok and len(set(hashes)) >= 2 and fast)
                    record("export", f"export produces a real {fmt.upper()} video",
                           f"file={meta} info={info} want_frames={want_frames} "
                           f"boxes={boxes[:6]} seek={seek_ok} hashes={hashes}", ok)
                    record("export", f"{fmt.upper()} covers the clip from the playhead",
                           f"playhead={playhead} export duration={info['duration']} "
                           f"frames={info['frames']}", info["duration"] >= 5.8
                           and info["frames"] >= want_frames - 1)
                    ok_progress = (progress_seen.get("present")
                                   and not progress_seen.get("hidden")
                                   and "frame" in progress_seen.get("text", "").lower()
                                   and progress_seen.get("cancel"))
                    record("export", f"{fmt.upper()} export shows progress and cancel",
                           json.dumps(progress_seen), ok_progress)
                except Exception as exc:  # noqa: BLE001
                    record("export", f"export produces a real {fmt.upper()} video",
                           f"error={exc}", False)

            restored = page.evaluate("""() => ({
              busy: !!state.videoExporting,
              playing: !!state.video && !state.video.paused && !state.video.ended,
              t: state.video ? +state.video.currentTime.toFixed(2) : null,
            })""")
            record("export", "preview state is restored after export",
                   json.dumps(restored) + f" playhead={playhead}",
                   not restored["busy"] and restored["playing"])
            done_ui = progress_ui()
            record("export", "progress panel hides when the export finishes",
                   json.dumps(done_ui), done_ui["present"] and done_ui["hidden"]
                   and not done_ui["busy"])

            # Export Frame is a separate still action, not the video default.
            page.evaluate("() => { state.video.pause(); }")
            page.wait_for_timeout(300)
            out = WORK / f"v2-frame-{tag}.png"
            try:
                with page.expect_download(timeout=120000) as dl:
                    page.click("#btn-export-frame")
                download = dl.value
                download.save_as(out)
                meta = {"suggested": download.suggested_filename,
                        "size": out.stat().st_size}
                probe = subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                    "-of", "json", str(out)], capture_output=True, text=True, check=True)
                st = json.loads(probe.stdout)["streams"][0]
                record("export", "Export Frame writes one full-size still",
                       f"file={meta} size={st['width']}x{st['height']}",
                       meta["size"] > 2000 and (st["width"], st["height"]) == (1280, 720))
            except Exception as exc:  # noqa: BLE001
                record("export", "Export Frame writes one full-size still",
                       f"error={exc}", False)

            # Audio: the note must be visible, and the file must not claim
            # to carry audio it does not have.
            audio_src = WORK / "src-audio-320x180.webm"
            page.set_input_files("#file-input", str(audio_src))
            page.wait_for_function(
                "() => state.sourceType === 'video' && state.video.readyState >= 2",
                timeout=120000)
            page.wait_for_function("() => state.exportSupport && state.exportSupport.key",
                                   timeout=60000)
            page.wait_for_timeout(400)
            audio_ui = page.evaluate("""() => {
              const note = document.getElementById('export-audio-note');
              const r = note.getBoundingClientRect();
              return {hasAudio: !!state.videoHasAudio, hidden: note.hidden,
                      width: r.width, height: r.height,
                      text: note.textContent.trim()};
            }""")
            record("export", "a clip with audio shows a visible note about audio",
                   json.dumps(audio_ui), audio_ui["hasAudio"] and not audio_ui["hidden"]
                   and audio_ui["width"] > 0 and audio_ui["height"] > 0
                   and "audio" in audio_ui["text"].lower())
            out = WORK / f"v2-audio-{tag}.webm"
            try:
                page.select_option("#export-format", "webm")
                with page.expect_download(timeout=600000) as dl:
                    page.click("#btn-export")
                dl.value.save_as(out)
                streams = subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                    "-of", "csv=p=0", str(out)], capture_output=True, text=True,
                    check=True).stdout.split()
                record("export", "the audio clip exports a real picture and keeps the note",
                       f"streams={streams} bytes={out.stat().st_size}",
                       streams.count("video") == 1 and out.stat().st_size > 2000
                       and "audio" in audio_ui["text"].lower())
            except Exception as exc:  # noqa: BLE001
                record("export", "the audio clip exports a real picture and keeps the note",
                       f"error={exc}", False)

            # Cancel must leave no partial download and no busy flag.
            downloads = []
            page.on("download", lambda d: downloads.append(d.suggested_filename))
            page.set_input_files("#file-input", str(WORK / "src-3840x2160.webm"))
            page.wait_for_function(
                "() => state.sourceType === 'video' && state.video.readyState >= 2",
                timeout=180000)
            page.wait_for_function("() => state.exportSupport && state.exportSupport.key",
                                   timeout=60000)
            page.wait_for_timeout(500)
            big_fmt = "webm"
            page.select_option("#export-format", big_fmt)
            page.click("#btn-export")
            cancelled = False
            for _ in range(120):
                ui = progress_ui()
                frames = page.evaluate("() => state.videoExportFrames || 0")
                if ui["present"] and not ui["hidden"] and frames >= 2:
                    page.click("#export-cancel")
                    cancelled = True
                    break
                page.wait_for_timeout(250)
            page.wait_for_timeout(1500)
            after = progress_ui()
            flag = page.evaluate("""() => ({
              busy: !!state.videoExporting, frames: state.videoExportFrames || 0,
              button: (!document.getElementById('btn-export').disabled),
              sources: document.querySelectorAll('a[download]').length,
            })""")
            record("export", "cancel stops the export and leaves the app clean",
                   f"started={cancelled} ui={after} state={flag} downloads={downloads}",
                   cancelled and after["hidden"] and not flag["busy"]
                   and flag["button"] and not downloads)
            seek(page, 1.0)
            still = still_hash(page, 1.0)
            now = page.evaluate("() => window.__gcState()")
            record("export", "preview still renders after a cancelled export",
                   f"hash={now['hash']} still={still}",
                   now["hash"] == still and now["w"] > 0)

            # Cancel must also be reachable on the 700 px peek sheet.
            page.set_viewport_size({"width": 700, "height": 900})
            page.wait_for_timeout(400)
            page.evaluate("() => window.__gcSetSnap && window.__gcSetSnap('peek', false)")
            page.set_input_files("#file-input", str(WORK / "src-1280x720.webm"))
            page.wait_for_function(
                "() => state.sourceType === 'video' && state.video.readyState >= 2",
                timeout=120000)
            page.wait_for_function("() => state.exportSupport && state.exportSupport.key",
                                   timeout=60000)
            page.wait_for_timeout(400)
            page.select_option("#export-format", "webm")
            page.click("#btn-export")
            mobile = None
            for _ in range(120):
                mobile = page.evaluate("""() => {
                  const el = document.getElementById('export-progress');
                  const btn = document.getElementById('export-cancel');
                  const r = el.getBoundingClientRect();
                  const b = btn.getBoundingClientRect();
                  const hit = document.elementFromPoint(b.left + b.width / 2,
                                                        b.top + b.height / 2);
                  return {frames: state.videoExportFrames || 0,
                          snap: document.querySelector('.panel').dataset.snap,
                          panel: [r.left, r.top, r.right, r.bottom],
                          cancel: [b.left, b.top, b.right, b.bottom],
                          hidden: el.hidden,
                          hitId: hit ? (hit.id || hit.className) : null,
                          vw: innerWidth, vh: innerHeight};
                }""")
                if mobile["frames"] >= 1 and not mobile["hidden"]:
                    break
                page.wait_for_timeout(250)
            record("export", "Cancel is visible and clickable on a 700 px peek sheet",
                   json.dumps(mobile),
                   mobile is not None and not mobile["hidden"]
                   and mobile["snap"] != "peek"
                   and mobile["panel"][1] >= 0 and mobile["panel"][3] <= mobile["vh"]
                   and mobile["cancel"][1] >= 0 and mobile["cancel"][3] <= mobile["vh"]
                   and mobile["hitId"] == "export-cancel")
            clicked = False
            tap_error = ""
            try:
                page.click("#export-cancel", timeout=10000)
                clicked = True
            except Exception as exc:  # noqa: BLE001
                tap_error = str(exc)
            idle = False
            try:
                page.wait_for_function("() => !state.videoExporting", timeout=120000)
                idle = True
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(400)
            hidden = page.evaluate(
                "() => document.getElementById('export-progress').hidden")
            record("export", "the 700 px Cancel tap stops the export",
                   f"clicked={clicked} idle={idle} hidden={hidden} error={tap_error}",
                   clicked and idle and hidden)
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.wait_for_timeout(400)

        # ---------------------------------------------------------------- hitch
        if wanted("hitch"):
            page.set_input_files("#file-input", str(WORK / "fixture-3840x2160.png"))
            page.wait_for_function("() => state.sourceType === 'image'", timeout=120000)
            page.wait_for_timeout(500)
            # Fullest state: 4K image, six effects, slider and compare drags.
            page.evaluate("""() => {
              state.opts.outputPreset = 'original';
              state.opts.effects = state.opts.effects.map(fx => ({
                ...fx, enabled: ['posterize','edges','sketch','emboss','blur','sharpen'].includes(fx.id),
              }));
              state.compare = true;
              scheduleRender(0);
            }""")
            page.wait_for_timeout(1200)
            hitch = page.evaluate("""async () => {
              const lt = [];
              const obs = new PerformanceObserver(l => {
                for (const e of l.getEntries()) lt.push(e.duration);
              });
              obs.observe({entryTypes: ['longtask']});
              const frames = [];
              let last = performance.now();
              let stop = false;
              const tick = (now) => { frames.push(now - last); last = now;
                if (!stop) requestAnimationFrame(tick); };
              requestAnimationFrame(tick);
              const slider = document.getElementById('compare-slider');
              const r = slider.getBoundingClientRect();
              slider.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true, clientX: r.left + r.width * 0.5,
                clientY: r.top + 40, pointerId: 1, pointerType: 'mouse',
                button: 0, buttons: 1,
              }));
              const start = performance.now();
              for (let i = 0; i < 60; i++) {
                const x = r.left + (r.width * (0.2 + 0.6 * (i % 30) / 29));
                slider.dispatchEvent(new PointerEvent('pointermove', {
                  bubbles: true, clientX: x, clientY: r.top + 40,
                  pointerId: 1, pointerType: 'mouse', buttons: 1,
                }));
                await new Promise(r2 => requestAnimationFrame(r2));
                if (performance.now() - start > 3000) break;
              }
              stop = true;
              obs.disconnect();
              frames.sort((a, b) => a - b);
              return {
                longtasks: lt.length, longtaskMs: lt.reduce((a, b) => a + b, 0),
                worstLong: Math.max(0, ...lt),
                median: frames[Math.floor(frames.length / 2)] || 0,
                p95: frames[Math.floor(frames.length * 0.95)] || 0,
                max: frames[frames.length - 1] || 0,
              };
            }""")
            record("hitch", "compare drag stays responsive on a 4K image with 6 effects",
                   json.dumps(hitch), hitch["longtasks"] == 0 and hitch["p95"] <= 25)

        record("errors", "no page or console errors", repr(errors[:6]), not errors)

        result = {
            "browser": args.browser,
            "user_agent": page.evaluate("() => navigator.userAgent"),
            "rows": rows,
            "problems": problems,
        }
        (EVIDENCE / f"g22-{tag}.json").write_text(json.dumps(result, indent=2),
                                                   encoding="utf-8")
        ctx.close()
        browser.close()

    print(f"{len(rows)} checks, {len(problems)} failure(s) [{args.browser}]")
    if problems:
        print("G22 FAIL")
        for problem in problems:
            print("FAIL " + problem)
        return 1
    print("G22 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
