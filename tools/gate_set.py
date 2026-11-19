#!/usr/bin/env python3
"""Run full gate sets until three consecutive runs are valid.

Valid = G1..G21 PASS, G22 failures strictly inside the known V3/V4/V5 set for
that browser, G23 PASS (16 checks). Starts a run only when the machine is quiet
(load < 2.2 for 2 minutes) and the blank-page canary is clean, and aborts a run
when the 1-minute load stays above 8.0 for 3 minutes, so an obviously doomed
50-minute run does not finish.

Each attempt is written to docs/evidence/l1/run-in-progress.log. A valid attempt
becomes gate-run1.log, gate-run2.log then gate-run3.log (exactly three
consecutive valid runs); an invalid one is renamed
attempt-<stamp>-<reason>.log and the streak restarts at 1.

Run it detached so a harness restart cannot kill it:

    systemd-run --user --unit=gc-l1-gate --collect \
      --working-directory=$HOME/glyphcraft \
      python tools/gate_set.py

Progress is appended to docs/evidence/l1/gate-progress.txt.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "evidence" / "l1"
PROGRESS = OUT / "gate-progress.txt"
CANARY = ROOT / "tools" / "machine_canary.py"

CHROME_KNOWN = {
    "video control bar exists",
    "seek bar is a range input",
    "jump buttons meet 44px touch target",
    "size controls are enabled for video",
}
FIREFOX_KNOWN = CHROME_KNOWN | {
    "compare drag stays responsive on a 4K image with 6 effects",
}

QUIET_LOAD = 2.2
ABORT_LOAD = 8.0
ABORT_SAMPLES = 12          # 12 x 15 s = 3 min above ABORT_LOAD
MAX_RUNS = 14
MAX_HOURS = 14


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%dT%H:%M:%S} {msg}"
    print(line, flush=True)
    with PROGRESS.open("a") as fh:
        fh.write(line + "\n")


def load1() -> float:
    return float(Path("/proc/loadavg").read_text().split()[0])


def wait_quiet(deadline: float) -> bool:
    while time.time() < deadline:
        if load1() < QUIET_LOAD:
            time.sleep(120)
            if load1() < QUIET_LOAD:
                canary = subprocess.run([sys.executable, str(CANARY)],
                                        capture_output=True, text=True)
                lines = " | ".join(canary.stdout.strip().splitlines())
                if canary.returncode == 0:
                    log(f"quiet + canary clean: {lines}")
                    return True
                log(f"canary dirty: {lines}")
        time.sleep(60)
    log("quiet wait timed out; starting anyway")
    return False


def run_gate(path: Path) -> tuple[int, str]:
    env = dict(os.environ, GATE_TASK="l1")
    with path.open("w") as fh:
        proc = subprocess.Popen(["npm", "run", "gate"], cwd=ROOT, env=env,
                                stdout=fh, stderr=subprocess.STDOUT,
                                start_new_session=True)
        above = 0
        while proc.poll() is None:
            above = above + 1 if load1() > ABORT_LOAD else 0
            if above >= ABORT_SAMPLES:
                log(f"load {load1():.2f} above {ABORT_LOAD} for 3 min: aborting run")
                os.killpg(proc.pid, signal.SIGTERM)
                time.sleep(10)
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                return proc.wait(), "load-abort"
            time.sleep(15)
    return proc.wait(), "finished"


def classify(path: Path) -> tuple[bool, str]:
    text = path.read_text(errors="replace")
    missing = [f"G{i}" for i in range(1, 22)
               if not re.search(rf"^G{i} PASS", text, re.M)]
    if missing:
        return False, "g1-g21:" + ",".join(missing)
    g23 = re.search(r"^G23 (PASS|FAIL)", text, re.M)
    if not g23 or g23.group(1) != "PASS":
        return False, "g23"
    if not re.search(r"^G22 FAIL", text, re.M):
        return False, "g22-missing"
    bad = []
    for m in re.finditer(r"^\s+(chromium|firefox) FAIL \[[a-z]+\] (.*?):", text, re.M):
        browser, name = m.group(1), m.group(2)
        allowed = CHROME_KNOWN if browser == "chromium" else FIREFOX_KNOWN
        if name not in allowed:
            bad.append(f"{browser}:{name}")
    if bad:
        return False, "g22-unknown:" + ",".join(sorted(set(bad))[:3])
    return True, "valid"


def manifest() -> str:
    cmd = ("find app.js engine.js effects.js reorder.js render-worker.js style.css "
           "index.html tests/gate tests tools -maxdepth 2 -type f "
           "\\( -name '*.js' -o -name '*.py' -o -name '*.css' -o -name '*.html' \\) "
           "-print0 | sort -z | xargs -0 sha256sum")
    return subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True,
                          text=True).stdout


def shots(tag: str) -> tuple[int, str]:
    """Hash the screenshot matrix so three runs can be diffed after the fact.

    The gate rewrites docs/evidence/l1/*.png on every run, so the only way to
    prove two runs are identical outside the live canvas is to snapshot the
    hashes while the files are still that run's. Returns (files, digest).
    """
    files = sorted(OUT.glob("*.png"))
    lines = []
    for path in files:
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    data = "\n".join(lines) + "\n"
    (OUT / f"shots-{tag}.sha256").write_text(data)
    return len(files), hashlib.sha256(data.encode()).hexdigest()[:16]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text("")
    deadline = time.time() + MAX_HOURS * 3600
    valid = runs = 0
    log(f"driver start; load {load1():.2f}; max {MAX_RUNS} runs / {MAX_HOURS} h")
    while valid < 3 and runs < MAX_RUNS and time.time() < deadline:
        runs += 1
        wait_quiet(deadline)
        stamp = f"{datetime.now():%m%d-%H%M}"
        slot = valid + 1
        target = OUT / "run-in-progress.log"
        log(f"attempt {runs} for slot {slot}; load {load1():.2f}")
        started = time.time()
        rc, how = run_gate(target)
        ok, why = classify(target)
        if how == "load-abort":
            ok, why = False, "load-abort"
        minutes = (time.time() - started) / 60
        if ok:
            valid += 1
            final = OUT / f"gate-run{slot}.log"
            shutil.copy(str(target), str(final))
            target.unlink()
            log(f"VALID rc={rc} in {minutes:.0f} min: {valid}/3 consecutive -> {final.name}")
            with (OUT / "gate-runs.txt").open("a") as fh:
                fh.write(f"{final.name} valid ({minutes:.0f} min, load {load1():.2f})\n")
        else:
            shutil.move(str(target), OUT / f"attempt-{stamp}-{why.replace(':', '_')}.log")
            valid = 0
            log(f"INVALID ({why}) rc={rc} in {minutes:.0f} min: streak reset")
            with (OUT / "gate-runs.txt").open("a") as fh:
                fh.write(f"attempt-{stamp} invalid:{why} ({minutes:.0f} min)\n")
        data = manifest()
        (OUT / "code-hashes.txt").write_text(data)
        log(f"manifest sha256 {hashlib.sha256(data.encode()).hexdigest()[:16]} "
            f"files {len(data.splitlines())}")
        shot_tag = f"run{slot}" if ok else f"attempt-{stamp}"
        count, digest = shots(shot_tag)
        log(f"screenshots {count} files sha256 {digest} -> shots-{shot_tag}.sha256")
    log("DONE: three consecutive valid runs" if valid >= 3 else "STOPPED without three valid runs")
    return 0 if valid >= 3 else 2


if __name__ == "__main__":
    sys.exit(main())
