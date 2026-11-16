#!/usr/bin/env python3
"""Generate classic-script builds of the vendored muxers.

Dynamic `import()` of a file URL is blocked by the browser on `file://`
(origin "null"), so the app loads the muxers as classic scripts and reads a
window global instead. The only change to the upstream file is the final ESM
`export { ... }` block, replaced by that global.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUXERS = {
    "mp4-muxer.mjs": ("mp4-muxer.js", "Mp4Muxer"),
    "webm-muxer.mjs": ("webm-muxer.js", "WebmMuxer"),
}
HEADER = """/*
 * {source} — MIT, see {license}.
 * Generated from {source} by tools/vendor_muxers.py; do not edit.
 * Wrapped in an IIFE and the ESM export block is replaced by
 * window.{global_name}, so the file loads as a classic script (including from
 * file://) without its top-level names colliding with the other muxer.
 */
"""


def convert(source: Path, target: Path, global_name: str) -> None:
    text = source.read_text()
    match = re.search(r"export \{\n(.*?)\n\};", text, re.S)
    if not match:
        raise SystemExit(f"{source}: no ESM export block found")
    names = [name.strip() for name in match.group(1).split(",") if name.strip()]
    body = "(function () {\n" + text[: match.start()] + \
        f"window.{global_name} = {{ {', '.join(names)} }};\n" + "})();\n"
    header = HEADER.format(source=source.name,
                           license=source.name.replace(".mjs", ".LICENSE.txt"),
                           global_name=global_name)
    target.write_text(header + body)


def main() -> int:
    for source_name, (target_name, global_name) in MUXERS.items():
        source = ROOT / "vendor" / source_name
        target = ROOT / "vendor" / target_name
        convert(source, target, global_name)
        print(f"{source_name} -> {target_name} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
