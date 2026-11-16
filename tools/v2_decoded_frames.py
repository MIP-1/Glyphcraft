import glob
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/mustafa/glyphcraft")
OUT = Path("/tmp/opencode/v2-matrix")
rows = {}
for path in sorted(glob.glob(str(ROOT / "docs/evidence/v2/matrix-*.json"))):
    name = Path(path).name
    if name == "matrix-decoded.json":
        continue
    browser = "chromium" if "chromium" in name else "firefox"
    for cell in json.load(open(path)):
        if cell["kind"] not in ("matrix", "dist") or cell.get("skipped") or cell.get("error"):
            continue
        ext = "mp4" if cell["format"] == "mp4" else "webm"
        out = OUT / browser / f"{cell['name']}.{ext}"
        if not out.exists():
            print("missing", out)
            continue
        proc = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
            "-show_entries", "stream=nb_read_frames,pix_fmt,width,height,duration",
            "-show_entries", "format=duration", "-of", "json", str(out),
        ], capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        st = data["streams"][0]
        rows[(browser, cell["name"])] = {
            "browser": browser, "cell": cell["name"],
            "decoded_frames": int(st.get("nb_read_frames") or 0),
            "want_frames": cell["want_frames"],
            "duration": round(float(st.get("duration") or data["format"].get("duration") or 0), 3),
            "want_duration": round(cell["duration"], 3),
            "width": st["width"], "height": st["height"], "pix_fmt": st["pix_fmt"],
            "bytes": out.stat().st_size,
        }

target = ROOT / "docs/evidence/v2/matrix-decoded.json"
rows = sorted(rows.values(), key=lambda r: (r["browser"], r["cell"]))
target.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print(len(rows), "files")
for row in rows:
    ok = abs(row["decoded_frames"] - row["want_frames"]) <= 1
    print(("PASS " if ok else "FAIL ") + f'{row["browser"]:8s} {row["cell"]:38s} '
          f'{row["decoded_frames"]}/{row["want_frames"]} frames {row["duration"]}s '
          f'{row["width"]}x{row["height"]} {row["pix_fmt"]}')
print("evidence:", target)
