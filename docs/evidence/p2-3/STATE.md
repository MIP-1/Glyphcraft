# P2-3 STATE

- Branch: `p2-3-work` (from `main` @ 3686017)
- Safety tag: `pre-P2-3` pushed
- Step 1: build exit 0, dist_smoke PASS hash 4135467496, no gate running, tmux absent
- Step 2: P2-2 closeout complete — see `closeout.md`
  - 68/68 run-3 screenshots reviewed; run 1/2 equivalence measured
  - hash difference explained (Depth 80 vs 75)
  - 740 px `data-snap` race explained (index.html:125, app.js:2562-2567)
  - Firefox 157 worker 6/6 checks; long-task API unsupported there (reported)
  - `file://` fallback hash-equal, no errors
  - font OFL licence added; README network sentence corrected
  - build + dist smoke re-run green
- Tag: `P2-2-closeout-pass`
- Step 3 (Task A):
  - A1 audit complete: `docs/evidence/p2-3/audit.md`
  - A2 baseline complete: `baseline.json` + `baseline.log`, all 9 sections,
    no page errors, 132 render rows, 24 stack rows
  - A3 golden complete: 200 cases, seed `0x5EED1234`, no exclusions;
    `tests/gate/golden_p2_3.json`, generator `tests/bench/golden_gen.py`,
    checker `tests/gate/golden_check.py`; two exact check runs
  - G20 wired into `tests/gate/run_gate.py`; standalone G20 PASS 200/200
    exact in 193.5 s (`g20-run.log`)
  - A4 decisions complete: `docs/evidence/p2-3/decisions.md`; no rebuild
    candidate, no owner question needed
- Tag: `P2-3-A-pass`
- Next: Step 4 — Task B video (850 MB limit, native-resolution export),
  checks RED first
