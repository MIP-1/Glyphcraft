# P2-2 session start

This file is the full prompt for this session. Read all of it before doing anything, then follow it in order.
This file is untracked in git. That is expected; include it in your first commit.

## Step 0: Skills

Load skills: using-rigor-skills, rigor-gate, verify-before-claim, root-cause-debugging, test-first, perf-measure, code-audit, ui-visual-audit, namethatui, performance-optimization, webapp-testing, improve-codebase-architecture, tmux.

- Load them by name, no @ mentions.
- If a skill is missing, skip it and tell me. Install nothing.
- `improve-codebase-architecture` is advice only: do not refactor anything outside P2-2.

## Step 1: Evidence first

Part M is closed (HEAD 4cc993d, tags M1-1-pass and M1-2-pass). Git and the code are the source of truth, not memory files. If this file disagrees with git, git wins.

Run:

- `git status -sb`
- `git log -5 --oneline`
- `git tag --list "*-pass"`
- `npm run build`
- `python tools/dist_smoke.py`

If anything is dirty, ahead of origin or failing, fix it and report it before anything else. The last report said build and dist_smoke "previously passed", so run them again now.

## Step 2: P2-2 (Worker + OffscreenCanvas)

Source spec: `docs/prompts/part2_performance_core.md`.

1. Write the acceptance check first and see it RED.
2. Implement.
3. Run the full gate 3 times in a row, in the background, using tmux. Never interrupt a run (about 25 minutes each).
4. Open every screenshot and describe it.
5. List at least 5 break-it cases and test them.
6. Record everything in `docs/GATE.md`.
7. One commit and the tag `P2-2-pass`.

## Rules

- Never weaken a test or a threshold. Gate rules may change only when a check measures the machine and not the app: show the numbers first, prefer relative metrics, record it in `docs/GATE.md`.
- Keep G1 to G18 green. The 169 tests: the count may only go up.
- English only, no Arabic anywhere in the repo (G6). All CSS variables stay namespaced `--gc-*`.
- No explanatory comments in app code (short section markers are allowed).
- Optimise by measuring: keep only changes that are measurably faster.
- Three failed attempts on a task means BLOCKED, not a loosened check.
- Do not start P2-3.

## Questions

If you need information from me, ask ONE question at a time with numbered options. The last option must always be "Other: I'll type it". Never ask what you can find out yourself from the repo.

## Finish

Stop after P2-2. Update README.md (current status, Done, Next steps, HUMAN-CHECK, date) and `docs/PROJECT_MEMORY.md`, commit, push the branch and tags, and show `git status -sb` (clean, not ahead) and `git tag --list "*-pass"`.

HUMAN-CHECK, never claim as verified: real-device frame rate, real GPU playback, real Safari.
