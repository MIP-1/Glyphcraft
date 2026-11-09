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
- Next: Step 3 — Task A audit/baseline/decisions
