"""Emit a collection's missing days as a JSON array (rung-3 fan-out seam).

`find_gaps` (T18) answers "which days are missing?"; this CLI makes that answer consumable by Argo:
the rung-3 workflow runs `python -m eo_ingest.list_gaps`, captures stdout as the step's result,
and fans `ingest` out over the days printed here. An empty array makes a re-run a clean no-op.

stdout is *only* the JSON array — no rich, no logging on stdout — so `withParam` can parse it.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from datetime import date

from .config import load_config
from .logbook import find_gaps

# Defaults align with the seeded window (eo_ingest.seed) so the workflow can run param-free.
_DEFAULT_START = date(2026, 3, 1)
_DEFAULT_END = date(2026, 3, 14)


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eo_ingest.list_gaps", description="Print a collection's missing days as JSON."
    )
    parser.add_argument("--start", type=date.fromisoformat, default=_DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=_DEFAULT_END)
    parser.add_argument("--max-items", type=int, default=1000)
    args = parser.parse_args(argv)

    config = load_config(env if env is not None else os.environ)
    gaps = find_gaps(config, config.collection, args.start, args.end, max_items=args.max_items)
    print(json.dumps([d.isoformat() for d in gaps]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
