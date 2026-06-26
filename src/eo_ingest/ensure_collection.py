"""Bootstrap the configured collection into the logbook (rung-1 prerequisite).

Wires the synthetic collection doc to the idempotent upsert so a workflow can guarantee the
collection exists *before* the frozen ``ingest`` registers items under it. This deliberately lives
outside ``ingest.py`` (which is byte-frozen from rung 1, AD-2): the unit of work never changed,
the orchestration around it merely ensures its precondition.

Run as ``python -m eo_ingest.ensure_collection``. Synthetic-only: real catalogs (earthsearch)
already own their collections, so for them this is a no-op.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from rich.console import Console

from .config import load_config
from .logbook import ensure_collection
from .stac_source import EARTH_SEARCH_URL
from .synthetic import build_collection

_console = Console()
_TIMEOUT = 30.0


def _earthsearch_collection(collection: str) -> dict:
    """Fetch a real collection definition from Earth Search to mirror into our local logbook."""
    resp = httpx.get(f"{EARTH_SEARCH_URL}/collections/{collection}", timeout=_TIMEOUT)
    resp.raise_for_status()
    doc = resp.json()
    doc["links"] = []  # drop upstream self/parent links; they don't belong in our catalog
    return doc


def main(env: Mapping[str, str] | None = None) -> int:
    config = load_config(env)

    if config.source_type == "synthetic":
        doc = build_collection(config.collection)
    else:
        # Real backend: mirror the upstream collection so register() has somewhere to POST items.
        doc = _earthsearch_collection(config.collection)

    action = ensure_collection(config, doc)
    _console.print(f"[green]✓[/] collection [bold]{config.collection}[/] {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
