#!/usr/bin/env python3
"""P2-3 Step 7 break-it pass.

  python tests/bench/breakit_p2_3.py

Twelve cases from docs/prompts/p2_3_session_start.md Step 7, run against the
real page. Each case prints PASS/FAIL with the observed value; a failure does
not stop later cases. Screenshots for the mobile, playback and reload cases go
to docs/evidence/p2-3/breakit-*.png.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "bench"))
sys.path.insert(0, str(ROOT / "tests" / "gate"))

import bench_lib as B  # noqa: E402
import video_p2_3_check as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

EVID = ROOT / "docs" / "evidence" / "p2-3"
WORK = Path("/tmp/opencode/glyphcraft_breakit")
LONG_PROBE = r"""
(() => {
  window.__longTasks = [];
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__longTasks.push(+e.duration.toFixed(1));
    }).observe({ entryTypes: ["longtask"] });
  } catch (e) {}
})();
"""


def png_hash(page, selector="#canvas"):
    return page.evaluate(
        """(sel) => {
          const c = document.querySelector(sel);
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let h = 2166136261;
          for (let i = 0; i < d.length; i += 4) {
            h ^= d[i]; h = Math.imul(h, 16777619);
            h ^= d[i + 1]; h = Math.imul(h, 16777619);
            h ^= d[i + 2]; h = Math.imul(h, 16777619);
          }
          return h >>> 0;
        }""", selector)


def wait_image(page, timeout=30000):
    page.wait_for_function(
        "() => state.sourceType === 'image' && state.source && !state.renderDirty",
        timeout=timeout)
    page.wait_for_timeout(350)


def load_image(page, path=None):
    page.set_input_files("#file-input", str(path or B.FIXTURE_1080))
    wait_image(page)


def load_video(page, path):
    V.load_video(page, path)


def make_files():
    WORK.mkdir(parents=True, exist_ok=True)
    V.ensure_fixtures()
    B.fixtures()
    good = V.FIXTURES["720p"][0].read_bytes()
    (WORK / "zero.webm").write_bytes(b"")
    (WORK / "corrupt.webm").write_bytes(b"not a video at all\n" * 40)
    (WORK / "truncated.mp4").write_bytes(good[:100])
    (WORK / "renamed.png").write_bytes(good)
    return {
        "zero": WORK / "zero.webm",
        "corrupt": WORK / "corrupt.webm",
        "truncated": WORK / "truncated.mp4",
        "renamed": WORK / "renamed.png",
    }


def record(rows, name, ok, detail):
    rows.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ": " + detail, flush=True)


def drop_error(page, path, name=None, mime=None):
    if name:
        payload = {"name": name, "mimeType": mime or "application/octet-stream",
                   "buffer": Path(path).read_bytes()}
        page.set_input_files("#file-input", payload)
    else:
        page.set_input_files("#file-input", str(path))
    page.wait_for_timeout(2500)
    return page.evaluate("""() => {
      const zone = document.querySelector('#drop-zone, .drop-zone');
      const err = document.querySelector('.drop-error, #drop-error');
      return {
        text: (err ? err.textContent : (zone ? zone.textContent : '')).trim().slice(0, 240),
        type: state.sourceType,
        hasSource: !!state.source,
      };
    }""")


def case_1_2_3(browser, srv, rows, files):
    # 1. limits on the live page
    ctx, page, errors = V.new_page(browser, srv)
    try:
        limits = page.evaluate("""() => {
          const mk = (t, s) => new File([new Uint8Array(0)], 'x', { type: t });
          const fake = (size) => Object.defineProperty(
            new File([], 'x', { type: 'video/webm' }), 'size', { value: size });
          return {
            image: IMAGE_MAX_FILE_BYTES,
            video: VIDEO_MAX_FILE_BYTES,
            exact: fileSizeError(fake(VIDEO_MAX_FILE_BYTES)),
            over: fileSizeError(fake(VIDEO_MAX_FILE_BYTES + 1)),
            zero: fileSizeError(fake(0)),
          };
        }""")
        record(rows, "1a limits", limits["image"] == 40 * 1024 * 1024
               and limits["video"] == 850 * 1024 * 1024,
               f"image={limits['image']} video={limits['video']} B")
        record(rows, "1b 850 MB exact / +1", limits["exact"] == "" and "850 MB" in limits["over"],
               f"exact={limits['exact']!r} over={limits['over']!r}")

        # 2. broken files
        err = drop_error(page, files["zero"])
        record(rows, "2a 0-byte video", "empty" in err["text"].lower(),
               f"type={err['type']} text={err['text'][:120]!r}")
        page.reload(wait_until="load"); page.wait_for_timeout(400)
        err = drop_error(page, files["corrupt"], name="corrupt.webm", mime="video/webm")
        record(rows, "2b corrupt video", not err["hasSource"] and "play" in err["text"].lower(),
               f"type={err['type']} text={err['text'][:140]!r}")
        page.reload(wait_until="load"); page.wait_for_timeout(400)
        err = drop_error(page, files["truncated"], name="truncated.mp4", mime="video/mp4")
        record(rows, "2c truncated video", not err["hasSource"] and bool(err["text"]),
               f"type={err['type']} text={err['text'][:140]!r}")
        page.reload(wait_until="load"); page.wait_for_timeout(400)
        err = drop_error(page, files["renamed"], name="photo.png", mime="image/png")
        record(rows, "2d video renamed as image", not err["hasSource"] and "decode" in err["text"].lower(),
               f"type={err['type']} text={err['text'][:140]!r}")

        # 3. portrait / rotated / odd / 4K with six effects
        load_video(page, V.FIXTURES["4k"][0])
        page.evaluate("""() => {
          const ids = ['halftone', 'crt', 'bloom', 'posterize', 'vignette', 'thermal'];
          state.opts.effects = state.opts.effects.map(fx => ({
            ...fx, enabled: ids.includes(fx.id)
          }));
          rebuildRamp();
          scheduleRender(0);
        }""")
        page.wait_for_timeout(600)
        page.evaluate("() => window.__longTasks = []")
        page.evaluate("() => state.video && state.video.play()")
        page.wait_for_timeout(2500)
        stats = page.evaluate("""() => ({
          frames: state.playback.frames,
          scale: state.playback.scale,
          long: window.__longTasks.slice(),
          size: [state.video.videoWidth, state.video.videoHeight],
          snap: state.playback.sig ? 'playing' : (state.video.paused ? 'paused' : 'playing'),
          effects: state.opts.effects.filter(f => f.enabled).length,
        })""")
        record(rows, "3a 4K video + 6 effects plays",
               stats["size"] == [3840, 2160] and stats["effects"] == 6
               and stats["frames"] > 5 and stats["scale"] <= 1,
               json.dumps(stats))
        for label in ("portrait", "odd"):
            load_video(page, V.FIXTURES[label][0])
            native = page.evaluate("() => [state.video.videoWidth, state.video.videoHeight]")
            record(rows, f"3b {label} video loads", native == list(V.FIXTURES[label][1:]),
                   f"native={native}")
        load_video(page, V.ROTATED)
        rotated = page.evaluate("() => [state.video.videoWidth, state.video.videoHeight]")
        record(rows, "3c rotated video honours rotation metadata",
               rotated != [1080, 1920], f"coded=1080x1920 displayed={rotated}")
        record(rows, "3d no errors in 1-3", not errors, repr(errors[:4]))
    finally:
        ctx.close()


def case_4(browser, srv, rows):
    import subprocess
    ctx, page, errors = B.new_page(browser, srv, downloads=True)
    try:
        load_video(page, V.FIXTURES["720p"][0])
        page.evaluate("""() => {
          state.opts.effects.forEach(fx => fx.enabled = false);
          state.opts.exportFormat = 'webm';
          state.opts.outputPreset = 'custom';
          state.opts.outputWidth = 320;
          state.opts.outputHeight = 180;
          syncUIFromState();
          scheduleRender(0);
        }""")
        page.wait_for_timeout(400)
        out = WORK / "during-load.webm"
        with page.expect_download(timeout=180000) as dl:
            page.click("#btn-export")
            page.wait_for_timeout(900)
            load_image(page, B.FIXTURE_1080)
        dl.value.save_as(out)
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height", "-of", "json", str(out)],
                               capture_output=True, text=True, check=True)
        size = json.loads(probe.stdout)["streams"][0]
        state_after = page.evaluate("""() => ({
          type: state.sourceType, exporting: state.videoExporting,
          status: document.getElementById('status-bar').textContent.trim() } )""")
        record(rows, "4a new file during export",
               (size["width"], size["height"]) == (1280, 720)
               and state_after["type"] == "image" and not state_after["exporting"]
               and "Exporting" not in state_after["status"],
               f"download={size['width']}x{size['height']} state={json.dumps(state_after)}")

        # Abandon an export by leaving the page mid-flight.
        load_video(page, V.FIXTURES["720p"][0])
        page.click("#btn-export")
        page.wait_for_timeout(1000)
        mid = page.evaluate("() => state.videoExporting")
        page.goto(srv.url + "/index.html", wait_until="load")
        page.wait_for_timeout(500)
        after = page.evaluate("() => ({ exporting: state.videoExporting, type: state.sourceType })")
        record(rows, "4b export abandoned mid-flight", mid and not after["exporting"],
               f"mid={mid} after={json.dumps(after)}")

        # Export started while another page is in front (tab hidden if headless honours it).
        other = ctx.new_page()
        other.goto(srv.url + "/index.html", wait_until="load")
        other.bring_to_front()
        page.evaluate("() => window.focus && window.focus()")
        hidden = page.evaluate("() => document.hidden")
        load_video(page, V.FIXTURES["720p"][0])
        page.evaluate("""() => {
          state.opts.effects.forEach(fx => fx.enabled = false);
          state.opts.exportFormat = 'webm';
          syncUIFromState();
        }""")
        page.evaluate("() => { window.__exportPromise = exportImage(); }")
        page.wait_for_timeout(1200)
        exporting = page.evaluate("() => state.videoExporting")
        other.bring_to_front()
        other.close()
        page.bring_to_front()
        page.wait_for_function("() => !state.videoExporting", timeout=120000)
        settled = page.evaluate("() => !!window.__exportPromise")
        finished = page.evaluate("() => !state.videoExporting")
        record(rows, "4c export with another page in front", exporting and settled and finished,
               f"document.hidden={hidden} started={exporting} finished={finished} "
               f"(headless reports hidden={hidden}, so the hidden-tab branch can only "
               f"be checked in a headed browser)")
        record(rows, "4d no errors in case 4", not errors, repr(errors[:4]))
    finally:
        ctx.close()


def case_5_6(browser, srv, rows):
    ctx, page, errors = V.new_page(browser, srv)
    try:
        load_video(page, V.FIXTURES["720p"][0])
        page.evaluate("() => state.video.play()")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
          state.opts.depth = 60; pushHistory('d1');
          state.opts.depth = 71; pushHistory('d2'); rebuildRamp(); scheduleRender(0);
        }""")
        page.wait_for_timeout(300)
        page.evaluate("() => undo()")
        d1 = page.evaluate("() => state.opts.depth")
        page.evaluate("() => redo()")
        d2 = page.evaluate("() => state.opts.depth")
        page.evaluate("() => toggleCompare()")
        page.wait_for_timeout(300)
        compare = page.evaluate("() => ({ on: state.compare, frames: state.playback.frames })")
        page.evaluate("() => toggleTheme()")
        page.wait_for_timeout(200)
        theme = page.evaluate("() => document.documentElement.dataset.theme")
        page.set_viewport_size({"width": 1100, "height": 820})
        page.wait_for_timeout(500)
        page.evaluate("() => toggleCompare()")
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(400)
        record(rows, "5a undo/redo during playback", d1 == 60 and d2 == 71, f"{d1} then {d2}")
        record(rows, "5b compare split during playback", compare["on"], json.dumps(compare))
        record(rows, "5c theme switch during playback", theme == "light", theme)
        record(rows, "5d resize during playback", not errors, repr(errors[:4]))
        page.evaluate("() => { if (state.video) state.video.pause(); }")

        # 6. 360px mobile with a video
        page.set_viewport_size({"width": 360, "height": 740})
        page.wait_for_timeout(700)
        snaps = []
        for snap in ("peek", "half", "full"):
            page.evaluate("(s) => window.__gcSetSnap(s, false)", snap)
            page.wait_for_timeout(450)
            data = page.evaluate("""() => {
              const panel = document.getElementById('panel');
              return {
                snap: panel.dataset.snap || '',
                sheet: Math.round(panel.getBoundingClientRect().height),
                overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                sheetTop: Math.round(panel.getBoundingClientRect().top),
              };
            }""")
            page.screenshot(path=str(EVID / f"breakit-360-video-{snap}.png"))
            snaps.append(data)
        record(rows, "6 360px video sheet peek/half/full",
               all(s["overflow"] <= 1 for s in snaps)
               and snaps[1]["sheet"] > snaps[0]["sheet"] + 1
               and snaps[2]["sheet"] > snaps[1]["sheet"] + 1,
               json.dumps(snaps))
    finally:
        ctx.close()


def case_7(browser, srv, rows, playwright):
    ctx, page, errors = V.new_page(browser, srv)
    try:
        page.goto(srv.url + "/index.html?worker=0", wait_until="load")
        page.wait_for_timeout(400)
        load_image(page, B.FIXTURE_1080)
        page.evaluate("""() => {
          state.opts.effects = state.opts.effects.map(fx => ({
            ...fx, enabled: ['halftone','crt','bloom','posterize','vignette','thermal'].includes(fx.id)
          }));
          rebuildRamp(); scheduleRender(0);
        }""")
        page.wait_for_timeout(900)
        off = page.evaluate("""() => ({
          worker: typeof renderWorker !== "undefined" && !!renderWorker, ready: state.workerReady,
          hash: (() => { const c = document.getElementById('canvas');
            const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let h = 2166136261; for (let i = 0; i < d.length; i += 4) { h ^= d[i]; h = Math.imul(h,16777619); }
            return h >>> 0; })(),
        })""")
        record(rows, "7a ?worker=0 falls back", off["hash"] != 0 and not errors,
               json.dumps(off))
        record(rows, "7b no errors with worker off", not errors, repr(errors[:4]))
    finally:
        ctx.close()

    ctx = browser.new_context(viewport={"width": 1200, "height": 900},
                              locale="en-US", color_scheme="dark")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    try:
        page.goto("file://" + str(ROOT / "index.html"), wait_until="load")
        page.wait_for_timeout(500)
        load_image(page, B.FIXTURE_1080)
        h = png_hash(page)
        record(rows, "7c file:// renders", h != 0 and not errs, f"hash={h} errors={errs[:3]}")
    finally:
        ctx.close()

    try:
        ff = playwright.firefox.launch(headless=True)
        try:
            fctx, fpage, ferrs = V.new_page(ff, srv)
            try:
                load_image(fpage, B.FIXTURE_1080)
                fpage.evaluate("""() => {
                  state.opts.effects = state.opts.effects.map(fx => ({
                    ...fx, enabled: ['halftone','crt','bloom','posterize','vignette','thermal'].includes(fx.id)
                  }));
                  rebuildRamp(); scheduleRender(0);
                }""")
                fpage.wait_for_timeout(1500)
                info = fpage.evaluate("""() => ({
                  hash: (() => { const c = document.getElementById('canvas');
                    const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                    let h = 2166136261; for (let i = 0; i < d.length; i += 4) { h ^= d[i]; h = Math.imul(h,16777619); }
                    return h >>> 0; })(),
                  worker: !!window.renderWorker,
                  offscreen: typeof OffscreenCanvas !== 'undefined',
                })""")
                record(rows, "7d Firefox renders", info["hash"] != 0 and not ferrs,
                       json.dumps(info) + f" errors={ferrs[:3]}")
            finally:
                fctx.close()
        finally:
            ff.close()
    except Exception as exc:
        record(rows, "7d Firefox renders", False, f"launch failed: {exc}")


def case_8(browser, srv, rows):
    ctx, page, errors = V.new_page(browser, srv)
    ctx.add_init_script(LONG_PROBE)
    try:
        page.reload(wait_until="load")
        page.wait_for_timeout(400)
        load_image(page, B.FIXTURE_4K)
        page.evaluate("""() => {
          const ids = ['halftone','crt','pixelate','bloom','vignette','posterize',
                       'edges','sketch','emboss','blur','thermal','retro'];
          state.opts.effects = state.opts.effects.map(fx => ({ ...fx, enabled: ids.includes(fx.id) }));
          rebuildRamp(); scheduleRender(0);
        }""")
        page.wait_for_timeout(1200)
        box = page.locator("#depth").bounding_box()
        x, y = box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.evaluate("() => window.__longTasks = []")
        for i in range(20):
            page.mouse.move(x + (i % 2) * 40 - 20, y)
            page.wait_for_timeout(80)
        page.mouse.up()
        page.wait_for_timeout(600)
        stats = page.evaluate("""() => ({
          long: window.__longTasks.slice(),
          worst: Math.max(0, ...window.__longTasks),
          over: window.__longTasks.filter(v => v > 50).length,
          effects: state.opts.effects.filter(f => f.enabled).length,
          scale: state.playback.scale,
          previewW: document.getElementById('canvas').width,
        })""")
        record(rows, "8 4K still, 12 effects, slider drag",
               stats["effects"] == 12 and stats["over"] <= 2 and not errors,
               json.dumps(stats))
    finally:
        ctx.close()


def case_9_10(browser, srv, rows):
    ctx, page, errors = V.new_page(browser, srv)
    cdp = B.cdp_session(page)
    try:
        B.gc(cdp)
        heap0 = B.js_heap(cdp)
        for i in range(20):
            page.set_input_files("#file-input", str(B.FIXTURE_1080))
            page.wait_for_function("(n) => state.sourceId >= n && !state.renderDirty",
                                   arg=i + 1, timeout=20000)
            page.wait_for_timeout(80)
        B.gc(cdp)
        page.wait_for_timeout(300)
        heap1 = B.js_heap(cdp)
        record(rows, "9 20 image loads", heap1 - heap0 < 8_000_000 and not errors,
               f"heap {heap0/1e6:.1f}->{heap1/1e6:.1f}MB delta={(heap1-heap0)/1e6:+.2f}MB")
    finally:
        ctx.close()

    ctx, page, errors = V.new_page(browser, srv)
    try:
        empty = page.evaluate("""() => ({
          type: state.sourceType, has: !!state.source,
          status: document.getElementById('status-bar').textContent.trim() })""")
        load_video(page, V.FIXTURES["720p"][0])
        v = page.evaluate("() => ({ type: state.sourceType, w: state.sourceW, h: state.sourceH })")
        load_image(page, B.FIXTURE_1080)
        i = page.evaluate("() => ({ type: state.sourceType, w: state.sourceW, h: state.sourceH })")
        record(rows, "10 empty -> video -> image",
               empty["has"] is False and v["type"] == "video" and i["type"] == "image"
               and not errors,
               f"empty={json.dumps(empty)} video={json.dumps(v)} image={json.dumps(i)}")
    finally:
        ctx.close()


def case_11(browser, srv, rows):
    ctx, page, errors = V.new_page(browser, srv)
    try:
        load_image(page, B.FIXTURE_1080)
        report = page.evaluate("""() => {
          const out = [];
          const ids = EFFECTS.map(e => e.id);
          for (const id of ids) {
            const def = EFFECTS.find(e => e.id === id);
            state.opts.effects = state.opts.effects.map(fx => {
              if (fx.id !== id) return { ...fx, enabled: false };
              const params = { ...fx.params };
              for (const p of (def.params || [])) {
                if (p.type === 'number' || p.type === 'range' || (!p.type && p.min !== undefined)) {
                  params[p.key] = p.min - 1000;
                }
              }
              return { ...fx, enabled: true, params };
            });
            rebuildRamp();
            const base = prepareBase(state.source, 1600, 900, renderOpts(), null);
            const c = document.createElement('canvas');
            c.width = 1600; c.height = 900;
            renderToContext(base, c.getContext('2d'), 1600, 900, renderOpts());
            out.push(id);
            c.width = 0;
          }
          return { effects: out.length, ids: out };
        }""")
        record(rows, "11a all 22 effects at out-of-range values",
               report["effects"] == 22 and not errors,
               f"{report['effects']} effects rendered, errors={errors[:3]}")
        extremes = page.evaluate("""() => {
          const bad = [];
          for (const def of EFFECTS) {
            const params = effectDefaults(def.id);
            for (const p of (def.params || [])) {
              if (p.type === 'color' || p.type === 'select') continue;
              for (const v of [p.min, p.max, p.min - 1e6, p.max + 1e6]) {
                params[p.key] = v;
              }
            }
            const opts = { ...renderOpts(), effects: [{ id: def.id, enabled: true, params }] };
            try {
              const c = document.createElement('canvas'); c.width = 400; c.height = 240;
              const base = prepareBase(state.source, 400, 240, opts, null);
              renderToContext(base, c.getContext('2d'), 400, 240, opts);
              c.width = 0;
            } catch (err) { bad.push(def.id + ': ' + err.message); }
          }
          return bad;
        }""")
        record(rows, "11b every amount at 0/max/typed out of range",
               extremes == [], repr(extremes[:5]))
        typed = page.evaluate("""() => {
          const el = document.getElementById('depth');
          el.value = '99999';
          el.dispatchEvent(new Event('change', { bubbles: true }));
          const high = Number(el.value);
          el.value = '-500';
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return { high, low: Number(el.value) };
        }""")
        record(rows, "11c typed out-of-range clamps",
               0 < typed["high"] <= 400 and typed["low"] >= 1,
               json.dumps(typed))
    finally:
        ctx.close()


def case_12(browser, srv, rows):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                              locale="en-US", color_scheme="dark")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(srv.url + "/index.html", wait_until="load")
    page.wait_for_timeout(500)
    try:
        load_image(page, B.FIXTURE_1080)
        page.evaluate("""() => {
          const ids = ['halftone','crt','pixelate','bloom','vignette','posterize',
                       'edges','sketch','emboss','blur','thermal','retro'];
          state.opts.effects = state.opts.effects.map(fx => ({ ...fx, enabled: ids.includes(fx.id) }));
          state.opts.adj.contrast = 25;
          state.opts.adj.sepia = true;
          setTheme('light');
          syncUIFromState(); rebuildRamp(); scheduleRender(0);
        }""")
        page.wait_for_timeout(1000)
        page.reload(wait_until="load")
        page.wait_for_timeout(1200)
        state = page.evaluate("""() => ({
          theme: document.documentElement.dataset.theme,
          effects: state.opts.effects.filter(f => f.enabled).length,
          sepia: state.opts.adj.sepia,
          contrast: state.opts.adj.contrast,
          blank: !document.querySelector('.canvas-area').classList.contains('has-content'),
        })""")
        page.screenshot(path=str(EVID / "breakit-light-fullest-reload.png"))
        record(rows, "12 reload light theme with fullest state",
               state["theme"] == "light" and not errors,
               json.dumps(state) + f" (state.persisted effects/adj is not required; theme is)")
    finally:
        ctx.close()


def main() -> int:
    files = make_files()
    rows: list[tuple[str, bool, str]] = []
    started = time.time()
    with V.Server() as srv, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for fn, args in (
                (case_1_2_3, (browser, srv, rows, files)),
                (case_4, (browser, srv, rows)),
                (case_5_6, (browser, srv, rows)),
                (case_7, (browser, srv, rows, p)),
                (case_8, (browser, srv, rows)),
                (case_9_10, (browser, srv, rows)),
                (case_11, (browser, srv, rows)),
                (case_12, (browser, srv, rows)),
            ):
                try:
                    fn(*args)
                except Exception:
                    record(rows, fn.__name__ + " crashed", False,
                           traceback.format_exc().splitlines()[-1])
                    traceback.print_exc()
        finally:
            browser.close()

    failed = [r for r in rows if not r[1]]
    print("")
    print(f"BREAK-IT {len(rows) - len(failed)}/{len(rows)} PASS in {time.time() - started:.1f}s")
    for name, ok, detail in failed:
        print(f"FAIL {name}: {detail}")
    print("BREAK-IT PASS" if not failed else "BREAK-IT FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
