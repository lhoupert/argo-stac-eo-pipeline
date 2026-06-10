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

from rich.console import Console

from .config import load_config
from .logbook import ensure_collection
from .synthetic import build_collection

_console = Console()


def main(env: Mapping[str, str] | None = None) -> int:
    config = load_config(env)

    if config.source_type != "synthetic":
        _console.print(
            f"[yellow]ensure_collection: source {config.source_type!r} owns its collections — "
            f"nothing to bootstrap[/]"
        )
        return 0

    action = ensure_collection(config, build_collection(config.collection))
    _console.print(f"[green]✓[/] collection [bold]{config.collection}[/] {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
