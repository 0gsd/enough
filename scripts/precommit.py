#!/usr/bin/env python3
"""The one command that must be green before every commit.

    uv run python scripts/precommit.py            # everything
    uv run python scripts/precommit.py --quick    # the pre-commit hook's mode
    uv run python scripts/precommit.py --list
    uv run python scripts/precommit.py --only ui
    uv run python scripts/precommit.py --skip harness,ui

It runs, in order, everything CI runs plus the two checks CI cannot:

    bash      bash -n bootstrap.sh llama_server.sh   (macOS bash 3.2 is the floor)
    pytest    the whole suite, including the content-drift guards
    i18n      scripts/i18n_check.py — catalog structure across six languages
    smoke     scripts/smoke_boot.py — a real boot against a scratch project
    harness   tests/bootstrap_linux_harness.sh — the installer, fully shimmed
    ui        scripts/ui_check.py — layout + mode-stack drift in a real browser

Each stage prints one PASS/FAIL/SKIP line with its wall-clock time, and the
exit status is non-zero if any stage failed. A stage that cannot run on this
machine (no browser for the `ui` stage) SKIPs and does not fail the run —
CI has no guarantee of a browser, and a check that could not run is not a
check that failed.

`--quick` is what the git hook uses: it passes `--quick` down to the browser
stage (3 viewports x 3 languages instead of the full matrix), which is the
difference between a commit you wait a minute for and one you wait six for.
`ENOUGH_PRECOMMIT=quick` in the environment does the same thing, which is
how the hook asks without needing to know the flag.

Nothing here writes to the developer's real state: the two stages that boot
a server both go through `smoke_boot.build_env()`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Stage:
    name: str
    blurb: str
    #: argv, as a function of the parsed flags — `quick` is the only one any
    #: stage cares about today.
    argv: tuple[str, ...]
    quick_argv: tuple[str, ...] = ()

    def command(self, *, quick: bool) -> tuple[str, ...]:
        return self.quick_argv if (quick and self.quick_argv) else self.argv


PY = sys.executable

STAGES: tuple[Stage, ...] = (
    Stage("bash", "shell syntax (bash 3.2 floor)",
          ("bash", "-n", "bootstrap.sh", "llama_server.sh")),
    Stage("pytest", "the python suite + content-drift guards",
          (PY, "-m", "pytest", "-q")),
    Stage("i18n", "catalog + help parity across six languages",
          (PY, "scripts/i18n_check.py")),
    Stage("smoke", "a real boot against a scratch project",
          (PY, "scripts/smoke_boot.py")),
    Stage("harness", "bootstrap.sh under shimmed tools",
          ("bash", "tests/bootstrap_linux_harness.sh")),
    Stage("ui", "layout + mode-stack drift in a real browser",
          (PY, "scripts/ui_check.py"),
          (PY, "scripts/ui_check.py", "--quick")),
)

STAGE_NAMES = tuple(s.name for s in STAGES)


def _resolve(argv: tuple[str, ...]) -> tuple[str, ...] | None:
    """Absolute-ise the interpreter/shell so a stage cannot pick up a
    different one than this process is running under. None = unavailable."""
    head = argv[0]
    if head == PY:
        return argv
    found = shutil.which(head)
    return (found, *argv[1:]) if found else None


def run_stage(stage: Stage, *, quick: bool, verbose: bool) -> tuple[str, float, str]:
    """(verdict, seconds, note). Verdict is PASS / FAIL / SKIP."""
    argv = _resolve(stage.command(quick=quick))
    if argv is None:
        return "SKIP", 0.0, f"{stage.command(quick=quick)[0]} is not on PATH"

    started = time.monotonic()
    if verbose:
        proc = subprocess.run(argv, cwd=REPO)
        out = ""
    else:
        proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")
    elapsed = time.monotonic() - started

    if proc.returncode == 0:
        # The browser stage exits 0 both when it ran clean and when it had no
        # browser to run in; only its own output can tell the two apart, and
        # the difference matters to whoever reads this summary.
        if stage.name == "ui" and "SKIPPED" in out:
            return "SKIP", elapsed, "no Chrome/Chromium on this machine"
        return "PASS", elapsed, ""
    if not verbose:
        print(f"\n----- {stage.name} output " + "-" * (46 - len(stage.name)))
        sys.stdout.write(out if out.strip() else "(no output)\n")
        print("-" * 60 + "\n")
    return "FAIL", elapsed, f"exit {proc.returncode}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true",
                    help="the fast matrix for the browser stage")
    ap.add_argument("--only", default="",
                    help=f"comma-separated stages to run ({', '.join(STAGE_NAMES)})")
    ap.add_argument("--skip", default="", help="comma-separated stages to skip")
    ap.add_argument("--list", action="store_true", help="print the stages and exit")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="stream each stage's output instead of capturing it")
    args = ap.parse_args(argv)

    if args.list:
        print("stages, in order:")
        for s in STAGES:
            print(f"  {s.name:<9} {s.blurb}")
        return 0

    quick = args.quick or os.environ.get("ENOUGH_PRECOMMIT", "") == "quick"

    def names(raw: str) -> set[str]:
        out = {n.strip() for n in raw.split(",") if n.strip()}
        unknown = out - set(STAGE_NAMES)
        if unknown:
            raise SystemExit(f"unknown stage(s): {', '.join(sorted(unknown))}\n"
                             f"known: {', '.join(STAGE_NAMES)}")
        return out

    only, skip = names(args.only), names(args.skip)
    todo = [s for s in STAGES
            if (not only or s.name in only) and s.name not in skip]

    print(f"precommit{' --quick' if quick else ''}: "
          f"{len(todo)} stage(s) — {', '.join(s.name for s in todo)}")
    results: list[tuple[Stage, str, float, str]] = []
    started = time.monotonic()
    for stage in todo:
        print(f"\n== {stage.name}: {stage.blurb}", flush=True)
        verdict, elapsed, note = run_stage(stage, quick=quick, verbose=args.verbose)
        results.append((stage, verdict, elapsed, note))
        print(f"{verdict:<5} {stage.name:<9} {elapsed:6.1f}s"
              + (f"  ({note})" if note else ""), flush=True)

    total = time.monotonic() - started
    failed = [s.name for s, v, _e, _n in results if v == "FAIL"]
    print("\n" + "=" * 60)
    for stage, verdict, elapsed, note in results:
        print(f"{verdict:<5} {stage.name:<9} {elapsed:6.1f}s"
              + (f"  ({note})" if note else ""))
    print(f"{'-' * 60}\n{'FAILED' if failed else 'OK'}: {len(results)} stage(s) "
          f"in {total:.1f}s")
    if failed:
        print(f"\nred: {', '.join(failed)}\n"
              f"Re-run one on its own with "
              f"`uv run python scripts/precommit.py --only {failed[0]} -v`.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
