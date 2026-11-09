#!/usr/bin/env python3
import sys, json
from pathlib import Path
import numpy as np
from PIL import Image

def diff(a, b):
    ia = np.asarray(Image.open(a).convert("RGB"), dtype=np.int16)
    ib = np.asarray(Image.open(b).convert("RGB"), dtype=np.int16)
    if ia.shape != ib.shape:
        return {"shape": [list(ia.shape), list(ib.shape)]}
    d = np.abs(ia - ib)
    px = d.max(axis=2)
    over2 = int((px > 2).sum())
    over16 = int((px > 16).sum())
    nz = np.argwhere(px > 0)
    bbox = [int(nz[:,1].min()), int(nz[:,0].min()), int(nz[:,1].max()), int(nz[:,0].max())] if len(nz) else None
    return {"mean": round(float(d.mean()), 4), "max": int(px.max()),
            "px_over_2": over2, "px_over_16": over16,
            "frac_over_2": round(over2 / px.size, 6), "bbox": bbox}

def main(ra, rb, mapping=None):
    a, b = Path(ra), Path(rb)
    names = sorted(p.name for p in a.glob("*.png"))
    rows = []
    for n in names:
        bn = mapping.get(n, n) if mapping else n
        if not (b / bn).exists():
            rows.append({"file": n, "status": "missing-in-b"}); continue
        r = diff(a / n, b / bn)
        r["file"] = n
        rows.append(r)
    rows.sort(key=lambda r: max(r.get("px_over_2", 0), 0), reverse=True)
    print(json.dumps({"a": ra, "b": rb, "files": len(rows), "rows": rows}, indent=1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
