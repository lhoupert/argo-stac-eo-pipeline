"""Seed the logbook with deliberate, per-collection gaps (T17).

The seed is just the frozen unit of work run over a window with **holes**: for each mission it
ensures the collection exists, then ingests every day in the window *except* a planted set of gap
offsets. The result is a catalog that looks like a real one mid-backfill — mostly there, with
reproducible missing days. Rung 3 (`find_gaps` + `stages/03-stac-logbook/`) is what later detects
and closes those holes.

Two missions, two distinct regions (Finnish Lapland / Wadden Sea — see `synthetic/world.py`), two
different gap patterns, so the demo is visually separable per collection.

The orchestration here is intentionally thin and dependency-injectable (`ingest_fn`, `ensure_fn`)
so the gap logic is unit-testable without a cluster. `scripts/seed_stac.py` is the CLI shim.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, timedelta

from rich.console import Console

from .config import Config, load_config
from .ingest import ingest_one
from .logbook import ensure_collection
from .synthetic import build_collection
from .synthetic.world import iter_missions

DEFAULT_START = date(2026, 3, 1)
DEFAULT_WINDOW = 14  # days in the seeded window (small enough that `make seed` is quick)

# Planted, reproducible gaps per collection (offsets from DEFAULT_START that are NOT ingested).
# Distinct per mission so the two collections show different holes.
GAP_OFFSETS: dict[str, frozenset[int]] = {
    "synthetic-aurora-veil": frozenset({3, 4, 9}),
    "synthetic-tidal-glass": frozenset({1, 7, 8, 12}),
}

_console = Console()

IngestFn = Callable[[Config, date], dict]
EnsureFn = Callable[[Config, dict], str]


def present_offsets(collection: str, window: int) -> list[int]:
    """Window offsets that ARE seeded for ``collection`` (the planted gaps removed)."""
    gaps = GAP_OFFSETS.get(collection, frozenset())
    return [o for o in range(window) if o not in gaps]


def seed(
    env: Mapping[str, str],
    *,
    start: date = DEFAULT_START,
    window: int = DEFAULT_WINDOW,
    ingest_fn: IngestFn = ingest_one,
    ensure_fn: EnsureFn = ensure_collection,
) -> dict[str, dict]:
    """Seed both missions into the logbook with their planted gaps; return a per-collection summary.

    ``env`` must carry ``STAC_URL`` (you cannot seed a logbook with no catalog). ``ingest_fn`` and
    ``ensure_fn`` are injectable for testing.
    """
    if not (env.get("STAC_URL") or "").strip():
        raise ValueError("seed requires STAC_URL to be set (there is no logbook to seed otherwise)")

    summary: dict[str, dict] = {}
    for mission in iter_missions():
        cid = mission.collection_id
        config = load_config({**env, "COLLECTION": cid})
        ensure_fn(config, build_collection(cid))

        offsets = present_offsets(cid, window)
        for offset in offsets:
            ingest_fn(config, start + timedelta(days=offset))

        gaps = sorted(GAP_OFFSETS.get(cid, frozenset()))
        summary[cid] = {"present": len(offsets), "gaps": gaps}
        _console.print(
            f"[green]✓[/] seeded [bold]{cid}[/] over {mission.region_bbox} — "
            f"{len(offsets)} days, {len(gaps)} planted gap(s) at offsets {gaps}"
        )
    return summary


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(
        prog="eo_ingest.seed", description="Seed the logbook with gaps."
    )
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    args = parser.parse_args(argv)

    seed(env if env is not None else os.environ, start=args.start, window=args.window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
