#!/usr/bin/env python3
"""Glyphcraft gate: G1-G21.

Run with `npm run gate` (which calls this file). The gate is intentionally
strict: it uses a real Chromium page and reports file:line or selector evidence
for every failure. It never edits the app or the 169 existing tests.

Optional: `GATE_TASK=p1-1 npm run gate` names the evidence directory.
"""

from __future__ import annotations

import base64
import functools
import json
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import zlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover - environment error is the point
    print("G0 FAIL cannot import Playwright:", exc)
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[2]
GATE_TASK = os.environ.get("GATE_TASK", "p1-0")
EVIDENCE = ROOT / "docs" / "evidence" / GATE_TASK
ALLOWLIST_PATH = Path(__file__).with_name("allowlist.json")
HOST_USERCONTENT = Path(__file__).with_name("host_usercontent.css")
FIXTURE = Path("/tmp/glyphcraft_gate_fixture.png")
TEST_IMAGE = Path("/tmp/glyphcraft_test.png")
REPORTS = ROOT / "tests" / "reports"

ALLOWLIST = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def fail(message: str) -> None:
    print(message)


def make_png(path: Path, width: int = 320, height: int = 240, seed: int = 0) -> None:
    """Deterministic opaque test image, written without third-party packages."""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            r = (x * 255 // max(1, width - 1) + seed * 31) % 256
            g = (y * 255 // max(1, height - 1) + seed * 17) % 256
            b = ((x + y) * 255 // max(1, width + height - 2) + seed * 7) % 256
            row.extend((r, g, b))
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    raw = b"".join(rows)
    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(raw, 9)) +
           chunk(b"IEND", b""))
    path.write_bytes(png)


def ensure_fixtures() -> None:
    # The existing 169-test suite asserts that its fixture is 900x600.
    for path, seed, width, height in ((FIXTURE, 0, 900, 600), (TEST_IMAGE, 1, 900, 600)):
        make_png(path, width=width, height=height, seed=seed)


def start_server() -> tuple[ThreadingHTTPServer, str, threading.Thread]:
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, _format, *_args):
            pass

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{httpd.server_port}", thread


# ---------------------------------------------------------------------------
# G1 - token lint
# ---------------------------------------------------------------------------

COLOR_RE = re.compile(
    r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"
    r"|rgba?\([^)]*\)|hsla?\([^)]*\)"
    r"|(?<![\w-])(?:black|white|red|green|blue|yellow|orange|purple|magenta|cyan|pink|brown|gray|grey)(?![\w-])",
    re.IGNORECASE,
)
NAMED_OK = {"transparent", "currentcolor", "inherit", "initial", "unset", "none", "auto"}


def mask_css_comments(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))
    return re.sub(r"/\*.*?\*/", repl, text, flags=re.S)


def css_block_span(text: str, header: str) -> tuple[int, int] | None:
    start = text.find(header)
    if start < 0:
        return None
    brace = text.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def mask_span(text: str, span: tuple[int, int] | None) -> str:
    if not span:
        return text
    a, b = span
    return text[:a] + re.sub(r"[^\n]", " ", text[a:b]) + text[b:]


def g1_token_lint() -> tuple[bool, list[str]]:
    violations: list[str] = []

    css_path = ROOT / "style.css"
    css = mask_css_comments(css_path.read_text(encoding="utf-8"))
    dark = css_block_span(css, ":root {")
    light = css_block_span(css, ':root[data-theme="light"] {')
    if not dark or not light:
        violations.append("style.css: expected both :root and :root[data-theme=\"light\"] token blocks")
    masked = mask_span(mask_span(css, dark), light)
    for lineno, line in enumerate(masked.splitlines(), 1):
        for match in COLOR_RE.finditer(line):
            token = match.group(0)
            if token.lower() in NAMED_OK:
                continue
            violations.append(f"style.css:{lineno}: hardcoded color {token!r} outside theme token blocks")

    # Only style-bearing HTML is linted. Color-picker values are canvas data.
    html_path = ROOT / "index.html"
    html = html_path.read_text(encoding="utf-8")
    for lineno, line in enumerate(html.splitlines(), 1):
        for match in re.finditer(r'style\s*=\s*"([^"]*)"', line, flags=re.I):
            for color in COLOR_RE.finditer(match.group(1)):
                if color.group(0).lower() in NAMED_OK:
                    continue
                violations.append(f"index.html:{lineno}: hardcoded color {color.group(0)!r} in inline style")

    # JS: colour literals in DOM/CSS writes. Canvas/effect palette colours are
    # preview-canvas data and are intentionally outside this lint.
    for js_path in sorted(ROOT.glob("*.js")):
        text = js_path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if not re.search(r"\.style\.|cssText|setProperty\s*\(", line):
                continue
            for match in COLOR_RE.finditer(line):
                if match.group(0).lower() in NAMED_OK:
                    continue
                violations.append(
                    f"{js_path.name}:{lineno}: hardcoded color {match.group(0)!r} in JS DOM style"
                )

    # Generic custom-property names are globally owned by host browser
    # stylesheets (for example Noctalia/Zen userContent.css). A direct `*`
    # declaration on every element beats an inherited app token, so these
    # names must never be used by the app. Namespaced names are safe.
    generic_names = ("--surface", "--text", "--muted")
    app_texts = [("style.css", css_path.read_text(encoding="utf-8"))]
    app_texts += [(p.name, p.read_text(encoding="utf-8", errors="replace")) for p in sorted(ROOT.glob("*.js"))]
    app_texts.append(("index.html", html_path.read_text(encoding="utf-8")))
    for name, text in app_texts:
        for generic in generic_names:
            pattern = re.compile(rf"(?<![\w-]){re.escape(generic)}(?![\w-])")
            for match in pattern.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{name}:{lineno}: host-generic token {generic!r} used; namespace the app token"
                )

    return not violations, violations


# ---------------------------------------------------------------------------
# G6 - no Arabic
# ---------------------------------------------------------------------------

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
TEXT_SUFFIXES = {
    ".js", ".css", ".html", ".htm", ".json", ".md", ".txt", ".py", ".svg",
    ".xml", ".yml", ".yaml", ".toml", ".ini", ".sh", ".zsh", ".csv",
}
SKIP_DIRS = {".git", "node_modules", "docs/ref"}


def g6_no_arabic() -> tuple[bool, list[str]]:
    violations: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ARABIC_RE.search(line):
                snippet = line.strip().replace("\t", " ")
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                violations.append(f"{rel}:{lineno}: {snippet}")
    return not violations, violations


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

SETUP_EFFECTS_JS = r"""
() => {
  if (typeof EFFECTS === "undefined" || typeof state === "undefined") {
    throw new Error("Glyphcraft globals are missing");
  }
  state.opts.effects = EFFECTS.map(effect => ({
    id: effect.id,
    enabled: true,
    params: effectDefaults(effect.id)
  }));
  renderEffectsList();
  render();
  return state.opts.effects.length;
}
"""

EXPAND_SECTIONS_JS = r"""
() => {
  document.querySelectorAll('.panel-section.collapsed').forEach(section => {
    if (getComputedStyle(section).display === 'none') return;
    const title = section.querySelector('.section-title');
    if (title) title.click();
  });
  return document.querySelectorAll('.panel-section.collapsed').length;
}
"""

SCAN_JS = r"""
([theme, width, state, allowlist]) => {
  const luminanceAllow = (allowlist.luminance || []).map(x => x.selector);
  const contrastAllow = (allowlist.contrast || []).map(x => x.selector);
  const violations = [];
  const seen = new Set();

  function matchesAny(el, selectors) {
    for (const selector of selectors) {
      try {
        if (el.matches(selector) || el.closest(selector)) return true;
      } catch (e) {}
    }
    return false;
  }

  function parseColor(str) {
    if (!str) return null;
    str = String(str).trim().toLowerCase();
    if (str === 'transparent') return [0, 0, 0, 0];
    if (str === 'none' || str === 'currentcolor' || str === 'auto') return null;
    if (str[0] === '#') {
      let hex = str.slice(1);
      if (hex.length === 3 || hex.length === 4) hex = hex.split('').map(c => c + c).join('');
      if (hex.length === 6 || hex.length === 8) {
        const p = [];
        for (let i = 0; i < hex.length; i += 2) p.push(parseInt(hex.slice(i, i + 2), 16));
        return [p[0], p[1], p[2], p.length > 3 ? p[3] / 255 : 1];
      }
      return null;
    }
    let m = str.match(/^rgba?\(([^)]+)\)$/);
    if (m) {
      const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
      if (p.length >= 3 && p.slice(0, 3).every(Number.isFinite)) {
        return [p[0], p[1], p[2], p.length > 3 && Number.isFinite(p[3]) ? p[3] : 1];
      }
    }
    return null;
  }

  function blend(top, bottom) {
    const a = top[3] + bottom[3] * (1 - top[3]);
    if (a <= 0) return [0, 0, 0, 0];
    return [
      (top[0] * top[3] + bottom[0] * bottom[3] * (1 - top[3])) / a,
      (top[1] * top[3] + bottom[1] * bottom[3] * (1 - top[3])) / a,
      (top[2] * top[3] + bottom[2] * bottom[3] * (1 - top[3])) / a,
      a
    ];
  }

  function firstGradientColor(str) {
    if (!str || str.indexOf('gradient') === -1) return null;
    const colors = str.match(/rgba?\([^)]+\)/g);
    if (!colors || !colors.length) return null;
    const parsed = colors.map(parseColor).filter(Boolean);
    if (!parsed.length) return null;
    const n = parsed.length;
    return [
      parsed.reduce((sum, c) => sum + c[0] * c[3], 0) / n,
      parsed.reduce((sum, c) => sum + c[1] * c[3], 0) / n,
      parsed.reduce((sum, c) => sum + c[2] * c[3], 0) / n,
      parsed.reduce((sum, c) => sum + c[3], 0) / n
    ];
  }

  function effectiveBg(el) {
    const chain = [];
    let node = el;
    while (node) { chain.push(node); node = node.parentElement; }
    chain.reverse();
    let bg = [0, 0, 0, 0];
    for (const item of chain) {
      const cs = getComputedStyle(item);
      const own = parseColor(cs.backgroundColor);
      if (own && own[3] > 0) bg = blend(own, bg);
      const gradient = firstGradientColor(cs.backgroundImage);
      if (gradient && gradient[3] > 0) bg = blend(gradient, bg);
    }
    if (bg[3] < 1) bg = blend(bg, [255, 255, 255, 1]);
    return bg;
  }

  function lum(rgb) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
  }

  function ratio(a, b) {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }

  function selectorFor(el) {
    if (el.id) return '#' + el.id;
    let out = el.tagName.toLowerCase();
    if (el.classList && el.classList.length) {
      out += '.' + Array.from(el.classList).slice(0, 3).join('.');
    }
    const siblings = el.parentElement ? Array.from(el.parentElement.children).filter(x => x.tagName === el.tagName) : [];
    if (siblings.length > 1) out += ':nth-of-type(' + (siblings.indexOf(el) + 1) + ')';
    if (el.dataset && el.dataset.id) out += '[data-id="' + el.dataset.id + '"]';
    return out;
  }

  function visible(el) {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'LINK' || el.tagName === 'META') return false;
    if (el.closest('[hidden]')) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse') return false;
    if (parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 1 && r.height >= 1;
  }

  function add(kind, el, fg, bg, contrast, minimum, detail) {
    if (contrast >= minimum - 0.01) return;
    const selector = selectorFor(el);
    const key = [kind, theme, width, selector, fg ? fg.join(',') : '', bg.join(',')].join('|');
    if (seen.has(key)) return;
    seen.add(key);
    violations.push({
      kind, theme, width, state, selector,
      bg: 'rgb(' + bg.slice(0, 3).map(v => Math.round(v)).join(', ') + ')',
      fg: fg ? 'rgb(' + fg.slice(0, 3).map(v => Math.round(v)).join(', ') + ')' : '',
      ratio: +contrast.toFixed(2), min: minimum, detail: detail || ''
    });
  }

  function fgWithOpacity(el, color) {
    if (!color) return null;
    let opacity = 1;
    let node = el;
    while (node && node.nodeType === 1) {
      opacity *= parseFloat(getComputedStyle(node).opacity || '1');
      node = node.parentElement;
    }
    return [color[0], color[1], color[2], color[3] * opacity];
  }

  const elements = Array.from(document.querySelectorAll('body *'));

  // Text and icon contrast.
  for (const el of elements) {
    if (!visible(el)) continue;
    const tag = el.tagName.toLowerCase();
    const cs = getComputedStyle(el);
    const bg = effectiveBg(el);

    if (tag === 'svg') {
      const icon = fgWithOpacity(el, parseColor(cs.color));
      if (icon && icon[3] > 0.01) {
        add('icon', el, icon, bg, ratio(icon, bg), 3, 'svg icon');
      }
      continue;
    }

    if (el.classList && el.classList.contains('drag-handle')) {
      const dots = fgWithOpacity(el, parseColor(cs.color));
      if (dots && dots[3] > 0.01) add('icon', el, dots, bg, ratio(dots, bg), 3, 'handle dots');
    }

    if (el.matches('input[type="range"]')) {
      try {
        const thumb = getComputedStyle(el, '::-webkit-slider-thumb');
        const track = getComputedStyle(el, '::-webkit-slider-runnable-track');
        const tc = parseColor(thumb.backgroundColor);
        const tr = parseColor(track.backgroundColor);
        if (tc && tr && tc[3] > 0.01 && tr[3] > 0.01) {
          add('ui', el, tc, blend(tr, bg), ratio(tc, blend(tr, bg)), 3, 'slider thumb');
        }
      } catch (e) {}
    }

    let text = '';
    for (const child of el.childNodes) {
      if (child.nodeType === 3) text += child.textContent;
    }
    text = text.trim();

    const isField = el.matches('input[type="text"], input[type="number"], input[type="search"], input[type="email"], input[type="password"], input:not([type]), select, textarea');
    if (!text && !isField) continue;

    let fg = parseColor(cs.color);
    if (!fg) continue;

    if (isField) {
      if (tag === 'input') {
        if (!el.value && el.placeholder) {
          const placeholder = getComputedStyle(el, '::placeholder');
          fg = parseColor(placeholder.color) || fg;
          text = el.placeholder;
        } else {
          text = el.value || '';
        }
      } else if (tag === 'select') {
        text = el.selectedOptions && el.selectedOptions[0] ? el.selectedOptions[0].textContent.trim() : '';
      } else {
        text = el.value || el.placeholder || '';
      }
    }
    if (!text) continue;
    fg = fgWithOpacity(el, fg);
    add('text', el, fg, bg, ratio(fg, bg), 4.5, text.slice(0, 48));
  }

  // Border contrast for complete control/component outlines. One-sided
  // separators inside a group are not component boundaries; they are checked
  // by their parent component instead.
  const borderTargets = elements.filter(el =>
    visible(el) && el.matches('input:not([type="range"]):not([type="checkbox"]):not([type="color"]), select, textarea, .btn, .preset-btn, .preset-trigger, .zoom-controls, .zoom-level, .menu-dropdown, .preset-popup')
  );
  for (const el of borderTargets) {
    if (matchesAny(el, contrastAllow)) continue;
    const cs = getComputedStyle(el);
    const sides = ['Top', 'Right', 'Bottom', 'Left'];
    const visibleSides = [];
    let complete = true;
    for (const side of sides) {
      const widthPx = parseFloat(cs['border' + side + 'Width'] || '0');
      const style = cs['border' + side + 'Style'];
      const color = parseColor(cs['border' + side + 'Color']);
      if (widthPx <= 0 || style === 'none' || !color || color[3] <= 0.01) {
        complete = false;
        continue;
      }
      visibleSides.push({side, color});
    }
    if (!complete || visibleSides.length !== 4) continue;
    const behind = effectiveBg(el.parentElement || el);
    for (const item of visibleSides) {
      add('ui', el, item.color, behind, ratio(item.color, behind), 3, item.side.toLowerCase() + ' border');
    }
  }

  // Pseudo-element backgrounds and glyphs (collapse arrows, handle dots and
  // similar affordances) are reachable through getComputedStyle.
  for (const el of elements) {
    if (!visible(el)) continue;
    for (const pseudo of ['::before', '::after']) {
      const pcs = getComputedStyle(el, pseudo);
      const content = pcs.content;
      if (!content || content === 'none' || content === 'normal') continue;
      const pbg = parseColor(pcs.backgroundColor);
      if (pbg && pbg[3] > 0.01) {
        const resolved = blend(pbg, effectiveBg(el));
        const l = lum(resolved);
        if (theme === 'light' && l < 0.35) {
          add('luminance', el, null, resolved, 1, 2, pseudo + ' background luminance ' + l.toFixed(3) + ' < 0.35');
        }
        if (theme === 'dark' && l > 0.35) {
          add('luminance', el, null, resolved, 1, 2, pseudo + ' background luminance ' + l.toFixed(3) + ' > 0.35');
        }
      }
      const pfg = parseColor(pcs.color);
      const glyph = content.replace(/^["']|["']$/g, '').trim();
      if (pfg && pfg[3] > 0.01 && glyph) {
        const pbgResolved = effectiveBg(el);
        add('icon', el, pfg, pbgResolved, ratio(pfg, pbgResolved), 3, pseudo + ' glyph ' + glyph.slice(0, 12));
      }
    }
  }

  // Custom checkbox backgrounds are images; the visible checked/unchecked
  // artwork is additionally covered by the screenshot matrix and manual
  // state review below.
  for (const el of elements.filter(x => visible(x) && x.matches('input[type="checkbox"]'))) {
    const cs = getComputedStyle(el);
    const bg = effectiveBg(el.parentElement || el);
    const image = cs.backgroundImage;
    if (image && image !== 'none') {
      // Data-URI checkbox artwork cannot be parsed reliably as a CSS colour.
      // It is retained in every full-state screenshot for visual inspection.
      void bg;
    }
  }

  // Scrollbars declared through scrollbar-color.
  for (const el of [document.scrollingElement, ...elements.filter(x => x.matches('.panel-content, .preset-list, .effects-list'))]) {
    if (!el || !visible(el)) continue;
    const value = getComputedStyle(el).scrollbarColor;
    if (!value || value === 'auto') continue;
    const parts = value.match(/rgba?\([^)]+\)|#[0-9a-fA-F]{3,8}/g);
    if (!parts || parts.length < 2) continue;
    const thumb = parseColor(parts[0]);
    const track = parseColor(parts[1]);
    if (thumb && track) {
      const trackBg = track[3] > 0.01 ? blend(track, effectiveBg(el)) : effectiveBg(el);
      add('ui', el, thumb, trackBg, ratio(thumb, trackBg), 3, 'scrollbar');
    }
  }

  // Background luminance rule.
  const surfaceTargets = elements.filter(el =>
    visible(el) && el.matches('body, .app, .menubar, .panel, .panel-section, .panel-actionbar, .effect-item, .preset-btn, .btn, .icon-btn, .menu-btn, .zoom-controls, .zoom-level, .preset-trigger, .preset-popup, .preset-option, .menu-dropdown, .menu-item, input:not([type="range"]):not([type="checkbox"]):not([type="color"]), select, textarea, .drop-zone, .toast, .shortcuts')
  );
  for (const el of surfaceTargets) {
    if (matchesAny(el, luminanceAllow)) continue;
    const cs = getComputedStyle(el);
    const own = parseColor(cs.backgroundColor);
    const gradient = firstGradientColor(cs.backgroundImage);
    const color = (own && own[3] > 0.01) ? own : (gradient && gradient[3] > 0.01 ? gradient : null);
    if (!color) continue;
    const resolved = blend(color, effectiveBg(el.parentElement || document.body));
    const l = lum(resolved);
    if (theme === 'light' && l < 0.35) {
      add('luminance', el, null, resolved, 1, 2, 'light theme surface luminance ' + l.toFixed(3) + ' < 0.35');
    }
    if (theme === 'dark' && l > 0.35) {
      add('luminance', el, null, resolved, 1, 2, 'dark theme surface luminance ' + l.toFixed(3) + ' > 0.35');
    }
  }

  return {
    theme: document.documentElement.dataset.theme,
    state,
    violations,
    checkedText: elements.filter(visible).length,
    effects: document.querySelectorAll('.effect-item').length,
    effectIds: Array.from(document.querySelectorAll('.effect-item')).map(el => el.getAttribute('data-id') || ''),
    expectedEffectIds: (typeof EFFECTS !== 'undefined' ? EFFECTS.map(e => e.id) : []),
    presets: document.querySelectorAll('.preset-btn').length,
    canvasWidth: document.getElementById('canvas') ? document.getElementById('canvas').width : 0
  };
}
"""


def setup_page(browser, theme: str, width: int):
    height = 900 if width >= 1000 else 740
    context = browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=theme,
        locale="en-US",
        reduced_motion="reduce",
    )
    context.add_init_script(
        "try{localStorage.setItem('glyphcraft-theme','%s')}catch(e){}" % theme
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
    page.wait_for_timeout(350)
    page.set_input_files("#file-input", str(FIXTURE))
    page.wait_for_selector(".canvas-area.has-content", timeout=20000)
    page.wait_for_timeout(500)

    if width <= 768:
        page.click("#panel-toggle-btn")
        page.wait_for_timeout(300)

    page.evaluate(SETUP_EFFECTS_JS)
    page.evaluate(EXPAND_SECTIONS_JS)
    page.fill("#depth-num", "91")
    page.dispatch_event("#depth-num", "change")
    page.wait_for_timeout(650)
    return context, page, errors


def screenshot(page, theme: str, width: int, state: str, scroll_selector: str | None = None) -> Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if scroll_selector:
        page.evaluate(
            """(selector) => {
              const el = document.querySelector(selector);
              if (el) el.scrollIntoView({block: 'start'});
            }""",
            scroll_selector,
        )
        page.wait_for_timeout(150)
    path = EVIDENCE / f"{theme}-{width}-{state}.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def scan(page, theme: str, width: int, state: str) -> dict:
    # After a stress toggle the actual theme is authoritative; the requested
    # cell theme is only the starting point.
    actual = page.evaluate("() => document.documentElement.dataset.theme || 'dark'")
    return page.evaluate(SCAN_JS, [actual, width, state, ALLOWLIST])


def geometry(page, theme: str, width: int) -> dict:
    return page.evaluate(
        r"""
        ([theme, width]) => {
          const bar = document.querySelector('.menubar');
          if (!bar) return {theme, width, error: 'menubar missing', violations: []};
          const barRect = bar.getBoundingClientRect();
          const items = Array.from(document.querySelector('.menubar-right').children)
            .filter(el => getComputedStyle(el).display !== 'none');
          const info = items.map((el, i) => {
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const svgs = Array.from(el.querySelectorAll(':scope > svg'))
              .map(svg => {
                const sr = svg.getBoundingClientRect();
                return {left: sr.left, top: sr.top, right: sr.right, bottom: sr.bottom, width: sr.width, height: sr.height};
              })
              .filter(sr => sr.width >= 1 && sr.height >= 1);
            const borderWidths = ['Top', 'Right', 'Bottom', 'Left'].map(side => parseFloat(cs['border' + side + 'Width']) || 0);
            return {
              index: i,
              name: el.id || el.className || el.tagName.toLowerCase(),
              tag: el.tagName.toLowerCase(),
              left: r.left, top: r.top, right: r.right, bottom: r.bottom,
              width: r.width, height: r.height,
              radius: parseFloat(cs.borderTopLeftRadius) || 0,
              borderWidth: Math.max(...borderWidths),
              borderWidths,
              boxed: borderWidths.some(x => x > 0) && !['none', 'hidden'].includes(cs.borderTopStyle),
              svgs
            };
          });
          const sg = document.querySelector('.status-group');
          const status = sg ? {
            tag: sg.tagName.toLowerCase(),
            role: sg.getAttribute('role') || '',
            tabIndex: sg.getAttribute('tabindex'),
            cursor: getComputedStyle(sg).cursor,
            segments: Array.from(sg.querySelectorAll('.status-seg')).map(seg => {
              const scs = getComputedStyle(seg);
              return {
                text: (seg.textContent || '').trim(),
                hidden: seg.hidden || scs.display === 'none',
                borderStart: parseFloat(scs.borderInlineStartWidth) || 0,
                height: seg.getBoundingClientRect().height,
                clientWidth: seg.clientWidth,
                scrollWidth: seg.scrollWidth
              };
            })
          } : null;
          return {theme, width, bar: {left: barRect.left, top: barRect.top, right: barRect.right, bottom: barRect.bottom, width: barRect.width, height: barRect.height}, items: info, status};
        }
        """,
        [theme, width],
    )


def evaluate_geometry(data: dict, tolerance: float = 1.0) -> list[dict]:
    if data.get("error"):
        return [{"cell": f"{data['theme']} {data['width']}", "kind": "error", "detail": data["error"]}]
    cell = f"{data['theme']} {data['width']}"
    out: list[dict] = []
    bar = data["bar"]
    items = data["items"]
    if not items:
        return [{"cell": cell, "kind": "missing", "detail": "no direct top-bar items"}]

    for item in items:
        name = item["name"]
        if item["left"] < bar["left"] - tolerance or item["right"] > bar["right"] + tolerance:
            out.append({"cell": cell, "kind": "overflow", "detail": f"{name} horizontal box {item['left']:.1f}..{item['right']:.1f} outside bar {bar['left']:.1f}..{bar['right']:.1f}"})
        if item["top"] < bar["top"] - tolerance or item["bottom"] > bar["bottom"] + tolerance:
            out.append({"cell": cell, "kind": "overflow", "detail": f"{name} vertical box {item['top']:.1f}..{item['bottom']:.1f} outside bar {bar['top']:.1f}..{bar['bottom']:.1f}"})
        if item["svgs"]:
            for sr in item["svgs"]:
                r = item
                if sr["left"] < r["left"] - tolerance or sr["right"] > r["right"] + tolerance or sr["top"] < r["top"] - tolerance or sr["bottom"] > r["bottom"] + tolerance:
                    out.append({"cell": cell, "kind": "clipped-icon", "detail": f"{name} svg {sr['left']:.1f},{sr['top']:.1f} {sr['width']:.1f}x{sr['height']:.1f} outside item {r['left']:.1f},{r['top']:.1f} {r['width']:.1f}x{r['height']:.1f}"})
                item_cx = (r["left"] + r["right"]) / 2
                item_cy = (r["top"] + r["bottom"]) / 2
                svg_cx = (sr["left"] + sr["right"]) / 2
                svg_cy = (sr["top"] + sr["bottom"]) / 2
                if abs(item_cx - svg_cx) > tolerance or abs(item_cy - svg_cy) > tolerance:
                    out.append({"cell": cell, "kind": "icon-center", "detail": f"{name} icon center ({svg_cx:.1f},{svg_cy:.1f}) vs item center ({item_cx:.1f},{item_cy:.1f})"})

    heights = [i["height"] for i in items]
    if max(heights) - min(heights) > tolerance:
        out.append({"cell": cell, "kind": "height", "detail": "heights " + ", ".join(f"{i['name']}={i['height']:.1f}" for i in items)})

    # Rows are stable groups of items sharing a top offset. The desktop bar is
    # one row; below 768 px the status group alone may wrap onto a second row.
    rows: list[list[dict]] = []
    for item in sorted(items, key=lambda i: (i["top"], i["left"])):
        if rows and abs(rows[-1][0]["top"] - item["top"]) <= tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])
    if data["width"] > 768 and len(rows) > 1:
        out.append({"cell": cell, "kind": "rows", "detail": f"{len(rows)} rows at desktop width: " + " | ".join(", ".join(i["name"] for i in row) for row in rows)})
    if data["width"] <= 700 and len(rows) != 1:
        out.append({"cell": cell, "kind": "rows", "detail": f"{len(rows)} rows at mobile width, expected a single row: " + " | ".join(", ".join(i["name"] for i in row) for row in rows)})
    if len(rows) > 2:
        out.append({"cell": cell, "kind": "rows", "detail": f"{len(rows)} rows: " + " | ".join(", ".join(i["name"] for i in row) for row in rows)})
    if len(rows) == 2:
        alone = [row for row in rows if len(row) == 1 and row[0]["name"] == "status-bar"]
        if not alone:
            out.append({"cell": cell, "kind": "rows", "detail": "wrapped row must contain only the status group: " + " | ".join(", ".join(i["name"] for i in row) for row in rows)})
    for row in rows:
        row_tops = [i["top"] for i in row]
        if max(row_tops) - min(row_tops) > tolerance:
            out.append({"cell": cell, "kind": "top", "detail": "tops " + ", ".join(f"{i['name']}={i['top']:.1f}" for i in row)})
        row_heights = [i["height"] for i in row]
        if max(row_heights) - min(row_heights) > tolerance:
            out.append({"cell": cell, "kind": "row-height", "detail": "heights " + ", ".join(f"{i['name']}={i['height']:.1f}" for i in row)})
        gaps = []
        for a, b in zip(row, row[1:]):
            gaps.append((a["name"], b["name"], b["left"] - a["right"]))
        if gaps:
            values = [g[2] for g in gaps]
            if max(values) - min(values) > tolerance:
                out.append({"cell": cell, "kind": "gap", "detail": ", ".join(f"{a}/{b}={g:.1f}" for a, b, g in gaps)})

    boxed = [i for i in items if i["boxed"]]
    if len(boxed) != len(items):
        out.append({"cell": cell, "kind": "boxed", "detail": "unboxed items: " + ", ".join(i["name"] for i in items if not i["boxed"])})
    if boxed:
        bw = [i["borderWidth"] for i in boxed]
        radii = [i["radius"] for i in boxed]
        if max(bw) - min(bw) > tolerance:
            out.append({"cell": cell, "kind": "border-width", "detail": ", ".join(f"{i['name']}={i['borderWidth']:.1f}" for i in boxed)})
        if max(radii) - min(radii) > tolerance:
            out.append({"cell": cell, "kind": "radius", "detail": ", ".join(f"{i['name']}={i['radius']:.1f}" for i in boxed)})

    status = data.get("status")
    if not status:
        out.append({"cell": cell, "kind": "status", "detail": "status group missing"})
    else:
        segs = status["segments"]
        if status["tag"] != "div" or status["role"] != "status":
            out.append({"cell": cell, "kind": "status", "detail": f"status group must be a non-interactive div with role=status, got <{status['tag']}> role={status['role']!r}"})
        if status["tabIndex"] is not None or status["cursor"] == "pointer":
            out.append({"cell": cell, "kind": "status", "detail": f"status group must not be interactive: tabindex={status['tabIndex']} cursor={status['cursor']}"})
        if len(segs) != 3:
            out.append({"cell": cell, "kind": "status", "detail": f"expected 3 status segments, got {len(segs)}"})
        visible = [s for s in segs if not s["hidden"]]
        if len(visible) != 3:
            out.append({"cell": cell, "kind": "status", "detail": f"expected 3 visible segments with an image loaded, got {len(visible)}"})
        if any(not s["text"] for s in visible):
            out.append({"cell": cell, "kind": "status", "detail": "empty status segment: " + repr([s["text"] for s in visible])})
        clipped = [s["text"] for s in visible if s["scrollWidth"] > s["clientWidth"] + tolerance]
        if clipped:
            out.append({"cell": cell, "kind": "status", "detail": "clipped status text: " + repr(clipped)})
        dividers = [s["borderStart"] for s in segs[1:]]
        if len(dividers) != 2 or any(abs(d - 1) > tolerance for d in dividers):
            out.append({"cell": cell, "kind": "status", "detail": f"internal dividers must be 1px, got {dividers}"})
    return out


def run_frame_harness(page, theme: str, width: int) -> dict:
    page.evaluate(
        r"""
        () => {
          window.__gateFrames = [];
          window.__gateSampling = true;
          window.__gateLast = performance.now();
          const tick = (t) => {
            if (!window.__gateSampling) return;
            window.__gateFrames.push(t - window.__gateLast);
            window.__gateLast = t;
            requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
        """
    )
    slider = page.locator("#depth")
    slider.scroll_into_view_if_needed()
    box = slider.bounding_box()
    if not box:
        page.evaluate("() => { window.__gateSampling = false; }")
        return {"theme": theme, "width": width, "error": "depth slider has no box", "frames": 0}
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + 4, y)
    page.mouse.down()
    steps = 32
    for i in range(1, steps + 1):
        x = box["x"] + 4 + (box["width"] - 8) * i / steps
        page.mouse.move(x, y)
        page.wait_for_timeout(14)
    page.mouse.up()
    page.wait_for_timeout(150)
    result = page.evaluate(
        r"""
        () => {
          window.__gateSampling = false;
          const frames = (window.__gateFrames || []).filter(x => Number.isFinite(x) && x > 0);
          const sorted = frames.slice().sort((a, b) => a - b);
          const pick = p => sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] : null;
          return {frames: frames.length, median: pick(0.5), p95: pick(0.95)};
        }
        """
    )
    result.update({"theme": theme, "width": width})
    return result


def apply_host_usercontent(page) -> None:
    """Apply the same generic token block a global browser userContent.css adds.

    The fixture is loaded as an author stylesheet in the gate, which reproduces
    the cascade that matters here: a direct `*` declaration on every element
    beats the app's inherited `:root[data-theme]` values. In the user's Zen
    profile the same rules are user-origin; the computed values are identical.
    """
    page.add_style_tag(path=str(HOST_USERCONTENT))
    page.wait_for_timeout(250)


def ensure_panel_open(page, width: int) -> None:
    if width > 768:
        return
    if not page.evaluate("() => !!document.querySelector('#panel.open')"):
        page.click("#panel-toggle-btn")
        page.wait_for_timeout(300)


def add_effects_with_real_click(page, width: int) -> None:
    ensure_panel_open(page, width)
    page.locator("#section-effects").scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    page.locator('.preset-btn[data-preset="oldphoto"]').click()
    page.wait_for_timeout(750)


def run_real_theme_flow(
    browser,
    result: dict,
    seen_g2: set[tuple],
    width: int,
    os_theme: str,
    host_css: bool,
    label: str,
) -> None:
    """Exercise the user's real flow, optionally with a host userContent.css.

    Start with no app localStorage, open a file through the real input, add
    effects with a real preset click, toggle via the top-bar icon and `T`,
    then reload while light. The OS-light variant starts on a first visit with
    no saved theme.
    """
    height = 900 if width >= 1000 else 740
    context = browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=os_theme,
        locale="en-US",
        reduced_motion="reduce",
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    result["g2"]["cells"] += 1
    try:
        page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
        page.wait_for_timeout(450)
        if host_css:
            apply_host_usercontent(page)
        ensure_panel_open(page, width)

        page.set_input_files("#file-input", str(FIXTURE))
        page.wait_for_selector(".canvas-area.has-content", timeout=20000)
        page.wait_for_timeout(500)
        add_effects_with_real_click(page, width)

        data = scan(page, os_theme, width, f"{label}-initial")
        _merge_scan(result["g2"], data, seen_g2)

        if os_theme == "dark":
            page.click("#theme-toggle")
            page.wait_for_timeout(600)
            shot = screenshot(page, "light", width, f"{label}-icon")
            result["g3"]["screenshots"].append(str(shot.relative_to(ROOT)))
            data = scan(page, "light", width, f"{label}-icon")
            _merge_scan(result["g2"], data, seen_g2)

            page.keyboard.press("t")
            page.wait_for_timeout(600)
            data = scan(page, "dark", width, f"{label}-T-dark")
            _merge_scan(result["g2"], data, seen_g2)

            page.keyboard.press("t")
            page.wait_for_timeout(600)
            shot = screenshot(page, "light", width, f"{label}-T-light")
            result["g3"]["screenshots"].append(str(shot.relative_to(ROOT)))
            data = scan(page, "light", width, f"{label}-T-light")
            _merge_scan(result["g2"], data, seen_g2)

            page.reload(wait_until="load")
            page.wait_for_timeout(650)
            if host_css:
                apply_host_usercontent(page)
            ensure_panel_open(page, width)
            shot = screenshot(page, "light", width, f"{label}-reload-light")
            result["g3"]["screenshots"].append(str(shot.relative_to(ROOT)))
            data = scan(page, "light", width, f"{label}-reload-light")
            _merge_scan(result["g2"], data, seen_g2)
        else:
            shot = screenshot(page, "light", width, f"{label}-os-light")
            result["g3"]["screenshots"].append(str(shot.relative_to(ROOT)))
            data = scan(page, "light", width, f"{label}-os-light")
            _merge_scan(result["g2"], data, seen_g2)

        if errors:
            result["errors"].extend(f"{label} {width}: {e}" for e in errors)
    finally:
        context.close()


def run_browser_checks() -> dict:
    result = {
        "g2": {"pass": True, "violations": [], "checked": 0, "states": 0, "cells": 0},
        "g3": {"pass": True, "screenshots": []},
        "g4": {"pass": True, "runs": []},
        "g7": {"pass": True, "items": []},
        "g8": {"pass": True, "violations": []},
        "errors": [],
    }
    seen_g2: set[tuple] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for theme in ("dark", "light"):
                for width in (1280, 360):
                    context, page, page_errors = setup_page(browser, theme, width)
                    try:
                        result["g2"]["cells"] += 1
                        if page_errors:
                            result["errors"].extend(f"{theme} {width}: {e}" for e in page_errors)

                        # G7 is DOM-only; record it once per page.
                        view_items = page.evaluate(
                            """() => Array.from(document.querySelectorAll('#dropdown-view .menu-item')).map(el => ({
                              action: el.getAttribute('data-action') || '',
                              text: (el.innerText || el.textContent || '').trim()
                            }))"""
                        )
                        bad = [i for i in view_items if i["action"] in ("theme", "light-theme", "dark-theme") or re.search(r"\b(theme|light theme|dark theme)\b", i["text"], re.I)]
                        if bad:
                            result["g7"]["pass"] = False
                            result["g7"]["items"].append({"theme": theme, "width": width, "items": bad})
                        else:
                            result["g7"]["items"].append({"theme": theme, "width": width, "items": []})

                        # G8 before interactions, while every top-bar item is in its normal state.
                        geo = evaluate_geometry(geometry(page, theme, width))
                        if geo:
                            result["g8"]["pass"] = False
                            result["g8"]["violations"].extend(geo)

                        # Full-state screenshot views and DOM scans.
                        page.evaluate("() => { const p=document.querySelector('.panel-content'); if(p) p.scrollTop=0; }")
                        sh = screenshot(page, theme, width, "fullest-top")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "fullest-top")
                        _merge_scan(result["g2"], data, seen_g2)

                        sh = screenshot(page, theme, width, "fullest-effects", "#section-effects")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))

                        # Menus.
                        if width <= 700:
                            page.evaluate("() => closeAllMenus()")
                            page.evaluate("() => { const p=document.querySelector('.panel-content'); if(p) p.scrollTop=0; }")
                            page.click("#mobile-menu-btn")
                            page.wait_for_timeout(220)
                            sh = screenshot(page, theme, width, "mobile-menu")
                            result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                            data = scan(page, theme, width, "mobile-menu")
                            _merge_scan(result["g2"], data, seen_g2)
                            page.evaluate("() => closeAllMenus()")
                            page.wait_for_timeout(120)
                        else:
                            for menu in ("file", "view", "edit"):
                                page.evaluate("() => closeAllMenus()")
                                page.evaluate("() => { const p=document.querySelector('.panel-content'); if(p) p.scrollTop=0; }")
                                page.click(f"#menu-{menu}")
                                page.wait_for_timeout(220)
                                sh = screenshot(page, theme, width, f"{menu}-menu")
                                result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                                data = scan(page, theme, width, f"{menu}-menu")
                                _merge_scan(result["g2"], data, seen_g2)
                                page.evaluate("() => closeAllMenus()")
                                page.wait_for_timeout(120)

                        page.click("#zoom-level")
                        page.wait_for_timeout(220)
                        sh = screenshot(page, theme, width, "zoom-menu")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "zoom-menu")
                        _merge_scan(result["g2"], data, seen_g2)
                        page.evaluate("() => closeAllMenus()")
                        page.wait_for_timeout(120)

                        # Size picker, with every group expanded.
                        page.evaluate("""() => {
                          const el = document.getElementById('output-preset-trigger');
                          const c = document.querySelector('.panel-content');
                          const bar = document.getElementById('panel-actionbar');
                          const top = el.getBoundingClientRect().top - c.getBoundingClientRect().top + c.scrollTop;
                          c.scrollTop = Math.max(0, top - bar.getBoundingClientRect().height - 8);
                        }""")
                        page.wait_for_timeout(200)
                        page.click("#output-preset-trigger")
                        page.wait_for_timeout(250)
                        more = page.locator("[data-preset-more]")
                        if more.count():
                            more.scroll_into_view_if_needed()
                            more.click()
                            page.wait_for_timeout(350)
                        sh = screenshot(page, theme, width, "size-picker")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "size-picker")
                        _merge_scan(result["g2"], data, seen_g2)
                        if width <= 700:
                            page.evaluate("() => closePresetPicker(false)")
                        else:
                            page.keyboard.press("Escape")
                        page.wait_for_timeout(120)

                        # Native select focus (its OS popup cannot be screenshot in headless Chromium).
                        page.locator("#export-format").scroll_into_view_if_needed()
                        page.focus("#export-format")
                        page.wait_for_timeout(150)
                        sh = screenshot(page, theme, width, "select-focus")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "select-focus")
                        _merge_scan(result["g2"], data, seen_g2)

                        # Focus ring and hover state.
                        page.evaluate("() => { const p=document.querySelector('.panel-content'); if(p) p.scrollTop=0; }")
                        page.focus("#theme-toggle")
                        page.wait_for_timeout(150)
                        sh = screenshot(page, theme, width, "focus-theme")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "focus-theme")
                        _merge_scan(result["g2"], data, seen_g2)

                        # Native tooltip is a HUMAN-CHECK in headless Chromium; the
                        # hover state itself is real and captured.
                        page.hover("#theme-toggle")
                        page.wait_for_timeout(700)
                        sh = screenshot(page, theme, width, "hover-theme-tooltip")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "hover-theme-tooltip")
                        _merge_scan(result["g2"], data, seen_g2)

                        page.evaluate("""() => {
                          const el = document.getElementById('section-effects');
                          const c = document.querySelector('.panel-content');
                          const bar = document.getElementById('panel-actionbar');
                          const top = el.getBoundingClientRect().top - c.getBoundingClientRect().top + c.scrollTop;
                          c.scrollTop = Math.max(0, top - bar.getBoundingClientRect().height - 8);
                        }""")
                        page.wait_for_timeout(150)
                        page.hover(".preset-btn")
                        page.wait_for_timeout(150)
                        sh = screenshot(page, theme, width, "hover-preset")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "hover-preset")
                        _merge_scan(result["g2"], data, seen_g2)

                        page.hover("#btn-export")
                        page.wait_for_timeout(150)
                        sh = screenshot(page, theme, width, "hover-primary")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "hover-primary")
                        _merge_scan(result["g2"], data, seen_g2)

                        # G4 on the full effect stack.
                        frame = run_frame_harness(page, theme, width)
                        result["g4"]["runs"].append(frame)

                        # G2 stress: five actual theme toggles, each with a full scan.
                        page.evaluate("() => document.querySelectorAll('.menu-dropdown.open').forEach(d => d.classList.remove('open'))")
                        page.evaluate("() => { const p=document.querySelector('.panel-content'); if(p) p.scrollTop=0; }")
                        for n in range(1, 6):
                            page.click("#theme-toggle")
                            # The scan must see a settled theme: a cell theme is
                            # the starting point, and each click flips it.
                            expect = theme if n % 2 == 0 else ("light" if theme == "dark" else "dark")
                            page.wait_for_function(
                                "(t) => document.documentElement.dataset.theme === t",
                                arg=expect, timeout=5000,
                            )
                            page.evaluate(
                                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
                            )
                            page.wait_for_timeout(300)
                            data = scan(page, theme, width, f"toggle-{n}")
                            _merge_scan(result["g2"], data, seen_g2)
                    finally:
                        context.close()

            # Real user flows. These do not pre-seed localStorage and do not
            # inject effects through JS: they open a file, click a preset, use
            # the icon and `T`, and reload while light.
            for width in (1280, 360):
                run_real_theme_flow(browser, result, seen_g2, width, "dark", False, "real-clean")
                run_real_theme_flow(browser, result, seen_g2, width, "dark", True, "host-dark")
                run_real_theme_flow(browser, result, seen_g2, width, "light", True, "host-os-light")
        finally:
            browser.close()

    for run in result["g4"]["runs"]:
        if run.get("error") or not run.get("frames") or run["frames"] < 10:
            result["g4"]["pass"] = False

    # Desktop captures 12 states per theme/width; mobile replaces the three
    # separate menu states with one mobile-menu state.
    expected_shots = 2 * (12 + 10)
    if len(result["g3"]["screenshots"]) < expected_shots:
        result["g3"]["pass"] = False
    for shot in result["g3"]["screenshots"]:
        if not (ROOT / shot).exists():
            result["g3"]["pass"] = False

    return result


def _merge_scan(g2: dict, data: dict, seen: set[tuple]) -> None:
    g2["checked"] += data.get("checkedText", 0)
    g2["states"] += 1
    if data.get("theme") not in ("dark", "light"):
        g2["pass"] = False
        g2["violations"].append({"kind": "theme", "detail": f"unexpected theme {data.get('theme')!r}", "selector": "html"})
    if data.get("state") == "fullest-top":
        expected = data.get("expectedEffectIds") or []
        actual = data.get("effectIds") or []
        if len(actual) != 22 or actual != expected:
            key = ("effect-coverage", data.get("theme"), data.get("width"), ".effect-item", "", "")
            if key not in seen:
                seen.add(key)
                g2["pass"] = False
                g2["violations"].append({
                    "kind": "effect-coverage",
                    "detail": f"fullest state expected {len(expected)} effect ids {expected}, got {len(actual)} {actual}",
                    "selector": ".effect-item",
                })
    for violation in data.get("violations", []):
        key = (violation.get("kind"), violation.get("theme"), violation.get("width"), violation.get("selector"),
               violation.get("bg"), violation.get("fg"))
        if key in seen:
            continue
        seen.add(key)
        g2["violations"].append(violation)
        g2["pass"] = False


# ---------------------------------------------------------------------------
# G5 - existing tests
# ---------------------------------------------------------------------------

def g5_existing_tests() -> tuple[bool, list[str], str]:
    ensure_fixtures()
    REPORTS.mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "test_suite.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1200,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/test_suite.py: timed out after 1200s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    for line in lines:
        if line.startswith("FAIL "):
            continue
    failures = [line for line in lines if line.startswith("FAIL ")]
    summary = next((line for line in reversed(lines) if "REPORT WRITTEN" in line), "")
    match = re.search(r"REPORT WRITTEN\s+(\d+)\s+checks,\s+(\d+)\s+failures", summary)
    problems: list[str] = []
    if proc.returncode != 0:
        problems.append(f"tests/test_suite.py exited {proc.returncode}")
    if not match:
        problems.append("tests/test_suite.py did not print its REPORT WRITTEN summary")
    else:
        checks, failed = int(match.group(1)), int(match.group(2))
        if checks != 169:
            problems.append(f"expected 169 checks, got {checks}")
        if failed != 0:
            problems.append(f"{failed} test failure(s)")
    if failures:
        problems.extend(failures[:20])
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems, detail


# ---------------------------------------------------------------------------
# G9 - numeric steppers (H1)
# ---------------------------------------------------------------------------

FIXTURE_4K = Path("/tmp/glyphcraft_gate_4k.png")

G9_INSTRUMENT_JS = r"""
() => {
  if (window.__gc) return;
  window.__gc = {writes: 0, times: [], downT: 0, writesAtDown: 0, renders: 0, lastWrite: 0};
  const proto = HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, 'value');
  Object.defineProperty(proto, 'value', {
    configurable: true,
    get() { return desc.get.call(this); },
    set(v) {
      if (this.type === 'number') {
        window.__gc.writes += 1;
        window.__gc.lastWrite = performance.now();
        window.__gc.times.push(window.__gc.lastWrite);
      }
      desc.set.call(this, v);
    }
  });
  const originalRender = window.render;
  window.render = function () {
    window.__gc.renders += 1;
    return originalRender.apply(this, arguments);
  };
  window.addEventListener('pointerdown', e => {
    const btn = e.target && e.target.closest ? e.target.closest('.step-btn') : null;
    if (!btn) return;
    window.__gc.downT = performance.now();
    window.__gc.writesAtDown = window.__gc.writes;
  }, true);
}
"""

G9_CONTROLS_JS = r"""
() => Array.from(document.querySelectorAll('.stepper[data-control]')).map(group => {
  const input = group.parentElement.querySelector('input[type=number]');
  if (!input) return {id: group.dataset.control, missing: true};
  return {
    id: group.dataset.control,
    min: +input.min,
    max: +input.max,
    step: +input.step,
    value: +input.value,
    up: group.querySelector('[data-step="up"]') ? true : false,
    down: group.querySelector('[data-step="down"]') ? true : false,
    width: group.getBoundingClientRect().width,
    height: group.getBoundingClientRect().height
  };
})
"""

G9_STATE_JS = r"""
(id) => {
  const fx = id.match(/^fx\.([^.]+)\.(.+)$/);
  if (fx) {
    const item = (state.opts.effects || []).find(e => e.id === fx[1]);
    return item ? item.params[fx[2]] : null;
  }
  if (id.startsWith('adj.') && !id.endsWith('-num')) return state.opts.adj[id.slice(4)];
  if (id.startsWith('adj-') && id.endsWith('-num')) return state.opts.adj[id.slice(4, -4)];
  const map = {'depth-num': 'depth', 'char-offset-num': 'charOffset', 'cell-size-num': 'cellSize',
               'glyph-weight-num': 'glyphWeight', 'dither-depth-num': 'ditherDepth', 'jpg-quality-num': 'jpgQuality'};
  return map[id] ? state.opts[map[id]] : null;
}
"""


def _g9_decimals(step: float) -> int:
    text = repr(step)
    return len(text.split(".")[1]) if "." in text and "e" not in text else 0


def _g9_clamp_step(value: float, param: dict, steps: int) -> float:
    mn, mx, step = param["min"], param["max"], param["step"]
    # Same order as app.js: snap to the step grid anchored at min, then clamp.
    snapped = mn + round((value - mn) / step) * step
    snapped = round(snapped, _g9_decimals(step))
    return min(mx, max(mn, snapped))


def _g9_apply(param: dict, steps: int) -> float:
    """Apply `steps` one-step presses to the current value, clamping each step."""
    value = param["value"]
    direction = 1 if steps >= 0 else -1
    for _ in range(abs(steps)):
        value = _g9_clamp_step(value + direction * param["step"], param, 1)
    return value


def _g9_input(page, control_id: str):
    return page.locator(f'.stepper[data-control="{control_id}"]').locator("xpath=..").locator('input[type="number"]')


def _g9_button(page, control_id: str, direction: str):
    return page.locator(f'.stepper[data-control="{control_id}"] .step-btn[data-step="{direction}"]')


def _g9_reset(page, control_id: str, param: dict) -> None:
    inp = _g9_input(page, control_id)
    inp.scroll_into_view_if_needed(timeout=5000)
    inp.fill(str(param["min"]))
    inp.press("Enter")
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    param["value"] = param["min"]
    # Let the reset's debounced render run and finish before the burst starts,
    # so the burst measures input handling, not a render already in flight.
    page.wait_for_timeout(170)
    page.evaluate("() => window.__gc && window.__gc.renders")
    page.wait_for_timeout(30)


def _g9_click(page, control_id: str, direction: str, count: int, spacing_ms: int = 25) -> None:
    button = _g9_button(page, control_id, direction)
    button.scroll_into_view_if_needed(timeout=5000)
    box = button.bounding_box()
    if not box or box["width"] < 8 or box["height"] < 8:
        raise RuntimeError(f"stepper button {control_id}/{direction} has no usable box: {box}")
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    for _ in range(count):
        page.mouse.click(x, y)
        if spacing_ms:
            page.wait_for_timeout(spacing_ms)


def _g9_value(page, control_id: str) -> float:
    return float(_g9_input(page, control_id).input_value())


def _g9_check_value(page, control_id: str, param: dict, label: str, failures: list[str]) -> float:
    got = _g9_value(page, control_id)
    expected = param["value"]
    if abs(got - expected) > 1e-9:
        failures.append(f"{control_id} {label}: value {got!r} != expected {expected!r}")
    state_value = page.evaluate(G9_STATE_JS, control_id)
    if state_value is None or abs(float(state_value) - expected) > 1e-9:
        failures.append(f"{control_id} {label}: state {state_value!r} != expected {expected!r}")
    return got


def _g9_wait_render(page, before: int, failures: list[str], control_id: str, label: str) -> None:
    try:
        page.wait_for_function("n => window.__gc.renders > n", arg=before, timeout=20000)
    except Exception:
        failures.append(f"{control_id} {label}: no render after the gesture")


def g9_steppers() -> tuple[bool, list[str], str]:
    """Real-mouse acceptance test for every numeric control (H1)."""
    if not FIXTURE_4K.exists():
        make_png(FIXTURE_4K, width=4000, height=3000, seed=5)
    failures: list[str] = []
    summary: list[str] = []
    rates: list[str] = []

    def light_page(browser):
        context = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark")
        page = context.new_page()
        page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
        page.wait_for_timeout(400)
        page.set_input_files("#file-input", str(FIXTURE))
        page.wait_for_selector(".canvas-area.has-content", timeout=20000)
        page.wait_for_timeout(700)
        page.evaluate(EXPAND_SECTIONS_JS)
        page.wait_for_timeout(250)
        return context, page

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ---- light stack: every control, real 25 ms clicks ----
            context, page = light_page(browser)
            page_errors: list[str] = []
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            try:
                page.evaluate(G9_INSTRUMENT_JS)
                controls = page.evaluate(G9_CONTROLS_JS)
                bad = [c for c in controls if c.get("missing") or not c.get("up") or not c.get("down")]
                if bad:
                    failures.append(f"controls without both stepper buttons: {[c['id'] for c in bad]}")
                if len(controls) < 42:
                    failures.append(f"expected at least 42 numeric steppers, got {len(controls)}")
                effect_controls = [c for c in controls if c["id"].startswith("fx.")]
                if len(effect_controls) < 28:
                    failures.append(f"expected at least 28 effect steppers, got {len(effect_controls)}")
                if not controls:
                    return False, [
                        "no .stepper[data-control] groups: the numeric arrows are not a shared, testable control"
                    ], "0 controls"

                for param in controls:
                    if param.get("missing") or not param.get("up") or not param.get("down"):
                        continue
                    cid = param["id"]
                    if param["step"] <= 0:
                        failures.append(f"{cid}: non-positive step {param['step']}")
                        continue

                    # Two numeric controls are only visible in another mode or
                    # export format; switch through the real selects, then back.
                    switched = None
                    inp_handle = _g9_input(page, cid)
                    if not inp_handle.evaluate("el => !!(el.offsetWidth || el.offsetHeight)"):
                        if cid == "dither-depth-num":
                            page.select_option("#select-mode", "dither")
                            switched = ("#select-mode", "script")
                        elif cid == "jpg-quality-num":
                            page.select_option("#export-format", "jpg")
                            switched = ("#export-format", "png")
                        else:
                            failures.append(f"{cid}: control is not reachable in the real UI")
                            continue
                        page.wait_for_timeout(350)

                    # 1. 30 up-clicks then 30 down-clicks at 25 ms spacing.
                    _g9_reset(page, cid, param)
                    renders = page.evaluate("() => window.__gc.renders")
                    _g9_click(page, cid, "up", 30, 25)
                    param["value"] = _g9_apply(param, 30)
                    got = _g9_check_value(page, cid, param, "30 up", failures)
                    summary.append(f"{cid}=+30->{got:g}")
                    _g9_wait_render(page, renders, failures, cid, "30 up")
                    _g9_click(page, cid, "down", 30, 25)
                    param["value"] = _g9_apply(param, -30)
                    _g9_check_value(page, cid, param, "30 down", failures)

                    # 2. Mixed burst: 10 up, 5 down, 10 up, 3 down.
                    _g9_reset(page, cid, param)
                    for direction, count in (("up", 10), ("down", 5), ("up", 10), ("down", 3)):
                        _g9_click(page, cid, direction, count, 25)
                        param["value"] = _g9_apply(param, count if direction == "up" else -count)
                    _g9_check_value(page, cid, param, "mixed burst", failures)

                    # 3. Keyboard: 30 rapid ArrowUp, Shift+ArrowUp x10, PageUp x10.
                    _g9_reset(page, cid, param)
                    inp = _g9_input(page, cid)
                    inp.focus()
                    for _ in range(30):
                        page.keyboard.press("ArrowUp")
                    param["value"] = _g9_apply(param, 30)
                    _g9_check_value(page, cid, param, "30 ArrowUp", failures)
                    for _ in range(10):
                        page.keyboard.press("Shift+ArrowUp")
                    param["value"] = _g9_apply(param, 100)
                    _g9_check_value(page, cid, param, "10 Shift+ArrowUp", failures)
                    for _ in range(10):
                        page.keyboard.press("PageDown")
                    param["value"] = _g9_apply(param, -100)
                    _g9_check_value(page, cid, param, "10 PageDown", failures)

                    # 4. Wheel bursts: 30 ticks up, then 30 ticks down.
                    _g9_reset(page, cid, param)
                    inp.hover()
                    for _ in range(30):
                        page.mouse.wheel(0, -100)
                    param["value"] = _g9_apply(param, 30)
                    _g9_check_value(page, cid, param, "30 wheel up", failures)
                    for _ in range(30):
                        page.mouse.wheel(0, 100)
                    param["value"] = _g9_apply(param, -30)
                    _g9_check_value(page, cid, param, "30 wheel down", failures)

                    if switched:
                        page.select_option(switched[0], switched[1])
                        page.wait_for_timeout(300)

                # 9. Extreme speed on three contrasting controls.
                by_id = {c["id"]: c for c in controls}
                extreme_ids = [cid for cid in ("adj-brightness-num", "fx.blur.radius", "fx.halftone.size") if cid in by_id]
                for cid in extreme_ids:
                    param = by_id[cid]
                    _g9_reset(page, cid, param)
                    box = _g9_button(page, cid, "up").bounding_box()
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    page.mouse.move(x, y)
                    for _ in range(100):
                        page.mouse.click(x, y)
                    param["value"] = _g9_apply(param, 100)
                    _g9_check_value(page, cid, param, "100 clicks at 0-10 ms", failures)

                    # Double and triple click on the arrow itself. down/up with
                    # an increasing click count is exactly what a real
                    # double/triple click sends (one pointerdown per click).
                    for clicks, expected_steps in ((2, 2), (3, 3)):
                        _g9_reset(page, cid, param)
                        box = _g9_button(page, cid, "up").bounding_box()
                        x = box["x"] + box["width"] / 2
                        y = box["y"] + box["height"] / 2
                        page.mouse.move(x, y)
                        for n in range(1, clicks + 1):
                            page.mouse.down(click_count=n)
                            page.mouse.up(click_count=n)
                            if n < clicks:
                                page.wait_for_timeout(20)
                        param["value"] = _g9_apply(param, expected_steps)
                        _g9_check_value(page, cid, param, f"double/triple click ({clicks} clicks)", failures)

                    # Click then immediately hold: every applied step is visible.
                    _g9_reset(page, cid, param)
                    page.wait_for_timeout(200)
                    box = _g9_button(page, cid, "up").bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.wait_for_timeout(600)
                    page.mouse.up()
                    page.wait_for_timeout(150)
                    total = page.evaluate("() => window.__gc.writes - window.__gc.writesAtDown")
                    if total < 5:
                        failures.append(f"{cid} click-then-hold: only {total} value writes")
                    param["value"] = _g9_apply(param, total)
                    _g9_check_value(page, cid, param, f"click-then-hold ({total} steps)", failures)

                # 8. Input latency on an idle light stack.
                cid = "adj-brightness-num"
                if cid in by_id:
                    _g9_reset(page, cid, by_id[cid])
                    page.wait_for_timeout(300)
                    box = _g9_button(page, cid, "up").bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.mouse.up()
                    latency = page.evaluate("() => window.__gc.lastWrite - window.__gc.downT")
                    summary.append(f"latency={latency:.2f}ms")
                    if latency > 16:
                        failures.append(f"{cid}: pointerdown->display latency {latency:.2f}ms > 16ms")

                if page_errors:
                    failures.extend(f"page error: {e}" for e in page_errors)
            finally:
                context.close()

            # ---- 7. Hold rate: 1 s, 2 s, 3 s on five controls ----
            hold_ids = ["adj-brightness-num", "adj-contrast-num", "adj-hue-num", "depth-num", "cell-size-num"]
            context, page = light_page(browser)
            try:
                page.evaluate(G9_INSTRUMENT_JS)
                controls = {c["id"]: c for c in page.evaluate(G9_CONTROLS_JS)}
                for cid in hold_ids:
                    if cid not in controls:
                        failures.append(f"{cid}: hold-rate control is missing")
                        continue
                    param = controls[cid]
                    for seconds in (1, 2, 3):
                        _g9_reset(page, cid, param)
                        page.wait_for_timeout(300)
                        box = _g9_button(page, cid, "up").bounding_box()
                        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        page.mouse.down()
                        page.wait_for_timeout(seconds * 1000)
                        page.mouse.up()
                        page.wait_for_timeout(180)
                        data = page.evaluate("() => ({times: window.__gc.times.slice(window.__gc.writesAtDown), downT: window.__gc.downT})")
                        times = data["times"]
                        if len(times) < 3:
                            failures.append(f"{cid} hold {seconds}s: only {len(times)} steps")
                            continue
                        delay = times[1] - data["downT"]
                        intervals = [b - a for a, b in zip(times[1:], times[2:])]
                        intervals.sort()
                        median = intervals[len(intervals) // 2]
                        rate = 1000.0 / median if median > 0 else 0
                        rate_text = f"{cid} {seconds}s: delay={delay:.0f}ms rate={rate:.1f}/s steps={len(times)}"
                        summary.append(rate_text)
                        rates.append(rate_text)
                        if not (280 <= delay <= 520):
                            failures.append(f"{cid} hold {seconds}s: initial delay {delay:.0f}ms outside 300-500ms")
                        if not (15 <= rate <= 30):
                            failures.append(f"{cid} hold {seconds}s: repeat rate {rate:.1f}/s outside 15-30/s")
                        expected = _g9_apply(param, len(times))
                        got = _g9_value(page, cid)
                        if abs(got - expected) > 1e-9:
                            failures.append(f"{cid} hold {seconds}s: value {got!r} != {expected!r} after {len(times)} steps")
            finally:
                context.close()

            # ---- 5. Heavy stack on a 4000x3000 image ----
            context = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark")
            page = context.new_page()
            heavy_errors: list[str] = []
            page.on("pageerror", lambda exc: heavy_errors.append(str(exc)))
            try:
                page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
                page.wait_for_timeout(400)
                page.set_input_files("#file-input", str(FIXTURE_4K))
                page.wait_for_selector(".canvas-area.has-content", timeout=30000)
                page.wait_for_timeout(1200)
                page.evaluate(EXPAND_SECTIONS_JS)
                page.select_option("#export-format", "jpg")
                names = page.evaluate("() => Object.fromEntries(EFFECTS.map(e => [e.id, e.name]))")
                heavy = [("halftone", "size", 14), ("posterize", "levels", 2), ("edges", "amount", 100),
                         ("emboss", "amount", 100), ("blur", "radius", 8), ("sharpen", "amount", 100)]
                for effect_id, key, value in heavy:
                    name = names[effect_id]
                    page.locator(f'.effect-item input[type="checkbox"][aria-label="Enable {name}"]').check()
                    inp = _g9_input(page, f"fx.{effect_id}.{key}")
                    inp.scroll_into_view_if_needed(timeout=5000)
                    inp.fill(str(value))
                    inp.press("Enter")
                    page.evaluate("() => document.activeElement && document.activeElement.blur()")
                page.wait_for_timeout(3000)
                page.evaluate(G9_INSTRUMENT_JS)
                controls = {c["id"]: c for c in page.evaluate(G9_CONTROLS_JS)}
                heavy_ids = ["adj-brightness-num", "adj-hue-num", "depth-num", "fx.blur.radius",
                             "fx.sharpen.amount", "fx.halftone.size", "fx.posterize.levels", "jpg-quality-num"]
                for cid in heavy_ids:
                    if cid not in controls:
                        failures.append(f"{cid}: heavy-stack control is missing")
                        continue
                    param = controls[cid]
                    _g9_reset(page, cid, param)
                    _g9_click(page, cid, "up", 30, 25)
                    param["value"] = _g9_apply(param, 30)
                    _g9_check_value(page, cid, param, "heavy 30 up", failures)
                    _g9_click(page, cid, "down", 30, 25)
                    param["value"] = _g9_apply(param, -30)
                    _g9_check_value(page, cid, param, "heavy 30 down", failures)
                    _g9_reset(page, cid, param)
                    for direction, count in (("up", 10), ("down", 5), ("up", 10), ("down", 3)):
                        _g9_click(page, cid, direction, count, 25)
                        param["value"] = _g9_apply(param, count if direction == "up" else -count)
                    _g9_check_value(page, cid, param, "heavy mixed burst", failures)

                # Latency with a slow render pending is measured on an idle stack only:
                # a synchronous render blocks event dispatch, which no input handler can avoid.
                for cid in ("adj-brightness-num", "fx.blur.radius"):
                    if cid not in controls:
                        failures.append(f"{cid}: heavy latency control is missing")
                        continue
                    param = controls[cid]
                    _g9_reset(page, cid, param)
                    page.wait_for_timeout(2500)
                    box = _g9_button(page, cid, "up").bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.mouse.up()
                    latency = page.evaluate("() => window.__gc.lastWrite - window.__gc.downT")
                    summary.append(f"heavy latency {cid}={latency:.2f}ms")
                    if latency > 16:
                        failures.append(f"{cid}: heavy pointerdown->display latency {latency:.2f}ms > 16ms")

                # Hold rates with the heavy stack.
                for cid in hold_ids:
                    if cid not in controls:
                        failures.append(f"{cid}: heavy hold control is missing")
                        continue
                    param = controls[cid]
                    _g9_reset(page, cid, param)
                    page.wait_for_timeout(300)
                    box = _g9_button(page, cid, "up").bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.wait_for_timeout(3000)
                    page.mouse.up()
                    page.wait_for_timeout(180)
                    data = page.evaluate("() => ({times: window.__gc.times.slice(window.__gc.writesAtDown), downT: window.__gc.downT})")
                    times = data["times"]
                    if len(times) < 3:
                        failures.append(f"{cid} heavy hold: only {len(times)} steps")
                        continue
                    intervals = sorted(b - a for a, b in zip(times[1:], times[2:]))
                    median = intervals[len(intervals) // 2]
                    rate = 1000.0 / median if median > 0 else 0
                    summary.append(f"heavy {cid} 3s: rate={rate:.1f}/s steps={len(times)}")
                    if not (15 <= rate <= 30):
                        failures.append(f"{cid} heavy hold: repeat rate {rate:.1f}/s outside 15-30/s")
                    expected = _g9_apply(param, len(times))
                    got = _g9_value(page, cid)
                    if abs(got - expected) > 1e-9:
                        failures.append(f"{cid} heavy hold: value {got!r} != {expected!r} after {len(times)} steps")
                if heavy_errors:
                    failures.extend(f"heavy page error: {e}" for e in heavy_errors)
            finally:
                context.close()
        finally:
            browser.close()

    detail = f"{len(summary)} measurements, {len(rates)} hold-rate rows"
    return not failures, failures, detail


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

BASE_URL = ""


# ---------------------------------------------------------------------------
# G10 - effects: sketch acceptance + every effect at its range ends (H2)
# ---------------------------------------------------------------------------

def g10_effects() -> tuple[bool, list[str], str]:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "effects_sweep.py"),
             "--only", "all", "--quick"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/effects_sweep.py: timed out after 1800s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if "checks," in line and "failure" in line), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/effects_sweep.py exited {proc.returncode}")
    match = re.search(r"(\d+) checks, (\d+) failure", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 30:
        problems.append(f"effects sweep ran only {checks} checks")
    if "EFFECTS SWEEP PASS" not in output:
        problems.append("effects sweep did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems[:40], detail


# ---------------------------------------------------------------------------
# G11 - compare split: cache, handle grab, drag frames, split correctness (H3)
# ---------------------------------------------------------------------------

def g11_compare() -> tuple[bool, list[str], str]:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "compare_check.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/compare_check.py: timed out after 1800s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if "checks," in line and "failure" in line), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/compare_check.py exited {proc.returncode}")
    match = re.search(r"(\d+) checks, (\d+) failure", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 20:
        problems.append(f"compare check ran only {checks} checks")
    if "COMPARE PASS" not in output:
        problems.append("compare check did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems[:40], detail


# ---------------------------------------------------------------------------
# G12 - load: idle, coalescing, stage cache, identity, memory, cached gain (H4)
# ---------------------------------------------------------------------------

def g12_load() -> tuple[bool, list[str], str]:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "load_check.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=2400,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/load_check.py: timed out after 2400s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if "checks," in line and "failure" in line), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/load_check.py exited {proc.returncode}")
    match = re.search(r"(\d+) checks, (\d+) failure", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 15:
        problems.append(f"load check ran only {checks} checks")
    if "LOAD PASS" not in output:
        problems.append("load check did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems[:40], detail


def g13_video() -> tuple[bool, list[str], str]:
    """Part 1C: playback cost, allocation rate, play/pause control contract,
    hidden-tab resume, export state, listener/heap stability, idle regressions."""
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "video_check.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=2400,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/video_check.py: timed out after 2400s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if "checks," in line and "failure" in line), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/video_check.py exited {proc.returncode}")
    match = re.search(r"(\d+) checks, (\d+) failure", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 25:
        problems.append(f"video check ran only {checks} checks")
    if "VIDEO PASS" not in output:
        problems.append("video check did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems[:40], detail


# ---------------------------------------------------------------------------
# G14-G17 - mobile sheet, gestures, touch targets, desktop guard
# ---------------------------------------------------------------------------

MOBILE_SHEET_JS = r"""
() => {
  const panel = document.getElementById('panel');
  const area = document.getElementById('canvas-area');
  const canvas = document.getElementById('canvas');
  const handle = document.getElementById('sheet-handle');
  const status = document.getElementById('status-bar');
  const vv = window.visualViewport;
  const pr = panel.getBoundingClientRect();
  const ar = area.getBoundingClientRect();
  const cr = canvas.getBoundingClientRect();
  const hr = handle ? handle.getBoundingClientRect() : null;
  const cx = cr.left + cr.width / 2;
  const cy = cr.top + cr.height / 2;
  const hit = document.elementFromPoint(cx, cy);
  const segs = status ? Array.from(status.querySelectorAll('.status-seg')) : [];
  const visibleSegs = segs.filter(seg => !seg.hidden && getComputedStyle(seg).display !== 'none');
  const bar = document.querySelector('.menubar');
  const barRect = bar.getBoundingClientRect();
  const rows = [];
  for (const el of bar.querySelectorAll('.menubar-left, .menubar-right > *')) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    const center = r.top + r.height / 2;
    if (!rows.some(row => Math.abs(row - center) < 12)) rows.push(center);
  }
  return {
    viewport: {w: innerWidth, h: innerHeight, vvW: vv ? vv.width : innerWidth, vvH: vv ? vv.height : innerHeight},
    topbar: {height: barRect.height, rows: rows.length, width: barRect.width},
    sheet: {x: pr.x, top: pr.top, bottom: pr.bottom, width: pr.width, height: pr.height,
            snap: panel.dataset.snap || '', bottomGap: innerHeight - pr.bottom},
    preview: {x: ar.x, top: ar.top, bottom: ar.bottom, width: ar.width, height: ar.height, left: ar.left, right: ar.right},
    canvas: {left: cr.left, top: cr.top, right: cr.right, bottom: cr.bottom, width: cr.width, height: cr.height},
    centerHit: hit ? {id: hit.id || '', tag: hit.tagName.toLowerCase(), canvas: hit === canvas || hit.closest && hit.closest('#canvas') !== null} : null,
    handle: hr ? {top: hr.top, bottom: hr.bottom, width: hr.width, height: hr.height,
                  role: handle.getAttribute('role'), valuenow: handle.getAttribute('aria-valuenow'),
                  valuemin: handle.getAttribute('aria-valuemin'), valuemax: handle.getAttribute('aria-valuemax'),
                  tabindex: handle.getAttribute('tabindex')} : null,
    status: {inSheet: !!(status && panel.contains(status)), inHandle: !!(status && handle && handle.contains(status)),
             segs: segs.length, visible: visibleSegs.length, text: (status ? status.textContent : '').trim()},
    overflowX: document.documentElement.scrollWidth - innerWidth,
    docScroll: (document.scrollingElement || document.documentElement).scrollTop,
    bodyScroll: document.body.scrollTop,
    contentScroll: (document.querySelector('.panel-content') || {}).scrollTop || 0
  };
}
"""

MOBILE_INSTRUMENT_JS = r"""
() => {
  if (window.__mp) return;
  const P = window.__mp = {renders: 0, base: 0};
  const r = window.render;
  window.render = function () { P.renders += 1; return r.apply(this, arguments); };
  const b = window.prepareBase;
  if (typeof b === 'function') {
    window.prepareBase = function () { P.base += 1; return b.apply(this, arguments); };
  }
}
"""


def mobile_context(browser, width: int, height: int, theme: str, reduce: bool = True):
    return browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=theme,
        locale="en-US",
        reduced_motion="reduce" if reduce else "no-preference",
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2,
    )


def mobile_open(browser, width: int, height: int, theme: str, image: bool = True,
                effects: int = 0, reduce: bool = True):
    ctx = mobile_context(browser, width, height, theme, reduce)
    ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','%s')}catch(e){}" % theme)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
    page.wait_for_timeout(450)
    if image:
        before = page.evaluate("() => state.sourceId")
        page.set_input_files("#file-input", str(FIXTURE))
        page.wait_for_selector(".canvas-area.has-content", timeout=30000)
        page.wait_for_function("(id) => state.sourceId > id", arg=before, timeout=30000)
        page.wait_for_timeout(700)
    if effects:
        page.evaluate(
            """(n) => {
              state.opts.effects = EFFECTS.slice(0, n).map(effect => ({
                id: effect.id, enabled: true, params: effectDefaults(effect.id)
              }));
              renderEffectsList();
              scheduleRender(0);
            }""", effects)
        page.wait_for_timeout(1200)
    page.wait_for_timeout(350)
    return ctx, page, errors


def cdp_touch_start(client, x: float, y: float) -> None:
    client.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": x, "y": y, "id": 1, "radiusX": 2, "radiusY": 2}],
    })


def cdp_touch_move(client, x: float, y: float) -> None:
    client.send("Input.dispatchTouchEvent", {
        "type": "touchMove",
        "touchPoints": [{"x": x, "y": y, "id": 1, "radiusX": 2, "radiusY": 2}],
    })


def cdp_touch_end(client) -> None:
    client.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def touch_swipe(client, page, x: float, y1: float, y2: float, steps: int = 12,
                step_ms: int = 16) -> None:
    cdp_touch_start(client, x, y1)
    page.wait_for_timeout(step_ms)
    for i in range(1, steps + 1):
        cdp_touch_move(client, x, y1 + (y2 - y1) * i / steps)
        page.wait_for_timeout(step_ms)
    cdp_touch_end(client)
    page.wait_for_timeout(520)


def touch_tap(client, page, x: float, y: float) -> None:
    cdp_touch_start(client, x, y)
    page.wait_for_timeout(40)
    cdp_touch_end(client)
    page.wait_for_timeout(500)


def mobile_snap(page) -> str:
    return page.evaluate("() => document.getElementById('panel').dataset.snap || ''")


def mobile_measure(page) -> dict:
    return page.evaluate(MOBILE_SHEET_JS)


def set_mobile_snap(page, snap: str) -> None:
    page.evaluate("(snap) => { if (window.__gcSetSnap) window.__gcSetSnap(snap, false); }", snap)
    page.wait_for_timeout(420)


def g14_mobile_layout() -> tuple[bool, list[str], list[str]]:
    problems: list[str] = []
    detail: list[str] = []
    shots: list[str] = []
    cells = [
        (360, 680, "dark", True, 22),
        (390, 750, "light", True, 22),
        (412, 800, "dark", False, 0),
        (320, 568, "light", True, 0),
        (640, 360, "dark", True, 0),
        (740, 360, "light", True, 0),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width, height, theme, image, effects in cells:
                ctx, page, errors = mobile_open(browser, width, height, theme, image, effects)
                try:
                    cell = f"{theme} {width}x{height}"
                    if errors:
                        problems.extend(f"{cell} page error: {e}" for e in errors)
                    data = mobile_measure(page)
                    mobile = width <= 700
                    if data["overflowX"] > 1:
                        problems.append(f"{cell}: horizontal overflow {data['overflowX']}px")
                    if data["docScroll"] != 0 or data["bodyScroll"] != 0:
                        problems.append(f"{cell}: page scroll {data['docScroll']}/{data['bodyScroll']}")
                    if mobile:
                        if not data["status"]["inSheet"]:
                            problems.append(f"{cell}: status box is not inside the sheet")
                        if not data["status"]["inHandle"]:
                            problems.append(f"{cell}: status box is not inside the sheet handle")
                        if image and data["status"]["visible"] != 3:
                            problems.append(f"{cell}: expected 3 visible status segments, got {data['status']['visible']}")
                        if not data["handle"]:
                            problems.append(f"{cell}: sheet handle missing")
                        else:
                            h = data["handle"]
                            if h["role"] != "separator":
                                problems.append(f"{cell}: handle role={h['role']!r}")
                            if h["valuenow"] is None or h["valuemin"] is None or h["valuemax"] is None:
                                problems.append(f"{cell}: handle aria-valuenow/min/max missing {h}")
                            if h["tabindex"] != "0":
                                problems.append(f"{cell}: handle is not keyboard focusable")
                        if data["sheet"]["bottomGap"] > 1:
                            problems.append(f"{cell}: sheet bottom gap {data['sheet']['bottomGap']:.1f}px")
                        if data["preview"]["bottom"] > data["sheet"]["top"] + 1:
                            problems.append(f"{cell}: sheet overlaps preview by {data['preview']['bottom'] - data['sheet']['top']:.1f}px")
                        if data["preview"]["height"] < 1:
                            problems.append(f"{cell}: preview region has no height")
                        cr, ar = data["canvas"], data["preview"]
                        if image and ar["height"] > 1 and (cr["left"] < ar["left"] - 1 or cr["right"] > ar["right"] + 1
                                                           or cr["top"] < ar["top"] - 1 or cr["bottom"] > ar["bottom"] + 1):
                            problems.append(f"{cell}: canvas {cr} is not inside preview {ar}")
                        if image and ar["height"] > 1 and not (data["centerHit"] or {}).get("canvas"):
                            problems.append(f"{cell}: canvas center hit {data['centerHit']}")
                        if image and data["sheet"]["snap"] != "peek":
                            problems.append(f"{cell}: image load default snap is {data['sheet']['snap']!r}, expected peek")
                        if not image and data["sheet"]["snap"] != "half":
                            problems.append(f"{cell}: empty state snap is {data['sheet']['snap']!r}, expected half")
                        if height < 500 and data["preview"]["height"] < 120:
                            problems.append(f"{cell}: landscape peek preview {data['preview']['height']:.1f}px < 120px")
                        single_row = page.evaluate("() => !!document.getElementById('mobile-menu-btn')")
                        if single_row:
                            if data["topbar"]["height"] > 57:
                                problems.append(f"{cell}: mobile top bar {data['topbar']['height']:.1f}px > 56px")
                            if data["topbar"]["rows"] != 1:
                                problems.append(f"{cell}: mobile top bar has {data['topbar']['rows']} rows")
                            if height >= 500 and image and data["sheet"]["snap"] == "peek":
                                frac = data["preview"]["height"] / max(1, data["viewport"]["vvH"])
                                if frac < 0.70:
                                    problems.append(f"{cell}: peek preview fraction {frac:.3f} < 0.70")
                    path = EVIDENCE / f"m1-g14-{theme}-{width}x{height}-{data['sheet']['snap'] or 'none'}.png"
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path))
                    shots.append(str(path.relative_to(ROOT)))
                    # Half snap: sheet grows, preview shrinks, still no overlap.
                    if width <= 700:
                        base = data
                        if not image:
                            set_mobile_snap(page, "peek")
                            base = mobile_measure(page)
                        set_mobile_snap(page, "half")
                        half = mobile_measure(page)
                        if half["sheet"]["height"] <= base["sheet"]["height"] + 1:
                            problems.append(f"{cell}: half sheet did not grow ({base['sheet']['height']:.1f} -> {half['sheet']['height']:.1f})")
                        if half["preview"]["height"] >= base["preview"]["height"]:
                            problems.append(f"{cell}: preview did not shrink when the sheet grew")
                        if half["preview"]["bottom"] > half["sheet"]["top"] + 1:
                            problems.append(f"{cell}: half sheet overlaps preview")
                        if half["overflowX"] > 1:
                            problems.append(f"{cell}: half snap horizontal overflow {half['overflowX']}px")
                        if page.evaluate("() => !!document.getElementById('mobile-menu-btn')") and height >= 500:
                            frac = half["preview"]["height"] / max(1, half["viewport"]["vvH"])
                            if frac < 0.40:
                                problems.append(f"{cell}: half preview fraction {frac:.3f} < 0.40")
                        path = EVIDENCE / f"m1-g14-{theme}-{width}x{height}-half.png"
                        EVIDENCE.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(path))
                        shots.append(str(path.relative_to(ROOT)))
                    elif width > 700:
                        if data["sheet"]["x"] < width - 1:
                            problems.append(f"{cell}: desktop-branch panel should stay in its column/overlay, got x={data['sheet']['x']:.1f}")
                    detail.append(f"{cell}: snap={data['sheet']['snap']} sheet={data['sheet']['height']:.0f}px "
                                  f"preview={data['preview']['height']:.0f}px topbar={data['topbar']['height']:.0f}px/{data['topbar']['rows']}row")
                finally:
                    ctx.close()
        finally:
            browser.close()
    return not problems, problems, detail + shots


def g15_mobile_gestures() -> tuple[bool, list[str], str]:
    problems: list[str] = []
    detail: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page, errors = mobile_open(browser, 360, 680, "dark", True, 0)
        client = ctx.new_cdp_session(page)
        try:
            page.evaluate(MOBILE_INSTRUMENT_JS)
            if errors:
                problems.extend(f"page error: {e}" for e in errors)
            if mobile_snap(page) != "peek":
                problems.append(f"start snap {mobile_snap(page)!r}, expected peek")
            handle = page.locator("#sheet-handle").bounding_box()
            if not handle:
                return False, ["sheet handle has no box"], "no handle"

            def handle_center():
                box = page.locator("#sheet-handle").bounding_box()
                return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

            hx, hy = handle_center()
            touch_swipe(client, page, hx, hy, hy - 190, 14, 16)
            s1 = mobile_snap(page)
            if s1 != "half":
                problems.append(f"swipe up from peek landed on {s1!r}")
            hx, hy = handle_center()
            touch_swipe(client, page, hx, hy, hy + 190, 14, 16)
            s2 = mobile_snap(page)
            if s2 != "peek":
                problems.append(f"swipe down from half landed on {s2!r}")
            hx, hy = handle_center()
            touch_swipe(client, page, hx, hy, hy - 90, 4, 10)
            s3 = mobile_snap(page)
            if s3 == "peek":
                problems.append("fast flick up did not leave peek")
            detail.append(f"swipes peek->{s1}->{s2}, flick->{s3}")

            set_mobile_snap(page, "peek")
            cycle = []
            for _ in range(3):
                grip = page.locator("#sheet-grip").bounding_box() or page.locator("#sheet-handle").bounding_box()
                gx = grip["x"] + grip["width"] / 2
                gy = grip["y"] + grip["height"] / 2
                touch_tap(client, page, gx, gy)
                cycle.append(mobile_snap(page))
            if cycle != ["half", "full", "peek"]:
                problems.append(f"grabber tap cycle {cycle}, expected ['half','full','peek']")
            detail.append("tap cycle " + ",".join(cycle))

            # List scroll must not move the sheet and must not leak to the page.
            set_mobile_snap(page, "full")
            content = page.locator(".panel-content").bounding_box()
            sheet_before = mobile_measure(page)["sheet"]["height"]
            scroll_before = page.evaluate("() => document.querySelector('.panel-content').scrollTop")
            cx = content["x"] + content["width"] / 2
            cy = content["y"] + content["height"] * 0.72
            touch_swipe(client, page, cx, cy, cy - 150, 12, 16)
            sheet_after = mobile_measure(page)["sheet"]["height"]
            scroll_after = page.evaluate("() => document.querySelector('.panel-content').scrollTop")
            if abs(sheet_after - sheet_before) > 1:
                problems.append(f"list scroll moved the sheet {sheet_before:.1f}->{sheet_after:.1f}")
            if scroll_after <= scroll_before:
                problems.append(f"list did not scroll inside the sheet ({scroll_before}->{scroll_after})")
            if mobile_measure(page)["docScroll"] != 0:
                problems.append("page scrolled during list scroll")

            # Handle drag must move the sheet and leave the list scroll alone.
            page.evaluate("() => { document.querySelector('.panel-content').scrollTop = 220; }")
            page.wait_for_timeout(120)
            list_before = page.evaluate("() => document.querySelector('.panel-content').scrollTop")
            hx, hy = handle_center()
            touch_swipe(client, page, hx, hy, hy + 60, 10, 16)
            list_after = page.evaluate("() => document.querySelector('.panel-content').scrollTop")
            if abs(list_after - list_before) > 1:
                problems.append(f"handle drag scrolled the list {list_before}->{list_after}")

            # Pipeline: zero during drag, at most one render/base after settle.
            set_mobile_snap(page, "peek")
            page.evaluate("() => { window.__mp.renders = 0; window.__mp.base = 0; }")
            hx, hy = handle_center()
            cdp_touch_start(client, hx, hy + 10)
            page.wait_for_timeout(30)
            for i in range(1, 13):
                cdp_touch_move(client, hx, hy + 10 - i * 14)
                page.wait_for_timeout(16)
            during = page.evaluate("() => ({r: window.__mp.renders, b: window.__mp.base})")
            cdp_touch_end(client)
            page.wait_for_timeout(900)
            after = page.evaluate("() => ({r: window.__mp.renders, b: window.__mp.base})")
            if during["r"] or during["b"]:
                problems.append(f"pipeline ran during drag: render={during['r']} base={during['b']}")
            if after["r"] - during["r"] > 1 or after["b"] - during["b"] > 1:
                problems.append(f"pipeline after settle: render+{after['r'] - during['r']} base+{after['b'] - during['b']}")
            detail.append(f"pipeline during={during} after={after}")

            # Soft keyboard: shrink the visual viewport and keep the focused field visible.
            set_mobile_snap(page, "full")
            page.focus("#depth-num")
            page.wait_for_timeout(250)
            client.send("Emulation.setDeviceMetricsOverride", {
                "width": 360, "height": 400, "deviceScaleFactor": 2,
                "mobile": True, "screenWidth": 360, "screenHeight": 680,
            })
            page.wait_for_timeout(650)
            kb = page.evaluate("""() => {
              const el = document.getElementById('depth-num');
              const r = el.getBoundingClientRect();
              const vv = window.visualViewport;
              const pc = document.querySelector('.panel-content').getBoundingClientRect();
              return {top:r.top, bottom:r.bottom, left:r.left, right:r.right,
                      vvH: vv ? vv.height : innerHeight, vvW: vv ? vv.width : innerWidth,
                      pcTop: pc.top, pcBottom: pc.bottom, active: document.activeElement === el};
            }""")
            if not kb["active"]:
                problems.append("focused input lost focus when the keyboard opened")
            if kb["bottom"] > kb["vvH"] + 1 or kb["top"] < -1:
                problems.append(f"focused input not visible above the keyboard: {kb}")
            if kb["bottom"] > kb["pcBottom"] + 1:
                problems.append(f"focused input outside the sheet list viewport: {kb}")
            client.send("Emulation.clearDeviceMetricsOverride")
            page.wait_for_timeout(500)
            detail.append(f"keyboard vvH={kb['vvH']:.0f} input={kb['top']:.0f}..{kb['bottom']:.0f}")

            # Compare split handle by touch, 20/20 at three zooms.
            set_mobile_snap(page, "peek")
            page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
            page.keyboard.press("c")
            page.wait_for_timeout(500)
            if not page.evaluate("() => state.compare"):
                problems.append("compare did not turn on before the touch test")
            compare_runs = []
            for zoom in (1, 2, 4):
                page.evaluate("(z) => setZoom(z)", zoom)
                page.wait_for_timeout(500)
                grabbed = 0
                for n in range(20):
                    geom = page.evaluate("""() => {
                      const s = document.getElementById('compare-slider').getBoundingClientRect();
                      const a = document.getElementById('canvas-area').getBoundingClientRect();
                      return {sl: s.left, sr: s.right, st: s.top, sb: s.bottom, sw: s.width,
                              at: a.top, ab: a.bottom, al: a.left, ar: a.right};
                    }""")
                    lo = max(geom["st"], geom["at"]) + 4
                    hi = min(geom["sb"], geom["ab"]) - 4
                    sx = (geom["sl"] + geom["sr"]) / 2
                    if hi <= lo or sx < geom["al"] or sx > geom["ar"]:
                        break
                    sy = lo + (hi - lo) * (0.25 + 0.5 * ((n % 5) / 4))
                    before = page.evaluate("() => state.compareFrac")
                    dx = 26 if n % 2 == 0 else -26
                    cdp_touch_start(client, sx, sy)
                    page.wait_for_timeout(30)
                    cdp_touch_move(client, sx + dx * 0.5, sy)
                    page.wait_for_timeout(20)
                    cdp_touch_move(client, sx + dx, sy)
                    page.wait_for_timeout(20)
                    cdp_touch_end(client)
                    page.wait_for_timeout(120)
                    after = page.evaluate("() => state.compareFrac")
                    if abs(after - before) > 0.0005:
                        grabbed += 1
                compare_runs.append((zoom, grabbed))
                if grabbed != 20:
                    problems.append(f"touch compare grab {zoom * 100}%: {grabbed}/20")
            page.evaluate("() => { if (state.compare) { state.compare = false; scheduleRender(0); } }")
            detail.append("compare " + ", ".join(f"{z*100}%={g}/20" for z, g in compare_runs))
        finally:
            ctx.close()
            browser.close()
    return not problems, problems, " | ".join(detail)


def g16_touch_targets() -> tuple[bool, list[str], str]:
    problems: list[str] = []
    detail: list[str] = []
    collect_js = r"""
    () => {
      const sel = 'button, select, input:not([type="hidden"]), textarea, a[href], [role="separator"], [role="button"], [role="menuitem"], [data-step], .palette-swatch';
      const seen = new Set();
      const out = [];
      for (const el of document.querySelectorAll(sel)) {
        if (!el.closest('.menubar, #panel')) continue;
        if (seen.has(el)) continue;
        seen.add(el);
        if (el.disabled) continue;
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden) continue;
        if (cs.pointerEvents === 'none' || parseFloat(cs.opacity) === 0) continue;
        if (el.getAttribute('aria-hidden') === 'true') continue;
        if (el.classList.contains('preset-native')) continue;
        if (el.closest('[hidden]')) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 0.5 || r.height < 0.5) continue;
        if (el.offsetParent === null) continue;
        out.push({
          name: el.id || el.className || el.tagName.toLowerCase(),
          tag: el.tagName.toLowerCase(),
          text: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
          w: +r.width.toFixed(1), h: +r.height.toFixed(1),
          scope: el.closest('.menubar') ? 'topbar' : 'sheet'
        });
      }
      return out;
    }
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page, errors = mobile_open(browser, 360, 680, "dark", True, 0)
        try:
            page.evaluate(EXPAND_SECTIONS_JS)
            page.wait_for_timeout(400)
            if errors:
                problems.extend(f"page error: {e}" for e in errors)
            seen: dict[tuple, dict] = {}
            for snap in ("peek", "half", "full"):
                set_mobile_snap(page, snap)
                items = page.evaluate(collect_js)
                detail.append(f"{snap}:{len(items)}")
                for item in items:
                    key = (item["name"], item["text"], item["tag"])
                    seen.setdefault(key, item)
                    if item["w"] < 44 - 0.5 or item["h"] < 44 - 0.5:
                        problems.append(f"{snap} {item['scope']} {item['tag']} {item['name']!r} {item['text']!r} is {item['w']}x{item['h']}, needs >=44x44")
            detail.append(f"unique={len(seen)}")
            # Once more with every section expanded and the effects list populated.
            page.evaluate(SETUP_EFFECTS_JS)
            page.evaluate(EXPAND_SECTIONS_JS)
            page.wait_for_timeout(900)
            set_mobile_snap(page, "full")
            items = page.evaluate(collect_js)
            for item in items:
                key = (item["name"], item["text"], item["tag"])
                seen.setdefault(key, item)
                if item["w"] < 44 - 0.5 or item["h"] < 44 - 0.5:
                    problems.append(f"full+effects {item['scope']} {item['tag']} {item['name']!r} {item['text']!r} is {item['w']}x{item['h']}, needs >=44x44")
            detail.append(f"unique+effects={len(seen)}")
        finally:
            ctx.close()
            browser.close()
    return not problems, problems, " ".join(detail)


def g17_desktop_unchanged() -> tuple[bool, list[str], str]:
    baseline_path = Path(__file__).with_name("desktop_baseline.json")
    if not baseline_path.exists():
        return False, [f"missing {baseline_path}"], "no baseline"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    sels = {"menubar": ".menubar", "panel": "#panel", "preview": "#canvas-area",
            "status": "#status-bar", "zoom": ".zoom-controls"}
    fix = """() => {
      document.getElementById('status-zoom').textContent = '100%';
      document.getElementById('status-size').textContent = '320×240';
      document.getElementById('status-time').textContent = '100ms';
    }"""
    rects_js = """(sels) => {
      const out = {};
      for (const [k, sel] of Object.entries(sels)) {
        const el = document.querySelector(sel);
        if (!el) { out[k] = null; continue; }
        const r = el.getBoundingClientRect();
        out[k] = {x:+r.x.toFixed(2), y:+r.y.toFixed(2), w:+r.width.toFixed(2), h:+r.height.toFixed(2)};
      }
      return out;
    }"""
    problems: list[str] = []
    checked = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for size in ("1280x720", "701x800"):
                width, height = (int(v) for v in size.split("x"))
                ctx = browser.new_context(viewport={"width": width, "height": height},
                                          color_scheme="dark", locale="en-US", reduced_motion="reduce")
                ctx.add_init_script("try{localStorage.setItem('glyphcraft-theme','dark')}catch(e){}")
                page = ctx.new_page()
                try:
                    page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
                    page.wait_for_timeout(400)
                    page.set_input_files("#file-input", str(FIXTURE))
                    page.wait_for_selector(".canvas-area.has-content", timeout=30000)
                    page.wait_for_timeout(700)
                    states = [("closed", None)]
                    if width == 701:
                        states.append(("open", "#panel-toggle-btn"))
                    for state, click in states:
                        if click:
                            page.click(click)
                            page.wait_for_timeout(400)
                        page.evaluate(fix)
                        page.wait_for_timeout(60)
                        got = page.evaluate(rects_js, sels)
                        want = baseline[size][state]
                        for key in sels:
                            checked += 1
                            a, b = got.get(key), want.get(key)
                            if a is None or b is None:
                                problems.append(f"{size} {state} {key}: missing rect {a} vs {b}")
                                continue
                            if any(abs(a[k] - b[k]) > 1.0 for k in ("x", "y", "w", "h")):
                                problems.append(f"{size} {state} {key}: {a} != {b}")
                finally:
                    ctx.close()
        finally:
            browser.close()
    return not problems, problems, f"{checked} rect(s)"


G18_CONTRAST_JS = r"""
() => {
  function parse(str) {
    const m = String(str || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  }
  function blend(fg, bg) {
    if (!fg) return null;
    if (!bg || fg.a >= 1) return fg;
    return {r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1};
  }
  function lum(c) {
    if (!c) return 0;
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function ratio(a, b) {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function bgOf(el) {
    let node = el;
    let acc = null;
    while (node && node.nodeType === 1) {
      const c = parse(getComputedStyle(node).backgroundColor);
      if (c && c.a > 0.01) {
        acc = acc ? blend(acc, c) : c;
        if (c.a >= 0.99) return acc;
      }
      node = node.parentElement;
    }
    return acc || {r: 255, g: 255, b: 255, a: 1};
  }
  function pair(fgEl, bgEl, prop) {
    const fg = parse(getComputedStyle(fgEl)[prop || 'color']);
    const bg = bgOf(bgEl || fgEl);
    return +ratio(blend(fg, bg), bg).toFixed(2);
  }
  const menu = document.getElementById('dropdown-mobile');
  const item = menu ? menu.querySelector('.menu-item') : null;
  const handle = document.getElementById('sheet-handle');
  const grip = document.getElementById('sheet-grip');
  const status = document.getElementById('status-bar');
  const seg = status ? status.querySelector('.status-seg') : null;
  const btn = document.getElementById('mobile-menu-btn');
  return {
    menuText: item ? pair(item) : null,
    menuBorder: menu ? pair(menu, menu, 'borderTopColor') : null,
    handleGrip: handle && grip ? pair(grip, handle) : null,
    handleBorder: handle ? pair(handle, handle, 'borderBottomColor') : null,
    statusText: seg ? pair(seg, status) : null,
    menuButton: btn ? pair(btn, btn) : null
  };
}
"""


def g18_menu_reachability() -> tuple[bool, list[str], str]:
    problems: list[str] = []
    detail: list[str] = []
    menu_js = """(ids) => {
      const out = [];
      ids.forEach(id => {
        const root = document.getElementById(id);
        if (!root) return;
        root.querySelectorAll('.menu-item[data-action]').forEach(el => {
          const group = el.dataset.group
            || (id === 'dropdown-file' ? 'File' : id === 'dropdown-view' ? 'View' : 'Edit');
          const span = el.querySelector('span');
          const key = el.querySelector('.menu-key');
          out.push({group, action: el.dataset.action || '', text: (span || el).textContent.trim(),
                    key: key ? key.textContent.trim() : ''});
        });
      });
      return out;
    }"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(viewport={"width": 1280, "height": 720}, color_scheme="dark",
                                      locale="en-US", reduced_motion="reduce")
            page = ctx.new_page()
            page.goto(BASE_URL + "/index.html", wait_until="load", timeout=30000)
            page.wait_for_timeout(500)
            desktop = page.evaluate(menu_js, ["dropdown-file", "dropdown-view", "dropdown-edit"])
            ctx.close()

            theme_ratios = {}
            for theme in ("dark", "light"):
                ctx, page, errors = mobile_open(browser, 360, 680, theme, True, 0)
                try:
                    if errors:
                        problems.extend(f"{theme} page error: {e}" for e in errors)
                    if page.locator("#mobile-menu-btn").count() == 0:
                        problems.append(f"{theme} 360: mobile menu button missing")
                        continue
                    page.click("#mobile-menu-btn")
                    page.wait_for_timeout(350)
                    visible = page.evaluate("""() => {
                      const dd = document.getElementById('dropdown-mobile');
                      if (!dd) return null;
                      const r = dd.getBoundingClientRect();
                      const items = [];
                      for (const el of dd.querySelectorAll('.menu-item[data-action]')) {
                        el.scrollIntoView({block: 'nearest'});
                        const ir = el.getBoundingClientRect();
                        items.push({action: el.dataset.action, w: ir.width, h: ir.height,
                                    inView: ir.left >= -1 && ir.right <= innerWidth + 1 && ir.top >= -1 && ir.bottom <= innerHeight + 1});
                      }
                      dd.scrollTop = 0;
                      return {left:r.left, right:r.right, top:r.top, bottom:r.bottom,
                              open: dd.classList.contains('open'), items};
                    }""")
                    if not visible or not visible["open"]:
                        problems.append(f"{theme} 360: mobile menu did not open")
                        continue
                    if visible["left"] < -1 or visible["right"] > 361:
                        problems.append(f"{theme} 360: mobile menu outside viewport {visible}")
                    bad = [i for i in visible["items"] if i["h"] < 44 or not i["inView"]]
                    if bad:
                        problems.append(f"{theme} 360: mobile menu items clipped/small {bad[:5]}")
                    mobile = page.evaluate(menu_js, ["dropdown-mobile"])
                    if mobile != desktop:
                        problems.append(f"{theme} 360: reachable menu list differs from desktop: {len(mobile)} vs {len(desktop)}")
                        only_desktop = [d for d in desktop if d not in mobile]
                        only_mobile = [m for m in mobile if m not in desktop]
                        if only_desktop:
                            problems.append(f"  missing on mobile: {only_desktop}")
                        if only_mobile:
                            problems.append(f"  extra on mobile: {only_mobile}")
                    body = page.evaluate(G18_CONTRAST_JS)
                    theme_ratios[theme] = body
                    if body["menuText"] is None or body["menuText"] < 4.5:
                        problems.append(f"{theme} 360: mobile menu text contrast {body['menuText']}")
                    if body["menuBorder"] is None or body["menuBorder"] < 3:
                        problems.append(f"{theme} 360: mobile menu border contrast {body['menuBorder']}")
                    if body["statusText"] is None or body["statusText"] < 4.5:
                        problems.append(f"{theme} 360: status text contrast {body['statusText']}")
                    if body["handleGrip"] is None or body["handleGrip"] < 3:
                        problems.append(f"{theme} 360: sheet grip contrast {body['handleGrip']}")
                    if body["menuButton"] is None or body["menuButton"] < 3:
                        problems.append(f"{theme} 360: menu button icon contrast {body['menuButton']}")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(150)
                finally:
                    ctx.close()
            detail.append(f"desktop items={len(desktop)}")
            detail.append("contrast " + json.dumps(theme_ratios))
        finally:
            browser.close()
    return not problems, problems, " | ".join(detail)


def g19_worker() -> tuple[bool, list[str], str]:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "p2_2_check.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/p2_2_check.py: timed out after 1800s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if "checks," in line and "failure" in line), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/p2_2_check.py exited {proc.returncode}")
    match = re.search(r"(\d+) checks, (\d+) failure", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 6:
        problems.append(f"worker check ran only {checks} checks")
    if "WORKER PASS" not in output:
        problems.append("worker check did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems, detail


def g20_golden() -> tuple[bool, list[str], str]:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "golden_check.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=2400,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/golden_check.py: timed out after 2400s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if line.startswith("GOLDEN CHECK ")), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/golden_check.py exited {proc.returncode}")
    match = re.search(r"GOLDEN CHECK (\d+) cases", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 200:
        problems.append(f"golden check ran only {checks} cases")
    if "GOLDEN PASS" not in output:
        problems.append("golden check did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems, detail


def g21_video_p2_3() -> tuple[bool, list[str], str]:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate" / "video_p2_3_check.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return False, ["tests/gate/video_p2_3_check.py: timed out after 1800s"], ""
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.splitlines()
    summary = next((line for line in reversed(lines) if "checks," in line and "failure" in line), "")
    problems = [line.strip() for line in lines if line.strip().startswith("FAIL ")]
    if proc.returncode != 0:
        problems.insert(0, f"tests/gate/video_p2_3_check.py exited {proc.returncode}")
    match = re.search(r"(\d+) checks, (\d+) failure", summary)
    checks = int(match.group(1)) if match else 0
    if checks < 25:
        problems.append(f"video P2-3 check ran only {checks} checks")
    if "VIDEO P2-3 PASS" not in output:
        problems.append("video P2-3 check did not report PASS")
    elapsed = time.time() - started
    detail = f"{summary or 'no summary'} ({elapsed:.1f}s)"
    return not problems, problems[:40], detail


def main() -> int:
    global BASE_URL
    ensure_fixtures()
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    httpd, BASE_URL, _thread = start_server()
    results: dict[str, dict] = {}

    try:
        ok, violations = g1_token_lint()
        results["G1"] = {"pass": ok, "violations": violations}
        print(("G1 PASS" if ok else "G1 FAIL") + f" token lint: {len(violations)} violation(s)")
        for violation in violations:
            print("  " + violation)

        browser = run_browser_checks()
        g2 = browser["g2"]
        print(("G2 PASS" if g2["pass"] else "G2 FAIL") +
              f" theme parity: {len(g2['violations'])} violation(s), "
              f"{g2['checked']} element/state checks, {g2['cells']} cells, {g2['states']} scans")
        for violation in g2["violations"]:
            print("  " + f"[{violation.get('theme')} {violation.get('width')} {violation.get('state')}] "
                  f"{violation.get('selector')} kind={violation.get('kind')} bg={violation.get('bg')} "
                  f"fg={violation.get('fg')} ratio={violation.get('ratio')} min={violation.get('min')} {violation.get('detail','')}")
        for error in browser["errors"]:
            print("  PAGE ERROR " + error)
        results["G2"] = {"pass": g2["pass"], "violations": g2["violations"]}

        g3 = browser["g3"]
        print(("G3 PASS" if g3["pass"] else "G3 FAIL") + f" screenshots: {len(g3['screenshots'])} captured in docs/evidence/{GATE_TASK}/")
        for path in g3["screenshots"]:
            print("  " + path)
        results["G3"] = {"pass": g3["pass"], "screenshots": g3["screenshots"]}

        g4 = browser["g4"]
        print(("G4 PASS" if g4["pass"] else "G4 FAIL") + " frame timings: " +
              ", ".join(f"{r['theme']} {r['width']}: median={r.get('median')}ms p95={r.get('p95')}ms frames={r.get('frames')}" for r in g4["runs"]))
        results["G4"] = {"pass": g4["pass"], "runs": g4["runs"]}

        g5_ok, g5_problems, g5_detail = g5_existing_tests()
        print(("G5 PASS" if g5_ok else "G5 FAIL") + " existing tests: " + g5_detail)
        for problem in g5_problems:
            print("  " + problem)
        results["G5"] = {"pass": g5_ok, "problems": g5_problems}

        g6_ok, g6_violations = g6_no_arabic()
        print(("G6 PASS" if g6_ok else "G6 FAIL") + f" no Arabic: {len(g6_violations)} violation(s)")
        for violation in g6_violations:
            print("  " + violation)
        results["G6"] = {"pass": g6_ok, "violations": g6_violations}

        print(("G7 PASS" if browser["g7"]["pass"] else "G7 FAIL") + " no Theme item in View menu")
        for cell in browser["g7"]["items"]:
            if cell["items"]:
                print(f"  [{cell['theme']} {cell['width']}] " + json.dumps(cell["items"], ensure_ascii=False))
        results["G7"] = {"pass": browser["g7"]["pass"], "items": browser["g7"]["items"]}

        g8 = browser["g8"]
        print(("G8 PASS" if g8["pass"] else "G8 FAIL") + f" top-bar geometry: {len(g8['violations'])} violation(s)")
        for violation in g8["violations"]:
            print(f"  [{violation['cell']}] {violation['kind']}: {violation['detail']}")
        results["G8"] = {"pass": g8["pass"], "violations": g8["violations"]}

        g9_ok, g9_problems, g9_detail = g9_steppers()
        print(("G9 PASS" if g9_ok else "G9 FAIL") + " numeric steppers: " + g9_detail)
        for problem in g9_problems[:80]:
            print("  " + problem)
        results["G9"] = {"pass": g9_ok, "problems": g9_problems}

        g10_ok, g10_problems, g10_detail = g10_effects()
        print(("G10 PASS" if g10_ok else "G10 FAIL") + " effects: " + g10_detail)
        for problem in g10_problems:
            print("  " + problem)
        results["G10"] = {"pass": g10_ok, "problems": g10_problems}

        g11_ok, g11_problems, g11_detail = g11_compare()
        print(("G11 PASS" if g11_ok else "G11 FAIL") + " compare split: " + g11_detail)
        for problem in g11_problems:
            print("  " + problem)
        results["G11"] = {"pass": g11_ok, "problems": g11_problems}

        g12_ok, g12_problems, g12_detail = g12_load()
        print(("G12 PASS" if g12_ok else "G12 FAIL") + " load: " + g12_detail)
        for problem in g12_problems:
            print("  " + problem)
        results["G12"] = {"pass": g12_ok, "problems": g12_problems}

        g13_ok, g13_problems, g13_detail = g13_video()
        print(("G13 PASS" if g13_ok else "G13 FAIL") + " video: " + g13_detail)
        for problem in g13_problems:
            print("  " + problem)
        results["G13"] = {"pass": g13_ok, "problems": g13_problems}

        g14_ok, g14_problems, g14_detail = g14_mobile_layout()
        print(("G14 PASS" if g14_ok else "G14 FAIL") + " mobile layout: " + " | ".join(g14_detail[:12]))
        for problem in g14_problems[:60]:
            print("  " + problem)
        results["G14"] = {"pass": g14_ok, "problems": g14_problems}

        g15_ok, g15_problems, g15_detail = g15_mobile_gestures()
        print(("G15 PASS" if g15_ok else "G15 FAIL") + " mobile gestures: " + g15_detail)
        for problem in g15_problems[:40]:
            print("  " + problem)
        results["G15"] = {"pass": g15_ok, "problems": g15_problems}

        g16_ok, g16_problems, g16_detail = g16_touch_targets()
        print(("G16 PASS" if g16_ok else "G16 FAIL") + " touch targets: " + g16_detail)
        for problem in g16_problems[:60]:
            print("  " + problem)
        results["G16"] = {"pass": g16_ok, "problems": g16_problems}

        g17_ok, g17_problems, g17_detail = g17_desktop_unchanged()
        print(("G17 PASS" if g17_ok else "G17 FAIL") + " desktop unchanged: " + g17_detail)
        for problem in g17_problems[:40]:
            print("  " + problem)
        results["G17"] = {"pass": g17_ok, "problems": g17_problems}

        g18_ok, g18_problems, g18_detail = g18_menu_reachability()
        print(("G18 PASS" if g18_ok else "G18 FAIL") + " menu reachability: " + g18_detail)
        for problem in g18_problems[:40]:
            print("  " + problem)
        results["G18"] = {"pass": g18_ok, "problems": g18_problems}

        g19_ok, g19_problems, g19_detail = g19_worker()
        print(("G19 PASS" if g19_ok else "G19 FAIL") + " worker: " + g19_detail)
        for problem in g19_problems[:40]:
            print("  " + problem)
        results["G19"] = {"pass": g19_ok, "problems": g19_problems}

        g20_ok, g20_problems, g20_detail = g20_golden()
        print(("G20 PASS" if g20_ok else "G20 FAIL") + " golden outputs: " + g20_detail)
        for problem in g20_problems[:40]:
            print("  " + problem)
        results["G20"] = {"pass": g20_ok, "problems": g20_problems}

        g21_ok, g21_problems, g21_detail = g21_video_p2_3()
        print(("G21 PASS" if g21_ok else "G21 FAIL") + " video P2-3: " + g21_detail)
        for problem in g21_problems[:40]:
            print("  " + problem)
        results["G21"] = {"pass": g21_ok, "problems": g21_problems}
    finally:
        httpd.shutdown()
        httpd.server_close()

    failed = [name for name in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13", "G14", "G15", "G16", "G17", "G18", "G19", "G20", "G21") if not results.get(name, {}).get("pass")]
    print("")
    print("GATE " + ("PASS" if not failed else "FAIL") + " " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
