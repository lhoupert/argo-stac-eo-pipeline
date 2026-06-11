#!/usr/bin/env python
"""Reset the cluster to a clip's deterministic starting state (T28, part b — SCAFFOLD).

Each screencast (docs/slides/screencast-scripts.md) must re-record identically, which means each
starts from a known state. This orchestrates the existing `make` targets to set that up — it does
*not* re-implement any pipeline logic (the unit of work is frozen and lives in the image).

    python scripts/make_screencast_data.py rung3-gapclose

By default it prints the steps (dry run); pass --run to execute them.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Per-clip setup: the make targets / commands that establish the starting state.
CLIPS: dict[str, list[list[str]]] = {
    # A fresh cluster so the FAIL_ONCE marker is absent → the retry actually fires.
    "rung1-retry": [["make", "down"], ["make", "up"]],
    "rung2-fanout": [["make", "up"]],  # idempotent; backfill is self-contained
    # Plant the gaps rung 3 will close.
    "rung3-gapclose": [["make", "up"], ["make", "seed"]],
    "rung4-report": [["make", "up"]],  # assumes a prior demo or seed has produced history
    "recap": [],  # pure diagram + one command, no cluster state
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make_screencast_data", description=__doc__)
    parser.add_argument("clip", choices=sorted(CLIPS), help="which screencast to prepare")
    parser.add_argument("--run", action="store_true", help="execute the steps (default: dry run)")
    args = parser.parse_args(argv)

    steps = CLIPS[args.clip]
    if not steps:
        print(f"[{args.clip}] no cluster state needed.")
        return 0

    for cmd in steps:
        printable = " ".join(cmd)
        if not args.run:
            print(f"[dry-run] {printable}")
            continue
        print(f"[run] {printable}")
        result = subprocess.run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"step failed: {printable}", file=sys.stderr)
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
