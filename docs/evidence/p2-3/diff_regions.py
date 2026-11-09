#!/usr/bin/env python3
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image

CANVAS = (40, 52, 954, 787)  # x0,y0,x1,y1 preview region at 1280x900

def regions(w, h):
    R = {"topbar": (0,0,w,52), "right": (980,52,w,h), "canvas": (0,52,w,h)}
    if w <= 700:
        R = {"topbar": (0,0,w,118), "sheet": (0,430,w,h), "canvas": (0,118,w,430)}
    return R

def stats(a,b,box):
    x0,y0,x1,y1 = box
    d = np.abs(a[y0:y1,x0:x1].astype(np.int16)-b[y0:y1,x0:x1].astype(np.int16))
    px = d.max(axis=2)
    return {"over2": int((px>2).sum()), "total": int(px.size),
            "frac": round(float((px>2).mean()),6), "max": int(px.max()) if px.size else 0}

def main(ra, rb):
    a,b = Path(ra), Path(rb)
    rows=[]
    for p in sorted(a.glob("*.png")):
        q=b/p.name
        if not q.exists():
            alt = q.with_name(q.name.replace("-half.png","-none.png"))
            q = alt if alt.exists() else q
        if not q.exists():
            rows.append({"file":p.name,"status":"missing"}); continue
        ia=np.asarray(Image.open(p).convert("RGB"))
        ib=np.asarray(Image.open(q).convert("RGB"))
        h,w,_=ia.shape
        r={"file":p.name,"size":[w,h]}
        for name,box in regions(w,h).items(): r[name]=stats(ia,ib,box)
        rows.append(r)
    worst=max(r.get("canvas",{}).get("frac",0) for r in rows)
    chrome=[r["file"] for r in rows if max(r.get("topbar",{}).get("over2",0), r.get("right",r.get("sheet",{})).get("over2",0))>0]
    print(json.dumps({"a":ra,"b":rb,"files":len(rows),"worst_canvas_frac":worst,"chrome_diff_files":chrome,"rows":rows},indent=1))

main(sys.argv[1], sys.argv[2])
