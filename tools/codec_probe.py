#!/usr/bin/env python3
"""Report which WebCodecs codecs and sizes each browser can encode.

Read-only probe: it configures no encoder output and downloads nothing. Writes
docs/evidence/v2/codec-support.json and prints a table.

Usage:
  python tools/codec_probe.py
"""
from __future__ import annotations

import functools
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "v2" / "codec-support.json"

VIDEO = ["avc1.640028", "avc1.4d0028", "avc1.42E01E", "vp09.00.10.08", "vp8"]
AUDIO = ["mp4a.40.2", "opus"]
SIZES = [(1280, 720), (1920, 1080), (3840, 2160)]

JS = """async (spec) => {
  const out = {video: {}, audio: {}, webcodecs: typeof VideoEncoder !== 'undefined'};
  if (!out.webcodecs) return out;
  for (const [w, h] of spec.sizes) {
    out.video[w + 'x' + h] = {};
    for (const codec of spec.video) {
      try {
        const r = await VideoEncoder.isConfigSupported({codec, width: w, height: h,
          bitrate: 6000000, framerate: 30});
        out.video[w + 'x' + h][codec] = !!(r && r.supported);
      } catch (err) {
        out.video[w + 'x' + h][codec] = 'error: ' + err.name;
      }
    }
  }
  for (const codec of spec.audio) {
    try {
      const r = await AudioEncoder.isConfigSupported({codec, sampleRate: 48000,
        numberOfChannels: 2, bitrate: 128000});
      out.audio[codec] = !!(r && r.supported);
    } catch (err) {
      out.audio[codec] = 'error: ' + err.name;
    }
  }
  return out;
}"""


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


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict] = {}
    with Server() as srv, sync_playwright() as p:
        for name in ("firefox", "chromium"):
            browser = getattr(p, name).launch(headless=True)
            page = browser.new_page()
            page.goto(srv.url + "/index.html", wait_until="load")
            data = page.evaluate(JS, {"sizes": SIZES, "video": VIDEO, "audio": AUDIO})
            data["user_agent"] = page.evaluate("() => navigator.userAgent")
            report[name] = data
            browser.close()
    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")

    for name, data in report.items():
        print(name, "WebCodecs:", data["webcodecs"])
        for size, codecs in data["video"].items():
            print(" ", size, {k: v for k, v in codecs.items() if v is True},
                  "unsupported:", [k for k, v in codecs.items() if v is not True])
        print("  audio", data["audio"])
    print("evidence:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
