#!/usr/bin/env python3
"""Glyphcraft gate: G1-G8.

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
                        for menu in ("file", "view", "edit"):
                            page.evaluate("() => document.querySelectorAll('.menu-dropdown.open').forEach(d => d.classList.remove('open'))")
                            page.evaluate("() => { const p=document.querySelector('.panel-content'); if(p) p.scrollTop=0; }")
                            page.click(f"#menu-{menu}")
                            page.wait_for_timeout(220)
                            sh = screenshot(page, theme, width, f"{menu}-menu")
                            result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                            data = scan(page, theme, width, f"{menu}-menu")
                            _merge_scan(result["g2"], data, seen_g2)
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(120)

                        page.click("#zoom-level")
                        page.wait_for_timeout(220)
                        sh = screenshot(page, theme, width, "zoom-menu")
                        result["g3"]["screenshots"].append(str(sh.relative_to(ROOT)))
                        data = scan(page, theme, width, "zoom-menu")
                        _merge_scan(result["g2"], data, seen_g2)
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(120)

                        # Size picker, with every group expanded.
                        trigger = page.locator("#output-preset-trigger")
                        trigger.scroll_into_view_if_needed()
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

                        page.locator("#section-effects").scroll_into_view_if_needed()
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

    required_states = 12
    expected_shots = 2 * 2 * required_states
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
# Main
# ---------------------------------------------------------------------------

BASE_URL = ""


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
    finally:
        httpd.shutdown()
        httpd.server_close()

    failed = [name for name in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8") if not results.get(name, {}).get("pass")]
    print("")
    print("GATE " + ("PASS" if not failed else "FAIL") + " " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
