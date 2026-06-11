"""Rung-4 daily report: render the ladder's self-correction at a glance.

Two levels, two sources:
  * SYSTEM level — per-collection **gap heatmaps** from the STAC logbook (`find_gaps`): ⬜ days that
    flip to ✅ as rung 3 refills them.
  * ITEM level   — recent **workflow runs** from the Argo Workflows API (no Prometheus): failed
    attempts that retried and still Succeeded.

The glyphs (✅ present / ⬜ gap) are shape-distinct, so the heatmap is color-blind-safe by
construction. There is **no plugin interface**: the report is a markdown string written to a
documented sink (a file path and/or `rich` stdout). The two data sources are plain functions, so
the whole thing is unit-testable without a cluster; a thin CLI (`python -m eo_ingest.report`) wires
them to the live STAC + Argo for the in-cluster rung (T22).
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from rich.console import Console
from rich.markdown import Markdown

from .config import load_config
from .logbook import find_gaps
from .synthetic.world import iter_missions

_TIMEOUT = 30.0
_PRESENT = "✅"
_GAP = "⬜"
_WEEK = 7


# --- SYSTEM level: gap heatmap -------------------------------------------------------------------
def gap_heatmap(collection: str, start: date, end: date, present: set[date]) -> str:
    """A color-blind-safe calendar grid of present (✅) vs missing (⬜) days for a collection."""
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    gaps = [d for d in days if d not in present]

    rows: list[str] = []
    for i in range(0, len(days), _WEEK):
        cells = [f"{d.day:02d}{_PRESENT if d in present else _GAP}" for d in days[i : i + _WEEK]]
        rows.append("  ".join(cells))
    grid = "\n".join(rows)

    return (
        f"### {collection} — {len(gaps)} gap(s) / {len(days)} days "
        f"({start.isoformat()} → {end.isoformat()})\n\n```\n{grid}\n```"
    )


def present_days(config, collection: str, start: date, end: date) -> set[date]:
    """Days in the window that DO have an item — derived from `find_gaps` so the logic is shared."""
    gaps = set(find_gaps(config, collection, start, end, max_items=(end - start).days + 1 + 1000))
    window = ((end - start).days + 1)
    return {start + timedelta(days=i) for i in range(window)} - gaps


# --- ITEM level: workflow runs from the Argo API -------------------------------------------------
@dataclass(frozen=True)
class Run:
    """A normalized Argo workflow run."""

    name: str
    phase: str
    retried_attempts: int  # failed pod attempts that were retried (item-level self-correction)


def _normalize_run(workflow: dict) -> Run:
    status = workflow.get("status") or {}
    nodes = (status.get("nodes") or {}).values()
    # A failed Pod node inside a run is an attempt that retried (our steps have retryStrategy).
    retried = sum(1 for n in nodes if n.get("type") == "Pod" and n.get("phase") == "Failed")
    return Run(
        name=(workflow.get("metadata") or {}).get("name", "?"),
        phase=status.get("phase", "Unknown"),
        retried_attempts=retried,
    )


def fetch_runs(argo_api_url: str, namespace: str, *, last_n: int = 20) -> list[Run]:
    """Recent workflow runs, preferring the durable archive and degrading to the live list.

    Never raises: if both the archive and the live API are unreachable, returns ``[]`` so the
    report still renders its STAC-sourced half. TLS verification is off because argo-server uses a
    self-signed cert (local demo).
    """
    base = argo_api_url.rstrip("/")
    attempts = (
        (f"{base}/api/v1/archived-workflows", {"listOptions.limit": last_n}),
        (f"{base}/api/v1/workflows/{namespace}", {"listOptions.limit": last_n}),
    )
    for url, params in attempts:
        try:
            resp = httpx.get(url, params=params, timeout=_TIMEOUT, verify=False)
            resp.raise_for_status()
        except httpx.HTTPError:
            continue
        items = resp.json().get("items") or []
        if items:
            return [_normalize_run(w) for w in items]
    return []


def summarize_runs(runs: Sequence[Run]) -> dict[str, int]:
    """Counts that convey item-level self-correction: phases + total retried attempts."""
    return {
        "total": len(runs),
        "succeeded": sum(1 for r in runs if r.phase == "Succeeded"),
        "failed": sum(1 for r in runs if r.phase == "Failed"),
        "retried_attempts": sum(r.retried_attempts for r in runs),
    }


# --- assembly + sink -----------------------------------------------------------------------------
def build_markdown(
    heatmaps: Sequence[str], run_summary: Mapping[str, int], *, generated_at: str
) -> str:
    """Assemble the full report markdown from the two levels."""
    s = run_summary
    lines = [
        "# EO logbook — daily report",
        f"_generated {generated_at}_",
        "",
        "**Two levels of self-correction:** items *retry* (Argo, item-level) and missing days "
        "*refill* (the logbook, system-level).",
        "",
        "## Item level — workflow runs (Argo)",
        f"- {s['total']} recent run(s): **{s['succeeded']} succeeded**, {s['failed']} failed",
        f"- **{s['retried_attempts']} attempt(s) failed then retried** to success",
        "",
        "## System level — gap heatmaps (logbook)",
        "",
        *heatmaps,
        "",
    ]
    return "\n".join(lines)


def report(
    env: Mapping[str, str] | None = None,
    *,
    collections: Sequence[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    argo_api_url: str | None = None,
    namespace: str = "eo",
    out_path: Path | None = None,
    console: Console | None = None,
    now: datetime | None = None,
) -> str:
    """Build the report, print it (rich stdout), optionally write markdown to ``out_path``.

    The sink is just a path — no plugin interface. Returns the markdown string.
    """
    env = env if env is not None else os.environ
    start = start or date(2026, 3, 1)
    end = end or date(2026, 3, 14)
    collections = collections or [m.collection_id for m in iter_missions()]
    argo_api_url = argo_api_url or env.get("ARGO_API_URL", "https://argo-server:2746")
    console = console or Console()

    heatmaps = []
    for collection in collections:
        config = load_config({**env, "COLLECTION": collection})
        present = present_days(config, collection, start, end)
        heatmaps.append(gap_heatmap(collection, start, end, present))

    summary = summarize_runs(fetch_runs(argo_api_url, namespace))
    generated = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    markdown = build_markdown(heatmaps, summary, generated_at=generated)

    console.print(Markdown(markdown))
    if out_path is not None:
        Path(out_path).write_text(markdown)
    return markdown


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eo_ingest.report", description="Render the daily report."
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 3, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 3, 14))
    parser.add_argument("--out", type=Path, default=None, help="write markdown here too")
    args = parser.parse_args(argv)
    report(env, start=args.start, end=args.end, out_path=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
