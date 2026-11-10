# P2-3 A3 golden outputs

`tests/gate/golden_p2_3.json` is the parity contract for every P2-3 change.
It holds **200 exact canvas hashes** on the pre-change tree (`2547d1f`).

## What is hashed

- 132 preview cases: 22 effects x 3 modes x 2 fixed inputs (1080p and 4K).
  Both inputs render at the app preview clamp (1600x900), through the same
  `prepareBase` + `renderToContext` path the app uses.
- 44 native cases: 22 effects x 2 fixed inputs in Effects Only mode, at
  1920x1080 and 3840x2160. This covers the full-size effect path that export
  uses, including `oil` (8.8-13.1 s per native 4K render in the baseline).
- 24 stack cases: 1, 3, 6 and 12 effects x 3 modes x 2 inputs at preview size.

Randomness is seeded, not excluded. `bench_lib` replaces `Math.random` with a
deterministic generator (seed `0x5EED1234`) and resets it before every render.
The five random effects are therefore part of the contract:

`glitch`, `vhs`, `pixelsort`, `grain`, `matrix`.

Excluded cases: **none**.

## Determinism evidence

| Run | Cases | Result | Log |
|---|---:|---|---|
| `golden_gen.py` (200-case set) | 200 | wrote file, exit 0 | `golden-gen.log` |
| `golden_check.py` after generation | 200 | 0 problems, 200/200 exact, exit 0 | `golden-check.log` |
| Earlier 156-case preview-only set, two independent checks | 156 | exact both times | `golden-check-preview-only.log` |

Generation and checking are separate browser processes, so the 200-case match
also proves the seed and page-load ordering are stable across processes.

## Duplicate hashes are real output, not a harness failure

188 of 200 hashes are unique. The duplicates were opened as PNGs
(`golden-probe-*.png`) and explained:

- `*-halftone` equals `*-stack1` in every mode by definition (stack 1 is that
  one effect).
- `1080p-dither-retro` equals `1080p-effects-retro` (and the 4K pair): the
  Retro Palette effect maps the frame onto CGA's four colours, which already
  sit on the dither grid, so Dither has nothing left to change.
- The four `*-stack12` cases collapse to one colour because the mid value of
  the Retro Palette select is CGA and the preceding 12-effect chain is orange
  (mean `[122, 69, 38]`); every orange pixel is nearer CGA black than any other
  CGA colour. That is the app's real output, not a lost render. The 1/3/6
  stacks and every individual effect remain non-degenerate and keep their own
  hashes.
- `1080p-script-stack12` equals `4k-script-stack12` for the same reason: the
  final CGA quantisation removes the remaining source difference. Effects,
  Dither, and all native cases still distinguish the two inputs.

The probe used the same preview path and reproduced the golden hashes exactly
(`4226268613`, `2870267574`, `2656290245`).

## Gate wiring

`tests/gate/run_gate.py` now runs **G20** after G19. G20 executes
`tests/gate/golden_check.py`, requires at least 200 cases, requires
`GOLDEN PASS`, and fails on any `FAIL ` line, non-zero exit, page error, or hash
or size mismatch. The checker rebuilds the case list from the live `EFFECTS`
catalog, so adding, removing or renaming an effect also fails the check and
forces a deliberate regeneration.

A change is kept only if all 200 hashes match exactly (0/255 difference).
