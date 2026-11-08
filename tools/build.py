#!/usr/bin/env python3
"""Glyphcraft source cleanup and publish build.

Python only: no npm packages, no network.

  python tools/build.py --strip app.js effects.js engine.js
      Remove explanatory comments from the given sources in place. Short
      /* --- section --- */ markers stay; code, indentation and blank lines
      are otherwise untouched.

  npm run build
      Write dist/ with the same app, comments removed and whitespace
      collapsed. Sources in git stay readable. Newlines are preserved
      wherever JavaScript's automatic semicolon insertion could depend on
      them; literals (strings, templates, regexes) are copied byte for byte.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SCRIPTS = ("engine.js", "effects.js", "reorder.js", "app.js", "render-worker.js")

SECTION = re.compile(r"^/\*\s*[-=*]{3,}.*[-=*]{3,}\s*\*/$")
INVARIANT = re.compile(r"\b(must|never|do not|only|always|cannot|keep)\b", re.I)
KEYWORDS = {
    "return", "typeof", "case", "in", "of", "new", "delete", "void",
    "throw", "do", "else", "yield", "await", "instanceof",
}


def _regex_allowed(out: str) -> bool:
    s = out.rstrip()
    if not s:
        return True
    if s[-1] in "(,=:[!&|?{};+-*%<>~^":
        return True
    m = re.search(r"([A-Za-z_$][\w$]*)$", s)
    return bool(m and m.group(1) in KEYWORDS)


def _line_start(src: str, i: int) -> int:
    return src.rfind("\n", 0, i) + 1


def _line_end(src: str, i: int) -> int:
    j = src.find("\n", i)
    return len(src) if j < 0 else j


def _scan(src: str) -> list[tuple[str, object]]:
    """Return ('code', text) and ('comment', info) chunks in source order.

    Literals are code. `info` holds start, end, text, line (bool), standalone
    (bool) and group_end (end of a contiguous // run).
    """
    events: list[tuple[str, object]] = []
    tail = ""

    def code(text: str) -> None:
        nonlocal tail
        events.append(("code", text))
        tail = (tail + text)[-160:]

    def push(info: dict) -> None:
        events.append(("comment", info))

    i, n = 0, len(src)
    stack = [{"kind": "code", "brace": 0, "interp": False}]
    while i < n:
        ctx = stack[-1]
        if ctx["kind"] == "template":
            c = src[i]
            if c == "`":
                code(c)
                i += 1
                stack.pop()
            elif c == "\\":
                code(src[i:i + 2])
                i += 2
            elif src.startswith("${", i):
                code("${")
                i += 2
                stack.append({"kind": "code", "brace": 0, "interp": True})
            else:
                code(c)
                i += 1
            continue

        c = src[i]
        if src.startswith("//", i):
            ls = _line_start(src, i)
            standalone = src[ls:i].strip() == ""
            group_end = _line_end(src, i)
            push({
                "start": i, "end": group_end, "text": src[i:group_end],
                "line": True, "standalone": standalone, "group_end": group_end,
            })
            i = group_end
            continue

        if src.startswith("/*", i):
            close = src.find("*/", i + 2)
            end = n if close < 0 else close + 2
            ls = _line_start(src, i)
            standalone = (src[ls:i].strip() == ""
                          and src[end:_line_end(src, end)].strip() == "")
            push({
                "start": i, "end": end, "text": src[i:end],
                "line": False, "standalone": standalone, "group_end": end,
            })
            i = end
            continue

        if c in ("'", '"'):
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    j += 1
                    break
                j += 1
            code(src[i:j])
            i = j
            continue
        if c == "`":
            code(c)
            i += 1
            stack.append({"kind": "template"})
            continue
        if c == "/":
            if _regex_allowed(tail):
                j = i + 1
                in_class = False
                while j < n:
                    ch = src[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        j += 1
                        while j < n and src[j].isalpha():
                            j += 1
                        break
                    elif ch == "\n":
                        break
                    j += 1
                code(src[i:j])
                i = j
            else:
                code(c)
                i += 1
            continue
        if c == "{":
            ctx["brace"] += 1
        elif c == "}":
            if ctx["interp"] and ctx["brace"] == 0:
                code(c)
                i += 1
                stack.pop()
                continue
            ctx["brace"] -= 1
        code(c)
        i += 1
    return events


def _keep_comment(info: dict, keep_invariants: bool) -> bool:
    text = info["text"]
    if info["line"]:
        marker = text.lstrip("/ \t")
        return bool(re.match(r"[-=*]{3,}", marker) or
                    (keep_invariants and bool(INVARIANT.search(text))))
    compact = text.replace("\n", " ").strip()
    return bool(SECTION.match(compact)
                or (keep_invariants and INVARIANT.search(compact)))


def strip_comments(src: str, keep_invariants: bool) -> str:
    """Remove comments from source text, leaving code and layout intact."""
    out: list[str] = []
    pos = 0
    for kind, chunk in _scan(src):
        if kind == "code":
            continue
        info = chunk
        if info["standalone"]:
            ls = _line_start(src, info["start"])
            le = _line_end(src, info["end"])
            if le < len(src):
                le += 1
            if ls < pos:
                continue
            if _keep_comment(info, keep_invariants):
                out.append(src[pos:le])
            else:
                out.append(src[pos:ls])
            pos = le
        else:
            out.append(src[pos:info["start"]])
            if _keep_comment(info, keep_invariants):
                out.append(info["text"])
            elif "\n" in info["text"]:
                out.append("\n")
            else:
                out.append(" ")
            pos = info["end"]
    out.append(src[pos:])
    return "".join(out)


def minify(src: str) -> str:
    """Remove all comments and collapse whitespace, preserving literals."""
    out: list[str] = []
    pending = ""
    i, n = 0, len(src)
    stack = [{"kind": "code", "brace": 0, "interp": False}]

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        if out:
            out.append("\n" if "\n" in pending else " ")
        pending = ""

    def emit(text: str) -> None:
        flush()
        out.append(text)

    while i < n:
        ctx = stack[-1]
        if ctx["kind"] == "template":
            c = src[i]
            if c == "`":
                emit(c)
                i += 1
                stack.pop()
            elif c == "\\":
                emit(src[i:i + 2])
                i += 2
            elif src.startswith("${", i):
                emit("${")
                i += 2
                stack.append({"kind": "code", "brace": 0, "interp": True})
            else:
                emit(c)
                i += 1
            continue

        c = src[i]
        if src.startswith("//", i):
            i = _line_end(src, i)
            pending += "\n"
            continue
        if src.startswith("/*", i):
            close = src.find("*/", i + 2)
            end = n if close < 0 else close + 2
            pending += "\n" if "\n" in src[i:end] else " "
            i = end
            continue

        if c in ("'", '"'):
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    j += 1
                    break
                j += 1
            emit(src[i:j])
            i = j
            continue
        if c == "`":
            emit(c)
            i += 1
            stack.append({"kind": "template"})
            continue
        if c == "/":
            if not _regex_allowed("".join(out[-160:])):
                emit(c)
                i += 1
                continue
            j = i + 1
            in_class = False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    j += 1
                    while j < n and src[j].isalpha():
                        j += 1
                    break
                elif ch == "\n":
                    break
                j += 1
            emit(src[i:j])
            i = j
            continue
        if c.isspace():
            pending += c
            i += 1
            continue
        if c == "{":
            ctx["brace"] += 1
        elif c == "}":
            if ctx["interp"] and ctx["brace"] == 0:
                emit(c)
                i += 1
                stack.pop()
                continue
            ctx["brace"] -= 1
        emit(c)
        i += 1
    return "".join(out)


def check_js(path: Path) -> None:
    result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"node --check failed for {path}:\n{result.stderr}")


def strip_sources(paths: list[str]) -> int:
    for name in paths:
        path = (ROOT / name).resolve()
        source = path.read_text(encoding="utf-8")
        cleaned = strip_comments(source, keep_invariants=False)
        path.write_text(cleaned, encoding="utf-8")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tmp:
            tmp.write(cleaned)
            tmp_path = Path(tmp.name)
        try:
            check_js(tmp_path)
        finally:
            tmp_path.unlink()
        print(f"strip {name}: {len(source)} -> {len(cleaned)} bytes")
    return 0


def minify_css(text: str) -> str:
    out = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            out.append(c)
            i += 1
            continue
        if text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = n if close < 0 else close + 2
            out.append(" ")
            continue
        if c.isspace():
            j = i
            had_newline = False
            while j < n and text[j].isspace():
                had_newline = had_newline or text[j] == "\n"
                j += 1
            out.append("\n" if had_newline else " ")
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out).strip() + "\n"


def build() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    total_before = total_after = 0
    for name in SCRIPTS:
        source = (ROOT / name).read_text(encoding="utf-8")
        built = minify(source)
        target = DIST / (Path(name).stem + ".min.js")
        target.write_text(built, encoding="utf-8")
        check_js(target)
        total_before += len(source)
        total_after += len(built)
        print(f"{name}: {len(source)} -> {len(built)} bytes")
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    css_min = minify_css(css)
    (DIST / "style.min.css").write_text(css_min, encoding="utf-8")
    print(f"style.css: {len(css)} -> {len(css_min)} bytes")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="style.css"', 'href="style.min.css"')
    for name in SCRIPTS:
        html = html.replace(f'src="{name}"', f'src="{Path(name).stem}.min.js"')
    (DIST / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(ROOT / "assets", DIST / "assets")
    print(f"dist/ ready: JS {total_before} -> {total_after} bytes, "
          f"{len(list(DIST.rglob('*')))} paths")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "--strip":
        return strip_sources(argv[2:] or ["app.js", "effects.js", "engine.js"])
    return build()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
