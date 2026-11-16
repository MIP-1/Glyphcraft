#!/usr/bin/env python3
"""V2 export matrix: drive the real UI for every size and preset, then probe.

This is evidence tooling, not part of `npm run gate`. Every cell exports a
whole clip through the real page, saves the download, and checks it with
ffprobe/ffmpeg: codec, pixel format, size, frame count, duration, seeking,
MP4 fast start, WebM cues, distinct frames and that effects reached the file.

Usage:
  python tools/v2_export_matrix.py --browser chromium
  python tools/v2_export_matrix.py --browser firefox --only original
  python tools/v2_export_matrix.py --browser chromium --only dist
"""
from __future__ import annotations

import argparse
import functools
import json
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "gate"))
import video_real_flow as vrf  # noqa: E402

WORK = Path("/tmp/opencode/glyphcraft_video") / "matrix"
OUT = Path("/tmp/opencode/v2-matrix")
EVIDENCE = ROOT / "docs" / "evidence" / "v2"
FPS = 30
LIGHT = vrf.LIGHT


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def make_clip(name: str, w: int, h: int, duration: float,
              rotate: bool = False) -> Path:
    path = WORK / name
    if path.exists() and path.stat().st_size > 50_000:
        return path
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = WORK / f"tmp-{name}.mp4"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"testsrc2=size={w}x{h}:rate={FPS}:duration={duration}",
         "-f", "lavfi", "-i", f"mandelbrot=size={w}x{h}:rate={FPS}",
         "-filter_complex", "[0:v][1:v]blend=all_mode=overlay,format=yuv420p",
         "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-an", str(tmp)])
    if rotate:
        run(["ffmpeg", "-y", "-display_rotation", "90", "-i", str(tmp),
             "-c", "copy", str(path)])
    else:
        tmp.replace(path)
    tmp.unlink(missing_ok=True)
    return path


def clip_specs() -> list[dict]:
    return [
        {"key": "orig-1280x720", "path": make_clip("matrix-1280x720.mp4", 1280, 720, 2.0),
         "w": 1280, "h": 720, "duration": 2.0},
        {"key": "orig-1920x1080", "path": make_clip("matrix-1920x1080.mp4", 1920, 1080, 2.0),
         "w": 1920, "h": 1080, "duration": 2.0},
        {"key": "orig-3840x2160", "path": make_clip("matrix-3840x2160.mp4", 3840, 2160, 1.0),
         "w": 3840, "h": 2160, "duration": 1.0},
        {"key": "orig-1080x1920", "path": make_clip("matrix-1080x1920.mp4", 1080, 1920, 2.0),
         "w": 1080, "h": 1920, "duration": 2.0},
        {"key": "orig-rotated", "path": make_clip("matrix-rotated.mp4", 1920, 1080, 2.0,
                                                   rotate=True),
         "w": 1080, "h": 1920, "duration": 2.0, "rotated": True},
    ]


def ffprobe_stream(path: Path) -> dict:
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,pix_fmt,width,height,r_frame_rate,duration,"
        "nb_read_frames",
        "-show_entries", "format=duration,start_time", "-of", "json", str(path),
    ], capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    num, _, den = (stream.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    duration = float(stream.get("duration") or fmt.get("duration") or 0)
    return {
        "codec": stream.get("codec_name"), "pix_fmt": stream.get("pix_fmt"),
        "w": stream.get("width"), "h": stream.get("height"),
        "fps": round(fps, 3), "duration": round(duration, 3),
        "frames": int(stream.get("nb_read_frames") or 0)
        or (round(duration * fps) if fps else 0),
        "start": float(fmt.get("start_time") or 0),
    }


def decodes(path: Path, t: float) -> bool:
    proc = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i",
                           str(path), "-frames:v", "1", "-f", "null", "-"],
                          capture_output=True, text=True)
    return proc.returncode == 0 and not proc.stderr.strip()


def boxes(path: Path) -> list[str]:
    out, off = [], 0
    data = path.read_bytes()
    while off + 8 <= len(data):
        size = int.from_bytes(data[off:off + 4], "big")
        kind = data[off + 4:off + 8].decode("latin1")
        if size < 8:
            break
        out.append(kind)
        off += size
    return out


def sig(path: Path, t: float) -> bytes:
    proc = subprocess.run([
        "ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
        "-frames:v", "1", "-vf", "scale=32:32,format=gray", "-f", "rawvideo", "-",
    ], capture_output=True, check=True)
    return proc.stdout


def mad(a: bytes, b: bytes) -> float:
    return round(sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a)), 2)


def has_cues(path: Path) -> bool:
    return b"\x1c\x53\xbb\x6b" in path.read_bytes()


class Server:
    def __init__(self, directory: Path):
        self.directory = directory

    def __enter__(self):
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.directory)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def page_at(p, browser: str, url: str, srv):
    browser_obj = getattr(p, browser).launch()
    ctx = browser_obj.new_context(viewport={"width": 1440, "height": 1000},
                                  accept_downloads=True, locale="en-US")
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    page.on("console", lambda m: errors.append("console: " + m.text)
            if m.type == "error" else None)
    ctx.add_init_script(
        "try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
    page.goto(url, wait_until="load")
    page.wait_for_timeout(500)
    return browser_obj, page, errors


def set_preset(page, preset: str, fit: str = "contain") -> None:
    page.evaluate("""(opts) => {
      Object.assign(state.opts, opts);
      syncOutputControls();
      scheduleRender(0);
    }""", {"outputPreset": preset, "outputFit": fit,
            "outputWidth": 640, "outputHeight": 360})


def browser_rss() -> tuple[float, int]:
    """Summed VmRSS in MB over this Playwright browser's processes."""
    total = 0.0
    count = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ")
        except OSError:
            continue
        if b"ms-playwright" not in cmdline:
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                total += int(line.split()[1]) / 1024
                count += 1
                break
    return round(total, 1), count


def export_one(page, fmt: str, out: Path, mem: bool = False) -> dict:
    if out.exists():
        out.unlink()
    page.select_option("#export-format", fmt)
    if mem:
        page.evaluate("""() => {
          window.__gcMemPeak = 0;
          window.__gcMemTimer = setInterval(() => {
            if (performance.memory) {
              window.__gcMemPeak = Math.max(window.__gcMemPeak,
                performance.memory.usedJSHeapSize);
            }
          }, 100);
        }""")
    rss_base, _ = browser_rss() if mem else (0.0, 0)
    rss_peak, rss_count = 0.0, 0
    rss_stop = threading.Event()

    def sample_rss() -> None:
        nonlocal rss_peak, rss_count
        while not rss_stop.is_set():
            total, count = browser_rss()
            rss_peak = max(rss_peak, total)
            rss_count = count
            rss_stop.wait(0.2)

    sampler = threading.Thread(target=sample_rss, daemon=True) if mem else None
    if sampler:
        sampler.start()
    started = time.time()
    with page.expect_download(timeout=3600000) as dl:
        page.click("#btn-export")
    download = dl.value
    download.save_as(out)
    took = round(time.time() - started, 1)
    peak = None
    if mem:
        rss_stop.set()
        if sampler:
            sampler.join(timeout=2)
        peak = page.evaluate("""() => {
          clearInterval(window.__gcMemTimer);
          return Math.round(window.__gcMemPeak / 1048576);
        }""")
    result = {"suggested": download.suggested_filename,
              "size": out.stat().st_size, "seconds": took, "peakMB": peak}
    if mem:
        result["rssPeakMB"] = rss_peak
        result["rssBaseMB"] = rss_base
        result["rssProcesses"] = rss_count
    return result


def probe_cell(out: Path, fmt: str, w: int, h: int, duration: float,
               source: Path) -> dict:
    info = ffprobe_stream(out)
    frame_box = (w, h)
    want_frames = round(duration * FPS)
    seek_ok = decodes(out, duration * 0.35) and decodes(out, duration * 0.8)
    mid = duration * 0.5
    first = sig(out, duration * 0.15)
    middle = sig(out, mid)
    last = sig(out, duration * 0.85)
    source_sig = sig(source, mid)
    fast = True
    if fmt == "mp4":
        names = boxes(out)
        fast = "moov" in names and "mdat" in names and names.index("moov") < names.index("mdat")
    cell = {
        "format": fmt,
        "codec": info["codec"], "pix_fmt": info["pix_fmt"],
        "width": info["w"], "height": info["h"],
        "frames": info["frames"], "want_frames": want_frames,
        "duration": info["duration"], "start": info["start"],
        "seek": seek_ok, "fast_start": fast,
        "cues": has_cues(out) if fmt == "webm" else None,
        "frame_diff_min": min(mad(first, middle), mad(middle, last),
                              mad(first, last)),
        "effects_diff": mad(middle, source_sig),
        "bytes": out.stat().st_size,
    }
    ok = (cell["width"], cell["height"]) == frame_box
    ok = ok and abs(cell["frames"] - want_frames) <= 1
    ok = ok and abs(cell["duration"] - duration) <= 0.25
    ok = ok and seek_ok and cell["frame_diff_min"] >= 2.0
    ok = ok and cell["effects_diff"] >= 8.0
    if fmt == "mp4":
        ok = ok and cell["codec"] == "h264"
        ok = ok and cell["pix_fmt"] in ("yuv420p", "yuvj420p")
        ok = ok and fast
    else:
        ok = ok and cell["codec"] in ("vp9", "vp8")
        ok = ok and cell["pix_fmt"] == "yuv420p"
        ok = ok and cell["cues"]
    cell["ok"] = ok
    return cell


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", choices=["chromium", "firefox"], default="chromium")
    ap.add_argument("--only", default="")
    ap.add_argument("--clips", default="")
    ap.add_argument("--formats", default="")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}
    clips = {s for s in args.clips.split(",") if s}
    formats = {s for s in args.formats.split(",") if s} or {"webm", "mp4"}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{args.browser}-{time.strftime('%H%M%S')}"
    results: list[dict] = []
    problems: list[str] = []

    def record(kind: str, name: str, detail: dict) -> None:
        detail = {"kind": kind, "name": name, **detail}
        results.append(detail)
        flag = "PASS" if detail.get("ok") else "FAIL"
        if not detail.get("ok"):
            problems.append(f"[{kind}] {name}: {json.dumps(detail)}")
        print(flag, f"[{kind}] {name}: {json.dumps(detail)}", flush=True)

    specs = clip_specs()
    custom_modes = ["contain", "cover", "stretch"]

    with Server(ROOT) as srv, sync_playwright() as p:
        b, page, errors = page_at(p, args.browser, srv.url + "/index.html", srv)
        first = True

        def prepare(source: Path):
            nonlocal first
            vrf.load_video(page, source)
            if first:
                vrf.set_effects(page, LIGHT)
                first = False

        if not only or "original" in only:
            for spec in specs:
                if clips and spec["key"] not in clips:
                    continue
                prepare(spec["path"])
                native = page.evaluate("() => ({w: state.sourceW, h: state.sourceH})")
                set_preset(page, "original")
                for fmt, ext in (("webm", "webm"), ("mp4", "mp4")):
                    if fmt not in formats:
                        continue
                    support = page.evaluate("""async () => {
                      const s = videoOutputSize();
                      await ensureExportSupport(s.w, s.h);
                      return {webm: state.exportSupport.webm, mp4: state.exportSupport.mp4,
                              reason: state.exportSupport.mp4Reason};
                    }""")
                    name = f"{spec['key']}-original-{fmt}"
                    if fmt == "mp4" and not support["mp4"]:
                        record("matrix", name, {
                            "ok": True, "skipped": "MP4 disabled with a visible reason",
                            "reason": support["reason"]})
                        continue
                    out = OUT / args.browser / f"{name}.{ext}"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    mem = args.browser == "chromium" and fmt == "webm" and spec["key"] in (
                        "orig-1920x1080", "orig-3840x2160")
                    try:
                        meta = export_one(page, fmt, out, mem=mem)
                        cell = probe_cell(out, fmt, native["w"], native["h"],
                                          spec["duration"], spec["path"])
                        record("matrix", name, {"ok": cell["ok"], "file": meta, **cell})
                    except Exception as exc:  # noqa: BLE001
                        record("matrix", name, {"ok": False, "error": str(exc)})

        if not only or "custom" in only:
            source = specs[0]
            prepare(source["path"])
            for fit in custom_modes:
                set_preset(page, "custom", fit)
                for fmt, ext in (("webm", "webm"), ("mp4", "mp4")):
                    support = page.evaluate("""async () => {
                      const s = videoOutputSize();
                      await ensureExportSupport(s.w, s.h);
                      return {webm: state.exportSupport.webm, mp4: state.exportSupport.mp4,
                              reason: state.exportSupport.mp4Reason};
                    }""")
                    name = f"custom-640x360-{fit}-{fmt}"
                    if fmt == "mp4" and not support["mp4"]:
                        record("matrix", name, {
                            "ok": True, "skipped": "MP4 disabled with a visible reason",
                            "reason": support["reason"]})
                        continue
                    out = OUT / args.browser / f"{name}.{ext}"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        meta = export_one(page, fmt, out)
                        cell = probe_cell(out, fmt, 640, 360, 2.0, source["path"])
                        record("matrix", name, {"ok": cell["ok"], "file": meta, **cell})
                    except Exception as exc:  # noqa: BLE001
                        record("matrix", name, {"ok": False, "error": str(exc)})

        record("errors", f"{args.browser} source page", {"ok": not errors,
                                                        "errors": errors[:5]})
        b.close()

    if not only or "dist" in only:
        with Server(ROOT / "dist") as srv, sync_playwright() as p:
            b, page, errors = page_at(p, args.browser, srv.url + "/index.html", srv)
            spec = clip_specs()[0]
            vrf.load_video(page, spec["path"])
            vrf.set_effects(page, LIGHT)
            for fmt, ext, w, h in (("webm", "webm", 1280, 720),
                                   ("mp4", "mp4", 1280, 720)):
                name = f"dist-1280x720-{fmt}"
                out = OUT / args.browser / f"{name}.{ext}"
                out.parent.mkdir(parents=True, exist_ok=True)
                try:
                    meta = export_one(page, fmt, out)
                    cell = probe_cell(out, fmt, w, h, 2.0, spec["path"])
                    record("dist", name, {"ok": cell["ok"], "file": meta, **cell})
                except Exception as exc:  # noqa: BLE001
                    record("dist", name, {"ok": False, "error": str(exc)})
            record("errors", f"{args.browser} dist page", {"ok": not errors,
                                                          "errors": errors[:5]})
            b.close()

    path = EVIDENCE / f"matrix-{tag}.json"
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"{len(results)} cells, {len(problems)} failure(s) [{args.browser}]")
    print(f"evidence: {path}")
    for line in problems:
        print("FAIL", line)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
