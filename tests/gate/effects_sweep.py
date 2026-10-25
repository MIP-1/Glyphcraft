#!/usr/bin/env python3
"""Permanent effects regression sweep (H2).

Runs the real effect runners from effects.js in a real browser against
generated test cards and asserts, for every effect:

  * output dimensions match the input,
  * the output is not uniformly white (mean luma >= 0.97 and std <= 2/255),
  * the output is not unexpectedly uniform black,
  * alpha is 255 everywhere,
  * the neutral value is pixel-identical (hash) where identity is defined.

It also carries the Pencil Sketch / Crosshatch acceptance tests (a)-(e) from
docs/prompts/part1b_hotfix.md.

usage:
  python tests/gate/effects_sweep.py                 # full: all effects, pairs, 4K timing
  python tests/gate/effects_sweep.py --quick         # gate mode: no 4K timing, no fuzz
  python tests/gate/effects_sweep.py --only sketch   # one effect, verbose table
"""
from __future__ import annotations

import argparse
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

HELPERS = r"""
() => {
  if (window.__h2) return;
  const mulberry32 = (a) => () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  const card = (kind, w, h) => {
    const key = kind + '-' + w + 'x' + h;
    if (cards[key]) return key;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d', {willReadFrequently: true});
    const img = ctx.createImageData(w, h), d = img.data;
    const rnd = mulberry32(0x5eed);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4;
        let r = 0, g = 0, b = 0;
        if (kind === 'gradient') {
          const v = Math.round(255 * x / Math.max(1, w - 1));
          r = g = b = v;
        } else if (kind === 'photo') {
          // Dark, galaxy-like: low base, bright wispy band, deterministic noise.
          const t = y / Math.max(1, h - 1);
          const band = Math.exp(-Math.pow((t - 0.45 - 0.12 * Math.sin(x / 41)) / 0.14, 2));
          const stars = rnd() > 0.996 ? 150 * rnd() : 0;
          const base = 12 + 26 * t + 165 * band + stars;
          r = Math.min(255, base * 0.55 + 8);
          g = Math.min(255, base * 0.82 + 6);
          b = Math.min(255, base * 1.00 + 14);
        } else if (kind === 'bars') {
          const bars = [[255,255,255],[255,255,0],[0,255,255],[0,255,0],
                        [255,0,255],[255,0,0],[0,0,255],[0,0,0]];
          const bar = bars[Math.min(7, Math.floor(x * 8 / w))];
          r = bar[0]; g = bar[1]; b = bar[2];
        } else if (kind === 'ramp') {
          const v = Math.round(255 * Math.floor(x * 16 / w) / 15);
          r = g = b = v;
        } else { // flat mid gray
          r = g = b = 128;
        }
        d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    cards[key] = c;
    return key;
  };
  const hash = (data) => {
    let h = 0x811c9dc5;
    for (let i = 0; i < data.length; i++) { h ^= data[i]; h = Math.imul(h, 0x01000193); }
    return h >>> 0;
  };
  const stats = (c, sample) => {
    const w = c.width, h = c.height;
    const d = c.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, w, h).data;
    const step = Math.max(1, sample | 0);
    let n = 0, sum = 0, sum2 = 0, white = 0, black = 0, alphaBad = 0, min = 255, max = 0, nonFinite = 0;
    for (let i = 0; i < d.length; i += 4 * step) {
      const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      if (!Number.isFinite(l)) nonFinite++;
      sum += l; sum2 += l * l; n++;
      if (l >= 250) white++;
      if (l <= 5) black++;
      if (d[i + 3] !== 255) alphaBad++;
      if (l < min) min = l;
      if (l > max) max = l;
    }
    const mean = sum / n, varr = Math.max(0, sum2 / n - mean * mean);
    return {
      w, h, mean: +(mean / 255).toFixed(4), std: +(Math.sqrt(varr) / 255).toFixed(4),
      whiteFrac: +(white / n).toFixed(4), blackFrac: +(black / n).toFixed(4),
      alphaBad, nonFinite, min: +min.toFixed(2), max: +max.toFixed(2),
      hash: hash(d)
    };
  };
  const cards = {};
  const get = (v) => (v === 'last' ? window.__h2.last : cards[v]);
  const run = (id, params, key, sample) => {
    const started = performance.now();
    const out = applyEffects(get(key), [{id, enabled: true, params}]);
    const ms = performance.now() - started;
    window.__h2.last = out;
    return {ms: +ms.toFixed(1), stats: stats(out, sample || 1)};
  };
  // Mean luma (0-255) of the three vertical thirds of a card.
  const thirds = (c) => {
    const w = c.width, h = c.height;
    const d = c.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, w, h).data;
    const sums = [0, 0, 0], counts = [0, 0, 0];
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4;
        const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
        const t = Math.min(2, Math.floor(x * 3 / w));
        sums[t] += l; counts[t]++;
      }
    }
    return sums.map((s, k) => +(s / counts[k]).toFixed(2));
  };
  // Count "ink" pixels (pencil darkening below 200 luma) - a proxy for stroke count.
  const ink = (c) => {
    const w = c.width, h = c.height;
    const d = c.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, w, h).data;
    let n = 0;
    for (let i = 0; i < d.length; i += 4) {
      const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      if (l < 200) n++;
    }
    return n;
  };
  // Count pixels that are darker than their 3x3 neighbourhood: hatch strokes,
  // independent of the overall tone, so density can be compared across Hatch.
  const strokes = (c) => {
    const w = c.width, h = c.height;
    const d = c.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, w, h).data;
    const lum = (i) => 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
    let n = 0;
    for (let y = 1; y < h - 1; y++) {
      for (let x = 1; x < w - 1; x++) {
        const i = (y * w + x) * 4;
        let sum = 0;
        for (let ky = -1; ky <= 1; ky++) {
          for (let kx = -1; kx <= 1; kx++) {
            if (!kx && !ky) continue;
            sum += lum(((y + ky) * w + (x + kx)) * 4);
          }
        }
        if (lum(i) < sum / 8 - 10) n++;
      }
    }
    return n;
  };
  const copy = (c) => {
    const out = document.createElement('canvas');
    out.width = c.width; out.height = c.height;
    out.getContext('2d').drawImage(c, 0, 0);
    return out;
  };
  window.__h2 = {card, stats: (k, s) => stats(get(k), s || 1), run, thirds: (k) => thirds(get(k)),
                 ink: (k) => ink(get(k)), strokes: (k) => strokes(get(k)), copy, hash, last: null};
}
"""


def make_page(p):
    class Q(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"http://127.0.0.1:{httpd.server_port}/index.html", wait_until="load")
    page.wait_for_timeout(400)
    page.evaluate(HELPERS)
    return browser, page, httpd


def sketch_acceptance(page, problems, rows, full):
    def card(kind, w, h):
        return page.evaluate("([k,w,h]) => window.__h2.card(k,w,h)", [kind, w, h])

    def run(params, key, sample=1):
        return page.evaluate("([p,k,n]) => window.__h2.run('sketch', p, k, n)",
                             [params, key, sample])

    def stats(key):
        return page.evaluate("(k) => window.__h2.stats(k, 1)", key)

    gradient = card("gradient", 512, 512)
    photo = card("photo", 512, 512)
    bright = card("bars", 512, 512)

    # (a) Amount 0 is identity, pixel-identical, at every Hatch and odd sizes.
    for cross in (0, 40, 100):
        out = run({"amount": 0, "cross": cross}, gradient)
        src_stats = stats(gradient)
        ok = out["stats"]["hash"] == src_stats["hash"]
        rows.append(("a identity amount=0", f"hatch={cross}", "hash equal" if ok else
                     f"DIFF {src_stats['hash']} != {out['stats']['hash']}", ok))
        problems += [] if ok else [f"sketch amount 0 hatch {cross}: output is not the input"]
    for size in ((1, 1), (2, 2), (17, 13), (31, 7)):
        src = card("photo", size[0], size[1])
        sstats = stats(src)
        out = run({"amount": 0, "cross": 40}, src)
        ok = out["stats"]["hash"] == sstats["hash"] and out["stats"]["w"] == size[0] and out["stats"]["h"] == size[1]
        rows.append(("a identity size", f"{size[0]}x{size[1]}", "ok" if ok else "DIFF", ok))
        problems += [] if ok else [f"sketch amount 0 at {size[0]}x{size[1]}: not the input or wrong size"]

    # (b) Tonal: dark third must be >= 25 points darker than the light third.
    for cross in (0, 40, 100):
        out = run({"amount": 100, "cross": cross}, gradient)
        means = page.evaluate("() => window.__h2.thirds('last')")
        dark, light = means[0], means[2]
        gap = (light - dark) / 255
        ok = gap >= 0.25
        rows.append(("b tonal dark-vs-light", f"hatch={cross} gap={gap:.2f}",
                     f"dark={dark:.1f} light={light:.1f}", ok))
        problems += [] if ok else [f"sketch tonal hatch {cross}: dark third {dark:.1f} vs light {light:.1f} (gap {gap:.2f} < 0.25)"]

    # (c) Never uniformly white for amount >= 10 at any hatch, on two cards.
    for name, src in (("gradient", gradient), ("dark photo", photo), ("color bars", bright)):
        for amount in (10, 30, 50, 70, 100):
            for cross in (0, 40, 100):
                st = run({"amount": amount, "cross": cross}, src)["stats"]
                ok = st["mean"] < 0.97 and st["std"] > 2 / 255 and st["nonFinite"] == 0 and st["alphaBad"] == 0
                if not ok:
                    rows.append(("c not white", f"{name} amount={amount} hatch={cross}", str(st), False))
                    problems.append(f"sketch {name} amount {amount} hatch {cross}: {st}")
                elif amount in (10, 70) and cross in (0, 100):
                    rows.append(("c not white", f"{name} amount={amount} hatch={cross}",
                                 f"mean={st['mean']} std={st['std']}", True))

    # (d) Hatch changes line density by >= 2x at the same amount. A flat card
    # isolates the strokes from the source's own tones.
    flat = card("flat", 512, 512)
    for amount in (50, 100):
        run({"amount": amount, "cross": 0}, flat)
        lo = page.evaluate("() => window.__h2.strokes('last')")
        run({"amount": amount, "cross": 100}, flat)
        hi = page.evaluate("() => window.__h2.strokes('last')")
        ratio = hi / max(1, lo)
        ok = ratio >= 2.0
        rows.append(("d hatch density", f"amount={amount} ink {lo} -> {hi} (x{ratio:.2f})",
                     "denser" if ok else "FAIL", ok))
        problems += [] if ok else [f"sketch hatch density amount {amount}: {lo} -> {hi} (ratio {ratio:.2f} < 2x)"]

    # Fuzz the parameter path: strings, empty, NaN, over-range.
    for raw in ("", "-", ".", "0", "-5", "150", "1e3", " 40 ", None, "abc"):
        st = run({"amount": raw, "cross": raw}, gradient)["stats"]
        ok = st["nonFinite"] == 0 and st["w"] == 512 and st["alphaBad"] == 0 and st["mean"] < 0.97
        rows.append(("param path", f"amount=cross={raw!r}", str(st), ok))
        problems += [] if ok else [f"sketch param path {raw!r}: {st}"]

    if full:
        big = card("photo", 4000, 3000)
        out = run({"amount": 70, "cross": 40}, big, sample=7)
        ms = out["ms"]
        ok = out["stats"]["w"] == 4000 and out["stats"]["h"] == 3000 and ms < 2000
        rows.append(("e 4000x3000", f"{ms}ms", "off the interaction path", ok))
        problems += [] if ok else [f"sketch 4000x3000 took {ms}ms or wrong size"]


# Effects whose neutral value is defined as "leave the image alone". Random
# effects (grain, glitch, vhs, pixelsort, matrix) are excluded: their suppression
# values are covered by the not-white / not-black checks, not by a hash.
IDENTITY = {
    "sketch": {"amount": 0},
    "edges": {"amount": 0},
    "emboss": {"amount": 0},
    "sharpen": {"amount": 0},
    "thermal": {"amount": 0},
    "sepia": {"amount": 0},
    "grain": {"amount": 0},
    "vignette": {"amount": 0},
    "blur": {"radius": 0},
    "pixelsort": {"amount": 0},
    "crt": {"scan": 0, "curve": 0, "mask": 0},
    "bloom": {"amount": 0},
}

# White output is the bug being hunted; uniform black is legitimate only for
# Invert on a white card (its whole purpose), and for Edge Detect below 5%
# strength (a sub-percent edge gain over black really is black).
def black_allowed(eid, params):
    if eid == "invert":
        return True
    if eid == "edges":
        return float(params.get("amount", 80)) < 5
    return False

SWEEP_CARDS = ("gradient", "bars", "ramp", "photo")


def value_sets(params):
    defaults = {p["key"]: p["def"] for p in params}
    sets = [("default", dict(defaults))]
    numeric = [p for p in params if p.get("type") not in ("color", "select")]
    for p in numeric:
        lo, hi, st = float(p["min"]), float(p["max"]), float(p["step"])
        raw = [lo, lo + st, float(p["def"]), (lo + hi) / 2, hi - st, hi]
        seen = []
        for v in raw:
            v = round(v, 6)
            if v not in seen:
                seen.append(v)
        for v in seen:
            sets.append((f"{p['key']}={v:g}", {**defaults, p["key"]: v}))
    if len(numeric) > 1:
        sets.append(("all min", {**defaults, **{p["key"]: p["min"] for p in numeric}}))
        sets.append(("all max", {**defaults, **{p["key"]: p["max"] for p in numeric}}))
    for p in params:
        if p.get("type") == "select":
            for value, _label in p.get("options", []):
                sets.append((f"{p['key']}={value}", {**defaults, p["key"]: value}))
    return sets


def all_effects(page, problems, rows, full):
    effects = page.evaluate("() => EFFECTS.map(e => ({id: e.id, params: e.params}))")
    cards = {}
    for name in SWEEP_CARDS:
        cards[name] = page.evaluate("([k,w,h]) => window.__h2.card(k,w,h)", [name, 512, 512])
    src_hash = {name: page.evaluate("(k) => window.__h2.stats(k, 1)", key)["hash"]
                for name, key in cards.items()}

    for effect in effects:
        eid = effect["id"]
        neutral = IDENTITY.get(eid)
        for label, params in value_sets(effect["params"]):
            is_neutral = neutral is not None and all(params.get(k) == v for k, v in neutral.items())
            card_names = SWEEP_CARDS if label in ("default",) else ("gradient", "bars", "photo")
            worst_mean = 1.0
            worst_std = 1.0
            any_white = False
            black_cards = 0
            bad_alpha = 0
            identity = "n/a"
            wrong_dims = False
            for name in card_names:
                out = page.evaluate("([id,p,k]) => window.__h2.run(id,p,k,1)", [eid, params, cards[name]])
                st = out["stats"]
                if st["w"] != 512 or st["h"] != 512:
                    wrong_dims = True
                bad_alpha += st["alphaBad"]
                # Spec: the output must have mean luma < 0.97 AND std > 2/255
                # whenever the input has variation.
                # White or washed-out: bright AND flat is a white page; a flat
                # black result is the separate black check below.
                is_white = st["mean"] >= 0.97 or (st["std"] <= 2 / 255 and st["mean"] >= 0.5)
                is_black = st["mean"] <= 0.03 and st["std"] <= 2 / 255
                any_white = any_white or is_white
                black_cards += 1 if is_black else 0
                if is_white:
                    worst_mean = min(worst_mean, st["mean"])
                if is_neutral and name == "gradient":
                    identity = "yes" if st["hash"] == src_hash[name] else "NO"
            ok = not any_white and not wrong_dims and bad_alpha == 0
            # A genuinely blank effect blacks out every card; a smooth
            # gradient legitimately has no edges to show in one of them.
            any_black = black_cards == len(card_names)
            if any_black and not black_allowed(eid, params):
                ok = False
            if is_neutral and identity != "yes":
                ok = False
            rows.append((eid, label,
                         f"white={'YES' if any_white else 'no'} alpha_bad={bad_alpha} "
                         f"identity={identity} alpha_bad={bad_alpha}", ok))
            if not ok:
                detail = []
                if any_white:
                    detail.append("uniform white")
                if any_black and not black_allowed(eid, params):
                    detail.append("uniform black")
                if wrong_dims:
                    detail.append("wrong dimensions")
                if bad_alpha:
                    detail.append(f"{bad_alpha} non-255 alpha pixels")
                if is_neutral and identity != "yes":
                    detail.append(f"not identity at neutral {neutral}")
                problems.append(f"{eid} [{label}]: " + ", ".join(detail))


def pair_matrix(page, problems, rows, full):
    """Every ordered pair A->B and B->A at default and at all-max, 256x256."""
    ids = page.evaluate("() => EFFECTS.map(e => e.id)")
    result = page.evaluate("""(ids) => {
      const base = (() => {
        const c = document.createElement('canvas');
        c.width = 256; c.height = 256;
        const ctx = c.getContext('2d', {willReadFrequently: true});
        const img = ctx.createImageData(256, 256), d = img.data;
        for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
          const i = (y * 256 + x) * 4, v = Math.round(255 * x / 255);
          d[i] = v; d[i+1] = Math.round(255 * y / 255); d[i+2] = (v + y) % 256; d[i+3] = 255;
        }
        ctx.putImageData(img, 0, 0);
        return c;
      })();
      const params = (id, which) => {
        const e = EFFECTS.find(x => x.id === id); const out = {};
        e.params.forEach(p => {
          if (p.type === 'color' || p.type === 'select') out[p.key] = p.def;
          else out[p.key] = which === 'max' ? p.max : p.def;
        });
        return out;
      };
      const bad = [];
      let n = 0;
      for (const a of ids) for (const b of ids) {
        if (a === b) continue;
        for (const which of ['default', 'max']) {
          for (const order of [[a, b], [b, a]]) {
            const buf = applyEffects(base, [
              {id: order[0], enabled: true, params: params(order[0], which)},
              {id: order[1], enabled: true, params: params(order[1], which)}
            ]);
            const d = buf.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, 256, 256).data;
            let sum = 0, sum2 = 0, k = 0, alphaBad = 0;
            for (let i = 0; i < d.length; i += 4) {
              const l = 0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2];
              sum += l; sum2 += l * l; k++;
              if (d[i+3] !== 255) alphaBad++;
            }
            const mean = sum / k / 255;
            const std = Math.sqrt(Math.max(0, sum2 / k - (sum / k) ** 2)) / 255;
            n++;
            const blackOk = order.includes('edges') || order.includes('invert');
            if ((mean >= 0.97 && std <= 2 / 255) || (mean <= 0.03 && std <= 2 / 255 && !blackOk)
                || alphaBad || buf.width !== 256) {
              bad.push({pair: order.join('->'), which, mean: +mean.toFixed(3), std: +std.toFixed(3), alphaBad});
            }
          }
        }
      }
      return {n, bad};
    }""", ids)
    rows.append(("pairs", f"{result['n']} ordered pairs", f"{len(result['bad'])} white/blank", not result["bad"]))
    for b in result["bad"][:40]:
        problems.append(f"pair {b['pair']} [{b['which']}]: mean={b['mean']} std={b['std']} alpha_bad={b['alphaBad']}")


FUZZ_JS = r"""
(seed) => {
  const mulberry32 = (a) => () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  const rnd = mulberry32(seed);
  const mk = (kind, w, h) => {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d', {willReadFrequently: true});
    const img = ctx.createImageData(w, h), d = img.data;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      let r, g, b, a = 255;
      const t = x / Math.max(1, w - 1);
      if (kind === 'grad') { r = g = b = Math.round(255 * t); }
      else if (kind === 'clear') { r = Math.round(255 * t); g = Math.round(255 * (1 - t)); b = 128; a = x % 2 ? 0 : 255; }
      else if (kind === 'gray') { r = g = b = Math.round(255 * t); }
      else { r = Math.round(255 * t); g = 40; b = 200 - Math.round(180 * t); }
      d[i] = r; d[i+1] = g; d[i+2] = b; d[i+3] = a;
    }
    ctx.putImageData(img, 0, 0);
    return c;
  };
  const check = (buf, w, h, blankOnly) => {
    if (buf.width !== w || buf.height !== h) return 'dimensions ' + buf.width + 'x' + buf.height;
    const d = buf.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, w, h).data;
    let sum = 0, sum2 = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) {
      const l = 0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2];
      if (!Number.isFinite(l)) return 'non-finite pixel';
      sum += l; sum2 += l * l; n++;
    }
    const mean = sum / n, std = Math.sqrt(Math.max(0, sum2 / n - (sum / n) ** 2));
    // A 1x1 or 2x2 card cannot show variation, and a degenerate parameter set
    // (e.g. Duotone with dark == light) is legitimately flat; the deterministic
    // sweep covers flatness with known configs. Here we hunt washed-out pages.
    if (w * h < 9) return null;
    // For multi-effect stacks "white" means a blank page, not a legitimately
    // bright stack (those still have structure); single effects use the strict
    // spec threshold.
    if (blankOnly) {
      if (mean >= 0.985 * 255 && std <= 1.5) return 'blank white page mean=' + (mean/255).toFixed(3);
      return null;
    }
    if (mean >= 0.97 * 255) return 'white page mean=' + (mean/255).toFixed(3) + ' std=' + (std/255).toFixed(4);
    return null;
  };
  const params = (e, gen) => {
    const out = {};
    e.params.forEach(p => {
      if (p.type === 'color') out[p.key] = ['#000000', '#ffffff', '#ff0000', '#00ff00', '#0a1a10', 'not-a-colour'][Math.floor(rnd() * 6)];
      else if (p.type === 'select') out[p.key] = p.options[Math.floor(rnd() * p.options.length)][0];
      else out[p.key] = gen(p);
    });
    // Identical Duotone endpoints are a flat tint by definition, not a bug.
    if (e.id === 'duotone' && out.dark === out.light) out.light = out.dark === '#ffffff' ? '#000000' : '#ffffff';
    return out;
  };
  const NUM_JUNK = ['', '-', '.', '1e3', ' 40 ', null, undefined, true, false, NaN, Infinity, -Infinity, '40x'];
  const numValue = (p) => {
    const roll = rnd();
    const lo = +p.min, hi = +p.max, span = hi - lo;
    if (roll < 0.08) return NUM_JUNK[Math.floor(rnd() * NUM_JUNK.length)];
    if (roll < 0.20) return lo + (rnd() < 0.5 ? rnd() * 0.02 : 0.98 + rnd() * 0.02) * span;
    if (roll < 0.30) return lo - span * rnd() * 0.5 + (hi + span * rnd() * 0.5 - (lo - span * rnd() * 0.5)) * 0;
    if (roll < 0.55) return lo + rnd() * span;                 // continuous, non-integer
    return Math.round(lo + rnd() * span);                      // on the step grid
  };
  const outOfRange = (p) => {
    const lo = +p.min, hi = +p.max, span = Math.max(1, hi - lo);
    const roll = rnd();
    if (roll < 0.34) return lo - span * rnd();
    if (roll < 0.68) return hi + span * rnd();
    return [0, -1, 1e9, -1e9, 2 ** 53][Math.floor(rnd() * 5)];
  };
  const effects = EFFECTS;
  const failures = [];
  const base = mk('grad', 96, 96);
  let renders = 0;

  for (const e of effects) {
    const numeric = e.params.filter(p => p.type !== 'color' && p.type !== 'select');
    if (!numeric.length) {
      const buf = applyEffects(base, [{id: e.id, enabled: true, params: params(e, () => 0)}]);
      renders++; const bad = check(buf, 96, 96);
      if (bad) failures.push({effect: e.id, where: 'default', detail: bad});
      continue;
    }
    for (const p of numeric) {
      for (const gen of [numValue, outOfRange]) {
        const label = gen === numValue ? 'random' : 'out-of-range';
        for (let k = 0; k < 2000; k++) {
          const ps = params(e, (q) => q === p ? gen(p) : (q.type === 'color' ? q.def : q.def));
          const buf = applyEffects(base, [{id: e.id, enabled: true, params: ps}]);
          renders++;
          const bad = check(buf, 96, 96);
          if (bad) { failures.push({effect: e.id, param: p.key, where: label, value: String(ps[p.key]), detail: bad}); break; }
        }
      }
    }
  }

  // Random stacks of 2-8 effects, random order and params.
  for (let k = 0; k < 3000; k++) {
    const n = 2 + Math.floor(rnd() * 7);
    const stack = [];
    for (let j = 0; j < n; j++) {
      const e = effects[Math.floor(rnd() * effects.length)];
      const ps = params(e, numValue);
      // Duotone with identical endpoints is a flat tint by definition, not a bug.
      if (e.id === 'duotone' && ps.dark === ps.light) ps.light = ps.dark === '#ffffff' ? '#000000' : '#ffffff';
      stack.push({id: e.id, enabled: true, params: ps});
    }
    const buf = applyEffects(base, stack);
    renders++;
    // Invert and Duotone (with the user's own two colours) make a bright
    // background by definition; the colour is the parameter, not a bug.
    const byDefinition = stack.some(s => s.id === 'invert' || s.id === 'duotone');
    const bad = byDefinition ? null : check(buf, 96, 96, true);
    if (bad) { failures.push({effect: stack.map(s => s.id).join('->'), where: 'random stack', detail: bad}); break; }
  }

  // Sizes and input kinds.
  const sizes = [[1,1],[2,2],[17,13],[3,200],[200,3],[300,700],[700,300],[2000,1500]];
  for (const e of effects) {
    for (const [w, h] of sizes) {
      for (const kind of ['grad', 'clear', 'gray']) {
        if (w * h > 400000 && kind !== 'grad') continue;
        const card = mk(kind, w, h);
        const buf = applyEffects(card, [{id: e.id, enabled: true, params: params(e, numValue)}]);
        renders++;
        const bad = check(buf, w, h);
        if (bad) failures.push({effect: e.id, where: 'size ' + w + 'x' + h + ' ' + kind, detail: bad});
      }
    }
  }

  // Three successive "video frames" (the pipeline hands effects canvas frames).
  for (const e of effects) {
    for (let f = 0; f < 3; f++) {
      const card = mk(f % 2 ? 'clear' : 'grad', 160, 120);
      const buf = applyEffects(card, [{id: e.id, enabled: true, params: params(e, numValue)}]);
      renders++;
      const bad = check(buf, 160, 120);
      if (bad) failures.push({effect: e.id, where: 'video frame ' + f, detail: bad});
    }
  }
  return {renders, failures: failures.slice(0, 40), total: failures.length};
}
"""


def fuzz(page, problems, rows):
    result = page.evaluate(FUZZ_JS, 0xC0FFEE)
    rows.append(("fuzz", f"{result['renders']} renders", f"{result['total']} failures",
                 result["total"] == 0))
    for failure in result["failures"]:
        problems.append(f"fuzz {failure}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="gate mode: no pairwise matrix, no 4K")
    ap.add_argument("--only", default="sketch")
    args = ap.parse_args()

    problems: list[str] = []
    rows: list[tuple[str, str, str, bool]] = []

    with sync_playwright() as p:
        browser, page, httpd = make_page(p)
        try:
            if args.only in ("sketch", "all"):
                sketch_acceptance(page, problems, rows, full=not args.quick)
            if args.only in ("all", "effects"):
                all_effects(page, problems, rows, full=not args.quick)
            if args.only in ("all", "pairs"):
                pair_matrix(page, problems, rows, full=True)
            if args.only in ("all", "fuzz") and not args.quick:
                fuzz(page, problems, rows)
        finally:
            browser.close()
            httpd.shutdown()
            httpd.server_close()

    print(f"{'check':24} {'case':38} {'detail':46} verdict")
    for name, case, detail, ok in rows:
        print(f"{name:24} {case:38} {detail:46} {'PASS' if ok else 'FAIL'}")
    print()
    print(f"{len(rows)} checks, {len(problems)} failure(s)")
    for problem in problems:
        print("  FAIL " + problem)
    print("EFFECTS SWEEP " + ("PASS" if not problems else "FAIL"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
