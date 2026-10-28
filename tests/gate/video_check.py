#!/usr/bin/env python3
"""Part 1C acceptance (permanent gate check G13).

Measures, in real Chromium with real pointer/keyboard input:
  (a) the video Play/Pause control contract: presence per source type, 44px
      hit area, label/icon truth from `video.paused`, click/keyboard control,
      rapid toggles, a rejected play() promise, no listener/heap/loop growth;
  (b) lifecycle audit: hidden-tab resume, export preserves the paused state,
      no stale video element, no page/console errors across the real flow;
  (c) multi-effect playback cost: p95 render, long tasks, rendered frames,
      canvas allocations per frame, paused/idle regressions, and pixel identity
      between the pooled playback path and the cached still path.

usage:
  python tests/gate/video_check.py            # acceptance (gate)
  python tests/gate/video_check.py --baseline # numbers only, writes JSON
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_check as C  # noqa: E402

ROOT = C.ROOT
OUT = ROOT / "docs" / "evidence" / "part1c"
VIDEO = Path("/tmp/glyphcraft_gate_1280x720.webm")
VIDEO_SMALL = Path("/tmp/glyphcraft_test.webm")
FIXTURE_1080 = Path("/tmp/glyphcraft_gate_1920x1080.png")
FIXTURE_900 = Path("/tmp/glyphcraft_gate_fixture.png")
HEAVY = ["posterize", "edges", "sketch", "emboss", "blur", "sharpen"]

# Playback budget: 30 fps display with room for compositing. The governor in
# app.js targets 26 ms, so a healthy run converges under these. Measured after
# the 1C fixes at load 2-3: p50 20.9 ms, median-window p95 29.7 ms, 258 frames
# per 10 s, 0.0 canvas allocations per frame.
#
# Wall-clock numbers are joint bounds, not absolutes: each one is allowed to
# rise to the zero-effect control measured in the same session plus a margin
# (see the budget check). Identical code measured p95 26.5 ms in one run and
# 85 ms in another at an unchanged p50, and 0-effect playback on this desktop
# produces the same 50-130 ms tasks, so above the control's own floor the
# number describes the desktop, not the renderer. The absolute value is still
# the primary bound whenever the control is below it, and every run reports
# both. CPU per frame is absolute and is not affected by preemption.
PLAYBACK_P95_MS = 40.0
PLAYBACK_P50_MS = 26.0
PLAYBACK_LONG_TASK_MS = 400.0   # per 2 s window, median of five
PLAYBACK_LONGEST_MS = 120.0     # median window's worst single task
PLAYBACK_LONGEST_ANY_MS = 250.0 # worst single task in any window
# CPU spent running this page per presented frame. The pre-1C build was
# ~400 ms/frame, a calm desktop measures ~15-20 ms and the same build at load 5
# on 4 cores measures 27.6 ms. A doubling of the pipeline crosses it;
# scheduler noise does not.
PLAYBACK_SCRIPT_PER_FRAME_MS = 40.0
PLAYBACK_MIN_FRAMES = 50
CANVAS_PER_RENDER_MAX = 1.0

SET_EFFECTS = """(ids) => {
  state.opts.effects = state.opts.effects.map(fx => ({
    ...fx, enabled: ids.includes(fx.id),
    params: { ...effectDefaults(fx.id), ...(fx.params || {}) },
  }));
  scheduleRender(0);
}"""

EXTRA_JS = r"""
() => {
  window.__load = { raf: 0, timeouts: 0, intervals: 0, frames: 0 };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    window.__load.raf++;
    return raf((t) => { window.__load.frames++; return cb(t); });
  };
  const add = EventTarget.prototype.addEventListener;
  const rem = EventTarget.prototype.removeEventListener;
  window.__mediaListeners = [];
  const isMedia = (t) => t instanceof HTMLMediaElement;
  EventTarget.prototype.addEventListener = function (type, fn, opt) {
    if (isMedia(this)) {
      if (!window.__mediaListeners.some((l) => l.t === this && l.type === type && l.fn === fn)) {
        window.__mediaListeners.push({ t: this, type, fn });
      }
    }
    return add.call(this, type, fn, opt);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, opt) {
    if (isMedia(this)) {
      window.__mediaListeners = window.__mediaListeners.filter(
        (l) => !(l.t === this && l.type === type && l.fn === fn));
    }
    return rem.call(this, type, fn, opt);
  };
  window.__mediaListenerCount = function (el) {
    return window.__mediaListeners.filter((l) => !el || l.t === el).length;
  };
  window.__lt = [];
  new PerformanceObserver((l) => {
    for (const e of l.getEntries()) window.__lt.push({ d: e.duration, t: e.startTime });
  }).observe({ entryTypes: ['longtask'] });
  // Diagnostics: any render outside a measured flow is a bug, so keep a short
  // ring of who asked for it.
  window.__renderLog = [];
  const origRender = window.render;
  window.render = function (...a) {
    window.__renderLog.push({
      t: +performance.now().toFixed(0),
      src: state.sourceType,
      stack: String(new Error().stack).split("\n").slice(2, 5).join(" | "),
    });
    if (window.__renderLog.length > 30) window.__renderLog.shift();
    return origRender.apply(this, a);
  };
  // Who asked for a render that was coalesced into a later frame.
  window.__scheduleLog = [];
  const origSchedule = window.scheduleRender;
  window.scheduleRender = function (delay) {
    window.__scheduleLog.push({
      t: +performance.now().toFixed(0),
      delay: delay || 0,
      stack: String(new Error().stack).split("\n").slice(2, 7).join(" | "),
    });
    if (window.__scheduleLog.length > 30) window.__scheduleLog.shift();
    return origSchedule.apply(this, arguments);
  };
  window.__resetFlow = function () {
    Object.assign(window.__load, { raf: 0, timeouts: 0, intervals: 0, frames: 0 });
    __perf.longtasks = []; __perf.renders = 0; __perf.renderMs = [];
    __perf.pipeline = 0; __perf.canvasCreated = 0;
    window.__lt = []; window.__ltFrom = performance.now();
    window.__scaleLog = [];
  };
  // Which playback scale each measured frame actually used: a window that
  // still contains convergence frames is not a steady-state measurement.
  const scaledRender = window.render;
  window.render = function (...a) {
    if (window.__scaleLog && window.__scaleLog.length < 400) {
      window.__scaleLog.push(state.playback ? +state.playback.scale.toFixed(2) : null);
    }
    return scaledRender.apply(this, a);
  };
}
"""


def ensure_fixtures(problems: list[str]) -> None:
    if not FIXTURE_900.exists() or not FIXTURE_1080.exists():
        try:
            import run_gate
            run_gate.ensure_fixtures()
        except Exception as exc:  # pragma: no cover - fixture setup guard
            problems.append(f"fixture setup failed: {exc}")
            return
    if not FIXTURE_1080.exists():
        from PIL import Image
        Image.open(FIXTURE_900).convert("RGB").resize((1920, 1080)).save(FIXTURE_1080)
    if not VIDEO.exists():
        # 20 s, not 8: the playback measurement runs five 2 s windows plus a
        # 1.5 s convergence, and looping inside the measurement costs a decoder
        # restart in one window that has nothing to do with the app.
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "testsrc2=size=1280x720:rate=30:duration=20",
             "-c:v", "libvpx-vp9", "-b:v", "1500k", "-row-mt", "1",
             "-deadline", "realtime", "-cpu-used", "8", str(VIDEO)],
            capture_output=True, check=False,
        )
    if not VIDEO_SMALL.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2",
             "-c:v", "libvpx-vp9", "-b:v", "200k", str(VIDEO_SMALL)],
            capture_output=True, check=False,
        )


def metric(cdp) -> dict:
    names = ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration")
    m = {row["name"]: row["value"] for row in cdp.send("Performance.getMetrics")["metrics"]}
    return {n: round(m.get(n, 0.0), 4) for n in names}


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = min(len(xs) - 1, int(round((len(xs) - 1) * p)))
    return round(xs[k], 1)


def reset_flow(page):
    page.evaluate("() => window.__resetFlow()")


def flow(page, cdp, seconds, label=""):
    reset_flow(page)
    page.evaluate("() => { window.__ltFrom = performance.now(); }")
    before = metric(cdp)
    page.wait_for_timeout(seconds * 1000)
    after = metric(cdp)
    data = page.evaluate("""() => ({
      renders: __perf.renders, renderMs: __perf.renderMs.slice(),
      pipeline: __perf.pipeline, canvases: __perf.canvasCreated,
      raf: __load.raf, frames: __load.frames, timeouts: __load.timeouts,
      intervals: __load.intervals,
      longtasks: window.__lt.filter(e => e.t >= window.__ltFrom).map(e => e.d),
      videoTime: state.video ? +state.video.currentTime.toFixed(2) : null,
      paused: state.video ? state.video.paused : null,
      scale: state.playback ? state.playback.scale : null,
      backing: document.getElementById('canvas').width,
      scales: Array.from(new Set(window.__scaleLog || [])),
      scaleCounts: (window.__scaleLog || []).reduce((m, s) => (m[s] = (m[s] || 0) + 1, m), {}),
      mediaListeners: window.__mediaListenerCount(state.video),
    })""")
    data["longtask_ms"] = round(sum(data["longtasks"]), 1)
    data["longest_ms"] = round(max(data["longtasks"] + [0]), 1)
    data["task_ms"] = round((after["TaskDuration"] - before["TaskDuration"]) * 1000, 1)
    data["script_ms"] = round((after["ScriptDuration"] - before["ScriptDuration"]) * 1000, 1)
    data["layout_ms"] = round((after["LayoutDuration"] - before["LayoutDuration"]) * 1000, 1)
    data["style_ms"] = round((after["RecalcStyleDuration"] - before["RecalcStyleDuration"]) * 1000, 1)
    data["p50"] = pct(data["renderMs"], 0.5)
    data["p95"] = pct(data["renderMs"], 0.95)
    data["max"] = max(data["renderMs"] or [0])
    data["canvas_per_render"] = round(data["canvases"] / max(1, data["renders"]), 2)
    data["label"] = label
    return data


def load(page, path, settle=True):
    # `.canvas-area.has-content` is already set by the previous source, so the
    # only reliable signal that the new file is in is a new sourceId.
    before = page.evaluate("() => state.sourceId")
    page.evaluate("() => { document.getElementById('file-input').value = ''; }")
    page.set_input_files("#file-input", str(path))
    page.wait_for_function("(id) => state.sourceId > id", arg=before, timeout=90000)
    page.wait_for_selector(".canvas-area.has-content", timeout=90000)
    if settle:
        C.settle(page, quiet_ms=250, timeout_ms=40000)


def load_video(page, path=VIDEO, settle=False):
    # A freshly loaded video starts playing (muted autoplay), so the render
    # counter never goes quiet: never wait for settle here.
    load(page, path, settle=settle)
    page.wait_for_function("() => state.sourceType === 'video' && state.video && state.video.readyState >= 2",
                           timeout=60000)


def toggle_state(page):
    return page.evaluate("""() => {
      const b = document.getElementById('video-toggle');
      if (!b) return null;
      return {
        hidden: b.hidden || getComputedStyle(b).display === 'none',
        label: b.getAttribute('aria-label'),
        w: Math.round(b.getBoundingClientRect().width),
        h: Math.round(b.getBoundingClientRect().height),
        playing: !!state.video && !state.video.paused && !state.video.ended,
        name: b.textContent.trim(),
      };
    }""")


def visibility(page, hidden):
    page.evaluate(
        """(hidden) => {
          try {
            Object.defineProperty(document, 'visibilityState', {
              configurable: true, get: () => hidden ? 'hidden' : 'visible',
            });
            Object.defineProperty(document, 'hidden', {
              configurable: true, get: () => hidden,
            });
          } catch (e) {}
          document.dispatchEvent(new Event('visibilitychange'));
        }""",
        hidden,
    )
    page.wait_for_timeout(300)


def heap(cdp):
    cdp.send("HeapProfiler.collectGarbage")
    return cdp.send("Runtime.getHeapUsage")["usedSize"]


def hash_frame(page):
    return page.evaluate("() => window.__hashCanvas(document.getElementById('canvas'))")


def main() -> int:
    baseline = "--baseline" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[tuple] = []
    problems: list[str] = []
    ensure_fixtures(problems)

    def record(name, detail, ok):
        rows.append((name, detail, ok))
        print(("PASS " if ok else "FAIL ") + name + " - " + detail)
        if not ok and not baseline:
            problems.append(f"{name}: {detail}")

    with C.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        ctx.add_init_script(C.INIT_JS)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
        page.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" else None)
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(400)
        page.evaluate(C.PATCH_JS)
        page.evaluate(EXTRA_JS)
        page.evaluate("""() => {
          window.__hashCanvas = function (c) {
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let h = 2166136261;
            for (let i = 0; i < d.length; i += 4) {
              h ^= d[i]; h = Math.imul(h, 16777619);
              h ^= d[i + 1]; h = Math.imul(h, 16777619);
              h ^= d[i + 2]; h = Math.imul(h, 16777619);
              h ^= d[i + 3]; h = Math.imul(h, 16777619);
            }
            return h >>> 0;
          };
        }""")
        cdp = ctx.new_cdp_session(page)
        cdp.send("Performance.enable")
        data = {"control": {}, "audit": {}, "playback": {}, "idle": {}, "identity": {}}

        # ---------------------------------------------------------------- (a)
        # Empty state: the control exists but must be hidden (no source).
        t = toggle_state(page)
        record("empty state hides the video control",
               f"hidden={t and t['hidden']} size={t and t['w']}x{t and t['h']}",
               t is not None and t["hidden"] and t["w"] == 0)
        data["control"]["empty"] = t

        # Image: no control.
        load(page, FIXTURE_1080)
        page.evaluate(SET_EFFECTS, HEAVY)
        C.settle(page)
        t = toggle_state(page)
        record("image source hides video control",
               f"hidden={t and t['hidden']}", t is not None and t["hidden"])
        data["control"]["image"] = t

        # Video: visible, 44px, labelled.
        load_video(page)
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(250)
        t = toggle_state(page)
        ok = (t is not None and not t["hidden"] and t["w"] >= 44 and t["h"] >= 44
              and t["label"] and not t["playing"] and "play" in (t["label"] or "").lower())
        record("video shows a 48px play control",
               f"hidden={t and t['hidden']} size={t and t['w']}x{t and t['h']} "
               f"label={t and t['label']!r} playing={t and t['playing']}", ok)
        data["control"]["video"] = t

        # Click toggles the real element and the label follows it.
        page.click("#video-toggle")
        page.wait_for_function("() => !state.video.paused", timeout=5000)
        page.wait_for_timeout(300)
        t1 = toggle_state(page)
        page.click("#video-toggle")
        page.wait_for_function("() => state.video.paused", timeout=5000)
        page.wait_for_timeout(300)
        t2 = toggle_state(page)
        record("click controls play and pause; label follows state",
               f"after play: playing={t1['playing']} label={t1['label']!r}; "
               f"after pause: playing={t2['playing']} label={t2['label']!r}",
               t1["playing"] and not t2["playing"]
               and "pause" in (t1["label"] or "").lower()
               and "play" in (t2["label"] or "").lower())
        data["control"]["click"] = {"play": t1, "pause": t2}

        # Label follows a programmatic pause/play (e.g. export, external code).
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(400)
        prog_play = toggle_state(page)
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(400)
        prog_pause = toggle_state(page)
        record("label follows programmatic play/pause",
               f"play={prog_play['label']!r}/{prog_play['playing']} "
               f"pause={prog_pause['label']!r}/{prog_pause['playing']}",
               prog_play["playing"] and not prog_pause["playing"]
               and "pause" in (prog_play["label"] or "").lower()
               and "play" in (prog_pause["label"] or "").lower())
        data["control"]["programmatic"] = {"play": prog_play, "pause": prog_pause}

        # Keyboard: focus the control, Space must activate it and must NOT pan.
        page.focus("#video-toggle")
        page.keyboard.press("Space")
        page.wait_for_function("() => !state.video.paused", timeout=5000)
        page.wait_for_timeout(250)
        kb = page.evaluate("""() => ({
          playing: !state.video.paused,
          cursor: document.getElementById('canvas-area').style.cursor,
          spaceDown: !!state.spaceDown,
          label: document.getElementById('video-toggle').getAttribute('aria-label'),
        })""")
        page.keyboard.press("Space")
        page.wait_for_function("() => state.video.paused", timeout=5000)
        page.wait_for_timeout(200)
        kb2 = page.evaluate("""() => ({
          playing: !state.video.paused,
          cursor: document.getElementById('canvas-area').style.cursor,
          spaceDown: !!state.spaceDown,
        })""")
        record("Space on the focused control toggles without panning",
               f"first={kb} second={kb2}",
               kb["playing"] and not kb["spaceDown"] and kb["cursor"] == "" and not kb2["playing"])
        data["control"]["keyboard"] = {"play": kb, "pause": kb2}

        # A focused control owns its keys: a letter shortcut must not fire from
        # underneath the button the user is about to activate.
        page.focus("#video-toggle")
        theme_before = page.evaluate("() => document.documentElement.dataset.theme")
        page.keyboard.press("KeyT")
        page.wait_for_timeout(250)
        theme_after = page.evaluate("() => document.documentElement.dataset.theme")
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.keyboard.press("KeyT")
        page.wait_for_timeout(250)
        theme_blurred = page.evaluate("() => document.documentElement.dataset.theme")
        record("letter shortcuts stay off a focused control",
               f"before={theme_before} onControl={theme_after} blurred={theme_blurred}",
               theme_after == theme_before and theme_blurred != theme_before)
        data["control"]["shortcut"] = {"before": theme_before, "onControl": theme_after,
                                       "blurred": theme_blurred}
        # Leave the flow in the theme it started in.
        page.keyboard.press("KeyT")
        page.wait_for_timeout(200)

        # Rapid double clicks: no stuck half state, no second loop.
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(250)
        for _ in range(6):
            page.click("#video-toggle", delay=10)
            page.wait_for_timeout(30)
        page.wait_for_timeout(700)
        rapid = page.evaluate("""() => ({
          paused: state.video.paused,
          label: document.getElementById('video-toggle').getAttribute('aria-label'),
          playingLabel: document.getElementById('video-toggle').dataset.playing,
        })""")
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(300)
        rapid2 = toggle_state(page)
        record("six rapid clicks settle in the true state",
               f"mid={rapid} after-pause label={rapid2['label']!r} playing={rapid2['playing']}",
               (rapid["paused"] and "play" in (rapid["label"] or "").lower())
               or (not rapid["paused"] and "pause" in (rapid["label"] or "").lower())
               and not rapid2["playing"])
        data["control"]["rapid"] = rapid

        # Rejected play(): caught, true state, no unhandled rejection.
        page.evaluate("""() => {
          const v = state.video;
          v.__origPlay = v.play.bind(v);
          v.play = () => Promise.reject(new DOMException('interrupted', 'AbortError'));
          window.__rejection = null;
          window.addEventListener('unhandledrejection', (e) => { window.__rejection = String(e.reason); });
        }""")
        errors_before = len(errors)
        page.click("#video-toggle")
        page.wait_for_timeout(600)
        rejected = page.evaluate("""() => ({
          paused: state.video.paused,
          label: document.getElementById('video-toggle').getAttribute('aria-label'),
          rejection: window.__rejection,
        })""")
        page.evaluate("() => { state.video.play = state.video.__origPlay; delete state.video.__origPlay; }")
        record("rejected play() leaves the control truthful",
               f"paused={rejected['paused']} label={rejected['label']!r} "
               f"unhandled={rejected['rejection']!r} newErrors={len(errors)-errors_before}",
               rejected["paused"] and "play" in (rejected["label"] or "").lower()
               and rejected["rejection"] is None and len(errors) == errors_before)
        data["control"]["rejected"] = rejected

        # 50 toggles: heap, listeners, one loop.
        cdp.send("HeapProfiler.collectGarbage")
        h0 = heap(cdp)
        l0 = page.evaluate("() => window.__mediaListenerCount(state.video)")
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(250)
        for i in range(50):
            page.click("#video-toggle", delay=0)
            page.wait_for_timeout(18)
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(700)
        h1 = heap(cdp)
        l1 = page.evaluate("() => window.__mediaListenerCount(state.video)")
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(300)
        loops = flow(page, cdp, 1.0, "loop check")
        growth = (h1 - h0) / max(1, h0) * 100
        record("50 toggles: no heap/listener/loop growth",
               f"heap {h0/1e6:.1f}->{h1/1e6:.1f}MB ({growth:+.1f}%), "
               f"listeners {l0}->{l1}, raf/s={loops['raf']}, renders/s={loops['renders']}",
               growth <= 15 and l1 == l0 and loops["raf"] <= 45 and loops["renders"] <= 45)
        data["control"]["toggles"] = {"heap0": h0, "heap1": h1, "pct": round(growth, 2),
                                      "listeners": [l0, l1], "loop": loops}

        # ---------------------------------------------------------------- (b)
        # Hidden tab during playback must resume when visible again.
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(300)
        load_video(page)
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(500)
        visibility(page, True)
        page.wait_for_timeout(900)
        visibility(page, False)
        page.wait_for_timeout(300)
        resumed = flow(page, cdp, 2.0, "resume")
        record("visible tab resumes the play loop",
               f"renders={resumed['renders']} raf={resumed['raf']} "
               f"videoTime={resumed['videoTime']}",
               # The loop rides requestVideoFrameCallback, so rAF stays at 0 by
               # design; what proves resumption is fresh rendered frames.
               resumed["renders"] >= 4)
        data["audit"]["resume"] = resumed
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(300)

        # Export must preserve the paused state.
        load_video(page, VIDEO_SMALL)
        page.evaluate("""() => {
          state.video.pause();
          state.opts.exportFormat = 'webm';
          state.opts.outputPreset = 'custom';
          state.opts.outputWidth = 160;
          state.opts.outputHeight = 120;
          scheduleRender(0);
        }""")
        page.wait_for_timeout(500)
        was_paused = page.evaluate("() => state.video.paused")
        t_before = toggle_state(page)
        page.click("#btn-export")
        page.wait_for_function("() => state.videoExporting === true", timeout=10000)
        page.wait_for_function("() => state.videoExporting === false", timeout=180000)
        page.wait_for_timeout(800)
        after = page.evaluate("""() => ({
          paused: state.video.paused,
          label: document.getElementById('video-toggle').getAttribute('aria-label'),
        })""")
        record("export preserves a paused video and its control",
               f"was_paused={was_paused} label_before={t_before['label']!r} "
               f"paused_after={after['paused']} label_after={after['label']!r}",
               was_paused and after["paused"] and "play" in (after["label"] or "").lower())
        data["audit"]["export"] = {"was_paused": was_paused, "after": after}

        # Replacing the video must not leak listeners or keep an old element live.
        l_first = page.evaluate("() => ({count: window.__mediaListenerCount(state.video), id: state.video.__id || 0})")
        ids = []
        for _ in range(3):
            load_video(page)
            page.evaluate("() => { if (!state.video.__id) state.video.__id = (window.__vidSeq = (window.__vidSeq || 0) + 1); }")
            ids.append(page.evaluate("() => state.video.__id"))
            page.evaluate("() => { state.video.pause(); }")
            page.wait_for_timeout(200)
        stale = page.evaluate("""() => ({
          listeners: window.__mediaListenerCount(state.video),
          total: window.__mediaListeners.length,
          videos: window.__mediaListeners.reduce((n, l) => n + (l.t === state.video ? 1 : 0), 0),
        })""")
        record("replacing the source keeps one listener set",
               f"first={l_first['count']} last={stale['listeners']} ids={ids} "
               f"totalTracked={stale['total']}",
               stale["listeners"] == l_first["count"] and len(set(ids)) == 3)
        data["audit"]["replace"] = {"first": l_first, "last": stale, "ids": ids}

        # ---------------------------------------------------------------- (c)
        # Playback cost: six stacked effects on a 1280x720 video.
        load_video(page)
        # The export check above leaves the output preset at 160x120. Measuring
        # playback there would prove nothing, so restore the native preset and
        # assert the backing store really is the full preview size.
        page.evaluate("""() => {
          state.opts.outputPreset = 'original';
          state.opts.outputWidth = 0;
          state.opts.outputHeight = 0;
        }""")
        full_w = page.evaluate("""() => computeOutputSize(state.sourceW, state.sourceH,
          state.opts.outputPreset, state.opts.outputWidth, state.opts.outputHeight,
          state.opts.outputFit).w""")
        page.evaluate(SET_EFFECTS, HEAVY)
        duration = page.evaluate("() => state.video.duration")
        # The measurement is ten seconds of playback plus convergence; a cached
        # 8 s fixture would loop inside it and blame the decoder restart on the
        # app.
        record("playback fixture outlasts the measurement",
               f"duration={duration}s", duration >= 14)
        # The governor shrinks the backing store, so the CSS transform has to
        # grow to compensate. A preview that stays the same size on screen while
        # its pixels get cheaper is the whole point; a preview that collapses to
        # a thumbnail is not a performance fix.
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(600)
        box_js = """() => {
          const c = document.getElementById('canvas');
          const r = c.getBoundingClientRect();
          return { w: +r.width.toFixed(1), h: +r.height.toFixed(1),
                   backing: c.width, scale: +state.scale.toFixed(3) };
        }"""
        paused_box = page.evaluate(box_js)
        page.evaluate("() => { state.video.play().catch(() => {}); }")
        page.wait_for_timeout(1500)  # let the governor converge
        play_box = page.evaluate(box_js)
        size_err = max(abs(play_box["w"] / paused_box["w"] - 1),
                       abs(play_box["h"] / paused_box["h"] - 1))
        record("the preview keeps its on-screen size while playing",
               f"paused={paused_box} playing={play_box} boxErr={size_err * 100:.2f}%",
               play_box["backing"] < full_w and size_err <= 0.01)
        data["playback"]["box"] = {"paused": paused_box, "playing": play_box,
                                   "err": round(size_err, 4)}
        # Five short windows instead of one long one. A desktop at load 2.5-3
        # preempts the renderer in bursts: identical code measured p95 26.5 in
        # one run and 67.5 in another, and a 2 s window can be entirely inside a
        # stall (long-task totals 452/550/0 over three consecutive windows at an
        # unchanged p50). The median window is the sustained cost; a real
        # regression raises every window. The video loops, so 10 s is safe.
        windows = [flow(page, cdp, 2.0, f"heavy6-{i}") for i in range(5)]

        def summarize(windows):
            p95s = sorted(w["p95"] for w in windows)
            out = {
                "renders": sum(w["renders"] for w in windows),
                "canvases": sum(w["canvases"] for w in windows),
                "longtask_ms": sorted(w["longtask_ms"] for w in windows)[2],
                "longtask_total_ms": round(sum(w["longtask_ms"] for w in windows), 1),
                "windowLongtask": [w["longtask_ms"] for w in windows],
                "longest_ms": sorted(w["longest_ms"] for w in windows)[2],
                "longest_any_ms": max(w["longest_ms"] for w in windows),
                "windowLongest": [w["longest_ms"] for w in windows],
                "task_ms": round(sum(w["task_ms"] for w in windows), 1),
                "script_ms": round(sum(w["script_ms"] for w in windows), 1),
                "p50": pct([m for w in windows for m in w["renderMs"]], 0.5),
                "p95": p95s[len(p95s) // 2],
                "max": max(w["max"] for w in windows),
                "videoTime": windows[-1]["videoTime"],
                "scale": windows[-1]["scale"],
                "backing": windows[-1]["backing"],
                "scaleCounts": windows[-1]["scaleCounts"],
                "windowP95": p95s,
                "windowP50": [w["p50"] for w in windows],
            }
            out["canvas_per_render"] = round(out["canvases"] / max(1, out["renders"]), 2)
            out["script_per_frame"] = round(out["script_ms"] / max(1, out["renders"]), 2)
            return out

        play = summarize(windows)

        # Same page, same session, same governor, zero effects. This is the
        # ambient floor of the desktop, not of the app: measured here it shows
        # 50-130 ms long tasks and p95 up to 69 ms with nothing applied, at the
        # same time as the six-effect run. The budget below therefore judges the
        # heavy stack *against this control* when the control is also over the
        # absolute number; the absolute numbers stay in the message either way,
        # and CPU per frame (script time) is still an absolute check.
        page.evaluate(SET_EFFECTS, [])
        page.wait_for_timeout(1500)  # let the governor converge for this stack
        ctrl = summarize([flow(page, cdp, 2.0, f"control0-{i}") for i in range(5)])
        page.evaluate(SET_EFFECTS, HEAVY)
        data["playback"]["control0"] = ctrl
        record("a zero-effect control is measured in the same session",
               f"p50={ctrl['p50']}ms p95(median)={ctrl['p95']}ms "
               f"longest={ctrl['longest_ms']}ms/any {ctrl['longest_any_ms']}ms "
               f"script/frame={ctrl['script_per_frame']}ms backing={ctrl['backing']}",
               ctrl["renders"] >= PLAYBACK_MIN_FRAMES)
        record("playback cost is measured at full output size",
               f"full={full_w} backing={play['backing']} scale={play['scale']}",
               full_w >= 1000 and play["backing"] >= 150)

        # A bound is the absolute budget, or the control plus a margin when the
        # control itself is over: identical code measured p95 26.5 one run and
        # 85 the next at an unchanged p50, with 0-effect playback producing the
        # same 50-130 ms tasks. Pre-1C the stack cost 443 ms/frame and 4635 ms
        # of long tasks, i.e. an order of magnitude over any of these margins.
        limit_p50 = max(PLAYBACK_P50_MS, (ctrl["p50"] or 0) + 6)
        limit_p95 = max(PLAYBACK_P95_MS, (ctrl["p95"] or 0) + 10)
        limit_long = max(PLAYBACK_LONG_TASK_MS, (ctrl["longtask_ms"] or 0) + 200)
        limit_longest = max(PLAYBACK_LONGEST_MS, (ctrl["longest_ms"] or 0) + 40)
        limit_any = max(PLAYBACK_LONGEST_ANY_MS, (ctrl["longest_any_ms"] or 0) + 150)
        record("playback 6 effects stays under budget",
               f"renders={play['renders']} p50={play['p50']}ms(limit {limit_p50}) "
               f"p95(median)={play['p95']}ms(limit {limit_p95}) "
               f"windows={play['windowP95']} windowP50={play['windowP50']} "
               f"max={play['max']}ms longtask(median)={play['longtask_ms']}ms(limit {limit_long}) "
               f"windows={play['windowLongtask']} total={play['longtask_total_ms']}ms "
               f"script/frame={play['script_per_frame']}ms "
               f"longest(median)={play['longest_ms']}ms(limit {limit_longest}) "
               f"any={play['longest_any_ms']}ms(limit {limit_any}) "
               f"windows={play['windowLongest']} task={play['task_ms']}ms "
               f"videoTime={play['videoTime']} scale={play['scale']} backing={play['backing']} "
               f"scales={play['scaleCounts']} "
               f"| control: p50={ctrl['p50']} p95={ctrl['p95']} "
               f"longtask={ctrl['longtask_ms']} longest={ctrl['longest_ms']}/{ctrl['longest_any_ms']} "
               f"script/frame={ctrl['script_per_frame']} backing={ctrl['backing']}",
               play["renders"] >= PLAYBACK_MIN_FRAMES
               # The median frame is what "smooth" means; if the sustained
               # frame time is over budget the p95 does not matter.
               and play["p50"] <= limit_p50
               and play["p95"] <= limit_p95
               and play["longtask_ms"] <= limit_long
               and play["longest_ms"] <= limit_longest
               and play["longest_any_ms"] <= limit_any
               # 80% of wall time over the ten measured seconds.
               and play["task_ms"] < 8000)
        data["playback"]["heavy6"] = play
        data["playback"]["limits"] = {"p50": limit_p50, "p95": limit_p95,
                                       "longtask": limit_long, "longest": limit_longest,
                                       "any": limit_any}

        # Wall-clock percentiles move with whatever else the desktop is doing
        # (load 5 on 4 cores moved p95 from 29 to 85 ms at an unchanged p50 of
        # 18-20 ms). Script time per frame is CPU actually spent running this
        # page and does not count preemption, so it is the regression signal.
        record("playback CPU per frame stays inside the budget",
               f"script/frame={play['script_per_frame']}ms renders={play['renders']}",
               play["script_per_frame"] <= PLAYBACK_SCRIPT_PER_FRAME_MS)

        record("playback allocates at most one canvas per frame",
               f"canvases={play['canvases']} renders={play['renders']} "
               f"per_render={play['canvas_per_render']}",
               play["canvas_per_render"] <= CANVAS_PER_RENDER_MAX)
        data["playback"]["alloc"] = {"canvases": play["canvases"], "per_render": play["canvas_per_render"]}

        # Paused video with the same stack: true idle.
        page.evaluate("() => { state.video.pause(); }")
        page.wait_for_timeout(600)
        paused = flow(page, cdp, 3.0, "paused heavy6")
        record("paused video with 6 effects is idle",
               f"raf={paused['raf']} renders={paused['renders']} timeouts={paused['timeouts']} "
               f"longtask={paused['longtask_ms']}ms",
               paused["raf"] == 0 and paused["renders"] == 0 and paused["timeouts"] == 0)
        data["idle"]["paused"] = paused

        # Paused frame must be full quality again (playback scale reset).
        quality = page.evaluate("""() => {
          const full = computeOutputSize(state.sourceW, state.sourceH, state.opts.outputPreset,
            state.opts.outputWidth, state.opts.outputHeight, state.opts.outputFit);
          const pv = previewSize(full);
          return { canvasW: document.getElementById('canvas').width, previewW: pv.w };
        }""")
        record("paused video renders at full preview resolution",
               f"canvas={quality['canvasW']} preview={quality['previewW']}",
               quality["canvasW"] == quality["previewW"])
        data["idle"]["quality"] = quality

        # Image with the same stack: idle must stay at zero work (H4).
        load(page, FIXTURE_1080)
        page.evaluate(SET_EFFECTS, HEAVY)
        C.settle(page)
        idle = flow(page, cdp, 3.0, "image idle")
        stray = page.evaluate("""() => ({
          renders: window.__renderLog.filter(e => e.t >= window.__ltFrom).slice(-3),
          scheduled: window.__scheduleLog.filter(e => e.t >= window.__ltFrom - 400).slice(-4),
        })""")
        record("image with 6 effects is idle",
               f"raf={idle['raf']} renders={idle['renders']} timeouts={idle['timeouts']}"
               + (f" stray={stray}" if idle["renders"] else ""),
               idle["raf"] == 0 and idle["renders"] == 0 and idle["timeouts"] == 0)
        data["idle"]["image"] = idle

        # Pixel identity: pooled (cache-disabled) vs cached still path.
        page.evaluate("() => { window.__resetCaches && window.__resetCaches(); }")
        page.evaluate("() => { state.cacheDisabled = false; render(); }")
        h_cached = hash_frame(page)
        page.evaluate("() => { state.cacheDisabled = true; render(); }")
        h_pooled = hash_frame(page)
        page.evaluate("() => { state.cacheDisabled = false; render(); }")
        record("pooled path is pixel-identical to the cached path",
               f"cached={h_cached} pooled={h_pooled}",
               h_cached == h_pooled and h_cached != 0)
        data["identity"] = {"cached": h_cached, "pooled": h_pooled}

        record("no page or console errors in the whole flow",
               f"{len(errors)} error(s): {errors[:6]}", not errors)
        data["errors"] = errors

    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    Path("/tmp/opencode/part1c_result.json").write_text(json.dumps(
        {"checks": [{"name": n, "detail": d, "ok": o} for n, d, o in rows], "data": data}, indent=2))
    if problems:
        print("VIDEO FAIL")
        return 1
    print("VIDEO PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
